<script setup>
import { onMounted, watch } from 'vue';
import { RouterView, useRoute, useRouter } from "vue-router";
import AppFooter from "@/components/AppFooter.vue";
import MaintenanceBanner from "@/components/ui/MaintenanceBanner.vue"; // 引入元件
import { useUserStore } from '@/stores/userStore';
import { useAppInfoStore } from '@/stores/appInfo'; // 引入 store
import { useChannelViewPreference } from '@/composables/useChannelViewPreference';
import { useFavoriteBosses } from '@/composables/useFavoriteBosses';
import { useLayoutConfig } from '@/composables/useLayoutConfig';
import { canAccess } from '@/router';

const userStore = useUserStore();
const route = useRoute();
const router = useRouter();
const appInfoStore = useAppInfoStore(); // 實例化 store
const { syncFromUser: syncChannelView } = useChannelViewPreference();
const { syncFromUser: syncFavoriteBosses } = useFavoriteBosses();
const { syncFromUser: syncLayout } = useLayoutConfig();

// 換成另一個登入者時（開頁、登入、換人）把帳號偏好同步到本地；同一個人的查詢結果不覆蓋（跨裝置同步，ADR-0009）
watch(() => userStore.preferencesVersion, () => {
  syncChannelView();
  syncFavoriteBosses();
  syncLayout();
});

// 登入狀態改變後（登入失效、其他分頁登出、切回分頁時的查詢）不能再停在需要登入的頁面時回首頁，不論原因（ADR-0009）。
// 使用中途遇到 401 而發現登入失效的分頁，interceptor 另外會提示並回首頁
watch(() => canAccess(route), (allowed) => {
  if (!allowed) router.push({ name: 'RoomSelection' });
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
