<template>
  <span :class="timeClass" class="font-mono font-medium">
    {{ formattedTime }}
  </span>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useTimer } from '../composables/useTimer'

const props = defineProps({
  targetTime: String
})

const targetTimeRef = computed(() => props.targetTime)
const { timeLeft, formattedTime } = useTimer(targetTimeRef)

const timeClass = computed(() => {
  if (timeLeft.value <= 0) return 'text-green-600'
  if (timeLeft.value <= 300000) return 'text-red-600' // 5分鐘內
  if (timeLeft.value <= 600000) return 'text-yellow-600' // 10分鐘內
  return 'text-gray-600'
})
</script>