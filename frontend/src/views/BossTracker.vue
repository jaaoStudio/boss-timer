<template>
  <div class="min-h-screen bg-white dark:bg-gray-900">
    <div class="flex justify-center">
      <!-- 左側廣告 -->
      <aside class="hidden xl:flex flex-col items-center pt-8 w-[160px] shrink-0">
        <AdBanner ad-slot="6801399498" />
      </aside>

      <!-- 主內容 -->
      <div class="flex-1 min-w-0 max-w-5xl px-4 py-8">
        <AppHeader />

        <!-- 編輯模式工具列 -->
        <div
          v-if="isEditMode"
          class="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-indigo-200 dark:border-indigo-700 bg-indigo-50 dark:bg-indigo-900/20 px-4 py-2.5"
        >
          <div class="flex items-center gap-2 text-indigo-700 dark:text-indigo-300 min-w-0">
            <ViewColumnsIcon class="w-4 h-4 shrink-0" />
            <span class="text-sm">{{ $t('layout.editModeHint') }}</span>
          </div>
          <div class="flex items-center gap-2 shrink-0">
            <el-button size="small" @click="resetLayout">{{ $t('layout.reset') }}</el-button>
            <el-button size="small" type="primary" @click="exitEditMode">{{ $t('layout.done') }}</el-button>
          </div>
        </div>

        <!-- 自訂版面按鈕（平時低調） -->
        <div v-else class="flex justify-end mb-1">
          <div
            @click="enterEditMode"
            class="flex items-center gap-1.5 text-xs text-gray-400 dark:text-gray-600 hover:text-indigo-500 dark:hover:text-indigo-400 transition-colors cursor-pointer py-1 px-2 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800/50"
          >
            <ViewColumnsIcon class="w-3.5 h-3.5" />
            {{ $t('layout.customize') }}
          </div>
        </div>

        <!-- 版面 Grid -->
        <VueDraggable
          v-model="layout"
          :disabled="!isEditMode"
          handle=".drag-handle"
          :animation="150"
          ghost-class="opacity-30"
          class="grid grid-cols-1 md:grid-cols-2 gap-4"
        >
          <LayoutItemWrapper
            v-for="(item, index) in layout"
            :key="item.id"
            :item="item"
            :index="index"
            :total-items="layout.length"
            :is-edit-mode="isEditMode"
            :visible="isItemVisible(item.id)"
            @move-up="moveItem(index, index - 1)"
            @move-down="moveItem(index, index + 1)"
            @toggle-col-span="toggleColSpan(item.id)"
          >
            <BossControlPanel v-if="item.id === 'controlPanel'" />
            <BossInfo v-else-if="item.id === 'bossInfo'" />
            <ChannelView v-else-if="item.id === 'channelView'" />
            <RecommendedChannels v-else-if="item.id === 'recommendedChannels'" />
            <RecordHistory v-else-if="item.id === 'recordHistory'" />
          </LayoutItemWrapper>
        </VueDraggable>
      </div>

      <!-- 右側廣告 -->
      <aside class="hidden xl:flex flex-col items-center pt-8 w-[160px] shrink-0">
        <AdBanner ad-slot="6801399498" />
      </aside>
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useRoomStore } from '@/stores/roomStore.js'
import { useBossStore } from '@/stores/bossStore.js'
import { useUserStore } from '@/stores/userStore.js'
import { useWebSocketStore } from '@/stores/websocketStore'
import ApiService from '@/services/apiService.ts'
import AppHeader from '@/components/AppHeader.vue'
import BossControlPanel from '@/components/BossControlPanel.vue'
import BossInfo from '@/components/BossInfo.vue'
import ChannelView from '@/components/ChannelView.vue'
import RecommendedChannels from '@/components/RecommendedChannels.vue'
import RecordHistory from '@/components/RecordHistory.vue'
import LayoutItemWrapper from '@/components/LayoutItemWrapper.vue'
import { showMessage } from '@/composables/useElementPlus.js'
import { useI18n } from 'vue-i18n'
import { useRecentRooms } from '@/composables/useRecentRooms'
import { useBossAlerts } from '@/composables/useBossAlerts'
import { useLayoutConfig } from '@/composables/useLayoutConfig'
import AdBanner from '@/components/AdBanner.vue'
import { VueDraggable } from 'vue-draggable-plus'
import { ViewColumnsIcon } from '@heroicons/vue/24/outline'

const { t } = useI18n()
const router = useRouter()
const roomStore = useRoomStore()
const bossStore = useBossStore()
const userStore = useUserStore()
const websocketStore = useWebSocketStore()
const { addRecentRoom } = useRecentRooms()

useBossAlerts()

const { layout, isEditMode, moveItem, toggleColSpan, enterEditMode, exitEditMode, resetLayout } = useLayoutConfig()

function isItemVisible(id) {
  if (id === 'recordHistory') {
    return userStore.user?.preferences?.showRecordHistory ?? true
  }
  return true
}

const props = defineProps({
  roomId: {
    type: String,
    required: true,
  },
})

onMounted(async () => {
  try {
    roomStore.setRoomId(props.roomId)

    const roomExistResponse = await ApiService.checkRoomExists(props.roomId)
    if (roomExistResponse.exists) {
      const types = await ApiService.getBossTypes()
      bossStore.setBossTypes(types)

      websocketStore.sendMessage({
        type: 'join_room',
        payload: { room_id: props.roomId },
      })

      addRecentRoom(props.roomId)
    } else {
      await router.push({ name: 'RoomSelection' })
      showMessage.error(t('bossTracker.roomNotFound'))
    }
  } catch (error) {
    console.error('Failed to initialize BossTracker:', error)
    await router.push({ name: 'RoomSelection' })
    showMessage.error(t('bossTracker.failedToEnter'))
  }
})

onUnmounted(() => {
  if (props.roomId) {
    websocketStore.sendMessage({
      type: 'leave_room',
      payload: { room_id: props.roomId },
    })
  }
  roomStore.setRoomId(null)
  bossStore.setBossRecords([])
})
</script>