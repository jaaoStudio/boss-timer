<template>
  <div class="relative">
    <button @click="toggleDropdown" class="flex items-center space-x-2 px-3 py-2 bg-gray-700 text-gray-200 rounded-md hover:bg-gray-600 focus:outline-none">
      <span class="text-sm font-medium">{{ t('roomManager.roomActions') }}</span>
      <svg class="w-4 h-4 text-gray-200" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
    </button>

    <div v-if="isDropdownOpen" class="absolute right-0 mt-2 w-48 bg-gray-700 rounded-md shadow-lg z-10 text-left">
      <a @click.prevent="copyRoomId" href="#" class="block px-4 py-2 text-sm text-gray-200 hover:bg-gray-600">{{ t('roomManager.copyRoomId') }}</a>
      <a @click.prevent="switchLanguage" href="#" class="block px-4 py-2 text-sm text-gray-200 hover:bg-gray-600">{{ t('roomManager.toggleLanguage') }}</a>
      <a @click.prevent="toggleDark()" href="#" class="block px-4 py-2 text-sm text-red-400 hover:bg-gray-600">{{ t('roomManager.toggleTheme') }}</a>
      <a class="flex items-center justify-between px-4 py-2 text-sm text-red-400 hover:bg-gray-600" v-show="isLoggedIn">
        <div class="cursor-default">{{ t('roomManager.recordHistory') }}</div>
        <el-switch
          v-model="showRecordHistory"
          @change="toggleRecordHistory"
          style="--el-switch-on-color: #3b82f6;"
        />
      </a>
      <a @click.prevent="leaveRoom" href="#" class="block px-4 py-2 text-sm text-red-400 hover:bg-gray-600">{{ t('roomManager.leaveRoom') }}</a>

    </div>
    <div v-if="showCopySuccess" class="absolute right-0 -bottom-8 px-3 py-1 bg-green-500 text-white text-xs rounded-md">
      {{ t('roomManager.copied') }}
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useRoomStore } from '@/stores/roomStore.js'
import { useDark, useToggle } from '@vueuse/core'
import { useUserStore } from '@/stores/userStore.js'
import { useWebSocketStore } from '@/stores/websocketStore';
import { useI18n } from 'vue-i18n';
import { ElLoading } from 'element-plus';
import {showMessage} from "@/composables/useElementPlus.js";

const { t, locale } = useI18n();

const isDark = useDark({
  selector: 'html',
  attribute: 'color-scheme',
  valueDark: 'dark',
  valueLight: 'light',
})
const toggleDark = useToggle(isDark)

const router = useRouter()
const roomStore = useRoomStore()
const userStore = useUserStore()
const websocketStore = useWebSocketStore()

const { roomId } = storeToRefs(roomStore)
const { user, isLoggedIn } = storeToRefs(userStore)

const isDropdownOpen = ref(false)
const showCopySuccess = ref(false)

const showRecordHistory = ref(user.value?.preferences?.showRecordHistory ?? true)

const switchLanguage = () => {
  const newLocale = locale.value === 'en' ? 'zh' : 'en';
  locale.value = newLocale;
  localStorage.setItem('language', newLocale);
  isDropdownOpen.value = false; // Close dropdown after selection
};

const toggleRecordHistory = async () => {
  if (!user.value) return;
  await userStore.updatePreferences({ showRecordHistory: showRecordHistory.value });
}

const toggleDropdown = () => {
  isDropdownOpen.value = !isDropdownOpen.value
}

const copyRoomId = () => {
  navigator.clipboard.writeText(roomId.value).then(() => {
  showMessage.success(t('roomManager.copied'))
  isDropdownOpen.value = false
  })
}

const leaveRoom = async () => {
  const loadingInstance = ElLoading.service({
    lock: true,
    text: t('roomManager.leavingRoom'),
    background: 'rgba(0, 0, 0, 0.7)',
  });

  // Simulate a delay to ensure the user sees the loading state
  await new Promise(resolve => setTimeout(resolve, 500));

  if (roomStore.roomId) {
    websocketStore.sendMessage({
      type: 'leave_room',
      payload: { room_id: roomStore.roomId },
    });
  }
  roomStore.clearRoomId();
  router.push({ name: 'RoomSelection' }).finally(() => {
    loadingInstance.close();
  });
};
</script>
