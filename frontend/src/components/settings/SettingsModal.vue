<template>
  <el-dialog
    v-model="visible"
    :title="t('settings.title')"
    width="500px"
    :close-on-click-modal="true"
    class="settings-dialog"
  >
    <el-tabs v-model="activeTab" class="settings-tabs pr-4">
      <el-tab-pane :label="t('settings.tabs.preferences')" name="preferences">
        <SettingsPreferences :visible="visible" />
      </el-tab-pane>

      <el-tab-pane v-if="inRoom" :label="t('settings.tabs.customBoss')" name="customBoss">
        <SettingsCustomBosses />
      </el-tab-pane>

      <el-tab-pane :label="t('settings.tabs.feedback')" name="feedback" lazy>
        <SettingsFeedback />
      </el-tab-pane>

      <el-tab-pane :label="t('settings.tabs.changelog')" name="changelog">
        <SettingsChangelog />
      </el-tab-pane>

      <el-tab-pane :label="t('settings.tabs.support')" name="support">
        <SettingsSupport />
      </el-tab-pane>
    </el-tabs>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useRoomStore } from '@/stores/roomStore'
import SettingsPreferences from '@/components/settings/SettingsPreferences.vue'
import SettingsChangelog from '@/components/settings/SettingsChangelog.vue'
import SettingsSupport from '@/components/settings/SettingsSupport.vue'
import SettingsCustomBosses from '@/components/settings/SettingsCustomBosses.vue'
import SettingsFeedback from '@/components/settings/SettingsFeedback.vue'

const { t } = useI18n()
const { roomId } = storeToRefs(useRoomStore())

const visible = defineModel<boolean>({ default: false })
const activeTab = ref('preferences')
const inRoom = computed(() => !!roomId.value)
</script>