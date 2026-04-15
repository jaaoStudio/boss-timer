---
name: Boss Timer Backend 開發規範
description: FastAPI 後端架構、資料庫模型、服務層模式、WebSocket 協議、Celery 非同步任務、認證流程與開發慣例。適用於所有後端相關的開發、修改與除錯任務。細項請參考子 skill：backend-api（路由/Schema）、backend-database（ORM/Migration）、backend-celery-webhook（Celery/Webhook）。
---

# Boss Timer Backend 開發規範

## 專案總覽

Artale Boss Timer 是一款為楓之谷世界 (Artale) 設計的即時 Boss 重生計時器。  
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
| 限流 | slowapi |
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
│   ├── database.py        # SQLAlchemy engine、SessionLocal、Base、get_db()
│   └── models.py          # ORM 模型定義 (User, Room, BossType, BossRecord, RoomUser, RefreshToken)
│
├── schemas/
│   ├── auth.py            # Pydantic 資料模型: 認證相關 (Login, Token, User, Session, RecorderInfo)
│   ├── boss.py            # Pydantic 資料模型: Boss 相關 (BossRecordCreate, BossRecordResponse, BossTypeResponse)
│   └── room.py            # Pydantic 資料模型: 房間相關 (RoomCreate, RoomResponse, RoomExists, RoomSettingsUpdate)
│
├── routers/
│   ├── auth.py            # 認證路由: Google 登入、Token 刷新/驗證、登出、Session 初始化、偏好設定
│   ├── rooms.py           # 房間路由: 建立房間、檢查房間是否存在、更新房間設定
│   ├── bosses.py          # Boss 路由: 取得 Boss 類型列表、刪除(撤銷)紀錄
│   ├── websocket.py       # WebSocket 路由: 連線管理、訊息處理 (join/leave/record_boss)
│   └── system.py          # 系統路由: 維護模式資訊讀取/更新 (管理員限定)
│
├── services/
│   ├── auth_service.py    # 認證服務: Google Token 驗證、JWT 生成/驗證、使用者 CRUD、偏好設定
│   ├── boss_service.py    # Boss 服務: 重生時間計算、紀錄寫入、WebSocket 廣播、Discord Webhook 推播
│   └── room_service.py    # 房間服務: 房間建立/查詢、使用者加入/離開房間、取得房間完整狀態
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

### Webhook 推播流程 (`boss_service.py`)
1. **即時廣播**: 擊殺/標記時立即發送消息到 Discord
2. **預警排程**: `killed` 狀態時，根據 `webhook_alert_type` 設定：
   - `min` → 最短重生時間前 5 分鐘預警
   - `max` → 最長重生時間前 5 分鐘預警
   - `both` → 兩者皆發
   - `none` → 不發預警
3. **任務追蹤**: 排程的 Celery Task ID 存入 `boss_record.celery_task_ids`

### 紀錄撤銷流程 (`bosses.py` DELETE endpoint)
1. 呼叫 `celery_app.control.revoke(task_id)` 撤銷排程中的預警任務
2. 將紀錄標記為 `is_archived = True` (軟刪除)
3. WebSocket 廣播 `record_deleted` 事件通知所有連線客戶端

---

## 認證流程

### Google OAuth 登入
1. 前端透過 `vue3-google-login` 取得 Google `credential` (ID Token) 或 `code` (Authorization Code)
2. `POST /auth/google` — 後端驗證 Google Token / 交換 Code，建立或更新使用者
3. 生成 JWT access token (30 分鐘) + refresh token (30 天)
4. Token 透過 **HttpOnly Cookie** 設置 (`access_token`, `refresh_token`)
5. 回傳 `LoginResponse` 包含 user 資訊

### Token 刷新
- `POST /auth/refresh` — 從 Cookie 讀取 refresh token → 驗證 → 生成新的 access token

### Token 驗證
- `POST /auth/validate` — 支援 `Authorization: Bearer <token>` Header 或 `access_token` Cookie

### 匿名使用者 Session
- `POST /auth/session` — 若無 access_token 且無 anonymous_user_id cookie，建立新的 UUID 匿名 ID

### 安全設定
- `samesite='lax'`, `secure=True` (生產環境)
- refresh token 存入資料庫，支援撤銷
- 每位使用者只保留一個有效 refresh token

---

## WebSocket 協議

### 連線建立
- Endpoint: `ws://<host>/api/ws/`
- 連線時自動從 Cookie 讀取 `access_token` 解析使用者身份 (可選，也支援匿名)
- 使用全域 Singleton `ConnectionManager` 管理所有連線

### 訊息格式 (JSON)
所有訊息皆為 JSON，結構為 `{ "type": "<msg_type>", "payload": { ... } }`

#### Client → Server

| type | payload | 說明 |
|---|---|---|
| `ping` | — | 心跳 (每 30 秒) |
| `join_room` | `{ "room_id": "ABCD123456" }` | 加入房間，取得初始狀態 |
| `leave_room` | `{ "room_id": "..." }` | 離開房間 |
| `record_boss` | `BossRecordCreate` 完整欄位 | 回報 Boss 狀態 |
| `authenticate` | `{ "token": "<jwt>" }` | 連線期間動態切換為已登入身份 |
| `deauthenticate` | — | 連線期間切換為匿名身份 |

#### Server → Client

| type | 說明 |
|---|---|
| `pong` | 心跳回應 |
| `room_state` | 加入房間時的完整初始狀態 (boss_records + boss_types) |
| `boss_update` | 單筆 Boss 記錄更新 (BossRecordResponse) |
| `record_deleted` | 紀錄被撤銷 (`{ "record_id": N, "room_id": "..." }`) |
| `user_count_update` | 房間內目前連線人數 (`{ "count": N }`) |
| `maintenance_status_update` | 維護模式狀態變更 |
| `error` | 錯誤訊息 |

### Rate Limiting (WebSocket)
- `record_boss` 訊息: 每連線每 60 秒最多 30 次
- 超過限制回傳 error 訊息

### ConnectionManager 架構
```
ConnectionManager
├── active_connections: Set[WebSocket]        # 所有連線
├── room_subscriptions: Dict[str, Set[WS]]   # room_id → 訂閱的 WS
├── socket_to_room: Dict[WS, str]            # WS → 目前所在 room_id
└── socket_to_user: Dict[WS, int]            # WS → user_id
```

---

## 服務層模式

### 設計原則
1. **Router 層**: 只負責 HTTP 請求/回應處理、參數驗證、錯誤包裝
2. **Service 層**: 包含所有業務邏輯。Router 調用 Service 完成工作
3. **Model/Schema 分離**: SQLAlchemy Model 做資料庫存取，Pydantic Schema 做 API 序列化/驗證

### boss_service.py 模式
- 使用 **靜態方法類** (`BossService`) 聚合相關邏輯
- 方法鏈: `_validate_room_exists` → `_get_boss_type_by_id` → `_calculate_respawn_times` → `_create_boss_record`
- 建立記錄後立即廣播到房間
- 擊殺記錄同時觸發 Discord Webhook 推播與預警排程

### room_service.py 模式
- 函式直接導出 (非類別)
- `get_room_state()` 使用 `joinedload` 避免 N+1 查詢
- 預先載入 `BossRecord.recorder` 和 `BossRecord.boss_type`

### auth_service.py 模式
- Google Token 驗證: 支援 credential (ID Token 直接驗證) 和 code (Authorization Code 交換)
- 用戶偏好白名單: `ALLOWED_PREFERENCE_KEYS = {"showRecordHistory"}`
- 防止任意 JSON 注入

---

## API 路由

### 認證 (`/auth`)
| Method | Path | Auth | 說明 |
|---|---|---|---|
| POST | `/auth/google` | 無 | Google 登入/註冊 |
| POST | `/auth/refresh` | Cookie | 刷新 access token |
| POST | `/auth/validate` | Header/Cookie | 驗證 token 有效性 |
| GET | `/auth/me` | Cookie | 取得當前使用者資訊 |
| POST | `/auth/logout` | Cookie | 登出 + 撤銷 refresh token |
| PUT | `/auth/me/preferences` | Cookie | 更新使用者偏好設定 |
| POST | `/auth/session` | Cookie (可選) | 初始化使用者 Session (匿名/已登入) |

### 房間 (`/room`)
| Method | Path | Auth | Rate Limit | 說明 |
|---|---|---|---|---|
| POST | `/room/` | Session | 5/min | 建立新房間 |
| GET | `/room/{room_id}/exists` | 無 | 15/min | 檢查房間是否存在 |
| PATCH | `/room/{room_id}/settings` | Session | 30/min | 更新房間設定 (Webhook URL, 預警模式) |

### Boss (`/boss`)
| Method | Path | Auth | 說明 |
|---|---|---|---|
| GET | `/boss/boss-types` | 無 | 取得所有 Boss 類型列表 |
| DELETE | `/boss/room/{room_id}/records/{record_id}` | Session | 撤銷紀錄 + 撤銷 Celery 預警任務 |

### 系統 (`/system`)
| Method | Path | Auth | 說明 |
|---|---|---|---|
| GET | `/system/maintenance-info` | 無 | 讀取維護模式設定 |
| POST | `/system/maintenance-config` | Admin | 更新維護模式設定 + WebSocket 廣播 |

### WebSocket (`/ws`)
| Method | Path | 說明 |
|---|---|---|
| GET | `/ws/connections/count` | 取得目前 WebSocket 連線總數 |
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
- **邏輯**: 標記 `last_active < 7 天前` 的房間為 `is_active = False`，並將所屬 Boss 記錄標記為 `is_archived = True`
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
- 廣播: 使用 `manager.broadcast_to_room()` 或 `manager.broadcast_to_all()`
- 所有 WebSocket 訊息須做好安全驗證 (如檢查送訊者是否在目標房間內)

### 錯誤處理
- Router 層使用 `HTTPException` 回傳適當 HTTP 狀態碼
- Service 層使用 `logging.error()` 記錄內部錯誤
- WebSocket 錯誤直接透過 `websocket.send_text(json.dumps({"type": "error", ...}))` 回傳
- Celery 任務錯誤透過 `self.retry()` 自動重試

### 安全守則
- ⚠️ 使用者偏好設定更新必須過白名單 (`ALLOWED_PREFERENCE_KEYS`)
- ⚠️ 匿名記錄者資訊使用結構化的 `RecorderInfo` schema，防止任意 JSON 注入
- ⚠️ Room ID 路徑參數限制長度: `min_length=10, max_length=10`
- ⚠️ 管理員端點使用 `Depends(get_current_admin_user)` 保護
- ⚠️ 所有 HTTP API 使用 slowapi 限流
- ⚠️ Celery Worker 不使用 root 執行 (Docker 中建議加 `--uid` 參數)
