<template>
  <div class="min-h-screen bg-white dark:bg-gray-900">
    <div class="flex justify-center">
      <!-- 左側廣告 -->
      <aside class="hidden xl:flex flex-col items-center pt-8 w-[160px] shrink-0">
        <AdBanner ad-slot="6801399498" />
      </aside>

      <!-- 主內容 -->
      <div class="flex-1 min-w-0 max-w-5xl px-4 py-8 gap-2">
        <AppHeader />

        <!-- 編輯模式工具列 -->
        <EditModeToolbar
          :is-edit-mode="isEditMode"
          @enter="enterEditMode"
          @exit="exitEditMode"
          @reset="resetLayout"
        />

        <!-- 版面 Grid -->
        <VueDraggable
          v-model="layout"
          :disabled="!isEditMode"
          handle=".drag-handle"
          :animation="150"
          ghost-class="opacity-30"
          class="grid grid-cols-1 md:grid-cols-4 gap-6"
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
            @increase-col-span="increaseColSpan(item.id)"
            @decrease-col-span="decreaseColSpan(item.id)"
            @toggle-collapsed="toggleCollapsed(item.id)"
          >
            <BossControlPanel v-if="item.id === 'controlPanel'" :col-span="item.colSpan" />
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

<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useRouter } from 'vue-router'
import { useUserStore } from '@/stores/userStore'
import { useWebSocketStore } from '@/stores/websocketStore'
import AppHeader from '@/components/AppHeader.vue'
import BossControlPanel from '@/components/boss/BossControlPanel.vue'
import BossInfo from '@/components/boss/BossInfo.vue'
import ChannelView from '@/components/channel/ChannelView.vue'
import RecommendedChannels from '@/components/channel/RecommendedChannels.vue'
import RecordHistory from '@/components/record/RecordHistory.vue'
import LayoutItemWrapper from '@/components/layout/LayoutItemWrapper.vue'
import EditModeToolbar from '@/components/layout/EditModeToolbar.vue'
import { showMessage } from '@/composables/useElementPlus'
import { useI18n } from 'vue-i18n'
import { useBossAlerts } from '@/composables/useBossAlerts'
import { useLayoutConfig } from '@/composables/useLayoutConfig'
import { useRoomSession, RoomNotFoundError } from '@/composables/useRoomSession'
import AdBanner from '@/components/ui/AdBanner.vue'
import { VueDraggable } from 'vue-draggable-plus'

const { t } = useI18n()
const router = useRouter()
const userStore = useUserStore()
const websocketStore = useWebSocketStore()
const { isMaxReconnectReached } = storeToRefs(websocketStore)
const { enter, leave } = useRoomSession()

watch(isMaxReconnectReached, (reached) => {
  if (reached) {
    router.push({ name: 'RoomSelection' })
    showMessage.error(t('bossTracker.connectionLost'))
  }
})

useBossAlerts()

const { layout, isEditMode, moveItem, increaseColSpan, decreaseColSpan, toggleCollapsed, enterEditMode, exitEditMode, resetLayout } = useLayoutConfig()

function isItemVisible(id: string): boolean {
  if (id === 'recordHistory') {
    return (userStore.user?.preferences?.showRecordHistory as boolean) ?? true
  }
  return true
}

const props = defineProps<{ roomId: string }>()

onMounted(async () => {
  try {
    await enter(props.roomId)
  } catch (error) {
    await router.push({ name: 'RoomSelection' })
    showMessage.error(
      error instanceof RoomNotFoundError
        ? t('bossTracker.roomNotFound')
        : t('bossTracker.failedToEnter')
    )
  }
})

onUnmounted(() => {
  leave()
})
</script>