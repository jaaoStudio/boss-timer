<template>
  <button
    type="button"
    :class="buttonClass"
    :disabled="disabled"
    @click="$emit('click')"
    class="flex-1 flex flex-col items-center justify-center gap-1 @[360px]:gap-1.5 py-2 @[360px]:py-3 px-1 @[360px]:px-2 rounded-lg transition-all active:scale-[0.97] cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed disabled:active:scale-100 select-none"
  >
    <component :is="buttonConfig.icon" class="w-5 h-5 shrink-0" fill="currentColor"/>
    <span v-if="!compact" class="hidden @[360px]:inline-block text-xs font-medium leading-tight text-center whitespace-nowrap">
      {{ buttonConfig.title }}
    </span>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import SkullIcon from "@icons/SkullIcon.vue"
import SearchIcon from "@icons/SearchIcon.vue"
import QuestionIcon from "@icons/questionIcon.vue"
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

const props = defineProps<{
  type: 'alive' | 'killed' | 'not_found'
  disabled?: boolean
  compact?: boolean
}>()

defineEmits<{
  (e: 'click'): void
}>()

const buttonConfigs = computed(() => ({
  alive: {
    title: t('bossStatusButton.alive'),
    icon: SearchIcon,
    baseClass: 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200 active:bg-emerald-300 dark:bg-emerald-900/30 dark:text-emerald-400 dark:hover:bg-emerald-900/50'
  },
  killed: {
    title: t('bossStatusButton.killed'),
    icon: SkullIcon,
    baseClass: 'bg-red-100 text-red-700 hover:bg-red-200 active:bg-red-300 dark:bg-red-900/30 dark:text-red-400 dark:hover:bg-red-900/50'
  },
  not_found: {
    title: t('bossStatusButton.notFound'),
    icon: QuestionIcon,
    baseClass: 'bg-gray-100 text-gray-600 hover:bg-gray-200 active:bg-gray-300 dark:bg-gray-700 dark:text-gray-300 dark:hover:bg-gray-600'
  }
}))

const buttonConfig = computed(() => buttonConfigs.value[props.type])
const buttonClass = computed(() => buttonConfig.value.baseClass)
</script>