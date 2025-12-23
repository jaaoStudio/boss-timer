<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 mb-6">
    <h2 class="text-xl font-semibold text-gray-900 dark:text-white mb-4"></h2>

    <el-form
      :model="form"
      @submit.prevent="recordBoss"
      label-position="top"
      class="grid grid-cols-1 md:grid-cols-3 gap-4"
    >

      <el-form-item :label="t('bossControlPanel.channel')">
        <el-input
          v-model="form.channel"
          :placeholder="t('bossControlPanel.channel')"
          @input="onChannelInput"
          clearable
          :maxlength="5"
        >
          </el-input>
      </el-form-item>

      <el-form-item :label="t('bossControlPanel.boss')">
        <el-select
          v-model="form.boss_type_id"
          :placeholder="t('bossControlPanel.selectBoss')"
          @change="bossStore.setSelectedBossTypeId(form.boss_type_id)"
          filterable
          clearable
          class="w-full"
        >
          <el-option
            v-for="boss in bossTypes"
            :key="boss.id"
            :label="locale === 'zh' ? boss.name_zh : boss.name_en"
            :value="boss.id"
          />
        </el-select>
      </el-form-item>

      <el-form-item :label="t('bossControlPanel.status')">
        <div class="flex gap-2 w-full">
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
      </el-form-item>

    </el-form>
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
const { bossTypes, selectedChannel, selectedBossTypeId } = storeToRefs(bossStore)
const { isLoggedIn, anonymousId, anonymousName} = storeToRefs(userStore)

const statuses = [
  { type: 'alive' },
  { type: 'killed' },
  { type: 'not_found' }
]

const form = ref({
  channel: selectedChannel.value || '',
  boss_type_id: null,
  status: ''
})

const onSelectStatus = async (statusType) => {
  if (loading.value) return;
  form.value.status = statusType;
  await recordBoss();
}

watch(selectedChannel, (newVal) => {
  form.value.channel = newVal
})

watch(selectedBossTypeId, (newVal) => {
  form.value.boss_type_id = newVal
})

const loading = ref(false)

const canSubmit = computed(() => {
  return roomId.value &&
         form.value.channel &&
         form.value.boss_type_id !== null &&
         form.value.status
})

const recordBoss = async () => {
  if (!canSubmit.value) return

  loading.value = true
  try {
    const payload = {
      room_id: roomId.value,
      channel: parseInt(form.value.channel),
      boss_type_id: form.value.boss_type_id,
      status: form.value.status,
      recorder_info: null
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

    // Reset form field (channel) only if desired, or keep logic as is
    form.value.channel = ''

  } catch (error) {
    console.error('Failed to send record boss message via WebSocket:', error);
    showMessage.error(t('bossControlPanel.sendRecordFailed'));
  } finally {
    loading.value = false
  }
}

// 修改: Element Plus 的 @input 傳遞的是 value 字串，不是 event 物件
const onChannelInput = (value) => {
    // 確保 value 是字串再進行 replace，避免 null/undefined 報錯
    if (!value) {
        form.value.channel = '';
        return;
    }
    const sanitized = value.toString().replace(/\D/g, '');
    form.value.channel = sanitized ? parseInt(sanitized, 10) : '';
}

onMounted(() => {
  form.value.boss_type_id = selectedBossTypeId.value
})
</script>

<style scoped>
</style>