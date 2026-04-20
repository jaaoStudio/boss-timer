<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
    <div class="flex items-center justify-between mb-4 flex-wrap gap-1.5">
      <h2 class="text-xl font-semibold text-gray-900 dark:text-white">{{ t('channelOverview.title') }}</h2>
      <el-segmented
        :model-value="viewMode"
        :options="viewOptions"
        @change="setViewMode"
        size="small"
        style="--el-segmented-item-selected-color: #6366f1; --el-segmented-item-selected-bg-color: #eef2ff;"
      >
        <template #default="{ item }">
          <div class="flex items-center gap-1">
            <component :is="item.icon" class="w-3.5 h-3.5 shrink-0" />
            {{ item.label }}
          </div>
        </template>
      </el-segmented>
    </div>
    <ChannelTimeline v-if="viewMode === 'timeline'" />
    <ChannelOverview v-else />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Squares2X2Icon, ChartBarSquareIcon } from '@heroicons/vue/24/outline'
import { useChannelViewPreference } from '@/composables/useChannelViewPreference'
import ChannelOverview from './ChannelOverview.vue'
import ChannelTimeline from './ChannelTimeline.vue'

const { t } = useI18n()
const { viewMode, setViewMode } = useChannelViewPreference()

const viewOptions = computed(() => [
  { value: 'overview', label: t('settings.channelViewOverview'), icon: Squares2X2Icon },
  { value: 'timeline', label: t('settings.channelViewTimeline'), icon: ChartBarSquareIcon },
])
</script>