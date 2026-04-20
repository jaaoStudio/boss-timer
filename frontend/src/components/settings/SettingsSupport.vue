<template>
  <div class="py-2 space-y-5">
    <p class="text-sm text-gray-600 dark:text-gray-400 text-center leading-relaxed">
      {{ t('settings.support.message') }}
    </p>

    <div class="flex flex-col gap-3">
      <!-- Buy Me a Coffee -->
      <a
        href="https://buymeacoffee.com/jack580936"
        target="_blank"
        rel="noopener noreferrer"
        class="flex items-center gap-3 p-4 rounded-xl border-2 border-yellow-400 dark:border-yellow-500 bg-yellow-50 dark:bg-yellow-900/10 hover:bg-yellow-100 dark:hover:bg-yellow-900/20 transition-colors group no-underline"
      >
        <span class="text-2xl shrink-0">☕</span>
        <div class="flex-1 min-w-0">
          <div class="font-semibold text-gray-800 dark:text-gray-200 text-sm">Buy Me a Coffee</div>
          <div class="text-xs text-gray-500 dark:text-gray-400">buymeacoffee.com</div>
        </div>
        <ArrowTopRightOnSquareIcon class="w-4 h-4 text-gray-300 dark:text-gray-600 group-hover:text-yellow-500 transition-colors shrink-0" />
      </a>

      <!-- PayUni -->
      <a
        href="https://api.payuni.com.tw/api/uop/receive_info/2/1/HIBE014209/0ksBJWqn4we38mzhYGsM"
        target="_blank"
        rel="noopener noreferrer"
        class="flex items-center gap-3 p-4 rounded-xl border-2 border-indigo-300 dark:border-indigo-700 bg-indigo-50 dark:bg-indigo-900/10 hover:bg-indigo-100 dark:hover:bg-indigo-900/20 transition-colors group no-underline"
      >
        <span class="text-2xl shrink-0">💳</span>
        <div class="flex-1 min-w-0">
          <div class="font-semibold text-gray-800 dark:text-gray-200 text-sm">{{ t('settings.support.payuniLabel') }}</div>
          <div class="text-xs text-gray-500 dark:text-gray-400">{{ t('settings.support.payuniMethods') }}</div>
        </div>
        <ArrowTopRightOnSquareIcon class="w-4 h-4 text-gray-300 dark:text-gray-600 group-hover:text-indigo-500 transition-colors shrink-0" />
      </a>
    </div>

    <p class="text-xs text-center text-gray-400 dark:text-gray-500">
      {{ t('settings.support.thankyou') }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
import { ArrowTopRightOnSquareIcon } from '@heroicons/vue/24/outline'

const { t } = useI18n()
</script>