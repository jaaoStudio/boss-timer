import { defineStore } from 'pinia'
import ApiService from '@/services/apiService.js'

export const useBossStore = defineStore('boss', {
  state: () => ({
    bossTypes: [],
    bossRecords: [],
    history: new Map(),
    loading: false,
    selectedBossName: '',
    selectedChannel: null, // 新增 selectedChannel 狀態
  }),
  getters: {
    priorityChannels: (state) => {
      return state.bossRecords
          .filter(record => record.boss_name === state.selectedBossName && record.current_status === 'may_respawn')
          .sort((a, b) => new Date(a.respawn_min_time) - new Date(b.respawn_min_time))
    },
    avoidChannels: (state) => {
      return state.bossRecords
          .filter(record => record.boss_name === state.selectedBossName && record.current_status === 'respawning')
          .sort((a, b) => new Date(a.respawn_max_time) - new Date(b.respawn_max_time))
    }
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
    async updateBossRecord(record) {
      const index = this.bossRecords.findIndex(
          r => r.channel === record.channel && r.boss_name === record.boss_name
      )
      if (index >= 0) {
        this.bossRecords[index] = record
      } else {
        this.bossRecords.push(record)
      }

      this.bossRecords = this.bossRecords.sort((a, b) => {
        if (a.boss_name === b.boss_name) {
          return new Date(a.respawn_min_time) - new Date(b.respawn_min_time)
        }
        return a.boss_name.localeCompare(b.boss_name)
      })

      // const historyData = await ApiService.getRoomHistory(
      //     record.room_id,
      //     record.boss_name || null
      // )

      // this.setHistory(record.room_id, historyData)
      // 將新記錄添加到歷史記錄的開頭
      // console.log(this.history,'aaa')
      // if (!this.history.has(record.roomId)) {
      //   this.history.set(record.roomId, []);
      // }
      // this.history.get(record.roomId).unshift(record);

      // 可以選擇限制歷史記錄的長度，例如只保留最新的 50 條
      // if (this.history.length > 50) {
      //   this.history.pop()
      // }
    },
    setHistory(roomId, historyData) {
      this.history.set(roomId, historyData)
      console.log(this.history)
    },
    setLoading(status) {
      this.loading = status
    },
    setSelectedChannel(channel) { // 新增 setSelectedChannel action
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
          r => r.channel === record.channel && r.boss_name === record.boss_name
      );

      if (index !== -1) {
        const currentRecord = this.bossRecords[index];
        currentRecord.current_status = this.calculateCurrentStatus(currentRecord);
      }
    },
  }
})