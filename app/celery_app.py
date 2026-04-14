from celery import Celery
from app.config import settings

celery_app = Celery(
    "boss_timer",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.webhook_tasks"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    broker_connection_retry_on_startup=True,
    task_routes={
        "app.tasks.webhook_tasks.*": {"queue": "discord_queue"},
        # 這裡未來若有其他信件發送、數據統計等非同步任務，可以設定到 default 或是別的 queue
    },
)
