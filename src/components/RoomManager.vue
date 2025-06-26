<template>
  <div class="relative">
    <button @click="toggleDropdown" class="flex items-center space-x-2 px-3 py-2 bg-gray-200 text-gray-700 rounded-md hover:bg-gray-300 focus:outline-none">
      <span class="text-sm font-medium">Room Actions</span>
      <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg>
    </button>

    <div v-if="isDropdownOpen" class="absolute right-0 mt-2 w-48 bg-white rounded-md shadow-lg z-10">
      <a @click.prevent="copyRoomId" href="#" class="block px-4 py-2 text-sm text-gray-700 hover:bg-gray-100">Copy Room ID</a>
      <a @click.prevent="leaveRoom" href="#" class="block px-4 py-2 text-sm text-red-600 hover:bg-gray-100">Leave Room</a>
    </div>
    <div v-if="showCopySuccess" class="absolute right-0 -bottom-8 px-3 py-1 bg-green-500 text-white text-xs rounded-md">
      Copied!
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useRoomStore } from '@/stores/roomStore'
import { useWebSocket } from '@/composables/useWebSocket'

const router = useRouter()
const roomStore = useRoomStore()
const { disconnect } = useWebSocket()

const isDropdownOpen = ref(false)
const showCopySuccess = ref(false)

const toggleDropdown = () => {
  isDropdownOpen.value = !isDropdownOpen.value
}

const copyRoomId = () => {
  navigator.clipboard.writeText(roomStore.roomId).then(() => {
    showCopySuccess.value = true
    setTimeout(() => {
      showCopySuccess.value = false
    }, 2000)
  })
  isDropdownOpen.value = false
}

const leaveRoom = () => {
  disconnect()
  roomStore.clearRoomId()
  router.push({ name: 'RoomSelection' })
}
</script>
