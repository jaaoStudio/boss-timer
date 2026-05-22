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
│   ├── AppHeader.vue             ← 全域頂部導覽列（保留頂層）
│   ├── AppFooter.vue             ← 全域頁尾（保留頂層）
│   │
│   ├── boss/                     ← Boss 相關
│   │   ├── BossControlPanel.vue  ← 收藏 Boss chips 快速切換 + Boss 種類 Tab + 頻道輸入
│   │   ├── BossInfo.vue
│   │   ├── BossInfoItem.vue
│   │   └── BossStatusButton.vue
│   │
│   ├── channel/                  ← 頻道相關
│   │   ├── ChannelCard.vue
│   │   ├── ChannelOverview.vue
│   │   ├── ChannelTimeline.vue
│   │   ├── ChannelView.vue
│   │   └── RecommendedChannels.vue
│   │
│   ├── layout/                   ← 版面結構
│   │   ├── EditModeToolbar.vue   ← 編輯模式工具列（props/emits 與父溝通）
│   │   └── LayoutItemWrapper.vue ← Widget 容器（寬度、收合、拖曳把手）
│   │
│   ├── record/                   ← 擊殺紀錄
│   │   ├── RecordHistory.vue
│   │   └── RecordItem.vue
│   │
│   ├── room/                     ← 房間操作
│   │   └── RoomManager.vue
│   │
│   ├── settings/                 ← 設定彈窗（通知、音效、Webhook、自訂 Boss）
│   │   ├── SettingsModal.vue
│   │   ├── SettingsPreferences.vue
│   │   ├── SettingsChangelog.vue
│   │   ├── SettingsSupport.vue
│   │   └── SettingsCustomBosses.vue
│   │
│   └── ui/                       ← 通用 UI 元件
│       ├── AdBanner.vue
│       ├── CountdownTimer.vue
│       ├── GoogleLoginButton.vue
│       ├── MaintenanceBanner.vue
│       ├── RecommendedSection.vue
│       └── StatusBadge.vue
│
├── composables/
│   ├── useLocalStorage.ts    ← 通用 localStorage 基礎層（load/deserialize/watch-persist）
│   ├── useElementPlus.ts     ← showMessage / showMessageBox 封裝
│   ├── useTheme.ts           ← isDark / toggleDark
│   ├── useLayoutConfig.ts    ← 版面 Widget 排列、寬度、收合狀態管理（singleton）
│   ├── useStatusConfig.ts    ← 狀態色彩映射、STATUS_ORDER、isExpiredRecord(record, liveStatus?, nowMs?) 統一定義
│   ├── useRoomSession.ts     ← 房間進出封裝（enter/leave），BossTracker.vue 使用
│   ├── useFavoriteBosses.ts  ← 收藏 Boss 列表（localStorage）
│   ├── useChannelViewPreference.ts ← 頻道檢視偏好（localStorage）
│   └── ...
│
├── axios/
│   ├── index.ts              ← 強型別 AxiosInstance class
│   └── handlingErrors.ts     ← 全域 Axios 錯誤處理（已轉 .ts）
│
├── locales/
│   ├── zh.json               ← 繁體中文翻譯
│   └── en.json               ← 英文翻譯
└── views/
    ├── RoomSelection.vue
    ├── BossTracker.vue
    └── ...
```

> **⚠️ Import 路徑規則**：
> - 跨子目錄引用元件一律使用 `@/components/<子目錄>/元件名.vue`，禁止使用相對路徑
> - **不加副檔名**：`import { showMessage } from '@/composables/useElementPlus'`（勿加 `.js` 或 `.ts`）
> - `@/` 路徑由 `tsconfig.app.json` 的 `baseUrl` + `paths` 解析，**不是** root `tsconfig.json`

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

## TypeScript 型別規範

### Store 型別從 Store 引入

`bossStore.ts` 已匯出 `BossType` 與 `BossRecord` 介面，**不要在元件內自己重定義**：

```typescript
import { type BossType, type BossRecord } from '@/stores/bossStore'
```

`BossRecord` 的重點欄位：

| 欄位 | 型別 | 說明 |
|---|---|---|
| `id` | `number` | 主鍵 |
| `channel` | `number` | 頻道 |
| `boss_type_id` | `number` | Boss 種類 ID |
| `status` | `string` | 原始狀態（`killed/alive/not_found`） |
| `current_status` | `string` | 動態狀態（`respawning/may_respawn/alive/not_found`） |
| `respawn_min_time` | `string \| null` | 最早重生時間（ISO string） |
| `respawn_max_time` | `string \| null` | 最晚重生時間（ISO string） |
| `recorder_info` | `object \| null` | 匿名記錄者資訊 |

> ⚠️ `respawn_min_time` / `respawn_max_time` 可能為 `null`，使用前須 null check 或 `!` 非空斷言。

---

## 通用元件 API

### `RecommendedSection.vue`

顯示推薦頻道清單，支援兩種渲染模式：

| Prop | 型別 | 預設 | 說明 |
|---|---|---|---|
| `title` | `string` | — | 區塊標題 |
| `channels` | `BossRecord[]` | — | 要顯示的記錄列表 |
| `type` | `'priority' \| 'avoid'` | — | 決定背景色與計時器方向 |
| `showBossName` | `boolean?` | `false` | `true` → 列表模式（顯示 Boss 名稱 + 頻道），`false` → 格線模式（僅頻道） |
| `clickable` | `boolean?` | `false` | `true` → 點擊列表項目觸發 `record-click` emit |

| Emit | Payload | 說明 |
|---|---|---|
| `record-click` | `BossRecord` | 列表模式下點擊時觸發，用於帶入 BossControlPanel 的選擇狀態 |

**使用情境**:
- `RecommendedChannels` 的「當前 Boss」模式使用格線模式（`showBossName` 預設 false）
- 「全部 Boss」模式傳入 `bossStore.allBossPriorityRecords`，並啟用 `showBossName` + `clickable`，點擊後呼叫 `bossStore.setSelectedBossTypeId()` + `bossStore.setSelectedChannel()`

> `CountdownTimer` 的 `@timer-end` 在 `RecommendedSection` 中**不再監聽**，狀態切換改由 `bossStore._now` 每秒驅動（`calculateCurrentStatus`），不依賴 UI timer 的存活狀態。

---

## 版面系統（useLayoutConfig）

### 資料結構

```typescript
interface LayoutItem {
  id: LayoutItemId       // 'controlPanel' | 'bossInfo' | 'channelView' | 'recommendedChannels' | 'recordHistory'
  colSpan: 1 | 2 | 3 | 4  // 在 4 欄 Grid 中佔幾欄（¼ ½ ¾ 全寬）
  collapsed: boolean       // 是否收合
}
```

### 各 Widget 最小寬度限制（`MIN_COL_SPAN`）

```typescript
// channelView / recommendedChannels / recordHistory 最小 2/4，不可縮到 1/4
import { MIN_COL_SPAN } from '@/composables/useLayoutConfig'
```

| Widget | 最小 colSpan |
|---|---|
| controlPanel | 1 |
| bossInfo | 1 |
| channelView | 2 |
| recommendedChannels | 2 |
| recordHistory | 2 |

### 使用方式

```typescript
const {
  layout,
  isEditMode,
  moveItem,
  increaseColSpan,   // ← 取代舊 toggleColSpan
  decreaseColSpan,   // ← 取代舊 toggleColSpan
  toggleCollapsed,   // ← 收合/展開，立即持久化
  enterEditMode,
  exitEditMode,
  resetLayout,
} = useLayoutConfig()
```

### BossTracker Grid 結構

```vue
<VueDraggable
  v-model="layout"
  :disabled="!isEditMode"
  handle=".drag-handle"
  class="grid grid-cols-1 md:grid-cols-4 gap-6"
>
  <LayoutItemWrapper
    v-for="(item, index) in layout"
    :key="item.id"
    :item="item"
    :index="index"
    :total-items="layout.length"
    :is-edit-mode="isEditMode"
    :visible="isItemVisible(item.id)"
    @move-up="moveItem(index, index - 1)"
    @move-down="moveItem(index, index + 1)"
    @increase-col-span="increaseColSpan(item.id)"
    @decrease-col-span="decreaseColSpan(item.id)"
    @toggle-collapsed="toggleCollapsed(item.id)"
  >
    <!-- slot content -->
  </LayoutItemWrapper>
</VueDraggable>
```

### LayoutItemWrapper 行為說明

- **編輯模式**：顯示拖曳把手、上下移動、`[−] n/4 [+]` 寬度控制；**無**收合按鈕
- **非編輯模式（展開）**：Widget 右上角有浮動 chevron 收合按鈕（hover 才顯現）
- **非編輯模式（收合）**：顯示薄 header bar，點擊展開

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
    "webhookUrl": "Webhook URL",
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
| `channelTimeline.*` | 重生時間軸 |
| `recommendedChannels.*` | 推薦頻道 |
| `recordHistory.*` | 擊殺紀錄 |
| `recordItem.*` | 單筆紀錄 |
| `status.*` | 狀態標籤文字 |
| `recentRooms.*` | 最近房間 |
| `settings.*` | 設定彈窗（通知、音效、Webhook） |
| `notification.*` | 瀏覽器通知文字 |
| `layout.*` | 版面編輯模式工具列與自訂版面（含 `collapse/expand/narrower/wider`） |
| `appFooter.*` | 頁尾 |
| `credits.*` | 致謝頁 |
| `legal.*` | 法律聲明頁 |
| `privacy.*` | 隱私政策頁 |
| `changelog.*` | 更新日誌內容 |
| `globalErrors.*` | 全域錯誤提示 |

---

## Element Plus 使用注意事項

- 元件透過 `unplugin-vue-components` 自動引入（不需 import）
- 圖示需手動引入：`import { VideoPlay } from '@element-plus/icons-vue'`
- Checkbox group 的 `value` vs `label`：
  ```vue
  <el-checkbox-group v-model="webhookNotifyEvents">
    <el-checkbox value="killed" :label="t('settings.webhookNotifyKilled')" />
    <el-checkbox value="alive" :label="t('settings.webhookNotifyAlive')" />
  </el-checkbox-group>
  ```
- Switch 顏色覆寫：`style="--el-switch-on-color: #6366f1;"`

---

## showMessage 封裝

不直接使用 `ElMessage`，改用封裝後的工具：

```typescript
import { showMessage } from '@/composables/useElementPlus'

showMessage.success(t('settings.webhookUpdated'))
showMessage.error(t('settings.webhookUpdateFailed'))
showMessage.warning(t('settings.fileTooLarge'))
```

> `useElementPlus.ts` 已完整型別化（`MessageType`、`ShowMessage` class）。

---

## 深色模式

```typescript
import { isDark, toggleDark } from '@/composables/useTheme'
```

> `useTheme.ts` 已完整型別化。`isDark` 為 `Ref<boolean>`，`toggleDark` 為切換函式。

---

## Path Alias

| Alias | 路徑 |
|---|---|
| `@` | `src/` |
| `@images` | `src/assets/images/` |
| `@icons` | `src/assets/icons/` |
| `@public` | `public/` |

> `@/` alias 定義在 `tsconfig.app.json` 的 `compilerOptions.paths`（**非** root `tsconfig.json`），Vite 端定義在 `vite.config.ts`。