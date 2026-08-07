"""PostgreSQL authority for governed learning, publication, rollback and TTL expiry."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.learning import (
    BrainTarget,
    LearningObject,
    LearningState,
    can_transition_learning,
)
from genios_engine.feedback.governance import LearningPolicy, ValidationResult
from genios_engine.feedback.units import (
    DeliveryFact,
    EnterpriseFact,
    FeedbackFact,
    LearningBatch,
    OutcomeFact,
)
from genios_engine.platform.canonical import canonical_dumps, stable_id
from genios_engine.platform.ids import new_id

SOURCE_WINDOW_DAYS = 28


def _json(value: Any, default: Any) -> Any:
    if isinstance(value, type(default)):
        return value
    try:
        decoded = json.loads(value or ("{}" if isinstance(default, dict) else "[]"))
    except (TypeError, ValueError):
        return default
    return decoded if isinstance(decoded, type(default)) else default


def _get(row: Any, name: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(name, default)
    return getattr(row, name, default)


def load_policy(conn, org_id: str, policy_key: str = "default") -> LearningPolicy:
    row = conn.execute(text(
        "select learning_enabled,min_observations,min_distinct_days,min_confidence_bp,"
        "max_noise_bp,max_conflict_bp,min_business_value_bp,max_temporary_ttl_hours,"
        "require_human_targets,blocked_subject_prefixes from learning_policies "
        "where org_id=:o and policy_key=:p"), {"o": org_id, "p": policy_key}).first()
    if row is None:
        return LearningPolicy()
    targets = frozenset(BrainTarget(str(item)) for item in (_get(row, "require_human_targets") or ()))
    return LearningPolicy(
        enabled=bool(_get(row, "learning_enabled")),
        min_observations=int(_get(row, "min_observations")),
        min_distinct_days=int(_get(row, "min_distinct_days")),
        min_confidence_bp=int(_get(row, "min_confidence_bp")),
        max_noise_bp=int(_get(row, "max_noise_bp")),
        max_conflict_bp=int(_get(row, "max_conflict_bp")),
        min_business_value_bp=int(_get(row, "min_business_value_bp")),
        max_temporary_ttl_hours=int(_get(row, "max_temporary_ttl_hours")),
        require_human_targets=targets,
        blocked_subject_prefixes=tuple(_get(row, "blocked_subject_prefixes") or ()))


def load_batch(conn, org_id: str, evaluated_at: datetime,
               window_days: int = SOURCE_WINDOW_DAYS) -> LearningBatch:
    """Read the three Atlas inputs from durable lower-layer seams.

    Card feedback is the latest canonical verdict, execution outcomes measure real efficacy,
    graph observations are normalized enterprise events, and delivery rows provide transport
    performance.  Open delivery rows remain visible but never become failures.
    """
    since = evaluated_at - timedelta(days=window_days)
    feedback: list[FeedbackFact] = []
    for row in conn.execute(text(
        "select feedback_id,card_id,cause,detail,occurred_at from card_feedback_verdicts "
        "where org_id=:o and occurred_at>=:since and occurred_at<=:at"),
            {"o": org_id, "since": since, "at": evaluated_at}):
        detail = _json(_get(row, "detail"), {})
        preference = detail.get("preference") if isinstance(detail.get("preference"), dict) else {}
        feedback.append(FeedbackFact(
            feedback_id=str(_get(row, "feedback_id")),
            subject_key=str(_get(row, "card_id")), action=str(_get(row, "cause")),
            occurred_at=_get(row, "occurred_at"), explicit=True,
            preference_key=preference.get("key"), preference_value=preference.get("value"),
            preference_scope=preference.get("scope"),
            preference_category=preference.get("category"),
            source_ref=str(_get(row, "feedback_id"))))

    outcomes = tuple(OutcomeFact(
        outcome_id=str(_get(row, "outcome_id")), capability_id=str(_get(row, "capability_id")),
        play_id=str(_get(row, "play_id")), label=str(_get(row, "label")),
        closed_at=_get(row, "closed_at"), progress_bp=int(_get(row, "progress_bp", 0)),
        reminders_sent=int(_get(row, "reminders_sent", 0)),
        escalations_fired=int(_get(row, "escalations_fired", 0)),
        seconds_to_close=int(_get(row, "seconds_to_close", 0)))
        for row in conn.execute(text(
            "select outcome_id,capability_id,play_id,label,closed_at,progress_bp,"
            "reminders_sent,escalations_fired,seconds_to_close from execution_outcomes "
            "where org_id=:o and closed_at>=:since and closed_at<=:at"),
            {"o": org_id, "since": since, "at": evaluated_at}))

    events = tuple(EnterpriseFact(
        event_id=str(_get(row, "observation_id")),
        pattern_key=str(_get(row, "subject_node_id") or _get(row, "kind")),
        kind=str(_get(row, "kind")), occurred_at=_get(row, "occurred_at"))
        for row in conn.execute(text(
            "select observation_id,subject_node_id,kind,coalesce(occurred_at,created_at) as "
            "occurred_at from graph_observations where org_id=:o and status='active' "
            "and coalesce(occurred_at,created_at)>=:since "
            "and coalesce(occurred_at,created_at)<=:at"),
            {"o": org_id, "since": since, "at": evaluated_at}))

    deliveries = tuple(DeliveryFact(
        delivery_id=str(_get(row, "id")), channel=str(_get(row, "channel")),
        status=str(_get(row, "status")), created_at=_get(row, "created_at"),
        delivered_at=_get(row, "delivered_at"), attempts=int(_get(row, "attempts", 0)),
        deferrals=int(_get(row, "defer_count", 0)), reason_code=_get(row, "gate_reason"))
        for row in conn.execute(text(
            "select id,channel,status,created_at,delivered_at,attempts,defer_count,gate_reason "
            "from delivery_outbox where org_id=:o and created_at>=:since and created_at<=:at"),
            {"o": org_id, "since": since, "at": evaluated_at}))
    return LearningBatch(org_id=org_id, evaluated_at=evaluated_at, feedback=tuple(feedback),
                         outcomes=outcomes, events=events, deliveries=deliveries)


def claim_run(conn, org_id: str, evaluated_at: datetime) -> tuple[str, bool]:
    period = (evaluated_at - timedelta(days=evaluated_at.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    run_id = stable_id("learnrun", {"org_id": org_id, "period_start": period})
    row = conn.execute(text(
        "insert into learning_runs (run_id,org_id,period_start,evaluation_time,units_planned) "
        "values (:id,:o,:period,:at,:units) on conflict (org_id,period_start) do nothing "
        "returning run_id"),
        {"id": run_id, "o": org_id, "period": period, "at": evaluated_at,
         "units": ["feedback_learning", "outcome_analysis", "pattern_learning",
                   "preference_learning", "temporary_memory", "behavior_evolution",
                   "adaptive_evolution", "recommendation_learning", "performance_optimization",
                   "knowledge_evolution", "learning_validation"]}).first()
    return run_id, row is not None


def persist_object(conn, item: LearningObject, run_id: str | None) -> bool:
    item.verify_round_trip()
    evidence = item.evidence
    result = conn.execute(text(
        "insert into learning_objects (org_id,learning_id,semantic_hash,schema_version,unit_name,"
        "target_brain,subject_key,current_state,confidence_bp,observations,distinct_days,"
        "positive_evidence,negative_evidence,noise_bp,conflict_bp,business_value_bp,policy_key,"
        "source_run_id,payload,observed_at,expires_at) values "
        "(:o,:id,:hash,:sv,:unit,:target,:subject,'observed',:confidence,:observations,:days,"
        ":positive,:negative,:noise,:conflict,:value,:policy,:run,cast(:payload as jsonb),:at,:exp) "
        "on conflict (org_id,semantic_hash) do nothing returning learning_id"),
        {"o": item.org_id, "id": item.learning_id, "hash": item.semantic_hash,
         "sv": item.schema_version, "unit": item.unit.value, "target": item.target.value,
         "subject": item.subject_key, "confidence": evidence.confidence_bp,
         "observations": evidence.observations, "days": evidence.distinct_days,
         "positive": evidence.positive, "negative": evidence.negative,
         "noise": evidence.noise_bp, "conflict": evidence.conflict_bp,
         "value": evidence.business_value_bp, "policy": item.policy_key, "run": run_id,
         "payload": canonical_dumps(item.to_semantic_dict()), "at": item.observed_at,
         "exp": item.expires_at}).first()
    if result is None:
        return False
    conn.execute(text(
        "insert into learning_transitions (transition_id,org_id,learning_id,from_state,to_state,"
        "reason_code,actor,detail,occurred_at) values "
        "(:id,:o,:learning,null,'observed','object_persisted','system','{}',:at)"),
        {"id": new_id("ltr"), "o": item.org_id, "learning": item.learning_id,
         "at": item.observed_at})
    return True


def transition(conn, item: LearningObject, target: LearningState, reason_code: str,
               *, actor: str = "system", at: datetime, detail: dict | None = None) -> None:
    row = conn.execute(text(
        "select current_state from learning_objects where org_id=:o and learning_id=:id for update"),
        {"o": item.org_id, "id": item.learning_id}).first()
    if row is None:
        raise ValueError("learning object not found")
    current = LearningState(str(_get(row, "current_state", row[0])))
    if current is target:
        return
    if not can_transition_learning(current, target):
        raise ValueError(f"illegal learning transition: {current.value} -> {target.value}")
    changed = conn.execute(text(
        "update learning_objects set current_state=:target,requires_review=:review,updated_at=:at "
        "where org_id=:o and learning_id=:id and current_state=:current"),
        {"target": target.value, "review": target is LearningState.HUMAN_REVIEW,
         "at": at, "o": item.org_id, "id": item.learning_id,
         "current": current.value})
    if changed.rowcount != 1:
        raise RuntimeError("learning transition lost serialization race")
    conn.execute(text(
        "insert into learning_transitions (transition_id,org_id,learning_id,from_state,to_state,"
        "reason_code,actor,detail,occurred_at) values "
        "(:id,:o,:learning,:before,:after,:reason,:actor,cast(:detail as jsonb),:at)"),
        {"id": new_id("ltr"), "o": item.org_id, "learning": item.learning_id,
         "before": current.value, "after": target.value, "reason": reason_code,
         "actor": actor, "detail": canonical_dumps(detail or {}), "at": at})


def _publish_brain(conn, item: LearningObject, at: datetime) -> None:
    prior = conn.execute(text(
        "select entry_id,learning_id,version from learned_brain_entries where org_id=:o "
        "and brain=:brain and subject_key=:subject and active for update"),
        {"o": item.org_id, "brain": item.target.value, "subject": item.subject_key}).first()
    version = int(_get(prior, "version", 0)) + 1 if prior is not None else 1
    if prior is not None:
        conn.execute(text(
            "update learned_brain_entries set active=false,ended_at=:at,ended_reason='superseded' "
            "where org_id=:o and entry_id=:id and active"),
            {"at": at, "o": item.org_id, "id": _get(prior, "entry_id")})
        old = conn.execute(text(
            "select current_state from learning_objects where org_id=:o and learning_id=:id "
            "for update"), {"o": item.org_id, "id": _get(prior, "learning_id")}).first()
        if old is not None and str(_get(old, "current_state", old[0])) == "published":
            old_payload = conn.execute(text(
                "select payload from learning_objects where org_id=:o and learning_id=:id"),
                {"o": item.org_id, "id": _get(prior, "learning_id")}).first()
            if old_payload is not None:
                old_item = LearningObject.from_semantic_dict(
                    _json(_get(old_payload, "payload", old_payload[0]), {}))
                transition(conn, old_item, LearningState.SUPERSEDED, "newer_learning_published",
                           at=at, detail={"superseded_by": item.learning_id})
    entry_id = stable_id("brain", {"org_id": item.org_id, "brain": item.target.value,
                                   "subject_key": item.subject_key, "version": version})
    conn.execute(text(
        "insert into learned_brain_entries (org_id,entry_id,brain,subject_key,version,value,"
        "confidence_bp,learning_id,active,effective_at) values "
        "(:o,:id,:brain,:subject,:version,cast(:value as jsonb),:confidence,:learning,true,:at)"),
        {"o": item.org_id, "id": entry_id, "brain": item.target.value,
         "subject": item.subject_key, "version": version,
         "value": canonical_dumps(dict(item.value)), "confidence": item.evidence.confidence_bp,
         "learning": item.learning_id, "at": at})


def publish(conn, item: LearningObject, at: datetime) -> None:
    """Evolution Publisher. The closed target enum makes an Expert write impossible."""
    if item.target in {BrainTarget.ORGANIZATION, BrainTarget.BEHAVIOR, BrainTarget.ADAPTIVE}:
        _publish_brain(conn, item, at)
    elif item.target is BrainTarget.RUNTIME:
        conn.execute(text(
            "insert into temporary_memories (org_id,memory_id,subject_key,value,learning_id,"
            "confidence_bp,observed_at,expires_at) values "
            "(:o,:id,:subject,cast(:value as jsonb),:learning,:confidence,:observed,:expires) "
            "on conflict (org_id,learning_id) do nothing"),
            {"o": item.org_id, "id": stable_id("memory", item.learning_id),
             "subject": item.subject_key, "value": canonical_dumps(dict(item.value)),
             "learning": item.learning_id, "confidence": item.evidence.confidence_bp,
             "observed": item.observed_at, "expires": item.expires_at})
        return
    elif item.target is BrainTarget.METRICS:
        start = item.observed_at - timedelta(days=SOURCE_WINDOW_DAYS)
        conn.execute(text(
            "insert into learning_metrics (org_id,metric_id,metric_key,period_start,period_end,"
            "value,learning_id) values "
            "(:o,:id,:key,:start,:end,cast(:value as jsonb),:learning) "
            "on conflict (org_id,metric_key,period_start,period_end) do nothing"),
            {"o": item.org_id, "id": stable_id("lmetric", item.learning_id),
             "key": item.subject_key, "start": start, "end": item.observed_at,
             "value": canonical_dumps(dict(item.value)), "learning": item.learning_id})
    elif item.target is BrainTarget.KNOWLEDGE_SUGGESTION:
        raise ValueError("knowledge suggestions must enter human review, never publish")
    transition(conn, item, LearningState.PUBLISHED, "published_to_dynamic_target", at=at)
    conn.execute(text(
        "update learning_objects set published_at=:at where org_id=:o and learning_id=:id"),
        {"at": at, "o": item.org_id, "id": item.learning_id})


def enqueue_review(conn, item: LearningObject) -> None:
    if item.target is not BrainTarget.KNOWLEDGE_SUGGESTION:
        return
    conn.execute(text(
        "insert into knowledge_suggestions (org_id,suggestion_id,learning_id,subject_key,"
        "suggestion,evidence) values "
        "(:o,:id,:learning,:subject,cast(:suggestion as jsonb),cast(:evidence as jsonb)) "
        "on conflict (org_id,learning_id) do nothing"),
        {"o": item.org_id, "id": stable_id("ksug", item.learning_id),
         "learning": item.learning_id, "subject": item.subject_key,
         "suggestion": canonical_dumps(dict(item.value)),
         "evidence": canonical_dumps(item.evidence.to_semantic_dict())})


def apply_path(conn, item: LearningObject, path: tuple[ValidationResult, ...],
               at: datetime) -> LearningState:
    state = LearningState.OBSERVED
    for decision in path:
        if decision.state is state:
            continue
        transition(conn, item, decision.state, decision.reason_code, at=at)
        state = decision.state
    if state is LearningState.HUMAN_REVIEW:
        enqueue_review(conn, item)
    elif state is LearningState.PROMOTED:
        publish(conn, item, at)
        state = LearningState.PUBLISHED
    elif state is LearningState.TEMPORARY:
        publish(conn, item, at)
    return state


def expire_memories(conn, at: datetime) -> int:
    rows = conn.execute(text(
        "select m.learning_id,o.payload from temporary_memories m join learning_objects o "
        "on o.org_id=m.org_id and o.learning_id=m.learning_id "
        "where m.expired_at is null and m.expires_at<=:at for update of m,o"), {"at": at}).all()
    for row in rows:
        item = LearningObject.from_semantic_dict(_json(_get(row, "payload", row[1]), {}))
        conn.execute(text(
            "update temporary_memories set expired_at=:at where org_id=:o and learning_id=:id "
            "and expired_at is null"), {"at": at, "o": item.org_id, "id": item.learning_id})
        transition(conn, item, LearningState.EXPIRED, "temporary_ttl_elapsed", at=at)
    return len(rows)


def complete_run(conn, run_id: str, org_id: str, *, observed: int, published: int,
                 held: int, rejected: int, result: dict[str, Any], at: datetime) -> None:
    conn.execute(text(
        "update learning_runs set status='completed',objects_observed=:observed,"
        "objects_published=:published,objects_held=:held,objects_rejected=:rejected,"
        "result=cast(:result as jsonb),completed_at=:at where run_id=:id and org_id=:o"),
        {"observed": observed, "published": published, "held": held,
         "rejected": rejected, "result": canonical_dumps(result), "at": at,
         "id": run_id, "o": org_id})


__all__ = ["SOURCE_WINDOW_DAYS", "apply_path", "claim_run", "complete_run",
           "enqueue_review", "expire_memories", "load_batch", "load_policy", "persist_object",
           "publish", "transition"]
