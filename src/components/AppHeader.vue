<template>
  <div class="bg-white rounded-lg shadow-md p-6 mb-6">
    <div class="flex items-center justify-between">
      <div>
        <h1 class="text-3xl font-bold text-gray-800">BOSS Tracker</h1>
        <p class="text-gray-600 mt-1">Room: <span class="font-mono bg-gray-200 px-2 py-1 rounded">{{ roomStore.roomId }}</span></p>
      </div>
      <div class="flex items-center space-x-4">
        <!-- 連接狀態 -->
        <div class="flex items-center space-x-2">
          <div :class="[
            'w-3 h-3 rounded-full',
            roomStore.isConnected ? 'bg-green-500' : 'bg-red-500'
          ]"></div>
          <span class="text-sm font-medium">
            {{ roomStore.isConnected ? 'Connected' : 'Disconnected' }}
          </span>
        </div>

        <!-- 在線用戶數 -->
        <div class="flex items-center space-x-2">
          <svg class="w-5 h-5 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5 0a4 4 0 11-8 0 4 4 0 018 0z"></path>
          </svg>
          <span class="text-sm font-medium">{{ roomStore.userCount }} users online</span>
        </div>

        <!-- 房間管理 -->
        <RoomManager />
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRoomStore } from '@/stores/roomStore'
import RoomManager from '@/components/RoomManager.vue'


const roomStore = useRoomStore()


</script>