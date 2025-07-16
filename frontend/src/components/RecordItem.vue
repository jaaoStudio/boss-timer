<template>
  <div class="bg-gray-700 rounded-lg p-3 transition-all duration-200 ease-in-out hover:bg-gray-600">
    <div class="flex justify-between items-center">
      <div class="flex items-center space-x-3">
        <StatusBadge :status="record.status" />
        <div>
          <span class="font-semibold text-white">{{ record.boss_name }}</span>
          <span class="text-gray-300 font-mono">- CH{{ record.channel }}</span>
          <span class="text-xs text-gray-500 ml-2">by {{ recorderDisplayName }}</span>
        </div>
      </div>
      <div class="text-sm text-gray-400">{{ formattedTime }}</div>
    </div>
    <div v-if="record.respawn_min_time" class="text-xs text-gray-400 mt-1 pl-10">
      Respawn Window: {{ formatRespawnTime(record.respawn_min_time) }} - {{ formatRespawnTime(record.respawn_max_time) }}
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import StatusBadge from './StatusBadge.vue'

const props = defineProps({
  record: {
    type: Object,
    required: true,
  },
})

const recorderDisplayName = computed(() => {
  console.log(props.record)
  // 優先顯示已登入的使用者資訊 (recorder 是關聯的 User 物件)
  if (props.record.recorder && props.record.recorder.display_name) {
    return props.record.recorder.display_name;
  }
  // 其次顯示匿名的 recorder_info
  if (props.record.recorder_info && props.record.recorder_info.anonymous_name) {
    return props.record.recorder_info.anonymous_name;
  }
  // 最後的備用選項
  return '匿名';
});


const formatTime = (time) => new Date(time).toLocaleString('en-US')
const formatRespawnTime = (time) => new Date(time).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })

const formattedTime = computed(() => formatTime(props.record.recorded_at))

</script>