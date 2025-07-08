<script setup>
import { RouterView } from "vue-router";
import AppFooter from "@/components/AppFooter.vue";


</script>

<template>
  <div class="flex flex-col min-h-screen">
    <RouterView />
    <AppFooter/>
  </div>
</template>

<style scoped>
/* 不再需要自訂 app-footer 或 attribution 样式 */
</style>
