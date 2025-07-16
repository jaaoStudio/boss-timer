<template>
  <div class="bg-gray-800 rounded-lg shadow-md p-4 mb-6">
    <div class="flex items-center justify-between">
      <div class="flex items-center">
        <img src="/leaf24px.png" alt="Logo" class="h-8 w-8 mr-3">
        <div>
          <h1 class="text-2xl font-bold text-white">BOSS Timer</h1>
          <p v-if="roomId" class="text-gray-400 text-sm">Room: <span class="font-mono bg-gray-700 px-2 py-1 rounded">{{ roomId }}</span></p>
        </div>
      </div>

      <div class="flex items-center space-x-4">
        <!-- Connection Status & User Count -->
        <div v-if="roomId" class="flex items-center space-x-4">
          <div class="flex items-center space-x-2">
            <div :class="['w-3 h-3 rounded-full', isConnected ? 'bg-green-400' : 'bg-red-500']"></div>
            <span class="text-sm font-medium text-gray-300">{{ isConnected ? 'Live' : 'Offline' }}</span>
          </div>
          <div class="flex items-center space-x-2">
            <UsersIcon class="w-4 h-4 text-gray-400" />
            <span class="text-sm font-medium text-gray-300">{{ userCount }}</span>
          </div>
        </div>

        <!-- Spacer -->
        <div class="w-px h-8 bg-gray-600" v-if="roomId"></div>

        <!-- Auth Section -->
        <div v-if="!isLoggedIn">
          <GoogleLogin
            :callback="handleLoginSuccess"
            :error="handleLoginError"

            class="google-login-custom"
          />
        </div>
        <div v-else class="flex items-center space-x-3">
          <img :src="userStore.user.avatar_url" alt="User Avatar" class="w-8 h-8 rounded-full" v-if="userStore.user && userStore.user.avatar_url"/>
          <span class="text-white font-medium text-sm">{{ userStore.user.display_name }}</span>
          <button @click="handleLogout" class="bg-red-500 hover:bg-red-600 text-white px-3 py-1.5 rounded-md text-sm font-medium">Logout</button>
        </div>

        <!-- Room Manager -->
        <RoomManager v-if="roomId" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { storeToRefs } from 'pinia';
import { useRoomStore } from '@/stores/roomStore';
import { useUserStore } from '@/stores/userStore';
import { UsersIcon } from '@heroicons/vue/24/outline';
import RoomManager from '@/components/RoomManager.vue';
import {GoogleLogin} from "vue3-google-login";

const roomStore = useRoomStore();
const { roomId, isConnected, userCount } = storeToRefs(roomStore);

const userStore = useUserStore();
const { isLoggedIn } = storeToRefs(userStore)

const handleLoginSuccess = async (response) => {
  console.log("Google sign-in success:", response);
  try {
    await userStore.loginWithGoogle(response.credential);
  } catch (error) {
    console.error("Backend login failed:", error);
    // Optionally show an error message to the user
  }
};

const handleLoginError = (error) => {
  console.error("Google sign-in error:", error);
};

const handleLogout = () => {
  userStore.logout();
};
</script>
