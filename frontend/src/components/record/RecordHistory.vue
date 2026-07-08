<template>
  <div class="bg-white dark:bg-gray-800/90 rounded-2xl border border-gray-200 dark:border-gray-700/70 shadow-[var(--shadow-card)] p-6">
    <div class="flex flex-wrap items-center justify-between gap-2 mb-4">
      <h2 class="text-xl font-semibold tracking-tight text-gray-900 dark:text-white">{{ t('recordHistory.title') }}</h2>
      <div class="flex flex-wrap gap-2 w-full @md:w-auto">
        <el-date-picker
          v-model="dateRange"
          type="daterange"
          value-format="YYYY-MM-DD"
          :start-placeholder="t('recordHistory.startDate')"
          :end-placeholder="t('recordHistory.endDate')"
          :range-separator="t('recordHistory.dateRangeSeparator')"
          :shortcuts="dateShortcuts"
          :disabled-date="disabledDate"
          @calendar-change="onCalendarChange"
          clearable
          unlink-panels
          class="!w-full @md:!w-auto"
        />
        <select v-model="selectedBossFilter"
                class="flex-1 @md:flex-none px-3 py-2 border border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-[var(--accent-ring)] focus:border-transparent transition">
          <option value="">{{ t('recordHistory.allBosses') }}</option>
          <option v-for="boss in bossTypes" :key="boss.id" :value="boss.id">
            {{ locale === 'zh' ? boss.name_zh : boss.name_en }}
          </option>
        </select>
      </div>
    </div>
    <div ref="scrollEl" class="space-y-3 max-h-96 overflow-y-auto">
      <RecordItem
          v-for="record in sortedRecords"
          :key="record.id"
          :record="record"
          :isDeleting="deletingIds.includes(record.id)"
          @click="bossStore.setSelectedBossTypeId(record.boss_type_id)"
          @delete="handleDelete"
          class="cursor-pointer"
      />
      <div v-if="isLoading" class="text-center text-sm text-gray-500 dark:text-gray-400 py-3">
        {{ t('recordHistory.loadingMore') }}
      </div>
      <div v-else-if="!sortedRecords.length" class="text-center text-sm text-gray-500 dark:text-gray-400 py-6">
        {{ t('recordHistory.empty') }}
      </div>
      <div v-else-if="!hasMore" class="text-center text-sm text-gray-400 dark:text-gray-500 py-3">
        {{ t('recordHistory.noMore') }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useInfiniteScroll } from '@vueuse/core'
import { useBossStore } from '@/stores/bossStore'
import { useRoomStore } from '@/stores/roomStore'
import { useRecordHistoryStore } from '@/stores/recordHistoryStore'
import RecordItem from './RecordItem.vue'
import { useI18n } from 'vue-i18n'
import { ElMessageBox, ElMessage } from 'element-plus'
import { subDays, format } from 'date-fns'
import apiService from '@/services/apiService'

const { t, locale } = useI18n()
const bossStore = useBossStore()
const roomStore = useRoomStore()
const recordHistoryStore = useRecordHistoryStore()

const { bossTypes } = storeToRefs(bossStore)
const { sortedRecords, hasMore, isLoading } = storeToRefs(recordHistoryStore)

const deletingIds = ref<number[]>([])
const selectedBossFilter = ref<number | ''>('')

const MAX_RANGE_DAYS = 30
const DAY_MS = 86_400_000

const defaultRange = (): [string, string] => [
  format(subDays(new Date(), 1), 'yyyy-MM-dd'),
  format(new Date(), 'yyyy-MM-dd'),
]
const dateRange = ref<[string, string] | null>(defaultRange())

const pickingStart = ref<Date | null>(null)

const onCalendarChange = (dates: [Date, Date] | null) => {
  pickingStart.value = dates?.[0] ?? null
}

const disabledDate = (date: Date): boolean => {
  if (date.getTime() > Date.now()) return true
  if (pickingStart.value) {
    const anchor = pickingStart.value.getTime()
    return Math.abs(date.getTime() - anchor) > (MAX_RANGE_DAYS - 1) * DAY_MS
  }
  return false
}

const dateShortcuts = [
  {
    text: t('recordHistory.last1Day'),
    value: () => [subDays(new Date(), 1), new Date()] as [Date, Date],
  },
  {
    text: t('recordHistory.last7Days'),
    value: () => [subDays(new Date(), 6), new Date()] as [Date, Date],
  },
  {
    text: t('recordHistory.last30Days'),
    value: () => [subDays(new Date(), 29), new Date()] as [Date, Date],
  },
]

const scrollEl = ref<HTMLElement | null>(null)

useInfiniteScroll(
  scrollEl,
  () => recordHistoryStore.loadMore(),
  {
    distance: 100,
    canLoadMore: () => recordHistoryStore.hasMore && !recordHistoryStore.isLoading,
  },
)

function applyFiltersAndReload() {
  recordHistoryStore.setRoomId(roomStore.roomId)
  recordHistoryStore.setFilters({
    start: dateRange.value?.[0],
    end: dateRange.value?.[1],
    bossTypeId: selectedBossFilter.value || undefined,
  })
  recordHistoryStore.loadMore()
}

watch([dateRange, selectedBossFilter, () => roomStore.roomId], () => {
  applyFiltersAndReload()
})

onMounted(() => {
  applyFiltersAndReload()
})

onUnmounted(() => {
  recordHistoryStore.reset()
})

const handleDelete = async (recordId: number) => {
  if (deletingIds.value.includes(recordId)) return;
  deletingIds.value.push(recordId)

  try {
    await ElMessageBox.confirm(
      t('recordHistory.deleteConfirmMessage'),
      t('recordHistory.deleteConfirmTitle'),
      {
        confirmButtonText: t('recordHistory.deleteConfirm'),
        cancelButtonText: t('recordHistory.deleteCancel'),
        type: 'warning',
      }
    )

    await apiService.deleteBossRecord(roomStore.roomId, recordId)
    ElMessage.success(t('recordHistory.deleteSuccess'))
  } catch (err: unknown) {
    const status = (err as { response?: { status?: number } })?.response?.status
    if (err !== 'cancel' && status !== 429 && status !== 404) {
      ElMessage.error(t('recordHistory.deleteFailed'))
      console.error(err)
    }
  } finally {
    deletingIds.value = deletingIds.value.filter(id => id !== recordId)
  }
}
</script>