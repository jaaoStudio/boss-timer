<template>
  <div class="flex min-h-dvh w-full justify-center bg-gray-50 dark:bg-gray-900 px-4 py-12">
    <div class="w-full max-w-xl">
      <h1 class="text-2xl font-bold tracking-tight text-gray-900 dark:text-white mb-6 text-center">{{ t('maintenanceAdmin.title') }}</h1>

      <form @submit.prevent="updateMaintenanceConfig"
            class="space-y-5 bg-white dark:bg-gray-800/90 rounded-2xl border border-gray-200 dark:border-gray-700/70 shadow-[var(--shadow-card)] p-6">

        <label class="flex items-center justify-between gap-4 cursor-pointer">
          <span class="text-sm font-medium text-gray-700 dark:text-gray-300">{{ t('maintenanceAdmin.isMaintenance') }}</span>
          <input type="checkbox" v-model="config.is_maintenance"
                 class="h-5 w-5 rounded accent-[var(--accent)] cursor-pointer" />
        </label>

        <label class="flex items-center justify-between gap-4 cursor-pointer">
          <span class="text-sm font-medium text-gray-700 dark:text-gray-300">{{ t('maintenanceAdmin.isReady') }}</span>
          <input type="checkbox" v-model="config.is_ready_for_maintenance"
                 class="h-5 w-5 rounded accent-[var(--accent)] cursor-pointer" />
        </label>

        <div>
          <label for="title" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">{{ t('maintenanceAdmin.fieldTitle') }}</label>
          <input type="text" id="title" v-model="config.title" required
                 class="block w-full px-3 py-2.5 border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)] focus:border-transparent transition text-sm" />
        </div>

        <div>
          <label for="message" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">{{ t('maintenanceAdmin.fieldMessage') }}</label>
          <textarea id="message" v-model="config.message" rows="4" required
                    class="block w-full px-3 py-2.5 border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-white rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)] focus:border-transparent transition text-sm resize-y"></textarea>
        </div>

        <button type="submit"
                class="w-full px-4 py-2.5 text-sm font-semibold text-white bg-gray-900 dark:bg-white dark:text-gray-900 rounded-lg hover:bg-gray-800 dark:hover:bg-gray-100 active:scale-[0.98] transition cursor-pointer">
          {{ t('maintenanceAdmin.submit') }}
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import apiService from '@/services/apiService';
import { showMessage } from '@/composables/useElementPlus';
import { useAppInfoStore } from '@/stores/appInfo';

const { t } = useI18n();
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
    showMessage.success(t('maintenanceAdmin.updateSuccess'));
    appInfoStore.maintenanceInfo = response.data;
  } catch (error: unknown) {
    console.error('更新維護配置失敗:', error);
    const e = error as { response?: { data?: { detail?: string } }; message?: string }
    showMessage.error(t('maintenanceAdmin.updateFailed') + (e.response?.data?.detail ?? e.message ?? String(error)));
  }
};
</script>
