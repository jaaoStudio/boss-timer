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
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import SettingsPreferences from '@/components/SettingsPreferences.vue'
import SettingsChangelog from '@/components/SettingsChangelog.vue'
import SettingsSupport from '@/components/SettingsSupport.vue'

const { t } = useI18n()

const visible = defineModel<boolean>({ default: false })
const activeTab = ref('preferences')
</script>