// 同一台裝置的分頁之間同步本地偏好（#67）：舊分頁拿著舊值存檔，會把其他分頁剛存的整份清單 / 版面蓋掉
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/stores/websocketStore', () => ({ useWebSocketStore: () => ({ connect: vi.fn(), reconnect: vi.fn() }) }))

// storage 事件只會送到其他分頁，這裡模擬「其他分頁寫入了 localStorage」
function otherTabWrites(key: string, value: string | null) {
  if (value === null) localStorage.removeItem(key)
  else localStorage.setItem(key, value)
  window.dispatchEvent(new StorageEvent('storage', { key, newValue: value, storageArea: localStorage }))
}

// 每次重新載入模組時，上一個測試的 storage 監聽還掛在 window 上：記下來，測完移除，測試之間互不影響
const listeners: [string, EventListenerOrEventListenerObject][] = []
const addEventListener = window.addEventListener.bind(window)

beforeEach(async () => {
  localStorage.clear()
  vi.spyOn(window, 'addEventListener').mockImplementation((type: string, listener: EventListenerOrEventListenerObject, options?: boolean | AddEventListenerOptions) => {
    listeners.push([type, listener])
    addEventListener(type, listener, options)
  })
  vi.resetModules()
  const { createPinia, setActivePinia } = await import('pinia')
  setActivePinia(createPinia())
})

afterEach(() => {
  for (const [type, listener] of listeners.splice(0)) window.removeEventListener(type, listener)
  vi.restoreAllMocks()
})

describe('useLocalStorage', () => {
  it('其他分頁改了同一個 key 時跟著更新，其他 key 不影響', async () => {
    const { useLocalStorage } = await import('@/composables/useLocalStorage')
    const ids = useLocalStorage<number[]>('favorite-boss-ids', [])
    otherTabWrites('favorite-boss-ids', '[5]')
    expect(ids.value).toEqual([5])
    otherTabWrites('something-else', '[9]')
    expect(ids.value).toEqual([5])
  })

  it('其他分頁清掉時回到預設值', async () => {
    const { useLocalStorage } = await import('@/composables/useLocalStorage')
    localStorage.setItem('channel-view-mode', '"timeline"')
    const mode = useLocalStorage<string>('channel-view-mode', 'overview')
    otherTabWrites('channel-view-mode', null)
    expect(mode.value).toBe('overview')
  })
})

describe('套用其他分頁的值時不寫回 localStorage', () => {
  it('其他分頁刪掉時不重新寫回', async () => {
    const { useLocalStorage } = await import('@/composables/useLocalStorage')
    localStorage.setItem('favorite-boss-ids', '[1]')
    useLocalStorage<number[]>('favorite-boss-ids', [])
    otherTabWrites('favorite-boss-ids', null)
    await Promise.resolve()
    expect(localStorage.getItem('favorite-boss-ids')).toBeNull()
  })

  it('讀取時會正規化的值，不寫回正規化後的結果（不會再觸發其他分頁一輪）', async () => {
    const { useLocalStorage } = await import('@/composables/useLocalStorage')
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    useLocalStorage<number[]>('favorite-boss-ids', [], (raw) => JSON.parse(raw).filter((v: unknown) => typeof v === 'number'))
    otherTabWrites('favorite-boss-ids', '[1, "x"]')
    setItem.mockClear()
    await Promise.resolve()
    expect(setItem).not.toHaveBeenCalled()
  })

  it('自己改的值照樣寫入', async () => {
    const { useLocalStorage } = await import('@/composables/useLocalStorage')
    const ids = useLocalStorage<number[]>('favorite-boss-ids', [])
    otherTabWrites('favorite-boss-ids', '[1]')
    ids.value = [1, 2]
    await Promise.resolve()
    expect(localStorage.getItem('favorite-boss-ids')).toBe('[1,2]')
  })
})

describe('頻道檢視', () => {
  it('重新開頁時讀回存過的設定（存的是 JSON 字串）', async () => {
    localStorage.setItem('channel-view-mode', JSON.stringify('timeline'))
    const { useChannelViewPreference } = await import('@/composables/useChannelViewPreference')
    expect(useChannelViewPreference().viewMode.value).toBe('timeline')
  })

  it('其他分頁切成時間軸時跟著切換，不會被改回預設值', async () => {
    const { useChannelViewPreference } = await import('@/composables/useChannelViewPreference')
    const { viewMode } = useChannelViewPreference()
    otherTabWrites('channel-view-mode', JSON.stringify('timeline'))
    expect(viewMode.value).toBe('timeline')
  })
})

describe('收藏 Boss：舊分頁存檔不蓋掉其他分頁剛加的收藏', () => {
  it('其他分頁加了收藏後，這個分頁再收藏時以最新的清單為準', async () => {
    const { useFavoriteBosses } = await import('@/composables/useFavoriteBosses')
    const { favoriteBossIds, toggleFavorite } = useFavoriteBosses()
    otherTabWrites('favorite-boss-ids', '[5]')
    await toggleFavorite(3)
    expect(favoriteBossIds.value).toEqual([5, 3])
  })
})

describe('版面', () => {
  const otherLayout = JSON.stringify({ items: [
    { id: 'recordHistory', colSpan: 2, collapsed: false },
    { id: 'controlPanel', colSpan: 2, collapsed: false },
    { id: 'bossInfo', colSpan: 4, collapsed: false },
    { id: 'channelView', colSpan: 4, collapsed: false },
    { id: 'recommendedChannels', colSpan: 4, collapsed: false },
  ] })

  it('其他分頁存了版面時跟著更新', async () => {
    const { useLayoutConfig } = await import('@/composables/useLayoutConfig')
    const { layout } = useLayoutConfig()
    otherTabWrites('boss_tracker_layout', otherLayout)
    expect(layout.value[0].id).toBe('recordHistory')
  })

  it('其他分頁刪掉版面時回到預設版面', async () => {
    localStorage.setItem('boss_tracker_layout', otherLayout)
    const { useLayoutConfig } = await import('@/composables/useLayoutConfig')
    const { layout } = useLayoutConfig()
    expect(layout.value[0].id).toBe('recordHistory')
    otherTabWrites('boss_tracker_layout', null)
    expect(layout.value[0].id).toBe('controlPanel')
  })

  it('正在編輯版面時不蓋掉還沒存的修改', async () => {
    const { useLayoutConfig } = await import('@/composables/useLayoutConfig')
    const { layout, enterEditMode } = useLayoutConfig()
    enterEditMode()
    otherTabWrites('boss_tracker_layout', otherLayout)
    expect(layout.value[0].id).toBe('controlPanel')
  })
})
