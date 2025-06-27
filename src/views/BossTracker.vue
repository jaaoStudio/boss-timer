<template>
  <div class="min-h-screen bg-gray-900">
    <div class="container mx-auto px-4 py-8">
      <!-- 標題 -->
      <AppHeader />

      <!-- 控制面板 -->
      <BossControlPanel />

      <!-- BOSS 資訊 -->
      <BossInfo />

      <!-- 頻道總覽 -->
      <ChannelOverview />

      <!-- 推薦頻道 -->
      <RecommendedChannels />

      <!-- 歷史紀錄 -->
      <RecordHistory />
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useRoomStore } from '@/stores/roomStore'
import { useBossStore } from '@/stores/bossStore'
import { useWebSocket } from '@/composables/useWebSocket'
import ApiService from '@/services/apiService.js'
import AppHeader from '@/components/AppHeader.vue'
import BossControlPanel from '@/components/BossControlPanel.vue'
import BossInfo from '@/components/BossInfo.vue'
import ChannelOverview from '@/components/ChannelOverview.vue'
import RecommendedChannels from '@/components/RecommendedChannels.vue'
import RecordHistory from '@/components/RecordHistory.vue'

const route = useRoute()
const roomStore = useRoomStore()
const bossStore = useBossStore()
const { connect, disconnect } = useWebSocket()

const props = defineProps({
  roomId: {
    type: String,
    required: true,
  },
})

onMounted(async () => {
  try {
    // 設定房間ID
    roomStore.setRoomId(props.roomId)

    // 載入BOSS類型
    const types = await ApiService.getBossTypes()
    console.log('BOSS類型:', types)
    bossStore.setBossTypes(types)

    // 連接 WebSocket
    connect(props.roomId)

  } catch (error) {
    console.error('Failed to initialize app:', error)
  }
})

onUnmounted(() => {
  disconnect()
})
</script>