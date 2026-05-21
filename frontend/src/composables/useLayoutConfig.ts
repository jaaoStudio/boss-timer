import { ref } from 'vue'
import { useUserStore } from '@/stores/userStore'

export type LayoutItemId = 'controlPanel' | 'bossInfo' | 'channelView' | 'recommendedChannels' | 'recordHistory'

export interface LayoutItem {
  id: LayoutItemId
  colSpan: 1 | 2 | 3 | 4
  collapsed: boolean
}

const STORAGE_KEY = 'boss_tracker_layout'
const PREFERENCE_KEY = 'bossTrackerLayout'

const DEFAULT_ITEMS: LayoutItem[] = [
  { id: 'controlPanel', colSpan: 4, collapsed: false },
  { id: 'bossInfo', colSpan: 4, collapsed: false },
  { id: 'channelView', colSpan: 4, collapsed: false },
  { id: 'recommendedChannels', colSpan: 4, collapsed: false },
  { id: 'recordHistory', colSpan: 4, collapsed: false },
]

const REQUIRED_IDS: LayoutItemId[] = ['controlPanel', 'bossInfo', 'channelView', 'recommendedChannels', 'recordHistory']

export const MIN_COL_SPAN: Record<LayoutItemId, 1 | 2> = {
  controlPanel:        1,
  bossInfo:            2,
  channelView:         2,
  recommendedChannels: 2,
  recordHistory:       2,
}

function isValidItems(data: unknown): data is LayoutItem[] {
  if (!Array.isArray(data) || data.length === 0) return false
  const ids = new Set(data.map((i: unknown) => (i as { id?: unknown })?.id))
  return REQUIRED_IDS.every(id => ids.has(id))
}

/**
 * Migrate old layout format (colSpan 1|2, no collapsed) to new format (colSpan 1-4, collapsed).
 * Old colSpan 2 (full width in 2-col grid) → 4 (full width in 4-col grid)
 * Old colSpan 1 (half width in 2-col grid) → 2 (half width in 4-col grid)
 */
function migrateItem(item: unknown): LayoutItem {
  const raw = item as Record<string, unknown>
  let colSpan = (raw.colSpan as number) ?? 4
  if (raw.collapsed === undefined && colSpan <= 2) {
    colSpan = colSpan === 2 ? 4 : 2
  }
  const min = MIN_COL_SPAN[raw.id as LayoutItemId] ?? 1
  colSpan = Math.max(min, Math.min(4, colSpan)) as 1 | 2 | 3 | 4
  return {
    id: raw.id as LayoutItemId,
    colSpan: colSpan as 1 | 2 | 3 | 4,
    collapsed: (raw.collapsed as boolean) ?? false,
  }
}

function parseStored(raw: string | null): { items?: unknown } | null {
  if (!raw) return null
  try {
    return JSON.parse(raw)
  } catch {
    return null
  }
}

// Singleton — 跨元件共享，第一次 call useLayoutConfig() 時初始化
const layout = ref<LayoutItem[]>([])
const isEditMode = ref(false)
let initialized = false

export function useLayoutConfig() {
  const userStore = useUserStore()

  if (!initialized) {
    initialized = true
    layout.value = loadItems()
  }

  function loadItems(): LayoutItem[] {
    let source: { items?: unknown } | null = null

    if (userStore.isLoggedIn && userStore.user?.preferences?.[PREFERENCE_KEY]) {
      source = userStore.user.preferences[PREFERENCE_KEY] as { items?: unknown }
    } else {
      source = parseStored(localStorage.getItem(STORAGE_KEY))
    }

    if (isValidItems(source?.items)) {
      return (source!.items as unknown[]).map(i => migrateItem(i))
    }
    return DEFAULT_ITEMS.map(i => ({ ...i }))
  }

  // 登入後將後端 preferences 同步到本地 layout（由 App.vue watch isLoggedIn 呼叫）
  function syncFromUser() {
    const prefs = userStore.user?.preferences?.[PREFERENCE_KEY] as { items?: unknown } | undefined
    if (!prefs) return
    if (isValidItems(prefs.items)) {
      layout.value = (prefs.items as unknown[]).map(i => migrateItem(i))
    }
  }

  async function saveLayout() {
    const data = { items: layout.value.map(i => ({ ...i })) }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
    if (userStore.isLoggedIn) {
      try {
        await userStore.updatePreferences({ [PREFERENCE_KEY]: data })
      } catch {
        // localStorage 已更新；server sync 失敗不影響本地使用
      }
    }
  }

  function moveItem(from: number, to: number) {
    const len = layout.value.length
    if (from < 0 || to < 0 || from >= len || to >= len || from === to) return
    const items = [...layout.value]
    const [moved] = items.splice(from, 1)
    items.splice(to, 0, moved)
    layout.value = items
  }

  function increaseColSpan(id: LayoutItemId) {
    const item = layout.value.find(i => i.id === id)
    if (item && item.colSpan < 4) {
      item.colSpan = (item.colSpan + 1) as 1 | 2 | 3 | 4
    }
  }

  function decreaseColSpan(id: LayoutItemId) {
    const item = layout.value.find(i => i.id === id)
    const min = MIN_COL_SPAN[id]
    if (item && item.colSpan > min) {
      item.colSpan = (item.colSpan - 1) as 1 | 2 | 3 | 4
    }
  }

  function toggleCollapsed(id: LayoutItemId) {
    const item = layout.value.find(i => i.id === id)
    if (item) item.collapsed = !item.collapsed
    saveLayout().catch(() => {})
  }

  function enterEditMode() {
    isEditMode.value = true
  }

  function exitEditMode() {
    isEditMode.value = false
    saveLayout().catch(() => {})
  }

  function resetLayout() {
    layout.value = DEFAULT_ITEMS.map(i => ({ ...i }))
  }

  return {
    layout,
    isEditMode,
    moveItem,
    increaseColSpan,
    decreaseColSpan,
    toggleCollapsed,
    enterEditMode,
    exitEditMode,
    resetLayout,
    syncFromUser,
  }
}