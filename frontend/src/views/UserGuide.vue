<template>
  <div class="min-h-screen bg-white dark:bg-gray-900">
    <div class="max-w-3xl mx-auto px-4 py-12">

      <!-- Header -->
      <div class="text-center mb-10">
        <h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-2">{{ t('guide.title') }}</h1>
        <p class="text-gray-500 dark:text-gray-400">{{ t('guide.subtitle') }}</p>
      </div>

      <!-- Sections -->
      <div class="space-y-8">
        <div
          v-for="(section, key) in sections"
          :key="key"
          class="bg-gray-50 dark:bg-gray-800 rounded-xl p-6 border border-gray-100 dark:border-gray-700"
        >
          <div class="flex items-center gap-3 mb-4">
            <span class="flex items-center justify-center w-8 h-8 rounded-full bg-indigo-100 dark:bg-indigo-900/50 text-indigo-600 dark:text-indigo-400 font-bold text-sm shrink-0">
              {{ section.index }}
            </span>
            <h2 class="text-lg font-semibold text-gray-900 dark:text-white">{{ section.title }}</h2>
          </div>
          <ol class="space-y-3 pl-11">
            <li
              v-for="(step, i) in section.steps"
              :key="i"
              class="flex gap-2 text-sm text-gray-600 dark:text-gray-300 leading-relaxed"
            >
              <span class="text-indigo-400 dark:text-indigo-500 font-mono shrink-0 mt-0.5">{{ i + 1 }}.</span>
              <span class="text-left">{{ step }}</span>
            </li>
          </ol>
        </div>
      </div>

      <!-- Tip Box -->
      <div class="mt-8 flex gap-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-700/50 rounded-xl px-5 py-4">
        <span class="text-amber-500 text-lg shrink-0">💡</span>
        <div class="text-sm text-amber-800 dark:text-amber-200 leading-relaxed">
          <span class="font-semibold mr-1">{{ t('guide.tip') }}：</span>{{ t('guide.tipContent') }}
        </div>
      </div>

      <!-- Back button -->
      <div class="mt-10 text-center">
        <router-link
          :to="{ name: 'RoomSelection' }"
          class="inline-flex items-center gap-2 text-sm text-indigo-600 dark:text-indigo-400 hover:underline"
        >
          <ArrowLeftIcon class="w-4 h-4" />
          {{ t('appFooter.backToHome') }}
        </router-link>
      </div>

    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ArrowLeftIcon } from '@heroicons/vue/24/outline'
import AppFooter from '@/components/AppFooter.vue'

const { t, tm } = useI18n()

interface Section {
  index: number
  title: string
  steps: string[]
}

const sections = computed<Record<string, Section>>(() => {
  const raw = tm('guide.sections') as Record<string, { title: string; steps: string[] }>
  return Object.fromEntries(
    Object.entries(raw).map(([key, val], i) => [
      key,
      { index: i + 1, title: val.title, steps: val.steps },
    ])
  )
})
</script>