<template>
  <div
    v-show="isEditMode || visible"
    :class="[
      'col-span-1 min-w-0 @container',
      colSpanClass,
    ]"
  >
    <!-- 編輯模式頂部工具列（只有順序與寬度，無收合） -->
    <div
      v-if="isEditMode"
      class="flex items-center justify-between bg-amber-50 dark:bg-amber-900/30 border border-b-0 border-amber-200 dark:border-amber-700 rounded-t-xl px-3 py-1.5 select-none"
    >
      <!-- 拖曳把手 + 名稱 + 隱藏標記 -->
      <div class="drag-handle flex items-center gap-1.5 cursor-grab active:cursor-grabbing">
        <Bars3Icon class="w-4 h-4 text-amber-400 shrink-0" />
        <span class="text-xs font-semibold text-amber-700 dark:text-amber-300">
          {{ $t(`layout.items.${item.id}`) }}
        </span>
        <span
          v-if="!visible"
          class="text-[10px] bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400 rounded px-1 py-0.5 leading-none"
        >
          {{ $t('layout.hidden') }}
        </span>
      </div>

      <!-- 順序 + 寬度操作 -->
      <div class="flex items-center gap-0.5">
        <!-- 上移 -->
        <div
          :class="[
            'p-1 rounded transition-colors',
            index === 0
              ? 'opacity-25 cursor-not-allowed'
              : 'cursor-pointer hover:bg-amber-100 dark:hover:bg-amber-800',
          ]"
          :title="$t('layout.moveUp')"
          @click.stop="index > 0 && $emit('moveUp')"
        >
          <ChevronUpIcon class="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
        </div>
        <!-- 下移 -->
        <div
          :class="[
            'p-1 rounded transition-colors',
            index === totalItems - 1
              ? 'opacity-25 cursor-not-allowed'
              : 'cursor-pointer hover:bg-amber-100 dark:hover:bg-amber-800',
          ]"
          :title="$t('layout.moveDown')"
          @click.stop="index < totalItems - 1 && $emit('moveDown')"
        >
          <ChevronDownIcon class="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
        </div>

        <!-- 寬度控制（桌電限定）：[−] 2/4 [+] -->
        <div class="hidden md:flex items-center gap-0.5 ml-1 border-l border-amber-200 dark:border-amber-600 pl-1.5">
          <div
            :class="[
              'p-1 rounded transition-colors',
              item.colSpan <= MIN_COL_SPAN[item.id]
                ? 'opacity-25 cursor-not-allowed'
                : 'cursor-pointer hover:bg-amber-100 dark:hover:bg-amber-800',
            ]"
            :title="$t('layout.narrower')"
            @click.stop="item.colSpan > MIN_COL_SPAN[item.id] && $emit('decreaseColSpan')"
          >
            <MinusIcon class="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
          </div>
          <span class="text-[11px] font-mono font-semibold text-amber-600 dark:text-amber-300 min-w-[2rem] text-center select-none">
            {{ item.colSpan }}/4
          </span>
          <div
            :class="[
              'p-1 rounded transition-colors',
              item.colSpan >= 4
                ? 'opacity-25 cursor-not-allowed'
                : 'cursor-pointer hover:bg-amber-100 dark:hover:bg-amber-800',
            ]"
            :title="$t('layout.wider')"
            @click.stop="item.colSpan < 4 && $emit('increaseColSpan')"
          >
            <PlusIcon class="w-3.5 h-3.5 text-amber-600 dark:text-amber-400" />
          </div>
        </div>
      </div>
    </div>

    <!-- 收合狀態下的薄 header bar（非編輯模式） -->
    <div
      v-if="!isEditMode && item.collapsed"
      class="flex items-center justify-between bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg px-4 py-2 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-750 transition-colors"
      @click="$emit('toggleCollapsed')"
    >
      <span class="text-sm font-medium text-gray-500 dark:text-gray-400">
        {{ $t(`layout.items.${item.id}`) }}
      </span>
      <ChevronDownIcon class="w-4 h-4 text-gray-400 dark:text-gray-500" />
    </div>

    <!-- 元件容器 -->
    <div
      v-show="isEditMode || !item.collapsed"
      :class="[
        isEditMode
          ? 'border border-t-0 border-amber-200 dark:border-amber-700 rounded-b-xl overflow-hidden pointer-events-none'
          : 'relative',
      ]"
    >
      <!-- 收合按鈕浮在右上角（非編輯模式、展開狀態） -->
      <div
        v-if="!isEditMode"
        class="absolute top-2 right-2 z-10 p-1 rounded-md cursor-pointer opacity-0 hover:opacity-100 transition-opacity bg-gray-100/80 dark:bg-gray-700/80 backdrop-blur-sm"
        :title="$t('layout.collapse')"
        @click.stop="$emit('toggleCollapsed')"
      >
        <ChevronUpIcon class="w-3.5 h-3.5 text-gray-400 dark:text-gray-500" />
      </div>
      <slot />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { MIN_COL_SPAN, type LayoutItem } from '@/composables/useLayoutConfig'
import {
  Bars3Icon,
  ChevronUpIcon,
  ChevronDownIcon,
  MinusIcon,
  PlusIcon,
} from '@heroicons/vue/24/outline'

const props = defineProps<{
  item: LayoutItem
  index: number
  totalItems: number
  isEditMode: boolean
  visible: boolean
}>()

const colSpanClass = computed(() => {
  const map: Record<number, string> = {
    1: 'md:col-span-1',
    2: 'md:col-span-2',
    3: 'md:col-span-3',
    4: 'md:col-span-4',
  }
  return map[props.item.colSpan] ?? 'md:col-span-4'
})

defineEmits<{
  moveUp: []
  moveDown: []
  increaseColSpan: []
  decreaseColSpan: []
  toggleCollapsed: []
}>()
</script>