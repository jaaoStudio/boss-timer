<template>
  <div class="bg-gray-800 rounded-lg shadow-md p-6 mb-6">
    <h2 class="text-xl font-semibold text-white mb-4">Recommended Channels</h2>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <RecommendedSection
        title="🎯 Priority Channels (May Respawn)"
        :channels="priorityChannels"
        type="priority"
      />
      <RecommendedSection
        title="❌ Avoid Channels (Respawning)"
        :channels="avoidChannels"
        type="avoid"
      />
    </div>
  </div>
</template>

<script setup>
import { storeToRefs } from 'pinia'
import { useBossStore } from '@/stores/bossStore.js'
import RecommendedSection from './RecommendedSection.vue'

const bossStore = useBossStore()
const { priorityChannels, avoidChannels } = storeToRefs(bossStore)
</script>