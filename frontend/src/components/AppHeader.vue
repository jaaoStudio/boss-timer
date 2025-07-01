<template>
  <div class="bg-gray-800 rounded-lg shadow-md p-6 mb-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-3xl font-bold text-white">BOSS Tracker</h1>
        <p class="text-gray-300 mt-1">Room: <span class="font-mono bg-gray-700 text-gray-200 px-2 py-1 rounded">{{ roomId }}</span></p>
      </div>
      <div class="flex items-center space-x-4">
        <!-- 連接狀態 -->
        <div class="flex items-center space-x-2">
          <div :class="[
            'w-3 h-3 rounded-full',
            isConnected ? 'bg-green-500' : 'bg-red-500'
          ]"></div>
          <span class="text-sm font-medium text-gray-300">
            {{ isConnected ? 'Connected' : 'Disconnected' }}
          </span>
        </div>

        <!-- 在線用戶數 -->
        <div class="flex items-center space-x-2">
          <svg class="w-5 h-5 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5 0a4 4 0 11-8 0 4 4 0 018 0z"></path>
          </svg>
          <span class="text-sm font-medium text-gray-300">{{ userCount }} users online</span>
        </div>

        <!-- 房間管理 -->
        <RoomManager />
      </div>
    </div>
  </div>
</template>

<script setup>
import { storeToRefs } from 'pinia'
import { useRoomStore } from '@/stores/roomStore'
import RoomManager from '@/components/RoomManager.vue'

const roomStore = useRoomStore()
const { roomId, isConnected, userCount } = storeToRefs(roomStore)


</script>