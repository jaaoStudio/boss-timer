<template>
  <div class="bg-gray-800 rounded-lg shadow-md p-6 mb-6">
    <h2 class="text-xl font-semibold text-white mb-4"></h2>

    <form @submit.prevent="recordBoss" class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <!-- 頻道選擇 -->
      <div>
        <label class="block text-sm font-medium text-gray-300 mb-1">{{ t('bossControlPanel.channel') }}</label>
        <input
          v-model.number="form.channel"
          type="text"
          inputmode="numeric"
          pattern="\d*"
          class="w-full h-9 px-3 py-2 border border-gray-700 bg-gray-900 text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
          maxlength="5"
          @input="onChannelInput"
        >
      </div>

      <!-- BOSS選擇 -->
      <div>
        <label class="block text-sm font-medium text-gray-300 mb-1">{{ t('bossControlPanel.boss') }}</label>
        <select
          v-model="form.boss_type_id"
          @change="bossStore.setSelectedBossTypeId(form.boss_type_id)"
          class="w-full h-9 px-3 py-2 border border-gray-700 bg-gray-900 text-gray-200 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          required
        >
          <option :value="null">{{ t('bossControlPanel.selectBoss') }}</option>
          <option v-for="boss in bossTypes" :key="boss.id" :value="boss.id">
            {{ locale.value === 'zh' ? boss.name_zh : boss.name_en }}
          </option>
        </select>
      </div>

      <!-- 狀態選擇 -->
      <div>
        <label class="block text-sm font-medium text-gray-300 mb-1">{{ t('bossControlPanel.status') }}</label>
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
import { useRoomStore } from '@/stores/roomStore.js'
import { useBossStore } from '@/stores/bossStore.js'
import BossStatusButton from "@/components/BossStatusButton.vue";
import {showMessage} from "@/composables/useElementPlus.js";
import {useUserStore} from "@/stores/userStore.js";
import { useWebSocketStore} from "@/stores/websocketStore.js";
import { useI18n } from 'vue-i18n';

const { t, locale } = useI18n();

const roomStore = useRoomStore()
const bossStore = useBossStore()
const userStore = useUserStore();
const websocketStore = useWebSocketStore();


const { roomId } = storeToRefs(roomStore)
// Updated to use selectedBossTypeId
const { bossTypes, selectedChannel, selectedBossTypeId } = storeToRefs(bossStore)
const { isLoggedIn, anonymousId, anonymousName} = storeToRefs(userStore)

const statuses = [
  { type: 'alive' },
  { type: 'killed' },
  { type: 'not_found' }
]

const form = ref({
  channel: selectedChannel.value || '',
  boss_type_id: null, // Changed from boss_name
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

// Watch selectedBossTypeId instead of selectedBossName
watch(selectedBossTypeId, (newVal) => {
  form.value.boss_type_id = newVal
})

const loading = ref(false)

const canSubmit = computed(() => {
  return roomId.value &&
         form.value.channel &&
         form.value.boss_type_id !== null && // Check for null
         form.value.status
})

const recordBoss = async () => {
  if (!canSubmit.value) return

  loading.value = true
  try {
    const payload = {
      room_id: roomId.value,
      channel: parseInt(form.value.channel),
      boss_type_id: form.value.boss_type_id, // Send boss_type_id
      status: form.value.status,
      recorder_info: null // 預設為 null
    }

    if (!isLoggedIn.value && anonymousName.value) {
      payload.recorder_info = {
        anonymous_id: anonymousId.value,
        anonymous_name: anonymousName.value,
      };
    }

    websocketStore.sendMessage({
      type: 'record_boss',
      payload: payload,
    });

    // Reset form field
    form.value.channel = ''

  } catch (error) {
    console.error('Failed to send record boss message via WebSocket:', error);
    showMessage.error(t('bossControlPanel.sendRecordFailed'));
  } finally {
    loading.value = false
  }
}

const onChannelInput = (e) => {
    e.target.value = e.target.value.replace(/\D/g, '');
    form.value.channel = e.target.value ? parseInt(e.target.value, 10) : null;
  }

onMounted(() => {
  // Set initial value from store
  form.value.boss_type_id = selectedBossTypeId.value
})
</script>