---
name: Boss Timer Celery & Discord Webhook 開發規範
description: 新增或修改 Discord Webhook 推播邏輯、Celery 非同步任務、預警排程時使用。包含任務路由、重試策略、速率限制與 Webhook 通知控制。
---

# Boss Timer Celery & Discord Webhook 開發規範

## 技術棧

| 項目 | 技術 |
|---|---|
| 非同步任務 | Celery |
| Broker & Backend | Redis |
| Webhook | Discord Webhook API |

---

## 檔案位置

```
app/
├── celery_app.py           # Celery 應用設定 (broker/backend/task routing)
├── tasks/
│   ├── cleanup.py          # 背景定時任務 (清理過期房間)
│   └── webhook_tasks.py    # Discord Webhook Celery 任務
└── services/
    ├── boss_service.py          # 建立紀錄後呼叫 NotificationPolicy.notify()
    └── notification_policy.py  # Webhook 推播邏輯（即時 + 預警排程）
```

---

## Celery 設定 (`celery_app.py`)

```python
celery_app = Celery(
    "boss_timer",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.webhook_tasks", "app.tasks.cleanup"]
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_routes={
        "app.tasks.webhook_tasks.*": {"queue": "discord_queue"},
    }
)
```

---

## 雙 Worker 架構

| Worker | Queue | Concurrency | 用途 |
|---|---|---|---|
| `celery_worker_fast` | `celery` (default) | 4 | 一般高速內部任務 |
| `celery_worker_discord` | `discord_queue` | 1 | Discord 推播（避免 429） |

啟動方式（本機開發，合併一個 Worker）：
```bash
uv run celery -A app.celery_app worker -Q celery,discord_queue --concurrency=2 --loglevel=info
```

---

## Discord Webhook 任務 (`webhook_tasks.py`)

```python
@celery_app.task(bind=True, max_retries=3, rate_limit="2/s")
def send_discord_webhook(self, webhook_url: str, content: str = None, embeds: list = None):
    payload = {}
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds

    response = requests.post(webhook_url, json=payload, timeout=10)

    if response.status_code == 429:
        retry_after = response.json().get("retry_after", 5)
        raise self.retry(countdown=retry_after)

    if response.status_code not in (200, 204):
        raise self.retry(countdown=2 ** self.request.retries)
```

- HTTP 429 → 按 `retry_after` 等待後重試
- 其他網路錯誤 → 指數退避重試（最多 3 次）

---

## Webhook 推播流程 (`notification_policy.py`)

推播邏輯已從 `boss_service.py` 提取為 `NotificationPolicy` class。`boss_service` 建立紀錄後呼叫：
```python
NotificationPolicy.notify(record, room, db)
```
Discord 失敗透過 `try/except` 隔離，不影響 `BossRecord` 建立。

### 欄位控制邏輯

`Room` 表有三個控制欄位：

| 欄位 | 預設值 | 說明 |
|---|---|---|
| `discord_webhook_enabled` | `False` | 全域開關，False 時完全不推播 |
| `webhook_notify_events` | `["killed","alive","not_found"]` | 控制哪些狀態事件會發送即時通知 |
| `webhook_alert_type` | `none` | 預警模式：`min/max/both/none` |

### 推播判斷邏輯

```python
class NotificationPolicy:

    @staticmethod
    def notify(record: BossRecord, room: Room, db: Session) -> None:
        if not room.discord_webhook_enabled or not room.discord_webhook_url:
            return
        try:
            NotificationPolicy._send_immediate(record, room)
            NotificationPolicy._schedule_alerts(record, room, db)
        except Exception as e:
            logging.error(f"NotificationPolicy.notify failed for record {record.id}: {e}")

    @staticmethod
    def _send_immediate(record, room):
        notify_events = room.webhook_notify_events or ["killed", "alive", "not_found"]
        if record.status not in notify_events:
            return
        # 組合訊息文字 + Discord timestamp，呼叫 send_discord_webhook.delay()

    @staticmethod
    def _schedule_alerts(record, room, db):
        if record.status != "killed" or (room.webhook_alert_type or "none") == "none":
            return
        # 依 alert_type 排程 min/max 預警，Task ID 寫回 record.celery_task_ids
```

---

## 撤銷已排程的 Celery 任務

當使用者刪除紀錄時，需同時撤銷排程中的預警任務：

```python
# routers/bosses.py (DELETE endpoint)
if record.celery_task_ids:
    for task_id in record.celery_task_ids.values():
        if task_id:
            celery_app.control.revoke(task_id, terminate=True)

record.is_archived = True
db.commit()
```

---

## Discord Timestamp 格式

Discord 支援 `<t:UNIX_TIMESTAMP:FORMAT>` 語法，自動顯示讀者的本地時間：

| 格式 | 顯示 |
|---|---|
| `<t:1234567890:t>` | 短時間（如 12:30） |
| `<t:1234567890:T>` | 長時間（如 12:30:00） |
| `<t:1234567890:R>` | 相對時間（如 5 分鐘後） |

```python
min_ts = int(boss_record.respawn_min_time.timestamp())
msg += f" (預計重生: <t:{min_ts}:t> ~ <t:{max_ts}:t>)"
```

---

## 新增 Celery 任務的步驟

1. 在 `app/tasks/` 建立任務模組
2. 使用 `@celery_app.task(bind=True)` 裝飾器
3. 在 `celery_app.py` 的 `include` 列表加入模組路徑
4. 需要分流的任務在 `task_routes` 中配置對應 Queue
