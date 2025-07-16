<script setup>
import { onMounted } from 'vue';
import { RouterView } from "vue-router";
import AppFooter from "@/components/AppFooter.vue";
import { useUserStore } from '@/stores/userStore';

const userStore = useUserStore();

// When the component is mounted, try to fetch the user data
onMounted(async () => {
  // 初始化認證狀態
  await userStore.initializeAuth()
});
</script>

<template>
  <div class="flex flex-col min-h-screen bg-gray-900 text-gray-200">
    <RouterView />
    <AppFooter/>
  </div>
</template>

<style scoped>
/* Scoped styles if needed */
</style>
