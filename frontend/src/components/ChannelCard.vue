<template>
  <div :class="['p-2', 'rounded-lg', 'text-center', 'cursor-pointer', 'transition-all', 'duration-200', 'ease-in-out', statusBackgroundClass]" @click="selectChannel">
    <div :class="['font-bold', channelNumber >= 1000 ? 'text-xs' : 'text-sm']">CH {{ channelNumber }}</div>
    <div class="text-xs font-medium">{{ statusText }}</div>
  </div>
</template>

<script setup>
import {computed} from 'vue'
import {storeToRefs} from 'pinia'
import {useBossStore} from '@/stores/bossStore'

const props = defineProps({
  channelNumber: {
    type: Number,
    required: true,
  },
})

const bossStore = useBossStore()
const { bossRecords, selectedBossName } = storeToRefs(bossStore)

const record = computed(() => {
  const foundRecord = bossRecords.value.find(
    r => r.channel === props.channelNumber && r.boss_name === selectedBossName.value
  )
  // console.log(`Channel ${props.channelNumber}, Boss ${selectedBossName.value}: Found record`, foundRecord)
  return foundRecord
})

const status = computed(() => {
  // console.log(`Channel ${props.channelNumber}, Boss ${selectedBossName.value}: Status`, currentStatus)
  return record.value?.current_status || 'unknown'
})

const statusMapping = {
  alive: { text: 'Alive', bg: 'bg-green-700 text-white' },
  killed: { text: 'Killed', bg: 'bg-red-700 text-white' },
  may_respawn: { text: 'May Respawn', bg: 'bg-yellow-700 text-white' },
  respawning: { text: 'Respawning', bg: 'bg-blue-700 text-white' },
  not_found: { text: 'Not Found', bg: 'bg-gray-700 text-white' },
  unknown: { text: 'Unknown', bg: 'bg-gray-600 text-gray-300' },
}

const statusBackgroundClass = computed(() => statusMapping[status.value]?.bg || statusMapping.unknown.bg)
const statusText = computed(() => statusMapping[status.value]?.text || statusMapping.unknown.text)

const selectChannel = () => {
  bossStore.setSelectedChannel(props.channelNumber)
}

</script>