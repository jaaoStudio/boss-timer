<template>
  <el-dialog
    v-model="visible"
    :title="t('settings.title')"
    width="440px"
    :close-on-click-modal="true"
    class="settings-dialog"
  >
    <!-- Discord Webhook Section -->
    <div class="mb-6">
      <h3 class="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">
        💬 Discord Webhook (房間專屬)
      </h3>
      <div class="space-y-4 pl-1">
        <div class="flex flex-col gap-2">
          <span class="text-sm text-gray-700 dark:text-gray-300">Webhook URL</span>
          <el-input
            v-model="webhookUrl"
            placeholder="https://discord.com/api/webhooks/..."
            clearable
            @change="saveWebhookSettings"
          />
        </div>
        <div class="flex flex-col gap-2 mt-2">
          <span class="text-sm text-gray-700 dark:text-gray-300">預警模式 (約 5 分鐘前通知)</span>
          <el-select v-model="webhookAlertType" @change="saveWebhookSettings">
            <el-option label="最小與最大時間 (皆通知)" value="both" />
            <el-option label="只通知最小時間" value="min" />
            <el-option label="只通知最大時間" value="max" />
            <el-option label="不預警 (只通知擊殺)" value="none" />
          </el-select>
        </div>
      </div>
    </div>

    <el-divider class="!my-4" />

    <!-- Notification Section -->
    <div class="mb-6">
      <h3 class="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">
        🔔 {{ t('settings.notificationSection') }}
      </h3>
      <div class="space-y-4 pl-1">
        <div class="flex items-center justify-between">
          <span class="text-sm text-gray-700 dark:text-gray-300">{{ t('settings.enableNotification') }}</span>
          <el-switch
            v-model="settings.notificationEnabled"
            @change="handleNotificationToggle"
            style="--el-switch-on-color: #6366f1;"
          />
        </div>
        <p v-if="permissionDenied" class="text-xs text-red-400">
          {{ t('settings.permissionDenied') }}
        </p>

        <!-- Alert timing -->
        <div v-if="settings.notificationEnabled || settings.soundEnabled" class="space-y-2 pt-1">
          <span class="text-xs text-gray-500 dark:text-gray-400">{{ t('settings.alertTiming') }}</span>
          <div class="space-y-1.5 pl-1">
            <el-checkbox v-model="settings.alertOnMinRespawn" class="!text-gray-700 dark:!text-gray-300">
              {{ t('settings.alertOnMinRespawn') }}
            </el-checkbox>
            <el-checkbox v-model="settings.alertOnMaxRespawn" class="!text-gray-700 dark:!text-gray-300">
              {{ t('settings.alertOnMaxRespawn') }}
            </el-checkbox>
          </div>
        </div>
      </div>
    </div>

    <el-divider class="!my-4" />

    <!-- Sound Section -->
    <div class="mb-2">
      <h3 class="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">
        🔊 {{ t('settings.soundSection') }}
      </h3>
      <div class="space-y-4 pl-1">
        <!-- Enable sound -->
        <div class="flex items-center justify-between">
          <span class="text-sm text-gray-700 dark:text-gray-300">{{ t('settings.enableSound') }}</span>
          <el-switch
            v-model="settings.soundEnabled"
            style="--el-switch-on-color: #6366f1;"
          />
        </div>

        <div v-if="settings.soundEnabled" class="space-y-4">
          <!-- Volume -->
          <div class="flex items-center gap-3">
            <span class="text-xs text-gray-500 dark:text-gray-400 w-8 shrink-0">{{ t('settings.volume') }}</span>
            <el-slider
              v-model="settings.soundVolume"
              :min="0"
              :max="100"
              :show-tooltip="false"
              class="flex-1"
            />
            <span class="text-xs text-gray-400 w-8 text-right">{{ settings.soundVolume }}%</span>
          </div>

          <!-- Min respawn sound (if enabled) -->
          <div v-if="settings.alertOnMinRespawn" class="p-3 rounded-lg bg-gray-50 dark:bg-gray-700/30 space-y-2.5">
            <span class="text-xs font-medium text-gray-600 dark:text-gray-300">{{ t('settings.alertOnMinRespawn') }}</span>
            <div class="flex items-center gap-2">
              <el-select v-model="settings.minRespawnSound" size="small" class="flex-1">
                <el-option value="default" :label="t('settings.soundDefault')" />
                <el-option value="gentle" :label="t('settings.soundGentle')" />
                <el-option value="urgent" :label="t('settings.soundUrgent')" />
                <el-option value="custom" :label="customMinLabel" />
              </el-select>
              <el-button size="small" @click="previewMin" :icon="VideoPlay" />
            </div>
            <div v-if="settings.minRespawnSound === 'custom'" class="flex items-center gap-2">
              <el-button size="small" @click="uploadMin">
                {{ hasCustomMin ? t('settings.changeFile') : t('settings.uploadFile') }}
              </el-button>
              <span v-if="customMinName" class="text-xs text-gray-400 truncate max-w-[180px]">{{ customMinName }}</span>
              <input ref="minFileInput" type="file" accept="audio/*" class="hidden" @change="onMinFileChange" />
            </div>
          </div>

          <!-- Max respawn sound (if enabled) -->
          <div v-if="settings.alertOnMaxRespawn" class="p-3 rounded-lg bg-gray-50 dark:bg-gray-700/30 space-y-2.5">
            <span class="text-xs font-medium text-gray-600 dark:text-gray-300">{{ t('settings.alertOnMaxRespawn') }}</span>
            <div class="flex items-center gap-2">
              <el-select v-model="settings.maxRespawnSound" size="small" class="flex-1">
                <el-option value="default" :label="t('settings.soundDefault')" />
                <el-option value="gentle" :label="t('settings.soundGentle')" />
                <el-option value="urgent" :label="t('settings.soundUrgent')" />
                <el-option value="custom" :label="customMaxLabel" />
              </el-select>
              <el-button size="small" @click="previewMax" :icon="VideoPlay" />
            </div>
            <div v-if="settings.maxRespawnSound === 'custom'" class="flex items-center gap-2">
              <el-button size="small" @click="uploadMax">
                {{ hasCustomMax ? t('settings.changeFile') : t('settings.uploadFile') }}
              </el-button>
              <span v-if="customMaxName" class="text-xs text-gray-400 truncate max-w-[180px]">{{ customMaxName }}</span>
              <input ref="maxFileInput" type="file" accept="audio/*" class="hidden" @change="onMaxFileChange" />
            </div>
          </div>
        </div>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSettings } from '@/composables/useSettings'
import { useNotification } from '@/composables/useNotification'
import { useSound } from '@/composables/useSound'
import { VideoPlay } from '@element-plus/icons-vue'
import { showMessage } from '@/composables/useElementPlus.js'
import apiService from '@/services/apiService'
import { useRoomStore } from '@/stores/roomStore'

const { t } = useI18n()
const { settings } = useSettings()
const { requestPermission } = useNotification()
const { previewSound, saveCustomSound, getCustomSound } = useSound()

const visible = defineModel<boolean>({ default: false })
const permissionDenied = ref(false)
const roomStore = useRoomStore()

// Webhook state
const webhookUrl = ref('')
const webhookAlertType = ref('both')

const loadRoomSettings = async () => {
    if (!roomStore.roomId) return
    try {
        const roomInfo = await apiService.checkRoomExists(roomStore.roomId)
        webhookUrl.value = roomInfo.discord_webhook_url || ''
        webhookAlertType.value = roomInfo.webhook_alert_type || 'both'
    } catch(e) {
        // ignore
    }
}

const saveWebhookSettings = async () => {
    if (!roomStore.roomId) return
    try {
        await apiService.updateRoomSettings(roomStore.roomId, {
            discord_webhook_url: webhookUrl.value || null,
            webhook_alert_type: webhookAlertType.value
        })
        showMessage.success('Webhook 設定已更新')
    } catch(e) {
        console.log(e)
        showMessage.error('更新失敗')
    }
}

// Custom sound state
const hasCustomMin = ref(false)
const hasCustomMax = ref(false)
const customMinName = ref('')
const customMaxName = ref('')
const minFileInput = ref<HTMLInputElement | null>(null)
const maxFileInput = ref<HTMLInputElement | null>(null)

const customMinLabel = computed(() =>
  hasCustomMin.value ? `${t('settings.soundCustom')} ✓` : t('settings.soundCustom')
)
const customMaxLabel = computed(() =>
  hasCustomMax.value ? `${t('settings.soundCustom')} ✓` : t('settings.soundCustom')
)

watch(visible, (newVal) => {
    if (newVal) {
        loadRoomSettings()
    }
})

onMounted(async () => {
  const minSound = await getCustomSound('custom-min')
  if (minSound) {
    hasCustomMin.value = true
    customMinName.value = minSound.name
  }
  const maxSound = await getCustomSound('custom-max')
  if (maxSound) {
    hasCustomMax.value = true
    customMaxName.value = maxSound.name
  }
})

async function handleNotificationToggle(val: boolean) {
  if (!val) return
  const result = await requestPermission()
  if (result === 'denied' || result === 'unsupported') {
    permissionDenied.value = true
    settings.value.notificationEnabled = false
  } else {
    permissionDenied.value = false
  }
}

function previewMin() {
  previewSound(settings.value.minRespawnSound, 'custom-min', settings.value.soundVolume)
}

function previewMax() {
  previewSound(settings.value.maxRespawnSound, 'custom-max', settings.value.soundVolume)
}

function uploadMin() { minFileInput.value?.click() }
function uploadMax() { maxFileInput.value?.click() }

async function onMinFileChange(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (file.size > 5 * 1024 * 1024) {
    showMessage.warning(t('settings.fileTooLarge'))
    return
  }
  await saveCustomSound('custom-min', file)
  hasCustomMin.value = true
  customMinName.value = file.name
  showMessage.success(t('settings.uploadSuccess'))
}

async function onMaxFileChange(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (file.size > 5 * 1024 * 1024) {
    showMessage.warning(t('settings.fileTooLarge'))
    return
  }
  await saveCustomSound('custom-max', file)
  hasCustomMax.value = true
  customMaxName.value = file.name
  showMessage.success(t('settings.uploadSuccess'))
}
</script>
