import { useLocalStorage } from '@/composables/useLocalStorage'
import { useUserStore } from '@/stores/userStore'

export type ChannelViewMode = 'overview' | 'timeline'

const DEFAULT_MODE: ChannelViewMode = 'overview'

const viewMode = useLocalStorage<ChannelViewMode>(
  'channel-view-mode',
  DEFAULT_MODE,
  (raw) => (raw === 'overview' || raw === 'timeline') ? raw as ChannelViewMode : DEFAULT_MODE,
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
