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
import { useUserStore} from "@/stores/userStore.js";
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
const userStore = useUserStore()
const { roomId } = storeToRefs(roomStore)
const { connect, disconnect } = useWebSocket()

const props = defineProps({
  roomId: {
    type: String,
    required: true,
  },
})

const MAX_CONNECTIONS = 1000;

onMounted(async () => {
  try {
    const canConnect = await userStore.canEstablishWebSocket();
    if (!canConnect) {
      showMessage.error("連線數已達上限，無法進入房間。請稍後再試。");
      await router.push({name: 'RoomSelection'});
      return;
    }

    // 設定房間ID
    roomId.value = props.roomId
    const roomExistResponse = await ApiService.checkRoomExists(roomId.value)
    console.log(roomExistResponse)
    if (roomExistResponse.exists) {
      // 載入BOSS類型
      const types = await ApiService.getBossTypes()
      console.log(types)
      bossStore.setBossTypes(types)

      // 連接 WebSocket
      connect(props.roomId)

    }
  } catch (error) {
    console.error('Failed to initialize app:', error)
    await router.push({name: 'RoomSelection'})
    showMessage.error("進入房間失敗，請重新嘗試")
    if (error.status === 404){
      // await router.push({name: 'RoomSelection'})
      // showMessage.error("房間不存在")
    }
  }
})

onUnmounted(() => {
  disconnect()
})
</script>