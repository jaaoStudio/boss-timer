<template>
  <div class="status-page-container">
    <img src="@public/leaf64px.png" alt="Logo" class="h-8 w-8 mr-3"/>
    <div class="status-page-content">
      <h1 class="status-title">伺服器發生錯誤 (500)</h1>
      <p class="status-message">很抱歉，我們的伺服器遇到了一些問題。我們已經收到通知並正在處理中。</p>
      <div class="button-group">
        <button @click="goHomeAndReload" class="status-button">返回首頁</button>
        <button @click="goHomeAndReload" class="status-button secondary">重試</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';

const router = useRouter();

const goHomeAndReload = () => {
  router.push('/').then(() => {
    window.location.reload();
  });
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
.button-group {
    display: flex;
    justify-content: center;
    gap: 1rem;
}
.status-button {
  background-color: #4a5568; /* bg-gray-700 */
  color: white;
  padding: 0.75rem 1.5rem;
  border: 1px solid transparent;
  border-radius: 0.375rem;
  cursor: pointer;
  transition: background-color 0.3s;
}
.status-button:hover {
  background-color: #2d3748; /* bg-gray-800 */
}
.status-button.secondary {
    background-color: transparent;
    border-color: #4a5568; /* border-gray-700 */
}
.status-button.secondary:hover {
    background-color: #2d3748; /* bg-gray-800 */
}
</style>
