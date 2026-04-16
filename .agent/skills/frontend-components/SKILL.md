---
name: Boss Timer Frontend 元件與 i18n 開發規範
description: 新增或修改 Vue 3 元件、Element Plus UI、多語系 i18n 鍵值時使用。包含元件結構、Tailwind CSS 慣例、i18n 必要步驟。
---

# Boss Timer Frontend 元件與 i18n 開發規範

## 技術棧

| 項目 | 技術 |
|---|---|
| 框架 | Vue 3 (Composition API / `<script setup>`) |
| UI 元件庫 | Element Plus（auto-import） |
| CSS | Tailwind CSS v4 |
| 國際化 | vue-i18n v11 |
| 圖示 | @heroicons/vue、@element-plus/icons-vue |
| TypeScript | ^5.8 |

---

## 元件目錄結構

```
frontend/src/
├── components/
│   ├── AppHeader.vue
│   ├── BossControlPanel.vue
│   ├── BossInfo.vue
│   ├── BossStatusButton.vue
│   ├── ChannelCard.vue
│   ├── ChannelOverview.vue
│   ├── RecordHistory.vue
│   ├── RecordItem.vue
│   ├── SettingsModal.vue     ← Discord Webhook 設定、通知、音效
│   ├── StatusBadge.vue
│   └── ...
├── locales/
│   ├── zh.json               ← 繁體中文翻譯
│   └── en.json               ← 英文翻譯
└── views/
    ├── RoomSelection.vue
    ├── BossTracker.vue
    └── ...
```

---

## 元件開發慣例

### 使用 `<script setup>` + Composition API

```vue
<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoomStore } from '@/stores/roomStore'

const { t } = useI18n()
const roomStore = useRoomStore()

const someRef = ref<string>('')
</script>
```

- 新元件一律用 `<script setup lang="ts">`
- 現有 Store 部分為 Options API（維護時維持原風格）
- Element Plus 元件透過 `unplugin-vue-components` 自動引入，**不需手動 import**

### Props 驗證
```typescript
const props = defineProps<{
  roomId: string
  isEnabled?: boolean
}>()
```

### Tailwind CSS
- 使用 Tailwind v4 語法（`@tailwindcss/vite` plugin）
- 深色模式使用 `dark:` 前綴：`dark:text-gray-300`
- 不使用行內 style（除非 Element Plus CSS 變數覆寫）

---

## 國際化 (i18n) — ⚠️ 所有使用者可見文字必須使用

### 使用方式

```vue
<template>
  <span>{{ t('settings.webhookUrl') }}</span>
  <el-option :label="t('settings.webhookAlertBoth')" value="both" />
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
</script>
```

### 新增翻譯的步驟

**必須同時更新兩個檔案：**
1. `frontend/src/locales/zh.json`
2. `frontend/src/locales/en.json`

翻譯 key 使用巢狀結構（`模組.功能`）：
```json
{
  "settings": {
    "discordWebhookSection": "💬 Discord Webhook (房間專屬)",
    "webhookUrl": "Webhook URL",
    "webhookNotifyEvents": "發送即時紀錄通知",
    "webhookNotifyKilled": "擊殺",
    "webhookNotifyAlive": "存活",
    "webhookNotifyNotFound": "未發現",
    "webhookAlertMode": "預警模式 (約 5 分鐘前通知)",
    "webhookAlertBoth": "最小重生與最大重生時間 (皆通知)",
    "webhookAlertMin": "只通知最小重生時間",
    "webhookAlertMax": "只通知最大重生時間",
    "webhookAlertNone": "不預警 (關閉)",
    "webhookUpdated": "Webhook 設定已更新",
    "webhookUpdateFailed": "更新失敗"
  }
}
```

---

## 現有 i18n Key 命名空間

| 命名空間 | 用途 |
|---|---|
| `login.*` | 登入頁 |
| `roomSelection.*` | 房間選擇頁 |
| `roomManager.*` | 房間管理操作 |
| `appHeader.*` | 頂部導覽列 |
| `bossTracker.*` | Boss 追蹤器頁 |
| `bossControlPanel.*` | Boss 操作面板 |
| `bossInfo.*` | Boss 詳細資訊 |
| `bossStatusButton.*` | Boss 狀態按鈕 |
| `channelOverview.*` | 頻道總覽 |
| `recommendedChannels.*` | 推薦頻道 |
| `recordHistory.*` | 擊殺紀錄 |
| `recordItem.*` | 單筆紀錄 |
| `status.*` | 狀態標籤文字 |
| `recentRooms.*` | 最近房間 |
| `settings.*` | 設定彈窗（通知、音效、Webhook） |
| `notification.*` | 瀏覽器通知文字 |
| `appFooter.*` | 頁尾 |
| `credits.*` | 致謝頁 |
| `legal.*` | 法律聲明頁 |
| `privacy.*` | 隱私政策頁 |

---

## Element Plus 使用注意事項

- 元件透過 `unplugin-vue-components` 自動引入（不需 import）
- 圖示需手動引入：`import { VideoPlay } from '@element-plus/icons-vue'`
- Checkbox group 的 `value` vs `label`：
  ```vue
  <!-- value 是實際綁定值，label 是顯示文字 -->
  <el-checkbox-group v-model="webhookNotifyEvents">
    <el-checkbox value="killed" :label="t('settings.webhookNotifyKilled')" />
    <el-checkbox value="alive" :label="t('settings.webhookNotifyAlive')" />
    <el-checkbox value="not_found" :label="t('settings.webhookNotifyNotFound')" />
  </el-checkbox-group>
  ```
- Switch 顏色覆寫：`style="--el-switch-on-color: #6366f1;"`

---

## showMessage 封裝

不直接使用 `ElMessage`，改用封裝後的工具：

```typescript
import { showMessage } from '@/composables/useElementPlus.js'

showMessage.success(t('settings.webhookUpdated'))
showMessage.error(t('settings.webhookUpdateFailed'))
showMessage.warning(t('settings.fileTooLarge'))
```

---

## Path Alias

| Alias | 路徑 |
|---|---|
| `@` | `src/` |
| `@images` | `src/assets/images/` |
| `@icons` | `src/assets/icons/` |
| `@public` | `public/` |
