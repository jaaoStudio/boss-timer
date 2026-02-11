<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
</script>

<template>
  <footer class="w-full p-4 text-gray-600 dark:text-gray-300 text-center text-xs ">
    <div class="space-y-2">
      <div class="flex justify-center space-x-4">
        <router-link :to="{ name: 'Credits' }" class="text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white underline cursor-pointer">{{ t('appFooter.credits') }}</router-link>
        <router-link :to="{ name: 'Legal' }" class="text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white underline cursor-pointer">{{ t('appFooter.legal') }}</router-link>
        <router-link :to="{ name: 'Privacy' }" class="text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white underline cursor-pointer">{{ t('appFooter.privacy') }}</router-link>
        <a href="mailto:boss-timer@jaao.tw" class="text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white underline cursor-pointer">{{ t('appFooter.contactUs') }}</a>
      </div>
      <p>{{ t('appFooter.copyright') }}</p>
    </div>
  </footer>
</template>