<template>
  <div>
    <!-- Channel View Section -->
    <div class="mb-6">
      <h3 class="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider mb-3">
        {{ t('settings.channelViewSection') }}
      </h3>
      <el-radio-group v-model="channelViewModeLocal" @change="handleViewModeChange" class="pl-1">
        <el-radio value="overview">{{ t('settings.channelViewOverview') }}</el-radio>
        <el-radio value="timeline">{{ t('settings.channelViewTimeline') }}</el-radio>
      </el-radio-group>
    </div>

    <el-divider class="!my-4" />

    <!-- Discord Webhook Section -->
    <div class="mb-6">
      <div class="flex items-center justify-between mb-3">
        <div class="flex items-center gap-1.5">
          <h3 class="text-sm font-semibold text-gray-500 dark:text-gray-400 uppercase tracking-wider">
            {{ t('settings.discordWebhookSection') }}
          </h3>
          <el-tooltip :content="t('settings.webhookInfoTooltip')" placement="top">
            <el-icon class="text-gray-400 hover:text-gray-600 cursor-help"><InfoFilled /></el-icon>
          </el-tooltip>
        </div>
        <el-switch v-model="webhookEnabled" @change="saveWebhookSettings" style="--el-switch-on-color: #6366f1;" />
      </div>
      <div class="space-y-4 pl-1" v-if="webhookEnabled">
        <div class="flex flex-col gap-2">
          <span class="text-sm text-gray-700 dark:text-gray-300">{{ t('settings.webhookUrl') }}</span>
          <el-input v-model="webhookUrl" placeholder="https://discord.com/api/webhooks/..." clearable @change="saveWebhookSettings" />
          <span v-if="webhookEnabled && !webhookUrl" class="text-xs text-orange-500 mt-1">
            {{ t('settings.webhookUrlEmptyWarning') }}
          </span>
        </div>
        <div class="flex flex-col gap-2 mt-2">
          <span class="text-sm text-gray-700 dark:text-gray-300">{{ t('settings.webhookNotifyEvents') }}</span>
          <el-checkbox-group v-model="webhookNotifyEvents" @change="saveWebhookSettings">
            <el-checkbox value="killed" :label="t('settings.webhookNotifyKilled')" />
            <el-checkbox value="alive" :label="t('settings.webhookNotifyAlive')" />
            <el-checkbox value="not_found" :label="t('settings.webhookNotifyNotFound')" />
          </el-checkbox-group>
        </div>
        <div class="flex flex-col gap-2 mt-2">
          <span class="text-sm text-gray-700 dark:text-gray-300">{{ t('settings.webhookAlertMode') }}</span>
          <el-select v-model="webhookAlertType" @change="saveWebhookSettings">
            <el-option :label="t('settings.webhookAlertBoth')" value="both" />
            <el-option :label="t('settings.webhookAlertMin')" value="min" />
            <el-option :label="t('settings.webhookAlertMax')" value="max" />
            <el-option :label="t('settings.webhookAlertNone')" value="none" />
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
          <el-switch v-model="settings.notificationEnabled" @change="handleNotificationToggle" style="--el-switch-on-color: #6366f1;" />
        </div>
        <p v-if="permissionDenied" class="text-xs text-red-400">{{ t('settings.permissionDenied') }}</p>
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
        <div class="flex items-center justify-between">
          <span class="text-sm text-gray-700 dark:text-gray-300">{{ t('settings.enableSound') }}</span>
          <el-switch v-model="settings.soundEnabled" style="--el-switch-on-color: #6366f1;" />
        </div>
        <div v-if="settings.soundEnabled" class="space-y-4">
          <div class="flex items-center gap-3">
            <span class="text-xs text-gray-500 dark:text-gray-400 w-8 shrink-0">{{ t('settings.volume') }}</span>
            <el-slider v-model="settings.soundVolume" :min="0" :max="100" :show-tooltip="false" class="flex-1" />
            <span class="text-xs text-gray-400 w-8 text-right">{{ settings.soundVolume }}%</span>
          </div>
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
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSettings } from '@/composables/useSettings'
import { useNotification } from '@/composables/useNotification'
import { useSound } from '@/composables/useSound'
import { VideoPlay, InfoFilled } from '@element-plus/icons-vue'
import { showMessage } from '@/composables/useElementPlus.js'
import apiService from '@/services/apiService'
import { useRoomStore } from '@/stores/roomStore'
import { useChannelViewPreference } from '@/composables/useChannelViewPreference'

const props = defineProps<{ visible: boolean }>()

const { t } = useI18n()
const { settings } = useSettings()
const { requestPermission } = useNotification()
const { previewSound, saveCustomSound, getCustomSound } = useSound()
const { viewMode, setViewMode } = useChannelViewPreference()
const roomStore = useRoomStore()

const permissionDenied = ref(false)

// Channel view
const channelViewModeLocal = ref(viewMode.value)
watch(viewMode, (v) => { channelViewModeLocal.value = v })
async function handleViewModeChange(mode: string) {
  await setViewMode(mode as 'overview' | 'timeline')
}

// Webhook state
const webhookEnabled = ref(false)
const webhookNotifyEvents = ref<string[]>(['killed', 'alive', 'not_found'])
const webhookUrl = ref('')
const webhookAlertType = ref('none')

const loadRoomSettings = async () => {
  if (!roomStore.roomId) return
  try {
    const roomInfo = await apiService.checkRoomExists(roomStore.roomId)
    webhookEnabled.value = roomInfo.discord_webhook_enabled || false
    webhookNotifyEvents.value = roomInfo.webhook_notify_events ?? ['killed', 'alive', 'not_found']
    webhookUrl.value = roomInfo.discord_webhook_url || ''
    webhookAlertType.value = roomInfo.webhook_alert_type || 'none'
  } catch { /* ignore */ }
}

const saveWebhookSettings = async () => {
  if (!roomStore.roomId) return
  if (webhookEnabled.value && webhookUrl.value) {
    const url = webhookUrl.value.trim()
    if (!url.startsWith('https://discord.com/api/webhooks/') && !url.startsWith('https://discordapp.com/api/webhooks/')) {
      showMessage.warning(t('settings.webhookUrlInvalid'))
    }
  }
  try {
    await apiService.updateRoomSettings(roomStore.roomId, {
      discord_webhook_enabled: webhookEnabled.value,
      webhook_notify_events: webhookNotifyEvents.value,
      discord_webhook_url: webhookUrl.value ? webhookUrl.value.trim() : null,
      webhook_alert_type: webhookAlertType.value,
    })
    showMessage.success(t('settings.webhookUpdated'))
  } catch (e) {
    console.log(e)
    showMessage.error(t('settings.webhookUpdateFailed'))
  }
}

watch(() => props.visible, (val) => {
  if (val) loadRoomSettings()
})

// Notification
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

// Sound
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

onMounted(async () => {
  const minSound = await getCustomSound('custom-min')
  if (minSound) { hasCustomMin.value = true; customMinName.value = minSound.name }
  const maxSound = await getCustomSound('custom-max')
  if (maxSound) { hasCustomMax.value = true; customMaxName.value = maxSound.name }
})

function previewMin() { previewSound(settings.value.minRespawnSound, 'custom-min', settings.value.soundVolume) }
function previewMax() { previewSound(settings.value.maxRespawnSound, 'custom-max', settings.value.soundVolume) }
function uploadMin() { minFileInput.value?.click() }
function uploadMax() { maxFileInput.value?.click() }

async function onMinFileChange(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (file.size > 5 * 1024 * 1024) { showMessage.warning(t('settings.fileTooLarge')); return }
  await saveCustomSound('custom-min', file)
  hasCustomMin.value = true
  customMinName.value = file.name
  showMessage.success(t('settings.uploadSuccess'))
}

async function onMaxFileChange(event: Event) {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return
  if (file.size > 5 * 1024 * 1024) { showMessage.warning(t('settings.fileTooLarge')); return }
  await saveCustomSound('custom-max', file)
  hasCustomMax.value = true
  customMaxName.value = file.name
  showMessage.success(t('settings.uploadSuccess'))
}
</script>