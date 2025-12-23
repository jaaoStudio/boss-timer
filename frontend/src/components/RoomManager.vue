<template>
  <el-dropdown trigger="click" @command="handleCommand">

    <el-button type="primary" plain class="custom-dropdown-btn flex items-center w-36 justify-between">
      <span>{{ t('roomManager.roomActions') }}</span>
      <el-icon class="el-icon--right"><arrow-down /></el-icon>
    </el-button>

    <template #dropdown>
      <el-dropdown-menu class="custom-dropdown-menu">

        <el-dropdown-item command="copy">
          <el-icon><copy-document /></el-icon>
          {{ t('roomManager.copyRoomId') }}
        </el-dropdown-item>

        <el-dropdown-item command="language">
          <el-icon><Switch /></el-icon>
          {{ t('roomManager.toggleLanguage') }}
        </el-dropdown-item>

        <el-dropdown-item command="theme">
          <el-icon v-if="isDark"><moon /></el-icon>
          <el-icon v-else><sunny /></el-icon>
          {{ t('roomManager.toggleTheme') }}
        </el-dropdown-item>

        <el-dropdown-item v-if="isLoggedIn" class="flex justify-between items-center gap-4">
          <span class="mr-2">{{ t('roomManager.recordHistory') }}</span>
          <div @click.stop>
            <el-switch
              v-model="showRecordHistory"
              size="small"
              @change="toggleRecordHistory"
              style="--el-switch-on-color: #6b7280;"
            />
          </div>
        </el-dropdown-item>

        <el-dropdown-item divided command="leave" class="danger-text">
          <el-icon><switch-button /></el-icon>
          {{ t('roomManager.leaveRoom') }}
        </el-dropdown-item>

      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useRoomStore } from '@/stores/roomStore.js'
import { useDark, useToggle } from '@vueuse/core'
import { useUserStore } from '@/stores/userStore.js'
import { useWebSocketStore } from '@/stores/websocketStore'
import { useI18n } from 'vue-i18n'
import { ElLoading } from 'element-plus'
import { showMessage } from "@/composables/useElementPlus.js"
import { ArrowDown, CopyDocument, Moon, Sunny, Switch, SwitchButton } from '@element-plus/icons-vue'

const { t, locale } = useI18n()
const router = useRouter()
const roomStore = useRoomStore()
const userStore = useUserStore()
const websocketStore = useWebSocketStore()
const { roomId } = storeToRefs(roomStore)
const { user, isLoggedIn } = storeToRefs(userStore)

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

const showRecordHistory = ref(user.value?.preferences?.showRecordHistory ?? true)

const handleCommand = (command) => {
  switch (command) {
    case 'copy': copyRoomId(); break;
    case 'language': switchLanguage(); break;
    case 'theme': toggleDark(); break;
    case 'leave': leaveRoom(); break;
  }
}

const switchLanguage = () => {
  const newLocale = locale.value === 'en' ? 'zh' : 'en'
  locale.value = newLocale
  localStorage.setItem('language', newLocale)
}

const toggleRecordHistory = async () => {
  if (!user.value) return
  await userStore.updatePreferences({ showRecordHistory: showRecordHistory.value })
}

const copyRoomId = () => {
  navigator.clipboard.writeText(roomId.value).then(() => {
    showMessage.success(t('roomManager.copied'))
  })
}

const leaveRoom = async () => {
  const loadingInstance = ElLoading.service({
    lock: true,
    text: t('roomManager.leavingRoom'),
  })
  await new Promise(resolve => setTimeout(resolve, 500))
  if (roomStore.roomId) {
    websocketStore.sendMessage({
      type: 'leave_room',
      payload: { room_id: roomStore.roomId },
    })
  }
  roomStore.clearRoomId()
  router.push({ name: 'RoomSelection' }).finally(() => {
    loadingInstance.close()
  })
}
</script>

<style lang="scss">
/* 移除 scoped 讓暗色模式樣式能正確應用 */

/* =========================================
   按鈕樣式 - 使用 :deep() 來穿透 scoped 限制
   ========================================= */

/* 亮色模式 */
.custom-dropdown-btn {
  /* 使用 !important 確保覆蓋 Element Plus 預設樣式 */
  color: #4b5563 !important; /* gray-600 */
  border-color: #4b5563 !important;
  background-color: white !important;

  /* Hover 狀態 */
  &:hover {
    color: #374151 !important; /* gray-700 */
    background-color: #f3f4f6 !important; /* gray-100 */
    border-color: #4b5563 !important;
  }

  /* Active 和 Focus 狀態 */
  &:active,
  &:focus {
    color: white !important;
    background-color: #4b5563 !important;
    border-color: #4b5563 !important;
  }
}

/* 暗色模式 */
html.dark .custom-dropdown-btn {
  color: #9ca3af !important; /* gray-400 */
  border-color: #6b7280 !important; /* gray-500 */
  background-color: #1f2937 !important; /* gray-800 */

  &:hover {
    color: white !important;
    background-color: #4b5563 !important; /* gray-600 */
    border-color: #6b7280 !important;
  }

  &:active,
  &:focus {
    color: white !important;
    background-color: #374151 !important; /* gray-700 */
    border-color: #4b5563 !important;
  }
}

/* =========================================
   下拉選單項目樣式
   ========================================= */

/* 一般選單項目 hover 效果 */
.el-dropdown-menu__item:not(.is-disabled) {
  &:hover,
  &:focus {
    background-color: #f3f4f6 !important; /* gray-100 */
    color: #1f2937 !important; /* gray-800 */
  }
}

/* 暗色模式下的一般選單項目 */
html.dark .el-dropdown-menu__item:not(.is-disabled) {
  &:hover,
  &:focus {
    background-color: #374151 !important; /* gray-700 */
    color: #f9fafb !important; /* gray-50 */
  }
}

/* 危險操作項目 (離開房間) */
.el-dropdown-menu__item.danger-text {
  color: var(--el-color-danger) !important;

  &:hover,
  &:focus {
    color: var(--el-color-danger) !important;
    background-color: var(--el-color-danger-light-9) !important;
  }
}

/* 暗色模式下的危險項目 */
html.dark .el-dropdown-menu__item.danger-text {
  &:hover,
  &:focus {
    background-color: rgba(245, 108, 108, 0.2) !important;
  }
}
</style>