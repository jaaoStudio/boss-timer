<template>
  <div class="bg-gray-700 rounded-lg p-3 transition-all duration-200 ease-in-out hover:bg-gray-600">
    <div class="flex justify-between items-center">
      <div class="flex items-center space-x-3">
        <StatusBadge :status="record.status" />
        <div>
          <span class="font-semibold text-white">{{ record.boss_name }}</span>
          <span class="text-gray-300 font-mono">- CH{{ record.channel }}</span>
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

const formatTime = (time) => new Date(time).toLocaleString('en-US')
const formatRespawnTime = (time) => new Date(time).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })

const formattedTime = computed(() => formatTime(props.record.recorded_at))

</script>