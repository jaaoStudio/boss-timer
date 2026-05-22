import apiService from '@/services/apiService'
import { useRoomStore } from '@/stores/roomStore'
import { useBossStore } from '@/stores/bossStore'
import { useWebSocketStore } from '@/stores/websocketStore'
import { useRecentRooms } from '@/composables/useRecentRooms'

export class RoomNotFoundError extends Error {
  constructor() {
    super('Room not found')
    this.name = 'RoomNotFoundError'
  }
}

export function useRoomSession() {
  const roomStore = useRoomStore()
  const bossStore = useBossStore()
  const websocketStore = useWebSocketStore()
  const { addRecentRoom } = useRecentRooms()

  async function enter(roomId: string): Promise<void> {
    const roomCheck = await apiService.checkRoomExists(roomId)
    if (!roomCheck.exists) {
      throw new RoomNotFoundError()
    }
    // State mutation only happens after room is confirmed to exist
    roomStore.setRoomId(roomId)
    websocketStore.sendMessage({ type: 'join_room', payload: { room_id: roomId } })
    addRecentRoom(roomId)
    bossStore.startStatusTick()
    // Boss types arrive via WS room_state — no redundant HTTP call needed
  }

  function leave(): void {
    const currentRoomId = roomStore.roomId
    if (currentRoomId) {
      websocketStore.sendMessage({ type: 'leave_room', payload: { room_id: currentRoomId } })
    }
    bossStore.stopStatusTick()
    roomStore.clearRoomId()
    bossStore.clearRoomState()
  }

  return { enter, leave }
}
