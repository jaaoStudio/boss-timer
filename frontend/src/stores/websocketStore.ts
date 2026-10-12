import { defineStore, storeToRefs } from 'pinia'
import { ref } from 'vue'
import apiService from '@/services/apiService'
import { useAppInfoStore } from './appInfo'
import { useBossStore } from './bossStore'
import { useRoomStore } from './roomStore'
import { useRecordHistoryStore } from './recordHistoryStore'
import type { BossRecord, BossType } from './bossStore'
import type { RoomSettings } from './roomStore'
import i18n from '@/i18n'
import { showMessage } from '@/composables/useElementPlus'

interface WSMessage {
  type: string
  [key: string]: unknown
}

// 伺服器因握手頻率或同時連線數超過上限而關閉連線（app/routers/websocket.py 的 CLOSE_CODE_LIMITED）
const CLOSE_CODE_CONNECTION_LIMITED = 4429
// 看門狗（ADR-0008）：伺服器每 25 秒送 heartbeat（app/websocket/manager.py 的 HEARTBEAT_INTERVAL_SECONDS），
// 超過 IDLE_PROBE_MS 沒收到任何訊息就送 ping 探測，PROBE_TIMEOUT_MS 內仍沒有回應就視為無聲中斷、重連
const IDLE_PROBE_MS = 45000
const PROBE_TIMEOUT_MS = 10000
const WATCHDOG_TICK_MS = 5000
// 重連延遲：min(上限, 1 秒 × 2^次數) + 0～1 秒抖動，不放棄
const BASE_BACKOFF_MS = 1000
const MAX_BACKOFF_MS = 30000

export const useWebSocketStore = defineStore('websocket', () => {
  const socket = ref<WebSocket | null>(null)

  const isManualDisconnect = ref(false)
  let reconnectAttempts = 0
  let reconnectTimeout: ReturnType<typeof setTimeout> | null = null
  let lastMessageAt = 0
  let probeTimeout: ReturnType<typeof setTimeout> | null = null

  const appInfoStore = useAppInfoStore()
  const bossStore = useBossStore()
  const roomStore = useRoomStore()
  const recordHistoryStore = useRecordHistoryStore()
  const { isConnected } = storeToRefs(roomStore)

  function connect() {
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      console.log('WebSocket already connected.')
      return
    }
    if (socket.value && socket.value.readyState === WebSocket.CONNECTING) {
      console.log('WebSocket connection already in progress.')
      return
    }

    if (reconnectTimeout) {
      clearTimeout(reconnectTimeout)
      reconnectTimeout = null
    }

    try {
      const ws = apiService.createWebSocket()
      socket.value = ws

      ws.onopen = () => {
        console.log('WebSocket connected.')
        isConnected.value = true
        isManualDisconnect.value = false
        lastMessageAt = Date.now()
        // 連線時重建伺服器端狀態：身分由 cookie 決定，房間以 roomStore.roomId 重新加入
        const currentRoomId = roomStore.roomId
        if (currentRoomId) {
          ws.send(JSON.stringify({
            type: 'join_room',
            payload: { room_id: currentRoomId },
          }))
        }
      }

      ws.onmessage = (event: MessageEvent) => {
        lastMessageAt = Date.now()
        // 收到伺服器訊息才算連線成功、重置重連次數：伺服器拒絕連線時是「接受後立刻關閉」且不送訊息，
        // 若在 onopen 就重置，每次都會被重置而一直以最短間隔重連
        reconnectAttempts = 0
        const message: WSMessage = JSON.parse(event.data)
        handleMessage(message)
      }

      ws.onclose = (event: CloseEvent) => {
        console.log('WebSocket disconnected.')
        clearProbe()
        isConnected.value = false
        socket.value = null
        // 被伺服器的連線限制擋下時不自動重連：限制以分鐘 / 小時計，馬上重試只會再被擋；
        // 之後使用者一有操作，sendMessage 會再嘗試連線
        if (event.code === CLOSE_CODE_CONNECTION_LIMITED) {
          notify('warning', 'roomSelection.errors.connectionLimit')
        } else if (!isManualDisconnect.value) {
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

  /**
   * 只在連線中才送出，回傳是否已送出；未連線時觸發重連但不保留訊息。
   * 不需要補送：重連時身分由 cookie 決定、房間由 onopen 重新加入；
   * 回報則刻意不補送（紀錄時間以伺服器收到為準，延遲送達會讓重生區間失準）。
   */
  function sendMessage(message: WSMessage): boolean {
    if (socket.value && socket.value.readyState === WebSocket.OPEN) {
      socket.value.send(JSON.stringify(message))
      return true
    }
    if (!socket.value || socket.value.readyState === WebSocket.CLOSED) {
      connect()
    }
    return false
  }

  /**
   * 以目前的 cookie 重新建立連線。身分由握手時的 cookie 決定，登出後拿到新的匿名 cookie、
   * 或其他分頁登入 / 登出時，既有連線帶的仍是舊 cookie，需要重連才會換成新身分。
   */
  function reconnect() {
    clearProbe()
    isManualDisconnect.value = false
    const ws = socket.value
    if (ws) {
      ws.onopen = ws.onmessage = ws.onclose = ws.onerror = null
      ws.close()
      socket.value = null
      isConnected.value = false
    }
    reconnectAttempts = 0
    connect()
  }

  function clearProbe() {
    if (probeTimeout) {
      clearTimeout(probeTimeout)
      probeTimeout = null
    }
  }

  /**
   * 送 ping 探測連線是否仍通，PROBE_TIMEOUT_MS 內沒收到任何伺服器訊息就重連。
   * 先探測再重連：凍結的分頁恢復時 lastMessageAt 雖然很舊，連線可能仍然正常
   */
  function probe() {
    const ws = socket.value
    if (!ws || ws.readyState !== WebSocket.OPEN || probeTimeout) return
    const sentAt = Date.now()
    ws.send(JSON.stringify({ type: 'ping' }))
    probeTimeout = setTimeout(() => {
      probeTimeout = null
      if (socket.value === ws && lastMessageAt < sentAt) {
        console.warn('WebSocket probe timed out, reconnecting.')
        reconnect()
      }
    }, PROBE_TIMEOUT_MS)
  }

  /** 分頁回到前景或網路恢復時：連線中就立即探測；正在等待重連就不再等，馬上重連 */
  function checkConnection() {
    if (socket.value) {
      probe()
    } else if (reconnectTimeout) {
      connect()
    }
  }

  // 看門狗只在分頁可見時檢查：背景分頁的計時器會被節流、凍結，此時的「很久沒收到訊息」不代表斷線
  setInterval(() => {
    if (document.visibilityState === 'visible' && Date.now() - lastMessageAt > IDLE_PROBE_MS) {
      probe()
    }
  }, WATCHDOG_TICK_MS)
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') checkConnection()
  })
  window.addEventListener('online', checkConnection)

  // Each handler name declares which stores it touches.
  // Handlers that update multiple stores make it explicit rather than hiding it in a case block.

  function notify(level: 'warning' | 'error', key: string, params: Record<string, unknown> = {}) {
    showMessage[level](i18n.global.t(key, params))
  }

  function onRoomState(msg: WSMessage) {
    const bossTypes = msg.boss_types as BossType[] | undefined
    const bossRecords = msg.boss_records as BossRecord[]
    if (bossTypes) bossStore.setBossTypes(bossTypes)
    if (msg.room_settings) roomStore.setRoomSettings(msg.room_settings as RoomSettings)
    bossStore.setClearedAt((msg.last_cleared_at as Record<string, string> | undefined) ?? {})
    bossStore.setBossRecords(bossRecords)
    roomStore.setUserCount(msg.user_count as number)
  }

  function onBossUpdate(msg: WSMessage) {
    const record = msg.data as BossRecord
    bossStore.updateBossRecord(record)
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
    const wasSelected = bossStore.removeCustomBossType(data.boss_type_id)
    recordHistoryStore.removeBossType(data.boss_type_id)
    // 正在用這隻 Boss 的人選擇會被自動切換，需告知原因以免回報到錯的 Boss
    if (wasSelected && !deletedBySelf) {
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
    // 只用來更新 lastMessageAt（看門狗），不需處理
    heartbeat: () => {},
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
    if (reconnectTimeout) clearTimeout(reconnectTimeout)
    const delay = Math.min(MAX_BACKOFF_MS, BASE_BACKOFF_MS * 2 ** reconnectAttempts) + Math.random() * 1000
    reconnectTimeout = setTimeout(() => {
      reconnectTimeout = null
      reconnectAttempts++
      connect()
    }, delay)
  }

  return {
    isConnected,
    connect,
    disconnect,
    sendMessage,
    reconnect,
  }
})