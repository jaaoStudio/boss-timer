<template>
  <div class="grid gap-2 overflow-auto [grid-template-columns:repeat(auto-fill,minmax(3.5rem,1fr))]">
    <ChannelCard
      v-for="channel in recordedChannels"
      :key="channel"
      :channel-number="channel"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useBossStore } from '@/stores/bossStore'
import ChannelCard from './ChannelCard.vue'
import { STATUS_ORDER, isExpiredRecord } from '@/composables/useStatusConfig'

const bossStore = useBossStore()
const { selectedBossTypeId } = storeToRefs(bossStore)

const recordedChannels = computed<number[]>(() => {
  if (bossStore.bossRecords.length === 0) return []

  const records = bossStore.bossRecords.filter(
    (r) => r.boss_type_id === selectedBossTypeId.value
  )

  return records
    .slice()
    .sort((a, b) => {
      const aExpired = isExpiredRecord(a)
      const bExpired = isExpiredRecord(b)
      if (aExpired !== bExpired) return aExpired ? 1 : -1

      const aOrder = STATUS_ORDER[a.current_status] ?? 4
      const bOrder = STATUS_ORDER[b.current_status] ?? 4
      if (aOrder !== bOrder) return aOrder - bOrder

      // 同狀態：依最早可重生時間升冪（越快出現的排越前）
      if (a.respawn_min_time && b.respawn_min_time) {
        return new Date(a.respawn_min_time).getTime() - new Date(b.respawn_min_time).getTime()
      }
      return a.channel - b.channel
    })
    .map((r) => r.channel)
})
</script>