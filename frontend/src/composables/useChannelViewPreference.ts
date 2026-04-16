import { ref, watch } from 'vue'
import { useUserStore } from '@/stores/userStore'

export type ChannelViewMode = 'overview' | 'timeline'

const STORAGE_KEY = 'channel-view-mode'
const DEFAULT_MODE: ChannelViewMode = 'overview'

function loadFromStorage(): ChannelViewMode {
  const stored = localStorage.getItem(STORAGE_KEY)
  return (stored === 'overview' || stored === 'timeline') ? stored : DEFAULT_MODE
}

// Singleton — 所有元件共享同一份狀態
const viewMode = ref<ChannelViewMode>(loadFromStorage())

export function useChannelViewPreference() {
  const userStore = useUserStore()

  // 從後端 preferences 初始化（登入後呼叫一次）
  function syncFromUser() {
    const serverValue = userStore.user?.preferences?.channelViewMode
    if (serverValue === 'overview' || serverValue === 'timeline') {
      viewMode.value = serverValue
    }
  }

  // 切換並儲存
  async function setViewMode(mode: ChannelViewMode) {
    viewMode.value = mode
    localStorage.setItem(STORAGE_KEY, mode)
    if (userStore.isLoggedIn) {
      await userStore.updatePreferences({ channelViewMode: mode })
    }
  }

  return { viewMode, setViewMode, syncFromUser }
}
