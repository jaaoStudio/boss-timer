import { ref, computed } from 'vue'

export function useBossRecords(selectedBoss, selectedChannel) {
  const records = ref([])

  const recordBossStatus = (status, boss) => {
    const now = new Date()

    const record = {
      id: Date.now(),
      bossId: selectedBoss.value,
      channel: selectedChannel.value,
      status: status,
      timestamp: now.getTime()
    }

    // 如果是擊殺記錄，計算重生時間
    if (status === 'dead') {
      const respawnTimeMin = now.getTime() + (boss.respawnMin * 60 * 1000)
      const respawnTimeMax = now.getTime() + (boss.respawnMax * 60 * 1000)
      record.respawnTime = respawnTimeMax // 使用最大重生時間作為安全估計
      record.respawnTimeMin = respawnTimeMin
    }

    records.value.unshift(record)
  }

  const getChannelStatus = (channel, bossId) => {
    if (!bossId) return null

    const channelRecords = records.value.filter(r =>
      r.channel === channel && r.bossId === bossId
    )

    if (channelRecords.length === 0) return null

    // 獲取最新記錄
    const latestRecord = channelRecords[0]
    const now = Date.now()

    if (latestRecord.status === 'dead' && latestRecord.respawnTime) {
      if (now < latestRecord.respawnTime) {
        return 'respawning'
      } else {
        return 'may_be_alive'
      }
    }

    return latestRecord.status
  }

  const getChannelStatusText = (channel, bossId) => {
    const status = getChannelStatus(channel, bossId)
    const statusMap = {
      'alive': '存在',
      'dead': '已死',
      'not_found': '未發現',
      'respawning': '重生中',
      'may_be_alive': '可能存在'
    }
    return statusMap[status] || '未知'
  }

  const getChannelStatusColor = (channel, bossId) => {
    const status = getChannelStatus(channel, bossId)
    const colorMap = {
      'alive': 'text-green-400',
      'dead': 'text-red-400',
      'not_found': 'text-yellow-400',
      'respawning': 'text-orange-400',
      'may_be_alive': 'text-blue-400'
    }
    return colorMap[status] || 'text-gray-400'
  }

  const getRecommendedChannels = () => {
    if (!selectedBoss.value) return { priority: [], avoid: [] }

    const now = Date.now()
    const priority = []
    const avoid = []

    // 獲取所有該BOSS的記錄頻道
    const recordedChannels = new Set(
      records.value
        .filter(r => r.bossId === selectedBoss.value)
        .map(r => r.channel)
    )

    // 只檢查有記錄的頻道
    recordedChannels.forEach(channel => {
      const status = getChannelStatus(channel, selectedBoss.value)

      if (status === 'may_be_alive' || status === 'alive') {
        priority.push(channel)
      } else if (status === 'respawning') {
        const record = records.value.find(r =>
          r.channel === channel &&
          r.bossId === selectedBoss.value &&
          r.status === 'dead'
        )

        if (record && record.respawnTime) {
          const timeLeft = record.respawnTime - now
          const minutesLeft = Math.ceil(timeLeft / (60 * 1000))
          if (minutesLeft > 0) {
            avoid.push({
              channel,
              timeLeft: `${minutesLeft}分鐘後`
            })
          } else {
            // 重生時間已過，加入優先查看
            priority.push(channel)
          }
        }
      }
    })

    // 排序
    priority.sort((a, b) => a - b)
    avoid.sort((a, b) => a.channel - b.channel)

    return { priority, avoid }
  }

  const getRecordedChannelsCount = () => {
    if (!selectedBoss.value) return 0
    return new Set(
      records.value
        .filter(r => r.bossId === selectedBoss.value)
        .map(r => r.channel)
    ).size
  }

  const getFilteredRecords = () => {
    if (!selectedBoss.value) return records.value.slice(0, 10)
    return records.value.filter(r => r.bossId === selectedBoss.value).slice(0, 10)
  }

  const getStatusText = (status) => {
    const statusMap = {
      'alive': '發現活著',
      'dead': '擊殺',
      'not_found': '未發現'
    }
    return statusMap[status] || status
  }

  const getStatusColor = (status) => {
    const colorMap = {
      'alive': 'text-green-400',
      'dead': 'text-red-400',
      'not_found': 'text-yellow-400'
    }
    return colorMap[status] || 'text-gray-400'
  }

  const formatTime = (timestamp) => {
    return new Date(timestamp).toLocaleString('zh-TW', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  return {
    records,
    recordBossStatus,
    getChannelStatus,
    getChannelStatusText,
    getChannelStatusColor,
    getRecommendedChannels,
    getRecordedChannelsCount,
    getFilteredRecords,
    getStatusText,
    getStatusColor,
    formatTime
  }
}