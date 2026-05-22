<template>
  <div class="rounded-lg p-4" :class="containerClass">
    <h3 class="font-bold mb-3" :class="titleClass">{{ title }}</h3>

    <!-- 全 Boss 模式：列表格式 -->
    <div v-if="showBossName && channels.length > 0" class="flex flex-col gap-1.5">
      <div
        v-for="record in channels"
        :key="record.id"
        class="flex items-center justify-between px-3 py-2 rounded-md transition-opacity"
        :class="[itemClass, clickable ? 'cursor-pointer hover:opacity-75 active:opacity-50' : '']"
        @click="clickable && emit('record-click', record)"
      >
        <div class="flex items-center gap-2 min-w-0">
          <span class="font-semibold text-sm truncate">{{ getBossName(record.boss_type_id) }}</span>
          <span class="text-xs opacity-70 shrink-0">CH {{ record.channel }}</span>
        </div>
        <div class="text-xs shrink-0">
          <CountdownTimer
            :target-time="record.respawn_max_time"
            prefix="until"
          />
        </div>
      </div>
    </div>

    <!-- 當前 Boss 模式：原始格線格式 -->
    <div v-else-if="channels.length > 0" class="grid gap-2 [grid-template-columns:repeat(auto-fill,minmax(6rem,1fr))]">
      <div v-for="record in channels" :key="record.channel" class="p-2 rounded-md text-center" :class="itemClass">
        <div class="font-semibold">CH {{ record.channel }}</div>
        <div class="text-xs">
          <CountdownTimer
            v-if="type === 'priority'"
            :target-time="record.respawn_max_time"
            prefix="until"
          />
          <CountdownTimer
            v-if="type === 'avoid'"
            :target-time="record.respawn_min_time"
            prefix="in"
          />
        </div>
      </div>
    </div>

    <div v-else class="text-sm" :class="emptyStateClass">
      {{ t('recommendedChannels.noChannels') }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import CountdownTimer from './CountdownTimer.vue'
import { useBossStore, type BossRecord } from '@/stores/bossStore'
import { useI18n } from 'vue-i18n'

const { t, locale } = useI18n()
const bossStore = useBossStore()

const props = defineProps<{
  title: string
  channels: BossRecord[]
  type: 'priority' | 'avoid'
  showBossName?: boolean
  clickable?: boolean
}>()

const emit = defineEmits<{
  'record-click': [record: BossRecord]
}>()

const getBossName = (bossTypeId: number): string => {
  const boss = bossStore.bossTypes.find(b => b.id === bossTypeId)
  if (!boss) return `Boss #${bossTypeId}`
  return locale.value === 'zh' ? boss.name_zh : boss.name_en
}


const typeClasses = {
  priority: {
    container: 'bg-green-100 dark:bg-green-800',
    title: 'text-green-900 dark:text-white',
    item: 'bg-green-200 dark:bg-green-700',
    empty: 'text-green-700 dark:text-green-200',
  },
  avoid: {
    container: 'bg-red-100 dark:bg-red-800',
    title: 'text-red-900 dark:text-white',
    item: 'bg-red-200 dark:bg-red-700',
    empty: 'text-red-700 dark:text-red-200',
  },
} as const

const containerClass = computed(() => typeClasses[props.type].container)
const titleClass = computed(() => typeClasses[props.type].title)
const itemClass = computed(() => typeClasses[props.type].item)
const emptyStateClass = computed(() => typeClasses[props.type].empty)
</script>
