<template>
  <div class="@container bg-white dark:bg-gray-800 rounded-lg shadow-md p-6 mb-6">

    <el-form
        :model="form"
        @submit.prevent="recordBoss"
        label-position="top"
        class="grid grid-cols-1 @[560px]:grid-cols-3 gap-4"
    >

      <el-form-item :label="t('bossControlPanel.channel')">
        <el-input
            v-model="form.channel"
            :placeholder="t('bossControlPanel.channel')"
            @input="onChannelInput"
            clearable
            maxlength="5"
        />
      </el-form-item>

      <el-form-item :label="t('bossControlPanel.boss')">


        <el-select
            v-model="form.boss_type_id"
            :placeholder="t('bossControlPanel.selectBoss')"
            @change="handleBossChange"
            filterable
            clearable
            class="w-full"
        >
          <!-- 收藏區 -->
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

          <!-- 其他 -->
          <el-option-group :label="favoriteOptions.length ? t('bossControlPanel.otherBosses') : ''">
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

          <!-- 自訂 Boss -->
          <el-option-group v-if="customBossTypes.length" :label="t('bossControlPanel.customBosses')">
            <el-option
                v-for="boss in customBossTypes"
                :key="boss.id"
                :label="boss.name_zh"
                :value="boss.id"
            />
          </el-option-group>
        </el-select>
      </el-form-item>

      <el-form-item :label="t('bossControlPanel.status')">
        <div class="flex gap-2 w-full">
          <BossStatusButton
              v-for="status in statuses"
              :key="status.type"
              :type="status.type"
              :disabled="loading"
              :class="{
              'opacity-60': loading
            }"
              @click="onSelectStatus(status.type)"
          />
        </div>
      </el-form-item>

    </el-form>
  </div>
</template>

<script setup lang="ts">
import {ref, computed, watch, onMounted} from 'vue'
import {storeToRefs} from 'pinia'
import {useRoomStore} from '@/stores/roomStore'
import {useBossStore} from '@/stores/bossStore'
import BossStatusButton from "@/components/BossStatusButton.vue"
import {showMessage} from "@/composables/useElementPlus"
import {useUserStore} from '@/stores/userStore'
import {useWebSocketStore} from '@/stores/websocketStore'
import {useI18n} from 'vue-i18n'
import {useFavoriteBosses} from '@/composables/useFavoriteBosses'
import {StarIcon} from '@heroicons/vue/24/outline'
import {StarIcon as StarSolidIcon} from '@heroicons/vue/24/solid'

const {t, locale} = useI18n()

const roomStore = useRoomStore()
const bossStore = useBossStore()
const userStore = useUserStore()
const websocketStore = useWebSocketStore()

const {roomId} = storeToRefs(roomStore)
const {bossTypes, selectedChannel, selectedBossTypeId} = storeToRefs(bossStore)
const {isLoggedIn, anonymousId, anonymousName} = storeToRefs(userStore)

const {favoriteBossIds, toggleFavorite} = useFavoriteBosses()

const bossLabel = (boss: any) => locale.value === 'zh' ? boss.name_zh : boss.name_en

const globalBossTypes = computed(() => bossTypes.value.filter(b => !b.room_id))
const customBossTypes = computed(() => bossTypes.value.filter(b => !!b.room_id))

const favoriteOptions = computed(() =>
    globalBossTypes.value.filter((b) => favoriteBossIds.value.includes(b.id))
)
const otherOptions = computed(() =>
    globalBossTypes.value.filter((b) => !favoriteBossIds.value.includes(b.id))
)


const statuses = [
  {type: 'alive'},
  {type: 'killed'},
  {type: 'not_found'}
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

// Sync from store to local form
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
    const payload: any = { // Using any for payload temporarily, ideally define interface
      room_id: roomId.value,
      channel: typeof form.value.channel === 'string' ? parseInt(form.value.channel, 10) : form.value.channel,
      boss_type_id: form.value.boss_type_id,
      status: form.value.status,
      recorder_info: null
    }

    if (!isLoggedIn.value && anonymousName.value) {
      payload.recorder_info = {
        anonymous_id: anonymousId.value,
        anonymous_name: anonymousName.value,
      }
    }

    websocketStore.sendMessage({
      type: 'record_boss',
      payload: payload,
    })

    form.value.channel = ''

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
  const sanitized = value.toString().replace(/\D/g, '')
  form.value.channel = sanitized
}

onMounted(() => {
  form.value.boss_type_id = selectedBossTypeId.value
})
</script>