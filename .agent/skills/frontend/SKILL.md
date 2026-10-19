---
name: Boss Timer Frontend 開發規範
description: Vue 3 前端架構、元件結構、Pinia 狀態管理、WebSocket 通訊、Composables 模式、路由與國際化慣例。適用於所有前端相關的開發、修改與除錯任務。新增元件、i18n、Element Plus UI 請參考子 skill：frontend-components。
---

# Boss Timer Frontend 開發規範

## 專案總覽

Boss Timer 前端是一個 **Vue 3 + Vite** 單頁應用 (SPA)，提供房間制的即時 Boss 重生狀態追蹤介面。  
支援 Google 帳號登入 / 匿名使用、多國語言 (i18n)、深色模式、瀏覽器通知與音效提醒。  
支援 Discord Webhook 設定與紀錄撤銷功能。

---

## 技術棧

| 項目 | 技術 | 版本 |
|---|---|---|
| 框架 | Vue.js 3 (Composition API + Options API 混用) | ^3.5 |
| 建置工具 | Vite | ^6.3 |
| 狀態管理 | Pinia | ^3.0 |
| 伺服器狀態查詢 | TanStack Vue Query（目前只用於登入狀態的查詢） | ^5 |
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
| 測試 | Vitest + jsdom（只測登入同步等不需要畫面的邏輯，#71） | ^3.2 |
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
    ├── queryClient.ts            # TanStack Vue Query 的 QueryClient（main.ts 以 VueQueryPlugin 掛載）
    ├── stores/__tests__/         # userStore 的規則測試（Vitest）
    ├── axios/__tests__/          # 全域錯誤處理的規則測試（Vitest）
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
    │   └── websocketStore.ts     # WebSocket 連線管理 (連線/斷線/重連)
    │
    ├── services/
    │   └── apiService.ts         # API 服務層 (封裝所有 HTTP/WS 調用)
    │
    ├── axios/
    │   ├── index.ts              # Axios 實例建立 (自訂 AxiosInstance class, 含 interceptor)
    │   └── handlingErrors.ts     # 全域 Axios 錯誤處理
    │
    ├── composables/              # Vue Composables (可複用邏輯)
    │   ├── useLocalStorage.ts    # 通用 localStorage 基礎層 (load/deserialize/watch-persist；其他分頁改了同一個 key 時跟著更新)
    │   ├── useBossAlerts.ts      # Boss 重生提醒 (通知 + 音效排程)
    │   ├── useNotification.ts    # 瀏覽器 Notification API 封裝
    │   ├── useSound.ts           # Web Audio API 音效播放 (含多種音色)
    │   ├── useSettings.ts        # 使用者設定 (通知、音效、音量，localStorage 持久化)
    │   ├── useFavoriteBosses.ts  # 收藏 Boss 列表 (localStorage 持久化)
    │   ├── useRecentRooms.ts     # 最近房間記錄 (localStorage)
    │   ├── useChannelViewPreference.ts # 頻道檢視偏好 (localStorage)
    │   ├── useStatusConfig.ts    # 狀態色彩/排序/isExpiredRecord 統一定義
    │   ├── useLayoutConfig.ts    # 版面 Widget 排列、寬度、收合狀態管理 (singleton)
    │   ├── useRoomSession.ts     # 房間進出封裝 (enter/leave，確認 Room 存在後才 setRoomId)
    │   ├── useTimer.ts           # 倒數計時器邏輯
    │   ├── useElementPlus.ts     # Element Plus 封裝 (showMessage, showDialog)
    │   └── useTheme.ts           # 深色模式切換
    │
    ├── components/               # Vue 元件（依領域分子目錄，完整清單見 frontend-components skill）
    │   ├── AppHeader.vue         # 頂部導航列 (房間 ID 顯示、設定按鈕、語系切換、登入)
    │   ├── AppFooter.vue         # 底部頁尾
    │   ├── boss/                 # BossControlPanel / BossInfo / BossInfoItem / BossStatusButton
    │   ├── channel/              # ChannelCard / ChannelOverview / ChannelTimeline / ChannelView / RecommendedChannels
    │   ├── layout/               # EditModeToolbar / LayoutItemWrapper（版面編輯模式）
    │   ├── record/               # RecordHistory / RecordItem
    │   ├── room/                 # RoomManager
    │   ├── settings/             # SettingsModal + 各設定 Tab（Preferences / Changelog / Support / CustomBosses / Feedback）
    │   └── ui/                   # AdBanner / CountdownTimer / GoogleLoginButton / MaintenanceBanner / RecommendedSection(已棄用) / StatusBadge
    │
    ├── views/                    # 頁面視圖 (對應路由)
    │   ├── RoomSelection.vue     # 首頁: 房間選擇 / 建立 / 最近房間
    │   ├── BossTracker.vue       # 主頁: Boss 追蹤器 (含所有核心元件)
    │   ├── UserGuide.vue         # 使用教學頁
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
| `anonymousName` | `string \| null` | 匿名使用者暱稱 (localStorage) |

**核心 Actions**:
- `initializeAuth()` — 開始查詢登入狀態（`/auth/session`，由伺服器判斷），第一次判斷完成後連線 WebSocket（細節見下方「登入狀態的查詢守則」）
- `loginWithGoogle(payload)` — Google 登入：照登入回應顯示（同時通知其他分頁），再重新查詢；失敗時不動登入狀態、往外丟（登入按鈕只在未登入時顯示，沒有「換帳號」流程）
- `logout()` — 進行中再呼叫共用同一次（`_logoutPromise`）。先打 `/auth/logout`，**成功才**清掉本分頁的畫面並重新查詢；取得匿名身分後才清 `user_info`（同時通知其他分頁，讓它們沿用同一個匿名身分），查詢失敗也照樣清掉並通知。`/auth/logout` 失敗時什麼都不動、往外丟，`RoomSelection` 顯示「登出失敗」：HttpOnly cookie 前端清不掉，只有 API 成功才算登出
- `updatePreferences(preferences)` — 更新使用者偏好設定：先寫進 `user.preferences` 與 `user_info`（快取仍是同一個登入者時）再存檔；失敗時本地保留、經 `showFailure` 提示「設定儲存失敗」（全站已處理的錯誤不重複，#66）

#### ⚠️ 登入狀態的查詢守則（ADR-0009，照 NextAuth 前端的模型）

動這段前務必讀 ADR-0009「跨分頁同步」。PR #64 曾在舊架構上逐一補特例，連續八輪審查都在這裡找到新問題，**勿再加計數器、重試迴圈或通知特例**。

1. **登入狀態只由伺服器判斷**
   以 TanStack Vue Query 的單一查詢（`['auth', 'session']`，`QueryObserver` 訂閱）呼叫 `apiService.initSession()`，結果在 `_fetchSession` 套用：`authenticated` → `_applyServerUser(user)`（處理帳號偏好，見第 6 條，勿直接呼叫 `setLoggedInUser`）；`anonymous` → `becomeAnonymous()`。access token 過期時伺服器會以 refresh token 順便換發，登入失效時會清掉舊的登入 cookie、改發匿名身分。**勿在前端自己換發或重新驗證**（已移除 `tryRefreshToken()`、`validateToken()`）。

2. **每個分頁只有一個查詢，何時查詢是固定的**
   開頁；切回分頁（`refetchOnWindowFocus`，`QueryClient` 要經 `VueQueryPlugin` 掛載才會生效）；本分頁登入、登出，或收到其他分頁的 `LOGIN` / `LOGOUT` 時呼叫 `_refetchSession()`：先 `cancelQueries` 取消進行中的請求（是 cookie 改變前送出的；`queryFn` 有傳 `signal`，取消時請求中斷、結果不套用到畫面，但回應標頭已到的話瀏覽器仍會套用 Set-Cookie），再重新查詢。只用 `invalidateQueries` 不夠：查詢還沒有任何結果時，Vue Query 不會取消進行中的請求。`App.vue` 的 `onMounted` 與 router `beforeEach` 首次載入時會同時呼叫 `initializeAuth()`，以 `_initPromise` 共用同一次初始化。

3. **WebSocket 只在身分不同時重連**（`_syncWebSocket`）
   開頁第一次判斷完成（成功或失敗）才 `connect()`。之後查詢成功時，伺服器回答的身分（`user:{id}` / `anon:{id}` / `none`）和 `_wsIdentity` 不同才 `reconnect()`；查詢失敗時，期間登入 / 登出過（`_cookieChanged`）才照目前的 cookie 重連。

4. **改變 `user_info` 的分頁負責通知**（`_writeUserInfo`）
   `user_info` 是所有分頁共用的顯示快取：變成沒有登入廣播 `LOGOUT`，變成另一個登入者（含從沒有變有）廣播 `LOGIN`。登入、登出、發現登入失效都由這一條處理；收到通知的分頁重新查詢時快取已是新狀態，不會再通知，多個分頁同時發現登入失效也只由第一個通知。`user_info` 寫不進去（`writeCachedUser` 回傳 false）時不通知：快取沒變，否則分頁之間會互相觸發。**勿另外呼叫 `notifyLogin()` / `notifyLogout()`。** `LOGIN` 仍帶 `user`，只給部署切換期間的舊版前端用。

5. **判斷失敗不改變登入狀態**
   網路錯誤、5xx、429 不代表登入失效：沿用目前的顯示（開頁時以 `restoreUserFromStorage()` 從 `user_info` 恢復，沒有就顯示匿名），**什麼都不清除、不通知**，也不自動重試（`retry: false`），等下一次觸發再問。查詢帶 `skipGlobalErrorHandler`，不跳維護 / 錯誤頁、不提示；伺服器真的掛掉時，`App.vue` 接著的 `checkMaintenanceStatus()` 會帶到維護頁或錯誤頁。`networkMode: 'always'`：離線時照樣送出、失敗就沿用顯示，不要暫停到恢復連線；請求有 10 秒逾時，網路卡住沒有回應時也不會讓開頁一直等。套用結果出錯時仍以 `finally` 完成初始化，`user_info` 寫不進去（`writeCachedUser`）只記錄、不中斷。使用中途遇到 401 代表伺服器已判斷登入失效（需要登入的 API 在 access token 過期時會自己換發），interceptor 呼叫 `handleLoginLost()` 照登出的順序處理，**不確認、不重送**，勿在前端自己換發（已移除 `refresh_token()`）或讓 token 保持有效。後端 IP 天花板會讓同 IP 的人互相影響（見 ADR-0007），勿改回「任何錯誤都清除登入」。

6. **帳號偏好只在換人時套用到本地**（`_applyServerUser`，CONTEXT.md「跨裝置同步」）
   伺服器回答（查詢成功或登入回應）的登入者和 `_preferencesUserId` 不同時（開頁、登入、換成另一個人）才套用帳號偏好並遞增 `preferencesVersion`，`App.vue` 據此呼叫各 composable 的 `syncFromUser()`。同一個人的回答只更新帳號資料、保留目前的 `user.preferences`。`updatePreferences` 先把存的項目寫進 `user.preferences` 再送出（回應先後顛倒也不會改回舊值）；`user_info` 的偏好也是這台裝置目前的偏好，一改就寫入、不等存檔結果，只在快取仍是同一個登入者時直接寫入，不經 `_writeUserInfo`、不通知（其他分頁已登出時不寫回）。**勿改回「每次查詢都同步偏好」**（PR #64 第 8～11 輪：存檔中的先後順序一直出問題；要即時同步得另外把偏好做成獨立查詢）。`becomeAnonymous()` 清掉 `_preferencesUserId`，再登入時一定套用。

7. **改這段邏輯前，先寫一個會失敗的測試**
   上面每一條規則都對應 `src/stores/__tests__/userStore.test.ts` / `src/axios/__tests__/handlingErrors.test.ts` 的一組測試（`describe` 的編號對應規則）。修 bug 或改規則時先寫重現的測試、確認失敗，再改程式。#59、#60 的審查約 20 輪多數是「兩件事剛好同時發生」的時序問題，靠審查推演一直收斂不了。測試以假的 `apiService` / `websocketStore` / `BroadcastChannel` 控制每次 `/auth/session` 何時、回答什麼（`answer()`），時序情境照這個寫法加。

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
- `allBossPriorityRecords` — 所有 Boss 的 `may_respawn` 記錄 (按最早重生時間排序)，供 `RecommendedChannels` 使用

**核心 Actions**:
- `updateBossRecord(record)` — 根據 `(channel, boss_type_id)` 更新或新增記錄；早於換輪分界線（`clearedAt`）或比現有紀錄舊的紀錄會被忽略
- `deleteBossRecord(recordId, replacement?)` — 移除指定紀錄；有 `replacement`（前一筆仍有效的紀錄）時由它接手該頻道
- `clearBossTypeRecords(bossTypeId, clearedAt)` — 記錄換輪分界線並移除該 Boss 種類的紀錄（收到 `boss_type_cleared` WS 事件時呼叫）
- `setClearedAt(lastClearedAt)` — 從 `room_state.last_cleared_at` 載入各 Boss 種類的換輪分界線
- `addCustomBossType(bossType)` / `removeCustomBossType(bossTypeId)` — 自訂 Boss 增刪（冪等，HTTP 回應與 WS 廣播都會呼叫）；移除時若正被選取，改選 `resolveBossTypeId` 的結果
- `markSelfDeletingBossType(id)` / `unmarkSelfDeletingBossType(id)` — 標記自己發起的刪除，讓 `boss_type_deleted` 廣播只對其他成員跳提示
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
- **`sendMessage()` 不排隊**: 只在連線中送出並回傳 `true`；未連線時觸發重連、丟棄訊息並回傳 `false`。連線建立時重建伺服器端狀態——身分由 cookie 決定、`onopen` 依 `roomStore.roomId` 重新 `join_room`，所以不需要補送。`record_boss` 刻意不補送（紀錄時間以伺服器收到為準），`BossControlPanel` 依回傳值顯示離線提示。心跳已過期但計時器還沒觸發（剛從休眠喚醒）時不送出、直接重連並回傳 `false`
- **身分由伺服器在握手時依 cookie 決定**：前端不送身分欄位，`BossControlPanel` 回報只帶 `anonymous_name`
- **`reconnect()`**: 以目前的 cookie 重新建立連線。**身分在握手時固定**，由 `userStore` 在登入狀態的查詢結果與連線身分不同時呼叫（見 userStore「登入狀態的查詢守則」第 3 條）
- **連線模型照 Socket.IO（engine.io v4，ADR-0008）**，勿自創機制或加特例：
  - **只連一次**：`initializeAuth()` 第一次完成時連線，之後換頁不呼叫 `connect()`（會繞過退避），斷線一律交給自動重連
  - **心跳逾時**：伺服器連線後先送 `hello`（`ping_interval` / `ping_timeout`），之後每 25 秒送 `heartbeat`。收到 `hello` 才啟動逾時，每次心跳重新計時，超過兩者相加（45 秒）沒收到就關閉並退避重連。**不分前景背景、不探測、前端不送 `ping`**：背景節流的是計時器，心跳照常送達，逾時只會晚觸發、不會誤判。連到不送 `hello` 的舊後端時不啟動逾時
  - **自動重連**：`min(30s, 1s × 2^次數) × (1 ± 0.5)`，**不放棄**。**收到伺服器第一則訊息才重置次數、清除 `isReconnecting`**（不在 `onopen`）：伺服器拒絕時是「接受後立刻關閉」且不送訊息，在 `onopen` 重置會一直以最短間隔重連。心跳逾時等主動判定斷線時走退避、不重置次數。握手卡在 CONNECTING 超過 20 秒（`CONNECT_TIMEOUT_MS`）就放棄；`createWebSocket()` 丟例外時同樣交給退避；`offline` 事件立刻關閉進入退避，`online` 不特別處理
  - 每個 socket 事件都先檢查 `socket.value === ws`，`connect()` 開新連線前先 `dropSocket()` 清掉仍在 CLOSING 的舊連線：被取代的舊連線遲到的 `onclose` 不可動到新連線（會變成兩條活連線）
  - 重連中 `isReconnecting` 為 true，`BossTracker` 的 `ConnectionBanner` 據此顯示「正在重新連線」（超過 2 秒才顯示）。伺服器以 close code **4429**（連線限制）關閉時照一般斷線退避重連（多半是休眠喚醒時舊連線的名額還沒釋放；被拒絕時伺服器不送訊息，次數不會重置，間隔自然拉長，**不另加特例**），連續被擋只在第一次顯示「連線數已達上限」提示，收到伺服器訊息或 `reconnect()`（換身分）後重新計算。登出後即使登入狀態的查詢失敗也會重連（期間登出過），避免 WS 停留在登入身分
- **訊息路由**: `handleMessage()` 根據 `type` 分發到對應 Store

**訊息路由表**:

| 訊息 type | 處理方式 |
|---|---|
| `hello` | 依 `ping_interval` + `ping_timeout` 啟動心跳逾時 |
| `heartbeat` | 重新計時心跳逾時 |
| `maintenance_status_update` | → `appInfoStore.setMaintenanceInfo()` |
| `room_state` | → `bossStore.setBossTypes()` + `roomStore.setRoomSettings()` + `setClearedAt()` + `setBossRecords()` + `roomStore.setUserCount()` |
| `boss_update` | → `bossStore.updateBossRecord()` + `recordHistoryStore.upsertRecord()` |
| `record_deleted` | → `bossStore.deleteBossRecord(record_id, replacement)` + `recordHistoryStore.removeRecord(record_id)` |
| `boss_type_cleared` | → `bossStore.clearBossTypeRecords(boss_type_id, cleared_at)` |
| `boss_type_added` | → `bossStore.addCustomBossType()` |
| `boss_type_deleted` | → `bossStore.removeCustomBossType()` + `recordHistoryStore.removeBossType()`；被其他成員刪掉且正被選取時跳提示 |
| `room_settings_updated` | → `roomStore.setRoomSettings()`（`SettingsPreferences` 只套用有變動的欄位） |
| `user_count_update` | → `roomStore.setUserCount()` |
| `error` | 依 `code`：`rate_limited` → 警告提示；`record_rejected` → 「回報未被記錄」錯誤提示；其他僅 `console.error`（連線限制改以 close code 4429 通知，見上方「自動重連」） |

### `appInfoStore` — 應用全域
**風格**: Options API

- 維護模式狀態管理
- `isMaintenanceActive` getter: `is_maintenance || is_ready_for_maintenance`

---

## Composables 模式

### `useLocalStorage`（同一台裝置的分頁之間同步）
- 監聽 `storage` 事件（只送到其他分頁）：其他分頁改了同一個 key 就重新讀取（清空、刪掉時回到預設值）。收藏 Boss、頻道檢視、設定、最近房間都經它，舊分頁才不會拿舊的整份值存檔、蓋掉其他分頁剛存的（#67）
- **套用其他分頁的值時不寫回**：記下這次套用的內容，`watch` 寫入前比對，相同就略過（值沒變就不賦值，標記不會殘留）。否則其他分頁刪掉的 key 會被重新寫回，讀取時正規化的值還會再觸發其他分頁一輪。`watch` 用預設的 flush，同一輪的修改只寫一次，勿改成 `flush: 'sync'`（每改一個欄位就寫一次、通知其他分頁一次）
- deserializer 收到的是 `JSON.stringify` 後的字串，要先 `JSON.parse` 再檢查（頻道檢視曾直接比對原始字串，設定從來沒存起來）
- **只能在模組層級呼叫**（監聽不會移除）：現有呼叫端都是模組層級的單例。勿在 scope 結束時停止監聽與寫入——模組第一次在某個元件裡載入的話，元件卸載會讓整個 app 停止存檔
- 接受的取捨：新開分頁時載入帳號的偏好，經 localStorage 同步到其他分頁；還在存檔中的修改可能被改回帳號的值（毫秒等級的時序）
- `useLayoutConfig` 直接讀寫 `localStorage`，另外監聽 `boss_tracker_layout`；**正在編輯版面時不套用**，不蓋掉還沒存的修改，離開編輯時以這個分頁的版面為準
- 接受的取捨：收藏、版面是整份存檔，兩個分頁在同步送達前幾毫秒內各自存同一項時，以最後存的為準（後端 `||` 只保證不同項目不互相丟失）
- 「顯示擊殺紀錄」只存在 `user.preferences` / `user_info`：`userStore` 監聽 `user_info`，同一個登入者時套用其他分頁的偏好
- 測試：`src/composables/__tests__/crossTabPreferences.test.ts`、`src/stores/__tests__/userStore.test.ts`（6b）

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
| `/guide` | `Guide` | `UserGuide.vue` | 無 |
| `/credits` | `Credits` | `Credits.vue` | 無 |
| `/legal` | `Legal` | `LegalDisclaimer.vue` | 無 |
| `/privacy-policy` | `Privacy` | `PrivacyPolicy.vue` | 無 |
| `/maintenance` | `Maintenance` | `MaintenancePage.vue` | 無 |
| `/error` | `Error` | `ErrorPage500.vue` | 無 |
| `/admin/maintenance` | `MaintenanceAdmin` | `MaintenanceAdmin.vue` | `requiresAuth` + `requiresAdmin` |
| `/:pathMatch(.*)*` | — | redirect `/` | 無 |

### 路由守衛 (`beforeEach`)
1. 每次導航前調用 `userStore.initializeAuth()` 確保認證狀態已載入
2. `canAccess(route)`：`requiresAuth` 路由要已登入、`requiresAdmin` 路由要是管理員，否則導向 `RoomSelection`
3. 停在頁面時登入狀態改變（登入失效、其他分頁登出、切回分頁時的查詢）：`App.vue` watch `canAccess(route)`，不能再停留就回首頁。使用中途遇到 401 而發現登入失效的分頁，interceptor 另外提示並回首頁

---

## API 服務層 (`apiService.ts`)

封裝所有 HTTP 請求為統一的 class:

```typescript
class ApiService {
  // Auth
  loginWithGoogle(payload)
  logout()
  initSession()
  updateMyPreferences(preferences)

  // Boss & Room
  createRoom(roomId)
  checkRoomExists(roomId)
  updateRoomSettings(roomId, settings)        // PATCH: Webhook URL + 預警模式
  deleteBossRecord(roomId, recordId)          // DELETE: 撤銷紀錄
  getRoomRecordsHistory(...)                  // 歷史紀錄 cursor 分頁
  createCustomBossType(...)                   // 自訂 Boss 建立
  deleteCustomBossType(roomId, bossTypeId)    // 自訂 Boss 刪除
  clearBossTypeRecords(roomId, bossTypeId)    // 清除頻道總覽（換輪）

  // Feedback
  listFeedback(sort)
  createFeedback(payload)
  voteFeedback(feedbackId)
  updateFeedbackStatus(feedbackId, status)    // Admin
  deleteFeedback(feedbackId)                  // Admin

  // WebSocket
  createWebSocket()  // 建立 WSS 連線 (自動帶 cookie)

  // System
  getMaintenanceStatus()
  updateMaintenanceConfig(config)
}
```

### Axios 設定
- **Base URL**: 由環境變數 `VITE_APP_BASE_URL` 控制
- **攔截器**: 全域回應錯誤處理 (在 `handlingErrors.ts` 中，ADR-0009「使用中途遇到 401」)：網路錯誤與 503 跳維護頁、5xx 跳錯誤頁、429 提示「操作太頻繁」（`detail.code === 'feedback_daily_limit'` 的回饋每日上限交給回饋頁）、401 代表登入失效：原本顯示為登入時提示「登入已失效」並回首頁（`handleLoginLost()`；之後接著的 401、正因 cookie 改變而重新查詢時的 401 不處理；顯示匿名時重新查詢一次以清掉失效的登入 cookie）；進行中的全域跳頁不被之後的 401 蓋掉；呼叫端自己取消的請求不處理。登入狀態的查詢（`initSession`）帶 `skipGlobalErrorHandler: true`，失敗由呼叫端處理
- **呼叫端的失敗提示**: 一律用 `showFailure(error, 訊息)`（勿直接 `showMessage.error`），全域已處理（跳頁或已提示）就不再顯示，同一個錯誤不會出現兩個提示。要導頁前先問 `isNavigatedGlobally(error)`，全域已跳頁就不要再導頁
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
4. 後端撤銷 Celery 預警任務 + 軟刪除紀錄 + WebSocket 廣播 `record_deleted`（附 `replacement`：該頻道前一筆仍有效的紀錄，不跨過換輪分界線）
5. 前端 `websocketStore` 接收 `record_deleted` → `bossStore.deleteBossRecord(recordId, replacement)`，與重新整理後看到的狀態一致

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

### 全域 button reset (style.css)
`style.css` 在 `@layer base` 中對 `button:not(.el-button)` / `[role="button"]:not(.el-button)` 設定 `background-color/border-color: transparent`，用來隔離 Element Plus 全域樣式。兩條鐵則：

1. **必須放在 `@layer base` 內** — 移出 layer 後 selector specificity (0,1,1) 會蓋過 Tailwind utility class (0,1,0)，導致元件上的 `bg-*` 全部失效
2. **用 `transparent` 不用 `initial`** — `initial` 在 button 上等於瀏覽器預設的白色 `ButtonFace`，淺色主題下會出現看不見的白底按鈕

原生 `<button>` + Tailwind class 是正確做法，**勿**因樣式吃不到而改用 `<div>`（會失去鍵盤操作、`:disabled`、語意）。

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
- **HTTPS**: 使用本地 SSL 憑證 (`vite.pem`, `vite-key.pem`)，僅在 `isDev` 模式載入；production build（Docker）略過以避免 ENOENT 錯誤
- **Port**: 5173
- **Proxy**: `/api` → `https://localhost:1254` (去除 `/api` 前綴)

### 建置與型別檢查
- `npm run build` = `npm run typecheck && npm run test && vite build` — **build 前強制跑型別檢查（`vue-tsc --noEmit -p tsconfig.app.json`）與測試（`vitest run`）**，任一失敗都會讓 build（含 Docker/CI）直接失敗
- 單獨檢查型別：`npm run typecheck`；單獨跑測試：`npm test`（設定在 `vitest.config.ts`，只載入 `@` alias、jsdom 環境；測試檔在 `src/**/__tests__/`，不在 app 的型別檢查裡）

### 插件
- `@vitejs/plugin-vue` — Vue SFC 支援
- `@tailwindcss/vite` — Tailwind CSS v4
- `unplugin-element-plus` — Element Plus 按需引入
- `unplugin-auto-import` — 自動引入 API (Element Plus)
- `unplugin-vue-components` — 自動引入元件 (Element Plus)
- `vite-plugin-html-env` — HTML 環境變數注入
