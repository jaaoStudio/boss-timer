<template>
  <div class="bg-white rounded-lg shadow-md p-6 mb-6">
    <h2 class="text-xl font-semibold text-gray-800 mb-4">記錄 BOSS 狀態</h2>

    <form @submit.prevent="recordBoss" class="grid grid-cols-1 md:grid-cols-4 gap-4">
      <!-- 頻道選擇 -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">頻道</label>
        <select
          v-model="form.channel"
          class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
        >
          <option value="">選擇頻道</option>
          <option v-for="i in 30" :key="i" :value="i">{{ i }}</option>
        </select>
      </div>

      <!-- BOSS選擇 -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">BOSS</label>
        <select
          v-model="form.boss_name"
          @change="bossStore.setSelectedBossName(form.boss_name)"
          class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
        >
          <option value="">選擇 BOSS</option>
          <option v-for="boss in bossStore.bossTypes" :key="boss.boss_name" :value="boss.boss_name">
            {{ boss.boss_name }}
          </option>
        </select>
      </div>

      <!-- 狀態選擇 -->
      <div>
        <label class="block text-sm font-medium text-gray-700 mb-1">狀態</label>
        <select
          v-model="form.status"
          class="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
        >
          <option value="">選擇狀態</option>
          <option value="alive">存活</option>
          <option value="killed">擊殺</option>
          <option value="not_found">未發現</option>
        </select>
      </div>

      <!-- 提交按鈕 -->
      <div class="flex items-end">
        <button
          type="submit"
          :disabled="!canSubmit || loading"
          class="w-full px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600 disabled:bg-gray-300 disabled:cursor-not-allowed"
        >
          {{ loading ? '記錄中...' : '記錄狀態' }}
        </button>
      </div>
    </form>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRoomStore } from '@/stores/roomStore'
import { useBossStore } from '@/stores/bossStore'
import ApiService from '@/services/apiService.js'

const roomStore = useRoomStore()
const bossStore = useBossStore()

const form = ref({
  channel: '',
  boss_name: '',
  status: ''
})

const loading = ref(false)

const canSubmit = computed(() => {
  return roomStore.roomId &&
         form.value.channel &&
         form.value.boss_name &&
         form.value.status
})

const recordBoss = async () => {
  if (!canSubmit.value) return

  loading.value = true
  try {
    await ApiService.recordBoss({
      room_id: roomStore.roomId,
      channel: parseInt(form.value.channel),
      boss_name: form.value.boss_name,
      status: form.value.status
    })

    // 重置表單
    form.value = { channel: '', boss_name: '', status: '' }
  } catch (error) {
    console.error('Failed to record boss:', error)
    alert('記錄失敗，請重試')
  } finally {
    loading.value = false
  }
}
</script>