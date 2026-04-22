<template>
  <div v-if="isMaintenanceActive" class="fixed top-0 left-0 z-[1050] w-full overflow-hidden bg-gray-900 text-yellow-300 py-2 text-sm">
    <p class="marquee-content">
      <strong>{{ maintenanceInfo.title }}:</strong> {{ maintenanceInfo.message }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useAppInfoStore } from '@/stores/appInfo'

const appInfoStore = useAppInfoStore()

const isMaintenanceActive = computed(() => appInfoStore.isMaintenanceActive)
const maintenanceInfo = computed(() => appInfoStore.maintenanceInfo)
</script>

<style scoped>
.marquee-content {
  display: inline-block;
  white-space: nowrap;
  padding-left: 100%;
  animation: marquee 25s linear infinite;
}

.marquee-content strong {
  margin-right: 1.5em;
}

@keyframes marquee {
  0% {
    transform: translateX(0);
  }
  100% {
    transform: translateX(-100%);
  }
}
</style>
