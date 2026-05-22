<template>
  <div
    :class="['relative', 'p-2', 'rounded-lg', 'text-center', 'cursor-pointer', 'transition-all', 'duration-200', 'ease-in-out', statusBackgroundClass, { 'opacity-50': isExpired }]"
    @click="selectChannel"
  >
    <div :class="['font-bold', channelNumber >= 1000 ? 'text-xs' : 'text-sm']">CH {{ channelNumber }}</div>
    <div class="text-xs font-medium">{{ statusText }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useBossStore, calculateCurrentStatus } from '@/stores/bossStore'
import { useStatusConfig, isExpiredRecord } from '@/composables/useStatusConfig'

const props = defineProps<{
  channelNumber: number
}>()

const bossStore = useBossStore()
const { bossRecords, selectedBossTypeId } = storeToRefs(bossStore)
const { getStatusConfig } = useStatusConfig()

const record = computed(() =>
  bossRecords.value.find(
    (r) => r.channel === props.channelNumber && r.boss_type_id === selectedBossTypeId.value
  )
)

const status = computed(() =>
  record.value ? calculateCurrentStatus(record.value, new Date(bossStore._now)) : 'unknown'
)
const isExpired = computed(() => isExpiredRecord(record.value, status.value))

const config = computed(() => getStatusConfig(status.value, isExpired.value))
const statusBackgroundClass = computed(() => config.value.bgClass)
const statusText = computed(() => config.value.text)

const selectChannel = () => {
  bossStore.setSelectedChannel(props.channelNumber)
}
</script>