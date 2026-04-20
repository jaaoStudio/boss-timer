<template>
  <div
    v-show="isEditMode || visible"
    :class="[
      'col-span-1 min-w-0',
      item.colSpan === 2 ? 'md:col-span-2' : 'md:col-span-1',
    ]"
  >
    <!-- 編輯模式頂部工具列 -->
    <div
      v-if="isEditMode"
      class="flex items-center justify-between bg-indigo-50 dark:bg-indigo-900/30 border border-b-0 border-indigo-200 dark:border-indigo-700 rounded-t-xl px-3 py-1.5 select-none"
    >
      <!-- 拖曳把手 + 名稱 + 隱藏標記 -->
      <div class="drag-handle flex items-center gap-1.5 cursor-grab active:cursor-grabbing">
        <Bars3Icon class="w-4 h-4 text-indigo-400 shrink-0" />
        <span class="text-xs font-semibold text-indigo-700 dark:text-indigo-300">
          {{ $t(`layout.items.${item.id}`) }}
        </span>
        <span
          v-if="!visible"
          class="text-[10px] bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400 rounded px-1 py-0.5 leading-none"
        >
          {{ $t('layout.hidden') }}
        </span>
      </div>

      <!-- 操作按鈕 -->
      <div class="flex items-center gap-0.5">
        <!-- 上移 -->
        <div
          :class="[
            'p-1 rounded transition-colors',
            index === 0
              ? 'opacity-25 cursor-not-allowed'
              : 'cursor-pointer hover:bg-indigo-100 dark:hover:bg-indigo-800',
          ]"
          :title="$t('layout.moveUp')"
          @click.stop="index > 0 && $emit('moveUp')"
        >
          <ChevronUpIcon class="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
        </div>
        <!-- 下移 -->
        <div
          :class="[
            'p-1 rounded transition-colors',
            index === totalItems - 1
              ? 'opacity-25 cursor-not-allowed'
              : 'cursor-pointer hover:bg-indigo-100 dark:hover:bg-indigo-800',
          ]"
          :title="$t('layout.moveDown')"
          @click.stop="index < totalItems - 1 && $emit('moveDown')"
        >
          <ChevronDownIcon class="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
        </div>
        <!-- 寬度切換（桌電限定） -->
        <div
          :title="item.colSpan === 2 ? $t('layout.halfWidth') : $t('layout.fullWidth')"
          class="hidden md:flex p-1 rounded cursor-pointer hover:bg-indigo-100 dark:hover:bg-indigo-800 transition-colors"
          @click.stop="$emit('toggleColSpan')"
        >
          <ArrowsPointingInIcon v-if="item.colSpan === 2" class="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
          <ArrowsPointingOutIcon v-else class="w-3.5 h-3.5 text-indigo-600 dark:text-indigo-400" />
        </div>
      </div>
    </div>

    <!-- 元件容器（編輯模式禁止互動） -->
    <div
      :class="[
        isEditMode
          ? 'border border-t-0 border-indigo-200 dark:border-indigo-700 rounded-b-xl overflow-hidden pointer-events-none'
          : '',
      ]"
    >
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { LayoutItem } from '@/composables/useLayoutConfig'
import {
  Bars3Icon,
  ChevronUpIcon,
  ChevronDownIcon,
  ArrowsPointingInIcon,
  ArrowsPointingOutIcon,
} from '@heroicons/vue/24/outline'

defineProps<{
  item: LayoutItem
  index: number
  totalItems: number
  isEditMode: boolean
  visible: boolean
}>()

defineEmits<{
  moveUp: []
  moveDown: []
  toggleColSpan: []
}>()
</script>