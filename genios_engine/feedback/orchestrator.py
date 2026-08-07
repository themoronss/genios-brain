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

from genios_engine.contracts.learning import BRAIN_TARGETS, LearningObject, LearningState, LearningTarget
from genios_engine.contracts.visibility import Visibility
from genios_engine.feedback.governance import (
    govern_learning,
    lifecycle_path,
    preflight_learning,
    validate_learning,
)
from genios_engine.feedback.store import (
    apply_path_result,
    claim_run,
    complete_run,
    ensure_policy,
    expire_memories,
    load_batch,
    load_learning_object,
    load_policy,
    lock_learning_tenant,
    persist_input_rejections,
    persist_object,
    persist_preflight_rejection,
    publish,
    record_evaluation,
    record_failed_run,
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
         "visibility": dict(item.visibility),
         "path": [{"state": step.state.value, "reason_code": step.reason_code}
                  for step in lifecycle_path(item, policy, eval_time=now)]}
        for item in objects]}


def run_learning(store, org_id: str, *, eval_time: datetime | None = None,
                 batch: LearningBatch | None = None) -> dict[str, Any]:
    """Run all applicable units and atomically publish only governed learning."""
    now = _at(eval_time)
    # Forgetting is its own committed retention operation. A later analysis failure must never
    # resurrect a value whose lease elapsed.
    with store.engine.begin() as conn:
        lock_learning_tenant(conn, org_id)
        expired = expire_memories(conn, org_id, now)
    policy_revision = 0
    run_claimed = False
    try:
        with store.engine.begin() as conn:
            lock_learning_tenant(conn, org_id)
            policy = ensure_policy(conn, org_id, for_share=True)
            policy_revision = policy.revision
            if not policy.enabled:
                return {"org_id": org_id, "applied": False, "already_ran": False,
                        "reason": "learning_disabled", "memories_expired": expired,
                        "policy_revision": policy.revision}
            run_id, claimed = claim_run(conn, org_id, now, policy.revision)
            run_claimed = claimed
            if not claimed:
                row = conn.execute(text(
                    "select status,result from learning_runs where run_id=:id and org_id=:o"),
                    {"id": run_id, "o": org_id}).first()
                prior = row.result if row is not None else {}
                if isinstance(prior, str):
                    prior = json.loads(prior or "{}")
                return {**(prior or {}), "org_id": org_id, "run_id": run_id,
                        "applied": False, "already_ran": True,
                        "memories_expired": expired}

            selected = batch or load_batch(conn, org_id, now)
            if selected.org_id != org_id:
                raise ValueError("learning batch tenant does not match requested tenant")
            if selected.evaluated_at != now:
                raise ValueError("learning batch evaluation time does not match run time")
            input_rejections = persist_input_rejections(
                conn, org_id, run_id, selected.rejections, now)
            objects = run_units(selected)
            states: dict[str, int] = {}
            inserted = reevaluated = unchanged = published = held = rejected = 0
            preflight_rejected = 0
            for item in objects:
                refusal = preflight_learning(item, policy)
                if refusal is not None:
                    persist_preflight_rejection(conn, item, run_id, refusal.reason_code, now)
                    try:
                        stored, current_state = load_learning_object(
                            conn, org_id, item.learning_id, for_update=True)
                    except LookupError:
                        rejected += 1
                        preflight_rejected += 1
                        states[LearningState.REJECTED.value] = (
                            states.get(LearningState.REJECTED.value, 0) + 1)
                        continue
                    if current_state not in {LearningState.OBSERVED, LearningState.CANDIDATE}:
                        # Review, published and terminal duplicates are immutable lifecycle no-ops.
                        unchanged += 1
                        continue
                    transition(
                        conn, stored, LearningState.REJECTED, refusal.reason_code, at=now,
                        detail={"run_id": run_id, "policy_revision": policy.revision,
                                "reevaluation": True})
                    record_evaluation(
                        conn, stored, run_id=run_id, policy_revision=policy.revision,
                        evaluation_time=now, prior_state=current_state,
                        result_state=LearningState.REJECTED,
                        reason_code=refusal.reason_code, object_inserted=False)
                    reevaluated += 1
                    rejected += 1
                    preflight_rejected += 1
                    states[LearningState.REJECTED.value] = (
                        states.get(LearningState.REJECTED.value, 0) + 1)
                    continue
                object_inserted = persist_object(conn, item, run_id, policy.revision)
                path = lifecycle_path(item, policy, eval_time=now)
                if object_inserted:
                    inserted += 1
                    prior_state = LearningState.OBSERVED
                    stored = item
                    outcome = apply_path_result(conn, item, path, now)
                else:
                    stored, prior_state = load_learning_object(
                        conn, org_id, item.learning_id, for_update=True)
                    if prior_state not in {LearningState.OBSERVED, LearningState.CANDIDATE}:
                        # Never reopen review, published, superseded, rolled-back or terminal rows.
                        unchanged += 1
                        continue
                    outcome = apply_path_result(
                        conn, stored, path, now, initial_state=prior_state,
                        audit_detail={"run_id": run_id, "policy_revision": policy.revision,
                                      "reevaluation": True})
                    reevaluated += 1
                final = outcome.state
                record_evaluation(
                    conn, stored, run_id=run_id, policy_revision=policy.revision,
                    evaluation_time=now, prior_state=prior_state, result_state=final,
                    reason_code=outcome.reason_code,
                    object_inserted=object_inserted)
                states[final.value] = states.get(final.value, 0) + 1
                published += int(final is LearningState.PUBLISHED)
                rejected += int(final is LearningState.REJECTED)
                held += int(final in {LearningState.OBSERVED, LearningState.CANDIDATE,
                                      LearningState.HUMAN_REVIEW, LearningState.TEMPORARY})
            result = {"org_id": org_id, "run_id": run_id, "applied": True,
                      "objects_produced": len(objects), "objects_inserted": inserted,
                      "objects_reevaluated": reevaluated,
                      "objects_unchanged": unchanged,
                      "published": published, "held": held, "rejected": rejected,
                      "preflight_rejected": preflight_rejected,
                      "input_rejections": input_rejections,
                      "states": states, "memories_expired": expired,
                      "policy_revision": policy.revision}
            complete_run(conn, run_id, org_id, observed=inserted, published=published,
                         held=held, rejected=rejected, result=result, at=now)
            return result
    except Exception as exc:
        # The atomic run transaction has rolled back. A separate sanitized row makes the failure
        # visible and reclaimable without retaining source content or a half-published lifecycle.
        if run_claimed:
            with store.engine.begin() as conn:
                try:
                    lock_learning_tenant(conn, org_id)
                except LookupError:
                    # Erasure may have committed after the failed run rolled back. Never recreate
                    # child authority (or mask the original error) for a tenant that no longer exists.
                    pass
                else:
                    persisted_policy = ensure_policy(conn, org_id, for_share=True)
                    record_failed_run(conn, org_id, now,
                                      policy_revision or persisted_policy.revision,
                                      type(exc).__name__)
        raise


def review_learning(conn, *, org_id: str, learning_id: str, decision: str,
                    actor: str, at: datetime, note: str | None = None,
                    viewer: str | None = None, owner_authorized: bool = True) -> dict[str, Any]:
    """Approve/reject a governed object. Knowledge approval records handoff; it edits no pack."""
    if decision not in {"approve", "reject"}:
        raise ValueError("decision must be approve or reject")
    lock_learning_tenant(conn, org_id)
    # Learn the immutable policy identity without a row lock, then establish the canonical
    # tenant -> policy -> object order.  The object is rehydrated and rechecked under FOR UPDATE
    # below, so this discovery read grants no authority by itself.
    discovered, _ = load_learning_object(conn, org_id, learning_id)
    policy = ensure_policy(conn, org_id, discovered.policy_key, for_share=True)
    item, current_state = load_learning_object(
        conn, org_id, learning_id, for_update=True)
    if item.policy_key != discovered.policy_key:
        raise RuntimeError("learning object policy identity changed during review")
    if not Visibility.model_validate(dict(item.visibility)).can_view(
            viewer or actor, org_member=True):
        raise LookupError("learning object not found")
    if item.target is LearningTarget.ORGANIZATION and not owner_authorized:
        raise PermissionError("organization learning requires owner authority")
    if current_state is not LearningState.HUMAN_REVIEW:
        raise RuntimeError(f"learning object is already {current_state.value}")
    if item.target is LearningTarget.KNOWLEDGE_SUGGESTION:
        suggestion = conn.execute(text(
            "select status from knowledge_suggestions where org_id=:o and learning_id=:id "
            "for update"), {"o": org_id, "id": learning_id}).first()
        if suggestion is None or str(suggestion.status) != "pending":
            raise RuntimeError("knowledge suggestion is not pending")
    if decision == "reject":
        transition(conn, item, LearningState.REJECTED, "human_rejected", actor=actor, at=at,
                   detail={"note": note})
        if item.target is LearningTarget.KNOWLEDGE_SUGGESTION:
            changed = conn.execute(text(
                "update knowledge_suggestions set status='rejected',decided_by=:actor,"
                "decided_at=:at,decision_note=:note where org_id=:o and learning_id=:id "
                "and status='pending'"),
                {"actor": actor, "at": at, "note": note, "o": org_id, "id": learning_id})
            if changed.rowcount != 1:
                raise RuntimeError("knowledge suggestion decision lost serialization race")
        return {"learning_id": learning_id, "state": "rejected", "published": False}

    validation = validate_learning(item, policy, eval_time=at)
    if validation.state is not LearningState.VALIDATED:
        raise RuntimeError(f"learning proposal no longer validates: {validation.reason_code}")
    governance = govern_learning(item, policy)
    if governance.state is LearningState.REJECTED:
        raise RuntimeError(f"learning proposal is no longer allowed: {governance.reason_code}")
    if item.target in BRAIN_TARGETS - {LearningTarget.RUNTIME}:
        newer = conn.execute(text(
            "select 1 from learned_brain_entries e join learning_objects o "
            "on o.org_id=e.org_id and o.learning_id=e.learning_id where e.org_id=:o "
            "and e.brain=:brain and e.subject_key=:subject and e.active "
            "and o.last_seen_at>:last_seen"),
            {"o": org_id, "brain": item.target.value, "subject": item.subject_key,
             "last_seen": item.last_seen_at}).first()
        if newer is not None:
            raise RuntimeError("a newer learning value is already active for this subject")
    transition(conn, item, LearningState.PROMOTED, "human_approved", actor=actor, at=at,
               detail={"note": note, "policy_revision": policy.revision,
                       "governance_reason": governance.reason_code})
    if item.target is LearningTarget.KNOWLEDGE_SUGGESTION:
        changed = conn.execute(text(
            "update knowledge_suggestions set status='approved',decided_by=:actor,decided_at=:at,"
            "decision_note=:note where org_id=:o and learning_id=:id and status='pending'"),
            {"actor": actor, "at": at, "note": note, "o": org_id, "id": learning_id})
        if changed.rowcount != 1:
            raise RuntimeError("knowledge suggestion decision lost serialization race")
        return {"learning_id": learning_id, "state": "promoted", "published": False,
                "expert_brain_changed": False}
    final = publish(conn, item, at)
    return {"learning_id": learning_id, "state": final.value,
            "published": final is LearningState.PUBLISHED}


def rollback_learning(conn, *, org_id: str, learning_id: str, actor: str,
                      at: datetime, reason: str, viewer: str | None = None,
                      owner_authorized: bool = True) -> dict[str, Any]:
    """Deactivate a published dynamic-brain value; immutable history remains queryable."""
    lock_learning_tenant(conn, org_id)
    item, initial_state = load_learning_object(conn, org_id, learning_id)
    if not Visibility.model_validate(dict(item.visibility)).can_view(
            viewer or actor, org_member=True):
        raise LookupError("learning object not found")
    if item.target not in BRAIN_TARGETS - {LearningTarget.RUNTIME}:
        raise RuntimeError("only a dynamic brain publication can be rolled back")
    if item.target is LearningTarget.ORGANIZATION and not owner_authorized:
        raise PermissionError("organization learning rollback requires owner authority")
    # Reject proposals before taking the subject lock.  Review owns the proposal row first and
    # takes this advisory lock only while publishing; taking the locks in reverse order here for
    # a HUMAN_REVIEW row would create a real PostgreSQL deadlock.  A genuinely published row is
    # rechecked under both locks below, so races with supersession/another rollback still fail
    # closed without weakening serialization.
    if initial_state is not LearningState.PUBLISHED:
        raise RuntimeError("only published learning can be rolled back")

    # Discover the immutable predecessor/policy identities without taking child-row locks.  Policy
    # rows are then locked in lexical order before the subject advisory lock and object rows.  The
    # whole topology is re-read under its publication locks below; a concurrent change fails closed.
    active_snapshot = conn.execute(text(
        "select entry_id,supersedes_entry_id from learned_brain_entries "
        "where org_id=:o and learning_id=:id and active"),
        {"o": org_id, "id": learning_id}).first()
    if active_snapshot is None:
        raise RuntimeError("published learning has no active brain entry")
    predecessor_snapshot = None
    candidate_snapshot = None
    restored_entry_id = active_snapshot.supersedes_entry_id
    if restored_entry_id:
        predecessor_snapshot = conn.execute(text(
            "select learning_id,ended_reason from learned_brain_entries where org_id=:o "
            "and entry_id=:entry and brain=:brain and subject_key=:subject"),
            {"o": org_id, "entry": restored_entry_id, "brain": item.target.value,
             "subject": item.subject_key}).first()
        if (predecessor_snapshot is not None
                and str(predecessor_snapshot.ended_reason) == "superseded"):
            candidate_snapshot, _ = load_learning_object(
                conn, org_id, str(predecessor_snapshot.learning_id))
    policy_keys = {item.policy_key}
    if candidate_snapshot is not None:
        policy_keys.add(candidate_snapshot.policy_key)
    policies = {key: ensure_policy(conn, org_id, key, for_share=True)
                for key in sorted(policy_keys)}

    lock_key = f"learning-brain:{org_id}:{item.target.value}:{item.subject_key}"
    conn.execute(text("select pg_advisory_xact_lock(hashtextextended(:key,0))"),
                 {"key": lock_key})
    item, current_state = load_learning_object(
        conn, org_id, learning_id, for_update=True)
    if item.policy_key not in policies:
        raise RuntimeError("learning object policy identity changed during rollback")
    if current_state is not LearningState.PUBLISHED:
        raise RuntimeError("only published learning can be rolled back")
    active = conn.execute(text(
        "select entry_id,supersedes_entry_id from learned_brain_entries "
        "where org_id=:o and learning_id=:id and active for update"),
        {"o": org_id, "id": learning_id}).first()
    if active is None:
        raise RuntimeError("published learning has no active brain entry")
    if (active.entry_id != active_snapshot.entry_id
            or active.supersedes_entry_id != active_snapshot.supersedes_entry_id):
        raise RuntimeError("learning publication topology changed during rollback")

    restored_item = None
    if restored_entry_id:
        predecessor = conn.execute(text(
            "select learning_id,ended_reason from learned_brain_entries where org_id=:o "
            "and entry_id=:entry and brain=:brain and subject_key=:subject for update"),
            {"o": org_id, "entry": restored_entry_id, "brain": item.target.value,
             "subject": item.subject_key}).first()
        if (predecessor is not None and predecessor_snapshot is not None
                and predecessor.learning_id == predecessor_snapshot.learning_id
                and str(predecessor.ended_reason) == "superseded"
                and str(predecessor_snapshot.ended_reason) == "superseded"):
            candidate, predecessor_state = load_learning_object(
                conn, org_id, str(predecessor.learning_id), for_update=True)
            if (candidate_snapshot is None
                    or candidate.learning_id != candidate_snapshot.learning_id
                    or candidate.policy_key not in policies):
                raise RuntimeError("rollback predecessor identity changed during rollback")
            policy = policies[candidate.policy_key]
            visible = Visibility.model_validate(dict(candidate.visibility)).can_view(
                viewer or actor, org_member=True)
            if (predecessor_state is LearningState.SUPERSEDED and visible
                    and preflight_learning(candidate, policy) is None):
                restored_item = candidate

    changed = conn.execute(text(
        "update learned_brain_entries set active=false,ended_at=:at,ended_reason='rolled_back' "
        "where org_id=:o and entry_id=:entry and active"),
        {"at": at, "o": org_id, "entry": active.entry_id})
    if changed.rowcount != 1:
        raise RuntimeError("published learning has no active brain entry")
    transition(conn, item, LearningState.ROLLED_BACK, "human_rollback", actor=actor, at=at,
               detail={"reason": reason})
    restored_learning_id = None
    if restored_item is not None:
        restored = conn.execute(text(
            "update learned_brain_entries set active=true,ended_at=null,ended_reason=null "
            "where org_id=:o and entry_id=:entry and not active and ended_reason='superseded'"),
            {"o": org_id, "entry": restored_entry_id})
        if restored.rowcount != 1:
            raise RuntimeError("rollback predecessor restoration lost serialization race")
        transition(conn, restored_item, LearningState.PUBLISHED,
                   "predecessor_restored_by_rollback", actor=actor, at=at,
                   detail={"rolled_back_learning_id": learning_id})
        restored_learning_id = restored_item.learning_id
    return {"learning_id": learning_id, "state": "rolled_back",
            "restored_learning_id": restored_learning_id}


__all__ = ["preview_learning", "review_learning", "rollback_learning", "run_learning"]
