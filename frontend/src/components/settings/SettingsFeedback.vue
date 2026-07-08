<template>
  <div class="space-y-4">
    <!-- 未登入提示 -->
    <div
      v-if="!isLoggedIn"
      class="rounded-lg border border-amber-300 dark:border-amber-700 bg-amber-50 dark:bg-amber-900/20 p-3 text-sm text-amber-700 dark:text-amber-300"
    >
      {{ t('settings.feedback.loginToSubmit') }}
    </div>

    <!-- 提交表單 -->
    <div
      v-if="isLoggedIn"
      class="border border-gray-200 dark:border-gray-700 rounded-lg p-3 space-y-3"
    >
      <p class="text-sm font-medium text-gray-700 dark:text-gray-300">
        {{ t('settings.feedback.submitTitle') }}
      </p>

      <el-segmented
        v-model="form.type"
        :options="typeOptions"
        block
      />

      <el-input
        v-model="form.title"
        :placeholder="t('settings.feedback.titlePlaceholder')"
        maxlength="200"
        show-word-limit
      />

      <el-input
        v-model="form.description"
        type="textarea"
        :rows="3"
        :placeholder="t('settings.feedback.descPlaceholder')"
        maxlength="2000"
        show-word-limit
      />

      <el-button
        type="primary"
        :loading="submitting"
        :disabled="!canSubmit"
        class="w-full"
        @click="submit"
      >
        {{ t('settings.feedback.submit') }}
      </el-button>
    </div>

    <!-- 清單區 header：標題 + 排序 -->
    <div class="flex items-center justify-between">
      <p class="text-sm font-medium text-gray-700 dark:text-gray-300">
        {{ t('settings.feedback.listTitle') }}
      </p>
      <el-radio-group v-model="sortBy" size="small">
        <el-radio-button value="votes">{{ t('settings.feedback.sortVotes') }}</el-radio-button>
        <el-radio-button value="newest">{{ t('settings.feedback.sortNewest') }}</el-radio-button>
      </el-radio-group>
    </div>

    <!-- 載入中 / 清單 -->
    <div v-if="loading" class="text-center text-sm text-gray-400 py-4">
      {{ t('settings.feedback.loading') }}
    </div>

    <div v-else-if="!items.length" class="text-center text-sm text-gray-400 py-4">
      {{ t('settings.feedback.empty') }}
    </div>

    <div v-else class="space-y-2">
      <div
        v-for="item in items"
        :key="item.id"
        class="flex items-start gap-3 border border-gray-200 dark:border-gray-700 rounded-lg p-3"
        :class="{ 'opacity-60': item.status === 'done' || item.status === 'rejected' }"
      >
        <!-- 投票按鈕 -->
        <button
          class="shrink-0 flex flex-col items-center justify-center min-w-[44px] py-1 px-2 rounded-md border transition-colors"
          :class="voteBtnClass(item)"
          :disabled="!isLoggedIn || votingId === item.id || !isVotable(item)"
          @click="vote(item)"
        >
          <ChevronUpIcon class="w-4 h-4" />
          <span class="text-xs font-semibold">{{ item.vote_count }}</span>
        </button>

        <!-- 內文 -->
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 flex-wrap">
            <el-tag :type="typeTagType(item.type)" size="small" effect="plain">
              {{ t(`settings.feedback.type.${item.type}`) }}
            </el-tag>
            <el-tag :type="statusTagType(item.status)" size="small">
              {{ t(`settings.feedback.status.${item.status}`) }}
            </el-tag>
          </div>

          <p class="mt-1 text-sm font-medium text-gray-800 dark:text-gray-200 break-words">
            {{ item.title }}
          </p>

          <p
            v-if="item.description"
            class="mt-1 text-xs text-gray-600 dark:text-gray-400 break-words whitespace-pre-wrap"
          >
            {{ item.description }}
          </p>

          <div class="mt-2 flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
            <img
              v-if="item.creator?.avatar_url"
              :src="item.creator.avatar_url"
              :alt="item.creator.display_name"
              class="w-4 h-4 rounded-full"
              referrerpolicy="no-referrer"
            />
            <span>{{ item.creator?.display_name ?? t('settings.feedback.anonymous') }}</span>
            <span>·</span>
            <span>{{ formatRelativeTime(item.created_at) }}</span>
          </div>

          <!-- Admin 控制列 -->
          <div v-if="isAdmin" class="mt-2 flex flex-wrap items-center gap-1">
            <el-select
              :model-value="item.status"
              size="small"
              style="width: 110px"
              @change="(s: FeedbackStatus) => updateStatus(item, s)"
            >
              <el-option v-for="s in allStatuses" :key="s" :value="s" :label="t(`settings.feedback.status.${s}`)" />
            </el-select>
            <el-button size="small" type="danger" text @click="remove(item)">
              {{ t('settings.feedback.delete') }}
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { ChevronUpIcon } from '@heroicons/vue/24/solid'
import { formatDistanceToNowStrict } from 'date-fns'
import { zhTW, enUS } from 'date-fns/locale'
import { ElMessageBox } from 'element-plus'

import { useUserStore } from '@/stores/userStore'
import ApiService, {
  type FeedbackItem,
  type FeedbackStatus,
  type FeedbackType,
} from '@/services/apiService'
import { showMessage } from '@/composables/useElementPlus'

const { t, locale } = useI18n()
const userStore = useUserStore()
const { isLoggedIn } = storeToRefs(userStore)
const isAdmin = computed(() => userStore.isAdmin)

const items = ref<FeedbackItem[]>([])
const loading = ref(false)
const submitting = ref(false)
const votingId = ref<number | null>(null)
const sortBy = ref<'votes' | 'newest'>('votes')

const form = ref<{ type: FeedbackType; title: string; description: string }>({
  type: 'feature',
  title: '',
  description: '',
})

const typeOptions = computed(() => [
  { label: t('settings.feedback.type.feature'), value: 'feature' as FeedbackType },
  { label: t('settings.feedback.type.bug'), value: 'bug' as FeedbackType },
])

const allStatuses: FeedbackStatus[] = ['pending', 'open', 'planning', 'done', 'rejected']

const canSubmit = computed(() =>
  form.value.title.trim().length > 0 && !submitting.value,
)

const isVotable = (item: FeedbackItem) => item.status !== 'pending' && item.status !== 'rejected'

const typeTagType = (type: FeedbackType) =>
  type === 'bug' ? 'danger' : 'success'

const statusTagType = (s: FeedbackStatus) => {
  switch (s) {
    case 'open':
      return 'primary'
    case 'planning':
      return 'warning'
    case 'done':
      return 'success'
    case 'rejected':
      return 'info'
    default:
      return 'info'
  }
}

const voteBtnClass = (item: FeedbackItem) => {
  if (!isVotable(item)) {
    return 'border-gray-200 dark:border-gray-700 text-gray-400 cursor-not-allowed'
  }
  if (item.voted_by_me) {
    return 'border-amber-500 bg-amber-50 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400'
  }
  return 'border-gray-300 dark:border-gray-600 text-gray-500 dark:text-gray-300 hover:border-amber-400 hover:text-amber-500'
}

const formatRelativeTime = (iso: string) => {
  try {
    return formatDistanceToNowStrict(new Date(iso), {
      addSuffix: true,
      locale: locale.value.startsWith('zh') ? zhTW : enUS,
    })
  } catch {
    return iso
  }
}

const load = async () => {
  loading.value = true
  try {
    const res = await ApiService.listFeedback(sortBy.value)
    items.value = res.items
  } catch {
    showMessage.error(t('settings.feedback.loadFailed'))
  } finally {
    loading.value = false
  }
}

const submit = async () => {
  if (!canSubmit.value) return
  submitting.value = true
  try {
    const created = await ApiService.createFeedback({
      type: form.value.type,
      title: form.value.title.trim(),
      description: form.value.description.trim() || undefined,
    })
    items.value = [created, ...items.value]
    form.value = { type: 'feature', title: '', description: '' }
    showMessage.success(t('settings.feedback.submitSuccess'))
  } catch (e: unknown) {
    const err = e as { response?: { status?: number } }
    if (err?.response?.status === 429) {
      showMessage.warning(t('settings.feedback.rateLimited'))
    } else {
      showMessage.error(t('settings.feedback.submitFailed'))
    }
  } finally {
    submitting.value = false
  }
}

const vote = async (item: FeedbackItem) => {
  if (!isLoggedIn.value || !isVotable(item)) return
  votingId.value = item.id
  try {
    const res = await ApiService.voteFeedback(item.id)
    item.voted_by_me = res.voted
    item.vote_count = res.vote_count
  } catch {
    showMessage.error(t('settings.feedback.voteFailed'))
  } finally {
    votingId.value = null
  }
}

const updateStatus = async (item: FeedbackItem, status: FeedbackStatus) => {
  try {
    const updated = await ApiService.updateFeedbackStatus(item.id, status)
    item.status = updated.status
    showMessage.success(t('settings.feedback.statusUpdated'))
  } catch {
    showMessage.error(t('settings.feedback.statusUpdateFailed'))
  }
}

const remove = async (item: FeedbackItem) => {
  try {
    await ElMessageBox.confirm(
      t('settings.feedback.deleteConfirm'),
      t('settings.feedback.deleteTitle'),
      {
        confirmButtonText: t('settings.feedback.delete'),
        cancelButtonText: t('settings.feedback.cancel'),
        type: 'warning',
      },
    )
  } catch {
    return
  }
  try {
    await ApiService.deleteFeedback(item.id)
    items.value = items.value.filter(i => i.id !== item.id)
    showMessage.success(t('settings.feedback.deleteSuccess'))
  } catch {
    showMessage.error(t('settings.feedback.deleteFailed'))
  }
}

watch(sortBy, load)
onMounted(load)
</script>
