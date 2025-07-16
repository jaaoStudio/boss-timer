import {onUnmounted, ref} from 'vue'
import {storeToRefs} from 'pinia'
import {useRoomStore} from '@/stores/roomStore.js'
import {useBossStore} from '@/stores/bossStore.js'
import ApiService from '@/services/apiService.ts'
import router from "@/router/index.js";

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

    try {
      const newWs = ApiService.createWebSocket(roomId)
      roomStore.setWebSocket(newWs)

      newWs.onopen = () => {
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
        roomStore.setConnected(false)
        if (!isManualDisconnect.value) { // 只有在非手動斷開時才嘗試重連
          attemptReconnect(roomId)
        } else {
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
    } catch (error) {
      console.error("Failed to create WebSocket:", error);
      router.push("/");
    }
  }

  const handleMessage = (message) => {
    switch (message.type) {
      case 'error':
        disconnect()
        router.push("/").then(r => {})
        break
      case 'room_state':
        bossStore.setBossRecords(message.boss_records)
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
