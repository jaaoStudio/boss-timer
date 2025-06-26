<template>
  <div class="flex items-center justify-center min-h-screen bg-gray-100">
    <div class="w-full max-w-md p-8 space-y-6 bg-white rounded-lg shadow-md">
      <div>
        <h2 class="text-3xl font-extrabold text-center text-gray-900">
          BOSS Timer
        </h2>
        <p class="mt-2 text-sm text-center text-gray-600">
          Create a new room or join an existing one to start tracking.
        </p>
      </div>
      <div class="space-y-4">
        <div>
          <button
            @click="createRoom"
            class="w-full px-4 py-2 text-sm font-medium text-white bg-indigo-600 border border-transparent rounded-md shadow-sm hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
          >
            Create New Room
          </button>
        </div>
        <div class="relative">
          <div class="absolute inset-0 flex items-center">
            <div class="w-full border-t border-gray-300"></div>
          </div>
          <div class="relative flex justify-center text-sm">
            <span class="px-2 text-gray-500 bg-white"> Or join with a code </span>
          </div>
        </div>
        <div class="flex space-x-2">
          <input
            v-model="joinRoomId"
            type="text"
            placeholder="Enter room code"
            class="block w-full px-3 py-2 placeholder-gray-400 border border-gray-300 rounded-md shadow-sm appearance-none focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm"
            @keyup.enter="joinRoom"
          />
          <button
            @click="joinRoom"
            :disabled="!joinRoomId.trim()"
            class="px-4 py-2 text-sm font-medium text-white bg-gray-600 border border-transparent rounded-md shadow-sm hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Join
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useRoomStore } from '@/stores/roomStore'

const router = useRouter()
const roomStore = useRoomStore()
const joinRoomId = ref('')

const generateRoomId = (length = 6) => {
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
  let result = ''
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return result
}

const createRoom = () => {
  const newRoomId = generateRoomId()
  roomStore.setRoomId(newRoomId)
  router.push({ name: 'BossTracker', params: { roomId: newRoomId } })
}

const joinRoom = () => {
  const roomIdToJoin = joinRoomId.value.trim().toUpperCase()
  if (roomIdToJoin) {
    roomStore.setRoomId(roomIdToJoin)
    router.push({ name: 'BossTracker', params: { roomId: roomIdToJoin } })
  }
}
</script>
