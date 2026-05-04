import json
import hmac
import hashlib
import httpx
import logging
import asyncio
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models import WebhookSubscription, WebhookDelivery

logger = logging.getLogger(__name__)

async def deliver_webhook(
    db: Session,
    subscription_id: UUID,
    event_id: UUID,
    payload: dict,
    max_retries: int = 3
):
    """
    Background task to deliver a webhook payload to a target URL.
    Includes HMAC-SHA256 signature header and retry logic with backoff.
    """
    sub = db.get(WebhookSubscription, subscription_id)
    if not sub or not sub.is_active:
        return

    # Prepare payload
    body = json.dumps(payload)
    
    # Calculate HMAC-SHA256 signature
    # Assuming sub.secret is used as the key for HMAC
    signature = hmac.new(
        sub.secret.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Webhook-Signature": signature,
        "X-Webhook-Event-Id": str(event_id)
    }

    status = "failed"
    response_code = None
    
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    sub.target_url,
                    content=body,
                    headers=headers
                )
                
                response_code = response.status_code
                if response.is_success:
                    status = "success"
                    break
                else:
                    logger.warning(
                        "Webhook delivery attempt %d failed for %s: HTTP %d", 
                        attempt + 1, sub.target_url, response_code
                    )
            
        except Exception as exc:
            logger.error("Webhook delivery attempt %d failed for %s: %s", attempt + 1, sub.target_url, exc)
            response_code = None

        if attempt < max_retries - 1:
            # Exponential backoff: 2s, 4s, 8s...
            await asyncio.sleep(2 ** (attempt + 1))

    # Log delivery
    delivery = WebhookDelivery(
        subscription_id=sub.id,
        event_id=event_id,
        status=status,
        response_code=response_code,
        attempted_at=datetime.now(timezone.utc)
    )
    db.add(delivery)
    db.commit()

async def trigger_webhooks(
    db: Session,
    workspace_id: UUID,
    event_type: str,
    event_id: UUID,
    payload: dict
):
    """
    Trigger all active subscriptions for a given event type in a workspace.
    """
    from sqlalchemy import select
    stmt = select(WebhookSubscription).where(
        WebhookSubscription.workspace_id == workspace_id,
        WebhookSubscription.event_type == event_type,
        WebhookSubscription.is_active == True
    )
    subs = db.execute(stmt).scalars().all()
    
    for sub in subs:
        # Note: In a production app, this should be enqueued to a task runner like Celery or Arq.
        # For now we'll rely on FastAPI BackgroundTasks if called from a router, 
        # but here we might need to handle it differently.
        await deliver_webhook(db, sub.id, event_id, payload)
