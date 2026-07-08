<template>
  <div class="flex min-h-dvh w-full flex-col items-center justify-center gap-6 flex-1 bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-100 px-6 text-center">
    <img src="@public/leaf64px.png" alt="Boss Timer logo" class="h-12 w-12 opacity-90" />

    <div class="max-w-md space-y-3">
      <p class="font-mono text-sm tracking-widest text-[var(--accent)]">MAINTENANCE</p>
      <h1 class="text-3xl sm:text-4xl font-bold tracking-tight">{{ t('maintenancePage.title') }}</h1>
      <p class="text-gray-500 dark:text-gray-400 leading-relaxed">
        {{ t('maintenancePage.message') }}
      </p>
    </div>

    <button
      @click="goHome"
      class="px-5 py-2.5 text-sm font-semibold text-white bg-gray-900 dark:bg-white dark:text-gray-900 rounded-lg hover:bg-gray-800 dark:hover:bg-gray-100 active:scale-[0.98] transition cursor-pointer"
    >{{ t('appFooter.backToHome') }}</button>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';

const { t } = useI18n();
const router = useRouter();

const goHome = () => {
  router.push('/');
};
</script>
