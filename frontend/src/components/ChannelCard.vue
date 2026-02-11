<template>
  <div :class="['p-2', 'rounded-lg', 'text-center', 'cursor-pointer', 'transition-all', 'duration-200', 'ease-in-out', statusBackgroundClass]" @click="selectChannel">
    <div :class="['font-bold', channelNumber >= 1000 ? 'text-xs' : 'text-sm']">CH {{ channelNumber }}</div>
    <div class="text-xs font-medium">{{ statusText }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useBossStore } from '@/stores/bossStore'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{
  channelNumber: number
}>()

const bossStore = useBossStore()
const { bossRecords, selectedBossTypeId } = storeToRefs(bossStore)

const record = computed(() => {
  return bossRecords.value.find(
    (r) => r.channel === props.channelNumber && r.boss_type_id === selectedBossTypeId.value
  )
})

const status = computed(() => {
  return record.value?.current_status || 'unknown'
})

interface StatusConfig {
  text: string
  bg: string
}

const statusMapping = computed<Record<string, StatusConfig>>(() => ({
  alive: { text: t('status.alive'), bg: 'bg-green-700 text-white' },
  killed: { text: t('status.killed'), bg: 'bg-red-700 text-white' },
  may_respawn: { text: t('status.mayRespawn'), bg: 'bg-yellow-700 text-white' },
  respawning: { text: t('status.respawning'), bg: 'bg-blue-700 text-white' },
  not_found: { text: t('status.notFound'), bg: 'bg-gray-400 dark:bg-gray-700 text-white' },
  unknown: { text: t('status.unknown'), bg: 'bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300' },
}))

const currentStatusConfig = computed(() => {
  return statusMapping.value[status.value] || statusMapping.value.unknown
})

const statusBackgroundClass = computed(() => currentStatusConfig.value.bg)
const statusText = computed(() => currentStatusConfig.value.text)

const selectChannel = () => {
  bossStore.setSelectedChannel(props.channelNumber)
}
</script>