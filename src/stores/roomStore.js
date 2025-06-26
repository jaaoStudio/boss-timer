import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useRoomStore = defineStore('room', () => {
  const roomId = ref(localStorage.getItem('roomId') || '')
  const userCount = ref(0)
  const isConnected = ref(false)
  const ws = ref(null)

  const setRoomId = (id) => {
    roomId.value = id
    localStorage.setItem('roomId', id)
  }

  const setUserCount = (count) => {
    userCount.value = count
  }

  const setConnected = (status) => {
    isConnected.value = status
  }

  const setWebSocket = (websocket) => {
    ws.value = websocket
  }

  const clearRoomId = () => {
    roomId.value = ''
    localStorage.removeItem('roomId')
  }

  return {
    roomId,
    userCount,
    isConnected,
    ws,
    setRoomId,
    setUserCount,
    setConnected,
    setWebSocket,
    clearRoomId
  }
})