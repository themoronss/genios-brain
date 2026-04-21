"""Event router — Celery-task-pull from the event bus.

Every tick (default 5s), the task reads up to 100 events, debounces per
(org_id, subject_entity_id) for GENIOS_BATCH_WINDOW_SECONDS, and flushes
entities whose window has closed. A flush runs:
    candidates → reasoner → scorer → gate → log metrics

Phase 2 ends at the log step. Phase 3 will write to `recommendations` and
trigger the webhook dispatcher.
"""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from uuid import uuid4

from sqlalchemy import text

from app import config
from app.brain import candidates as candgen
from app.brain import event_bus
from app.brain import gate as gate_mod
from app.brain import reasoner as reasoner_mod
from app.brain import scorer as scorer_mod
from app.database import SessionLocal
from app.redis_client import redis_client

logger = logging.getLogger(__name__)

_DEBOUNCE_PREFIX = "brain:debounce:"


def _debounce_key(org_id: str, entity_id: str) -> str:
    return f"{_DEBOUNCE_PREFIX}{org_id}:{entity_id}"


def _open_window(org_id: str, entity_id: str) -> None:
    """Mark (org, entity) as pending. Idempotent; resets TTL on each publish."""
    try:
        redis_client.setex(
            _debounce_key(org_id, entity_id),
            config.GENIOS_BATCH_WINDOW_SECONDS,
            int(time.time()),
        )
    except Exception as e:
        logger.warning(f"debounce set failed: {e}")


def _is_window_ready(org_id: str, entity_id: str) -> bool:
    """Flush when the debounce key has expired (absent)."""
    try:
        return not redis_client.exists(_debounce_key(org_id, entity_id))
    except Exception:
        return True  # fail-open: prefer flushing over starving


def run_once() -> dict:
    """One router tick. Returns counters for observability."""
    batch = event_bus.consume_batch(count=100, block_ms=1000)
    if not batch:
        return {"consumed": 0, "flushed": 0, "pushed": 0}

    entry_ids: list[str] = []
    pending: dict[tuple[str, str], int] = defaultdict(int)

    for entry_id, payload in batch:
        entry_ids.append(entry_id)
        org_id = str(payload.get("org_id") or "")
        entity_id = str(payload.get("subject_entity_id") or "")
        if not org_id or not entity_id:
            continue
        pending[(org_id, entity_id)] += 1
        _open_window(org_id, entity_id)

    # Ack events up front — the flush work is idempotent via the dedup layer.
    event_bus.ack(entry_ids)

    # Brain-activity dashboard counters (Item 6). Best-effort — never blocks.
    if pending:
        try:
            now_iso = str(int(time.time()))
            # Write last-tick markers per-org (first org in this batch wins the
            # `last_tick` slot; that's fine for a demo counter).
            for (oid, _eid), count in pending.items():
                redis_client.set(f"brain:router:last_tick:{oid}", now_iso, ex=3600)
                redis_client.incrby(f"brain:router:last_consumed:{oid}", count)
                redis_client.expire(f"brain:router:last_consumed:{oid}", 3600)
        except Exception as _e:
            logger.debug(f"brain activity counter write failed: {_e}")

    flushed = 0
    pushed = 0
    db = SessionLocal()
    try:
        for (org_id, entity_id), n in pending.items():
            # Only flush entities whose debounce window has closed. For the
            # first event this is always false; later ticks will see it expire.
            if not _is_window_ready(org_id, entity_id):
                continue

            flushed += 1

            # Pre-compute this contact's bundle in the background so the next
            # /v1/context pull hits Layer 1 cache with fresh data. Fire-and-
            # forget — the task is idempotent and self-guards against storms.
            try:
                from app.celery_app import task_refresh_bundle
                task_refresh_bundle.delay(org_id, entity_id)
            except Exception as e:
                logger.debug(f"bundle refresh enqueue failed: {e}")

            candidates = candgen.generate(
                db, org_id, subject_entity_ids=[entity_id]
            )
            for cand in candidates:
                cand.setdefault("org_id", org_id)
                result = reasoner_mod.reason(db, cand)
                priority = scorer_mod.score(result)
                allowed, blocked_reason = gate_mod.allow(
                    candidate=cand, reason_result=result, priority=priority,
                )
                logger.info(
                    "brain_decision %s",
                    json.dumps({
                        "org_id": org_id, "entity_id": entity_id,
                        "insight_type": cand.get("insight_type"),
                        "keep": result.keep, "confidence": result.confidence,
                        "priority": priority,
                        "allowed": allowed, "blocked_reason": blocked_reason,
                    }),
                )
                if allowed:
                    # Phase 3.3 — persist to recommendations table, then the
                    # webhook dispatcher picks it up on its next tick.
                    # Payload v2 (migration 073): evidence, precedent_links,
                    # suggested_action, confidence_level, rationale.
                    try:
                        from app.brain.payload_v2 import build_payload_v2
                        payload = build_payload_v2(db, org_id, entity_id, cand, result, priority)

                        rec_id = str(uuid4())
                        db.execute(
                            text("""
                                INSERT INTO recommendations (
                                    id, org_id, subject_entity_id, insight_type,
                                    category, priority, confidence,
                                    title, reason, action, metadata,
                                    evidence, precedent_links, suggested_action,
                                    confidence_level, rationale
                                ) VALUES (
                                    :id, :oid, :sub, :itype,
                                    :cat, :prio, :conf,
                                    :title, :reason, :action, CAST(:meta AS jsonb),
                                    CAST(:evidence AS jsonb),
                                    CAST(:precedent_links AS jsonb),
                                    CAST(:suggested_action AS jsonb),
                                    :conf_level, :rationale
                                )
                            """),
                            {
                                "id": rec_id, "oid": org_id,
                                "sub": entity_id, "itype": cand.get("insight_type", "generic"),
                                "cat": cand.get("category"),
                                "prio": priority, "conf": result.confidence,
                                "title": cand.get("title"),
                                "reason": result.reason, "action": result.action,
                                "meta": json.dumps(cand.get("metadata") or {}, default=str),
                                "evidence": json.dumps(payload["evidence"], default=str),
                                "precedent_links": json.dumps(payload["precedent_links"], default=str),
                                "suggested_action": json.dumps(payload["suggested_action"], default=str),
                                "conf_level": payload["confidence_level"],
                                "rationale": payload["rationale"],
                            },
                        )
                        db.commit()
                        pushed += 1
                    except Exception as e:
                        db.rollback()
                        logger.warning(f"recommendation insert failed: {e}")
    finally:
        db.close()

    return {"consumed": len(batch), "flushed": flushed, "pushed": pushed}
