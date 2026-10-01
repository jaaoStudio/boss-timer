import { defineStore, storeToRefs } from 'pinia'
import { ref } from 'vue'
import apiService from '@/services/apiService'
import { useAppInfoStore } from './appInfo'
import { useBossStore } from './bossStore'
import { useRoomStore } from './roomStore'
import { useRecordHistoryStore } from './recordHistoryStore'
import type { BossRecord, BossType } from './bossStore'
import type { RoomSettings } from './roomStore'

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

  // 房間進出以 roomStore.roomId 為準，連線建立時已重新 join，佇列中的 join/leave 不再需要
  const ROOM_MEMBERSHIP_TYPES = new Set(['join_room', 'leave_room'])

  function processMessageQueue() {
    while (messageQueue.value.length > 0) {
      const message = messageQueue.value.shift()
      if (message && socket.value && !ROOM_MEMBERSHIP_TYPES.has(message.type)) {
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
        // 先加入房間再送出佇列，否則需要房間身分的訊息會被伺服器拒絕
        const currentRoomId = roomStore.roomId
        if (currentRoomId) {
          ws.send(JSON.stringify({
            type: 'join_room',
            payload: { room_id: currentRoomId },
          }))
        }
        processMessageQueue()
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

  /** 只在連線中才送出，不進佇列；回傳是否已送出 */
  function sendIfConnected(message: WSMessage): boolean {
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify(message))
      return true
    }
    return false
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

  // Each handler name declares which stores it touches.
  // Handlers that update multiple stores make it explicit rather than hiding it in a case block.

  function notify(level: 'warning' | 'error', key: string, params: Record<string, unknown> = {}) {
    Promise.all([import('@/i18n'), import('@/composables/useElementPlus')]).then(
      ([{ default: i18n }, { showMessage }]) => {
        showMessage[level](i18n.global.t(key, params))
      },
    )
  }

  function onRoomState(msg: WSMessage) {
    const bossTypes = msg.boss_types as BossType[] | undefined
    const bossRecords = msg.boss_records as BossRecord[]
    if (bossTypes) bossStore.setBossTypes(bossTypes)
    bossStore.setClearedAt((msg.last_cleared_at as Record<string, string> | undefined) ?? {})
    bossStore.setBossRecords(bossRecords)
    roomStore.setUserCount(msg.user_count as number)
  }

  function onBossUpdate(msg: WSMessage) {
    const record = msg.data as BossRecord
    bossStore.updateBossRecord(record).then()
    recordHistoryStore.upsertRecord(record)
  }

  function onRecordDeleted(msg: WSMessage) {
    const data = msg.data as { record_id: number; replacement?: BossRecord | null }
    bossStore.deleteBossRecord(data.record_id, data.replacement ?? null)
    recordHistoryStore.removeRecord(data.record_id)
  }

  function onBossTypeCleared(msg: WSMessage) {
    const data = msg.data as { boss_type_id: number; cleared_at: string }
    bossStore.clearBossTypeRecords(data.boss_type_id, data.cleared_at)
  }

  function onBossTypeAdded(msg: WSMessage) {
    bossStore.addCustomBossType(msg.data as BossType)
  }

  function onBossTypeDeleted(msg: WSMessage) {
    const data = msg.data as { boss_type_id: number; name: string }
    const deletedBySelf = bossStore.unmarkSelfDeletingBossType(data.boss_type_id)
    const removed = bossStore.removeCustomBossType(data.boss_type_id)
    recordHistoryStore.removeBossType(data.boss_type_id)
    // 正在用這隻 Boss 的人選擇會被自動切換，需告知原因以免回報到錯的 Boss
    if (removed?.wasSelected && !deletedBySelf) {
      notify('warning', 'bossControlPanel.customBossDeletedByOther', { name: data.name })
    }
  }

  function onRoomSettingsUpdated(msg: WSMessage) {
    roomStore.setRoomSettings(msg.data as RoomSettings)
  }

  function onMaintenanceStatusUpdate(msg: WSMessage) {
    appInfoStore.setMaintenanceInfo(msg.data as Parameters<typeof appInfoStore.setMaintenanceInfo>[0])
  }

  function onUserCountUpdate(msg: WSMessage) {
    roomStore.setUserCount(msg.count as number)
  }

  function onError(msg: WSMessage) {
    console.error('Received error from server:', msg.message)
    if (msg.code === 'rate_limited') {
      notify('warning', 'globalErrors.rateLimitExceeded')
    } else if (msg.code === 'record_rejected') {
      notify('error', 'bossControlPanel.recordRejected')
    }
  }

  const MESSAGE_HANDLERS: Record<string, (msg: WSMessage) => void> = {
    pong: () => {},
    room_state: onRoomState,
    boss_update: onBossUpdate,
    record_deleted: onRecordDeleted,
    boss_type_cleared: onBossTypeCleared,
    boss_type_added: onBossTypeAdded,
    boss_type_deleted: onBossTypeDeleted,
    room_settings_updated: onRoomSettingsUpdated,
    maintenance_status_update: onMaintenanceStatusUpdate,
    user_count_update: onUserCountUpdate,
    error: onError,
  }

  function handleMessage(message: WSMessage) {
    const handler = MESSAGE_HANDLERS[message.type]
    if (handler) {
      handler(message)
    } else {
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
    sendIfConnected,
  }
})