<template>
  <div class="rounded-lg shadow-md bg-white dark:bg-slate-800 px-[18px] pt-[18px] pb-5">
    <!-- Header -->
    <div class="flex items-baseline justify-between mb-3.5">
      <span class="font-bold font-mono text-sm tracking-[1px] text-slate-900 dark:text-slate-200">
        {{ t('recommendedChannels.headerTitle') }}
      </span>
      <span class="font-mono text-[11px] tracking-[1px] text-slate-400 dark:text-slate-500">
        {{ t('recommendedChannels.statusLabel', { n: sortedRecords.length }) }}
      </span>
    </div>

    <!-- List container -->
    <div class="bg-slate-50 dark:bg-slate-900 rounded-md px-3 py-2.5 border border-slate-900/[8%] dark:border-slate-400/[14%]">

      <!-- Empty state -->
      <div
        v-if="sortedRecords.length === 0"
        class="font-mono text-xs tracking-[0.5px] py-2 text-slate-400 dark:text-slate-500"
      >{{ t('recommendedChannels.noChannels') }}</div>

      <!-- Records -->
      <button
        v-for="(item, i) in sortedRecords"
        :key="item.record.id"
        class="flex items-center gap-2.5 py-[7px] w-full border-0 rounded-none cursor-pointer text-left bg-transparent hover:bg-black/[2%] dark:hover:bg-white/[2%]"
        :style="{ borderBottom: i < sortedRecords.length - 1 ? '1px solid var(--rc-border)' : 'none' }"
        @click="handleClick(item.record)"
      >
        <!-- Radial dial -->
        <svg width="18" height="18" viewBox="0 0 18 18" class="shrink-0">
          <circle cx="9" cy="9" r="7.75" fill="none" stroke-width="2.5" style="stroke: var(--rc-border)" />
          <circle
            cx="9" cy="9" r="7.75"
            fill="none"
            stroke-width="2.5"
            stroke-linecap="round"
            :stroke-dasharray="CIRCUMFERENCE"
            :stroke-dashoffset="CIRCUMFERENCE * (1 - item.ratio)"
            transform="rotate(-90 9 9)"
            :style="{ stroke: item.color }"
          />
        </svg>

        <!-- Crit pulse dot -->
        <span
          v-if="item.urgency === 'crit'"
          class="inline-block size-[5px] rounded-full shrink-0 -ml-1.5 animate-[pulseDot_1.2s_ease-in-out_infinite]"
          :style="{ background: item.color }"
        />

        <!-- Channel number -->
        <span class="font-mono text-xs w-[80px] whitespace-pre shrink-0 text-slate-400 dark:text-slate-500">CH {{ String(item.record.channel).padStart(3, ' ') }}</span>

        <!-- Boss name -->
        <span class="font-mono text-xs flex-1 truncate min-w-0 text-slate-900 dark:text-slate-200">
          {{ getBossName(item.record.boss_type_id) }}
        </span>

        <!-- Dotted leader -->
        <span
          aria-hidden="true"
          class="flex-[0_1_60px] min-w-5 h-px shrink-0 translate-y-0.5 border-b border-dotted border-slate-900/[22%] dark:border-slate-400/[22%]"
        />

        <!-- Countdown -->
        <span
          class="font-semibold font-mono text-xs min-w-12 text-right shrink-0"
          :style="{ color: item.color }"
        >{{ item.fmtTime }}</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useBossStore, type BossRecord } from '@/stores/bossStore'
import { useI18n } from 'vue-i18n'

const { t, locale } = useI18n()
const bossStore = useBossStore()
const { allBossPriorityRecords } = storeToRefs(bossStore)

const CIRCUMFERENCE = 2 * Math.PI * 7.75

function fmtRemaining(sec: number): string {
  const s = Math.max(0, Math.floor(sec))
  const m = Math.floor(s / 60)
  const r = s % 60
  return `${m}:${String(r).padStart(2, '0')}`
}

function urgencyOf(remaining: number): 'crit' | 'warn' | 'ok' {
  if (remaining < 30) return 'crit'
  if (remaining < 90) return 'warn'
  return 'ok'
}

function urgencyColor(remaining: number): string {
  if (remaining < 30) return 'var(--rc-crit)'
  if (remaining < 90) return 'var(--rc-warn)'
  return 'var(--rc-amber)'
}

function getBossName(bossTypeId: number): string {
  const boss = bossStore.bossTypes.find(b => b.id === bossTypeId)
  if (!boss) return `Boss #${bossTypeId}`
  return locale.value === 'zh' ? boss.name_zh : boss.name_en
}

const sortedRecords = computed(() => {
  const now = bossStore._now
  return allBossPriorityRecords.value
    .map(r => {
      const maxMs = r.respawn_max_time ? new Date(r.respawn_max_time).getTime() : 0
      const minMs = r.respawn_min_time ? new Date(r.respawn_min_time).getTime() : 0
      const remaining = Math.max(0, (maxMs - now) / 1000)
      const windowSec = maxMs > minMs ? (maxMs - minMs) / 1000 : 1
      const ratio = Math.max(0, Math.min(1, remaining / windowSec))
      return {
        record: r,
        remaining,
        ratio,
        urgency: urgencyOf(remaining),
        color: urgencyColor(remaining),
        fmtTime: fmtRemaining(remaining),
      }
    })
    .sort((a, b) => a.remaining - b.remaining)
})

function handleClick(record: BossRecord) {
  bossStore.setSelectedBossTypeId(record.boss_type_id)
  bossStore.setSelectedChannel(record.channel)
}
</script>
