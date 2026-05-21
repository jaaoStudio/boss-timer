import { defineStore } from 'pinia'

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
  [key: string]: any
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
  [key: string]: any
}

interface BossState {
  bossTypes: BossType[]
  bossRecords: BossRecord[]
  loading: boolean
  selectedBossTypeId: number | null
  selectedChannel: number | null
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
  }),
  getters: {
    priorityChannels(state): BossRecord[] {
      return state.bossRecords
        .filter(record => record.boss_type_id === state.selectedBossTypeId && (record.current_status === 'may_respawn' || record.current_status === 'alive'))
        .sort((a, b) => ts(a.respawn_min_time) - ts(b.respawn_min_time))
    },
    avoidChannels(state): BossRecord[] {
      return state.bossRecords
        .filter(record => record.boss_type_id === state.selectedBossTypeId && record.current_status === 'respawning')
        .sort((a, b) => ts(a.respawn_max_time) - ts(b.respawn_max_time))
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
    async updateBossRecord(record: BossRecord) {
      const index = this.bossRecords.findIndex(
        r => r.channel === record.channel && r.boss_type_id === record.boss_type_id
      )
      if (index >= 0) {
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

    deleteBossRecord(recordId: number) {
      const index = this.bossRecords.findIndex(r => r.id === recordId)
      if (index >= 0) {
        this.bossRecords.splice(index, 1)
      }
    },

    addCustomBossType(bossType: BossType) {
      this.bossTypes.push(bossType)
    },

    removeCustomBossType(bossTypeId: number) {
      const index = this.bossTypes.findIndex(b => b.id === bossTypeId)
      if (index >= 0) {
        this.bossTypes.splice(index, 1)
      }
      if (this.selectedBossTypeId === bossTypeId) {
        this.selectedBossTypeId = null
      }
      this.bossRecords = this.bossRecords.filter(r => r.boss_type_id !== bossTypeId)
    },

    clearRoomState() {
      this.bossTypes = []
      this.bossRecords = []
      this.selectedBossTypeId = null
      this.selectedChannel = null
    },

    setLoading(status: boolean) {
      this.loading = status
    },
    setSelectedChannel(channel: number | null) {
      this.selectedChannel = channel
    },
    calculateCurrentStatus(record: BossRecord): string {
      const now = new Date()
      const respawnMinTime = record.respawn_min_time ? new Date(record.respawn_min_time) : null
      const respawnMaxTime = record.respawn_max_time ? new Date(record.respawn_max_time) : null

      if (record.status === 'killed') {
        if (respawnMaxTime && now >= respawnMaxTime) {
          return 'alive'
        }
        if (respawnMinTime && now >= respawnMinTime) {
          return 'may_respawn'
        }
        return 'respawning'
      }
      return record.status
    },
    updateBossStatusOnTimerEnd(record: BossRecord) {
      const index = this.bossRecords.findIndex(
        r => r.channel === record.channel && r.boss_type_id === record.boss_type_id
      )

      if (index !== -1) {
        const currentRecord = { ...this.bossRecords[index] }
        currentRecord.current_status = this.calculateCurrentStatus(currentRecord)
        this.bossRecords.splice(index, 1, currentRecord)
      }
    },
  },
})
