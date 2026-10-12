<script setup>
import { onMounted, watch } from 'vue';
import { RouterView } from "vue-router";
import AppFooter from "@/components/AppFooter.vue";
import MaintenanceBanner from "@/components/ui/MaintenanceBanner.vue"; // 引入元件
import { useUserStore } from '@/stores/userStore';
import { useAppInfoStore } from '@/stores/appInfo'; // 引入 store
import { useChannelViewPreference } from '@/composables/useChannelViewPreference';
import { useFavoriteBosses } from '@/composables/useFavoriteBosses';
import { useLayoutConfig } from '@/composables/useLayoutConfig';

const userStore = useUserStore();
const appInfoStore = useAppInfoStore(); // 實例化 store
const { syncFromUser: syncChannelView } = useChannelViewPreference();
const { syncFromUser: syncFavoriteBosses } = useFavoriteBosses();
const { syncFromUser: syncLayout } = useLayoutConfig();

// 登入後將後端偏好設定同步到本地（含頁面載入時的 cookie 自動登入）
watch(() => userStore.isLoggedIn, (loggedIn) => {
  if (loggedIn) {
    syncChannelView();
    syncFavoriteBosses();
    syncLayout();
  }
});

// When the component is mounted, try to fetch the user data
onMounted(async () => {
  // 初始化認證狀態；完成後（finally）才建立 WebSocket 連線。
  // WebSocket 的身分在握手時以 cookie 決定、整條連線固定，必須等 /auth/session 發好匿名 cookie 再連，
  // 否則第一次來的訪客整條連線都沒有身分
  await userStore.initializeAuth();
  // 檢查維護狀態 (首次載入時)
  await appInfoStore.checkMaintenanceStatus();
});
</script>

<template>
  <MaintenanceBanner /> <!-- 在頂部顯示橫幅 -->
  <div class="flex flex-col min-h-screen items-center bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-200">
    <RouterView />
    <AppFooter/>
  </div>

</template>

<style scoped>
/* Scoped styles if needed */
</style>
