from uuid import UUID

from app.models import MemoryAuditEvent, Project, Workspace
from app.services.memory_audit_service import MemoryAuditService
from app.services.memory_policy import MemoryScope
from tests.helpers import make_project, make_workspace


def test_memory_audit_service_writes_search_and_inject_events(client):
    workspace = make_workspace(client)
    project = make_project(client, workspace_id=workspace["id"])

    row = (
        client.db.query(Project.id, Workspace.id, Workspace.org_id)
        .join(Workspace, Workspace.id == Project.workspace_id)
        .filter(Project.id == UUID(project["id"]))
        .one()
    )
    scope = MemoryScope(
        org_id=str(row[2]), workspace_id=str(row[1]), project_id=str(row[0])
    )

    service = MemoryAuditService()
    service.log_memory_search(
        client.db,
        scope=scope,
        actor_type="system",
        actor_id=None,
        query="ship launch prep",
        result_count=3,
        latency_ms=77,
        status="ok",
        metadata={"action": "extraction"},
    )
    service.log_memory_injection(
        client.db,
        scope=scope,
        actor_type="system",
        actor_id=None,
        query="ship launch prep",
        result_count=2,
        status="ok",
        metadata={"context_chars": 240},
    )
    client.db.commit()

    events = (
        client.db.query(MemoryAuditEvent)
        .order_by(MemoryAuditEvent.created_at.asc(), MemoryAuditEvent.id.asc())
        .all()
    )
    assert len(events) == 2
    by_action = {event.action: event for event in events}
    assert by_action["search"].result_count == 3
    assert by_action["search"].latency_ms == 77
    assert by_action["search"].query_hash
    assert by_action["inject"].result_count == 2
