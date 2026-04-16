<template>
  <el-timeline class="pt-2 pl-1 pr-6 max-h-[50vh] overflow-y-auto w-full">
    <el-timeline-item
      v-for="(version, index) in changelogData"
      :key="version.id"
      :timestamp="version.date"
      placement="top"
      :type="index === 0 ? 'primary' : 'info'"
      :hollow="index !== 0"
    >
      <el-card shadow="never" class="!border-gray-100 dark:!border-gray-700 !bg-gray-50 dark:!bg-gray-800">
        <h4 class="font-bold text-sm text-gray-800 dark:text-gray-200 mb-2">{{ version.title }}</h4>
        <ul class="list-disc pl-4 space-y-1">
          <li v-for="(item, i) in version.items" :key="i" class="text-left text-xs text-gray-600 dark:text-gray-400">
            {{ item }}
          </li>
        </ul>
      </el-card>
    </el-timeline-item>
  </el-timeline>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { tm } = useI18n()

type ChangelogVersion = { title: string; date: string; items: string[] }

const changelogData = computed(() => {
  const all = tm('changelog') as Record<string, ChangelogVersion>
  return Object.keys(all).map((key) => ({
    id: key.replace(/_/g, '.'),
    title: all[key].title,
    date: all[key].date,
    items: all[key].items,
  }))
})
</script>