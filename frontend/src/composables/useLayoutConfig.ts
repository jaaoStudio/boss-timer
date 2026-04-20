import { ref } from 'vue'
import { useUserStore } from '@/stores/userStore'

export type LayoutItemId = 'controlPanel' | 'bossInfo' | 'channelView' | 'recommendedChannels' | 'recordHistory'

export interface LayoutItem {
  id: LayoutItemId
  colSpan: 1 | 2
}

const STORAGE_KEY = 'boss_tracker_layout'
const PREFERENCE_KEY = 'bossTrackerLayout'

const DEFAULT_ITEMS: LayoutItem[] = [
  { id: 'controlPanel', colSpan: 2 },
  { id: 'bossInfo', colSpan: 2 },
  { id: 'channelView', colSpan: 2 },
  { id: 'recommendedChannels', colSpan: 2 },
  { id: 'recordHistory', colSpan: 2 },
]

const REQUIRED_IDS: LayoutItemId[] = ['controlPanel', 'bossInfo', 'channelView', 'recommendedChannels', 'recordHistory']

function isValidItems(data: unknown): data is LayoutItem[] {
  if (!Array.isArray(data) || data.length === 0) return false
  const ids = new Set(data.map((i: any) => i?.id))
  return REQUIRED_IDS.every(id => ids.has(id))
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

    return isValidItems(source?.items)
      ? source!.items.map(i => ({ ...i }))
      : DEFAULT_ITEMS.map(i => ({ ...i }))
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

  function toggleColSpan(id: LayoutItemId) {
    const item = layout.value.find(i => i.id === id)
    if (item) item.colSpan = item.colSpan === 2 ? 1 : 2
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
    toggleColSpan,
    enterEditMode,
    exitEditMode,
    resetLayout,
  }
}