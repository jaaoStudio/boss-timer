<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg shadow-md p-6">
    <div class="flex items-center justify-between mb-4">
      <h2 class="text-xl font-semibold text-gray-900 dark:text-white">{{ t('recommendedChannels.title') }}</h2>
      <el-button-group size="small" class="boss-mode-toggle">
        <el-button
          :type="!showAllBosses ? 'primary' : 'default'"
          @click="showAllBosses = false"
        >
          {{ t('recommendedChannels.currentBoss') }}
        </el-button>
        <el-button
          :type="showAllBosses ? 'primary' : 'default'"
          @click="showAllBosses = true"
        >
          {{ t('recommendedChannels.allBosses') }}
        </el-button>
      </el-button-group>
    </div>

    <!-- 全 Boss 模式：單一排行清單，可點擊帶入控制面板 -->
    <template v-if="showAllBosses">
      <RecommendedSection
        :title="t('recommendedChannels.priorityTitle')"
        :channels="allBossPriorityRecords"
        type="priority"
        :show-boss-name="true"
        :clickable="true"
        @record-click="handleRecordClick"
      />
    </template>

    <!-- 當前 Boss 模式：原有優先 / 避開雙欄 -->
    <template v-else>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <RecommendedSection
          :title="t('recommendedChannels.priorityTitle')"
          :channels="priorityChannels"
          type="priority"
        />
        <RecommendedSection
          :title="t('recommendedChannels.avoidTitle')"
          :channels="avoidChannels"
          type="avoid"
        />
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useBossStore, type BossRecord } from '@/stores/bossStore'
import RecommendedSection from '@/components/ui/RecommendedSection.vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const bossStore = useBossStore()
const { priorityChannels, avoidChannels, allBossPriorityRecords } = storeToRefs(bossStore)

const showAllBosses = ref(false)

const handleRecordClick = (record: BossRecord) => {
  bossStore.setSelectedBossTypeId(record.boss_type_id)
  bossStore.setSelectedChannel(record.channel)
}
</script>

