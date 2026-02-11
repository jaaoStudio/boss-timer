<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow-md p-4 mb-6">
    <div class="flex flex-col sm:flex-row items-center sm:justify-between gap-y-4 sm:gap-x-2.5">
      <div class="flex flex-row sm:flex-col items-center gap-2.5 sm:gap-x-4">
        <div class="flex items-center">
          <img src="/leaf24px.png" alt="Logo" class="h-8 w-8 mr-3">
          <h1 class=" text-2xl sm:block hidden font-bold text-gray-900 dark:text-white">{{ t('appHeader.title') }}</h1>
        </div>
        <div v-if="roomId" class="cursor-pointer" @click="copyRoomId">
          <p class="text-gray-500 dark:text-gray-400 text-sm">{{ t('appHeader.room') }} <span class="font-mono bg-gray-100 dark:bg-gray-700 px-2 py-1 rounded">{{ roomId }}</span></p>
        </div>
      </div>

      <div class="flex flex-wrap items-center justify-center sm:justify-end gap-2 sm:gap-x-4">
        <!-- Connection Status & User Count -->
        <div v-if="roomId" class="flex items-center space-x-4">
          <div class="flex items-center space-x-2">
            <div :class="['w-3 h-3 rounded-full', isConnected ? 'bg-green-400' : 'bg-red-500']"></div>
            <span class="text-sm font-medium text-gray-700 dark:text-gray-300">{{ isConnected ? t('appHeader.live') : t('appHeader.offline') }}</span>
          </div>
          <div class="flex items-center space-x-2">
            <UsersIcon class="w-4 h-4 text-gray-400" />
            <span class="text-sm font-medium text-gray-700 dark:text-gray-300">{{ userCount }}</span>
          </div>
        </div>

        <!-- Auth Section -->
        <div v-if="!isLoggedIn" class="dark:p-[1px] dark:rounded-[4px] dark:border border-gray-600 flex items-center min-h-[40px]">
          <GoogleLogin
            v-if="showGoogleButton"
            :callback="handleLoginSuccess"
            :error="handleLoginError"
            :buttonConfig="googleButtonConfig"
          />
        </div>
        <div v-else class="flex items-center space-x-3">
          <img :src="userStore.user?.avatar_url" alt="User Avatar" class="w-8 h-8 rounded-full" v-if="userStore.user && userStore.user.avatar_url"/>
          <span class="text-gray-900 dark:text-white font-medium text-sm">{{ userStore.user?.display_name }}</span>
        </div>

        <!-- Room Manager -->
        <RoomManager v-if="roomId" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { storeToRefs } from 'pinia'
import { useRoomStore } from '@/stores/roomStore'
import { useUserStore } from '@/stores/userStore'
import { UsersIcon } from '@heroicons/vue/24/outline'
import RoomManager from '@/components/RoomManager.vue'
import { GoogleLogin } from "vue3-google-login"
import { showMessage } from "@/composables/useElementPlus"
import { useI18n } from "vue-i18n"
import { computed, ref, watch, nextTick, onMounted } from 'vue'
import { isDark } from '@/composables/useTheme'

const { t } = useI18n()

// Initialize as false to prevent rendering before theme is ready (avoids white flash in prod)
const showGoogleButton = ref(false)

const googleButtonConfig = computed(() => ({
  type: 'standard',
  size: 'medium',
  theme: isDark.value ? 'filled_black' : 'outline',
}))

watch(isDark, async () => {
  // 1. Remove button to force re-render with new theme config
  showGoogleButton.value = false

  // 2. Wait for DOM update
  await nextTick()

  // 3. Add button back
  showGoogleButton.value = true
})

const roomStore = useRoomStore()
const { roomId, isConnected, userCount } = storeToRefs(roomStore)

const userStore = useUserStore()
const { isLoggedIn } = storeToRefs(userStore)

const handleLoginSuccess = async (response: any) => {
  // console.log("Google sign-in success:", response);
  try {
    await userStore.loginWithGoogle(response.credential)
  } catch (error) {
    console.error("Backend login failed:", error)
  }
}

const handleLoginError = (error: any) => {
  console.error("Google sign-in error:", error)
  showMessage.error(t('appHeader.loginFailed'))
}

const copyRoomId = () => {
  if (!roomId.value) return
  navigator.clipboard.writeText(roomId.value).then(() => {
    showMessage.success(t('roomManager.copied'))
  })
}

onMounted(() => {
  // Delay showing the button slightly to ensure 'isDark' and hydration are settled
  // This helps avoid the case where isDark is undefined/false initially in prod
  nextTick(() => {
     showGoogleButton.value = true
  })
})
</script>
