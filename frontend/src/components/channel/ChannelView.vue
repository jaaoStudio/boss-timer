<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
    <div class="flex items-center justify-between mb-4 flex-wrap gap-1.5">
      <div class="flex items-center gap-2">
        <h2 class="text-xl font-semibold text-gray-900 dark:text-white">{{ t('channelOverview.title') }}</h2>
        <el-button
          v-if="hasRecordsForSelectedBoss"
          size="small"
          type="danger"
          plain
          :loading="isClearing"
          :title="t('channelOverview.clearButton')"
          @click="handleClear"
        >
          <el-icon><Delete /></el-icon>
        </el-button>
      </div>
      <el-segmented
        :model-value="viewMode"
        :options="viewOptions"
        @change="setViewMode"
        size="small"
      >
        <template #default="{ item }">
          <div class="flex items-center gap-1">
            <component :is="item.icon" class="w-3.5 h-3.5 shrink-0" />
            {{ item.label }}
          </div>
        </template>
      </el-segmented>
    </div>
    <ChannelTimeline v-if="viewMode === 'timeline'" />
    <ChannelOverview v-else />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { Squares2X2Icon, ChartBarSquareIcon } from '@heroicons/vue/24/outline'
import { Delete } from '@element-plus/icons-vue'
import { ElMessageBox } from 'element-plus'
import { useChannelViewPreference } from '@/composables/useChannelViewPreference'
import { useBossStore } from '@/stores/bossStore'
import { useRoomStore } from '@/stores/roomStore'
import { showMessage } from '@/composables/useElementPlus'
import apiService from '@/services/apiService'
import ChannelOverview from './ChannelOverview.vue'
import ChannelTimeline from './ChannelTimeline.vue'

const { t } = useI18n()
const { viewMode, setViewMode } = useChannelViewPreference()
const bossStore = useBossStore()
const roomStore = useRoomStore()
const { selectedBossTypeId } = storeToRefs(bossStore)
const { roomId } = storeToRefs(roomStore)

const isClearing = ref(false)

const hasRecordsForSelectedBoss = computed(() =>
  selectedBossTypeId.value !== null &&
  bossStore.bossRecords.some(r => r.boss_type_id === selectedBossTypeId.value)
)

const viewOptions = computed(() => [
  { value: 'overview', label: t('settings.channelViewOverview'), icon: Squares2X2Icon },
  { value: 'timeline', label: t('settings.channelViewTimeline'), icon: ChartBarSquareIcon },
])

async function handleClear() {
  if (!roomId.value || selectedBossTypeId.value === null) return

  try {
    await ElMessageBox.confirm(
      t('channelOverview.clearConfirmMessage'),
      t('channelOverview.clearConfirmTitle'),
      { type: 'warning', confirmButtonText: t('channelOverview.clearConfirm'), cancelButtonText: t('channelOverview.clearCancel') },
    )
  } catch {
    return
  }

  isClearing.value = true
  try {
    await apiService.clearBossTypeRecords(roomId.value, selectedBossTypeId.value)
  } catch {
    showMessage.error(t('channelOverview.clearFailed'))
  } finally {
    isClearing.value = false
  }
}
</script>