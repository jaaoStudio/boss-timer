<template>
  <div class="rounded-lg p-4" :class="containerClass">
    <h3 class="font-bold mb-3" :class="titleClass">{{ title }}</h3>
    <div v-if="channels.length > 0" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
      <div v-for="record in channels" :key="record.channel" class="p-2 rounded-md text-center" :class="itemClass">
        <div class="font-semibold">CH {{ record.channel }}</div>
        <div class="text-xs">
          <CountdownTimer
            v-if="type === 'priority'"
            :target-time="record.respawn_max_time"
            :prefix="'until'"
            @timer-end="handleTimerEnd(record)"
          />
          <CountdownTimer
            v-if="type === 'avoid'"
            :target-time="record.respawn_min_time"
            :prefix="'in'"
            @timer-end="handleTimerEnd(record)"
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
import { useBossStore } from '@/stores/bossStore'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const bossStore = useBossStore()

interface ChannelRecord {
  id?: number | string
  channel: number
  respawn_min_time: string
  respawn_max_time: string
  [key: string]: any
}

const props = defineProps<{
  title: string
  channels: ChannelRecord[]
  type: 'priority' | 'avoid'
}>()

const handleTimerEnd = (record: ChannelRecord) => {
  bossStore.updateBossStatusOnTimerEnd(record)
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