<template>
  <div class="bg-white rounded-lg shadow-md p-6 mb-6">
    <h2 class="text-xl font-semibold text-gray-800 mb-4">Channel Overview</h2>
    <div class="grid grid-cols-5 sm:grid-cols-10 md:grid-cols-15 lg:grid-cols-10 gap-2">
      <ChannelCard
        v-for="channel in 30"
        :key="channel"
        :channel-number="channel"
      />
    </div>
  </div>
</template>

<script setup>
import ChannelCard from './ChannelCard.vue'
</script>