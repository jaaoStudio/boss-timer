<template>
  <el-dropdown trigger="click" @command="handleCommand">

    <el-button type="primary" plain class="flex items-center justify-between w-36 !text-gray-600 dark:!text-gray-400 !bg-white dark:!bg-gray-800 !border-gray-300 dark:!border-gray-600 hover:!bg-gray-50 dark:hover:!bg-gray-700">
      <span>{{ t('roomManager.roomActions') }}</span>
      <el-icon class="el-icon--right"><arrow-down /></el-icon>
    </el-button>

    <template #dropdown>
      <el-dropdown-menu>

        <el-dropdown-item command="copy" class="hover:!bg-gray-100 dark:hover:!bg-gray-700 dark:!text-gray-200">
          <el-icon><copy-document /></el-icon>
          {{ t('roomManager.copyRoomId') }}
        </el-dropdown-item>

        <el-dropdown-item command="language" class="hover:!bg-gray-100 dark:hover:!bg-gray-700 dark:!text-gray-200">
          <el-icon><Switch /></el-icon>
          {{ t('roomManager.toggleLanguage') }}
        </el-dropdown-item>

        <el-dropdown-item command="theme" class="hover:!bg-gray-100 dark:hover:!bg-gray-700 dark:!text-gray-200">
          <el-icon v-if="isDark"><moon /></el-icon>
          <el-icon v-else><sunny /></el-icon>
          {{ t('roomManager.toggleTheme') }}
        </el-dropdown-item>

        <el-dropdown-item v-if="isLoggedIn" class="flex justify-between items-center gap-4 hover:!bg-gray-100 dark:hover:!bg-gray-700 dark:!text-gray-200">
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

        <el-dropdown-item command="settings" class="hover:!bg-gray-100 dark:hover:!bg-gray-700 dark:!text-gray-200">
          <el-icon><setting /></el-icon>
          {{ t('roomManager.settings') }}
        </el-dropdown-item>

        <el-dropdown-item divided command="leave" class="!text-red-500 hover:!bg-red-50 dark:hover:!bg-red-900/20">
          <el-icon><switch-button /></el-icon>
          {{ t('roomManager.leaveRoom') }}
        </el-dropdown-item>

      </el-dropdown-menu>
    </template>
  </el-dropdown>

  <SettingsModal v-model="showSettings" />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import SettingsModal from '@/components/SettingsModal.vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useRoomStore } from '@/stores/roomStore.js'
import { isDark, toggleDark } from '@/composables/useTheme.js'
import { useUserStore } from '@/stores/userStore.js'
import { useI18n } from 'vue-i18n'
import { ElLoading } from 'element-plus'
import { showMessage } from "@/composables/useElementPlus.js"
import { ArrowDown, CopyDocument, Moon, Sunny, Switch, SwitchButton, Setting } from '@element-plus/icons-vue'

const { t, locale } = useI18n()
const router = useRouter()
const roomStore = useRoomStore()
const userStore = useUserStore()
const { roomId } = storeToRefs(roomStore)
const { user, isLoggedIn } = storeToRefs(userStore)

const showRecordHistory = ref(user.value?.preferences?.showRecordHistory ?? true)
const showSettings = ref(false)

const handleCommand = (command: string) => {
  switch (command) {
    case 'copy': copyRoomId(); break;
    case 'language': switchLanguage(); break;
    case 'theme': toggleDark(); break;
    case 'settings': showSettings.value = true; break;
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
  if (!roomId.value) return
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

  roomStore.leaveRoomAction()

  router.push({ name: 'RoomSelection' }).finally(() => {
    loadingInstance.close()
  })
}
</script>