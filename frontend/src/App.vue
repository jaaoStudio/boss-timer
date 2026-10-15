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

// 查詢登入狀態成功、伺服器的偏好和上次套用的不同時（登入、換人、其他裝置改過），同步到本地（ADR-0009）
watch(() => userStore.preferencesVersion, () => {
  syncChannelView();
  syncFavoriteBosses();
  syncLayout();
});

onMounted(async () => {
  // 開始查詢登入狀態，第一次判斷完成後才建立 WebSocket 連線。
  // WebSocket 的身分在握手時以 cookie 決定、整條連線固定，必須等 /auth/session 發好匿名 cookie 再連，
  // 否則第一次來的訪客整條連線都沒有身分。登入狀態的查詢失敗不經全域錯誤處理；
  // 伺服器真的掛掉時，接著的維護狀態請求會帶到維護頁或錯誤頁
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
