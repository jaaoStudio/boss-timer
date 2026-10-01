import { defineStore } from 'pinia'

let _statusTickId: ReturnType<typeof setInterval> | null = null

// 自己發起刪除的自訂 Boss：收到 boss_type_deleted 廣播時用來區分「自己刪的」與「被其他成員刪的」
const _selfDeletingBossTypeIds = new Set<number>()

export function calculateCurrentStatus(record: BossRecord, now = new Date()): string {
  if (record.status !== 'killed') return record.status
  const min = record.respawn_min_time ? new Date(record.respawn_min_time) : null
  const max = record.respawn_max_time ? new Date(record.respawn_max_time) : null
  if (max && now >= max) return 'alive'
  if (min && now >= min) return 'may_respawn'
  return 'respawning'
}

function resolveBossTypeId(types: BossType[]): number | null {
  if (!types.length) return null

  const lastId = Number(localStorage.getItem('lastSelectedBossTypeId'))
  const lastIsCustom = localStorage.getItem('lastSelectedBossTypeIsCustom') === 'true'

  // 1. 上次選的存在於新房間
  if (lastId) {
    const found = types.find(t => t.id === lastId)
    if (found) return found.id
  }

  // 2. 上次選的是自訂 Boss → 找新房間第一個自訂 Boss
  if (lastIsCustom) {
    const firstCustom = types.find(t => !!t.room_id)
    if (firstCustom) return firstCustom.id
  }

  // 3. 收藏第一個
  try {
    const favorites: number[] = JSON.parse(localStorage.getItem('favorite-boss-ids') || '[]')
    const firstFav = favorites.find(id => types.some(t => t.id === id))
    if (firstFav) return firstFav
  } catch {}

  // 4. 退路
  return types[0].id
}

export interface BossType {
  id: number
  name_zh: string
  name_en: string
  min_respawn_minutes: number
  max_respawn_minutes: number
  room_id?: string | null
  description?: string | null
}

export interface BossRecord {
  id: number
  channel: number
  boss_type_id: number
  status: string
  current_status: string
  recorded_at: string
  respawn_min_time: string | null
  respawn_max_time: string | null
  recorder_info?: { anonymous_id?: string; anonymous_name?: string } | null
}

interface BossState {
  bossTypes: BossType[]
  bossRecords: BossRecord[]
  loading: boolean
  selectedBossTypeId: number | null
  selectedChannel: number | null
  // 各 Boss 種類的換輪分界線（ms epoch），早於分界線的紀錄不再有效
  clearedAt: Record<number, number>
  _now: number
}

function ts(value: string | null): number {
  return value ? new Date(value).getTime() : 0
}

export const useBossStore = defineStore('boss', {
  state: (): BossState => ({
    bossTypes: [],
    bossRecords: [],

    loading: false,
    selectedBossTypeId: null,
    selectedChannel: null,
    clearedAt: {},
    _now: Date.now(),
  }),
  getters: {
    allBossPriorityRecords(state): BossRecord[] {
      const now = new Date(state._now)
      return state.bossRecords
        .filter(r => calculateCurrentStatus(r, now) === 'may_respawn')
        .sort((a, b) => ts(a.respawn_min_time) - ts(b.respawn_min_time))
    },
  },
  actions: {
    setBossTypes(types: BossType[]) {
      this.bossTypes = types
      this.selectedBossTypeId = resolveBossTypeId(types)
    },
    setSelectedBossTypeId(id: number | null) {
      this.selectedBossTypeId = id
      if (id !== null) {
        const isCustom = !!this.bossTypes.find(t => t.id === id)?.room_id
        localStorage.setItem('lastSelectedBossTypeId', String(id))
        localStorage.setItem('lastSelectedBossTypeIsCustom', String(isCustom))
      }
    },
    setBossRecords(records: BossRecord[]) {
      this.bossRecords = records
    },
    setClearedAt(lastClearedAt: Record<string, string>) {
      this.clearedAt = Object.fromEntries(
        Object.entries(lastClearedAt).map(([id, iso]) => [Number(id), ts(iso)]),
      )
    },

    async updateBossRecord(record: BossRecord) {
      // 換輪前的紀錄即使晚送達也不算有效
      if (ts(record.recorded_at) < (this.clearedAt[record.boss_type_id] ?? 0)) return

      const index = this.bossRecords.findIndex(
        r => r.channel === record.channel && r.boss_type_id === record.boss_type_id
      )
      if (index >= 0) {
        // 已有更新的紀錄時不被舊紀錄覆蓋（例如撤銷後接手的前一筆晚於新回報送達）
        if (ts(this.bossRecords[index].recorded_at) > ts(record.recorded_at)) return
        this.bossRecords.splice(index, 1, record)
      } else {
        this.bossRecords.push(record)
      }

      this.bossRecords.sort((a, b) => {
        if (a.boss_type_id === b.boss_type_id) {
          return ts(a.respawn_min_time) - ts(b.respawn_min_time)
        }
        return a.boss_type_id - b.boss_type_id
      })
    },

    deleteBossRecord(recordId: number, replacement: BossRecord | null = null) {
      const index = this.bossRecords.findIndex(r => r.id === recordId)
      if (index >= 0) {
        this.bossRecords.splice(index, 1)
      }
      // 撤銷後由前一筆仍有效的紀錄接手該頻道
      if (replacement) {
        this.updateBossRecord(replacement).then()
      }
    },

    clearBossTypeRecords(bossTypeId: number, clearedAt: string) {
      this.clearedAt = { ...this.clearedAt, [bossTypeId]: ts(clearedAt) }
      this.bossRecords = this.bossRecords.filter(r => r.boss_type_id !== bossTypeId)
    },

    addCustomBossType(bossType: BossType) {
      // 自己新增時 HTTP 回應與 boss_type_added 廣播都會帶來同一筆
      if (this.bossTypes.some(b => b.id === bossType.id)) return
      this.bossTypes.push(bossType)
    },

    markSelfDeletingBossType(bossTypeId: number) {
      _selfDeletingBossTypeIds.add(bossTypeId)
    },

    unmarkSelfDeletingBossType(bossTypeId: number): boolean {
      return _selfDeletingBossTypeIds.delete(bossTypeId)
    },

    /** 移除自訂 Boss 與其紀錄；回傳被移除的 Boss 與它是否正被選取，不存在則回傳 null */
    removeCustomBossType(bossTypeId: number): { bossType: BossType; wasSelected: boolean } | null {
      const index = this.bossTypes.findIndex(b => b.id === bossTypeId)
      if (index < 0) return null
      const [bossType] = this.bossTypes.splice(index, 1)
      const wasSelected = this.selectedBossTypeId === bossTypeId
      if (wasSelected) {
        this.selectedBossTypeId = resolveBossTypeId(this.bossTypes)
      }
      this.bossRecords = this.bossRecords.filter(r => r.boss_type_id !== bossTypeId)
      return { bossType, wasSelected }
    },

    clearRoomState() {
      this.bossTypes = []
      this.bossRecords = []
      this.selectedBossTypeId = null
      this.selectedChannel = null
      this.clearedAt = {}
    },

    setLoading(status: boolean) {
      this.loading = status
    },
    setSelectedChannel(channel: number | null) {
      this.selectedChannel = channel
    },

    startStatusTick() {
      if (_statusTickId !== null) return
      _statusTickId = setInterval(() => { this._now = Date.now() }, 1_000)
    },

    stopStatusTick() {
      if (_statusTickId !== null) {
        clearInterval(_statusTickId)
        _statusTickId = null
      }
    },
  },
})
