import { ref, type Ref } from 'vue'

interface RecentRoom {
  roomId: string
  lastVisited: string // ISO string
}

const STORAGE_KEY = 'boss-timer-recent-rooms'
const MAX_ROOMS = 5

function loadRooms(): RecentRoom[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored ? JSON.parse(stored) : []
  } catch {
    return []
  }
}

function saveRooms(rooms: RecentRoom[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(rooms))
}

export function useRecentRooms() {
  const recentRooms: Ref<RecentRoom[]> = ref(loadRooms())

  function addRecentRoom(roomId: string) {
    const rooms = recentRooms.value.filter(r => r.roomId !== roomId)
    rooms.unshift({ roomId, lastVisited: new Date().toISOString() })
    recentRooms.value = rooms.slice(0, MAX_ROOMS)
    saveRooms(recentRooms.value)
  }

  function removeRecentRoom(roomId: string) {
    recentRooms.value = recentRooms.value.filter(r => r.roomId !== roomId)
    saveRooms(recentRooms.value)
  }

  function clearAll() {
    recentRooms.value = []
    saveRooms([])
  }

  function refresh() {
    recentRooms.value = loadRooms()
  }

  return { recentRooms, addRecentRoom, removeRecentRoom, clearAll, refresh }
}
