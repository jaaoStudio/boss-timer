<template>
  <div class="rounded-lg p-4" :class="containerClass">
    <h3 class="font-bold mb-3" :class="titleClass">{{ title }}</h3>
    <div v-if="channels.length > 0" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
      <div v-for="record in channels" :key="record.id" class="p-2 rounded-md text-center" :class="itemClass">
        <div class="font-semibold">CH {{ record.channel }}</div>
        <div class="text-xs">
          <CountdownTimer v-if="type === 'priority'" :target-time="record.respawn_min_time" :prefix="'in'" />
          <CountdownTimer v-if="type === 'avoid'" :target-time="record.respawn_max_time" :prefix="'until'" />
        </div>
      </div>
    </div>
    <div v-else class="text-sm" :class="emptyStateClass">
      No channels to display.
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import CountdownTimer from './CountdownTimer.vue'

const props = defineProps({
  title: {
    type: String,
    required: true,
  },
  channels: {
    type: Array,
    required: true,
  },
  type: {
    type: String,
    required: true,
    validator: (value) => ['priority', 'avoid'].includes(value),
  },
})

const typeClasses = {
  priority: {
    container: 'bg-green-100',
    title: 'text-green-800',
    item: 'bg-green-200 text-green-900',
    empty: 'text-green-700',
  },
  avoid: {
    container: 'bg-red-100',
    title: 'text-red-800',
    item: 'bg-red-200 text-red-900',
    empty: 'text-red-700',
  },
}

const containerClass = computed(() => typeClasses[props.type].container)
const titleClass = computed(() => typeClasses[props.type].title)
const itemClass = computed(() => typeClasses[props.type].item)
const emptyStateClass = computed(() => typeClasses[props.type].empty)
</script>