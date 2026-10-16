// 同一台裝置的分頁之間同步本地偏好（#67）：舊分頁拿著舊值存檔，會把其他分頁剛存的整份清單 / 版面蓋掉
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('@/stores/websocketStore', () => ({ useWebSocketStore: () => ({ connect: vi.fn(), reconnect: vi.fn() }) }))

// storage 事件只會送到其他分頁，這裡模擬「其他分頁寫入了 localStorage」
function otherTabWrites(key: string, value: string | null) {
  if (value === null) localStorage.removeItem(key)
  else localStorage.setItem(key, value)
  window.dispatchEvent(new StorageEvent('storage', { key, newValue: value, storageArea: localStorage }))
}

beforeEach(async () => {
  localStorage.clear()
  vi.resetModules()
  const { createPinia, setActivePinia } = await import('pinia')
  setActivePinia(createPinia())
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

  it('正在編輯版面時不蓋掉還沒存的修改', async () => {
    const { useLayoutConfig } = await import('@/composables/useLayoutConfig')
    const { layout, enterEditMode } = useLayoutConfig()
    enterEditMode()
    otherTabWrites('boss_tracker_layout', otherLayout)
    expect(layout.value[0].id).toBe('controlPanel')
  })
})
