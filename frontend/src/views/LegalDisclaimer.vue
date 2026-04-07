<template>
  <div class="max-w-4xl mx-auto p-4 sm:p-6 md:p-8 text-gray-800 dark:text-gray-200">
    <h1 class="text-4xl font-bold text-gray-900 dark:text-white mb-6 border-b border-gray-300 dark:border-gray-700 pb-4">
      {{ t('legal.title') }}
    </h1>
    <p class="text-gray-600 dark:text-gray-400 whitespace-pre-line leading-relaxed">
      {{ t('legal.content') }}
    </p>
    <div class="mt-12 text-center text-gray-500 dark:text-gray-500">
      <router-link to="/" class="hover:text-gray-700 dark:hover:text-gray-300 underline">{{ t('credits.backToHome') }}</router-link>
    </div>
  </div>
</template>
<script setup>
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

onMounted(() => {
  window.scrollTo({
    top: 0,
    behavior: 'smooth' // 平滑滾動
  })
})

</script>
