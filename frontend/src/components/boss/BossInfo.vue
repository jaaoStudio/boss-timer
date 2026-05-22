<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6" v-if="selectedBoss">
    <h2 class="text-xl font-semibold text-gray-900 dark:text-white mb-4">
      {{ locale === 'zh' ? selectedBoss.name_zh : selectedBoss.name_en }}
    </h2>

    <div class="grid grid-cols-1 @lg:grid-cols-2 gap-x-8 gap-y-1">
      <!-- 基本資訊 -->
      <div class="space-y-1.5">
        <p class="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500 mb-1">
          {{ t('bossInfo.basicInfo') }}
        </p>
        <div class="flex items-center justify-between py-1 border-b border-gray-100 dark:border-gray-700">
          <span class="text-sm text-gray-500 dark:text-gray-400">{{ t('bossInfo.respawnTime') }}</span>
          <span class="text-sm font-medium text-gray-800 dark:text-gray-200">
            {{ selectedBoss.min_respawn_minutes }} – {{ selectedBoss.max_respawn_minutes }} {{ t('bossInfo.minutes') }}
          </span>
        </div>
        <div class="flex items-center justify-between py-1 border-b border-gray-100 dark:border-gray-700">
          <span class="text-sm text-gray-500 dark:text-gray-400">{{ t('bossInfo.description') }}</span>
          <span class="text-sm font-medium text-gray-800 dark:text-gray-200 text-right max-w-[60%] break-words">
            {{ selectedBoss.description || t('bossInfo.none') }}
          </span>
        </div>
      </div>

      <!-- 當前狀態 -->
      <div class="space-y-1.5 mt-4 @lg:mt-0">
        <p class="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500 mb-1">
          {{ t('bossInfo.currentStatus') }}
        </p>
        <div class="flex items-center justify-between py-1 border-b border-gray-100 dark:border-gray-700">
          <span class="text-sm text-gray-500 dark:text-gray-400">{{ t('bossInfo.channel') }}</span>
          <span class="text-sm font-medium text-gray-800 dark:text-gray-200">{{ selectedRecord?.channel ?? '—' }}</span>
        </div>
        <div class="flex items-center justify-between py-1 border-b border-gray-100 dark:border-gray-700">
          <span class="text-sm text-gray-500 dark:text-gray-400">{{ t('bossInfo.status') }}</span>
          <StatusBadge :status="selectedStatus" />
        </div>
        <div class="flex items-center justify-between py-1 border-b border-gray-100 dark:border-gray-700">
          <span class="text-sm text-gray-500 dark:text-gray-400">{{ t('bossInfo.recordTime') }}</span>
          <span class="text-sm font-medium text-gray-800 dark:text-gray-200">{{ formatTime(selectedRecord?.recorded_at) }}</span>
        </div>
      </div>

      <!-- 重生時間 -->
      <div v-if="selectedRecord?.respawn_min_time" class="space-y-1.5 mt-4 @lg:col-span-2">
        <p class="text-xs font-semibold uppercase tracking-wide text-gray-400 dark:text-gray-500 mb-1">
          {{ t('bossInfo.respawnCountdown') }}
        </p>
        <div class="flex items-center justify-between py-1 border-b border-gray-100 dark:border-gray-700">
          <span class="text-sm text-gray-500 dark:text-gray-400">{{ t('bossInfo.earliestRespawn') }}</span>
          <CountdownTimer :target-time="selectedRecord.respawn_min_time" />
        </div>
        <div class="flex items-center justify-between py-1 border-b border-gray-100 dark:border-gray-700">
          <span class="text-sm text-gray-500 dark:text-gray-400">{{ t('bossInfo.latestRespawn') }}</span>
          <CountdownTimer :target-time="selectedRecord.respawn_max_time" />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useBossStore, calculateCurrentStatus } from '@/stores/bossStore'
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

const selectedStatus = computed(() =>
  selectedRecord.value ? calculateCurrentStatus(selectedRecord.value, new Date(bossStore._now)) : undefined
)

const formatTime = (timeString: string | null | undefined) => {
  if (!timeString) return t('bossInfo.notAvailable')
  return format(new Date(timeString), 'yyyy-MM-dd HH:mm:ss')
}
</script>