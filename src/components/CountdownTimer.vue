<template>
  <span :class="timeClass" class="font-mono font-medium">
    {{ displayTime }}
  </span>
</template>

<script setup>
import { computed, defineEmits } from 'vue'
import { useTimer } from '../composables/useTimer'

const props = defineProps({
  targetTime: String,
  prefix: { // 新增 prefix prop
    type: String,
    default: ''
  }
})

const emit = defineEmits(['timer-end'])

const onTimerEnd = () => {
  emit('timer-end', props.targetTime)
}

const targetTimeRef = computed(() => props.targetTime)
const { timeLeft, formattedTime } = useTimer(targetTimeRef, onTimerEnd)

const displayTime = computed(() => {
  return props.prefix ? `${props.prefix} ${formattedTime.value}` : formattedTime.value
})

const timeClass = computed(() => {
  if (timeLeft.value <= 0) return 'text-green-600'
  if (timeLeft.value <= 300000) return 'text-red-600' // 5分鐘內
  if (timeLeft.value <= 600000) return 'text-yellow-600' // 10分鐘內
  return 'text-gray-600'
})
</script>