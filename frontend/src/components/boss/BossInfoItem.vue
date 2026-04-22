<template>
  <div>
    <span class="text-gray-400">{{ label }}:</span>
    <span class="ml-2" :class="color">{{ value }}</span>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  label: string
  value: string
  color?: string
}>()
</script>