<template>
  <div class="bg-gray-900 text-gray-200 p-4 sm:p-6 md:p-8">
    <div class="max-w-4xl mx-auto">
      <h1 class="text-4xl font-bold text-white mb-6 border-b border-gray-700 pb-4">
        {{ t('credits.title') }}
      </h1>

      <div class="space-y-8">
        <!-- Icons section -->
        <div v-if="icons.length">
          <h2 class="text-2xl font-semibold text-teal-400 mb-4">{{ t('credits.iconsTitle') }}</h2>
          <p class="text-gray-400 mb-4">
            {{ t('credits.iconsDescription') }}
          </p>
          <ul class="list-disc list-inside space-y-3 text-gray-300">
            <li v-for="icon in icons" :key="icon.name">
              "{{ icon.name }}" {{ t('credits.iconMadeBy') }}
              <a :href="icon.authorUrl" target="_blank" rel="noopener noreferrer" class="text-blue-400 hover:text-blue-300 underline">
                {{ icon.author }}
              </a>
              <span v-if="icon.note" class="text-gray-400"> ({{ icon.note }})</span>
              <span v-else>
                {{ t('credits.from') }}
                <a href="https://www.flaticon.com" target="_blank" rel="noopener noreferrer" class="text-blue-400 hover:text-blue-300">
                  www.flaticon.com
                </a>
              </span>
            </li>
          </ul>
        </div>

        <!-- Technology section -->
        <div v-if="technologies.length">
          <h2 class="text-2xl font-semibold text-teal-400 mb-4">{{ t('credits.technologyTitle') }}</h2>
          <p class="text-gray-400 mb-4">
            {{ t('credits.technologyDescription') }}
          </p>
          <ul class="list-disc list-inside space-y-3 text-gray-300">
            <li v-for="tech in technologies" :key="tech">{{ tech.key ? t(tech.key) : tech.name }}</li>
          </ul>
        </div>

        <!-- Data Sources section -->
        <div v-if="resources.length">
          <h2 class="text-2xl font-semibold text-teal-400 mb-4">{{ t('credits.dataSourcesTitle') }}</h2>
          <ul class="list-disc list-inside space-y-3 text-gray-300">
            <li v-for="resource in resources" :key="resource.name">
              <a :href="resource.url" target="_blank" rel="noopener noreferrer" class="text-blue-400 hover:text-blue-300 underline">
                {{ resource.name }}
              </a>
            </li>
          </ul>
        </div>

      </div>

      <div class="mt-12 text-center text-gray-500">
        <router-link to="/" class="hover:text-gray-300 underline">{{ t('credits.backToHome') }}</router-link>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { useI18n } from 'vue-i18n';

const { t } = useI18n();

const icons = [
  {
    name: "maple-leaf",
    author: "Freepik",
    authorUrl: "https://www.flaticon.com/free-icons/maple-leaf",
  },
  {
    name: "Heroicons",
    author: "Tailwind Labs",
    authorUrl: "https://heroicons.com/",
    note: "MIT License - no individual attribution needed",
  },
  {
    name: "Font Awesome Free 6.7.2",
    author: "@fontawesome",
    authorUrl: "https://fontawesome.com",
    note: "CC BY 4.0 License - see license page for details",
  },
];

const technologies = [
  { name: "Vue.js" },
  { name: "FastAPI" },
  { name: "PostgreSQL" },
  { name: "Gemini cli" },
  { name: t('credits.manyOtherLibraries'), key: 'credits.manyOtherLibraries' },
];

const resources = [];

onMounted(() => {
  window.scrollTo({
    top: 0,
    behavior: 'smooth' // 平滑滾動
  })
})
</script>

<style scoped>
/* Tailwind utilities are already used inline */
</style>

