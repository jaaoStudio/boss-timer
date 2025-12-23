<template>
  <div :class="['p-2', 'rounded-lg', 'text-center', 'cursor-pointer', 'transition-all', 'duration-200', 'ease-in-out', statusBackgroundClass]" @click="selectChannel">
    <div :class="['font-bold', channelNumber >= 1000 ? 'text-xs' : 'text-sm']">CH {{ channelNumber }}</div>
    <div class="text-xs font-medium">{{ statusText }}</div>
  </div>
</template>

<script setup>
import {computed} from 'vue'
import {storeToRefs} from 'pinia'
import {useBossStore} from '@/stores/bossStore.js'
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const props = defineProps({
  channelNumber: {
    type: Number,
    required: true,
  },
})

const bossStore = useBossStore()
const { bossRecords, selectedBossTypeId } = storeToRefs(bossStore)

const record = computed(() => {
  const foundRecord = bossRecords.value.find(
    r => r.channel === props.channelNumber && r.boss_type_id === selectedBossTypeId.value
  )
  return foundRecord
})

const status = computed(() => {
  return record.value?.current_status || 'unknown'
})

const statusMapping = computed(() => ({
  alive: { text: t('status.alive'), bg: 'bg-green-700 text-white' },
  killed: { text: t('status.killed'), bg: 'bg-red-700 text-white' },
  may_respawn: { text: t('status.mayRespawn'), bg: 'bg-yellow-700 text-white' },
  respawning: { text: t('status.respawning'), bg: 'bg-blue-700 text-white' },
  not_found: { text: t('status.notFound'), bg: 'bg-gray-400 dark:bg-gray-700 text-white' },
  unknown: { text: t('status.unknown'), bg: 'bg-gray-200 dark:bg-gray-600 text-gray-600 dark:text-gray-300' },
}))

const statusBackgroundClass = computed(() => statusMapping.value[status.value]?.bg || statusMapping.value.unknown.bg)
const statusText = computed(() => statusMapping.value[status.value]?.text || statusMapping.value.unknown.text)

const selectChannel = () => {
  bossStore.setSelectedChannel(props.channelNumber)
}

</script>