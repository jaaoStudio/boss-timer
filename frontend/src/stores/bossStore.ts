import { defineStore } from 'pinia'

export const useBossStore = defineStore('boss', {
  state: () => ({
    bossTypes: [],
    bossRecords: [],

    loading: false,
    selectedBossTypeId: null, // Changed from selectedBossName
    selectedChannel: null,
  }),
  getters: {
    priorityChannels: (state) => {
      return state.bossRecords
        .filter(record => record.boss_type_id === state.selectedBossTypeId && record.current_status === 'may_respawn')
        .sort((a, b) => new Date(a.respawn_min_time) - new Date(b.respawn_min_time))
    },
    avoidChannels: (state) => {
      return state.bossRecords
        .filter(record => record.boss_type_id === state.selectedBossTypeId && record.current_status === 'respawning')
        .sort((a, b) => new Date(a.respawn_max_time) - new Date(b.respawn_max_time))
    }
  },
  actions: {
    setBossTypes(types) {
      this.bossTypes = types
      if (this.selectedBossTypeId === null && types.length > 0) { // check for null
        this.selectedBossTypeId = types[0].id // use id
      }
    },
    setSelectedBossTypeId(id) { // Renamed and takes id
      this.selectedBossTypeId = id
    },
    setBossRecords(records) {
      this.bossRecords = records
    },
    async updateBossRecord(record) {
      const index = this.bossRecords.findIndex(
        r => ((r.channel === record.channel) && (r.boss_type_id === record.boss_type_id))
      )
      if (index >= 0) {
        this.bossRecords.splice(index, 1, record);
      } else {
        this.bossRecords.push(record)
      }

      this.bossRecords.sort((a, b) => {
        if (a.boss_type_id === b.boss_type_id) {
          return new Date(a.respawn_min_time) - new Date(b.respawn_min_time)
        }
        // Sort by boss_type_id as a fallback
        return a.boss_type_id - b.boss_type_id;
      })
    },

    setLoading(status) {
      this.loading = status
    },
    setSelectedChannel(channel) {
      this.selectedChannel = channel
    },
    calculateCurrentStatus(record) {
      const now = new Date();
      const respawnMinTime = record.respawn_min_time ? new Date(record.respawn_min_time) : null;
      const respawnMaxTime = record.respawn_max_time ? new Date(record.respawn_max_time) : null;

      if (record.status === "killed") {
        if (respawnMaxTime && now >= respawnMaxTime) {
          return "alive";
        }
        if (respawnMinTime && now >= respawnMinTime) {
          return "may_respawn";
        }
        return "respawning";
      }
      return record.status;
    },
    updateBossStatusOnTimerEnd(record) {
      const index = this.bossRecords.findIndex(
        (r) => r.channel === record.channel && r.boss_type_id === record.boss_type_id
      )

      if (index !== -1) {
        const currentRecord = { ...this.bossRecords[index] }
        // Fix: Use create new object to trigger reactivity if needed, and call calculateCurrentStatus with this
        currentRecord.current_status = this.calculateCurrentStatus(currentRecord)
        this.bossRecords.splice(index, 1, currentRecord)
      }
    },
  },
})
