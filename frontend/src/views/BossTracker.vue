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
import { useRoute, useRouter } from 'vue-router'
import { useRoomStore } from '@/stores/roomStore.js'
import { useBossStore } from '@/stores/bossStore.js'
import { useWebSocket } from '@/composables/useWebSocket'
import ApiService from '@/services/apiService.ts'
import AppHeader from '@/components/AppHeader.vue'
import BossControlPanel from '@/components/BossControlPanel.vue'
import BossInfo from '@/components/BossInfo.vue'
import ChannelOverview from '@/components/ChannelOverview.vue'
import RecommendedChannels from '@/components/RecommendedChannels.vue'
import RecordHistory from '@/components/RecordHistory.vue'
import {storeToRefs} from "pinia";
import {showMessage} from "@/composables/useElementPlus.js";

const route = useRoute()
const router = useRouter()
const roomStore = useRoomStore()
const bossStore = useBossStore()
const { roomId } = storeToRefs(roomStore)
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
    roomId.value = props.roomId
    const roomExistResponse = await ApiService.checkRoomExists(roomId.value)
    if (roomExistResponse.data.exists) {
      // 載入BOSS類型
      const types = await ApiService.getBossTypes()
      bossStore.setBossTypes(types.data)

      // 連接 WebSocket
      connect(props.roomId)

    }
  } catch (error) {
    // console.error('Failed to initialize app:', error)
    if (error.status === 404){
      await router.push({name: 'RoomSelection'})
      showMessage.error("房間不存在")
    }
  }
})

onUnmounted(() => {
  disconnect()
})
</script>