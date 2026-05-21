from datetime import datetime, timedelta, timezone
import logging
from sqlalchemy.orm import Session
from app.database.models import BossRecord, Room
from app.tasks.webhook_tasks import send_discord_webhook


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
    def _send_immediate(record: BossRecord, room: Room) -> None:
        notify_events = room.webhook_notify_events or ["killed", "alive", "not_found"]
        if record.status not in notify_events:
            return

        boss_name = record.boss_type.name_zh
        channel = record.channel
        recorder_name = record.recorder.display_name if record.recorder else "訪客"
        action_text = (
            "擊殺了" if record.status == "killed"
            else "標記存活" if record.status == "alive"
            else "未發現"
        )
        msg = f"⚔️ **{recorder_name}** 在 **[{channel}頻]** {action_text} **[{boss_name}]**！"

        if record.respawn_min_time and record.respawn_max_time:
            min_ts = int(record.respawn_min_time.timestamp())
            max_ts = int(record.respawn_max_time.timestamp())
            msg += f" (預計重生: <t:{min_ts}:t> ~ <t:{max_ts}:t>)"

        send_discord_webhook.delay(room.discord_webhook_url, content=msg)

    @staticmethod
    def _schedule_alerts(record: BossRecord, room: Room, db: Session) -> None:
        if record.status != "killed":
            return

        alert_type = room.webhook_alert_type or "none"
        if alert_type == "none":
            return

        boss_name = record.boss_type.name_zh
        channel = record.channel
        now = datetime.now(timezone.utc)
        celery_ids = {}

        if alert_type in ["min", "both"] and record.respawn_min_time:
            eta = record.respawn_min_time - timedelta(minutes=5)
            if eta > now:
                msg = f"⚠️ **[{boss_name}]** 將於 5 分鐘後在 **[{channel}頻]** 重生 (最短時間)！"
                task = send_discord_webhook.apply_async(args=[room.discord_webhook_url, msg], eta=eta)
                celery_ids["min_task_id"] = task.id

        if alert_type in ["max", "both"] and record.respawn_max_time:
            eta = record.respawn_max_time - timedelta(minutes=5)
            if eta > now:
                msg = f"⚠️ **[{boss_name}]** 將於 5 分鐘後在 **[{channel}頻]** 重生 (最長時間)！"
                task = send_discord_webhook.apply_async(args=[room.discord_webhook_url, msg], eta=eta)
                celery_ids["max_task_id"] = task.id

        if celery_ids:
            record.celery_task_ids = celery_ids
            db.commit()