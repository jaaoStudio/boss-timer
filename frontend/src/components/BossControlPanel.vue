<template>
  <div class="bg-gray-800 rounded-lg shadow-md p-6 mb-6">
    <h2 class="text-xl font-semibold text-white mb-4"></h2>

    <form @submit.prevent="recordBoss" class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <!-- 頻道選擇 -->
      <div>
        <label class="block text-sm font-medium text-gray-300 mb-1">頻道</label>
        <input
          v-model.number="form.channel"
          type="text"
          inputmode="numeric"
          pattern="\d*"
          class="w-full h-9 px-3 py-2 border border-gray-700 bg-gray-900 text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
          @input="onChannelInput"
        >
      </div>

      <!-- BOSS選擇 -->
      <div>
        <label class="block text-sm font-medium text-gray-300 mb-1">BOSS</label>
        <select
          v-model="form.boss_name"
          @change="bossStore.setSelectedBossName(form.boss_name)"
          class="w-full h-9 px-3 py-2 border border-gray-700 bg-gray-900 text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
        >
          <option value="">選擇 BOSS</option>
          <option v-for="boss in bossTypes" :key="boss.boss_name" :value="boss.boss_name">
            {{ boss.boss_name }}
          </option>
        </select>
      </div>

      <!-- 狀態選擇 -->
      <div>
        <label class="block text-sm font-medium text-gray-300 mb-1">狀態</label>
        <div class="flex gap-2">
          <BossStatusButton
            v-for="status in statuses"
            :key="status.type"
            :type="status.type"
            :disabled="loading"
            :class="{
              'opacity-60': loading
            }"
            @click="() => onSelectStatus(status.type)"
          />
        </div>
      </div>
    </form>
  </div>
</template>

<script setup>
import {ref, computed, watch, onMounted} from 'vue'
import { storeToRefs } from 'pinia'
import { useRoomStore } from '@/stores/roomStore'
import { useBossStore } from '@/stores/bossStore'
import ApiService from '@/services/apiService.js'
import BossStatusButton from "@/components/BossStatusButton.vue";

const roomStore = useRoomStore()
const bossStore = useBossStore()

const { roomId } = storeToRefs(roomStore)
const { bossTypes, selectedChannel, selectedBossName } = storeToRefs(bossStore)

const statuses = [
  { type: 'alive' },
  { type: 'killed' },
  { type: 'not_found' }
]

const form = ref({
  channel: selectedChannel.value || '',
  boss_name: '',
  status: ''
})

const onSelectStatus = async (statusType) => {
  if (loading.value) return;
  form.value.status = statusType;
  await recordBoss();
}

// 監聽 selectedChannel 的變化並更新 form.channel
watch(selectedChannel, (newVal) => {
  form.value.channel = newVal
})

watch(selectedBossName, (newVal) => {
  form.value.boss_name = newVal
})

const loading = ref(false)

const canSubmit = computed(() => {
  return roomId.value &&
         form.value.channel &&
         form.value.boss_name &&
         form.value.status
})

const recordBoss = async () => {
  if (!canSubmit.value) return

  loading.value = true
  try {
    const newRecord = await ApiService.recordBoss({
      room_id: roomId.value,
      channel: parseInt(form.value.channel),
      boss_name: form.value.boss_name,
      status: form.value.status
    })

    // 更新 Pinia store 中的 bossRecords 和 history
    await bossStore.updateBossRecord(newRecord.data)

    // 重置表單
    form.value.channel = ''

  } catch (error) {
    console.error('Failed to record boss:', error)
    alert('記錄失敗，請重試')
  } finally {
    loading.value = false
  }
}

const onChannelInput = (e) => {
    // 移除非數字字元
    e.target.value = e.target.value.replace(/\D/g, '');
    form.value.channel = e.target.value ? parseInt(e.target.value, 10) : null;
  }

onMounted(() => {
  form.value.boss_name = selectedBossName.value
})
</script>