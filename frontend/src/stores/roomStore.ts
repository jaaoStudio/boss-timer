import { defineStore } from 'pinia'
import { useWebSocketStore } from './websocketStore'

export const useRoomStore = defineStore('room', {
  state: () => ({
    roomId: '',
    userCount: 0,
    isConnected: false,
    ws: null,
    isManualDisconnect: false, // 新增手動斷開標誌
  }),
  actions: {
    setRoomId(id) {
      this.roomId = id
    },
    setUserCount(count) {
      this.userCount = count
    },
    setConnected(status) {
      this.isConnected = status
    },
    setWebSocket(websocket) {
      this.ws = websocket
    },
    clearRoomId() {
      this.roomId = ''
    },
    setManualDisconnect(status) { // 新增設定手動斷開標誌的 action
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