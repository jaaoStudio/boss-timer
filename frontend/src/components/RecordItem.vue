<template>
  <div class="bg-gray-100 dark:bg-gray-700 rounded-lg p-3 transition-all duration-200 ease-in-out hover:bg-gray-200 dark:hover:bg-gray-600">
    <div class="flex justify-between items-center">
      <div class="flex items-center space-x-3">
        <StatusBadge :status="record.status" />
        <div>
          <span class="font-semibold text-gray-900 dark:text-white">{{ locale === 'zh' ? record.boss_type.name_zh : record.boss_type.name_en }}</span>
          <span class="text-gray-600 dark:text-gray-300 font-mono">- CH{{ record.channel }}</span>
          <span class="text-xs text-gray-500 ml-2">{{ t('recordItem.by') }} {{ recorderDisplayName }}</span>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <div class="text-sm text-gray-500 dark:text-gray-400">{{ formattedTime }}</div>
        <el-button
          type="danger"
          size="small"
          circle
          plain
          @click.stop="$emit('delete', record.id)"
          class="!p-1 h-6 w-6"
        >
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
    </div>
    <div v-if="record.respawn_min_time" class="text-xs text-gray-500 dark:text-gray-400 mt-1 pl-10">
      {{ t('recordItem.respawnWindow') }} {{ formatRespawnTime(record.respawn_min_time) }} - {{ formatRespawnTime(record.respawn_max_time) }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import StatusBadge from './StatusBadge.vue'
import { useI18n } from 'vue-i18n'

import { Delete } from '@element-plus/icons-vue'

const { t, locale } = useI18n()

interface Record {
  id: number
  room_id: string
  status: string
  boss_type: {
    name_zh: string
    name_en: string
  }
  channel: number
  recorded_at: string
  respawn_min_time?: string
  respawn_max_time?: string
  recorder?: {
    display_name: string
  }
  recorder_info?: {
    anonymous_name: string
  }
}

const props = defineProps<{
  record: Record
}>()

const emit = defineEmits<{
  (e: 'delete', id: number): void
}>()

const recorderDisplayName = computed(() => {
  // 優先顯示已登入的使用者資訊 (recorder 是關聯的 User 物件)
  if (props.record.recorder && props.record.recorder.display_name) {
    return props.record.recorder.display_name
  }
  // 其次顯示匿名的 recorder_info
  if (props.record.recorder_info && props.record.recorder_info.anonymous_name) {
    return props.record.recorder_info.anonymous_name
  }
  // 最後的備用選項
  return t('recordItem.anonymous')
})


const formatTime = (time: string) => new Date(time).toLocaleString('en-US')
const formatRespawnTime = (time: string) => new Date(time).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })

const formattedTime = computed(() => formatTime(props.record.recorded_at))
</script>