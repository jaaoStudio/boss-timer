import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useBossStore = defineStore('boss', () => {
  const bossTypes = ref([])
  const bossRecords = ref([])
  const history = ref([])
  const loading = ref(false)
  const selectedBossName = ref('')

  const setBossTypes = (types) => {
    bossTypes.value = types
    if (!selectedBossName.value && types.length > 0) {
      selectedBossName.value = types[0].boss_name
    }
  }

  const setSelectedBossName = (name) => {
    selectedBossName.value = name
  }

  const setBossRecords = (records) => {
    bossRecords.value = records
  }

  const updateBossRecord = (record) => {
    const index = bossRecords.value.findIndex(
      r => r.channel === record.channel && r.boss_name === record.boss_name
    )
    if (index >= 0) {
      bossRecords.value[index] = record
    } else {
      bossRecords.value.push(record)
    }
  }

  const setHistory = (historyData) => {
    history.value = historyData
  }

  const setLoading = (status) => {
    loading.value = status
  }

  // 計算屬性：按頻道分組的記錄
  const recordsByChannel = computed(() => {
    const grouped = {}
    bossRecords.value.forEach(record => {
      if (!grouped[record.channel]) {
        grouped[record.channel] = []
      }
      grouped[record.channel].push(record)
    })
    return grouped
  })

  // 計算屬性：建議的頻道（有可能重生的）
  const priorityChannels = computed(() => {
    return bossRecords.value
      .filter(record => record.current_status === 'may_respawn')
      .sort((a, b) => new Date(a.respawn_min_time) - new Date(b.respawn_min_time))
  })

  // 計算屬性：避免查看的頻道（重生中）
  const avoidChannels = computed(() => {
    return bossRecords.value
      .filter(record => record.current_status === 'respawning')
      .sort((a, b) => new Date(a.respawn_max_time) - new Date(b.respawn_max_time))
  })

  return {
    bossTypes,
    bossRecords,
    history,
    loading,
    recordsByChannel,
    priorityChannels,
    avoidChannels,
    setBossTypes,
    setBossRecords,
    updateBossRecord,
    setHistory,
    setLoading,
    selectedBossName,
    setSelectedBossName
  }
})