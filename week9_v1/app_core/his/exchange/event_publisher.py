from __future__ import annotations

from app_core.his.exchange.outbox import OutboxEvent


def publish_event(event: OutboxEvent) -> dict[str, str]:
    return {"outbox_id": event.outbox_id, "status": "DEFERRED"}
