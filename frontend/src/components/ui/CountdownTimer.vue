<template>
  <span :class="timeClass" class="font-mono font-medium">
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
  if (timeLeft.value <= 0) return 'text-green-400' // 倒數結束
  if (timeLeft.value <= 300000) return 'text-red-400' // 5分鐘內
  if (timeLeft.value <= 600000) return 'text-yellow-300' // 10分鐘內
  return 'text-gray-300' // 預設顏色
})
</script>