<template>
  <div class="@container bg-white dark:bg-gray-800 rounded-lg shadow-md p-4">

    <el-form
        :model="form"
        @submit.prevent
        label-position="top"
    >
      <div class="grid grid-cols-2 gap-3 mb-3">
        <el-form-item :label="t('bossControlPanel.channel')" class="mb-0">
          <el-input
              v-model="form.channel"
              :placeholder="t('bossControlPanel.channel')"
              @input="onChannelInput"
              clearable
              maxlength="5"
              inputmode="numeric"
              pattern="[0-9]*"
          />
        </el-form-item>

        <el-form-item :label="t('bossControlPanel.boss')" class="mb-0">
          <el-select
              v-model="form.boss_type_id"
              :placeholder="t('bossControlPanel.selectBoss')"
              @change="handleBossChange"
              filterable
              clearable
              class="w-full"
          >
            <el-option-group v-if="customBossTypes.length" :label="t('bossControlPanel.customBosses')">
              <el-option
                  v-for="boss in customBossTypes"
                  :key="boss.id"
                  :label="boss.name_zh"
                  :value="boss.id"
              />
            </el-option-group>

            <el-option-group v-if="favoriteOptions.length" :label="t('bossControlPanel.favorites')">
              <el-option
                  v-for="boss in favoriteOptions"
                  :key="boss.id"
                  :label="bossLabel(boss)"
                  :value="boss.id"
              >
                <div class="flex items-center justify-between w-full pr-1">
                  <span>{{ bossLabel(boss) }}</span>
                  <StarSolidIcon
                      class="w-4 h-4 text-yellow-400 shrink-0 cursor-pointer hover:text-yellow-500"
                      @click.stop="toggleFavorite(boss.id)"
                  />
                </div>
              </el-option>
            </el-option-group>

            <el-option-group :label="favoriteOptions.length || customBossTypes.length ? t('bossControlPanel.otherBosses') : ''">
              <el-option
                  v-for="boss in otherOptions"
                  :key="boss.id"
                  :label="bossLabel(boss)"
                  :value="boss.id"
              >
                <div class="flex items-center justify-between w-full pr-1">
                  <span>{{ bossLabel(boss) }}</span>
                  <StarIcon
                      class="w-4 h-4 text-gray-300 dark:text-gray-600 shrink-0 cursor-pointer hover:text-yellow-400"
                      @click.stop="toggleFavorite(boss.id)"
                  />
                </div>
              </el-option>
            </el-option-group>


          </el-select>
        </el-form-item>
      </div>

      <div class="flex gap-1 @[360px]:gap-2">
        <BossStatusButton
            v-for="status in statuses"
            :key="status.type"
            :type="status.type"
            :disabled="loading"
            :compact="isCompact"
            @click="onSelectStatus(status.type)"
        />
      </div>

    </el-form>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { useRoomStore } from '@/stores/roomStore'
import { useBossStore } from '@/stores/bossStore'
import BossStatusButton from "@/components/boss/BossStatusButton.vue"
import { showMessage } from "@/composables/useElementPlus"
import { useUserStore } from '@/stores/userStore'
import { useWebSocketStore } from '@/stores/websocketStore'
import { useI18n } from 'vue-i18n'
import { useFavoriteBosses } from '@/composables/useFavoriteBosses'
import { type BossType } from '@/stores/bossStore'
import { StarIcon } from '@heroicons/vue/24/outline'
import { StarIcon as StarSolidIcon } from '@heroicons/vue/24/solid'

const { t, locale } = useI18n()

const roomStore = useRoomStore()
const bossStore = useBossStore()
const userStore = useUserStore()
const websocketStore = useWebSocketStore()

const { roomId } = storeToRefs(roomStore)
const { bossTypes, selectedChannel, selectedBossTypeId } = storeToRefs(bossStore)
const { isLoggedIn, anonymousId, anonymousName } = storeToRefs(userStore)

const props = defineProps<{
  colSpan?: 1 | 2 | 3 | 4
}>()

const { favoriteBossIds, toggleFavorite } = useFavoriteBosses()

const isCompact = computed(() => [1,2].includes(props.colSpan))

const bossLabel = (boss: BossType) => locale.value === 'zh' ? boss.name_zh : boss.name_en

const globalBossTypes = computed(() => bossTypes.value.filter(b => !b.room_id))
const customBossTypes = computed(() => bossTypes.value.filter(b => !!b.room_id))

const favoriteOptions = computed(() =>
    globalBossTypes.value.filter((b) => favoriteBossIds.value.includes(b.id))
)
const otherOptions = computed(() =>
    globalBossTypes.value.filter((b) => !favoriteBossIds.value.includes(b.id))
)

const statuses = [
  { type: 'alive' },
  { type: 'killed' },
  { type: 'not_found' }
] as const

interface FormState {
  channel: string | number
  boss_type_id: number | null
  status: string
}

const form = ref<FormState>({
  channel: selectedChannel.value || '',
  boss_type_id: null,
  status: ''
})

const loading = ref(false)

const handleBossChange = (val: number | null) => {
  bossStore.setSelectedBossTypeId(val)
}

const onSelectStatus = async (statusType: string) => {
  if (loading.value) return
  if (!form.value.boss_type_id) {
    showMessage.warning(t('bossControlPanel.selectBossFirst'))
    return
  }
  if (!form.value.channel) {
    showMessage.warning(t('bossControlPanel.enterChannelFirst'))
    return
  }
  form.value.status = statusType
  await recordBoss()
}

watch(selectedChannel, (newVal) => {
  form.value.channel = newVal || ''
})

watch(selectedBossTypeId, (newVal) => {
  form.value.boss_type_id = newVal
})

const canSubmit = computed(() => {
  return roomId.value &&
      form.value.channel !== '' &&
      !!form.value.boss_type_id &&
      form.value.status
})

const recordBoss = async () => {
  if (!canSubmit.value) return

  loading.value = true
  try {
    const recorderInfo = (!isLoggedIn.value && anonymousName.value)
      ? { anonymous_id: anonymousId.value, anonymous_name: anonymousName.value }
      : null

    const payload = {
      room_id: roomId.value,
      channel: typeof form.value.channel === 'string' ? parseInt(form.value.channel, 10) : form.value.channel,
      boss_type_id: form.value.boss_type_id,
      status: form.value.status,
      recorder_info: recorderInfo,
    }

    websocketStore.sendMessage({
      type: 'record_boss',
      payload: payload,
    })

    form.value.channel = ''
    form.value.status = ''

  } catch (error) {
    console.error('Failed to send record boss message via WebSocket:', error)
    showMessage.error(t('bossControlPanel.sendRecordFailed'))
  } finally {
    loading.value = false
  }
}

const onChannelInput = (value: string) => {
  if (!value) {
    form.value.channel = ''
    return
  }
  form.value.channel = value.toString().replace(/\D/g, '')
}

onMounted(() => {
  form.value.boss_type_id = selectedBossTypeId.value
})
</script>