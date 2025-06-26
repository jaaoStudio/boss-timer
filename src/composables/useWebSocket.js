import { ref, onMounted, onUnmounted } from 'vue'
import { useRoomStore } from '@/stores/roomStore'
import { useBossStore } from '@/stores/bossStore'
import ApiService from '@/services/apiService.js'

export function useWebSocket() {
  const roomStore = useRoomStore()
  const bossStore = useBossStore()
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = 5
  const reconnectDelay = ref(1000)

  const connect = (roomId) => {
    if (roomStore.ws) {
      roomStore.ws.close()
    }

    const ws = ApiService.createWebSocket(roomId)
    roomStore.setWebSocket(ws)

    ws.onopen = () => {
      console.log('WebSocket connected')
      roomStore.setConnected(true)
      reconnectAttempts.value = 0
      reconnectDelay.value = 1000
    }

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data)
      handleMessage(message)
    }

    ws.onclose = () => {
      console.log('WebSocket disconnected')
      roomStore.setConnected(false)
      attemptReconnect(roomId)
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    // 心跳機制
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: 'ping' }))
      }
    }, 30000)

    ws.pingInterval = pingInterval
  }

  const handleMessage = (message) => {
    switch (message.type) {
      case 'room_state':
        bossStore.setBossRecords(message.data)
        break
      case 'boss_update':
        bossStore.updateBossRecord(message.data)
        break
      case 'user_count_update':
        roomStore.setUserCount(message.count)
        break
      case 'pong':
        // 心跳回應
        break
    }
  }

  const attemptReconnect = (roomId) => {
    if (reconnectAttempts.value < maxReconnectAttempts) {
      setTimeout(() => {
        console.log(`Attempting to reconnect... (${reconnectAttempts.value + 1}/${maxReconnectAttempts})`)
        reconnectAttempts.value++
        reconnectDelay.value *= 2
        connect(roomId)
      }, reconnectDelay.value)
    }
  }

  const disconnect = () => {
    if (roomStore.ws) {
      if (roomStore.ws.pingInterval) {
        clearInterval(roomStore.ws.pingInterval)
      }
      roomStore.ws.close()
      roomStore.setWebSocket(null)
      roomStore.setConnected(false)
    }
  }

  onUnmounted(() => {
    disconnect()
  })

  return {
    connect,
    disconnect,
    reconnectAttempts
  }
}
