<template>
  <div class="max-w-4xl mx-auto p-4 sm:p-6 md:p-8">
      <h1 class="text-4xl font-bold text-white mb-6 border-b border-gray-700 pb-4">
        {{ t('legal.title') }}
      </h1>
    <h2 class="text-2xl font-semibold text-teal-400 mb-4">{{ t('legal.title') }}</h2>
    <p class="text-gray-400 whitespace-pre-line">
      {{ t('legal.content') }}
    </p>
          <div class="mt-12 text-center text-gray-500">
        <router-link to="/" class="hover:text-gray-300 underline">{{ t('credits.backToHome') }}</router-link>
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
