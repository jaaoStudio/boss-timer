import { defineStore } from 'pinia'
import { useWebSocketStore } from './websocketStore'

export interface RoomSettings {
  discord_webhook_url?: string | null
  discord_webhook_enabled?: boolean
  webhook_notify_events?: string[] | null
  webhook_alert_type?: string | null
}

export const useRoomStore = defineStore('room', {
  state: (): {
    roomId: string
    userCount: number
    isConnected: boolean
    ws: WebSocket | null
    isManualDisconnect: boolean
    // 房間共用的 Webhook 設定；收到 room_settings_updated 時更新，設定視窗據此同步顯示
    roomSettings: RoomSettings | null
  } => ({
    roomId: '',
    userCount: 0,
    isConnected: false,
    ws: null,
    isManualDisconnect: false,
    roomSettings: null,
  }),
  actions: {
    setRoomId(id: string) {
      this.roomId = id
    },
    setUserCount(count: number) {
      this.userCount = count
    },
    setConnected(status: boolean) {
      this.isConnected = status
    },
    setWebSocket(websocket: WebSocket | null) {
      this.ws = websocket
    },
    clearRoomId() {
      this.roomId = ''
      this.roomSettings = null
    },
    setRoomSettings(settings: RoomSettings) {
      this.roomSettings = { ...settings }
    },
    setManualDisconnect(status: boolean) {
      this.isManualDisconnect = status
    },
    leaveRoomAction() {
      const websocketStore = useWebSocketStore()
      if (this.roomId) {
        websocketStore.sendMessage({
          type: 'leave_room',
          payload: { room_id: this.roomId },
        })
      }
      this.clearRoomId()
    },
  },
})