from uuid import UUID
from typing import Annotated, List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.auth import get_current_user, ensure_workspace_access
from app.dependencies import get_db
from app.models import WebhookSubscription, WebhookDelivery, User
from app.schemas import (
    WebhookSubscriptionCreate,
    WebhookSubscriptionUpdate,
    WebhookSubscriptionResponse,
    WebhookDeliveryResponse,
)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])
DbDep = Annotated[Session, Depends(get_db)]


def _get_subscription_or_404(
    subscription_id: UUID, db: Session, current_user: User
) -> WebhookSubscription:
    sub = db.get(WebhookSubscription, subscription_id)
    if not sub:
        raise HTTPException(status_code=404, detail="Subscription not found")
    ensure_workspace_access(sub.workspace_id, current_user, db, min_role="admin")
    return sub


@router.post("", response_model=WebhookSubscriptionResponse, status_code=201)
def create_subscription(
    workspace_id: UUID,
    payload: WebhookSubscriptionCreate,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    ensure_workspace_access(workspace_id, current_user, db, min_role="admin")
    sub = WebhookSubscription(
        workspace_id=workspace_id,
        event_type=payload.event_type,
        target_url=payload.target_url,
        secret=payload.secret,
        is_active=True,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.get("", response_model=List[WebhookSubscriptionResponse])
def list_subscriptions(
    workspace_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    ensure_workspace_access(workspace_id, current_user, db, min_role="admin")
    stmt = select(WebhookSubscription).where(
        WebhookSubscription.workspace_id == workspace_id
    )
    return db.execute(stmt).scalars().all()


@router.patch("/{subscription_id}", response_model=WebhookSubscriptionResponse)
def update_subscription(
    subscription_id: UUID,
    payload: WebhookSubscriptionUpdate,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    sub = _get_subscription_or_404(subscription_id, db, current_user)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(sub, field, value)
    db.commit()
    db.refresh(sub)
    return sub


@router.delete("/{subscription_id}", status_code=204)
def delete_subscription(
    subscription_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    sub = _get_subscription_or_404(subscription_id, db, current_user)
    db.delete(sub)
    db.commit()


@router.get("/{subscription_id}/deliveries", response_model=List[WebhookDeliveryResponse])
def list_deliveries(
    subscription_id: UUID,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = 50,
):
    sub = _get_subscription_or_404(subscription_id, db, current_user)
    stmt = (
        select(WebhookDelivery)
        .where(WebhookDelivery.subscription_id == subscription_id)
        .order_by(WebhookDelivery.attempted_at.desc())
        .limit(limit)
    )
    return db.execute(stmt).scalars().all()


@router.post("/{subscription_id}/test")
async def test_subscription(
    subscription_id: UUID,
    background_tasks: BackgroundTasks,
    db: DbDep,
    current_user: Annotated[User, Depends(get_current_user)],
):
    sub = _get_subscription_or_404(subscription_id, db, current_user)
    from app.services.webhook_service import deliver_webhook

    test_payload = {
        "event_type": "test.event",
        "data": {"message": "This is a test webhook"},
    }
    background_tasks.add_task(deliver_webhook, db, sub.id, UUID(int=0), test_payload)
    return {"message": "Test webhook delivery queued"}
