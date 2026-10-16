// 全域錯誤處理的分工（ADR-0009「使用中途遇到 401」、frontend skill「Axios 設定」，#71）
import { beforeEach, describe, expect, it, vi } from 'vitest'
import axios, { type AxiosError } from 'axios'

const router = vi.hoisted(() => ({
  currentRoute: { value: { name: 'BossTracker', meta: {} } as { name: string; meta: Record<string, unknown> } },
  push: vi.fn(),
}))
const userStore = vi.hoisted(() => ({ handleLoginLost: vi.fn() }))
const showMessage = vi.hoisted(() => ({ warning: vi.fn(), error: vi.fn() }))

vi.mock('@/router/index', () => ({
  default: router,
  canAccess: (route: { meta: Record<string, unknown> }) => !route.meta.requiresAuth,
}))
vi.mock('@/stores/userStore', () => ({ useUserStore: () => userStore }))
vi.mock('@/composables/useElementPlus', () => ({ showMessage }))
vi.mock('@/i18n', () => ({ default: { global: { t: (key: string) => key } } }))

const { handleError, isHandledGlobally, isNavigatedGlobally, showFailure } = await import('@/axios/handlingErrors')

const httpError = (status?: number, detail?: unknown) =>
  ({ isAxiosError: true, response: status === undefined ? undefined : { status, data: { detail } } }) as AxiosError

// handleError 一律丟出原本的錯誤；回傳它方便檢查
const handled = async (error: AxiosError) => {
  await expect(handleError(error)).rejects.toBe(error)
  return error
}

beforeEach(() => {
  vi.clearAllMocks()
  router.currentRoute.value = { name: 'BossTracker', meta: {} }
  router.push.mockResolvedValue(undefined)
})

describe('9. 全域只處理呼叫端處理不了的結果，呼叫端的提示不重複', () => {
  it('網路錯誤與 503 跳維護頁、5xx 跳錯誤頁，呼叫端不再提示也不再導頁', async () => {
    for (const [error, page] of [[httpError(), 'Maintenance'], [httpError(503), 'Maintenance'], [httpError(500), 'Error']] as const) {
      router.push.mockClear()
      await handled(error)
      expect(router.push).toHaveBeenCalledWith({ name: page })
      expect(isNavigatedGlobally(error)).toBe(true)
      showFailure(error, 'failed')
      expect(showMessage.error).not.toHaveBeenCalled()
    }
  })

  it('429 一律提示「操作太頻繁」，只有回饋每日上限交給呼叫端', async () => {
    const limited = await handled(httpError(429, 'Rate limit exceeded: 20 per 1 minute'))
    expect(showMessage.warning).toHaveBeenCalledWith('globalErrors.rateLimitExceeded')
    expect(isHandledGlobally(limited)).toBe(true)
    const fromCloudflare = await handled(httpError(429))
    expect(isHandledGlobally(fromCloudflare)).toBe(true)
    const daily = await handled(httpError(429, { code: 'feedback_daily_limit', message: '每日上限' }))
    expect(isHandledGlobally(daily)).toBe(false)
  })

  it('沒處理的錯誤（例如 400）交給呼叫端提示', async () => {
    const error = await handled(httpError(400, 'Invalid Google credential or code'))
    showFailure(error, 'failed')
    expect(showMessage.error).toHaveBeenCalledWith('failed')
  })

  it('呼叫端自己取消的請求不處理', async () => {
    const canceled = new axios.CanceledError() as unknown as AxiosError
    await handled(canceled)
    expect(isHandledGlobally(canceled)).toBe(false)
    expect(router.push).not.toHaveBeenCalled()
  })
})

describe('8. 401 代表登入失效', () => {
  it('原本顯示登入：提示「登入已失效」並回首頁，呼叫端不再提示', async () => {
    userStore.handleLoginLost.mockReturnValue(true)
    const error = await handled(httpError(401))
    expect(showMessage.warning).toHaveBeenCalledWith('globalErrors.sessionExpired')
    expect(router.push).toHaveBeenCalledWith({ name: 'RoomSelection' })
    showFailure(error, 'failed')
    expect(showMessage.error).not.toHaveBeenCalled()
  })

  it('不是登入失效的 401（已是匿名、正在重新查詢）交給呼叫端', async () => {
    userStore.handleLoginLost.mockReturnValue(false)
    const error = await handled(httpError(401))
    expect(showMessage.warning).not.toHaveBeenCalled()
    expect(router.push).not.toHaveBeenCalled()
    expect(isHandledGlobally(error)).toBe(false)
  })

  it('需要登入的頁面由 App.vue 跳頁，interceptor 不重複跳', async () => {
    userStore.handleLoginLost.mockReturnValue(true)
    router.currentRoute.value = { name: 'MaintenanceAdmin', meta: { requiresAuth: true } }
    await handled(httpError(401))
    expect(router.push).not.toHaveBeenCalled()
  })

  it('跳往維護頁的導頁還在進行時，晚到的 401 不蓋掉它', async () => {
    userStore.handleLoginLost.mockReturnValue(true)
    let finish!: () => void
    router.push.mockReturnValue(new Promise<void>((resolve) => { finish = resolve }))   // 維護頁還在載入
    await handled(httpError())
    router.push.mockClear()
    await handled(httpError(401))
    expect(router.push).not.toHaveBeenCalled()
    // 讓跳頁完成：handlingErrors 的「跳頁進行中」是模組層級狀態，不清掉會影響之後的測試
    finish()
    await new Promise((r) => setTimeout(r, 0))
  })
})
