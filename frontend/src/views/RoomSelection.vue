<template>
  <div class="flex flex-grow items-center justify-center bg-gray-900">
    <div class="w-full max-w-md p-8 space-y-6 bg-gray-800 rounded-lg shadow-md">
      <div>
        <h2 class="text-3xl font-extrabold text-center text-white">
          BOSS Timer
        </h2>
        <p class="mt-2 text-sm text-center text-gray-300">
          Create a new room or join an existing one to start tracking.
        </p>
      </div>

      <div class="space-y-4">
        <!-- 創建房間按鈕 -->
        <div>
          <button
            @click="createRoom"
            :disabled="isCreating"
            class="w-full px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-md shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
          >
            <svg v-if="isCreating" class="w-4 h-4 mr-2 animate-spin" fill="none" viewBox="0 0 24 24">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            {{ isCreating ? 'Creating Room...' : 'Create New Room' }}
          </button>
        </div>

        <!-- 分隔線 -->
        <div class="relative">
          <div class="absolute inset-0 flex items-center">
            <div class="w-full border-t border-gray-700"></div>
          </div>
          <div class="relative flex justify-center text-sm">
            <span class="px-2 text-gray-400 bg-gray-800"> Or join with a code </span>
          </div>
        </div>

        <!-- 加入房間 -->
        <div class="space-y-2">
          <div class="flex space-x-2">
            <input
              v-model="joinRoomId"
              type="text"
              placeholder="Enter room code"
              class="block w-full px-3 py-2 placeholder-gray-400 border border-gray-600 bg-gray-700 text-white rounded-md shadow-sm appearance-none focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
              @keyup.enter="joinRoom"
              @input="validateRoomId"
              :class="{ 'border-red-500': joinRoomError }"
            />
            <button
              @click="joinRoom"
              :disabled="!joinRoomId.trim() || isJoining"
              class="px-4 py-2 text-sm font-medium text-white bg-gray-600 border border-transparent rounded-md shadow-sm hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
            >
              <svg v-if="isJoining" class="w-4 h-4 mr-1 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
              {{ isJoining ? 'Joining...' : 'Join' }}
            </button>
          </div>

          <!-- 錯誤訊息 -->
          <div v-if="joinRoomError" class="text-red-400 text-sm">
            {{ joinRoomError }}
          </div>
        </div>
      </div>

      <!-- 成功訊息 -->
      <div v-if="successMessage" class="p-4 bg-green-800 bg-opacity-50 border border-green-600 rounded-md">
        <div class="flex">
          <div class="flex-shrink-0">
            <svg class="w-5 h-5 text-green-400" fill="currentColor" viewBox="0 0 20 20">
              <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd" />
            </svg>
          </div>
          <div class="ml-3">
            <p class="text-sm font-medium text-green-200">
              {{ successMessage }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useRoomStore } from '@/stores/roomStore.ts'
import ApiService from '@/services/apiService.ts'
import {storeToRefs} from "pinia";
import { showMessage } from "@/composables/useElementPlus.js";

const router = useRouter()
const roomStore = useRoomStore()
const { roomId } = storeToRefs(roomStore)

const joinRoomId = ref('')
const joinRoomError = ref('')
const successMessage = ref('')
const isCreating = ref(false)
const isJoining = ref(false)


const createRoom = async () => {
  if (isCreating.value) return

  isCreating.value = true
  successMessage.value = ''

  try {
    const response = await ApiService.createRoom()
    // console.log(response.data)
    if (response.success) {
      const newRoomId = response.room_id
      roomId.value = newRoomId

      // 顯示成功訊息
      successMessage.value = `Room ${newRoomId} created successfully!`
      // console.log(newRoomId)
      await router.push({ name: 'BossTracker', params: { roomId: newRoomId } })
    }
  } catch (error) {
    console.error('Error creating room:', error)
    showMessage.error("房間建立失敗，請稍後再試。")
  } finally {
    isCreating.value = false
  }
}

const joinRoom = async () => {
  const roomIdToJoin = joinRoomId.value.trim().toUpperCase()

  if (!roomIdToJoin) {
    joinRoomError.value = 'Please enter a room code'
    return
  }

  if (isJoining.value) return

  isJoining.value = true
  joinRoomError.value = ''
  successMessage.value = ''

  try {
    // 檢查房間是否存在
    const roomCheck = await ApiService.checkRoomExists(roomIdToJoin)

    if (roomCheck.exists) {
      roomId.value = roomIdToJoin

      // 顯示成功訊息
      successMessage.value = `Joining room ${roomIdToJoin}...`

      // 短暫延遲後跳轉
      await router.push({ name: 'BossTracker', params: { roomId: roomIdToJoin } })

    } else {
      joinRoomError.value = 'Room not found. Please check the room code.'
    }
  } catch (error) {
    console.error('Error joining room:', error)
    joinRoomError.value = 'Failed to join room. Please try again.'
  } finally {
    isJoining.value = false
  }
}
</script>
