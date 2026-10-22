---
name: Boss Timer Backend 開發規範
description: FastAPI 後端架構、資料庫模型、服務層模式、WebSocket 協議、Celery 非同步任務、認證流程與開發慣例。適用於所有後端相關的開發、修改與除錯任務。細項請參考子 skill：backend-api（路由/Schema）、backend-database（ORM/Migration）、backend-celery-webhook（Celery/Webhook）。
---

# Boss Timer Backend 開發規範

## 專案總覽

Boss Timer 是一款為楓之谷世界 (Artale, 楓星...) 設計的即時 Boss 重生計時器。  
後端使用 **FastAPI + SQLAlchemy + PostgreSQL**，透過 **WebSocket** 實現房間內所有使用者的即時狀態同步，並透過 **Celery + Redis** 實現非同步任務佇列 (如 Discord Webhook 推播)。

---

## 技術棧

| 項目 | 技術 |
|---|---|
| 框架 | FastAPI |
| ORM | SQLAlchemy (同步模式) |
| 資料庫 | PostgreSQL |
| 認證 | Google OAuth 2.0 + JWT (access + refresh token) |
| 即時通訊 | WebSocket (原生 FastAPI WebSocket) |
| 非同步任務 | Celery + Redis (Broker & Backend) |
| 設定管理 | pydantic-settings + python-dotenv |
| 套件管理 | uv (pyproject.toml + uv.lock) |
| 限流 | limits（記憶體計數，`dependencies.rate_limit()`） |
| 部署 | Docker + Docker Compose + Nginx (反向代理) |
| 資料庫遷移 | Alembic |
| Python 版本 | 3.11+ |

---

## 專案結構

```
app/
├── main.py                # 應用程式進入點、Lifespan、CORS、路由註冊
├── config.py              # pydantic-settings 設定類 (Settings)
├── celery_app.py          # Celery 應用設定 (broker/backend/task routing)
├── dependencies.py        # 全域依賴注入 (限流器、ConnectionManager、身份驗證工具函式)
├── maintenance.json       # 維護模式開關設定檔 (JSON)
│
├── database/
│   ├── database.py        # SQLAlchemy engine（pool_pre_ping=True、connect_timeout 5 秒、TCP keepalive / tcp_user_timeout 10 秒）、SessionLocal、Base、get_db()
│   └── models.py          # ORM 模型定義 (User, Room, BossType, BossRecord, FeedbackItem, FeedbackVote, RefreshToken)
│
├── schemas/
│   ├── auth.py            # Pydantic 資料模型: 認證相關 (Login, Token, User, Session, RecorderInfo)
│   ├── boss.py            # Pydantic 資料模型: Boss 相關 (BossRecordCreate, BossRecordResponse, BossTypeResponse)
│   ├── room.py            # Pydantic 資料模型: 房間相關 (RoomCreate, RoomResponse, RoomExists, RoomSettingsUpdate)
│   └── feedback.py        # Pydantic 資料模型: 回饋 / 許願 (FeedbackCreate, FeedbackResponse, FeedbackStatusUpdate, FeedbackVoteResponse)
│
├── routers/
│   ├── auth.py            # 認證路由: Google 登入、Token 刷新/驗證、登出、Session 初始化、偏好設定
│   ├── rooms.py           # 房間路由: 建立房間、檢查房間是否存在、更新房間設定
│   ├── bosses.py          # Boss 路由: 取得 Boss 類型列表、刪除(撤銷)紀錄
│   ├── websocket.py       # WebSocket 路由: 連線管理、訊息處理 (join/leave/record_boss)
│   ├── system.py          # 系統路由: 維護模式資訊讀取/更新 (管理員限定)
│   └── feedback.py        # 回饋路由: 清單 / 提交 / Toggle 投票 / Admin 改狀態 / 刪除
│
├── services/
│   ├── auth_service.py          # 認證服務: Google Token 驗證、JWT 生成/驗證、使用者 CRUD、偏好設定
│   ├── boss_service.py          # Boss 服務: 重生時間計算、紀錄寫入、WebSocket 廣播
│   ├── notification_policy.py   # Discord 通知策略: 即時推播 + Celery 預警排程（從 boss_service 提取）
│   ├── room_service.py          # 房間服務: 房間建立/查詢、使用者加入/離開房間、取得房間完整狀態
│   └── feedback_service.py      # 回饋服務: 可見性過濾、10/day rate limit、toggle 投票、狀態管理
│
├── websocket/
│   ├── manager.py         # ConnectionManager: 連線追蹤、房間訂閱、Room 廣播、全域廣播
│   └── handlers.py        # (保留檔案，目前邏輯在 routers/websocket.py 中)
│
├── tasks/
│   ├── cleanup.py         # 背景任務: 每小時清理超過 7 天不活躍的房間與歸檔記錄
│   └── webhook_tasks.py   # Celery 任務: Discord Webhook 發送 (含自動重試與速率限制)
│
├── utils/
│   ├── datetime_helper.py # 日期時間工具函式
│   ├── id_generator.py    # ID 生成工具
│   └── jwt_helper.py      # JWT 相關工具函式
│
├── Dockerfile             # Docker 映像定義 (使用 uv sync)
├── .env.example           # 環境變數範本
└── .env                   # 環境變數 (不納入版本控制)
```

---

## 資料庫模型 (ORM Models)

### User
| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | `BigInteger` PK | 主鍵 |
| `google_id` | `String(255)` UNIQUE | Google 帳號唯一識別 |
| `email` | `String(255)` UNIQUE | Email |
| `display_name` | `String(100)` | 顯示名稱 |
| `avatar_url` | `Text` | 頭像 URL |
| `preferences` | `JSONB` | 使用者偏好設定 (如 `showRecordHistory`) |
| `is_admin` | `Boolean` | 管理員標記 |
| `created_at` | `DateTime(tz)` | 建立時間 |
| `last_login_at` | `DateTime(tz)` | 最後登入時間 |

**關聯**: `records` → BossRecord, `room_associations` → RoomUser, `refresh_tokens` → RefreshToken

### Room
| 欄位 | 類型 | 說明 |
|---|---|---|
| `room_id` | `String(10)` PK | 10 碼大寫英數字房間 ID |
| `created_at` | `DateTime(tz)` | 建立時間 |
| `last_active` | `DateTime(tz)` | 最後活躍時間 |
| `is_active` | `Boolean` | 是否存活 (超過 7 天標記為 False) |
| `discord_webhook_url` | `String(1000)` nullable | Discord Webhook URL |
| `webhook_alert_type` | `String(20)` nullable | 預警模式: `min`, `max`, `both`, `none` |
| `last_cleared_at` | `JSONB` | 各 Boss 種類的最後清除時間（key = boss_type_id str, value = ISO timestamp），`server_default='{}'` |

### BossType
| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | `Integer` PK | 主鍵 |
| `name_en` | `String(50)` UNIQUE | 英文名稱 |
| `name_zh` | `String(50)` | 中文名稱 |
| `min_respawn_minutes` | `Integer` | 最小重生時間 (分鐘) |
| `max_respawn_minutes` | `Integer` | 最大重生時間 (分鐘) |
| `description` | `Text` | 描述 |

### BossRecord
| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | `BigInteger` PK | 主鍵 |
| `room_id` | FK → Room | 所屬房間 |
| `channel` | `Integer` ≥ 1 | 頻道號碼 |
| `boss_type_id` | FK → BossType | Boss 種類 |
| `status` | `String(20)` | 原始狀態: `alive`, `killed`, `not_found` |
| `recorded_at` | `DateTime(tz)` | 記錄時間 |
| `respawn_min_time` | `DateTime(tz)` | 最早重生時間 |
| `respawn_max_time` | `DateTime(tz)` | 最晚重生時間 |
| `recorder_id` | FK → User (nullable) | 記錄者 (登入使用者) |
| `recorder_info` | `JSONB` | 匿名記錄者資訊 (`anonymous_id`, `anonymous_name`) |
| `is_archived` | `Boolean` | 是否已歸檔 (撤銷時設為 True) |
| `celery_task_ids` | `JSONB` nullable | 記錄排程推播的 Celery Task ID (`min_task_id`, `max_task_id`) |

**Computed Property**: `current_status` — 根據當前時間計算動態狀態:
- `status == 'killed'` 且 `now >= max_respawn_time` → `alive`
- `status == 'killed'` 且 `now >= min_respawn_time` → `may_respawn`
- `status == 'killed'` 其他 → `respawning`
- 其他 → 原始 status

### FeedbackItem
| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | `BigInteger` PK | 主鍵 |
| `type` | `String(20)` | `bug` / `feature`（CheckConstraint）|
| `title` | `String(200)` | 必填 |
| `description` | `Text` nullable | 選填 |
| `status` | `String(20)` | `pending` / `open` / `planning` / `done` / `rejected`（CheckConstraint），預設 `pending` |
| `created_by` | FK → User (nullable) | `ondelete="SET NULL"` |
| `created_at` | `DateTime(tz)` | 建立時間 |

**索引**: `(status, created_at)`、`(created_by)`

**可見性規則**（Service 層處理）:
- `pending` / `rejected` 只有 `created_by == viewer` 或 admin 看得到
- 其他狀態所有人可見

### FeedbackVote
| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | `BigInteger` PK | 主鍵 |
| `feedback_id` | FK → FeedbackItem | `ondelete="CASCADE"` |
| `user_id` | FK → User | `ondelete="CASCADE"` |
| `created_at` | `DateTime(tz)` | 建立時間 |

**約束**: `UNIQUE(feedback_id, user_id)` — 一帳號一票
**投票邏輯**: Service 層 `toggle_vote()`，已有紀錄則 DELETE、沒紀錄則 INSERT

### RoomUser (多對多關聯)
| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | `BigInteger` PK | 主鍵 |
| `room_id` | FK → Room | 房間 |
| `user_id` | FK → User (nullable) | 登入使用者 |
| `anonymous_session_id` | `String(100)` (nullable) | 匿名使用者 |
| `joined_at` | `DateTime(tz)` | 加入時間 |
| `last_seen` | `DateTime(tz)` | 最後活躍時間 |

**約束**: `user_id` 或 `anonymous_session_id` 至少一個非 NULL。

### RefreshToken
| 欄位 | 類型 | 說明 |
|---|---|---|
| `id` | `Integer` PK | 主鍵 |
| `user_id` | FK → User | 所屬使用者 |
| `jti` | `String` UNIQUE | JWT ID (用於撤銷) |
| `token` | `Text` | 完整 Token |
| `expires_at` | `DateTime` | 過期時間 |
| `created_at` | `DateTime` | 建立時間 |

---

## Celery 非同步任務架構

### 設定 (`celery_app.py`)
- **Broker & Backend**: Redis (`redis_url` 環境變數，預設 `redis://localhost:6379/0`)
- **Task Routing**: `app.tasks.webhook_tasks.*` → `discord_queue`
- **序列化**: JSON

### 雙 Worker 分流
| Worker | Queue | Concurrency | 說明 |
|---|---|---|---|
| `celery_worker_fast` | `celery` (default) | 4 | 一般高速內部任務 |
| `celery_worker_discord` | `discord_queue` | 1 | Discord 推播 (嚴格限速，避免觸發 429) |

### Discord Webhook 任務 (`webhook_tasks.py`)
```python
@celery_app.task(bind=True, max_retries=3, rate_limit="2/s")
def send_discord_webhook(self, webhook_url, content=None, embeds=None):
```
- HTTP 429 (Rate Limited) → 自動等待 `retry_after` 後重試
- 網路錯誤 → 指數退避重試 (`2 ** retries` 秒)

### Webhook 推播流程 (`notification_policy.py`)
推播邏輯已從 `boss_service.py` 提取為獨立的 `NotificationPolicy` class，`boss_service` 建立記錄後呼叫 `NotificationPolicy.notify(record, room, db)`：

1. **即時推播** (`_send_immediate`): 依 `webhook_notify_events` 過濾，符合則立即 `send_discord_webhook.delay()`，Discord 失敗不影響 BossRecord 建立
2. **預警排程** (`_schedule_alerts`): `killed` 狀態時，根據 `webhook_alert_type` 設定：
   - `min` → 最短重生時間前 5 分鐘預警
   - `max` → 最長重生時間前 5 分鐘預警
   - `both` → 兩者皆發
   - `none` → 不發預警
3. **任務追蹤**: 排程的 Celery Task ID 存入 `boss_record.celery_task_ids`

### 紀錄撤銷流程 (`bosses.py` DELETE endpoint)
1. 呼叫 `celery_app.control.revoke(task_id)` 撤銷排程中的預警任務
2. 將紀錄標記為 `is_archived = True` (軟刪除)
3. 以 `room_service.get_effective_record()` 找出該頻道前一筆仍有效的紀錄（與 `get_room_state` 共用同一套有效條件：未撤銷、2 天內、不早於換輪分界線）
4. WebSocket 廣播 `record_deleted`（含 `replacement`）通知所有連線客戶端

---

## 認證流程

### Google OAuth 登入
1. 前端透過 `vue3-google-login` 取得 Google `credential` (ID Token) 或 `code` (Authorization Code)
2. `POST /auth/google` — 後端驗證 Google Token / 交換 Code，建立或更新使用者
3. 生成 JWT access token (30 分鐘) + refresh token (30 天)
4. Token 透過 **HttpOnly Cookie** 設置 (`access_token`, `refresh_token`)
5. 回傳 `LoginResponse` 包含 user 資訊

### Token 刷新
- `POST /auth/refresh` — 從 Cookie 讀取 refresh token → 驗證 → 生成新的 access token。只供部署切換期間的舊版前端，新前端使用中途遇到 401 改問 `/auth/session`（ADR-0009），日後與 `/auth/validate` 一起刪除

### Token 驗證
- `POST /auth/validate` — 支援 `Authorization: Bearer <token>` Header 或 `access_token` Cookie。只供部署切換期間的舊版前端，日後刪除

### 開頁判斷登入狀態 / 匿名使用者 Session
- `POST /auth/session` — **登入狀態只由伺服器判斷（ADR-0009）**：登入有效回 `authenticated` + user（access token 過期時以 refresh token 順便換發），登入已失效時清掉舊的登入 cookie、改以匿名回應；登入判斷與 WebSocket 握手共用 `resolve_login()`（詳見 backend-api skill「開頁判斷登入狀態」）。未登入時確保有伺服器簽發的匿名身分：cookie 為 httponly 的「UUID.簽章」；沒有、編造或簽章上線前的舊 cookie 一律發放新身分（不換發舊 UUID），受每個 IP 的發放上限限制（詳見 backend-api skill「匿名使用者」）

### 安全設定
- `samesite='lax'`, `secure=True` (生產環境)
- refresh token 存入資料庫，支援撤銷
- 每位使用者只保留一個有效 refresh token

---

## WebSocket 協議

### 連線建立
- Endpoint: `ws://<host>/api/ws/`
- **身分由伺服器在握手時以 `resolve_identity(websocket)` 決定**（有登入 cookie 時查資料庫，經 `run_db()` 呼叫，最多等資料庫鎖 15 秒（比前端放棄握手的 20 秒短）；匿名握手不碰資料庫）：access token 有效且使用者存在 → access token 無效時改用 refresh token（資料庫確認未撤銷；背景分頁常在 access token 過期後才重連）→ 簽章的匿名 cookie → 無（登入者的判斷與 `/auth/session` 共用 `resolve_login()`，ADR-0009；查資料庫失敗或等不到鎖時 endpoint 記 error log（完整堆疊一分鐘最多一次，#76）並拒絕這次握手（還沒 accept，uvicorn 回 HTTP 403、前端看到 1006），前端照一般斷線退避重連、資料庫恢復後照完整判斷連上；**勿退回較低的身分**：身分在握手時固定，前端看到的身分沒變就不會重連，#61）。連同限流 key 存在該連線的 `Connection`，**整條連線固定不變**；登入 / 登出時前端重新連線，前端送來的任何身分欄位都不採信
- 使用全域 Singleton `ConnectionManager` 管理所有連線

### 訊息格式 (JSON)
所有訊息皆為 JSON，結構為 `{ "type": "<msg_type>", "payload": { ... } }`

#### Client → Server

| type | payload | 說明 |
|---|---|---|
| `ping` | — | **舊版前端**的應用層 ping，伺服器回 `pong`（新版前端不送，改由伺服器心跳；部署切換期間仍需相容），**不以它判斷連線生死**。死連線由 uvicorn 協定層 WebSocket ping 偵測，設定只在 `app/Dockerfile` 的 `UVICORN_WS*`（`websockets` 實作、間隔 20 秒、逾時 60 秒）。設計與禁忌見 ADR-0008 |
| `join_room` | `{ "room_id": "ABCD123456" }` | 加入房間，取得初始狀態 |
| `leave_room` | `{ "room_id": "..." }` | 離開房間 |
| `record_boss` | `BossRecordCreate` 完整欄位 | 回報 Boss 狀態。記錄者由伺服器身分決定：登入者寫 `recorder_id`；匿名者的 `anonymous_id` 取自簽章 cookie，**payload 的 `recorder_info.anonymous_id` 一律忽略**，只採用 `anonymous_name` |
| `authenticate` / `deauthenticate` | — | **已移除**：身分在握手時固定，登入 / 登出改為重連。部署切換期間舊版前端仍可能送出，伺服器直接忽略 |

#### Server → Client

| type | 說明 |
|---|---|
| `hello` | 連線接受後的第一則訊息：`{ "ping_interval": 25, "ping_timeout": 20 }`（`app/websocket/manager.py` 的 `HEARTBEAT_*`），前端據此啟動心跳逾時（照 engine.io 的 open 封包，ADR-0008）。被連線限制拒絕時不送 |
| `heartbeat` | lifespan 的 `run_heartbeat()` 每 25 秒送給所有連線，讓前端偵測無聲中斷 |
| `pong` | 回應舊版前端的 `ping` |
| `room_state` | 加入房間時的完整初始狀態 (boss_records + boss_types + last_cleared_at + room_settings)；重連時用來重建所有房間狀態 |
| `boss_update` | 單筆 Boss 記錄更新 (BossRecordResponse) |
| `record_deleted` | 紀錄被撤銷 (`{ "record_id": N, "room_id": "...", "replacement": BossRecordResponse \| null }`) |
| `boss_type_added` | 房間新增自訂 Boss（BossTypeResponse） |
| `boss_type_deleted` | 房間刪除自訂 Boss（`{ "boss_type_id": N, "name": "..." }`），其紀錄已 CASCADE 刪除 |
| `room_settings_updated` | 房間 Webhook 設定變更（RoomResponse） |
| `boss_type_cleared` | 某 Boss 種類頻道總覽被清除（`{ "boss_type_id": N, "cleared_at": "..." }`） |
| `user_count_update` | 房間內目前連線人數 (`{ "count": N }`) |
| `maintenance_status_update` | 維護模式狀態變更 |
| `error` | 錯誤訊息（`{ "code": "...", "message": "..." }`；`code`：`room_not_found` / `record_rejected` / `rate_limited`） |

### Rate Limiting (WebSocket)
與 HTTP 相同的雙層限流（`check_dual_limit`，個人額度以伺服器身分計算、重連不會歸零；IP 天花板為個人額度 × `IP_CEILING_MULTIPLIER`，登入者以自己的身分計算，見 ADR-0007）：

| 限制 | 個人 | IP 天花板 | 超過時 |
|---|---|---|---|
| `record_boss` | `RECORD_BOSS_LIMIT` 30/分鐘、1000/天 | × 200 | 回 `error` `rate_limited` |
| 握手頻率 | `HANDSHAKE_LIMIT` 170/10 分鐘（約 1000/小時，撞到上限最多 10 分鐘恢復；所有分頁共用；#43 已修，部署後觀察重連頻率再收緊） | × 200 | 接受後立即以 close code **4429**（reason `connection_limited`）關閉，不另送訊息 |
| 同時連線數 | `MAX_CONNECTIONS` 10 | × 200 | 同上 |

前端收到 4429 照一般斷線退避重連（多半是休眠喚醒時舊連線的名額還沒釋放，約 90 秒內恢復；ADR-0008），連續被擋只提示一次。先檢查握手頻率、再檢查同時連線數，**勿對調**：對調的話被連線數擋下的嘗試不計入握手頻率，可以不受限制地一直重試。

### ConnectionManager 架構
```
ConnectionManager
├── active_connections: Set[WebSocket]        # 所有連線
├── room_subscriptions: Dict[str, Set[WS]]   # room_id → 訂閱的 WS
├── socket_to_room: Dict[WS, str]            # WS → 目前所在 room_id
├── _connection_keys: Dict[WS, Set[str]]     # WS → 握手時計入的連線數 key
├── _outboxes: Dict[WS, (Queue, Task)]      # 每條連線的送出佇列與寫出 task（ADR-0008）
└── _connection_counts: Counter              # 同時連線數，個人（personal:）與天花板（ceiling:）分開計；try_reserve 在 await 前一次完成檢查與計入
```

**⚠️ 送訊息一律經送出佇列**（照 engine.io 的 writeBuffer，ADR-0008）: 送給單一連線用 `manager.send(websocket, message)`，廣播用 `broadcast_to_room` / `broadcast_to_all`，**勿直接 `websocket.send_text`**（會繞過佇列、打亂順序，`hello` 也不再保證是第一則）。廣播只放進佇列、不等送出，一條收不下的連線不會拖住呼叫端。送出失敗，或同一則訊息從開始送出算起超過 `SEND_STALL_SECONDS`（45 秒，= 心跳間隔 + 逾時）還送不出去（對方停止接收後約 90 秒內一定關閉：緩衝沒塞滿時由協定層 ping，塞滿時由這個計時），寫出 task 就關閉該連線並移除其佇列，**勿在 manager 裡 `disconnect()`**——清理一律交給該連線 endpoint 的 `finally`，它才會一併廣播房間人數。**勿以為協定層 ping 會關閉收不下的連線**：ping 要先寫進同一個塞滿的緩衝才開始計時，這種情況永遠不會逾時，所以才有 `SEND_STALL_SECONDS`。

---

## 服務層模式

### 設計原則
1. **Router 層**: 只負責 HTTP 請求/回應處理、參數驗證、錯誤包裝
2. **Service 層**: 包含所有業務邏輯。Router 調用 Service 完成工作
3. **Model/Schema 分離**: SQLAlchemy Model 做資料庫存取，Pydantic Schema 做 API 序列化/驗證

### boss_service.py 模式
- 使用 **靜態方法類** (`BossService`) 聚合相關邏輯
- 方法鏈（全部同步）: `_validate_room_exists` → `_get_boss_type_by_id` → `_calculate_respawn_times` → `_create_boss_record`
- `record_boss(db, record, identity, broadcast)` 寫入紀錄，先以 `broadcast` 回呼廣播 `boss_update`（WebSocket handler 傳入 `manager.broadcast_to_room_from_thread`，回到 event loop），再排程 Discord 通知；handler 經 `run_db()` 呼叫（ADR-0010）
- 建立完成後呼叫 `NotificationPolicy.notify(record, room, db)` 處理推播（Discord 失敗不影響主流程）

### room_service.py 模式
- 函式直接導出 (非類別)
- `get_room_state()` 使用 `joinedload` 避免 N+1 查詢
- 預先載入 `BossRecord.recorder` 和 `BossRecord.boss_type`
- 使用 PostgreSQL `DISTINCT ON (channel, boss_type_id)` 在 DB 端去重，回傳筆數被 `channels × boss_types` 綁定
- 以 `ROOM_STATE_WINDOW_DAYS = 2` 過濾 `recorded_at`，讓頻道總覽只反映近期活躍頻道（歷史紀錄 API 不受影響）

### auth_service.py 模式
- Google Token 驗證: 支援 credential (ID Token 直接驗證) 和 code (Authorization Code 交換)
- 用戶偏好白名單: `ALLOWED_PREFERENCE_KEYS = {"showRecordHistory", "channelViewMode", "favoriteBossIds", "bossTrackerLayout"}`
- 偏好存檔在資料庫的同一個 `UPDATE` 裡以 jsonb `||` 合併這次存的項目（`update_user_preferences`，#68）。**勿改回讀出整份、改一項、整份寫回**：兩個同時的存檔會丟掉其中一項（`tests/test_preferences.py` 只檢查 SQL 結構，測試環境沒有 PostgreSQL；改這段時用臨時 PostgreSQL 容器實際跑過）
- 防止任意 JSON 注入

---

## API 路由

### 認證 (`/auth`)
| Method | Path | Auth | Rate Limit | 說明 |
|---|---|---|---|---|
| POST | `/auth/google` | 無 | 10/min | Google 登入/註冊 |
| POST | `/auth/refresh` | Cookie | 30/min | 刷新 access token（只供舊版前端；新前端遇到 401 改問 `/auth/session`，日後刪除） |
| POST | `/auth/validate` | Header/Cookie | 60/min | 驗證 token 有效性（只供舊版前端，日後刪除） |
| GET | `/auth/me` | Cookie | 60/min | 取得當前使用者資訊 |
| POST | `/auth/logout` | Cookie | 10/min | 登出 + 撤銷 refresh token |
| PUT | `/auth/me/preferences` | Cookie | 30/min | 更新使用者偏好設定 |
| POST | `/auth/session` | Cookie (可選) | 60/min | 開頁判斷登入狀態（ADR-0009），需要時換發 / 清 cookie / 發匿名身分 |

### 房間 (`/room`)
| Method | Path | Auth | Rate Limit | 說明 |
|---|---|---|---|---|
| POST | `/room/` | 無 | 15/min、50/day | 建立新房間 |
| GET | `/room/{room_id}/exists` | 無 | 15/min | 檢查房間是否存在 |
| PATCH | `/room/{room_id}/settings` | 無 | 30/min | 更新房間設定 (Webhook URL, 預警模式) |

### Boss (`/boss`)
| Method | Path | Auth | 說明 |
|---|---|---|---|
| GET | `/boss/boss-types` | 無 | 取得所有 Boss 類型列表，15/min |
| POST | `/boss/room/{room_id}/boss-types` | 無 | 新增房間自訂 Boss，30/min |
| DELETE | `/boss/room/{room_id}/boss-types/{boss_type_id}` | 無 | 刪除房間自訂 Boss，30/min |
| GET | `/boss/room/{room_id}/records` | 無 | 歷史紀錄 cursor 分頁（`before_id` / `limit` / `start` / `end` / `boss_type_id`），60/min |
| DELETE | `/boss/room/{room_id}/records/{record_id}` | 無 | 撤銷紀錄 + 撤銷 Celery 預警任務，15/min |
| POST | `/boss/room/{room_id}/boss-types/{boss_type_id}/clear` | 無（任何人） | 清除指定 Boss 種類頻道總覽、撤銷 Celery 預警、廣播 `boss_type_cleared`，10/min |

### 系統 (`/system`)
| Method | Path | Auth | Rate Limit | 說明 |
|---|---|---|---|---|
| GET | `/system/maintenance-info` | 無 | 60/min | 讀取維護模式設定 |
| POST | `/system/maintenance-config` | Admin | 10/min | 更新維護模式設定 + WebSocket 廣播 |

### 回饋 / 許願 (`/feedback`)
| Method | Path | Auth | Rate Limit | 說明 |
|---|---|---|---|---|
| GET | `/feedback/` | 匿名可看 | 60/min | 取得清單；`sort=votes\|newest`；pending/rejected 僅自己 / admin 可見，done 永遠排最下 |
| POST | `/feedback/` | 登入 | 20/min | 建立回饋（pending）；同帳號每日上限 10 筆 |
| POST | `/feedback/{id}/vote` | 登入 | 60/min | Toggle 投票（一帳號一票） |
| PATCH | `/feedback/{id}` | Admin | 60/min | 更新狀態（含 pending → open 核准） |
| DELETE | `/feedback/{id}` | Admin | 30/min | 硬刪除（含投票 CASCADE） |

### WebSocket (`/ws`)
| Method | Path | 說明 |
|---|---|---|
| GET | `/ws/connections/count` | 取得目前 WebSocket 連線總數，60/min |
| WS | `/ws/` | WebSocket 連線端點 |

---

## 維護模式

- 透過 `maintenance.json` 控制，支援熱更新
- `is_maintenance: true` → 所有受保護路由回傳 503
- `is_ready_for_maintenance: true` → 顯示即將維護的橫幅
- 狀態變更時透過 WebSocket 廣播通知所有連線客戶端
- Admin 可透過 `/system/maintenance-config` API 即時切換

---

## 背景任務

### cleanup_inactive_rooms (asyncio)
- **頻率**: 每 1 小時
- **邏輯**: 標記 `last_active < 7 天前` 的房間為 `is_active = False`，並將所屬 Boss 記錄標記為 `is_archived = True`（`archive_inactive_rooms()` 同步、批次更新，拿著 `db_lock()` 以 `anyio.to_thread` 執行，不在 event loop 上查資料庫，ADR-0010）
- **啟動**: 在 FastAPI lifespan 中以 `asyncio.create_task` 方式啟動

### run_heartbeat (asyncio)
- **頻率**: 每 25 秒（`HEARTBEAT_INTERVAL_SECONDS`）
- **邏輯**: `ConnectionManager.run_heartbeat()` 對所有 WebSocket 連線送 `{"type": "heartbeat"}`，前端據此偵測無聲中斷（ADR-0008）
- **啟動**: 在 FastAPI lifespan 中以 `asyncio.create_task` 方式啟動

### send_discord_webhook (Celery)
- **Queue**: `discord_queue` (由 `celery_worker_discord` 獨佔處理)
- **Rate Limit**: `2/s` (Task 層) + `concurrency=1` (Worker 層) 雙重限速
- **重試**: 最多 3 次，HTTP 429 時按 `retry_after` 等待，網路錯誤時指數退避

---

## 環境變數

| 變數 | 說明 | 預設值 |
|---|---|---|
| `DB_USER` | 資料庫使用者 | — |
| `DB_PASSWORD` | 資料庫密碼 | — |
| `DB_HOST` | 資料庫主機 | — |
| `DB_PORT` | 資料庫埠 | `5432` |
| `DB_NAME` | 資料庫名稱 | — |
| `SECRET_KEY` | JWT 簽名金鑰 | `your-secret-key` |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | — |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Client Secret | — |
| `ALLOWED_ORIGINS` | CORS 允許來源 (逗號分隔) | — |
| `VERSION` | 應用版本號 | `1.0.0` |
| `ENV` | 環境 (`development` / `production`) | `development` |
| `REDIS_URL` | Redis 連線 URL (Celery Broker) | `redis://localhost:6379/0` |

---

## 開發慣例與守則

### 新增 API 端點
0. 用到資料庫的端點宣告成 `def`，勿在 `async def` 裡直接查詢（ADR-0010，見 backend-api skill）
1. 在 `schemas/` 定義 Pydantic 輸入/輸出模型
2. 在 `services/` 實作業務邏輯
3. 在 `routers/` 註冊路由，調用 Service，處理例外
4. 在 `main.py` 的 `app.include_router(...)` 註冊路由器
5. 需要維護模式保護的路由加上 `dependencies=[Depends(check_maintenance_mode)]`

### 新增 ORM Model
1. 在 `database/models.py` 定義 Model 類別
2. 使用 Alembic 產生與執行 migration: `alembic revision --autogenerate -m "description"` → `alembic upgrade head`
3. Model 須使用 `DateTime(timezone=True)` 確保時區感知
4. 使用 `server_default=func.now()` 設定資料庫端預設時間

### 新增 Celery 任務
1. 在 `app/tasks/` 建立任務模組
2. 使用 `@celery_app.task(bind=True)` 裝飾器
3. 在 `celery_app.py` 的 `include` 列表加入模組路徑
4. 需要分流的任務在 `task_routes` 中配置對應 Queue

### Pydantic Schema 慣例
- 回應模型加上 `model_config = ConfigDict(from_attributes=True)` 以支援 ORM → Schema 轉換
- 使用 `Field(...)` 加上驗證約束 (min_length, max_length, ge, le)
- 敏感資訊模型分離: `User` (完整) vs `PublicUser` (僅公開欄位)

### WebSocket 開發慣例
- 新增訊息類型: 在 `routers/websocket.py` 的 `handle_message()` 中加入新的 `if msg_type == "..."` 分支
- 廣播: 在 event loop 上（async handler）用 `await manager.broadcast_to_room()` / `broadcast_to_all()`；在 threadpool 裡（`def` 端點、`run_db` 執行的函式）用 `manager.broadcast_to_room_from_thread()` / `broadcast_to_all_from_thread()`，勿直接呼叫 async 版本（沒有 await，廣播不會執行）
- 所有 WebSocket 訊息須做好安全驗證 (如檢查送訊者是否在目標房間內)
- **⚠️ DB Session 模式**: WebSocket endpoint **不可**使用 `Depends(get_db)` — 這會讓 DB 連線長持整個 WS 生命週期導致 connection pool 耗盡。改用 `with SessionLocal() as db:` 短暫取用，用完即還給 pool。**查資料庫的部分寫成同步函式、經 `run_db()` 執行**（拿資料庫鎖、在 threadpool；`_record_boss`，session 在函式裡開。唯一例外是加入房間：訂閱也要在鎖裡，所以自己 `async with db_lock()`），handler 本身留在 event loop 上操作 `ConnectionManager`（它的狀態不是 thread-safe，勿整段丟進 threadpool，ADR-0010）
- **`ping` 訊息**直接回 `pong` 並 `continue`，不進 `handle_message`、不碰資料庫

### 錯誤處理
- Router 層使用 `HTTPException` 回傳適當 HTTP 狀態碼
- Service 層使用 `logging.error()` 記錄內部錯誤
- WebSocket 錯誤透過 `manager.send(websocket, {"type": "error", ...})` 回傳（經送出佇列，勿直接 `send_text`）
- **連線何時關閉**（ADR-0008）：
  - 無法解析（二進位 frame、非 JSON 物件、`type` 非字串、`payload` 非物件）→ 以 **1007** 關閉，記 info（照 engine.io）
  - `handle_message` 拋例外 → 只記錄、**連線保留**（照 Socket.IO）。**勿改成出錯就關閉**：前端重連後 `hello` 會重置退避，資料庫故障時會變成每秒重連、耗盡握手額度後被 4429 擋下
  - endpoint 其他非預期錯誤（含握手）→ 先清理（移出房間、更新人數）再以 **1011** 關閉。**勿刪這個關閉**：uvicorn 在 app 返回時不會關閉傳輸，前端會以為還連著、回報無聲遺失
- `join_room` 取得 `room_state` 成功後才訂閱房間，出錯時不留在房間裡
- Celery 任務錯誤透過 `self.retry()` 自動重試

### 安全守則
- ⚠️ 使用者偏好設定更新必須過白名單 (`ALLOWED_PREFERENCE_KEYS`)
- ⚠️ 匿名記錄者資訊使用結構化的 `RecorderInfo` schema，防止任意 JSON 注入
- ⚠️ Room ID 路徑參數限制長度: `min_length=10, max_length=10`
- ⚠️ 管理員端點使用 `Depends(get_current_admin_user)` 保護
- ⚠️ 所有 HTTP API 以路由層級的 dependency 掛上 `rate_limit()` 雙層限流（`dependencies=[rate_limit("15/minute")]`，個人額度 + 真實 IP ×200 天花板，見 ADR-0007 與 backend-api skill）；勿改回包在端點外面的 decorator（#82）
- ⚠️ 限流與匿名身分一律經 `app/utils/identity.resolve_identity()` 判斷；需要登入的 API 用 `dependencies.get_current_user` / `get_optional_user`（以 `resolve_login` 判斷，access token 過期時在回應換發，401 只代表登入失效）。勿自己解析 JWT 或信任 cookie 原值（JWT 一律經 `decode_token_user_id()`，會檢查 access / refresh 類型）
- ⚠️ Celery Worker 不使用 root 執行 (Docker 中建議加 `--uid` 參數)
