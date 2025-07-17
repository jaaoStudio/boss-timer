import {onUnmounted, ref} from 'vue'
import {storeToRefs} from 'pinia'
import {useRoomStore} from '@/stores/roomStore.js'
import {useBossStore} from '@/stores/bossStore.js'
import ApiService from '@/services/apiService.ts'
import {useRouter} from 'vue-router'
import {showMessage} from "@/composables/useElementPlus.js";

export function useWebSocket() {
  const roomStore = useRoomStore()
  const bossStore = useBossStore()
  const router = useRouter()

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

      newWs.onclose = (event) => {
        roomStore.setConnected(false)
        if (event.code === 1013 && event.reason === "Connection limit reached") {
          showMessage.error("連線數已達上限，請稍後再試。");
          router.push("/");
          roomStore.setManualDisconnect(true); // 設置為手動斷開，避免重連
        } else if (!isManualDisconnect.value) { // 只有在非手動斷開時才嘗試重連
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
