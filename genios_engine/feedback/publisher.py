"""Layer 6 · Phase 5 — persistence, the five publisher seams, and restoration-aware rollback (Part 7).

The publisher writes learned state as data, only after validation and governance. Brains are
versioned (one active per tenant/brain/subject; a materially-new value gets ``max(version)+1``, a
byte-identical value is ``no_material_change``, never version noise). Runtime is an immediate
expiring lease. Metrics are measurements. Knowledge suggestions stop at human review and
``expert_brain_changed`` is always false. Rollback restores the exact verified predecessor, else
rolls to an empty active slot — history stays intact either way. The only Layer 6 module besides
the Selector that touches SQL.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.learning import (
    BrainTarget,
    LearningObject,
    LearningState,
    LearningTarget,
)
from genios_engine.platform.canonical import canonical_dumps
from genios_engine.platform.ids import new_id

_BRAIN_TARGETS = {LearningTarget.ORGANIZATION, LearningTarget.BEHAVIOR, LearningTarget.ADAPTIVE}


def log_transition(conn, *, org_id: str, learning_id: str, from_state: str | None,
                   to_state: str, reason_code: str, at: datetime, actor: str | None = None,
                   detail: dict | None = None) -> None:
    conn.execute(text(
        "insert into learning_transitions (id, org_id, learning_id, from_state, to_state, "
        "reason_code, actor, detail, occurred_at) values (:id, :o, :l, :f, :t, :r, :a, :d, :at)"),
        {"id": new_id("ltr"), "o": org_id, "l": learning_id, "f": from_state, "t": to_state,
         "r": reason_code, "a": actor, "d": canonical_dumps(detail or {}), "at": at})


def persist(conn, obj: LearningObject, *, state: LearningState, at: datetime,
            policy_revision: int | None = None) -> str:
    """Insert an immutable proposal at ``state``. Idempotent on ``learning_id``.

    Returns 'inserted' (new), 'reevaluated' (existing Observed/Candidate — eligible again) or
    'unchanged' (an existing later/terminal object — a no-op that cannot reopen).
    """
    existing = conn.execute(text(
        "select state from learning_objects where org_id = :o and learning_id = :l for update"),
        {"o": obj.org_id, "l": obj.learning_id}).mappings().first()
    if existing is not None:
        cur = existing["state"]
        if cur in (LearningState.OBSERVED.value, LearningState.CANDIDATE.value):
            return "reevaluated"          # eligible for re-evaluation under the new run's policy
        return "unchanged"                # later/terminal — never reopened

    conn.execute(text(
        "insert into learning_objects (org_id, learning_id, schema_version, unit, target, subject, "
        "semantic_hash, proposed_value, evidence, visibility_scope, visibility, lineage_complete, "
        "subject_principal, policy_key, policy_revision, first_seen_at, last_seen_at, expires_at, "
        "state, created_at) values (:o, :l, :sv, :u, :t, :s, :h, :pv, :ev, :vscope, :vis, :lc, "
        ":sp, :pk, :prev, :fs, :ls, :exp, :state, :at)"),
        {"o": obj.org_id, "l": obj.learning_id, "sv": obj.schema_version, "u": obj.unit,
         "t": obj.target.value, "s": obj.subject, "h": obj.semantic_hash(),
         "pv": canonical_dumps(dict(obj.proposed_value)),
         "ev": canonical_dumps(obj.evidence.to_semantic_dict()),
         "vscope": obj.visibility.scope.value, "vis": canonical_dumps(obj.visibility.to_semantic_dict()),
         "lc": obj.lineage_complete, "sp": obj.subject_principal, "pk": obj.policy_key,
         "prev": policy_revision, "fs": obj.first_seen_at, "ls": obj.last_seen_at,
         "exp": obj.expires_at, "state": state.value, "at": at})
    log_transition(conn, org_id=obj.org_id, learning_id=obj.learning_id, from_state=None,
                   to_state=state.value, reason_code="persisted", at=at)
    return "inserted"


def publish_brain(conn, obj: LearningObject, *, at: datetime) -> str:
    """Version a learned brain value. Byte-identical → ``no_material_change``; else max+1 supersede."""
    brain = obj.target.value
    if obj.target not in _BRAIN_TARGETS:
        raise ValueError(f"{brain} is not a brain target")
    active = conn.execute(text(
        "select version, value from learned_brain_entries "
        "where org_id = :o and brain = :b and subject = :s and active for update"),
        {"o": obj.org_id, "b": brain, "s": obj.subject}).mappings().first()

    value_json = canonical_dumps(dict(obj.proposed_value))
    if active is not None and canonical_dumps(active["value"]) == value_json:
        return "no_material_change"

    next_version = (active["version"] + 1) if active else 1
    if active is not None:
        conn.execute(text(
            "update learned_brain_entries set active = false, deactivated_at = :at "
            "where org_id = :o and brain = :b and subject = :s and version = :v"),
            {"at": at, "o": obj.org_id, "b": brain, "s": obj.subject, "v": active["version"]})
    conn.execute(text(
        "insert into learned_brain_entries (org_id, brain, subject, version, learning_id, value, "
        "visibility_scope, visibility, active, supersedes, created_at) "
        "values (:o, :b, :s, :v, :l, :val, :vscope, :vis, true, :sup, :at)"),
        {"o": obj.org_id, "b": brain, "s": obj.subject, "v": next_version, "l": obj.learning_id,
         "val": value_json, "vscope": obj.visibility.scope.value,
         "vis": canonical_dumps(obj.visibility.to_semantic_dict()),
         "sup": active["version"] if active else None, "at": at})
    return f"published_v{next_version}"


def publish_runtime(conn, obj: LearningObject, *, at: datetime) -> str:
    """A Runtime lease → temporary_memories, immediate, with its mandatory expiry."""
    conn.execute(text(
        "insert into temporary_memories (org_id, memory_id, learning_id, subject, value, "
        "visibility_scope, visibility, expires_at, active, created_at) "
        "values (:o, :m, :l, :s, :val, :vscope, :vis, :exp, true, :at)"),
        {"o": obj.org_id, "m": new_id("tmem"), "l": obj.learning_id, "s": obj.subject,
         "val": canonical_dumps(dict(obj.proposed_value)), "vscope": obj.visibility.scope.value,
         "vis": canonical_dumps(obj.visibility.to_semantic_dict()), "exp": obj.expires_at, "at": at})
    return "temporary_published"


def publish_metric(conn, obj: LearningObject, *, at: datetime) -> str:
    """A measurement → learning_metrics. Identity collision is rejected, not falsely 'published'."""
    result = conn.execute(text(
        "insert into learning_metrics (org_id, metric_id, learning_id, unit, subject, value, "
        "observed_at, created_at) values (:o, :m, :l, :u, :s, :val, :obs, :at) "
        "on conflict (org_id, metric_id) do nothing"),
        {"o": obj.org_id, "m": f"met_{obj.learning_id[3:]}", "l": obj.learning_id, "u": obj.unit,
         "s": obj.subject, "val": canonical_dumps(dict(obj.proposed_value)),
         "obs": obj.last_seen_at, "at": at})
    return "metric_published" if result.rowcount == 1 else "metric_identity_conflict"


def publish_knowledge(conn, obj: LearningObject, *, at: datetime) -> str:
    """A human-review suggestion. Stops at review; the Expert Brain is never changed."""
    conn.execute(text(
        "insert into knowledge_suggestions (org_id, suggestion_id, learning_id, subject, body, "
        "state, created_at) values (:o, :sg, :l, :s, :body, 'human_review', :at)"),
        {"o": obj.org_id, "sg": new_id("ksug"), "l": obj.learning_id, "s": obj.subject,
         "body": canonical_dumps(dict(obj.proposed_value)), "at": at})
    return "knowledge_review"


def rollback_brain(conn, *, org_id: str, brain: str, subject: str, at: datetime,
                   actor: str | None = None) -> str:
    """Restore the exact verified predecessor, else roll to empty. History stays intact."""
    active = conn.execute(text(
        "select version, supersedes from learned_brain_entries "
        "where org_id = :o and brain = :b and subject = :s and active for update"),
        {"o": org_id, "b": brain, "s": subject}).mappings().first()
    if active is None:
        return "nothing_active"

    conn.execute(text(
        "update learned_brain_entries set active = false, deactivated_at = :at "
        "where org_id = :o and brain = :b and subject = :s and version = :v"),
        {"at": at, "o": org_id, "b": brain, "s": subject, "v": active["version"]})

    predecessor = active["supersedes"]
    if predecessor is not None:
        # restore only if that exact version still exists and is not itself superseded by a newer
        # active value (there is none now — we just deactivated the head).
        restored = conn.execute(text(
            "update learned_brain_entries set active = true, deactivated_at = null "
            "where org_id = :o and brain = :b and subject = :s and version = :v"),
            {"o": org_id, "b": brain, "s": subject, "v": predecessor})
        if restored.rowcount == 1:
            return f"restored_v{predecessor}"
    return "rolled_back_to_empty"


def publish(conn, obj: LearningObject, *, target_state: LearningState, at: datetime) -> str:
    """Dispatch a governed proposal to its sink and record the transition."""
    from_state = LearningState.GOVERNED.value
    if target_state is LearningState.TEMPORARY:
        result = publish_runtime(conn, obj, at=at)
    elif target_state is LearningState.HUMAN_REVIEW:
        # Knowledge → suggestion queue; Org/constrained brains wait for a human before publishing.
        result = (publish_knowledge(conn, obj, at=at)
                  if obj.target is LearningTarget.KNOWLEDGE_SUGGESTION else "queued_for_review")
    elif target_state is LearningState.PROMOTED:
        if obj.target is LearningTarget.METRICS:
            result = publish_metric(conn, obj, at=at)
        elif obj.target in _BRAIN_TARGETS:
            result = publish_brain(conn, obj, at=at)
            target_state = LearningState.PUBLISHED
        else:
            result = "promoted"
    else:
        result = "rejected"
    log_transition(conn, org_id=obj.org_id, learning_id=obj.learning_id, from_state=from_state,
                   to_state=target_state.value, reason_code=result, at=at)
    return result


__all__ = ["log_transition", "persist", "publish", "publish_brain", "publish_knowledge",
           "publish_metric", "publish_runtime", "rollback_brain"]
