<template>
  <div :class="['p-2', 'rounded-lg', 'text-center', 'cursor-pointer', 'transition-all', 'duration-200', 'ease-in-out', statusBackgroundClass]" @click="selectChannel">
    <div class="font-bold text-sm">CH {{ channelNumber }}</div>
    <div class="text-xs font-medium">{{ statusText }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { useBossStore } from '@/stores/bossStore'

const props = defineProps({
  channelNumber: {
    type: Number,
    required: true,
  },
})

const bossStore = useBossStore()

const record = computed(() => {
  return bossStore.recordsByChannel[props.channelNumber]?.find(
    r => r.boss_name === bossStore.selectedBossName
  )
})

const status = computed(() => record.value?.current_status || 'unknown')

const statusMapping = {
  alive: { text: 'Alive', bg: 'bg-green-200 text-green-800' },
  killed: { text: 'Killed', bg: 'bg-red-200 text-red-800' },
  may_respawn: { text: 'May Respawn', bg: 'bg-yellow-200 text-yellow-800' },
  respawning: { text: 'Respawning', bg: 'bg-blue-200 text-blue-800' },
  not_found: { text: 'Not Found', bg: 'bg-gray-200 text-gray-800' },
  unknown: { text: 'Unknown', bg: 'bg-gray-100 text-gray-500' },
}

const statusBackgroundClass = computed(() => statusMapping[status.value]?.bg || statusMapping.unknown.bg)
const statusText = computed(() => statusMapping[status.value]?.text || statusMapping.unknown.text)

const selectChannel = () => {
  // You can add logic here to quickly select the channel in the control panel
}

</script>