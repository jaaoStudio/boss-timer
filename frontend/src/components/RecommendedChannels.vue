<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 mb-6">
    <h2 class="text-xl font-semibold text-gray-900 dark:text-white mb-4">{{ t('recommendedChannels.title') }}</h2>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
      <RecommendedSection
        :title="t('recommendedChannels.priorityTitle')"
        :channels="priorityChannels"
        type="priority"
      />
      <RecommendedSection
        :title="t('recommendedChannels.avoidTitle')"
        :channels="avoidChannels"
        type="avoid"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useBossStore } from '@/stores/bossStore'
import RecommendedSection from './RecommendedSection.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const bossStore = useBossStore()
const { priorityChannels, avoidChannels } = storeToRefs(bossStore)
</script>