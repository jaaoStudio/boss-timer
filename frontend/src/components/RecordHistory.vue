<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
    <h2 class="text-xl font-semibold text-gray-900 dark:text-white mb-4">{{ t('recordHistory.title') }}</h2>
    <div class="flex justify-end mb-4">
      <select v-model="selectedBossFilter"
              class="px-3 py-2 border border-gray-300 dark:border-gray-700 bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500">
        <option value="">{{ t('recordHistory.allBosses') }}</option>
        <option v-for="boss in bossTypes" :key="boss.id" :value="boss.id">
          {{ locale === 'zh' ? boss.name_zh : boss.name_en }}
        </option>
      </select>
    </div>
    <div class="space-y-3 max-h-96 overflow-y-auto">
      <RecordItem
          v-for="record in filteredBossRecords"
          :key="record.id"
          :record="record"
          @click="bossStore.setSelectedBossTypeId(record.boss_type_id)"
          @delete="handleDelete"
          class="cursor-pointer"
      />
    </div>
    <!-- Loading state removed as it was unused -->
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useBossStore } from '@/stores/bossStore'
import { useRoomStore } from '@/stores/roomStore'
import RecordItem from './RecordItem.vue'
import { useI18n } from 'vue-i18n'
import { ElMessageBox, ElMessage } from 'element-plus'
import apiService from '@/services/apiService'

const { t, locale } = useI18n()
const bossStore = useBossStore()
const roomStore = useRoomStore()

const { bossTypes, bossRecords } = storeToRefs(bossStore)

const selectedBossFilter = ref<number | ''>('')

const filteredBossRecords = computed(() => {
  if (!selectedBossFilter.value) {
    return bossRecords.value
  }
  return bossRecords.value.filter(record => record.boss_type_id === selectedBossFilter.value)
})

const handleDelete = async (recordId: number) => {
  try {
    await ElMessageBox.confirm(
      t('recordHistory.deleteConfirmMessage'),
      t('recordHistory.deleteConfirmTitle'),
      {
        confirmButtonText: '確定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
    
    await apiService.deleteBossRecord(roomStore.roomId, recordId)
    ElMessage.success(t('recordHistory.deleteSuccess'))
  } catch (err: any) {
    if (err !== 'cancel' && err?.response?.status !== 429 && err?.response?.status !== 404) {
      ElMessage.error(t('recordHistory.deleteFailed'))
      console.error(err)
    }
  }
}
</script>
