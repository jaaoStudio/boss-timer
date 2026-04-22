<template>
  <div class="space-y-4">
    <!-- 新增自訂 Boss 表單 -->
    <div class="border border-gray-200 dark:border-gray-700 rounded-lg p-4 space-y-3">
      <p class="text-sm font-medium text-gray-700 dark:text-gray-300">{{ t('settings.customBoss.addTitle') }}</p>

      <el-input
        v-model="form.name"
        :placeholder="t('settings.customBoss.namePlaceholder')"
        maxlength="50"
        show-word-limit
      />

      <div class="grid grid-cols-2 gap-2">
        <el-input
          v-model.number="form.min_respawn_minutes"
          :placeholder="t('settings.customBoss.minRespawn')"
          type="number"
          :min="1"
        />
        <el-input
          v-model.number="form.max_respawn_minutes"
          :placeholder="t('settings.customBoss.maxRespawn')"
          type="number"
          :min="1"
        />
      </div>

      <el-button
        type="primary"
        :loading="adding"
        :disabled="!canAdd"
        class="w-full"
        @click="addBoss"
      >
        {{ t('settings.customBoss.add') }}
      </el-button>
    </div>

    <!-- 現有自訂 Boss 列表 -->
    <div v-if="customBossTypes.length" class="space-y-2">
      <p class="text-sm font-medium text-gray-700 dark:text-gray-300">{{ t('settings.customBoss.existing') }}</p>
      <div
        v-for="boss in customBossTypes"
        :key="boss.id"
        class="flex items-center justify-between bg-gray-50 dark:bg-gray-700 rounded-lg px-3 py-2"
      >
        <div>
          <span class="text-sm font-medium text-gray-800 dark:text-gray-200">{{ boss.name_zh }}</span>
          <span class="text-xs text-gray-500 dark:text-gray-400 ml-2">
            {{ boss.min_respawn_minutes }}~{{ boss.max_respawn_minutes }} {{ t('bossInfo.minutes') }}
          </span>
        </div>
        <el-button
          type="danger"
          size="small"
          text
          :loading="deletingId === boss.id"
          @click="deleteBoss(boss.id)"
        >
          {{ t('settings.customBoss.delete') }}
        </el-button>
      </div>
    </div>

    <p v-else class="text-sm text-gray-400 dark:text-gray-500 text-center py-2">
      {{ t('settings.customBoss.empty') }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useBossStore } from '@/stores/bossStore'
import { useRoomStore } from '@/stores/roomStore'
import { showMessage } from '@/composables/useElementPlus'
import { ElMessageBox } from 'element-plus'
import ApiService from '@/services/apiService'

const { t } = useI18n()
const bossStore = useBossStore()
const roomStore = useRoomStore()
const { bossTypes } = storeToRefs(bossStore)
const { roomId } = storeToRefs(roomStore)

const customBossTypes = computed(() => bossTypes.value.filter(b => b.room_id))

const form = ref({ name: '', min_respawn_minutes: null as number | null, max_respawn_minutes: null as number | null })
const adding = ref(false)
const deletingId = ref<number | null>(null)

const canAdd = computed(() =>
  form.value.name.trim().length > 0 &&
  form.value.min_respawn_minutes! >= 1 &&
  form.value.max_respawn_minutes! >= 1 &&
  form.value.max_respawn_minutes! >= form.value.min_respawn_minutes!
)

const addBoss = async () => {
  if (!canAdd.value || !roomId.value) return
  adding.value = true
  try {
    const result = await ApiService.createCustomBossType(roomId.value, {
      name: form.value.name.trim(),
      min_respawn_minutes: form.value.min_respawn_minutes!,
      max_respawn_minutes: form.value.max_respawn_minutes!,
    })
    bossStore.addCustomBossType(result)
    form.value = { name: '', min_respawn_minutes: null, max_respawn_minutes: null }
    showMessage.success(t('settings.customBoss.addSuccess'))
  } catch {
    showMessage.error(t('settings.customBoss.addFailed'))
  } finally {
    adding.value = false
  }
}

const deleteBoss = async (id: number) => {
  if (!roomId.value) return
  try {
    await ElMessageBox.confirm(
      t('settings.customBoss.deleteConfirmMessage'),
      t('settings.customBoss.deleteConfirmTitle'),
      {
        confirmButtonText: t('settings.customBoss.delete'),
        cancelButtonText: '取消',
        type: 'warning',
      }
    )
  } catch {
    return
  }

  deletingId.value = id
  try {
    await ApiService.deleteCustomBossType(roomId.value, id)
    bossStore.removeCustomBossType(id)
    showMessage.success(t('settings.customBoss.deleteSuccess'))
  } catch {
    showMessage.error(t('settings.customBoss.deleteFailed'))
  } finally {
    deletingId.value = null
  }
}
</script>