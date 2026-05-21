import { useLocalStorage } from '@/composables/useLocalStorage'

interface RecentRoom {
  roomId: string
  lastVisited: string // ISO string
}

const MAX_ROOMS = 5

// Singleton — 跨元件共享，無需 refresh()
const recentRooms = useLocalStorage<RecentRoom[]>('boss-timer-recent-rooms', [])

export function useRecentRooms() {
  function addRecentRoom(roomId: string) {
    const rooms = recentRooms.value.filter(r => r.roomId !== roomId)
    rooms.unshift({ roomId, lastVisited: new Date().toISOString() })
    recentRooms.value = rooms.slice(0, MAX_ROOMS)
  }

  function removeRecentRoom(roomId: string) {
    recentRooms.value = recentRooms.value.filter(r => r.roomId !== roomId)
  }

  function clearAll() {
    recentRooms.value = []
  }

  return { recentRooms, addRecentRoom, removeRecentRoom, clearAll }
}
