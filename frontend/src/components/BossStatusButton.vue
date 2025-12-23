<template>
  <button
    :class="buttonClass"
    :disabled="disabled"
    :title="buttonConfig.title"
    @click="$emit('click')"
    class="flex-1 p-3 rounded transition-colors group relative disabled:bg-gray-300 dark:disabled:bg-gray-600 disabled:cursor-not-allowed hover:!bg-gray-100 dark:hover:!bg-gray-600"
  >
    <component :is="buttonConfig.icon" class="w-5 h-5 mx-auto" fill="currentColor"/>
    <span class="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 text-xs bg-black text-white rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
      {{ buttonConfig.title }}
    </span>
  </button>
</template>

<script setup>
import { computed } from 'vue'
import SkullIcon from "@icons/SkullIcon.vue"
import SearchIcon from "@icons/SearchIcon.vue";
import QuestionIcon from "@icons/questionIcon.vue";
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const props = defineProps({
  type: {
    type: String,
    required: true,
    validator: (value) => ['alive', 'killed', 'not_found'].includes(value)
  },
  disabled: Boolean
})

defineEmits(['click'])

const buttonConfigs = computed(() => ({
  alive: {
    title: t('bossStatusButton.alive'),
    icon: SearchIcon,
    baseClass: 'bg-green-600 hover:bg-green-700'
  },
  killed: {
    title: t('bossStatusButton.killed'),
    icon: SkullIcon,
    baseClass: 'bg-red-600 hover:bg-red-700'
  },
  not_found: {
    title: t('bossStatusButton.notFound'),
    icon: QuestionIcon,
    baseClass: 'bg-gray-400 dark:bg-gray-600 hover:bg-gray-500 dark:hover:bg-gray-700'
  }
}))

const buttonConfig = computed(() => buttonConfigs.value[props.type])

const buttonClass = computed(() => {
  return buttonConfig.value.baseClass
})
</script>