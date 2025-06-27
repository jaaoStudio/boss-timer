import { defineStore } from 'pinia'

export const useBossStore = defineStore('boss', {
  state: () => ({
    bossTypes: [],
    bossRecords: [],
    history: [],
    loading: false,
    selectedBossName: '',
    selectedChannel: null, // 新增 selectedChannel 狀態
  }),
  getters: {
    recordsByChannel: (state) => {
      const grouped = {}
      state.bossRecords.forEach(record => {
        if (!grouped[record.channel]) {
          grouped[record.channel] = []
        }
        grouped[record.channel].push(record)
      })
      return grouped
    },
    priorityChannels: (state) => {
      return state.bossRecords
        .filter(record => record.current_status === 'may_respawn')
        .sort((a, b) => new Date(a.respawn_min_time) - new Date(b.respawn_min_time))
    },
    avoidChannels: (state) => {
      return state.bossRecords
        .filter(record => record.current_status === 'respawning')
        .sort((a, b) => new Date(a.respawn_max_time) - new Date(b.respawn_max_time))
    },
  },
  actions: {
    setBossTypes(types) {
      this.bossTypes = types
      if (!this.selectedBossName && types.length > 0) {
        this.selectedBossName = types[0].boss_name
      }
    },
    setSelectedBossName(name) {
      this.selectedBossName = name
    },
    setBossRecords(records) {
      this.bossRecords = records
    },
    updateBossRecord(record) {
      const index = this.bossRecords.findIndex(
        r => r.channel === record.channel && r.boss_name === record.boss_name
      )
      if (index >= 0) {
        // 使用 Vue.set 或直接替換物件以確保響應性
        this.bossRecords[index] = record
      } else {
        this.bossRecords.push(record)
      }
      // 將新記錄添加到歷史記錄的開頭
      this.history.unshift(record)
      // 可以選擇限制歷史記錄的長度，例如只保留最新的 50 條
      // if (this.history.length > 50) {
      //   this.history.pop()
      // }
    },
    setHistory(historyData) {
      this.history = historyData
    },
    setLoading(status) {
      this.loading = status
    },
    setSelectedChannel(channel) { // 新增 setSelectedChannel action
      this.selectedChannel = channel
    },
  },
})