<template>
  <div class="relative flex flex-1 flex-col items-center justify-center h-full bg-gray-50 dark:bg-gray-900 p-4">
    <!-- Language Switcher -->
    <div class="absolute top-4 right-4 cursor-pointer flex items-center justify-center text-white gap-2">
      <el-icon :size="24" v-if="isDark" @click="toggleDark()">
        <moon class="text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors duration-200"/>
      </el-icon>
      <el-icon :size="24" v-else @click="toggleDark()">
        <sunny class="text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors duration-200"/>
      </el-icon>
      <LanguageIcon @click="switchLanguage" class="w-6 h-6 text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors duration-200" />
    </div>

    <div class="flex flex-col justify-center gap-5 w-full  max-w-md">
      <!-- Header -->
      <div class="text-center mb-8">
        <img src="/leaf64px.png" alt="Logo" class="h-12 w-12 mx-auto mb-4">
        <h2 class="text-3xl font-extrabold text-gray-900 dark:text-white">{{ t('roomSelection.title') }}</h2>
        <p class="mt-2 text-sm text-gray-500 dark:text-gray-400">{{ t('roomSelection.subtitle') }}</p>
      </div>

      <!-- Room Actions -->
      <div class="p-6 bg-white dark:bg-gray-800 rounded-lg shadow-md ">
        <div class="space-y-4">
          <button @click="createRoom" :disabled="isCreating" class="w-full flex justify-center items-center px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-md shadow-sm hover:!bg-gray-200 dark:hover:!bg-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50">
            <svg v-if="isCreating" class="w-5 h-5 mr-2 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
            {{ isCreating ? t('roomSelection.creatingRoom') : t('roomSelection.createRoom') }}
          </button>

          <div class="relative"><div class="absolute inset-0 flex items-center"><div class="w-full border-t border-gray-300 dark:border-gray-700"></div></div><div class="relative flex justify-center text-sm"><span class="px-2 text-gray-500 dark:text-gray-400 bg-white dark:bg-gray-800">{{ t('roomSelection.or') }}</span></div></div>

          <div class="flex space-x-2">
            <input v-model="joinRoomId"
                   type="text"
                   :placeholder="t('roomSelection.enterRoomCode')"
                   class="block w-full px-3 py-2 placeholder-gray-400 dark:placeholder-gray-500 border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-white rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                   maxlength="10"
                   @keyup.enter="joinRoom"
                   @input="joinRoomId = joinRoomId.toUpperCase()"
            />
            <button @click="joinRoom" :disabled="!joinRoomId.trim() || isJoining" class="px-4 py-2 w-24 text-sm font-medium text-white bg-gray-500 dark:bg-gray-600 rounded-md hover:bg-gray-600 dark:hover:bg-gray-700 disabled:opacity-50">
              {{ t('roomSelection.joinRoom') }}
            </button>
          </div>
          <p v-if="joinRoomError" class="text-red-400 text-sm mt-1">{{ joinRoomError }}</p>
        </div>
      </div>

      <!-- Auth Section -->
      <div class="p-6 bg-white dark:bg-gray-800 rounded-lg shadow-md">
        <div v-if="!userStore.isLoggedIn" class="text-center space-y-4">
          <div>
            <label for="anonymousName" class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">{{ t('roomSelection.anonymousNicknameLabel') }}</label>
            <input
              id="anonymousName"
              v-model="userStore.anonymousName"
              @input="userStore.setAnonymousName(event.target.value)"
              maxlength="20"
              type="text"
              :placeholder="t('roomSelection.anonymousNicknamePlaceholder')"
              class="block w-full px-3 py-2 placeholder-gray-400 dark:placeholder-gray-500 border border-gray-300 dark:border-gray-600 bg-gray-50 dark:bg-gray-900 text-gray-900 dark:text-white rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
            />
          </div>
          <div class="relative"><div class="absolute inset-0 flex items-center"><div class="w-full border-t border-gray-300 dark:border-gray-700"></div></div><div class="relative flex justify-center text-sm"><span class="px-2 text-gray-500 dark:text-gray-400 bg-white dark:bg-gray-800">{{ t('roomSelection.or') }}</span></div></div>
          <p class="text-gray-600 dark:text-gray-300 text-sm">{{ t('roomSelection.loginPrompt') }}</p>
          <GoogleLogin
            :callback="handleLoginSuccess"
            :error="handleLoginError"
            prompt
            class="google-login-custom"
          />
        </div>
        <div v-else class="flex items-center justify-center space-x-4">
          <img :src="userStore.user.avatar_url" alt="User Avatar" class="w-10 h-10 rounded-full" v-if="userStore.user && userStore.user.avatar_url"/>
          <div>
            <p class="text-gray-900 dark:text-white font-medium">{{ t('roomSelection.welcome', { name: userStore.user.display_name }) }}</p>
            <a @click="handleLogout" class="text-sm text-indigo-400 hover:text-indigo-300 cursor-pointer">{{ t('roomSelection.signOut') }}</a>
          </div>
        </div>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { useRoomStore } from '@/stores/roomStore';
import { useUserStore } from '@/stores/userStore';
import apiService from '@/services/apiService';
import { showMessage } from "@/composables/useElementPlus.js";
import { GoogleLogin } from "vue3-google-login";
import { useI18n } from 'vue-i18n';
import LanguageIcon from "@/assets/icons/LanguageIcon.vue";
import {Moon, Sunny} from "@element-plus/icons-vue";
import {useDark, useToggle} from "@vueuse/core";

const { t, locale } = useI18n();
const router = useRouter();
const roomStore = useRoomStore();
const userStore = useUserStore();

const joinRoomId = ref('');
const joinRoomError = ref('');
const isCreating = ref(false);
const isJoining = ref(false);
const isDark = useDark({
  selector: 'html',
  attribute: 'class',
  valueDark: 'dark',
  valueLight: 'light',
  onChanged(dark) {
    const html = document.documentElement
    html.setAttribute('class', dark ? 'dark' : 'light')
    html.style.colorScheme = dark ? 'dark' : 'light'
  }
})
const toggleDark = useToggle(isDark)

const switchLanguage = () => {
  const newLocale = locale.value === 'en' ? 'zh' : 'en';
  locale.value = newLocale;
  localStorage.setItem('language', newLocale);
};

// --- Auth Handlers ---
const handleLoginSuccess = async (response) => {
  try {
    await userStore.loginWithGoogle(response.credential);
    showMessage.success(t('roomSelection.toasts.loginSuccess'));
  } catch (error) {
    showMessage.error(t('roomSelection.toasts.loginFailed'));
  }
};

const handleLoginError = () => {
  showMessage.error(t('roomSelection.toasts.googleSignInFailed'));
};

const handleLogout = () => {
  userStore.logout();
  showMessage.info(t('roomSelection.toasts.logoutSuccess'));
};

// --- Room Handlers ---
const createRoom = async () => {
  if (!userStore.isLoggedIn && !userStore.anonymousName) {
    showMessage.error(t('roomSelection.errors.nicknameRequiredCreate'));
    return;
  }
  if (isCreating.value) return;

  try {
    const canConnect = await userStore.canEstablishWebSocket();
    if (!canConnect) {
      showMessage.error(t('roomSelection.errors.connectionLimit'));
      await router.push({name: 'RoomSelection'});
      return;
    }

    isCreating.value = true;
    const newRoom = await apiService.createRoom();
    roomStore.setRoomId(newRoom.room_id);
    router.push({ name: 'BossTracker', params: { roomId: newRoom.room_id } });
  } catch (error) {
    console.error('Error creating room:', error);
    showMessage.error(t('roomSelection.errors.createFailed'));
  } finally {
    isCreating.value = false;
  }
};

const joinRoom = async () => {
  if (!userStore.isLoggedIn && !userStore.anonymousName) {
    showMessage.error(t('roomSelection.errors.nicknameRequiredJoin'));
    return;
  }
  const roomIdToJoin = joinRoomId.value.trim();
  if (!roomIdToJoin) {
    joinRoomError.value = t('roomSelection.errors.enterRoomCode');
    return;
  }
  if (isJoining.value) return;

  try {
    const canConnect = await userStore.canEstablishWebSocket();
    if (!canConnect) {
      showMessage.error(t('roomSelection.errors.connectionLimit'));
      await router.push({name: 'RoomSelection'});
      return;
    }

    isJoining.value = true;
    joinRoomError.value = '';

    const roomCheck = await apiService.checkRoomExists(roomIdToJoin);
    if (roomCheck.exists) {
      roomStore.setRoomId(roomIdToJoin);
      await router.push({name: 'BossTracker', params: {roomId: roomIdToJoin}});
    }
  } catch (error) {
    console.error('Error joining room:', error);
    if(error.status === 404){
      joinRoomError.value = t('roomSelection.errors.roomNotFound');
    }
    else if(error.status === 422){
      joinRoomError.value = t('roomSelection.errors.invalidCode');
    }
    else {
      joinRoomError.value = t('roomSelection.errors.joinFailed');
    }


  } finally {
    isJoining.value = false;
  }
};

</script>