<template>
  <span :class="timeClass" class="font-mono font-medium tabular-nums">
    {{ displayTime }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useTimer } from '@/composables/useTimer'

const props = withDefaults(defineProps<{
  targetTime: string | null | undefined
  prefix?: string
}>(), {
  prefix: ''
})

const emit = defineEmits<{
  (e: 'timer-end', targetTime: string | null | undefined): void
}>()

const onTimerEnd = () => {
  emit('timer-end', props.targetTime)
}

const targetTimeRef = computed(() => props.targetTime)
const { timeLeft, formattedTime } = useTimer(targetTimeRef, onTimerEnd)

const displayTime = computed(() => {
  return props.prefix ? `${props.prefix} ${formattedTime.value}` : formattedTime.value
})

const timeClass = computed(() => {
  if (timeLeft.value <= 0) return 'text-green-500 dark:text-green-400'
  if (timeLeft.value <= 300000) return 'text-red-500 dark:text-red-400'
  if (timeLeft.value <= 600000) return 'text-yellow-500 dark:text-yellow-300'
  return 'text-gray-600 dark:text-gray-300'
})
</script>