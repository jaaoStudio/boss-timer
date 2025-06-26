<template>
  <div class="bg-white rounded-lg shadow-md p-6 mb-6" v-if="selectedBoss">
    <h2 class="text-xl font-semibold text-gray-800 mb-4">{{ selectedBoss.boss_name }} 詳細資訊</h2>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <!-- 基本資訊 -->
      <div>
        <h3 class="text-lg font-medium text-gray-700 mb-2">基本資訊</h3>
        <div class="space-y-2">
          <div class="flex justify-between">
            <span class="text-gray-600">重生時間:</span>
            <span class="font-medium">{{ selectedBoss.min_respawn_minutes }} - {{ selectedBoss.max_respawn_minutes }} 分鐘</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-600">描述:</span>
            <span class="font-medium">{{ selectedBoss.description || '無' }}</span>
          </div>
        </div>
      </div>

      <!-- 當前狀態 -->
      <div>
        <h3 class="text-lg font-medium text-gray-700 mb-2">當前狀態</h3>
        <div class="space-y-2">
          <div class="flex justify-between">
            <span class="text-gray-600">頻道:</span>
            <span class="font-medium">{{ selectedRecord?.channel }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-600">狀態:</span>
            <StatusBadge :status="selectedRecord?.current_status" />
          </div>
          <div class="flex justify-between">
            <span class="text-gray-600">記錄時間:</span>
            <span class="font-medium">{{ formatTime(selectedRecord?.recorded_at) }}</span>
          </div>
        </div>
      </div>

      <!-- 重生時間 -->
      <div v-if="selectedRecord?.respawn_min_time">
        <h3 class="text-lg font-medium text-gray-700 mb-2">重生倒數</h3>
        <div class="space-y-2">
          <div class="flex justify-between">
            <span class="text-gray-600">最早重生:</span>
            <CountdownTimer :target-time="selectedRecord.respawn_min_time" />
          </div>
          <div class="flex justify-between">
            <span class="text-gray-600">最遲重生:</span>
            <CountdownTimer :target-time="selectedRecord.respawn_max_time" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useBossStore } from '../stores/bossStore'
import StatusBadge from './StatusBadge.vue'
import CountdownTimer from './CountdownTimer.vue'

const bossStore = useBossStore()

const selectedBoss = computed(() => {
  return bossStore.bossTypes.find(b => b.boss_name === bossStore.selectedBossName)
})

const selectedRecord = computed(() => {
  return bossStore.bossRecords.find(r => r.boss_name === bossStore.selectedBossName)
})

const formatTime = (timeString) => {
  if (!timeString) return 'N/A'
  return new Date(timeString).toLocaleString('en-US')
}
</script>