import { useLocalStorage } from '@/composables/useLocalStorage'
import { useUserStore } from '@/stores/userStore'

export type ChannelViewMode = 'overview' | 'timeline'

const DEFAULT_MODE: ChannelViewMode = 'overview'

const viewMode = useLocalStorage<ChannelViewMode>(
  'channel-view-mode',
  DEFAULT_MODE,
  // 存的是 JSON 字串（useLocalStorage 以 JSON.stringify 寫入），先解開再檢查
  (raw) => {
    const value: unknown = JSON.parse(raw)
    return value === 'overview' || value === 'timeline' ? value : DEFAULT_MODE
  },
)

export function useChannelViewPreference() {
  const userStore = useUserStore()

  function syncFromUser() {
    const serverValue = userStore.user?.preferences?.channelViewMode
    if (serverValue === 'overview' || serverValue === 'timeline') {
      viewMode.value = serverValue
    }
  }

  async function setViewMode(mode: ChannelViewMode) {
    viewMode.value = mode
    if (userStore.isLoggedIn) {
      await userStore.updatePreferences({ channelViewMode: mode })
    }
  }

  return { viewMode, setViewMode, syncFromUser }
}
