// ADR-0009 登入同步規則的測試（frontend skill「登入狀態的查詢守則」，#71）。一條規則一組測試
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const api = vi.hoisted(() => ({
  initSession: vi.fn(),
  logout: vi.fn(),
  loginWithGoogle: vi.fn(),
  updateMyPreferences: vi.fn(),
}))
const ws = vi.hoisted(() => ({ connect: vi.fn(), reconnect: vi.fn() }))
const showFailure = vi.hoisted(() => vi.fn())

vi.mock('@/services/apiService', () => ({ default: api }))
vi.mock('@/stores/websocketStore', () => ({ useWebSocketStore: () => ws }))
vi.mock('@/axios/handlingErrors', () => ({ showFailure }))
vi.mock('@/i18n', () => ({ default: { global: { t: (key: string) => key } } }))

type Session =
  | { status: 'authenticated'; user: User }
  | { status: 'anonymous'; anonymous_user_id: string | null }

interface User {
  id: number
  display_name: string | null
  avatar_url: string | null
  preferences: Record<string, unknown>
  is_admin: boolean
}

const userA: User = { id: 1, display_name: 'A', avatar_url: null, preferences: { channelViewMode: 'overview' }, is_admin: false }
const userB: User = { id: 2, display_name: 'B', avatar_url: null, preferences: {}, is_admin: false }
const authed = (user: User): Session => ({ status: 'authenticated', user })
const anon = (id = 'x'): Session => ({ status: 'anonymous', anonymous_user_id: id })

// 每次 /auth/session 都先掛起，由測試決定回答什麼；取消時 signal 會被中斷
interface Pending { signal: AbortSignal; resolve: (s: Session) => void; reject: (e: unknown) => void }
let pending: Pending[]
let sent: unknown[]
let channels: FakeChannel[]

class FakeChannel {
  onmessage: ((event: { data: unknown }) => void) | null = null
  constructor() { channels.push(this) }
  postMessage(message: unknown) { sent.push(message) }
  close() {}
}

const flush = async () => {
  for (let i = 0; i < 5; i++) await new Promise((r) => setTimeout(r, 0))
}

// 回答最早送出、還沒回答的查詢
async function answer(result: Session | Error) {
  await flush()
  const request = pending.shift()
  if (!request) throw new Error('no pending /auth/session request')
  if (result instanceof Error) request.reject(result)
  else request.resolve(result)
  await flush()
}

async function setup() {
  vi.resetModules()
  const { createPinia, setActivePinia } = await import('pinia')
  setActivePinia(createPinia())
  const { useUserStore } = await import('@/stores/userStore')
  return useUserStore()
}

// 開頁並以 first 回答第一次查詢
async function opened(first: Session) {
  const store = await setup()
  const init = store.initializeAuth()
  await answer(first)
  await init
  return store
}

beforeEach(() => {
  pending = []
  sent = []
  channels = []
  localStorage.clear()
  vi.clearAllMocks()
  vi.stubGlobal('BroadcastChannel', FakeChannel)
  vi.spyOn(console, 'error').mockImplementation(() => {})   // 失敗路徑會記錄錯誤，測試輸出不需要
  api.initSession.mockImplementation((signal: AbortSignal) => new Promise((resolve, reject) => {
    pending.push({ signal, resolve, reject })
  }))
  api.logout.mockResolvedValue(undefined)
  api.updateMyPreferences.mockResolvedValue(undefined)
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('1. 開頁：第一次判斷完成才連線，併發初始化只查一次', () => {
  it('第一次判斷完成前不連線，App.vue 與路由守衛同時呼叫只查一次', async () => {
    const store = await setup()
    const first = store.initializeAuth()
    const second = store.initializeAuth()
    await flush()
    expect(api.initSession).toHaveBeenCalledTimes(1)
    expect(ws.connect).not.toHaveBeenCalled()
    await answer(anon())
    await Promise.all([first, second])
    expect(ws.connect).toHaveBeenCalledTimes(1)
  })

  it('第一次判斷失敗也連線，並以 user_info 恢復上次的顯示', async () => {
    localStorage.setItem('user_info', JSON.stringify(userA))
    const store = await setup()
    const init = store.initializeAuth()
    await answer(new Error('network'))
    await init
    expect(ws.connect).toHaveBeenCalledTimes(1)
    expect(store.isLoggedIn).toBe(true)
    expect(store.user?.id).toBe(1)
  })
})

describe('2. cookie 改變時取消進行中的查詢，被取消的結果不套用', () => {
  it('收到其他分頁通知時，改變前送出的查詢被取消、不套用', async () => {
    const store = await opened(anon())
    void store.resyncAfterCookieChange()   // 例如切回分頁觸發的查詢還在進行
    await flush()
    const stale = pending.shift()!
    channels[0].onmessage?.({ data: { type: 'LOGIN' } })   // 其他分頁登入了
    await flush()
    expect(stale.signal.aborted).toBe(true)
    stale.resolve(anon('old'))   // 改變前的回答晚到
    await answer(authed(userA))
    expect(store.user?.id).toBe(1)
    expect(api.initSession).toHaveBeenCalledTimes(3)
  })
})

describe('3. WebSocket 只在身分不同時重連', () => {
  it('查詢成功：身分相同不重連、不同才重連', async () => {
    const store = await opened(anon('x'))
    void store._refetchSession()
    await answer(anon('x'))
    expect(ws.reconnect).not.toHaveBeenCalled()
    void store._refetchSession()
    await answer(authed(userA))
    expect(ws.reconnect).toHaveBeenCalledTimes(1)
  })

  it('查詢失敗：期間沒有登入 / 登出不重連，有才照目前的 cookie 重連', async () => {
    const store = await opened(anon('x'))
    void store._refetchSession()
    await answer(new Error('5xx'))
    expect(ws.reconnect).not.toHaveBeenCalled()
    void store.resyncAfterCookieChange()
    await answer(new Error('5xx'))
    expect(ws.reconnect).toHaveBeenCalledTimes(1)
  })
})

describe('4. 改變 user_info 的分頁負責通知', () => {
  it('從沒有登入變成登入通知 LOGIN，同一個人再次回答不通知', async () => {
    const store = await opened(authed(userA))
    expect(sent).toEqual([expect.objectContaining({ type: 'LOGIN' })])
    void store._refetchSession()
    await answer(authed(userA))
    expect(sent).toHaveLength(1)
  })

  it('換成另一個登入者也通知 LOGIN', async () => {
    const store = await opened(authed(userA))
    void store._refetchSession()
    await answer(authed(userB))
    expect(sent.filter((m) => (m as { type: string }).type === 'LOGIN')).toHaveLength(2)
  })

  it('登入失效（變成匿名）通知 LOGOUT；其他分頁已清掉快取時不再通知', async () => {
    const store = await opened(authed(userA))
    sent = []
    void store._refetchSession()
    await answer(anon())
    expect(sent).toEqual([{ type: 'LOGOUT' }])
    localStorage.removeItem('user_info')   // 快取已是匿名：例如其他分頁先發現了
    void store._refetchSession()
    await answer(anon())
    expect(sent).toHaveLength(1)
  })

  it('user_info 寫不進去時不通知，分頁之間才不會互相觸發', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation((key: string) => {
      if (key === 'user_info') throw new Error('QuotaExceededError')
    })
    const store = await opened(authed(userA))
    expect(store.isLoggedIn).toBe(true)
    expect(sent).toHaveLength(0)
  })
})

describe('5. 判斷失敗不改變登入狀態', () => {
  it('登入中查詢失敗：維持登入、不清快取、不通知', async () => {
    const store = await opened(authed(userA))
    sent = []
    void store._refetchSession()
    await answer(new Error('5xx'))
    expect(store.isLoggedIn).toBe(true)
    expect(localStorage.getItem('user_info')).not.toBeNull()
    expect(sent).toHaveLength(0)
  })
})

describe('6. 帳號偏好只在換人時套用', () => {
  it('第一次登入套用；同一個人的回答保留本地偏好；換人再套用', async () => {
    const store = await opened(authed(userA))
    expect(store.preferencesVersion).toBe(1)
    await store.updatePreferences({ channelViewMode: 'timeline' })
    void store._refetchSession()
    await answer(authed(userA))   // 伺服器帶回的還是存檔前的偏好
    expect(store.user?.preferences.channelViewMode).toBe('timeline')
    expect(store.preferencesVersion).toBe(1)
    void store._refetchSession()
    await answer(authed(userB))
    expect(store.preferencesVersion).toBe(2)
  })

  it('存檔失敗時經 showFailure 提示（全站已處理過的由它略過），本地的修改保留（#66）', async () => {
    const store = await opened(authed(userA))
    const error = new Error('400')
    api.updateMyPreferences.mockRejectedValue(error)
    await store.updatePreferences({ channelViewMode: 'timeline' })
    expect(showFailure).toHaveBeenCalledWith(error, 'settings.preferencesSaveFailed')
    expect(store.user?.preferences.channelViewMode).toBe('timeline')
  })

  it('updatePreferences 先寫本地與 user_info，存檔失敗也不改回', async () => {
    const store = await opened(authed(userA))
    api.updateMyPreferences.mockRejectedValue(new Error('5xx'))
    await store.updatePreferences({ channelViewMode: 'timeline' })
    expect(store.user?.preferences.channelViewMode).toBe('timeline')
    expect(JSON.parse(localStorage.getItem('user_info')!).preferences.channelViewMode).toBe('timeline')
  })
})

describe('6b. 同一台裝置的分頁之間同步偏好（CONTEXT.md「跨裝置同步」）', () => {
  const otherTabWritesUserInfo = (user: User) => {
    localStorage.setItem('user_info', JSON.stringify(user))
    window.dispatchEvent(new StorageEvent('storage', { key: 'user_info', newValue: JSON.stringify(user), storageArea: localStorage }))
  }

  it('其他分頁改了同一個登入者的偏好（例如顯示擊殺紀錄）時跟著更新', async () => {
    const store = await opened(authed(userA))
    otherTabWritesUserInfo({ ...userA, preferences: { ...userA.preferences, showRecordHistory: false } })
    expect(store.user?.preferences.showRecordHistory).toBe(false)
  })

  it('快取換成另一個登入者時不套用（登入者改變由通知與查詢處理）', async () => {
    const store = await opened(authed(userA))
    otherTabWritesUserInfo({ ...userB, preferences: { showRecordHistory: false } })
    expect(store.user?.id).toBe(1)
    expect(store.user?.preferences.showRecordHistory).toBeUndefined()
  })
})

describe('7. 登出：取得匿名身分後才清 user_info 並通知', () => {
  it('畫面先清、快取等查詢回答匿名才清並通知', async () => {
    const store = await opened(authed(userA))
    sent = []
    const logout = store.logout()
    await flush()
    expect(store.isLoggedIn).toBe(false)
    expect(localStorage.getItem('user_info')).not.toBeNull()
    expect(sent).toHaveLength(0)
    await answer(anon())
    await logout
    expect(localStorage.getItem('user_info')).toBeNull()
    expect(sent).toEqual([{ type: 'LOGOUT' }])
  })

  it('登出後的回答仍是登入（換發與登出同時發生）就照它顯示、不通知 LOGOUT', async () => {
    const store = await opened(authed(userA))
    sent = []
    const logout = store.logout()
    await answer(authed(userA))
    await logout
    expect(store.isLoggedIn).toBe(true)
    expect(sent).toHaveLength(0)
  })

  it('/auth/logout 失敗時什麼都不動', async () => {
    const store = await opened(authed(userA))
    api.logout.mockRejectedValue(new Error('5xx'))
    await expect(store.logout()).rejects.toThrow()
    expect(store.isLoggedIn).toBe(true)
  })
})

describe('8. 401：原本顯示登入才當成登入失效，只處理一次', () => {
  it('第一個 401 照登出的順序處理，接著的 401 不處理', async () => {
    const store = await opened(authed(userA))
    expect(store.handleLoginLost()).toBe(true)
    expect(store.isLoggedIn).toBe(false)
    expect(store.handleLoginLost()).toBe(false)
    await answer(anon())
    expect(localStorage.getItem('user_info')).toBeNull()
  })

  it('其他分頁剛登出、正在重新查詢時的 401 不當成登入失效', async () => {
    const store = await opened(authed(userA))
    channels[0].onmessage?.({ data: { type: 'LOGOUT' } })
    expect(store.handleLoginLost()).toBe(false)
    expect(store.isLoggedIn).toBe(true)
  })

  it('顯示匿名時遇到 401，重新查詢一次以清掉失效的登入 cookie', async () => {
    const store = await opened(anon())
    expect(store.handleLoginLost()).toBe(false)
    await flush()
    expect(api.initSession).toHaveBeenCalledTimes(2)
  })
})
