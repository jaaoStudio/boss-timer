<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 mb-6" v-if="selectedBoss">
    <h2 class="text-xl font-semibold text-gray-900 dark:text-white mb-4">{{ locale === 'zh' ? selectedBoss.name_zh : selectedBoss.name_en }}</h2>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <!-- 基本資訊 -->
      <div>
        <h3 class="text-lg font-medium text-gray-700 dark:text-gray-300 mb-2">{{ t('bossInfo.basicInfo') }}</h3>
        <div class="space-y-2">
          <div class="flex justify-between">
            <span class="text-gray-500 dark:text-gray-400">{{ t('bossInfo.respawnTime') }}</span>
            <span class="font-medium text-gray-800 dark:text-gray-200">{{ selectedBoss.min_respawn_minutes }} - {{ selectedBoss.max_respawn_minutes }} {{ t('bossInfo.minutes') }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500 dark:text-gray-400">{{ t('bossInfo.description') }}</span>
            <span class="font-medium text-gray-800 dark:text-gray-200">{{ selectedBoss.description || t('bossInfo.none') }}</span>
          </div>
        </div>
      </div>

      <!-- 當前狀態 -->
      <div>
        <h3 class="text-lg font-medium text-gray-700 dark:text-gray-300 mb-2">{{ t('bossInfo.currentStatus') }}</h3>
        <div class="space-y-2">
          <div class="flex justify-between">
            <span class="text-gray-500 dark:text-gray-400">{{ t('bossInfo.channel') }}</span>
            <span class="font-medium text-gray-800 dark:text-gray-200">{{ selectedRecord?.channel }}</span>
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500 dark:text-gray-400">{{ t('bossInfo.status') }}</span>
            <StatusBadge :status="selectedRecord?.current_status" />
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500 dark:text-gray-400">{{ t('bossInfo.recordTime') }}</span>
            <span class="font-medium text-gray-800 dark:text-gray-200">{{ formatTime(selectedRecord?.recorded_at) }}</span>
          </div>
        </div>
      </div>

      <!-- 重生時間 -->
      <div v-if="selectedRecord?.respawn_min_time">
        <h3 class="text-lg font-medium text-gray-700 dark:text-gray-300 mb-2">{{ t('bossInfo.respawnCountdown') }}</h3>
        <div class="space-y-2">
          <div class="flex justify-between">
            <span class="text-gray-500 dark:text-gray-400">{{ t('bossInfo.earliestRespawn') }}</span>
            <CountdownTimer :target-time="selectedRecord.respawn_min_time" />
          </div>
          <div class="flex justify-between">
            <span class="text-gray-500 dark:text-gray-400">{{ t('bossInfo.latestRespawn') }}</span>
            <CountdownTimer :target-time="selectedRecord.respawn_max_time" />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useBossStore } from '@/stores/bossStore'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import CountdownTimer from '@/components/ui/CountdownTimer.vue'
import { useI18n } from 'vue-i18n'
import { format } from 'date-fns'

const { t, locale } = useI18n()
const bossStore = useBossStore()
const { bossTypes, bossRecords, selectedBossTypeId, selectedChannel } = storeToRefs(bossStore)

const selectedBoss = computed(() => {
  return bossTypes.value.find(b => b.id === selectedBossTypeId.value)
})

const selectedRecord = computed(() => {
  return bossRecords.value.find(r => r.boss_type_id === selectedBossTypeId.value && r.channel === selectedChannel.value)
})

const formatTime = (timeString: string | null | undefined) => {
  if (!timeString) return t('bossInfo.notAvailable')
  return format(new Date(timeString), 'yyyy-MM-dd HH:mm:ss')
}
</script>