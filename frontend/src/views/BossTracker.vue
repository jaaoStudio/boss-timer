<template>
  <div class="min-h-screen bg-white dark:bg-gray-900">
    <div class="container mx-auto px-4 py-8">
      <!-- 標題 -->
      <AppHeader />

      <!-- 控制面板 -->
      <BossControlPanel />

      <!-- BOSS 資訊 -->
      <BossInfo />

      <!-- 頻道總覽 / 時間軸 -->
      <ChannelView />

      <!-- 推薦頻道 -->
      <RecommendedChannels />

      <!-- 歷史紀錄 -->
      <RecordHistory v-if="userStore.user?.preferences?.showRecordHistory ?? true" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useRoomStore } from '@/stores/roomStore.js'
import { useBossStore } from '@/stores/bossStore.js'
import { useUserStore} from "@/stores/userStore.js";
import { useWebSocketStore } from '@/stores/websocketStore';
import ApiService from '@/services/apiService.ts';
import AppHeader from '@/components/AppHeader.vue';
import BossControlPanel from '@/components/BossControlPanel.vue';
import BossInfo from '@/components/BossInfo.vue';
import ChannelView from '@/components/ChannelView.vue';
import RecommendedChannels from '@/components/RecommendedChannels.vue';
import RecordHistory from '@/components/RecordHistory.vue';
import { showMessage } from "@/composables/useElementPlus.js";
import { useI18n } from "vue-i18n";
import { useRecentRooms } from '@/composables/useRecentRooms';
import { useBossAlerts } from '@/composables/useBossAlerts';

const { t } = useI18n();
const router = useRouter();
const roomStore = useRoomStore();
const bossStore = useBossStore();
const userStore = useUserStore();
const websocketStore = useWebSocketStore();
const { addRecentRoom } = useRecentRooms();

// Activate boss alert system (notifications + sounds)
useBossAlerts();


const props = defineProps({
  roomId: {
    type: String,
    required: true,
  },
});

onMounted(async () => {
  try {
    roomStore.setRoomId(props.roomId);

    const roomExistResponse = await ApiService.checkRoomExists(props.roomId);
    if (roomExistResponse.exists) {
      // Load boss types
      const types = await ApiService.getBossTypes();
      bossStore.setBossTypes(types);

      // Join the room via WebSocket message
      // The message will be queued if the connection is not ready yet.
      websocketStore.sendMessage({
        type: 'join_room',
        payload: { room_id: props.roomId },
      });

      // Save to recent rooms
      addRecentRoom(props.roomId);

    } else {
        await router.push({ name: 'RoomSelection' });
        showMessage.error(t('bossTracker.roomNotFound'));
    }
  } catch (error) {
    console.error('Failed to initialize BossTracker:', error);
    await router.push({ name: 'RoomSelection' });
    showMessage.error(t('bossTracker.failedToEnter'));
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
  // Reset room-specific data
  roomStore.setRoomId(null);
  bossStore.setBossRecords([]);
});
</script>