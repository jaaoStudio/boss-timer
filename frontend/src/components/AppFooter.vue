<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <footer class="w-full mt-auto border-t border-gray-200/70 dark:border-gray-800 px-4 py-6 text-gray-600 dark:text-gray-300 text-center text-xs">
    <div class="space-y-3">
      <div class="flex flex-wrap justify-center gap-x-5 gap-y-1.5">
        <router-link :to="{ name: 'Guide' }" class="text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:underline underline-offset-4 transition-colors cursor-pointer">{{ t('appFooter.guide') }}</router-link>
        <router-link :to="{ name: 'Credits' }" class="text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:underline underline-offset-4 transition-colors cursor-pointer">{{ t('appFooter.credits') }}</router-link>
        <router-link :to="{ name: 'Legal' }" class="text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:underline underline-offset-4 transition-colors cursor-pointer">{{ t('appFooter.legal') }}</router-link>
        <router-link :to="{ name: 'Privacy' }" class="text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:underline underline-offset-4 transition-colors cursor-pointer">{{ t('appFooter.privacy') }}</router-link>
        <a href="mailto:boss-timer@jaao.tw" class="text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white hover:underline underline-offset-4 transition-colors cursor-pointer">{{ t('appFooter.contactUs') }}</a>
      </div>
      <p class="text-gray-400 dark:text-gray-500">{{ t('appFooter.copyright') }}</p>
    </div>
  </footer>
</template>