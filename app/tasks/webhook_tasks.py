import requests
import logging
from app.celery_app import celery_app

logger = logging.getLogger(__name__)

# Discord Rate Limit is roughly 5/2s, but per-webhook URL.
# We set a global rate limit of 2 calls per second to be extremely safe out-of-the-box.
@celery_app.task(bind=True, max_retries=3, rate_limit="2/s")
def send_discord_webhook(self, webhook_url: str, content: str = None, embeds: list = None):
    """
    發送 Discord Webhook，帶有自動重試與速率限制功能。
    """
    if not webhook_url:
        return
        
    payload = {}
    if content:
        payload["content"] = content
    if embeds:
        payload["embeds"] = embeds

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        # Discord returns 204 No Content on success
        if response.status_code not in (200, 204):
            logger.error(f"Failed to send webhook. Status: {response.status_code}, Response: {response.text}")
            # If rate limited (HTTP 429), retry exponentially
            if response.status_code == 429:
                retry_after = response.json().get('retry_after', 1.0)
                raise self.retry(countdown=retry_after)
            else:
                response.raise_for_status()

        logger.info(f"Successfully sent Discord webhook to {webhook_url[:30]}...")

    except requests.exceptions.RequestException as exc:
        logger.error(f"Network error while sending webhook: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)
