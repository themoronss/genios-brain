"""Atlas Layer 6 Learning Orchestrator.

The orchestrator never learns. It selects inputs, plans deterministic units, resolves policy,
applies validation/governance, and delegates publication. A weekly database claim makes the whole
operation idempotent across retries and process replicas.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.learning import BrainTarget, LearningObject, LearningState
from genios_engine.feedback.governance import lifecycle_path
from genios_engine.feedback.store import (
    apply_path,
    claim_run,
    complete_run,
    expire_memories,
    load_batch,
    load_policy,
    persist_object,
    publish,
    transition,
)
from genios_engine.feedback.units import LearningBatch, run_units


def _at(value: datetime | None) -> datetime:
    now = value or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("eval_time must be timezone-aware")
    return now.astimezone(timezone.utc)


def preview_learning(store, org_id: str, *, eval_time: datetime | None = None,
                     batch: LearningBatch | None = None) -> dict[str, Any]:
    """Read-only plan with the exact states governance would choose."""
    now = _at(eval_time)
    with store.engine.connect() as conn:
        selected = batch or load_batch(conn, org_id, now)
        policy = load_policy(conn, org_id)
        objects = run_units(selected)
    return {"org_id": org_id, "evaluation_time": now.isoformat(), "objects": [
        {"learning_id": item.learning_id, "unit": item.unit.value,
         "target": item.target.value, "subject_key": item.subject_key,
         "confidence_bp": item.evidence.confidence_bp,
         "path": [{"state": step.state.value, "reason_code": step.reason_code}
                  for step in lifecycle_path(item, policy)]}
        for item in objects]}


def run_learning(store, org_id: str, *, eval_time: datetime | None = None,
                 batch: LearningBatch | None = None) -> dict[str, Any]:
    """Run all applicable units and atomically publish only governed learning."""
    now = _at(eval_time)
    with store.engine.begin() as conn:
        expired = expire_memories(conn, now)
        run_id, claimed = claim_run(conn, org_id, now)
        if not claimed:
            row = conn.execute(text(
                "select status,result from learning_runs where run_id=:id and org_id=:o"),
                {"id": run_id, "o": org_id}).first()
            prior = row.result if row is not None else {}
            if isinstance(prior, str):
                prior = json.loads(prior or "{}")
            return {**(prior or {}), "org_id": org_id, "run_id": run_id,
                    "applied": False, "already_ran": True, "memories_expired": expired}

        selected = batch or load_batch(conn, org_id, now)
        policy = load_policy(conn, org_id)
        objects = run_units(selected)
        states: dict[str, int] = {}
        inserted = published = held = rejected = 0
        for item in objects:
            if not persist_object(conn, item, run_id):
                continue
            inserted += 1
            final = apply_path(conn, item, lifecycle_path(item, policy), now)
            states[final.value] = states.get(final.value, 0) + 1
            published += int(final is LearningState.PUBLISHED)
            rejected += int(final is LearningState.REJECTED)
            held += int(final in {LearningState.OBSERVED, LearningState.CANDIDATE,
                                  LearningState.HUMAN_REVIEW, LearningState.TEMPORARY})
        result = {"org_id": org_id, "run_id": run_id, "applied": True,
                  "objects_produced": len(objects), "objects_inserted": inserted,
                  "published": published, "held": held, "rejected": rejected,
                  "states": states, "memories_expired": expired}
        complete_run(conn, run_id, org_id, observed=inserted, published=published,
                     held=held, rejected=rejected, result=result, at=now)
        return result


def review_learning(conn, *, org_id: str, learning_id: str, decision: str,
                    actor: str, at: datetime, note: str | None = None) -> dict[str, Any]:
    """Approve/reject a governed object. Knowledge approval records handoff; it edits no pack."""
    if decision not in {"approve", "reject"}:
        raise ValueError("decision must be approve or reject")
    row = conn.execute(text(
        "select payload,current_state from learning_objects where org_id=:o and learning_id=:id "
        "for update"), {"o": org_id, "id": learning_id}).first()
    if row is None:
        raise LookupError("learning object not found")
    payload = row.payload
    if isinstance(payload, str):
        payload = json.loads(payload)
    item = LearningObject.from_semantic_dict(payload)
    if str(row.current_state) != LearningState.HUMAN_REVIEW.value:
        raise RuntimeError(f"learning object is already {row.current_state}")
    if decision == "reject":
        transition(conn, item, LearningState.REJECTED, "human_rejected", actor=actor, at=at,
                   detail={"note": note})
        if item.target is BrainTarget.KNOWLEDGE_SUGGESTION:
            conn.execute(text(
                "update knowledge_suggestions set status='rejected',decided_by=:actor,"
                "decided_at=:at,decision_note=:note where org_id=:o and learning_id=:id "
                "and status='pending'"),
                {"actor": actor, "at": at, "note": note, "o": org_id, "id": learning_id})
        return {"learning_id": learning_id, "state": "rejected", "published": False}

    transition(conn, item, LearningState.PROMOTED, "human_approved", actor=actor, at=at,
               detail={"note": note})
    if item.target is BrainTarget.KNOWLEDGE_SUGGESTION:
        conn.execute(text(
            "update knowledge_suggestions set status='approved',decided_by=:actor,decided_at=:at,"
            "decision_note=:note where org_id=:o and learning_id=:id and status='pending'"),
            {"actor": actor, "at": at, "note": note, "o": org_id, "id": learning_id})
        return {"learning_id": learning_id, "state": "promoted", "published": False,
                "expert_brain_changed": False}
    publish(conn, item, at)
    return {"learning_id": learning_id, "state": "published", "published": True}


def rollback_learning(conn, *, org_id: str, learning_id: str, actor: str,
                      at: datetime, reason: str) -> dict[str, Any]:
    """Deactivate a published dynamic-brain value; immutable history remains queryable."""
    row = conn.execute(text(
        "select payload,current_state from learning_objects where org_id=:o and learning_id=:id "
        "for update"), {"o": org_id, "id": learning_id}).first()
    if row is None:
        raise LookupError("learning object not found")
    payload = row.payload
    if isinstance(payload, str):
        payload = json.loads(payload)
    item = LearningObject.from_semantic_dict(payload)
    if str(row.current_state) != LearningState.PUBLISHED.value:
        raise RuntimeError("only published learning can be rolled back")
    conn.execute(text(
        "update learned_brain_entries set active=false,ended_at=:at,ended_reason='rolled_back' "
        "where org_id=:o and learning_id=:id and active"),
        {"at": at, "o": org_id, "id": learning_id})
    transition(conn, item, LearningState.ROLLED_BACK, reason, actor=actor, at=at)
    return {"learning_id": learning_id, "state": "rolled_back"}


__all__ = ["preview_learning", "review_learning", "rollback_learning", "run_learning"]
