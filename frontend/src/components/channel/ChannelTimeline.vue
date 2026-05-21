<template>
  <div v-if="timelineData.length === 0" class="text-sm text-gray-400 dark:text-gray-500 py-2">
    {{ t('channelTimeline.noData') }}
  </div>
  <div v-else class="flex flex-col gap-2">

    <!-- Toolbar: filter chips + expand button -->
    <div class="flex items-center justify-between gap-2">
      <div class="flex items-center gap-2 flex-wrap">
        <div
          v-for="s in filterableStatuses"
          :key="s.key"
          @click="toggleFilter(s.key)"
          class="flex items-center gap-1 text-xs transition-opacity cursor-pointer select-none"
          :class="isFilterActive(s.key) ? 'opacity-100' : 'opacity-30'"
          :style="{ color: s.color }"
        >
          <span class="w-2 h-2 rounded-full shrink-0" :style="{ backgroundColor: s.color }" />
          {{ t(s.i18nKey) }}
        </div>
      </div>
      <div
        v-if="filteredData.length > MAX_VISIBLE_ROWS"
        @click="isExpanded = !isExpanded"
        class="text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-300 transition-colors shrink-0 cursor-pointer"
        :title="isExpanded ? t('channelTimeline.collapse') : t('channelTimeline.expand')"
      >
        <ArrowsPointingInIcon v-if="isExpanded" class="w-4 h-4" />
        <ArrowsPointingOutIcon v-else class="w-4 h-4" />
      </div>
    </div>

    <!-- No results after filter -->
    <div v-if="filteredData.length === 0" class="text-sm text-gray-400 dark:text-gray-500 py-1">
      {{ t('channelTimeline.noData') }}
    </div>

    <!-- Chart -->
    <v-chart
      v-else
      :option="chartOption"
      autoresize
      class="w-full"
      :style="{ height: chartHeight }"
      @click="handleChartClick"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useBossStore } from '@/stores/bossStore'
import { useI18n } from 'vue-i18n'
import { useDark } from '@vueuse/core'
import { ArrowsPointingOutIcon, ArrowsPointingInIcon } from '@heroicons/vue/24/outline'
import { STATUS_COLORS, STATUS_ORDER } from '@/composables/useStatusConfig'
import { type BossRecord } from '@/stores/bossStore'

// ECharts tree-shaking imports
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { CustomChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, DataZoomComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, CustomChart, GridComponent, TooltipComponent, DataZoomComponent])

const { t } = useI18n()
const bossStore = useBossStore()
const { selectedBossTypeId } = storeToRefs(bossStore)
const isDark = useDark()

const filterableStatuses = [
  { key: 'may_respawn', color: STATUS_COLORS.may_respawn, i18nKey: 'status.mayRespawn' },
  { key: 'respawning',  color: STATUS_COLORS.respawning,  i18nKey: 'status.respawning' },
  { key: 'alive',       color: STATUS_COLORS.alive,       i18nKey: 'status.alive' },
  { key: 'expired',     color: STATUS_COLORS.expired,     i18nKey: 'status.expired' },
] as const

// Filter state (all active by default)
const activeFilters = ref<string[]>(['may_respawn', 'respawning', 'alive', 'expired'])
const isExpanded = ref(false)

function isFilterActive(key: string): boolean {
  return activeFilters.value.includes(key)
}
function toggleFilter(key: string) {
  if (activeFilters.value.includes(key)) {
    activeFilters.value = activeFilters.value.filter((k) => k !== key)
  } else {
    activeFilters.value = [...activeFilters.value, key]
  }
}

function isExpiredRecord(record: BossRecord, now: number): boolean {
  if (record.current_status !== 'alive') return false
  if (!record.respawn_min_time || !record.respawn_max_time) return false
  const windowDuration = new Date(record.respawn_max_time).getTime() - new Date(record.respawn_min_time).getTime()
  return now - new Date(record.respawn_max_time).getTime() > windowDuration
}

interface TimelineRow {
  channel: number
  minTime: number
  maxTime: number
  status: string
  isExpired: boolean
}

const timelineData = computed<TimelineRow[]>(() => {
  const now = Date.now()
  const records = bossStore.bossRecords.filter(
    (r) => r.boss_type_id === selectedBossTypeId.value && r.respawn_min_time && r.respawn_max_time
  )
  if (records.length === 0) return []

  const sorted = records.slice().sort((a, b) => {
    const aExp = isExpiredRecord(a, now)
    const bExp = isExpiredRecord(b, now)
    if (aExp !== bExp) return aExp ? 1 : -1
    const aOrd = STATUS_ORDER[a.current_status] ?? 4
    const bOrd = STATUS_ORDER[b.current_status] ?? 4
    if (aOrd !== bOrd) return aOrd - bOrd
    return new Date(a.respawn_min_time!).getTime() - new Date(b.respawn_min_time!).getTime()
  })

  return sorted.map((r) => ({
    channel: r.channel,
    minTime: new Date(r.respawn_min_time!).getTime(),
    maxTime: new Date(r.respawn_max_time!).getTime(),
    status: r.current_status,
    isExpired: isExpiredRecord(r, now),
  }))
})

const filteredData = computed<TimelineRow[]>(() => {
  return timelineData.value.filter((r) => {
    const key = r.isExpired ? 'expired' : r.status
    return activeFilters.value.includes(key)
  })
})

const MAX_HEIGHT = 480
const ROW_HEIGHT = 34
const MAX_VISIBLE_ROWS = Math.floor((MAX_HEIGHT - 60) / ROW_HEIGHT)

const needsScroll = computed(() => !isExpanded.value && filteredData.value.length > MAX_VISIBLE_ROWS)

const chartHeight = computed(() => {
  const rows = filteredData.value.length
  return `${Math.min(MAX_HEIGHT, Math.max(120, rows * ROW_HEIGHT + 60))}px`
})

const chartOption = computed(() => {
  const rows = filteredData.value
  if (rows.length === 0) return {}

  const now = Date.now()
  const categories = rows.map((r) => `CH ${r.channel}`)

  const maxDisplayTime = Math.max(...rows.map((r) => r.maxTime))
  const span = maxDisplayTime - now
  const padding = span * 0.03

  const textColor = isDark.value ? '#9ca3af' : '#6b7280'
  const splitColor = isDark.value ? '#374151' : '#e5e7eb'
  const scrollbarFill = isDark.value ? 'rgba(99,102,241,0.35)' : 'rgba(99,102,241,0.25)'

  const barData = rows.map((r, i) => ({
    value: [i, Math.max(r.minTime, now), r.maxTime, r.status, r.channel, r.isExpired, r.minTime],
    itemStyle: {
      color: r.isExpired ? STATUS_COLORS['expired'] : (STATUS_COLORS[r.status] ?? '#9ca3af'),
      opacity: r.isExpired ? 0.5 : 0.85,
      borderRadius: 3,
    },
  }))

  return {
    backgroundColor: 'transparent',
    animation: true,
    animationDuration: 400,
    grid: {
      left: 56,
      right: needsScroll.value ? 22 : 16,
      top: 8,
      bottom: 32,
      containLabel: false,
    },
    xAxis: {
      type: 'time',
      min: now,
      max: maxDisplayTime + padding,
      axisLabel: {
        color: textColor,
        fontSize: 11,
        formatter: (value: number) => {
          const d = new Date(value)
          return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
        },
      },
      axisLine: { lineStyle: { color: splitColor } },
      splitLine: {
        show: true,
        lineStyle: { color: splitColor, type: 'dashed', opacity: 0.5 },
      },
    },
    yAxis: {
      type: 'category',
      data: categories,
      inverse: true,
      axisLabel: { color: textColor, fontSize: 11, fontWeight: 'bold' },
      axisTick: { show: false },
      axisLine: { lineStyle: { color: splitColor } },
      splitLine: { show: false },
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: isDark.value ? '#1f2937' : '#fff',
      borderColor: isDark.value ? '#374151' : '#e5e7eb',
      textStyle: { color: isDark.value ? '#e5e7eb' : '#374151', fontSize: 12 },
      formatter: (params: any) => {
        if (!params.data?.value) return ''
        const [, , end, status, channel, expired, originalMin] = params.data.value
        const start = originalMin
        const fmt = (ms: number) => {
          const d = new Date(ms)
          return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}`
        }
        const displayKey = expired ? 'expired' : status
        const i18nMap: Record<string, string> = {
          may_respawn: 'status.mayRespawn',
          respawning: 'status.respawning',
          alive: 'status.alive',
          not_found: 'status.notFound',
          expired: 'status.expired',
        }
        const statusText = t(i18nMap[displayKey] ?? `status.${displayKey}`)
        const dotColor = expired ? STATUS_COLORS['expired'] : (STATUS_COLORS[status] ?? '#9ca3af')
        const dot = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${dotColor};margin-right:4px;opacity:${expired ? 0.5 : 1}"></span>`
        return `<b>CH ${channel}</b><br/>${dot}${statusText}<br/>${t('recordItem.respawnWindow')} ${fmt(start)} ~ ${fmt(end)}`
      },
    },
    dataZoom: needsScroll.value ? [
      {
        type: 'inside',
        yAxisIndex: 0,
        startValue: 0,
        endValue: MAX_VISIBLE_ROWS - 1,
        zoomOnMouseWheel: false,
        moveOnMouseWheel: true,
        moveOnMouseMove: false,
      },
      {
        type: 'slider',
        yAxisIndex: 0,
        width: 6,
        right: 2,
        startValue: 0,
        endValue: MAX_VISIBLE_ROWS - 1,
        brushSelect: false,
        showDetail: false,
        showDataShadow: false,
        fillerColor: scrollbarFill,
        borderColor: 'transparent',
        backgroundColor: 'transparent',
        handleStyle: { color: '#6366f1', borderColor: 'transparent' },
        moveHandleStyle: { color: '#6366f1', opacity: 0.6 },
        emphasis: {
          handleStyle: { color: '#4f46e5' },
          moveHandleStyle: { color: '#4f46e5' },
        },
      },
    ] : [],
    series: [
      {
        type: 'custom',
        renderItem: (params: any, api: any) => {
          const catIndex = api.value(0)
          const start = api.coord([api.value(1), catIndex])
          const end = api.coord([api.value(2), catIndex])
          const bandWidth = api.size([0, 1])[1]
          const barHeight = bandWidth * 0.55
          const itemStyle = barData[params.dataIndex]?.itemStyle ?? {}
          return {
            type: 'rect',
            shape: {
              x: start[0],
              y: start[1] - barHeight / 2,
              width: Math.max(end[0] - start[0], 4),
              height: barHeight,
              r: itemStyle.borderRadius ?? 0,
            },
            style: {
              fill: itemStyle.color,
              opacity: itemStyle.opacity,
            },
          }
        },
        encode: { x: [1, 2], y: 0 },
        data: barData,
      },
    ],
  }
})

function handleChartClick(params: any) {
  if (params.data?.value) {
    const channel = params.data.value[4]
    if (channel != null) bossStore.setSelectedChannel(channel)
  }
}
</script>