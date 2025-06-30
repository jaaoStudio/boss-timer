<template>
  <div class="bg-gray-800 rounded-lg shadow-md p-6 mb-6">
    <h2 class="text-xl font-semibold text-white mb-4">Channel Overview</h2>
    <div class="grid grid-cols-5 sm:grid-cols-6 md:grid-cols-8 lg:grid-cols-10 gap-2 overflow-auto">
      <ChannelCard
        v-for="channel in recordedChannels"
        :key="channel"
        :channel-number="channel"
      />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useBossStore } from '@/stores/bossStore'
import ChannelCard from './ChannelCard.vue'

const bossStore = useBossStore()
const { selectedBossName } = storeToRefs(bossStore)

const recordedChannels = computed(() => {
  const channels = new Set(bossStore.bossRecords.filter(r => r.boss_name === selectedBossName.value).map(r => r.channel))
  return Array.from(channels).sort((a, b) => a - b)
})
</script>