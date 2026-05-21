import { defineStore, storeToRefs } from 'pinia'
import { ref } from 'vue'
import apiService from '@/services/apiService'
import { useAppInfoStore } from './appInfo'
import { useBossStore } from './bossStore'
import { useRoomStore } from './roomStore'
import { useRecordHistoryStore } from './recordHistoryStore'

interface WSMessage {
  type: string
  [key: string]: unknown
}

export const useWebSocketStore = defineStore('websocket', () => {
  const socket = ref<WebSocket | null>(null)
  const messageQueue = ref<WSMessage[]>([])

  const isManualDisconnect = ref(false)
  const reconnectAttempts = ref(0)
  const maxReconnectAttempts = 5
  const isMaxReconnectReached = ref(false)
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null

  const appInfoStore = useAppInfoStore()
  const bossStore = useBossStore()
  const roomStore = useRoomStore()
  const recordHistoryStore = useRecordHistoryStore()
  const { isConnected } = storeToRefs(roomStore)

  function processMessageQueue() {
    while (messageQueue.value.length > 0) {
      const message = messageQueue.value.shift()
      if (message && socket.value) {
        socket.value.send(JSON.stringify(message))
      }
    }
  }

  function connect() {
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected.')
      return
    }
    if (socket.value && socket.value.readyState === WebSocket.CONNECTING) {
      console.log('WebSocket connection already in progress.')
      return
    }

    try {
      const ws = apiService.createWebSocket()
      socket.value = ws

      ws.onopen = () => {
        console.log('WebSocket connected.')
        isConnected.value = true
        reconnectAttempts.value = 0
        isManualDisconnect.value = false
        isMaxReconnectReached.value = false
        processMessageQueue()
        const currentRoomId = roomStore.roomId
        if (currentRoomId) {
          ws.send(JSON.stringify({
            type: 'join_room',
            payload: { room_id: currentRoomId },
          }))
        }
      }

      ws.onmessage = (event: MessageEvent) => {
        const message: WSMessage = JSON.parse(event.data)
        handleMessage(message)
      }

      ws.onclose = () => {
        console.log('WebSocket disconnected.')
        isConnected.value = false
        socket.value = null
        if (!isManualDisconnect.value) {
          attemptReconnect()
        }
      }

      ws.onerror = (error: Event) => {
        console.error('WebSocket error:', error)
      }
    } catch (error) {
      console.error('Failed to create WebSocket:', error)
    }
  }

  function disconnect() {
    if (socket.value) {
      isManualDisconnect.value = true
      socket.value.close()
    }
  }

  function sendMessage(message: WSMessage) {
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify(message))
    } else {
      console.log('WebSocket not open. Queuing message.')
      messageQueue.value.push(message)
      if (!socket.value || socket.value.readyState === WebSocket.CLOSED) {
        connect()
      }
    }
  }

  function handleMessage(message: WSMessage) {
    switch (message.type) {
      case 'pong':
        break
      case 'maintenance_status_update':
        appInfoStore.setMaintenanceInfo(message.data as Parameters<typeof appInfoStore.setMaintenanceInfo>[0])
        break
      case 'room_state': {
        const bossTypes = message.boss_types as import('@/stores/bossStore').BossType[] | undefined
        const bossRecords = message.boss_records as import('@/stores/bossStore').BossRecord[]
        if (bossTypes) bossStore.setBossTypes(bossTypes)
        bossStore.setBossRecords(bossRecords)
        roomStore.setUserCount(message.user_count as number)
        break
      }
      case 'boss_update': {
        const record = message.data as import('@/stores/bossStore').BossRecord
        bossStore.updateBossRecord(record).then()
        recordHistoryStore.upsertRecord(record)
        break
      }
      case 'record_deleted': {
        const data = message.data as { record_id: number }
        bossStore.deleteBossRecord(data.record_id)
        recordHistoryStore.removeRecord(data.record_id)
        break
      }
      case 'user_count_update':
        roomStore.setUserCount(message.count as number)
        break
      case 'error': {
        const errMsg = message.message as string
        console.error('Received error from server:', errMsg)
        if (errMsg === 'Rate limit exceeded. Please slow down.') {
          import('@/i18n').then(({ default: i18n }) => {
            import('@/composables/useElementPlus').then(({ showMessage }) => {
              showMessage.warning(i18n.global.t('globalErrors.rateLimitExceeded'))
            })
          })
        }
        break
      }
      default:
        console.warn('Received unknown message type:', message.type)
    }
  }

  function attemptReconnect() {
    if (reconnectAttempts.value < maxReconnectAttempts) {
      if (reconnectTimeout) clearTimeout(reconnectTimeout)
      reconnectTimeout = setTimeout(() => {
        reconnectAttempts.value++
        connect()
      }, 2000 * (reconnectAttempts.value + 1))
    } else {
      console.error('WebSocket max reconnect attempts reached.')
      isMaxReconnectReached.value = true
    }
  }

  setInterval(() => {
    if (isConnected.value) {
      if (socket.value && socket.value.readyState === WebSocket.OPEN) {
        sendMessage({ type: 'ping' })
      }
    }
  }, 30000)

  return {
    isConnected,
    isMaxReconnectReached,
    connect,
    disconnect,
    sendMessage,
  }
})