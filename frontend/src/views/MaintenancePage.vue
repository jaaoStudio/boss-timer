<template>
  <div class="flex flex-col items-center justify-center flex-1">
    <img src="@public/leaf64px.png" alt="Logo" class="h-8 w-8 mr-3"/>
    <div class="status-page-content">
      <h1 class="status-title">系統維護中</h1>
      <p class="status-message">我們正在進行必要的系統更新以提供更好的服務，請稍後再回來。感謝您的耐心等待。</p>
      <button @click="goHome" class="status-button">返回首頁</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';

const router = useRouter();

const goHome = () => {
  router.push('/');
};
</script>

<style scoped>
.status-page-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  width: 100%;
  background-color: #1a202c; /* bg-gray-900 */
  color: #e2e8f0; /* text-gray-200 */
}
.status-page-content {
  text-align: center;
  padding: 2rem;
}
.status-title {
  font-size: 2.5rem;
  font-weight: bold;
  margin-bottom: 1rem;
}
.status-message {
  font-size: 1.2rem;
  margin-bottom: 2rem;
}
.status-button {
  background-color: #4a5568; /* bg-gray-700 */
  color: white;
  padding: 0.75rem 1.5rem;
  border-radius: 0.375rem;
  cursor: pointer;
  transition: background-color 0.3s;
}
.status-button:hover {
  background-color: #2d3748; /* bg-gray-800 */
}
</style>
