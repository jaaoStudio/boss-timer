import { defineStore } from 'pinia'

export const useRoomStore = defineStore('room', {
  state: () => ({
    roomId: localStorage.getItem('roomId') || '',
    userCount: 0,
    isConnected: false,
    ws: null,
    isManualDisconnect: false, // 新增手動斷開標誌
  }),
  actions: {
    setRoomId(id) {
      this.roomId = id
      localStorage.setItem('roomId', id)
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
      localStorage.removeItem('roomId')
    },
    setManualDisconnect(status) { // 新增設定手動斷開標誌的 action
      this.isManualDisconnect = status
    },
  },
})