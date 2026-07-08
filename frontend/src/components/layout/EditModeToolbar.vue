<template>
  <!-- 編輯模式工具列 -->
  <div
    v-if="isEditMode"
    class="my-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 px-4 py-2.5"
  >
    <div class="flex items-center gap-2 text-amber-700 dark:text-amber-300 min-w-0">
      <ViewColumnsIcon class="w-4 h-4 shrink-0" />
      <span class="text-sm">{{ t('layout.editModeHint') }}</span>
    </div>
    <div class="flex items-center gap-2 shrink-0">
      <el-button size="small" @click="emit('reset')">{{ t('layout.reset') }}</el-button>
      <el-button
        size="small"
        type="primary"
        :style="{
          '--el-color-primary': '#b45309',
          '--el-color-primary-light-3': '#d97706',
          '--el-color-primary-dark-2': '#92400e',
        }"
        @click="emit('exit')"
      >{{ t('layout.done') }}</el-button>
    </div>
  </div>

  <!-- 自訂版面按鈕（平時低調） -->
  <div v-else class="flex justify-end mb-1">
    <div
      @click="emit('enter')"
      class="flex items-center gap-1.5 text-xs text-gray-400 dark:text-gray-600 hover:text-amber-500 dark:hover:text-amber-400 transition-colors cursor-pointer py-1 px-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50"
    >
      <ViewColumnsIcon class="w-3.5 h-3.5" />
      {{ t('layout.customize') }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { ViewColumnsIcon } from '@heroicons/vue/24/outline'

defineProps<{
  isEditMode: boolean
}>()

const emit = defineEmits<{
  enter: []
  exit: []
  reset: []
}>()

const { t } = useI18n()
</script>
