import { defineStore } from 'pinia'
import { ref, computed, shallowRef } from 'vue'
import apiService from '@/services/apiService'
import type { BossRecord } from './bossStore'

interface HistoryFilters {
  start?: string
  end?: string
  bossTypeId?: number
}

const PAGE_LIMIT = 50

export const useRecordHistoryStore = defineStore('recordHistory', () => {
  const records = shallowRef(new Map<number, BossRecord>())
  const deletedIds = shallowRef(new Set<number>())
  const hasMore = ref(true)
  const isLoading = ref(false)
  const nextCursor = ref<number | null>(null)
  const roomId = ref<string | null>(null)
  const filters = ref<HistoryFilters>({})
  let currentAbort: AbortController | null = null

  const sortedRecords = computed<BossRecord[]>(() =>
    [...records.value.values()].sort((a, b) => b.id - a.id),
  )

  function abortInFlight() {
    if (currentAbort) {
      currentAbort.abort()
      currentAbort = null
    }
  }

  function reset() {
    abortInFlight()
    records.value = new Map()
    deletedIds.value = new Set()
    hasMore.value = true
    nextCursor.value = null
    isLoading.value = false
  }

  function setRoomId(id: string | null) {
    if (roomId.value === id) return
    roomId.value = id
    reset()
  }

  function setFilters(next: HistoryFilters) {
    filters.value = { ...next }
    reset()
  }

  function startOfDayIso(date?: string): string | undefined {
    if (!date) return undefined
    return new Date(`${date}T00:00:00`).toISOString()
  }

  function endOfDayIso(date?: string): string | undefined {
    if (!date) return undefined
    return new Date(`${date}T23:59:59.999`).toISOString()
  }

  function passesFilter(record: BossRecord): boolean {
    const f = filters.value
    if (f.bossTypeId && record.boss_type_id !== f.bossTypeId) return false
    const ts = new Date(record.recorded_at).getTime()
    if (f.start && ts < new Date(`${f.start}T00:00:00`).getTime()) return false
    if (f.end && ts > new Date(`${f.end}T23:59:59.999`).getTime()) return false
    return true
  }

  async function loadMore() {
    if (!roomId.value || isLoading.value || !hasMore.value) return
    isLoading.value = true
    const abort = new AbortController()
    currentAbort = abort

    try {
      const data = await apiService.getRoomRecordsHistory(
        roomId.value,
        {
          before_id: nextCursor.value ?? undefined,
          limit: PAGE_LIMIT,
          start: startOfDayIso(filters.value.start),
          end: endOfDayIso(filters.value.end),
          boss_type_id: filters.value.bossTypeId,
        },
        abort.signal,
      )
      if (currentAbort !== abort) return

      const nextMap = new Map(records.value)
      for (const r of data.records as BossRecord[]) {
        if (deletedIds.value.has(r.id)) continue
        nextMap.set(r.id, r)
      }
      records.value = nextMap
      hasMore.value = !!data.has_more
      nextCursor.value = data.next_cursor ?? null
    } catch (err: unknown) {
      const e = err as { name?: string; code?: string }
      if (e?.name === 'CanceledError' || e?.code === 'ERR_CANCELED') return
      console.error('Failed to load record history:', err)
    } finally {
      if (currentAbort === abort) currentAbort = null
      isLoading.value = false
    }
  }

  function upsertRecord(record: BossRecord) {
    if (deletedIds.value.has(record.id)) return
    if (!passesFilter(record)) return
    const next = new Map(records.value)
    next.set(record.id, record)
    records.value = next
  }

  function removeRecord(id: number) {
    const nextDeleted = new Set(deletedIds.value)
    nextDeleted.add(id)
    deletedIds.value = nextDeleted
    if (records.value.has(id)) {
      const next = new Map(records.value)
      next.delete(id)
      records.value = next
    }
  }

  return {
    records,
    deletedIds,
    hasMore,
    isLoading,
    roomId,
    filters,
    sortedRecords,
    setRoomId,
    setFilters,
    loadMore,
    reset,
    upsertRecord,
    removeRecord,
  }
})