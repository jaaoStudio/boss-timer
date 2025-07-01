import {onUnmounted, ref} from 'vue'
import {storeToRefs} from 'pinia'
import {useRoomStore} from '@/stores/roomStore'
import {useBossStore} from '@/stores/bossStore'
import ApiService from '@/services/apiService.js'

export function useWebSocket() {
  const roomStore = useRoomStore()
  const bossStore = useBossStore()

  const { ws, isConnected, isManualDisconnect } = storeToRefs(roomStore)

  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = 5
  const reconnectDelay = ref(1000)

  const connect = (roomId) => {
    if (ws.value) {
      // 在關閉舊的 WebSocket 之前，設定手動斷開標誌，防止其觸發重連
      roomStore.setManualDisconnect(true);
      if (ws.value.pingInterval) {
        clearInterval(ws.value.pingInterval);
      }
      ws.value.close();
      roomStore.setWebSocket(null); // 立即清除舊的 WebSocket 實例
      roomStore.setConnected(false);
    }

    const newWs = ApiService.createWebSocket(roomId)
    roomStore.setWebSocket(newWs)

    newWs.onopen = () => {
      console.log('WebSocket connected')
      roomStore.setConnected(true)
      reconnectAttempts.value = 0
      reconnectDelay.value = 1000
      roomStore.setManualDisconnect(false) // 新連線成功時重置標誌
    }

    newWs.onmessage = (event) => {
      const message = JSON.parse(event.data)
      handleMessage(message)
    }

    newWs.onclose = () => {
      console.log('WebSocket disconnected')
      roomStore.setConnected(false)
      if (!isManualDisconnect.value) { // 只有在非手動斷開時才嘗試重連
        attemptReconnect(roomId)
      } else {
        console.log('Manual disconnect, no reconnect attempt.')
        roomStore.setManualDisconnect(false) // 重置標誌
      }
    }

    newWs.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    // 心跳機制
    newWs.pingInterval = setInterval(() => {
      if (newWs.readyState === WebSocket.OPEN) {
        newWs.send(JSON.stringify({type: 'ping'}))
      }
    }, 30000)
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
    if (ws.value) {
      roomStore.setManualDisconnect(true) // 設定手動斷開標誌
      if (ws.value.pingInterval) {
        clearInterval(ws.value.pingInterval)
      }
      ws.value.close()
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
