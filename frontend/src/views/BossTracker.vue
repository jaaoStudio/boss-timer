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
      <RecordHistory v-if="userStore.user?.preferences?.showRecordHistory ?? true" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useRoomStore } from '@/stores/roomStore.js'
import { useBossStore } from '@/stores/bossStore.js'
import { useUserStore} from "@/stores/userStore.js";
import { useWebSocketStore } from '@/stores/websocketStore';
import ApiService from '@/services/apiService.ts';
import AppHeader from '@/components/AppHeader.vue';
import BossControlPanel from '@/components/BossControlPanel.vue';
import BossInfo from '@/components/BossInfo.vue';
import ChannelOverview from '@/components/ChannelOverview.vue';
import RecommendedChannels from '@/components/RecommendedChannels.vue';
import RecordHistory from '@/components/RecordHistory.vue';
import { storeToRefs } from "pinia";
import { showMessage } from "@/composables/useElementPlus.js";

const route = useRoute();
const router = useRouter();
const roomStore = useRoomStore();
const bossStore = useBossStore();
const userStore = useUserStore();
const websocketStore = useWebSocketStore();
const { roomId } = storeToRefs(roomStore);

const props = defineProps({
  roomId: {
    type: String,
    required: true,
  },
});

onMounted(async () => {
  try {
    // The global WebSocket connection is already established by App.vue
    // We just need to join the room.

    // Set room ID in the store
    roomStore.setRoomId(props.roomId);

    const roomExistResponse = await ApiService.checkRoomExists(roomId.value);
    if (roomExistResponse.exists) {
      // Load boss types
      const types = await ApiService.getBossTypes();
      bossStore.setBossTypes(types);

      // Join the room via WebSocket message
      websocketStore.sendMessage({
        type: 'join_room',
        payload: { room_id: roomId.value },
      });

    } else {
        await router.push({ name: 'RoomSelection' });
        showMessage.error("房間不存在");
    }
  } catch (error) {
    console.error('Failed to initialize BossTracker:', error);
    await router.push({ name: 'RoomSelection' });
    showMessage.error("進入房間失敗，請重新嘗試");
  }
});

onUnmounted(() => {
  // Leave the room via WebSocket message
  if (props.roomId) {
      websocketStore.sendMessage({
        type: 'leave_room',
        payload: { room_id: props.roomId },
      });
  }
  // The global WebSocket connection is NOT disconnected here.
});
</script>