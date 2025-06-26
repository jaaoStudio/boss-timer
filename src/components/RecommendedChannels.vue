<template>
  <div class="bg-white rounded-lg shadow-md p-6 mb-6">
    <h2 class="text-xl font-semibold text-gray-800 mb-4">Recommended Channels</h2>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <RecommendedSection
        title="🎯 Priority Channels (May Respawn)"
        :channels="bossStore.priorityChannels"
        type="priority"
      />
      <RecommendedSection
        title="❌ Avoid Channels (Respawning)"
        :channels="bossStore.avoidChannels"
        type="avoid"
      />
    </div>
  </div>
</template>

<script setup>
import { useBossStore } from '@/stores/bossStore'
import RecommendedSection from './RecommendedSection.vue'

const bossStore = useBossStore()
</script>