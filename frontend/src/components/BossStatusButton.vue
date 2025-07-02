<template>
  <button
    :class="buttonClass"
    :disabled="disabled"
    :title="buttonConfig.title"
    @click="$emit('click')"
    class="flex-1 p-3 rounded transition-colors group relative disabled:bg-gray-600 disabled:cursor-not-allowed"
  >
    <component :is="buttonConfig.icon" class="w-5 h-5 mx-auto" fill="currentColor"/>
    <span class="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-2 py-1 text-xs bg-black text-white rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
      {{ buttonConfig.title }}
    </span>
  </button>
</template>

<script setup>
import { computed } from 'vue'
import { MagnifyingGlassCircleIcon, QuestionMarkCircleIcon } from '@heroicons/vue/24/outline'
import SkullIcon from "/icons/SkullIcon.vue"

const props = defineProps({
  type: {
    type: String,
    required: true,
    validator: (value) => ['alive', 'killed', 'not_found'].includes(value)
  },
  disabled: Boolean
})

defineEmits(['click'])

const buttonConfigs = {
  alive: {
    title: '發現活著的BOSS',
    icon: MagnifyingGlassCircleIcon,
    baseClass: 'bg-green-600 hover:bg-green-700'
  },
  killed: {
    title: '剛擊殺BOSS',
    icon: SkullIcon,
    baseClass: 'bg-red-600 hover:bg-red-700'
  },
  not_found: {
    title: '沒有發現BOSS',
    icon: QuestionMarkCircleIcon,
    baseClass: 'bg-gray-600 hover:bg-gray-700'
  }
}

const buttonConfig = computed(() => buttonConfigs[props.type])

const buttonClass = computed(() => {
  return buttonConfig.value.baseClass
})
</script>