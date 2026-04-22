<template>
  <span :class="badgeClass" class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full">
    {{ statusText }}
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{
  status?: string
}>()

interface StatusConfig {
  text: string
  class: string
}

const statusConfig = computed<Record<string, StatusConfig>>(() => ({
  alive: { text: t('status.alive'), class: 'bg-green-700 text-white' },
  killed: { text: t('status.killed'), class: 'bg-red-700 text-white' },
  not_found: { text: t('status.notFound'), class: 'bg-gray-700 text-white' },
  respawning: { text: t('status.respawning'), class: 'bg-yellow-700 text-white' },
  may_respawn: { text: t('status.mayRespawn'), class: 'bg-blue-700 text-white' },
  unknown: { text: t('status.unknown'), class: 'bg-gray-700 text-white' }
}))

const currentConfig = computed(() => {
  const key = props.status || 'unknown'
  return statusConfig.value[key] || statusConfig.value.unknown
})

const statusText = computed(() => currentConfig.value.text)
const badgeClass = computed(() => currentConfig.value.class)
</script>