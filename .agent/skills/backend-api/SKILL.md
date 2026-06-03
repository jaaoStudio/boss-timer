---
name: Boss Timer Backend API 開發規範
description: 新增或修改 FastAPI 路由、Pydantic Schema、Service 層業務邏輯時使用。包含端點慣例、Rate Limiting、錯誤處理、依賴注入規範。
---

# Boss Timer Backend API 開發規範

## 專案技術棧

| 項目 | 技術 |
|---|---|
| 框架 | FastAPI |
| ORM | SQLAlchemy (同步模式) |
| 資料驗證 | Pydantic v2 |
| 限流 | slowapi |
| 套件管理 | uv (pyproject.toml) |

---

## 專案結構（API 相關）

```
app/
├── main.py              # 應用程式進入點、CORS、路由註冊
├── dependencies.py      # 全域依賴注入 (限流器、身份驗證)
├── schemas/
│   ├── auth.py          # 認證相關 Pydantic 模型
│   ├── boss.py          # Boss 相關 Pydantic 模型
│   ├── room.py          # 房間相關 Pydantic 模型
│   └── feedback.py      # 回饋 / 許願 Pydantic 模型 (Type/Status enum)
├── routers/
│   ├── auth.py          # /auth 路由
│   ├── rooms.py         # /room 路由
│   ├── bosses.py        # /boss 路由
│   ├── websocket.py     # /ws 路由
│   ├── system.py        # /system 路由 (管理員)
│   └── feedback.py      # /feedback 路由 (含 admin patch/delete)
└── services/
    ├── auth_service.py     # 認證業務邏輯
    ├── boss_service.py     # Boss 業務邏輯
    ├── room_service.py     # 房間業務邏輯
    └── feedback_service.py # 回饋業務邏輯 (含 10/day rate limit、toggle vote)
```

---

## 新增 API 端點的標準步驟

1. **定義 Schema** (`schemas/`): 建立 Pydantic 輸入/輸出模型
2. **實作 Service** (`services/`): 實作業務邏輯（不含 HTTP 細節）
3. **建立 Router** (`routers/`): 註冊路由，調用 Service，處理例外
4. **註冊路由器** (`main.py`): `app.include_router(...)`
5. **加上維護保護** (如需要): `dependencies=[Depends(check_maintenance_mode)]`

---

## Pydantic Schema 慣例

```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional

class RoomResponse(BaseModel):
    room_id: str = Field(..., max_length=10)
    discord_webhook_url: Optional[str] = None
    discord_webhook_enabled: bool = False
    webhook_notify_events: Optional[List[str]] = Field(
        default_factory=lambda: ["killed", "alive", "not_found"]
    )
    webhook_alert_type: Optional[str] = "none"

    # 回應模型必須加此設定以支援 ORM → Schema 轉換
    model_config = ConfigDict(from_attributes=True)

class RoomSettingsUpdate(BaseModel):
    discord_webhook_url: Optional[str] = Field(None, max_length=1000)
    discord_webhook_enabled: Optional[bool] = False
    webhook_notify_events: Optional[List[str]] = None
    webhook_alert_type: Optional[str] = Field("none", pattern="^(min|max|both|none)$")
```

- **回應模型** 必須加 `model_config = ConfigDict(from_attributes=True)`
- 使用 `Field(...)` 加上驗證約束
- 敏感資訊分離：`User`（完整）vs `PublicUser`（公開欄位）

---

## 服務層模式

**設計原則**:
1. **Router 層**: 只負責 HTTP 請求/回應、參數驗證、錯誤包裝
2. **Service 層**: 包含所有業務邏輯，Router 調用 Service 完成工作
3. **Model/Schema 分離**: SQLAlchemy Model 做資料庫存取，Pydantic Schema 做 API 序列化

**`boss_service.py` 模式（靜態方法類）**:
```python
class BossService:
    @staticmethod
    async def _validate_room_exists(db, room_id) -> Room: ...

    @staticmethod
    async def record_boss_from_websocket(db, record, user_id, manager): ...
```

**`room_service.py` 模式（函式直接導出）**:
```python
async def get_room_state(db, room_id) -> dict:
    # 使用 joinedload 避免 N+1 查詢
    records = db.query(BossRecord).options(
        joinedload(BossRecord.recorder),
        joinedload(BossRecord.boss_type)
    ).filter(...)
```

---

## API 路由一覽

### 認證 (`/auth`)
| Method | Path | Auth | 說明 |
|---|---|---|---|
| POST | `/auth/google` | 無 | Google 登入/註冊 |
| POST | `/auth/refresh` | Cookie | 刷新 access token |
| POST | `/auth/validate` | Header/Cookie | 驗證 token |
| GET | `/auth/me` | Cookie | 取得使用者資訊 |
| POST | `/auth/logout` | Cookie | 登出 |
| PUT | `/auth/me/preferences` | Cookie | 更新偏好設定 |
| POST | `/auth/session` | Cookie(可選) | 初始化 Session |

### 房間 (`/room`)
| Method | Path | Auth | Rate Limit | 說明 |
|---|---|---|---|---|
| POST | `/room/` | Session | 5/min | 建立新房間 |
| GET | `/room/{room_id}/exists` | 無 | 15/min | 查詢房間是否存在，同時回傳 Webhook 設定 |
| PATCH | `/room/{room_id}/settings` | Session | 30/min | 更新房間設定（Webhook/預警模式） |

### Boss (`/boss`)
| Method | Path | 說明 |
|---|---|---|
| GET | `/boss/boss-types` | 取得所有 Boss 類型 |
| GET | `/boss/room/{room_id}/records` | 歷史紀錄 cursor 分頁（`before_id`/`limit`/`start`/`end`/`boss_type_id`），回傳 `BossRecordHistoryPage`（records + has_more + next_cursor），60/min |
| DELETE | `/boss/room/{room_id}/records/{record_id}` | 撤銷紀錄 + 撤銷 Celery 預警 |
| POST | `/boss/room/{room_id}/boss-types/{boss_type_id}/clear` | 清除指定 Boss 種類頻道總覽（換輪用）；撤銷 Celery 預警、更新 `room.last_cleared_at`、廣播 `boss_type_cleared`；任何人可觸發，10/min |

### 系統 (`/system`)
| Method | Path | Auth | 說明 |
|---|---|---|---|
| GET | `/system/maintenance-info` | 無 | 讀取維護模式 |
| POST | `/system/maintenance-config` | Admin | 更新維護模式 |

### 回饋 / 許願 (`/feedback`)
| Method | Path | Auth | Rate Limit | 說明 |
|---|---|---|---|---|
| GET | `/feedback/` | 匿名可看 | 60/min | 取得清單；`sort=votes\|newest`；pending/rejected 僅自己 / admin 看得到，done 永遠排最下 |
| POST | `/feedback/` | 登入 | 20/min | 建立回饋（pending）；同帳號每日上限 10 筆（Service 端檢查，超過回 429） |
| POST | `/feedback/{id}/vote` | 登入 | 60/min | Toggle 投票；回 `{ voted, vote_count }`；pending/rejected 不可投 |
| PATCH | `/feedback/{id}` | Admin | 60/min | 更新狀態（pending → open 視為核准） |
| DELETE | `/feedback/{id}` | Admin | 30/min | 硬刪除（CASCADE 刪 votes） |

> 路由註冊在 `main.py`，受 `check_maintenance_mode` dependency 保護。
> 不依賴 `verify_user_session`——`/feedback/` GET 對匿名開放；其他 endpoint 用自訂 `_require_user` / `get_current_admin_user` 強制登入。

---

## Rate Limiting / 限流

使用 `slowapi`，在 `dependencies.py` 中初始化 `Limiter`：

```python
@router.post("/", dependencies=[Depends(RateLimiter(times=5, seconds=60))])
async def create_room(...):
```

---

## 錯誤處理

- **Router 層**: 使用 `HTTPException` 回傳適當 HTTP 狀態碼
- **Service 層**: 使用 `logging.error()` 記錄內部錯誤
- **WebSocket 錯誤**: 透過 `websocket.send_text(json.dumps({"type": "error", ...}))` 回傳

```python
# Router 層範例
try:
    result = await BossService.do_something(db, data)
except HTTPException:
    raise
except Exception as e:
    logging.error(f"Unexpected error: {e}")
    raise HTTPException(status_code=500, detail="Internal server error")
```

---

## 安全守則

- ⚠️ 使用者偏好設定更新必須過白名單 (`ALLOWED_PREFERENCE_KEYS = {"showRecordHistory"}`)
- ⚠️ Room ID 路徑參數限制長度: `min_length=10, max_length=10`
- ⚠️ 管理員端點使用 `Depends(get_current_admin_user)` 保護
- ⚠️ 匿名記錄者資訊使用結構化的 `RecorderInfo` schema，防止任意 JSON 注入

---

## 認證流程

### Google OAuth 登入
1. 前端透過 `vue3-google-login` 取得 Google `credential` 或 `code`
2. `POST /auth/google` — 後端驗證，建立或更新使用者
3. 生成 JWT access token (30 分鐘) + refresh token (30 天)
4. Token 透過 **HttpOnly Cookie** 設置

### Token 驗證
支援兩種方式：
- `Authorization: Bearer <token>` Header
- `access_token` Cookie

### 匿名使用者
`POST /auth/session` — 建立 UUID 匿名 ID，存入 Cookie
