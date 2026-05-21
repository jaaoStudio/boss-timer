<template>
  <div class="maintenance-admin-container">
    <h1>維護狀態管理</h1>
    <form @submit.prevent="updateMaintenanceConfig" class="maintenance-form">
      <div class="form-group">
        <label for="isMaintenance">正在維護:</label>
        <input type="checkbox" id="isMaintenance" v-model="config.is_maintenance" />
      </div>

      <div class="form-group">
        <label for="isReadyForMaintenance">即將維護:</label>
        <input type="checkbox" id="isReadyForMaintenance" v-model="config.is_ready_for_maintenance" />
      </div>

      <div class="form-group">
        <label for="title">標題:</label>
        <input type="text" id="title" v-model="config.title" required />
      </div>

      <div class="form-group">
        <label for="message">訊息:</label>
        <textarea id="message" v-model="config.message" rows="4" required></textarea>
      </div>

      <button type="submit" class="submit-button">更新配置</button>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import apiService from '@/services/apiService';
import { showMessage } from '@/composables/useElementPlus';
import { useAppInfoStore } from '@/stores/appInfo';

const appInfoStore = useAppInfoStore();

const config = ref({
  is_maintenance: false,
  is_ready_for_maintenance: false,
  title: '',
  message: '',
});

onMounted(async () => {
  // 載入當前配置
  await apiService.getMaintenanceStatus();
  config.value = { ...appInfoStore.maintenanceInfo };
});

const updateMaintenanceConfig = async () => {
  try {
    const response = await apiService.updateMaintenanceConfig(config.value);
    if (response.status === 200) {
      showMessage.success('維護配置更新成功！');
      // 更新 store 中的狀態，確保前端橫幅即時更新
      appInfoStore.maintenanceInfo = response.data;
    } else {
      showMessage.error('更新失敗: ' + response.data.detail);
    }
  } catch (error: unknown) {
    console.error('更新維護配置失敗:', error);
    const e = error as { response?: { data?: { detail?: string } }; message?: string }
    showMessage.error('更新維護配置失敗: ' + (e.response?.data?.detail ?? e.message ?? String(error)));
  }
};
</script>

<style scoped>
.maintenance-admin-container {
  max-width: 600px;
  margin: 2rem auto;
  padding: 2rem;
  background-color: #2d3748; /* bg-gray-800 */
  border-radius: 0.5rem;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  color: #e2e8f0; /* text-gray-200 */
}

h1 {
  text-align: center;
  color: #fcd34d; /* 黃色 */
  margin-bottom: 1.5rem;
}

.maintenance-form .form-group {
  margin-bottom: 1rem;
}

.maintenance-form label {
  display: block;
  margin-bottom: 0.5rem;
  font-weight: bold;
}

.maintenance-form input[type="text"],
.maintenance-form textarea {
  width: calc(100% - 1rem);
  padding: 0.5rem;
  border: 1px solid #4a5568; /* gray-700 */
  border-radius: 0.25rem;
  background-color: #1a202c; /* gray-900 */
  color: #e2e8f0;
}

.maintenance-form input[type="checkbox"] {
  margin-left: 0.5rem;
  transform: scale(1.2);
}

.submit-button {
  display: block;
  width: 100%;
  padding: 0.75rem;
  background-color: #4299e1; /* blue-500 */
  color: white;
  border: none;
  border-radius: 0.25rem;
  cursor: pointer;
  font-size: 1rem;
  transition: background-color 0.3s ease;
}

.submit-button:hover {
  background-color: #3182ce; /* blue-600 */
}
</style>
