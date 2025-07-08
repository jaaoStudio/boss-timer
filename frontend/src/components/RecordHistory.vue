<template>
  <div class="bg-gray-800 rounded-lg shadow-md p-6">
    <h2 class="text-xl font-semibold text-white mb-4">Record History</h2>
    <div class="flex justify-end mb-4">
      <select v-model="selectedBossFilter"
              class="px-3 py-2 border border-gray-700 bg-gray-900 text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
        <option value="">All Bosses</option>
        <option v-for="boss in bossTypes" :key="boss.boss_name" :value="boss.boss_name">
          {{ boss.boss_name }}
        </option>
      </select>
    </div>
    <div class="space-y-3 max-h-96 overflow-y-auto">
      <RecordItem
          v-for="record in filteredBossRecords"
          :key="record.id"
          :record="record"
      />
    </div>
    <div v-if="historyOnLoading" class="text-center mt-4">Loading...</div>
  </div>
</template>

<script setup>
import {ref, onMounted, watch, computed} from 'vue'
import {storeToRefs} from 'pinia'
import {useBossStore} from '@/stores/bossStore.js'
import {useRoomStore} from '@/stores/roomStore.js'
import RecordItem from './RecordItem.vue'

const bossStore = useBossStore()
const roomStore = useRoomStore()

const {bossTypes, bossRecords} = storeToRefs(bossStore)
const {roomId} = storeToRefs(roomStore)

const historyOnLoading = ref(false)
const selectedBossFilter = ref('')

const filteredBossRecords = computed(() => {
  if (!selectedBossFilter.value) {
    return bossRecords.value
  }
  return bossRecords.value.filter(record => record.boss_name === selectedBossFilter.value)
})

</script>