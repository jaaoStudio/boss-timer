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
          <user-icon class="w-4 h-4 text-gray-300" />
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
import { UserIcon } from '@heroicons/vue/24/solid'
import RoomManager from '@/components/RoomManager.vue'

const roomStore = useRoomStore()
const { roomId, isConnected, userCount } = storeToRefs(roomStore)


</script>