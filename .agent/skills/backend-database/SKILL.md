---
name: Boss Timer Backend Database 開發規範
description: 新增或修改 SQLAlchemy ORM Model、執行 Alembic Migration 時使用。包含資料庫欄位設計、關聯設定、遷移腳本注意事項。
---

# Boss Timer Backend Database 開發規範

## 技術棧

| 項目 | 技術 |
|---|---|
| ORM | SQLAlchemy (同步模式) |
| 資料庫 | PostgreSQL |
| 遷移工具 | Alembic |
| 套件管理 | uv |
| Python 版本 | 3.11+ |

---

## 檔案位置

```
app/
└── database/
    ├── database.py   # SQLAlchemy engine、SessionLocal、Base、get_db()
    └── models.py     # 所有 ORM 模型定義

alembic/
├── env.py
├── alembic.ini       # 設定檔 (在專案根目錄)
└── versions/         # Migration 腳本
```

---

## ORM 模型一覽

### Room
| 欄位 | 類型 | 備註 |
|---|---|---|
| `room_id` | `String(10)` PK | 10 碼大寫英數字 |
| `created_at` | `DateTime(tz)` | `server_default=func.now()` |
| `last_active` | `DateTime(tz)` | `onupdate=func.now()` |
| `is_active` | `Boolean` | 超過 7 天標記 False |
| `discord_webhook_url` | `String(1000)` nullable | Discord Webhook URL |
| `discord_webhook_enabled` | `Boolean` | `server_default='false'` |
| `webhook_notify_events` | `JSONB` | `["killed","alive","not_found"]` |
| `webhook_alert_type` | `String(20)` | `min/max/both/none`，預設 `none` |
| `last_cleared_at` | `JSONB` | 各 Boss 種類最後清除時間（key = boss_type_id str），`server_default='{}'` |

### BossRecord
| 欄位 | 類型 | 備註 |
|---|---|---|
| `id` | `BigInteger` PK | autoincrement |
| `room_id` | FK → Room | CASCADE delete |
| `channel` | `Integer` ≥ 1 | CheckConstraint |
| `boss_type_id` | FK → BossType | |
| `status` | `String(20)` | `alive/killed/not_found` |
| `recorded_at` | `DateTime(tz)` | |
| `respawn_min_time` | `DateTime(tz)` | nullable |
| `respawn_max_time` | `DateTime(tz)` | nullable |
| `recorder_id` | FK → User (nullable) | `ondelete="SET NULL"` |
| `recorder_info` | `JSONB` | 匿名記錄者資訊 |
| `is_archived` | `Boolean` | 軟刪除標記 |
| `celery_task_ids` | `JSONB` nullable | `{min_task_id, max_task_id}` |

**Computed Property** (`current_status`):
```python
@property
def current_status(self) -> str:
    now = datetime.now(timezone.utc)
    if self.status == "killed":
        if self.respawn_max_time and now >= self.respawn_max_time:
            return "alive"
        if self.respawn_min_time and now >= self.respawn_min_time:
            return "may_respawn"
        return "respawning"
    return self.status
```

**索引**:
| 索引 | 欄位 | 用途 |
|---|---|---|
| `idx_boss_records_room_channel` | `(room_id, channel)` | 一般頻道過濾 |
| `idx_boss_records_room_boss_type` | `(room_id, boss_type_id)` | Boss 種類過濾 |
| `idx_boss_records_time` | `(recorded_at)` | 時間範圍 |
| `idx_boss_records_recorder_id` | `(recorder_id)` | 記錄者查詢 |
| `idx_boss_records_room_latest` | `(room_id, channel, boss_type_id, recorded_at)` | 支援 `get_room_state` 的 `DISTINCT ON (channel, boss_type_id)` 走 index scan |
| `idx_boss_records_room_history` | `(room_id, id)` | 支援歷史紀錄 cursor 分頁（`WHERE room_id=? AND id<? ORDER BY id DESC`） |

### User
| 欄位 | 類型 | 備註 |
|---|---|---|
| `id` | `BigInteger` PK | |
| `google_id` | `String(255)` UNIQUE | |
| `email` | `String(255)` UNIQUE | |
| `display_name` | `String(100)` | |
| `avatar_url` | `Text` | |
| `preferences` | `JSONB` | `{"showRecordHistory": bool}` |
| `is_admin` | `Boolean` | `default=False` |

### RoomUser（多對多）
| 欄位 | 備註 |
|---|---|
| `user_id` | nullable（匿名時為 NULL）|
| `anonymous_session_id` | nullable（登入時為 NULL）|
| 約束 | `user_id` 或 `anonymous_session_id` 至少一個非 NULL |

### FeedbackItem
| 欄位 | 類型 | 備註 |
|---|---|---|
| `id` | `BigInteger` PK | autoincrement |
| `type` | `String(20)` | `'bug' \| 'feature'`，CheckConstraint |
| `title` | `String(200)` | 必填 |
| `description` | `Text` nullable | 選填 |
| `status` | `String(20)` | `pending/open/planning/done/rejected`，CheckConstraint，預設 `pending` |
| `created_by` | FK → User (nullable) | `ondelete="SET NULL"` |
| `created_at` | `DateTime(tz)` | `server_default=func.now()` |

**索引**:
| 索引 | 欄位 | 用途 |
|---|---|---|
| `idx_feedback_items_status_created` | `(status, created_at)` | 清單依狀態 + 時間排序 |
| `idx_feedback_items_created_by` | `(created_by)` | 找某使用者所有提交（含自己的 pending）|

**可見性規則（在 Service 層處理，非 DB 約束）**:
- `pending` / `rejected`：只有 `created_by == viewer` 或 admin 可見
- 其他狀態：所有人可見

### FeedbackVote
| 欄位 | 類型 | 備註 |
|---|---|---|
| `id` | `BigInteger` PK | autoincrement |
| `feedback_id` | FK → FeedbackItem | `ondelete="CASCADE"` |
| `user_id` | FK → User | `ondelete="CASCADE"` |
| `created_at` | `DateTime(tz)` | `server_default=func.now()` |

**約束**:
- `UNIQUE(feedback_id, user_id)` (`uq_feedback_vote_user`) — 一帳號一票
- `idx_feedback_votes_feedback` 索引在 `(feedback_id)` — 加速票數聚合

**投票邏輯（toggle）**: 由 Service 層的 `toggle_vote()` 處理：有紀錄就 DELETE、沒紀錄就 INSERT，回傳 `(voted_now, vote_count)`。

---

## 新增 ORM Model 欄位的步驟

1. **修改 `app/database/models.py`**，新增欄位定義
2. **注意 `server_default`**：若欄位為 `NOT NULL` 且資料表已有資料，**必須**加上 `server_default`，否則 Migration 會失敗
3. **執行 Alembic** 產生 Migration 腳本
4. **驗證腳本**後執行 upgrade

---

## ⚠️ 常見陷阱

### NOT NULL 欄位新增失敗
```
psycopg2.errors.NotNullViolation: column "xxx" contains null values
```
**解法**: 加上 `server_default`：
```python
# ❌ 錯誤：既有資料表新增 NOT NULL 欄位
discord_webhook_enabled = Column(Boolean, default=False, nullable=False)

# ✅ 正確：補上 server_default
discord_webhook_enabled = Column(Boolean, default=False, server_default='false', nullable=False)
```

### Boolean server_default 寫法
```python
# PostgreSQL 用字串 'false' / 'true'
server_default='false'
server_default='true'
```

---

## Alembic Migration 執行方式

> ⚠️ **必須在專案根目錄執行**，不能在 `app/` 裡面

```bash
# 在專案根目錄
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head

# 若 uv 找不到，用 conda 虛擬環境的路徑
/home/jack/miniconda3/envs/boss-timing/bin/alembic revision --autogenerate -m "description"
/home/jack/miniconda3/envs/boss-timing/bin/alembic upgrade head
```

### 在正式機執行（容器內）
```bash
docker compose -f docker-compose.prod.yaml exec boss_service alembic upgrade head
```

---

## 資料庫連線設定

```python
# app/database/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

---

## 欄位設計慣例

- 時間欄位一律使用 `DateTime(timezone=True)` 確保時區感知
- `server_default=func.now()` 讓資料庫端設預設時間
- JSONB 欄位適合儲存結構不固定的資料（如 `preferences`、`celery_task_ids`、`webhook_notify_events`）
- 軟刪除使用 `is_archived = Column(Boolean, default=False, nullable=False)` 而非真正刪除
- 外鍵刪除策略：
  - `BossRecord.room_id` → `CASCADE`（房間刪除時一併刪除記錄）
  - `BossRecord.recorder_id` → `SET NULL`（使用者刪除時保留紀錄）
