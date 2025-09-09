<template>
  <div class="max-w-4xl mx-auto p-4 sm:p-6 md:p-8">
    <h1 class="text-4xl font-bold text-white mb-6 border-b border-gray-700 pb-4">
      {{ t('privacy.title') }}
    </h1>
    <h2 class="text-2xl font-semibold text-teal-400 mb-4">{{ t('privacy.title') }}</h2>
    <div class="text-gray-400 space-y-4">
      <p>{{ t('privacy.introduction') }}</p>
      <h3 class="text-xl font-semibold text-teal-500 pt-2">{{ t('privacy.section1Title') }}</h3>
      <p>{{ t('privacy.section1Content') }}</p>
      <h3 class="text-xl font-semibold text-teal-500 pt-2">{{ t('privacy.section2Title') }}</h3>
      <p>{{ t('privacy.section2Content1') }}</p>
      <ul class="list-disc list-inside pl-4">
        <li><strong>{{ t('privacy.section2ListItem1') }}</strong></li>
        <li><strong>{{ t('privacy.section2ListItem2') }}</strong></li>
      </ul>
      <p>{{ t('privacy.section2Content2') }}</p>
      <h3 class="text-xl font-semibold text-teal-500 pt-2">{{ t('privacy.section3Title') }}</h3>
      <p>{{ t('privacy.section3Content') }}</p>
      <h3 class="text-xl font-semibold text-teal-500 pt-2">{{ t('privacy.section4Title') }}</h3>
      <p>{{ t('privacy.section4Content') }}</p>
      <h3 class="text-xl font-semibold text-teal-500 pt-2">{{ t('privacy.section5Title') }}</h3>
      <p>{{ t('privacy.section5Content') }}</p>
      <h3 class="text-xl font-semibold text-teal-500 pt-2">{{ t('privacy.section6Title') }}</h3>
      <p>{{ t('privacy.section6Content') }}</p>
      <h3 class="text-xl font-semibold text-teal-500 pt-2">{{ t('privacy.section7Title') }}</h3>
      <p>{{ t('privacy.section7Content') }}</p>
      <h3 class="text-xl font-semibold text-teal-500 pt-2">{{ t('privacy.section8Title') }}</h3>
      <p>{{ t('privacy.section8Content') }}<a href="mailto:boss-timer@jaao.tw" class="text-blue-400 hover:underline">boss-timer@jaao.tw</a>.</p>
    </div>

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
