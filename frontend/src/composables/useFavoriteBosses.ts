import { ref } from 'vue'
import { useUserStore } from '@/stores/userStore'

const STORAGE_KEY = 'favorite-boss-ids'

function loadFromStorage(): number[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (!stored) return []
    const parsed = JSON.parse(stored)
    return Array.isArray(parsed) ? parsed.filter((v) => typeof v === 'number') : []
  } catch {
    return []
  }
}

// Singleton
const favoriteBossIds = ref<number[]>(loadFromStorage())

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
    localStorage.setItem(STORAGE_KEY, JSON.stringify(favoriteBossIds.value))
    if (userStore.isLoggedIn) {
      await userStore.updatePreferences({ favoriteBossIds: favoriteBossIds.value })
    }
  }

  function syncFromUser() {
    const serverValue = userStore.user?.preferences?.favoriteBossIds
    if (Array.isArray(serverValue)) {
      favoriteBossIds.value = serverValue.filter((v: any) => typeof v === 'number')
    }
  }

  return { favoriteBossIds, isFavorite, toggleFavorite, syncFromUser }
}