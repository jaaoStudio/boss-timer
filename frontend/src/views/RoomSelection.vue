<template>
  <div class="flex flex-col items-center justify-center h-full bg-gray-900 p-4">
    <div class="flex flex-col justify-center gap-5 w-full h-full  max-w-md">
      <!-- Header -->
      <div class="text-center mb-8 mt-40">
        <img src="/leaf64px.png" alt="Logo" class="h-12 w-12 mx-auto mb-4">
        <h2 class="text-3xl font-extrabold text-white">BOSS Timer</h2>
        <p class="mt-2 text-sm text-gray-400">Real-time boss tracking for your party.</p>
      </div>

      <!-- Room Actions -->
      <div class="p-6 bg-gray-800 rounded-lg shadow-md ">
        <div class="space-y-4">
          <button @click="createRoom" :disabled="isCreating" class="w-full flex justify-center items-center px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-md shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50">
            <svg v-if="isCreating" class="w-5 h-5 mr-2 animate-spin" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>
            {{ isCreating ? 'Creating Room...' : 'Create a New Room' }}
          </button>

          <div class="relative"><div class="absolute inset-0 flex items-center"><div class="w-full border-t border-gray-700"></div></div><div class="relative flex justify-center text-sm"><span class="px-2 text-gray-400 bg-gray-800">or</span></div></div>

          <div class="flex space-x-2">
            <input v-model="joinRoomId"
                   type="text"
                   placeholder="Enter room code"
                   class="block w-full px-3 py-2 placeholder-gray-500 border border-gray-600 bg-gray-900 text-white rounded-md focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
                   maxlength="10"
                   @keyup.enter="joinRoom"
                   @input="joinRoomId = joinRoomId.toUpperCase()"
            />
            <button @click="joinRoom" :disabled="!joinRoomId.trim() || isJoining" class="px-4 py-2 text-sm font-medium text-white bg-gray-600 rounded-md hover:bg-gray-700 disabled:opacity-50">
              Join
            </button>
          </div>
          <p v-if="joinRoomError" class="text-red-400 text-sm mt-1">{{ joinRoomError }}</p>
        </div>
      </div>

      <!-- Auth Section -->
      <div class="p-6 bg-gray-800 rounded-lg shadow-md">
        <div v-if="!userStore.isLoggedIn" class="text-center">
          <p class="text-gray-300 text-sm pb-3">Sign in to sync your settings and history.</p>
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
            <p class="text-white font-medium">Welcome, {{ userStore.user.display_name }}!</p>
            <a @click="handleLogout" class="text-sm text-indigo-400 hover:text-indigo-300 cursor-pointer">Not you? Sign out</a>
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
import {GoogleLogin} from "vue3-google-login";

const router = useRouter();
const roomStore = useRoomStore();
const userStore = useUserStore();

const joinRoomId = ref('');
const joinRoomError = ref('');
const isCreating = ref(false);
const isJoining = ref(false);

// --- Auth Handlers ---
const handleLoginSuccess = async (response) => {
  try {
    await userStore.loginWithGoogle(response.credential);
    console.log(response);
    showMessage.success("Login successful!");
  } catch (error) {
    showMessage.error("Login failed. Please try again.");
  }
};

const handleLoginError = () => {
  showMessage.error("Google sign-in failed.");
};

const handleLogout = () => {
  userStore.logout();
  showMessage.info("You have been logged out.");
};

// --- Room Handlers ---
const createRoom = async () => {
  if (isCreating.value) return;
  isCreating.value = true;
  try {
    const newRoom = await apiService.createRoom();
    roomStore.setRoomId(newRoom.room_id);
    router.push({ name: 'BossTracker', params: { roomId: newRoom.room_id } });
  } catch (error) {
    console.error('Error creating room:', error);
    showMessage.error("Failed to create room. Please try again.");
  } finally {
    isCreating.value = false;
  }
};

const joinRoom = async () => {
  const roomIdToJoin = joinRoomId.value.trim();
  if (!roomIdToJoin) {
    joinRoomError.value = 'Please enter a room code.';
    return;
  }
  if (isJoining.value) return;

  isJoining.value = true;
  joinRoomError.value = '';

  try {
    const roomCheck = await apiService.checkRoomExists(roomIdToJoin);
    if (roomCheck.detail.exists) {
      roomStore.setRoomId(roomIdToJoin);
      await router.push({name: 'BossTracker', params: {roomId: roomIdToJoin}});
    }
  } catch (error) {
    console.error('Error joining room:', error);
    if(error.status === 404){
      joinRoomError.value = 'Room not found. Please check the code.';
    }
    else if(error.status === 422){
      joinRoomError.value = "Room code is invalid. Please check the code.";
    }
    else {
      joinRoomError.value = 'Failed to join room. Please try again.';
    }


  } finally {
    isJoining.value = false;
  }
};
</script>