<script setup lang="ts">
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router'; // Import useRouter

const { t } = useI18n();
const router = useRouter(); // Initialize useRouter

const navigateTo = (name: string) => {
  router.push({ name });
};
</script>

<template>
    <footer class="w-full p-4 bg-white dark:bg-gray-900 text-gray-600 dark:text-gray-300 text-center text-xs ">
      <div class="space-y-2">
        <div class="flex justify-center space-x-4">
          <a @click="navigateTo('Credits')" class="text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white underline cursor-pointer">{{ t('appFooter.credits') }}</a>
          <a @click="navigateTo('Legal')" class="text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white underline cursor-pointer">{{ t('appFooter.legal') }}</a>
          <a @click="navigateTo('Privacy')" class="text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white underline cursor-pointer">{{ t('appFooter.privacy') }}</a>
          <a href="mailto:boss-timer@jaao.tw" class="text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white underline cursor-pointer">{{ t('appFooter.contactUs') }}</a>
        </div>
        <p>{{ t('appFooter.copyright') }}</p>
      </div>
    </footer>
</template>

<style scoped>

</style>