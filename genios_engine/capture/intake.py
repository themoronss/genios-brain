"""The ONE door for manual intake — human notes/edits, agent outcome events, upload
chunks. Everything a person or an AI deliberately hands GeniOS becomes a SourceEvent
through the SAME capture_event pipeline as a connector sync: deduped, traced, gated
(W-05 keeps it from noise-drops), payload+prepared persisted, then drained by L2.

Before this, each intake path wrote around the pipeline (uploads did their own SQL
insert; human/agent events landed in side tables L2 never read) — so the twin simply
never learned what users explicitly told it."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.internal_knowledge import INTERNAL_KINDS, normalize_kind
from genios_engine.capture.pipeline import CaptureResult, capture_event
from genios_engine.contracts.events import AgentEvent, HumanEvent
from genios_engine.platform.canonical import semantic_hash


def ingest_manual(*, org_id: str, source: str, object_type: str, source_object_id: str,
                  body: str, subject: str | None = None,
                  actor_type: str = "internal_user", actor_email: str | None = None,
                  occurred_at: datetime | None = None,
                  raw_extra: dict | None = None, internal_kind: str | None = None,
                  content_version: str | None = None,
                  repo, payload_store=None, prepared_store=None, trace_repo=None,
                  connection_id: str = "manual") -> CaptureResult:
    """One deliberately-provided object → the full L1 pipeline. Idempotent via the
    same dedup ledger as everything else (same object id → duplicate, not a re-land)."""
    raw = RawObject(
        source=source, object_type=object_type, source_object_id=source_object_id,
        occurred_at=occurred_at or datetime.now(timezone.utc),
        actor_type=actor_type, actor_email=actor_email,
        internal_kind=internal_kind, content_version=content_version,
        raw={"body": body or "", "subject": subject or "", **(raw_extra or {})},
    )
    return capture_event(raw, org_id=org_id, connection_id=connection_id, repo=repo,
                         payload_store=payload_store, prepared_store=prepared_store,
                         trace_repo=trace_repo)


def ingest_internal_knowledge(*, org_id: str, kind: str, title: str, body: str,
                              key: str | None = None, author_email: str | None = None,
                              occurred_at: datetime | None = None,
                              repo, payload_store=None, prepared_store=None,
                              trace_repo=None) -> CaptureResult:
    """The company writing down something about ITSELF → the one door, at canon authority.

    `kind` must be one of internal_knowledge.INTERNAL_KINDS; anything else is refused
    here rather than silently demoted downstream, because the caller asked for canon and
    a typo would quietly hand it observed authority instead.

    SUPERSEDES, not append. The dedup key is (key, semantic hash of the content):

      * re-submitting identical content       → same key → duplicate, no re-land
      * editing the policy and re-submitting  → new hash → new key → it re-lands and
        the graph updates, exactly like a CRM deal whose stage changed

    `key` defaults to a slug of the title, so "Refund Policy" edited twice is ONE
    evolving assertion rather than three competing ones. Pass an explicit key when the
    title itself changes but the subject does not.
    """
    canonical = normalize_kind(kind)
    if canonical is None:
        raise ValueError(
            f"unknown internal knowledge kind {kind!r}; expected one of "
            f"{', '.join(sorted(INTERNAL_KINDS))}")
    body = (body or "").strip()
    if not body:
        raise ValueError("internal knowledge needs a body — an empty assertion is not canon")
    subject = (title or "").strip() or canonical
    slug = key or _slug(subject)
    return ingest_manual(
        org_id=org_id, source="internal", object_type=canonical,
        source_object_id=f"{canonical}:{slug}",
        content_version=semantic_hash({"title": subject, "body": body}),
        body=body, subject=subject,
        actor_type="internal_user", actor_email=author_email,
        occurred_at=occurred_at, internal_kind=canonical,
        raw_extra={"internal_kind": canonical, "title": subject, "knowledge_key": slug},
        repo=repo, payload_store=payload_store, prepared_store=prepared_store,
        trace_repo=trace_repo, connection_id="knowledge")


def _slug(text: str) -> str:
    """Title → a stable identity for the assertion. Case and punctuation must not fork
    one policy into two ('Refund policy' and 'refund-policy' are the same statement)."""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:80] or "untitled"


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
