import asyncio
import hmac
import hashlib
import json
from unittest.mock import patch, MagicMock
from uuid import uuid4
from datetime import datetime
from app.models import WebhookSubscription, WebhookDelivery, Workspace, Organization, User
from app.services.webhook_service import deliver_webhook
from tests.helpers import create_test_db

def test_deliver_webhook_hmac_signature():
    db, current_user, cleanup = create_test_db()
    try:
        # 1. Setup Data
        org = Organization(name="Test Org", slug="test-org", settings={})
        db.add(org)
        db.commit()
        workspace = Workspace(name="Test Workspace", org_id=org.id, owner_id=current_user.id)
        db.add(workspace)
        db.commit()

        secret = "super-secret-key"
        sub = WebhookSubscription(
            workspace_id=workspace.id,
            event_type="task.created",
            target_url="https://example.com/webhook",
            secret=secret, # Use secret instead of secret_hash
            is_active=True
        )
        db.add(sub)
        db.commit()

        event_id = uuid4()
        payload = {"event": "test", "data": 123}
        body = json.dumps(payload)
        
        # Calculate expected signature
        expected_signature = hmac.new(
            secret.encode(),
            body.encode(),
            hashlib.sha256
        ).hexdigest()

        # 2. Mock httpx and deliver
        with patch("httpx.AsyncClient.post") as mock_post:
            mock_resp = MagicMock()
            mock_resp.is_success = True
            mock_resp.status_code = 200
            mock_post.return_value = mock_resp

            asyncio.run(deliver_webhook(db, sub.id, event_id, payload))

            # 3. Assertions
            mock_post.assert_called_once()
            args, kwargs = mock_post.call_args
            assert kwargs["headers"]["X-Webhook-Signature"] == expected_signature
            assert kwargs["headers"]["X-Webhook-Event-Id"] == str(event_id)
            
            # Check delivery log
            delivery = db.query(WebhookDelivery).filter(WebhookDelivery.subscription_id == sub.id).first()
            assert delivery is not None
            assert delivery.status == "success"
            assert delivery.response_code == 200

    finally:
        cleanup()
