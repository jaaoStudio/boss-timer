import type { AxiosResponse } from 'axios'
import { bossService } from '@/axios'
import type { BossType, BossRecord } from '@/stores/bossStore'
import type { User } from '@/stores/userStore'
import type { MaintenanceInfo } from '@/stores/appInfo'

const WS_URL = `wss://${import.meta.env.VITE_WS_URL}`

interface ValidateTokenResponse {
  valid: boolean
  user?: User
}

interface InitSessionResponse {
  anonymous_user_id?: string
}

interface LoginResponse {
  user: User
  access_token: string
}

interface RoomCreateResponse {
  room_id: string
}

interface RoomExistsResponse {
  exists: boolean
  discord_webhook_url?: string | null
  discord_webhook_enabled?: boolean
  webhook_notify_events?: string[]
  webhook_alert_type?: string
}

interface RecordHistoryPage {
  records: BossRecord[]
  has_more: boolean
  next_cursor: number | null
}

export type FeedbackType = 'bug' | 'feature'
export type FeedbackStatus = 'pending' | 'open' | 'planning' | 'done' | 'rejected'

export interface FeedbackItem {
  id: number
  type: FeedbackType
  title: string
  description: string | null
  status: FeedbackStatus
  created_at: string
  vote_count: number
  voted_by_me: boolean
  creator: {
    id: number
    display_name: string
    avatar_url: string | null
  } | null
}

interface FeedbackListResponse {
  items: FeedbackItem[]
  total: number
}

interface FeedbackVoteResponse {
  feedback_id: number
  voted: boolean
  vote_count: number
}

class ApiService {
  private client: typeof bossService

  constructor() {
    this.client = bossService
  }

  async validateToken(): Promise<ValidateTokenResponse> {
    try {
      const res = await this.client.post<ValidateTokenResponse>('/auth/validate')
      return res.data
    } catch {
      return { valid: false }
    }
  }

  async loginWithGoogle(payload: { credential?: string; code?: string }): Promise<LoginResponse> {
    const res = await this.client.post<LoginResponse>('/auth/google', payload)
    return res.data
  }

  async logout(): Promise<void> {
    await this.client.post('/auth/logout')
  }

  async initSession(): Promise<InitSessionResponse> {
    const res = await this.client.post<InitSessionResponse>('/auth/session')
    return res.data
  }

  async getMe(): Promise<User> {
    const res = await this.client.get<User>('/auth/me')
    return res.data
  }

  async refresh_token(): Promise<{ status?: number }> {
    const res = await this.client.post<{ status?: number }>('auth/refresh')
    return res.data
  }

  async updateMyPreferences(preferences: Record<string, unknown>): Promise<User> {
    const res = await this.client.put<User>('/auth/me/preferences', preferences)
    return res.data
  }

  getBossTypes(): Promise<BossType[]> {
    return this.client.get<BossType[]>('/boss/boss-types').then(res => res.data)
  }

  createRoom(roomId?: string): Promise<RoomCreateResponse> {
    return this.client.post<RoomCreateResponse>('/room/', roomId ? { room_id: roomId } : {}).then(res => res.data)
  }

  checkRoomExists(roomId: string): Promise<RoomExistsResponse> {
    return this.client.get<RoomExistsResponse>(`/room/${roomId}/exists`).then(res => res.data)
  }

  updateRoomSettings(roomId: string, settings: Record<string, unknown>): Promise<RoomExistsResponse> {
    return this.client.patch<RoomExistsResponse>(`/room/${roomId}/settings`, settings).then(res => res.data)
  }

  deleteBossRecord(roomId: string, recordId: number): Promise<void> {
    return this.client.delete(`/boss/room/${roomId}/records/${recordId}`).then(() => undefined)
  }

  getRoomRecordsHistory(
    roomId: string,
    params: {
      before_id?: number
      limit?: number
      start?: string
      end?: string
      boss_type_id?: number
    } = {},
    signal?: AbortSignal,
  ): Promise<RecordHistoryPage> {
    return this.client
      .get<RecordHistoryPage>(`/boss/room/${roomId}/records`, { params, signal })
      .then(res => res.data)
  }

  createCustomBossType(
    roomId: string,
    payload: { name: string; min_respawn_minutes: number; max_respawn_minutes: number },
  ): Promise<BossType> {
    return this.client.post<BossType>(`/boss/room/${roomId}/boss-types`, payload).then(res => res.data)
  }

  deleteCustomBossType(roomId: string, bossTypeId: number): Promise<void> {
    return this.client.delete(`/boss/room/${roomId}/boss-types/${bossTypeId}`).then(() => undefined)
  }

  listFeedback(sort: 'votes' | 'newest' = 'votes'): Promise<FeedbackListResponse> {
    return this.client.get<FeedbackListResponse>('/feedback/', { params: { sort } }).then(res => res.data)
  }

  createFeedback(payload: { type: FeedbackType; title: string; description?: string }): Promise<FeedbackItem> {
    return this.client.post<FeedbackItem>('/feedback/', payload).then(res => res.data)
  }

  voteFeedback(feedbackId: number): Promise<FeedbackVoteResponse> {
    return this.client.post<FeedbackVoteResponse>(`/feedback/${feedbackId}/vote`).then(res => res.data)
  }

  updateFeedbackStatus(feedbackId: number, status: FeedbackStatus): Promise<FeedbackItem> {
    return this.client.patch<FeedbackItem>(`/feedback/${feedbackId}`, { status }).then(res => res.data)
  }

  deleteFeedback(feedbackId: number): Promise<void> {
    return this.client.delete(`/feedback/${feedbackId}`).then(() => undefined)
  }

  createWebSocket(): WebSocket {
    return new WebSocket(`${WS_URL}/ws/`)
  }

  async getMaintenanceStatus(): Promise<MaintenanceInfo> {
    const res = await this.client.get<MaintenanceInfo>('/system/maintenance-info')
    return res.data
  }

  async updateMaintenanceConfig(updatedConfig: Record<string, unknown>): Promise<AxiosResponse<MaintenanceInfo>> {
    return this.client.post<MaintenanceInfo>('/system/maintenance-config', updatedConfig)
  }
}

export default new ApiService()
