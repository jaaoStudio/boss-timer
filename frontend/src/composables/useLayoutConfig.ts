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
  bossInfo:            1,
  channelView:         2,
  recommendedChannels: 2,
  recordHistory:       2,
}

function isValidItems(data: unknown): data is LayoutItem[] {
  if (!Array.isArray(data) || data.length === 0) return false
  const ids = new Set(data.map((i: any) => i?.id))
  return REQUIRED_IDS.every(id => ids.has(id))
}

/**
 * Migrate old layout format (colSpan 1|2, no collapsed) to new format (colSpan 1-4, collapsed).
 * Old colSpan 2 (full width in 2-col grid) → 4 (full width in 4-col grid)
 * Old colSpan 1 (half width in 2-col grid) → 2 (half width in 4-col grid)
 */
function migrateItem(item: any): LayoutItem {
  let colSpan = item.colSpan ?? 4
  // Detect old format: colSpan was 1 or 2 in a 2-column system
  // If colSpan <= 2 and no collapsed field exists, it's likely old format
  if (item.collapsed === undefined && colSpan <= 2) {
    colSpan = colSpan === 2 ? 4 : 2
  }
  // Clamp to valid range, respecting per-item minimum
  const min = MIN_COL_SPAN[item.id as LayoutItemId] ?? 1
  colSpan = Math.max(min, Math.min(4, colSpan)) as 1 | 2 | 3 | 4
  return {
    id: item.id,
    colSpan,
    collapsed: item.collapsed ?? false,
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

export function useLayoutConfig() {
  const userStore = useUserStore()

  function loadItems(): LayoutItem[] {
    let source: { items?: unknown } | null = null

    if (userStore.isLoggedIn && userStore.user?.preferences?.[PREFERENCE_KEY]) {
      source = userStore.user.preferences[PREFERENCE_KEY]
    } else {
      source = parseStored(localStorage.getItem(STORAGE_KEY))
    }

    if (isValidItems(source?.items)) {
      return source!.items.map(i => migrateItem(i))
    }
    return DEFAULT_ITEMS.map(i => ({ ...i }))
  }

  const layout = ref<LayoutItem[]>(loadItems())
  const isEditMode = ref(false)

  async function saveLayout() {
    const data = { items: layout.value.map(i => ({ ...i })) }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
    if (userStore.isLoggedIn) {
      await userStore.updatePreferences({ [PREFERENCE_KEY]: data })
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
    // Persist immediately so collapse state survives without entering edit mode
    saveLayout()
  }

  function enterEditMode() {
    isEditMode.value = true
  }

  function exitEditMode() {
    isEditMode.value = false
    saveLayout()
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
  }
}