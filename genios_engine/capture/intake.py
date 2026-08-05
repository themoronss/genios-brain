"""The ONE door for manual intake — human notes/edits, agent outcome events, upload
chunks. Everything a person or an AI deliberately hands GeniOS becomes a SourceEvent
through the SAME capture_event pipeline as a connector sync: deduped, traced, gated
(W-05 keeps it from noise-drops), payload+prepared persisted, then drained by L2.

Before this, each intake path wrote around the pipeline (uploads did their own SQL
insert; human/agent events landed in side tables L2 never read) — so the twin simply
never learned what users explicitly told it."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.pipeline import CaptureResult, capture_event
from genios_engine.contracts.events import AgentEvent, HumanEvent


def ingest_manual(*, org_id: str, source: str, object_type: str, source_object_id: str,
                  body: str, subject: str | None = None,
                  actor_type: str = "internal_user", actor_email: str | None = None,
                  occurred_at: datetime | None = None,
                  raw_extra: dict | None = None,
                  repo, payload_store=None, prepared_store=None, trace_repo=None,
                  connection_id: str = "manual") -> CaptureResult:
    """One deliberately-provided object → the full L1 pipeline. Idempotent via the
    same dedup ledger as everything else (same object id → duplicate, not a re-land)."""
    raw = RawObject(
        source=source, object_type=object_type, source_object_id=source_object_id,
        occurred_at=occurred_at or datetime.now(timezone.utc),
        actor_type=actor_type, actor_email=actor_email,
        raw={"body": body or "", "subject": subject or "", **(raw_extra or {})},
    )
    return capture_event(raw, org_id=org_id, connection_id=connection_id, repo=repo,
                         payload_store=payload_store, prepared_store=prepared_store,
                         trace_repo=trace_repo)


def _dict_text(d: dict) -> str:
    """Human-legible text form of a structured detail dict (the LLM reads prose)."""
    try:
        return json.dumps(d, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        return str(d)


def ingest_human_event(ev: HumanEvent, *, repo, payload_store=None,
                       prepared_store=None, trace_repo=None) -> CaptureResult:
    """A human event (note, correction, manual context) enters the graph's world.
    source='human' → family human_input → W-05 (never noise-dropped)."""
    note = ev.detail.get("text") or ev.detail.get("note") or ""
    body = note if note else _dict_text({"target": ev.target, "detail": ev.detail})
    return ingest_manual(
        org_id=ev.org_id, source="human", object_type=ev.type.replace("human.", ""),
        source_object_id=f"{ev.actor_id}:{ev.type}:{ev.occurred_at.isoformat()}",
        body=body, subject=ev.type,
        actor_type="internal_user", actor_email=ev.detail.get("actor_email"),
        occurred_at=ev.occurred_at,
        raw_extra={"human_event": ev.model_dump(mode="json")},
        repo=repo, payload_store=payload_store, prepared_store=prepared_store,
        trace_repo=trace_repo, connection_id="human")


def ingest_agent_event(ev: AgentEvent, *, repo, payload_store=None,
                       prepared_store=None, trace_repo=None) -> CaptureResult:
    """An agent's completed action enters the graph's world — so GeniOS never
    recommends what an agent already did, and outcomes become learnable.
    Dedup key rides the agent's own idempotency key."""
    body = _dict_text({"action": ev.action_taken, "target": ev.target_hint,
                       "result": ev.result, "detail": ev.detail})
    return ingest_manual(
        org_id=ev.org_id, source="agent", object_type="action",
        source_object_id=ev.idempotency_key,
        body=body, subject=ev.action_taken,
        actor_type="agent", actor_email=None,
        occurred_at=ev.occurred_at,
        raw_extra={"agent_event": ev.model_dump(mode="json")},
        repo=repo, payload_store=payload_store, prepared_store=prepared_store,
        trace_repo=trace_repo, connection_id=ev.agent_id)
