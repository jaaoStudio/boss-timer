<template>
  <span :class="badgeClass" class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full">
    {{ statusText }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useStatusConfig } from '@/composables/useStatusConfig'

const props = defineProps<{
  status?: string
}>()

const { getStatusConfig } = useStatusConfig()

const config = computed(() => getStatusConfig(props.status || 'unknown'))
const statusText = computed(() => config.value.text)
const badgeClass = computed(() => config.value.bgClass)
</script>