<script setup lang="ts">
import { useI18n } from 'vue-i18n';
const { t } = useI18n();
</script>

<template>
    <footer class="w-full p-4 bg-gray-900 text-gray-300 text-center text-xs ">
      <div class="space-y-2">
        <div class="flex justify-center space-x-4">
          <router-link to="/credits" class="text-gray-400 hover:text-white underline">{{ t('appFooter.credits') }}</router-link>
          <router-link to="/legal" class="text-gray-400 hover:text-white underline">{{ t('appFooter.legal') }}</router-link>
          <router-link to="/privacy" class="text-gray-400 hover:text-white underline">{{ t('appFooter.privacy') }}</router-link>
        </div>
        <p>{{ t('appFooter.copyright') }}</p>
      </div>
    </footer>
</template>

<style scoped>

</style>