<template>
  <div v-if="isMaintenanceActive" class="maintenance-banner">
    <p class="marquee-content">
      <strong>{{ maintenanceInfo.title }}:</strong> {{ maintenanceInfo.message }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import { useAppInfoStore } from '@/stores/appInfo';

const appInfoStore = useAppInfoStore();

const isMaintenanceActive = computed(() => appInfoStore.isMaintenanceActive);
const maintenanceInfo = computed(() => appInfoStore.maintenanceInfo);
</script>

<style scoped>
.maintenance-banner {
  background-color: #111827; /* 黑底 */
  color: #fcd34d; /* 黃字 */
  padding: 0.5rem 0; /* 最小化垂直空間 */
  position: fixed;
  top: 0;
  left: 0;
  z-index: 1050;
  width: 100%;
  overflow: hidden; /* 隱藏超出範圍的內容，跑馬燈效果的關鍵 */
  font-size: 0.9rem;
}

.marquee-content {
  display: inline-block;
  white-space: nowrap; /* 確保內容在同一行 */
  padding-left: 100%; /* 從右側螢幕外開始 */
  animation: marquee 25s linear infinite; /* 應用動畫 */
}

.marquee-content strong {
  margin-right: 1.5em; /* 標題和訊息間的距離 */
}

@keyframes marquee {
  0% {
    transform: translateX(0);
  }
  100% {
    transform: translateX(-100%); /* 移動到左側螢幕外 */
  }
}
</style>
