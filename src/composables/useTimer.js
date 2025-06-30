import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

export function useTimer(targetTime, onEnd) {
  const now = ref(Date.now())
  const interval = ref(null)

  const timeLeft = computed(() => {
    if (!targetTime.value) return 0
    const diff = new Date(targetTime.value).getTime() - now.value
    return Math.max(0, diff)
  })

  watch(timeLeft, (newVal) => {
    if (newVal <= 0) {
      if (onEnd) onEnd()
    }
  })

  const formattedTime = computed(() => {
    const total = Math.floor(timeLeft.value / 1000)
    const hours = Math.floor(total / 3600)
    const minutes = Math.floor((total % 3600) / 60)
    const seconds = total % 60

    if (hours > 0) {
      return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`
    }
    return `${minutes}:${seconds.toString().padStart(2, '0')}`
  })

  const startTimer = () => {
    if (interval.value) return
    interval.value = setInterval(() => {
      now.value = Date.now()
    }, 1000)
  }

  const stopTimer = () => {
    if (interval.value) {
      clearInterval(interval.value)
      interval.value = null
    }
  }

  onMounted(startTimer)
  onUnmounted(stopTimer)

  return {
    timeLeft,
    formattedTime,
    startTimer,
    stopTimer
  }
}