<template>
  <div class="bg-gray-800 rounded-lg shadow-md p-6">
    <h2 class="text-xl font-semibold text-white mb-4">Record History</h2>
    <div class="flex justify-end mb-4">
      <select v-model="selectedBossFilter" @change="fetchHistory" class="px-3 py-2 border border-gray-700 bg-gray-900 text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
        <option value="">All Bosses</option>
        <option v-for="boss in bossTypes" :key="boss.boss_name" :value="boss.boss_name">
          {{ boss.boss_name }}
        </option>
      </select>
    </div>
    <div class="space-y-3 max-h-96 overflow-y-auto">
      <RecordItem
        v-for="record in history"
        :key="record.id"
        :record="record"
      />
    </div>
    <div v-if="loading" class="text-center mt-4">Loading...</div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useBossStore } from '@/stores/bossStore'
import { useRoomStore } from '@/stores/roomStore'
import ApiService from '@/services/apiService.js'
import RecordItem from './RecordItem.vue'

const bossStore = useBossStore()
const roomStore = useRoomStore()

const { bossTypes, history, loading } = storeToRefs(bossStore)
const { roomId } = storeToRefs(roomStore)

const selectedBossFilter = ref('')

const fetchHistory = async () => {
  bossStore.setLoading(true)
  try {
    const historyData = await ApiService.getRoomHistory(
      roomId.value,
      selectedBossFilter.value || null
    )
    bossStore.setHistory(historyData)
  } catch (error) {
    console.error('Failed to fetch history:', error)
  } finally {
    bossStore.setLoading(false)
  }
}

onMounted(() => {
  fetchHistory()
})
</script>