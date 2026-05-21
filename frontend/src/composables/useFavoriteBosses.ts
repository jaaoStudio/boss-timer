import { useLocalStorage } from '@/composables/useLocalStorage'
import { useUserStore } from '@/stores/userStore'

const favoriteBossIds = useLocalStorage<number[]>(
  'favorite-boss-ids',
  [],
  (raw) => {
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed.filter((v: unknown) => typeof v === 'number') : []
  },
)

export function useFavoriteBosses() {
  const userStore = useUserStore()

  function isFavorite(id: number): boolean {
    return favoriteBossIds.value.includes(id)
  }

  async function toggleFavorite(id: number) {
    const idx = favoriteBossIds.value.indexOf(id)
    if (idx === -1) {
      favoriteBossIds.value = [...favoriteBossIds.value, id]
    } else {
      favoriteBossIds.value = favoriteBossIds.value.filter((v) => v !== id)
    }
    if (userStore.isLoggedIn) {
      await userStore.updatePreferences({ favoriteBossIds: favoriteBossIds.value })
    }
  }

  function syncFromUser() {
    const serverValue = userStore.user?.preferences?.favoriteBossIds
    if (Array.isArray(serverValue)) {
      favoriteBossIds.value = serverValue.filter((v: unknown) => typeof v === 'number')
    }
  }

  return { favoriteBossIds, isFavorite, toggleFavorite, syncFromUser }
}