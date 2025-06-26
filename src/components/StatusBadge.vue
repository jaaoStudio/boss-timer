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
  alive: { text: 'Alive', class: 'bg-green-100 text-green-800' },
  killed: { text: 'Killed', class: 'bg-red-100 text-red-800' },
  not_found: { text: 'Not Found', class: 'bg-gray-100 text-gray-800' },
  respawning: { text: 'Respawning', class: 'bg-yellow-100 text-yellow-800' },
  may_respawn: { text: 'May Respawn', class: 'bg-blue-100 text-blue-800' },
  unknown: { text: 'Unknown', class: 'bg-gray-100 text-gray-800' }
}

const statusText = computed(() => {
  return statusConfig[props.status]?.text || 'Unknown'
})

const badgeClass = computed(() => {
  return statusConfig[props.status]?.class || 'bg-gray-100 text-gray-800'
})
</script>