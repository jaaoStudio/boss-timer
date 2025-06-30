<template>
  <div class="bg-gray-800 rounded-lg shadow-md p-6 mb-6" v-if="selectedBoss">
    <h2 class="text-xl font-semibold text-white mb-4">{{ selectedBoss.boss_name }} 詳細資訊</h2>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <!-- 基本資訊 -->
      <div>
        <h3 class="text-lg font-medium text-gray-300 mb-2">基本資訊</h3>
        <div class="space-y-2">
          <div class="flex justify-between">
            <span class="text-gray-400">重生時間:</span>
            <span class="font-medium text-gray-200">{{ selectedBoss.min_respawn_minutes }} - {{ selectedBoss.max_respawn_minutes }} 分鐘</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-400">描述:</span>
            <span class="font-medium text-gray-200">{{ selectedBoss.description || '無' }}</span>
          </div>
        </div>
      </div>

      <!-- 當前狀態 -->
      <div>
        <h3 class="text-lg font-medium text-gray-300 mb-2">當前狀態</h3>
        <div class="space-y-2">
          <div class="flex justify-between">
            <span class="text-gray-400">頻道:</span>
            <span class="font-medium text-gray-200">{{ selectedRecord?.channel }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-400">狀態:</span>
            <StatusBadge :status="selectedRecord?.current_status" />
          </div>
          <div class="flex justify-between">
            <span class="text-gray-400">記錄時間:</span>
            <span class="font-medium text-gray-200">{{ formatTime(selectedRecord?.recorded_at) }}</span>
          </div>
        </div>
      </div>

      <!-- 重生時間 -->
      <div v-if="selectedRecord?.respawn_min_time">
        <h3 class="text-lg font-medium text-gray-300 mb-2">重生倒數</h3>
        <div class="space-y-2">
          <div class="flex justify-between">
            <span class="text-gray-400">最早重生:</span>
            <CountdownTimer :target-time="selectedRecord.respawn_min_time" />
          </div>
          <div class="flex justify-between">
            <span class="text-gray-400">最遲重生:</span>
            <CountdownTimer :target-time="selectedRecord.respawn_max_time" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useBossStore } from '../stores/bossStore'
import StatusBadge from './StatusBadge.vue'
import CountdownTimer from './CountdownTimer.vue'

const bossStore = useBossStore()
const { bossTypes, bossRecords, selectedBossName, selectedChannel } = storeToRefs(bossStore)

console.log(bossTypes.value, bossRecords.value, selectedBossName.value ,1233)

const selectedBoss = computed(() => {
  return bossTypes.value.find(b => b.boss_name === selectedBossName.value)
})



const selectedRecord = computed(() => {
  return bossRecords.value.find(r => r.boss_name === selectedBossName.value && r.channel === selectedChannel.value)
})

import { format } from 'date-fns'

const formatTime = (timeString) => {
  if (!timeString) return 'N/A'
  return format(new Date(timeString), 'yyyy-MM-dd HH:mm:ss')
}
</script>