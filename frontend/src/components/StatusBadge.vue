<template>
  <span :class="badgeClass" class="px-2 inline-flex text-xs leading-5 font-semibold rounded-full">
    {{ statusText }}
  </span>
</template>

<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const props = defineProps({
  status: String
})

const statusConfig = computed(() => ({
  alive: { text: t('status.alive'), class: 'bg-green-700 text-white' },
  killed: { text: t('status.killed'), class: 'bg-red-700 text-white' },
  not_found: { text: t('status.notFound'), class: 'bg-gray-700 text-white' },
  respawning: { text: t('status.respawning'), class: 'bg-yellow-700 text-white' },
  may_respawn: { text: t('status.mayRespawn'), class: 'bg-blue-700 text-white' },
  unknown: { text: t('status.unknown'), class: 'bg-gray-700 text-white' }
}))

const statusText = computed(() => {
  return statusConfig.value[props.status]?.text || t('status.unknown')
})

const badgeClass = computed(() => {
  return statusConfig.value[props.status]?.class || 'bg-gray-700 text-white'
})
</script>