"""Discord 即時推播的訊息內容。"""
from types import SimpleNamespace

from app.services import notification_policy
from app.services.notification_policy import NotificationPolicy


def test_recorder_without_display_name_shows_guest(monkeypatch):
    # Google 沒有回傳名稱的使用者（#65）：訊息不可出現「None」
    sent = []
    monkeypatch.setattr(notification_policy.send_discord_webhook, "delay", lambda url, content: sent.append(content))
    record = SimpleNamespace(status="killed", channel=5, boss_type=SimpleNamespace(name_zh="黑龍"),
                             recorder=SimpleNamespace(display_name=None), respawn_min_time=None, respawn_max_time=None)
    room = SimpleNamespace(webhook_notify_events=None, discord_webhook_url="https://discord.example/webhook")
    NotificationPolicy._send_immediate(record, room)
    assert sent and "None" not in sent[0] and "訪客" in sent[0]
