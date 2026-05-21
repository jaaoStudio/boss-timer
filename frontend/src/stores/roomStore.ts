import { defineStore } from 'pinia'
import { useWebSocketStore } from './websocketStore'

export const useRoomStore = defineStore('room', {
  state: (): {
    roomId: string
    userCount: number
    isConnected: boolean
    ws: WebSocket | null
    isManualDisconnect: boolean
  } => ({
    roomId: '',
    userCount: 0,
    isConnected: false,
    ws: null,
    isManualDisconnect: false,
  }),
  actions: {
    setRoomId(id: string) {
      this.roomId = id
    },
    setUserCount(count: number) {
      this.userCount = count
    },
    setConnected(status: boolean) {
      this.isConnected = status
    },
    setWebSocket(websocket: WebSocket | null) {
      this.ws = websocket
    },
    clearRoomId() {
      this.roomId = ''
    },
    setManualDisconnect(status: boolean) {
      this.isManualDisconnect = status
    },
    leaveRoomAction() {
      const websocketStore = useWebSocketStore()
      if (this.roomId) {
        websocketStore.sendMessage({
          type: 'leave_room',
          payload: { room_id: this.roomId },
        })
      }
      this.clearRoomId()
    },
  },
})