import { defineStore, storeToRefs } from 'pinia'
import { ref } from 'vue'
import { useEventListener } from '@vueuse/core'
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
// 連線卡在 CONNECTING（例如切換網路時握手送往舊路由）不會自己結束，逾時就放棄、交給退避重連（同 Socket.IO 的 timeout）
const CONNECT_TIMEOUT_MS = 20000
// 重連延遲：min(上限, 1 秒 × 2^次數) × (1 ± 0.5)，不放棄。抖動照 Socket.IO 的 randomizationFactor，
// 部署停掉舊 slot 時所有人同時斷線，比例抖動才分散得開；上限比 Socket.IO 的 5 秒長，多開分頁才不會撞到握手限制
const BASE_BACKOFF_MS = 1000
const MAX_BACKOFF_MS = 30000
const BACKOFF_RANDOMIZATION = 0.5

type Timer = ReturnType<typeof setTimeout> | null

/** 清除計時器並回傳 null，用法：timer = cancel(timer) */
function cancel(timer: Timer): null {
  if (timer) clearTimeout(timer)
  return null
}

export const useWebSocketStore = defineStore('websocket', () => {
  const socket = ref<WebSocket | null>(null)

  // 連線中斷、正在自動重連（畫面據此顯示提示）；收到伺服器訊息或被連線限制擋下時清除
  const isReconnecting = ref(false)
  let reconnectAttempts = 0
  let reconnectTimeout: Timer = null
  let connectTimeout: Timer = null
  // 心跳逾時（ADR-0008，照 Socket.IO）：收到 hello 才啟動，之後每次心跳重新計時，
  // 超過伺服器宣告的「間隔 + 容忍」沒收到就視為無聲中斷（休眠喚醒、切換網路）而重連
  let heartbeatTimeout: Timer = null
  let heartbeatTimeoutMs = 0
  let heartbeatDeadline = 0

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

    reconnectTimeout = cancel(reconnectTimeout)
    // 仍在 CLOSING 的舊連線：先拋棄並清掉它的狀態，不等它的 onclose
    dropSocket()

    try {
      const ws = apiService.createWebSocket()
      socket.value = ws
      connectTimeout = setTimeout(() => {
        connectTimeout = null
        if (ws.readyState === WebSocket.CONNECTING) ws.close()   // 觸發 onclose → 退避重連
      }, CONNECT_TIMEOUT_MS)

      // 每個事件都先確認 ws 仍是目前的連線：被取代的舊連線遲到的事件不可動到新連線的狀態
      ws.onopen = () => {
        if (socket.value !== ws) return
        console.log('WebSocket connected.')
        connectTimeout = cancel(connectTimeout)
        isConnected.value = true
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
        if (socket.value !== ws) return
        // 收到伺服器訊息（新版後端第一則是 hello）才算連線成功、重置重連次數：伺服器拒絕連線時是
        // 「接受後立刻關閉」且不送訊息，若在 onopen 就重置，每次都會被重置而一直以最短間隔重連
        reconnectAttempts = 0
        isReconnecting.value = false
        const message: WSMessage = JSON.parse(event.data)
        handleMessage(message)
      }

      ws.onclose = (event: CloseEvent) => {
        if (socket.value !== ws) return
        console.log('WebSocket disconnected.')
        resetConnectionState()
        // 被伺服器的連線限制擋下時不自動重連：限制以分鐘 / 小時計，馬上重試只會再被擋；
        // 之後使用者一有操作，sendMessage 會再嘗試連線
        if (event.code === CLOSE_CODE_CONNECTION_LIMITED) {
          isReconnecting.value = false
          notify('warning', 'roomSelection.errors.connectionLimit')
        } else {
          attemptReconnect()
        }
      }

      ws.onerror = (error: Event) => {
        console.error('WebSocket error:', error)
      }
    } catch (error) {
      console.error('Failed to create WebSocket:', error)
      attemptReconnect()
    }
  }

  /**
   * 只在連線中才送出，回傳是否已送出；未連線時觸發重連但不保留訊息。
   * 不需要補送：重連時身分由 cookie 決定、房間由 onopen 重新加入；
   * 回報則刻意不補送（紀錄時間以伺服器收到為準，延遲送達會讓重生區間失準）。
   */
  function sendMessage(message: WSMessage): boolean {
    // 心跳已逾時但計時器還沒觸發（剛從休眠喚醒、背景計時器被延後）：連線多半已死，
    // 送出會無聲遺失，改為重連並回報未送出（同 Socket.IO 送出前的檢查）
    if (heartbeatDeadline && Date.now() > heartbeatDeadline) {
      closeAndReconnect('WebSocket heartbeat expired before send, reconnecting.')
      return false
    }
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
    dropSocket()
    reconnectAttempts = 0
    connect()
  }

  /** 連線結束時清掉它的計時器與狀態（onclose 與主動拋棄共用） */
  function resetConnectionState() {
    connectTimeout = cancel(connectTimeout)
    heartbeatTimeout = cancel(heartbeatTimeout)
    heartbeatTimeoutMs = 0
    heartbeatDeadline = 0
    isConnected.value = false
    socket.value = null
  }

  /** 關閉並拋棄目前的連線，不觸發 onclose 的自動重連 */
  function dropSocket() {
    const ws = socket.value
    if (ws) {
      ws.onopen = ws.onmessage = ws.onclose = ws.onerror = null
      ws.close()
    }
    resetConnectionState()
  }

  /** 判定連線已無聲中斷：拋棄它並走退避重連（不重置次數，伺服器卡住時大家不會一起以最短間隔重連） */
  function closeAndReconnect(reason: string) {
    console.warn(reason)
    dropSocket()
    attemptReconnect()
  }

  function attemptReconnect() {
    isReconnecting.value = true
    const base = Math.min(MAX_BACKOFF_MS, BASE_BACKOFF_MS * 2 ** reconnectAttempts)
    const delay = base * (1 + BACKOFF_RANDOMIZATION * (2 * Math.random() - 1))
    reconnectTimeout = cancel(reconnectTimeout)
    reconnectTimeout = setTimeout(() => {
      reconnectTimeout = null
      reconnectAttempts++
      connect()
    }, delay)
  }

  /**
   * 收到 hello 或心跳時重新計時。背景分頁的計時器被節流只會讓逾時晚一點觸發（心跳是網路事件，
   * 照常送達並重新計時），不會誤判；凍結的分頁恢復時可能重連一次，Socket.IO 也接受
   */
  function resetHeartbeat() {
    if (!heartbeatTimeoutMs) return
    heartbeatTimeout = cancel(heartbeatTimeout)
    heartbeatDeadline = Date.now() + heartbeatTimeoutMs
    heartbeatTimeout = setTimeout(() => {
      heartbeatTimeout = null
      closeAndReconnect('WebSocket heartbeat timed out, reconnecting.')
    }, heartbeatTimeoutMs)
  }

  // 網路中斷時立刻關閉、進入退避（同 engine.io）；網路恢復不特別處理，由退避重連
  useEventListener(window, 'offline', () => {
    if (socket.value) closeAndReconnect('Network went offline, reconnecting.')
  })

  // Each handler name declares which stores it touches.
  // Handlers that update multiple stores make it explicit rather than hiding it in a case block.

  function notify(level: 'warning' | 'error', key: string, params: Record<string, unknown> = {}) {
    showMessage[level](i18n.global.t(key, params))
  }

  function onHello(msg: WSMessage) {
    heartbeatTimeoutMs = ((msg.ping_interval as number) + (msg.ping_timeout as number)) * 1000
    resetHeartbeat()
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
    hello: onHello,
    heartbeat: resetHeartbeat,
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

  return {
    isConnected,
    isReconnecting,
    connect,
    sendMessage,
    reconnect,
  }
})