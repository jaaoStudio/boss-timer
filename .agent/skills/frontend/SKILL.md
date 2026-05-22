---
name: Boss Timer Frontend 開發規範
description: Vue 3 前端架構、元件結構、Pinia 狀態管理、WebSocket 通訊、Composables 模式、路由與國際化慣例。適用於所有前端相關的開發、修改與除錯任務。新增元件、i18n、Element Plus UI 請參考子 skill：frontend-components。
---

# Boss Timer Frontend 開發規範

## 專案總覽

Artale Boss Timer 前端是一個 **Vue 3 + Vite** 單頁應用 (SPA)，提供房間制的即時 Boss 重生狀態追蹤介面。  
支援 Google 帳號登入 / 匿名使用、多國語言 (i18n)、深色模式、瀏覽器通知與音效提醒。  
支援 Discord Webhook 設定與紀錄撤銷功能。

---

## 技術棧

| 項目 | 技術 | 版本 |
|---|---|---|
| 框架 | Vue.js 3 (Composition API + Options API 混用) | ^3.5 |
| 建置工具 | Vite | ^6.3 |
| 狀態管理 | Pinia | ^3.0 |
| 路由 | Vue Router | ^4.5 |
| CSS 框架 | Tailwind CSS v4 (`@tailwindcss/vite` plugin) | ^4.1 |
| UI 元件庫 | Element Plus | ^2.10 |
| HTTP 客戶端 | Axios | ^1.10 |
| 國際化 | vue-i18n | ^11.1 |
| 圖示 | @heroicons/vue | ^2.2 |
| 工具庫 | @vueuse/core, date-fns | — |
| Google 登入 | vue3-google-login + vue3-google-signin | — |
| 分析 | Google Tag Manager (@gtm-support/vue-gtm) + Microsoft Clarity | — |
| TypeScript | ^5.8 | — |
| 自動組件引入 | unplugin-auto-import + unplugin-vue-components (Element Plus Resolver) | — |

---

## 專案結構

```
frontend/
├── index.html                    # HTML 入口
├── vite.config.ts                # Vite 設定 (含 proxy、HTTPS、alias)
├── package.json                  # npm 依賴
├── tsconfig.json                 # TypeScript 設定
├── Dockerfile                    # Docker 映像 (Nginx static)
│
├── .env.development              # 開發環境變數 (localhost)
├── .env.production               # 正式環境變數 (boss-timer.jaao.tw)
│
├── public/                       # 靜態資源 (直接複製到 dist/)
├── nginx/                        # Nginx 設定檔 (部署用)
│
└── src/
    ├── main.ts                   # 應用程式進入點 (掛載 Pinia, Router, i18n, GTM, Clarity, Google Login)
    ├── App.vue                   # 根元件 (MaintenanceBanner + RouterView)
    ├── style.css                 # 全域 CSS / Tailwind 入口
    ├── i18n.ts                   # vue-i18n 設定 (自動偵測瀏覽器語系)
    │
    ├── router/
    │   └── index.ts              # 路由定義 + beforeEach 守衛 (認證 + 權限檢查)
    │
    ├── stores/                   # Pinia 狀態管理
    │   ├── appInfo.ts            # 應用全域資訊 (維護模式、Server 錯誤)
    │   ├── userStore.ts          # 使用者認證狀態 (Google 登入/登出、匿名、BroadcastChannel)
    │   ├── roomStore.ts          # 房間狀態 (roomId, userCount, 連線狀態)
    │   ├── bossStore.ts          # Boss 資料 (bossTypes, bossRecords, 篩選/排序/刪除)
    │   ├── recordHistoryStore.ts # 歷史紀錄 (cursor 分頁、日期/Boss 篩選、race-free upsert/remove)
    │   └── websocketStore.ts     # WebSocket 連線管理 (連線/斷線/重連/心跳/訊息佇列)
    │
    ├── services/
    │   └── apiService.ts         # API 服務層 (封裝所有 HTTP/WS 調用)
    │
    ├── axios/
    │   ├── index.ts              # Axios 實例建立 (自訂 AxiosInstance class, 含 interceptor)
    │   └── handlingErrors.js     # 全域 Axios 錯誤處理
    │
    ├── composables/              # Vue Composables (可複用邏輯)
    │   ├── useLocalStorage.ts    # 通用 localStorage 基礎層 (load/deserialize/watch-persist)
    │   ├── useBossAlerts.ts      # Boss 重生提醒 (通知 + 音效排程)
    │   ├── useNotification.ts    # 瀏覽器 Notification API 封裝
    │   ├── useSound.ts           # Web Audio API 音效播放 (含多種音色)
    │   ├── useSettings.ts        # 使用者設定 (通知、音效、音量，localStorage 持久化)
    │   ├── useFavoriteBosses.ts  # 收藏 Boss 列表 (localStorage 持久化)
    │   ├── useRecentRooms.ts     # 最近房間記錄 (localStorage)
    │   ├── useChannelViewPreference.ts # 頻道檢視偏好 (localStorage)
    │   ├── useStatusConfig.ts    # 狀態色彩/排序/isExpiredRecord 統一定義
    │   ├── useRoomSession.ts     # 房間進出封裝 (enter/leave，確認 Room 存在後才 setRoomId)
    │   ├── useTimer.ts           # 倒數計時器邏輯
    │   ├── useElementPlus.ts     # Element Plus 封裝 (showMessage, showDialog)
    │   └── useTheme.ts           # 深色模式切換
    │
    ├── components/               # Vue 元件
    │   ├── AppHeader.vue         # 頂部導航列 (房間 ID 顯示、設定按鈕、語系切換、登入)
    │   ├── AppFooter.vue         # 底部頁尾
    │   ├── BossControlPanel.vue  # Boss 選擇面板 (收藏 Boss chips 快速切換 + Boss 種類 Tab + 頻道輸入)
    │   ├── BossInfo.vue          # Boss 詳細資訊 (重生時間、狀態控制按鈕)
    │   ├── BossInfoItem.vue      # Boss 資訊子項目
    │   ├── BossStatusButton.vue  # Boss 狀態操作按鈕 (killed/alive/not_found)
    │   ├── ChannelCard.vue       # 單一頻道卡片 (含倒數計時)
    │   ├── ChannelOverview.vue   # 頻道總覽容器
    │   ├── CountdownTimer.vue    # 倒數計時器元件
    │   ├── GoogleLoginButton.vue # Google 登入按鈕
    │   ├── MaintenanceBanner.vue # 維護模式橫幅
    │   ├── RecommendedChannels.vue # 推薦頻道列表
    │   ├── RecommendedSection.vue  # 推薦頻道區塊 (含優先/避免)
    │   ├── RecordHistory.vue     # 歷史紀錄列表 (含刪除功能)
    │   ├── RecordItem.vue        # 單筆歷史紀錄項目 (含垃圾桶刪除按鈕)
    │   ├── RoomManager.vue       # 房間管理元件 (建立/加入房間)
    │   ├── SettingsModal.vue     # 設定彈窗 (通知、音效、偏好、Discord Webhook)
    │   └── StatusBadge.vue       # 狀態標籤 (alive/killed/respawning/may_respawn)
    │
    ├── views/                    # 頁面視圖 (對應路由)
    │   ├── RoomSelection.vue     # 首頁: 房間選擇 / 建立 / 最近房間
    │   ├── BossTracker.vue       # 主頁: Boss 追蹤器 (含所有核心元件)
    │   ├── MaintenancePage.vue   # 維護中頁面
    │   ├── MaintenanceAdmin.vue  # 管理員: 維護設定頁面
    │   ├── Credits.vue           # 貢獻者與致謝
    │   ├── LegalDisclaimer.vue   # 法律聲明
    │   ├── PrivacyPolicy.vue     # 隱私政策
    │   └── ErrorPage500.vue      # 500 錯誤頁面
    │
    ├── locales/                  # 多語言翻譯檔
    │   ├── zh.json               # 繁體中文
    │   └── en.json               # 英文
    │
    └── assets/                   # 靜態資源 (圖片、圖示)
```

---

## Pinia 狀態管理

### `userStore` — 使用者認證
**風格**: Options API

| State | 類型 | 說明 |
|---|---|---|
| `user` | `User \| null` | 登入使用者資訊 |
| `isLoggedIn` | `boolean` | 是否已登入 |
| `isLoading` | `boolean` | 正在初始化認證 |
| `anonymousId` | `string \| null` | 匿名使用者 ID (後端分配) |
| `anonymousName` | `string \| null` | 匿名使用者暱稱 (localStorage) |

**核心 Actions**:
- `initializeAuth()` — 初始化: 建立 Session → 驗證 Token → 連線 WebSocket
- `loginWithGoogle(payload)` — Google 登入 + 通知 WebSocket 更新身份
- `logout()` — 清除本地狀態 + API 登出 + 通知 WebSocket 切換匿名
- `updatePreferences(preferences)` — 更新使用者偏好設定

**跨頁籤同步**: 使用 `BroadcastChannel('user-auth')` 在多個瀏覽器頁籤間同步登入/登出狀態。

### `roomStore` — 房間狀態
**風格**: Options API

| State | 說明 |
|---|---|
| `roomId` | 當前房間 ID |
| `userCount` | 房間內人數 |
| `isConnected` | WebSocket 連線狀態 |

### `bossStore` — Boss 資料
**風格**: Options API

| State | 說明 |
|---|---|
| `bossTypes` | Boss 種類列表 |
| `bossRecords` | 當前房間的 Boss 記錄 |
| `selectedBossTypeId` | 目前選中的 Boss 種類 ID |
| `selectedChannel` | 目前選中的頻道 |
| `_now` | `number`（ms epoch）每秒 tick 一次，驅動全站 live status 計算 |

**Getters**（均使用 `_now` 動態計算，秒級更新）:
- `priorityChannels` — 當前選中 Boss 的 `may_respawn` 或 `alive` 記錄 (按最早重生時間排序)
- `avoidChannels` — 當前選中 Boss 的 `respawning` 記錄 (按最晚重生時間排序)
- `allBossPriorityRecords` — 所有 Boss 的 `may_respawn` 記錄 (按最早重生時間排序)

**核心 Actions**:
- `updateBossRecord(record)` — 根據 `(channel, boss_type_id)` 更新或新增記錄
- `deleteBossRecord(recordId)` — 從本地 `bossRecords` 中移除指定紀錄
- `startStatusTick()` / `stopStatusTick()` — 啟動/停止每秒 tick `_now` 的 interval（由 `useRoomSession` 管理生命週期）

**`calculateCurrentStatus` (exported)**:
```typescript
import { calculateCurrentStatus } from '@/stores/bossStore'

// 在元件 computed 中取得 live status（隨 _now 每秒更新）
const status = computed(() =>
  record.value ? calculateCurrentStatus(record.value, new Date(bossStore._now)) : 'unknown'
)
```
> ⚠️ 元件顯示狀態一律用 `calculateCurrentStatus(record, new Date(bossStore._now))`，**不要讀 `record.current_status`**——後者是伺服器傳來的初始快照，不隨時間更新。

**`isExpiredRecord` 的 `nowMs` 參數**：
```typescript
// ❌ status 穩定在 'alive' 後 isExpired 不再重算
const isExpired = computed(() => isExpiredRecord(record.value, status.value))

// ✅ 傳入 bossStore._now 讓 computed 每秒重算
const isExpired = computed(() => isExpiredRecord(record.value, status.value, bossStore._now))
```
`isExpiredRecord(record, liveStatus?, nowMs?)` — 不傳 `nowMs` 時內部呼叫 `Date.now()`，但這是靜態快照，不會觸發 Vue 重算。凡是在 computed 內使用都必須傳入 `bossStore._now`。

### `recordHistoryStore` — 歷史紀錄（audit log）
**風格**: Setup (Composition API)

| State | 說明 |
|---|---|
| `records` | `shallowRef<Map<id, BossRecord>>` — 由 id 索引，避免插入重複 |
| `deletedIds` | `shallowRef<Set<number>>` — 本地刪除集合，抑制 race 到達的 upsert |
| `hasMore` / `nextCursor` | cursor 分頁狀態 |
| `isLoading` | 避免並發載入 |
| `filters` | `{ start?, end?, bossTypeId? }` |
| `sortedRecords` | `computed` — 由 id 降冪 |

**核心 Actions**:
- `setRoomId(id)` / `setFilters(filters)` — 任一變動都會 `reset()` 並中斷 in-flight 請求
- `loadMore()` — 用 `AbortController` 可中斷；回傳後以 `currentAbort === abort` 守門，舊請求結果不覆蓋
- `upsertRecord(record)` — WebSocket 收到 `boss_update` 時呼叫；被 `deletedIds` 或 `filters` 過濾掉會直接略過
- `removeRecord(id)` — WebSocket 收到 `record_deleted` 時呼叫；先加入 `deletedIds`，之後即使 race 回來也不會復活
- `reset()` — 中斷 in-flight、清空 Map/Set、重置 cursor

### `websocketStore` — WebSocket 連線
**風格**: Setup (Composition API)

**核心功能**:
- **訊息佇列**: 未連線時的訊息會被排入佇列，連線建立後自動發送
- **自動重連**: 最多 5 次，延遲遞增 (`2000ms * (attempts + 1)`)
- **心跳**: 每 30 秒發送 `ping`
- **訊息路由**: `handleMessage()` 根據 `type` 分發到對應 Store

**訊息路由表**:

| 訊息 type | 處理方式 |
|---|---|
| `pong` | 忽略 |
| `maintenance_status_update` | → `appInfoStore.setMaintenanceInfo()` |
| `room_state` | → `bossStore.setBossRecords()` + `roomStore.setUserCount()` |
| `boss_update` | → `bossStore.updateBossRecord()` + `recordHistoryStore.upsertRecord()` |
| `record_deleted` | → `bossStore.deleteBossRecord(record_id)` + `recordHistoryStore.removeRecord(record_id)` |
| `user_count_update` | → `roomStore.setUserCount()` |
| `error` | `console.error` |

### `appInfoStore` — 應用全域
**風格**: Options API

- 維護模式狀態管理
- `isMaintenanceActive` getter: `is_maintenance || is_ready_for_maintenance`

---

## Composables 模式

### `useSettings`
- **Singleton 模式**: 模組層級的 `ref` 確保所有元件共享同一份設定
- **localStorage 持久化**: `watch(settings, persist, { deep: true })`
- **設定項目**: 通知開關、音效開關、音量、最小/最大重生提醒開關、音色選擇

### `useBossAlerts`
- 監聽 `bossRecords` 變化，為每筆記錄排程 `setTimeout` 提醒
- 支援瀏覽器通知 (`useNotification`) + 音效 (`useSound`)
- 使用 `firedAlerts` Set 避免重複觸發
- 元件卸載時清理所有 timeout

### `useRecentRooms`
- localStorage 存取最近進入的房間列表
- 用於 RoomSelection 頁面的快速進入

### `useSound`
- Web Audio API 音效生成 (不依賴外部音檔)
- 內建多種音色 preset: `default`, `gentle`, `urgent`

### `useNotification`
- 封裝 `Notification.requestPermission()` & `new Notification()`

### `useTimer`
- 倒數計時器邏輯，秒級精度

### `useTheme`
- 深色模式切換 (偵測系統偏好 + 手動切換)

### `useElementPlus`
- 封裝 `ElMessage`, `ElMessageBox` 等 Element Plus 互動元件

---

## 路由配置

| 路徑 | 名稱 | 元件 | 權限 |
|---|---|---|---|
| `/` | `RoomSelection` | `RoomSelection.vue` | 無 |
| `/room/:roomId` | `BossTracker` | `BossTracker.vue` | 無 |
| `/credits` | `Credits` | `Credits.vue` | 無 |
| `/legal` | `Legal` | `LegalDisclaimer.vue` | 無 |
| `/privacy-policy` | `Privacy` | `PrivacyPolicy.vue` | 無 |
| `/maintenance` | `Maintenance` | `MaintenancePage.vue` | 無 |
| `/error` | `Error` | `ErrorPage500.vue` | 無 |
| `/admin/maintenance` | `MaintenanceAdmin` | `MaintenanceAdmin.vue` | `requiresAuth` + `requiresAdmin` |
| `/:pathMatch(.*)*` | — | redirect `/` | 無 |

### 路由守衛 (`beforeEach`)
1. 每次導航前調用 `userStore.initializeAuth()` 確保認證狀態已載入
2. `requiresAuth` 路由: 未登入 → 導向 `RoomSelection`
3. `requiresAdmin` 路由: 非管理員 → 導向 `RoomSelection`

---

## API 服務層 (`apiService.ts`)

封裝所有 HTTP 請求為統一的 class:

```typescript
class ApiService {
  // Auth
  validateToken()
  loginWithGoogle(payload)
  logout()
  initSession()
  getMe()
  refresh_token()
  updateMyPreferences(preferences)

  // Boss & Room
  getBossTypes()
  createRoom(roomId)
  checkRoomExists(roomId)
  updateRoomSettings(roomId, settings)        // PATCH: Webhook URL + 預警模式
  deleteBossRecord(roomId, recordId)          // DELETE: 撤銷紀錄

  // WebSocket
  createWebSocket()  // 建立 WSS 連線 (自動帶 cookie)

  // System
  getMaintenanceStatus()
  updateMaintenanceConfig(config)
  getWebSocketConnectionsCount()
}
```

### Axios 設定
- **Base URL**: 由環境變數 `VITE_APP_BASE_URL` 控制
- **攔截器**: 全域回應錯誤處理 (在 `handlingErrors.js` 中)
- **認證**: Cookie-based (HttpOnly)，無需手動帶 Token

---

## 國際化 (i18n)

### 設定
- 自動偵測瀏覽器語系 (`navigator.language`)
- 支援語系: `zh` (繁體中文, 預設), `en` (英文)
- Fallback: `zh`

### 翻譯檔
- `locales/zh.json` (~10KB)
- `locales/en.json` (~10KB)

### 使用方式
```vue
<template>
  {{ $t('bossTracker.roomNotFound') }}
</template>

<script setup>
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
</script>
```

**新增翻譯時**，必須同時更新 `zh.json` 和 `en.json`。

---

## 核心使用者流程

### 進入房間
1. 首頁 `RoomSelection` → 建立新房間或輸入房間 ID
2. 導航到 `/room/:roomId`
3. `BossTracker.vue` `onMounted` 呼叫 `useRoomSession().enter(roomId)`:
   - `ApiService.checkRoomExists(roomId)` — 確認房間存在，否則拋 `RoomNotFoundError`
   - `roomStore.setRoomId(roomId)`
   - `websocketStore.sendMessage({ type: 'join_room', payload: { room_id } })` — 加入房間
   - `addRecentRoom(roomId)` — 儲存至最近房間
4. WebSocket 回傳 `room_state` → `bossStore.setBossRecords()` + `bossStore.setBossTypes()`
   - **⚠️ boss_types 由 `room_state` 帶入，不再有獨立的 `getBossTypes()` HTTP call**

### 回報 Boss 狀態
1. 使用者在 `BossControlPanel` 選擇 Boss 種類 + 輸入頻道
2. 點擊 `BossStatusButton` 發送 WebSocket 訊息:
   ```json
   {
     "type": "record_boss",
     "payload": {
       "room_id": "ABCD123456",
       "channel": 12,
       "boss_type_id": 1,
       "status": "killed",
       "recorder_info": { "anonymous_id": "...", "anonymous_name": "一個路人" }
     }
   }
   ```
3. 後端計算重生時間 → 廣播 `boss_update` → 所有連線同步更新
4. 若房間有設定 Discord Webhook → 後端觸發即時推播 + 重生預警排程

### 撤銷紀錄
1. 使用者在 `RecordHistory` 點擊 `RecordItem` 上的垃圾桶按鈕
2. `RecordHistory.handleDelete()` 彈出確認對話框
3. 確認後呼叫 `ApiService.deleteBossRecord(roomId, recordId)`
4. 後端撤銷 Celery 預警任務 + 軟刪除紀錄 + WebSocket 廣播 `record_deleted`
5. 前端 `websocketStore` 接收 `record_deleted` → `bossStore.deleteBossRecord(recordId)`

### 離開房間
1. `BossTracker.vue` `onUnmounted`:
   - 發送 `leave_room` 訊息
   - 清空 `roomStore.roomId` 與 `bossStore.bossRecords`
   - **不斷開** 全域 WebSocket 連線

---

## 環境變數

| 變數 | 說明 |
|---|---|
| `VITE_APP_BASE_URL` | 後端 API 基礎 URL |
| `VITE_WS_URL` | WebSocket 連線 URL (不含 `wss://` 前綴) |
| `VITE_GOOGLE_CLIENT_ID` | Google OAuth Client ID |
| `VITE_GTM_ID` | Google Tag Manager Container ID |
| `VITE_CLARITY_ID` | Microsoft Clarity Project ID |
| `VITE_BASE_PUBLIC_PATH` | Vite base public path |
| `VITE_APP_TITLE` | 應用標題 |

**注意**: `.env.development` 的 `VITE_WS_URL` 指向 `localhost:1254`，`.env.production` 指向 `boss-timer.jaao.tw/api`。Docker 建置前端時使用 `.env.production`，因此 Docker 內的前端 WebSocket 會連到正式環境。開發測試時請用 `npm run dev` 讀取 `.env.development`。

---

## 開發慣例與守則

### 元件開發
1. **Composition API**: 新增元件優先使用 `<script setup>` + Composition API
2. **現有元件**: 部分 Store 使用 Options API (歷史原因)，維護時維持一致風格
3. **命名**: PascalCase 元件名，camelCase props/emit
4. **Props 驗證**: 所有 `defineProps` 都應加上型別約束
5. **Tailwind CSS**: v4 語法，使用 `@tailwindcss/vite` plugin

### 狀態管理
1. 業務邏輯放在 Store 的 actions 中，元件只負責 UI
2. Store 間可互相引用 (如 `websocketStore` 在 `userStore.initializeAuth()` 中被調用)
3. 使用 `storeToRefs()` 解構 reactive state，避免失去響應性
4. WebSocket 訊息分發統一在 `websocketStore.handleMessage()` 處理

### Composable 開發
1. **命名**: `use<Feature>.ts`
2. **Singleton 模式**: 需要全域共享時，將 `ref` 宣告在函式外部 (如 `useSettings`)
3. **清理**: 使用 `onUnmounted` 清理 timer / listener / subscription
4. **返回值**: 返回需要暴露的 reactive state 和 methods

### API 調用
1. 所有 HTTP 請求透過 `apiService` 單例
2. WebSocket 訊息透過 `websocketStore.sendMessage()` 送出 (自動佇列 + 重連感知)
3. Cookie-based 認證，Axios 不需手動設定 Authorization header

### 國際化
1. 所有使用者可見文字 **必須** 使用 `t('key')` 或 `$t('key')`
2. 新增翻譯同時更新 `zh.json` 和 `en.json`
3. 使用巢狀 key 結構 (如 `bossTracker.roomNotFound`)

### 新增頁面
1. 在 `views/` 建立 Vue 元件
2. 在 `router/index.ts` 新增路由 (使用 lazy import)
3. 需要認證的頁面加上 `meta: { requiresAuth: true }`
4. 管理員頁面加上 `meta: { requiresAdmin: true }`

### 新增元件
1. 在 `components/` 建立 Vue 元件
2. Element Plus 元件透過 `unplugin-vue-components` 自動引入，不需手動 import
3. 使用 Tailwind CSS 處理樣式
4. 使用 Element Plus `dark/css-vars.css` 支援深色模式

### Element Plus 主色 (style.css)
`src/style.css` 已在 `:root` 與 `html.dark` 中完整定義 Element Plus primary 色階，對應 Tailwind gray 調色盤：

| CSS 變數 | light (gray-700) | dark (gray-400) |
|---|---|---|
| `--el-color-primary` | `#374151` | `#9ca3af` |
| `--el-color-primary-light-3` | `#737a85` | `#6b7280` |
| `--el-color-primary-light-5` | `#9ba0a8` | `#4b5563` |
| `--el-color-primary-light-7` | `#c3c6cb` | `#374151` |
| `--el-color-primary-light-8` | `#d7d9dc` | `#1f2937` |
| `--el-color-primary-light-9` | `#ebebee` | `#111827` |
| `--el-color-primary-dark-2` | `#2c3441` | `#d1d5db` |

**勿**在元件內用 `--el-color-primary: #6366f1` 覆寫單一按鈕顏色；若需品牌色請修改 `style.css` 以維持全站一致。

---

## Vite 設定重點

### Path Alias
| Alias | 路徑 |
|---|---|
| `@` | `src/` |
| `@images` | `src/assets/images/` |
| `@icons` | `src/assets/icons/` |
| `@public` | `public/` |

### 開發伺服器
- **HTTPS**: 使用本地 SSL 憑證 (`vite.pem`, `vite-key.pem`)
- **Port**: 5173
- **Proxy**: `/api` → `https://localhost:1254` (去除 `/api` 前綴)

### 插件
- `@vitejs/plugin-vue` — Vue SFC 支援
- `@tailwindcss/vite` — Tailwind CSS v4
- `unplugin-element-plus` — Element Plus 按需引入
- `unplugin-auto-import` — 自動引入 API (Element Plus)
- `unplugin-vue-components` — 自動引入元件 (Element Plus)
- `vite-plugin-html-env` — HTML 環境變數注入
