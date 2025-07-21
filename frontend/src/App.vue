<script setup>
import { onMounted } from 'vue';
import { RouterView } from "vue-router";
import AppFooter from "@/components/AppFooter.vue";
import MaintenanceBanner from "@/components/MaintenanceBanner.vue"; // 引入元件
import { useUserStore } from '@/stores/userStore';
import { useAppInfoStore } from '@/stores/appInfo'; // 引入 store

const userStore = useUserStore();
const appInfoStore = useAppInfoStore(); // 實例化 store

// When the component is mounted, try to fetch the user data
onMounted(async () => {
  // 初始化認證狀態
  await userStore.initializeAuth();
  // 檢查維護狀態 (首次載入時)
  await appInfoStore.checkMaintenanceStatus();
});
</script>

<template>
  <MaintenanceBanner /> <!-- 在頂部顯示橫幅 -->
  <div class="flex flex-col min-h-screen items-centerbg-gray-900 text-gray-200">
    <RouterView />
    <AppFooter/>
  </div>

</template>

<style scoped>
/* Scoped styles if needed */
</style>
