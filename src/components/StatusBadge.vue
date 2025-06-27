<template>
  <span :class="badgeClass" class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full">
    {{ statusText }}
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: String
})

const statusConfig = {
  alive: { text: 'Alive', class: 'bg-green-700 text-white' },
  killed: { text: 'Killed', class: 'bg-red-700 text-white' },
  not_found: { text: 'Not Found', class: 'bg-gray-700 text-white' },
  respawning: { text: 'Respawning', class: 'bg-yellow-700 text-white' },
  may_respawn: { text: 'May Respawn', class: 'bg-blue-700 text-white' },
  unknown: { text: 'Unknown', class: 'bg-gray-700 text-white' }
}

const statusText = computed(() => {
  return statusConfig[props.status]?.text || 'Unknown'
})

const badgeClass = computed(() => {
  return statusConfig[props.status]?.class || 'bg-gray-700 text-white'
})
</script>