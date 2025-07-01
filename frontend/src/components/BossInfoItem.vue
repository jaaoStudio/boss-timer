<template>
  <div>
    <span class="text-gray-400">{{ label }}:</span>
    <span class="ml-2" :class="color">{{ value }}</span>
  </div>
</template>

<script setup>
defineProps({
  label: {
    type: String,
    required: true
  },
  value: {
    type: String,
    required: true
  },
  color: {
    type: String,
    default: 'text-white'
  }
})
</script>