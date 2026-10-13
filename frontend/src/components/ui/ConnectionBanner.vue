<template>
  <div
    v-if="showBanner"
    role="status"
    class="mb-4 flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 text-sm text-amber-800 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-300"
  >
    <span class="inline-flex h-2.5 w-2.5 shrink-0 animate-pulse rounded-full bg-amber-500"></span>
    {{ t('bossTracker.reconnecting') }}
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { refDebounced } from '@vueuse/core'
import { useI18n } from 'vue-i18n'
import { useWebSocketStore } from '@/stores/websocketStore'

const { t } = useI18n()
const { isReconnecting } = storeToRefs(useWebSocketStore())

// 重連中超過 2 秒才顯示（部署切換等短暫重連不閃爍），恢復時立即隱藏
const settledReconnecting = refDebounced(isReconnecting, 2000)
const showBanner = computed(() => isReconnecting.value && settledReconnecting.value)
</script>
