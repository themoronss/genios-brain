"""PostgreSQL authority for governed learning, publication, rollback and TTL expiry."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.learning import (
    BRAIN_TARGETS,
    LearningObject,
    LearningState,
    LearningTarget,
    can_transition_learning,
)
from genios_engine.contracts.execution import ExecutionObject
from genios_engine.contracts.visibility import PRIVATE, Visibility, narrowest
from genios_engine.feedback.governance import LearningPolicy, ValidationResult
from genios_engine.feedback.units import (
    DeliveryFact,
    EnterpriseFact,
    FeedbackFact,
    InputRejection,
    LearningBatch,
    OutcomeFact,
)
from genios_engine.platform.canonical import canonical_dumps, semantic_hash, stable_id
from genios_engine.platform.db import lock_tenant_for_mutation
from genios_engine.platform.ids import new_id

SOURCE_WINDOW_DAYS = 28


def lock_learning_tenant(conn, org_id: str) -> None:
    """Take Layer 6's tenant-root lock before any policy, object or memory lock."""
    lock_tenant_for_mutation(conn, org_id)


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


def _private(reason: str) -> dict[str, Any]:
    return Visibility(scope=PRIVATE, principals=[], derived_from=reason).model_dump()


def _source_visibility(value: Any, *, nested: bool = False) -> tuple[dict[str, Any], bool]:
    raw = _json(value, {})
    if nested:
        raw = raw.get("visibility") if isinstance(raw, dict) else None
    required = {"scope", "principals", "derived_from"}
    if not isinstance(raw, dict) or not required <= set(raw):
        return _private("unresolved:l6-source-visibility"), False
    try:
        parsed = Visibility.model_validate(raw)
    except (TypeError, ValueError):
        return _private("invalid:l6-source-visibility"), False
    derived_from = str(parsed.derived_from or "").strip()
    if not derived_from:
        return _private("invalid:l6-source-visibility"), False
    return Visibility(
        scope=parsed.scope,
        principals=sorted({str(item).strip().lower() for item in parsed.principals
                           if str(item).strip()}),
        derived_from=derived_from,
    ).model_dump(), True


def _execution_envelope(value: Any, *, org_id: str, execution_id: Any,
                        expected_hash: Any = None) -> tuple[ExecutionObject, dict[str, Any], bool]:
    """Rehydrate an immutable L5 object before trusting its ACL or trace lineage."""
    payload = _json(value, {})
    try:
        execution = ExecutionObject.from_semantic_dict(payload)
        execution.verify_round_trip()
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("execution payload failed contract verification") from exc
    if execution.org_id != org_id or execution.execution_id != str(execution_id or ""):
        raise ValueError("execution lineage identity mismatch")
    if expected_hash is not None and execution.semantic_hash != str(expected_hash):
        raise ValueError("execution lineage hash mismatch")
    visibility, complete = _source_visibility(payload, nested=True)
    return execution, visibility, complete


def _input_rejection(kind: str, source_ref: Any, reason_code: str,
                     raw: Any) -> InputRejection:
    # Source identifiers and malformed values may contain PII or invalid identifier characters.
    # The rejection ledger retains only stable hashes plus a closed reason code.
    ref = stable_id("lsource", {"kind": kind, "source_ref": str(source_ref or "missing")})
    return InputRejection(source_kind=kind, source_ref=ref, reason_code=reason_code,
                          payload_hash=semantic_hash({"source_ref": ref, "error": str(raw)[:256]}))


def load_policy(conn, org_id: str, policy_key: str = "default", *,
                for_share: bool = False) -> LearningPolicy:
    lock = " for share" if for_share else ""
    row = conn.execute(text(
        "select revision,learning_enabled,min_observations,min_distinct_days,min_confidence_bp,"
        "max_noise_bp,max_conflict_bp,min_business_value_bp,max_temporary_ttl_hours,"
        "require_human_targets,blocked_targets,blocked_subject_prefixes,"
        "require_review_for_constrained_visibility from learning_policies "
        "where org_id=:o and policy_key=:p" + lock),
        {"o": org_id, "p": policy_key}).first()
    if row is None:
        return LearningPolicy()
    targets = frozenset(LearningTarget(str(item))
                        for item in (_get(row, "require_human_targets") or ()))
    blocked_targets = frozenset(LearningTarget(str(item))
                                for item in (_get(row, "blocked_targets") or ()))
    return LearningPolicy(
        revision=int(_get(row, "revision", 0)),
        enabled=bool(_get(row, "learning_enabled")),
        min_observations=int(_get(row, "min_observations")),
        min_distinct_days=int(_get(row, "min_distinct_days")),
        min_confidence_bp=int(_get(row, "min_confidence_bp")),
        max_noise_bp=int(_get(row, "max_noise_bp")),
        max_conflict_bp=int(_get(row, "max_conflict_bp")),
        min_business_value_bp=int(_get(row, "min_business_value_bp")),
        max_temporary_ttl_hours=int(_get(row, "max_temporary_ttl_hours")),
        require_human_targets=targets,
        blocked_targets=blocked_targets,
        blocked_subject_prefixes=tuple(_get(row, "blocked_subject_prefixes") or ()),
        require_review_for_constrained_visibility=bool(
            _get(row, "require_review_for_constrained_visibility", True)))


def ensure_policy(conn, org_id: str, policy_key: str = "default", *,
                  for_share: bool = True) -> LearningPolicy:
    conn.execute(text(
        "insert into learning_policies (org_id,policy_key,revision) values (:o,:p,1) "
        "on conflict (org_id,policy_key) do nothing"), {"o": org_id, "p": policy_key})
    return load_policy(conn, org_id, policy_key, for_share=for_share)


def load_batch(conn, org_id: str, evaluated_at: datetime,
               window_days: int = SOURCE_WINDOW_DAYS) -> LearningBatch:
    """Read the three Atlas inputs from durable lower-layer seams.

    Card feedback is the latest canonical verdict, execution outcomes measure real efficacy,
    graph observations are normalized enterprise events, and delivery rows provide transport
    performance.  Open delivery rows remain visible but never become failures.
    """
    since = evaluated_at - timedelta(days=window_days)
    rejections: list[InputRejection] = []
    feedback: list[FeedbackFact] = []
    feedback_rows = conn.execute(text(
        "select distinct on (r.feedback_id) r.revision_id,r.feedback_id,r.card_id,r.cause,"
        "r.reason,r.detail,r.actor_id,r.organization_authorized,r.verdict_version,r.occurred_at,"
        "v.capability_id,v.rule_id,k.signal_id,x.execution_id,x.payload as execution_payload,"
        "case when position('@' in r.actor_id)>0 then lower(r.actor_id) "
        "when r.actor_id='org_primary_key' then lower(tenant.email) "
        "else lower(seat.email) end as subject_principal "
        "from card_feedback_revisions r join card_feedback_verdicts v "
        "on v.org_id=r.org_id and v.feedback_id=r.feedback_id and v.card_id=r.card_id "
        "join cards k on k.org_id=r.org_id and k.card_id=r.card_id "
        "join executions x on x.org_id=k.org_id and x.execution_id=k.execution_id "
        "left join org_seats seat on seat.org_id=r.org_id and seat.seat_id=r.actor_id "
        "join orgs tenant on tenant.id=r.org_id "
        "where r.org_id=:o and r.occurred_at>=:since and r.occurred_at<=:at "
        "order by r.feedback_id,r.verdict_version desc,r.revision_id desc"),
        {"o": org_id, "since": since, "at": evaluated_at})
    for row in feedback_rows:
        source_ref = _get(row, "revision_id")
        try:
            execution, visibility, complete = _execution_envelope(
                _get(row, "execution_payload"), org_id=org_id,
                execution_id=_get(row, "execution_id"))
            if execution.capability_id != str(_get(row, "capability_id")):
                raise ValueError("feedback capability does not match frozen execution")
            detail = _json(_get(row, "detail"), {})
            preference = (detail.get("preference")
                          if isinstance(detail.get("preference"), dict) else {})
            base = dict(
                feedback_id=str(_get(row, "feedback_id")),
                subject_key=f"{_get(row, 'capability_id')}:{_get(row, 'rule_id')}",
                action=str(_get(row, "cause")), reason=_get(row, "reason"),
                occurred_at=_get(row, "occurred_at"),
                explicit=True, source_ref=str(source_ref),
                actor_key=str(_get(row, "actor_id")) if _get(row, "actor_id") else None,
                subject_principal=_get(row, "subject_principal"),
                trace_id=execution.reasoning_run_id,
                independence_key=str(_get(row, "card_id")), visibility=visibility,
                lineage_complete=complete)
            if preference:
                try:
                    feedback.append(FeedbackFact(
                        **base, preference_key=preference.get("key"),
                        preference_value=preference.get("value"),
                        preference_scope=preference.get("scope"),
                        preference_category=preference.get("category"),
                        organization_authorized=bool(
                            _get(row, "organization_authorized", False))))
                except (TypeError, ValueError) as exc:
                    # A bad optional preference cannot erase the otherwise-valid base verdict.
                    rejections.append(_input_rejection(
                        "feedback_preference", source_ref, "malformed_or_unauthorized_preference",
                        {"error": type(exc).__name__}))
                    feedback.append(FeedbackFact(**base))
            else:
                feedback.append(FeedbackFact(**base))
        except (TypeError, ValueError) as exc:
            rejections.append(_input_rejection(
                "feedback", source_ref, "malformed_feedback", {"error": type(exc).__name__}))

    outcomes: list[OutcomeFact] = []
    outcome_rows = conn.execute(text(
        "select o.outcome_id,o.execution_id,o.capability_id,o.play_id,o.label,o.closed_at,"
        "o.progress_bp,o.reminders_sent,o.escalations_fired,o.seconds_to_close,"
        "x.payload as execution_payload from execution_outcomes o "
        "join executions x on x.org_id=o.org_id and x.execution_id=o.execution_id "
        "and x.decision_hash=o.decision_hash and x.capability_id=o.capability_id "
        "and x.play_id=o.play_id where o.org_id=:o and o.closed_at>=:since and o.closed_at<=:at"),
        {"o": org_id, "since": since, "at": evaluated_at})
    for row in outcome_rows:
        source_ref = _get(row, "outcome_id")
        try:
            execution, visibility, complete = _execution_envelope(
                _get(row, "execution_payload"), org_id=org_id,
                execution_id=_get(row, "execution_id"))
            if (execution.capability_id != str(_get(row, "capability_id"))
                    or str(execution.metadata.get("play_id")) != str(_get(row, "play_id"))):
                raise ValueError("outcome does not match frozen execution")
            outcomes.append(OutcomeFact(
                outcome_id=str(source_ref), capability_id=str(_get(row, "capability_id")),
                play_id=str(_get(row, "play_id")), label=str(_get(row, "label")),
                closed_at=_get(row, "closed_at"), progress_bp=int(_get(row, "progress_bp", 0)),
                reminders_sent=int(_get(row, "reminders_sent", 0)),
                escalations_fired=int(_get(row, "escalations_fired", 0)),
                seconds_to_close=int(_get(row, "seconds_to_close", 0)),
                trace_id=execution.reasoning_run_id,
                independence_key=str(_get(row, "execution_id")), visibility=visibility,
                lineage_complete=complete))
        except (TypeError, ValueError) as exc:
            rejections.append(_input_rejection(
                "outcome", source_ref, "malformed_outcome", {"error": type(exc).__name__}))

    events: list[EnterpriseFact] = []
    event_rows = conn.execute(text(
        "select o.observation_id,o.subject_node_id,o.kind,"
        "coalesce(o.occurred_at,o.created_at) as occurred_at,o.confidence,"
        "o.created_by_event_id,r.source_ref_id,r.event_id as lineage_event_id,"
        "coalesce(r.independence_group,r.event_id) as independence_group,se.visibility "
        "from graph_observations o left join graph_source_refs r "
        "on r.org_id=o.org_id and r.observation_id=o.observation_id "
        "and r.event_id=o.created_by_event_id left join source_events se "
        "on se.org_id=r.org_id and se.event_id=r.event_id "
        "where o.org_id=:o and o.status='active' "
        "and coalesce(o.occurred_at,o.created_at)>=:since "
        "and coalesce(o.occurred_at,o.created_at)<=:at "
        "order by o.observation_id,r.source_ref_id"),
        {"o": org_id, "since": since, "at": evaluated_at})
    grouped_event_rows: dict[str, list[Any]] = {}
    for row in event_rows:
        grouped_event_rows.setdefault(str(_get(row, "observation_id")), []).append(row)
    for source_ref, source_rows in grouped_event_rows.items():
        try:
            if any(not _get(row, "source_ref_id") or not _get(row, "lineage_event_id")
                   for row in source_rows):
                raise ValueError("graph observation lacks exact source lineage")
            parsed_visibility: list[Visibility] = []
            complete = True
            for row in source_rows:
                value, valid = _source_visibility(_get(row, "visibility"))
                parsed_visibility.append(Visibility.model_validate(value))
                complete = complete and valid
            visibility = narrowest(*parsed_visibility).model_dump()
            row = source_rows[0]
            confidence = int(Decimal(str(_get(row, "confidence", "0"))) * 10_000)
            lineage_events = sorted({str(_get(item, "lineage_event_id"))
                                     for item in source_rows})
            independence = sorted({str(_get(item, "independence_group"))
                                   for item in source_rows})
            events.append(EnterpriseFact(
                event_id=str(source_ref),
                pattern_key=str(_get(row, "subject_node_id") or _get(row, "kind")),
                kind=str(_get(row, "kind")), occurred_at=_get(row, "occurred_at"),
                source_confidence_bp=confidence,
                trace_id=stable_id("ltrace", {"source_events": lineage_events}),
                independence_key=stable_id("lind", {"source_groups": independence}),
                visibility=visibility, lineage_complete=complete))
        except (InvalidOperation, TypeError, ValueError) as exc:
            rejections.append(_input_rejection(
                "enterprise_event", source_ref, "malformed_enterprise_event",
                {"error": type(exc).__name__}))

    structured_rows = conn.execute(text(
        "select event_id,pattern_key,kind,actor_key,value,explicit_memory,occurred_at,expires_at,"
        "trace_id,visibility,independence_key from learning_event_inbox where org_id=:o "
        "and occurred_at>=:since and occurred_at<=:at"),
        {"o": org_id, "since": since, "at": evaluated_at})
    for row in structured_rows:
        source_ref = _get(row, "event_id")
        try:
            visibility, complete = _source_visibility(_get(row, "visibility"))
            events.append(EnterpriseFact(
                event_id=str(source_ref), pattern_key=str(_get(row, "pattern_key")),
                kind=str(_get(row, "kind")), occurred_at=_get(row, "occurred_at"),
                actor_key=_get(row, "actor_key"), value=_json(_get(row, "value"), {}),
                explicit_memory=bool(_get(row, "explicit_memory")),
                expires_at=_get(row, "expires_at"), source_confidence_bp=10_000,
                trace_id=str(_get(row, "trace_id") or source_ref),
                independence_key=str(_get(row, "independence_key") or source_ref),
                visibility=visibility, lineage_complete=complete))
        except (TypeError, ValueError) as exc:
            rejections.append(_input_rejection(
                "structured_event", source_ref, "malformed_structured_event",
                {"error": type(exc).__name__}))

    deliveries: list[DeliveryFact] = []
    delivery_rows = conn.execute(text(
        "select d.id,d.channel,d.created_at,d.execution_id,d.execution_hash,d.execution_event_id,"
        "x.payload as execution_payload,"
        "coalesce((select e.event_type from delivery_events e where e.org_id=d.org_id "
        "and e.delivery_id=d.id and e.occurred_at<=:at order by e.occurred_at desc,e.event_id desc "
        "limit 1),'queued') as lifecycle_status,"
        "(select e.occurred_at from delivery_events e where e.org_id=d.org_id "
        "and e.delivery_id=d.id and e.occurred_at<=:at order by e.occurred_at desc,e.event_id desc "
        "limit 1) as lifecycle_at,"
        "(select e.reason_code from delivery_events e where e.org_id=d.org_id "
        "and e.delivery_id=d.id and e.occurred_at<=:at order by e.occurred_at desc,e.event_id desc "
        "limit 1) as reason_code,"
        "(select min(e.occurred_at) from delivery_events e where e.org_id=d.org_id "
        "and e.delivery_id=d.id and e.event_type='delivered' and e.occurred_at<=:at) delivered_at,"
        "(select min(e.occurred_at) from delivery_events e where e.org_id=d.org_id "
        "and e.delivery_id=d.id and e.event_type='viewed' and e.occurred_at<=:at) viewed_at,"
        "(select min(e.occurred_at) from delivery_events e where e.org_id=d.org_id "
        "and e.delivery_id=d.id and e.event_type='ignored' and e.occurred_at<=:at) ignored_at,"
        "(select min(e.occurred_at) from delivery_events e where e.org_id=d.org_id "
        "and e.delivery_id=d.id and e.event_type='accepted' and e.occurred_at<=:at) accepted_at,"
        "(select min(e.occurred_at) from delivery_events e where e.org_id=d.org_id "
        "and e.delivery_id=d.id and e.event_type='executed' and e.occurred_at<=:at) executed_at,"
        "(select min(e.occurred_at) from delivery_events e where e.org_id=d.org_id "
        "and e.delivery_id=d.id and e.event_type='expired' and e.occurred_at<=:at) expired_at,"
        "(select count(*) from delivery_attempts a where a.org_id=d.org_id "
        "and a.delivery_id=d.id and a.started_at<=:at) attempts,"
        "(select count(*) from delivery_events e where e.org_id=d.org_id "
        "and e.delivery_id=d.id and e.event_type='deferred' and e.occurred_at<=:at) deferrals "
        "from delivery_outbox d join executions x on x.org_id=d.org_id "
        "and x.execution_id=d.execution_id where d.org_id=:o "
        "and d.created_at<=:at and (d.created_at>=:since or exists ("
        "select 1 from delivery_events recent where recent.org_id=d.org_id "
        "and recent.delivery_id=d.id and recent.occurred_at>=:since "
        "and recent.occurred_at<=:at))"),
        {"o": org_id, "since": since, "at": evaluated_at})
    for row in delivery_rows:
        source_ref = _get(row, "id")
        try:
            if not _get(row, "execution_hash"):
                raise ValueError("delivery lacks frozen execution hash")
            execution, visibility, complete = _execution_envelope(
                _get(row, "execution_payload"), org_id=org_id,
                execution_id=_get(row, "execution_id"),
                expected_hash=_get(row, "execution_hash"))
            status = str(_get(row, "lifecycle_status"))
            deliveries.append(DeliveryFact(
                delivery_id=str(source_ref), channel=str(_get(row, "channel")), status=status,
                lifecycle_status=status, created_at=_get(row, "created_at"),
                lifecycle_at=_get(row, "lifecycle_at"),
                delivered_at=_get(row, "delivered_at"), attempts=int(_get(row, "attempts", 0)),
                deferrals=int(_get(row, "deferrals", 0)), reason_code=_get(row, "reason_code"),
                viewed_at=_get(row, "viewed_at"), ignored_at=_get(row, "ignored_at"),
                accepted_at=_get(row, "accepted_at"), executed_at=_get(row, "executed_at"),
                expired_at=_get(row, "expired_at"), execution_id=str(_get(row, "execution_id")),
                trace_id=execution.reasoning_run_id,
                independence_key=str(_get(row, "execution_id")), visibility=visibility,
                lineage_complete=complete))
        except (TypeError, ValueError) as exc:
            rejections.append(_input_rejection(
                "delivery", source_ref, "malformed_delivery", {"error": type(exc).__name__}))
    return LearningBatch(org_id=org_id, evaluated_at=evaluated_at, feedback=tuple(feedback),
                         outcomes=tuple(outcomes), events=tuple(events),
                         deliveries=tuple(deliveries), rejections=tuple(rejections))


def claim_run(conn, org_id: str, evaluated_at: datetime,
              policy_revision: int) -> tuple[str, bool]:
    period = (evaluated_at - timedelta(days=evaluated_at.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    run_id = stable_id("learnrun", {"org_id": org_id, "period_start": period})
    row = conn.execute(text(
        "insert into learning_runs (run_id,org_id,period_start,evaluation_time,units_planned,"
        "policy_revision,attempt_count) values (:id,:o,:period,:at,:units,:revision,1) "
        "on conflict (org_id,period_start) do update set status='started',"
        "evaluation_time=excluded.evaluation_time,units_planned=excluded.units_planned,"
        "policy_revision=excluded.policy_revision,attempt_count=learning_runs.attempt_count+1,"
        "last_error=null,completed_at=null where learning_runs.status='failed' "
        "returning run_id"),
        {"id": run_id, "o": org_id, "period": period, "at": evaluated_at,
         "revision": policy_revision,
         "units": ["feedback_learning", "outcome_analysis", "pattern_learning",
                   "preference_learning", "temporary_memory", "behavior_evolution",
                   "adaptive_evolution", "recommendation_learning", "performance_optimization",
                   "knowledge_evolution", "learning_validation"]}).first()
    return run_id, row is not None


def persist_object(conn, item: LearningObject, run_id: str | None,
                   policy_revision: int = 0, *, actor: str = "system") -> bool:
    item.verify_round_trip()
    evidence = item.evidence
    result = conn.execute(text(
        "insert into learning_objects (org_id,learning_id,semantic_hash,schema_version,unit_name,"
        "target_brain,subject_key,current_state,confidence_bp,observations,distinct_days,"
        "independent_observations,positive_evidence,negative_evidence,noise_bp,conflict_bp,"
        "business_value_bp,policy_key,"
        "policy_revision,source_run_id,payload,observed_at,first_seen_at,last_seen_at,expires_at,"
        "trace_id,visibility,lineage_complete,subject_principal) values "
        "(:o,:id,:hash,:sv,:unit,:target,:subject,'observed',:confidence,:observations,:days,"
        ":independent,:positive,:negative,:noise,:conflict,:value,:policy,:revision,:run,"
        "cast(:payload as jsonb),:at,:first,:last,:exp,:trace,cast(:visibility as jsonb),"
        ":complete,:principal) "
        "on conflict (org_id,semantic_hash) do nothing returning learning_id"),
        {"o": item.org_id, "id": item.learning_id, "hash": item.semantic_hash,
         "sv": item.schema_version, "unit": item.unit.value, "target": item.target.value,
         "subject": item.subject_key, "confidence": evidence.confidence_bp,
         "observations": evidence.observations, "days": evidence.distinct_days,
         "independent": evidence.independent_observations,
         "positive": evidence.positive, "negative": evidence.negative,
         "noise": evidence.noise_bp, "conflict": evidence.conflict_bp,
         "value": evidence.business_value_bp, "policy": item.policy_key,
         "revision": policy_revision, "run": run_id,
         "payload": canonical_dumps(item.to_semantic_dict()), "at": item.observed_at,
         "first": item.first_seen_at, "last": item.last_seen_at, "exp": item.expires_at,
         "trace": item.trace_id, "visibility": canonical_dumps(dict(item.visibility)),
         "complete": item.lineage_complete, "principal": item.subject_principal}).first()
    if result is None:
        return False
    conn.execute(text(
        "insert into learning_transitions (transition_id,org_id,learning_id,from_state,to_state,"
        "reason_code,actor,detail,occurred_at) values "
        "(:id,:o,:learning,null,'observed','object_persisted',:actor,'{}',:at)"),
        {"id": new_id("ltr"), "o": item.org_id, "learning": item.learning_id,
         "actor": actor, "at": item.observed_at})
    return True


def record_evaluation(conn, item: LearningObject, *, run_id: str,
                      policy_revision: int, evaluation_time: datetime,
                      prior_state: LearningState, result_state: LearningState,
                      reason_code: str, object_inserted: bool) -> None:
    """Append the policy/time decision for one object in one claimed weekly run.

    Object identity intentionally excludes policy and wall-clock evaluation time.  This ledger is
    therefore the missing half of reproducibility: it proves which immutable evidence was tested
    against which frozen policy revision, including held duplicates whose state did not change.
    """
    conn.execute(text(
        "insert into learning_object_evaluations "
        "(org_id,run_id,learning_id,policy_key,policy_revision,evaluation_time,prior_state,"
        "result_state,reason_code,object_inserted) values "
        "(:o,:run,:learning,:policy,:revision,:at,:prior,:result,:reason,:inserted)"),
        {"o": item.org_id, "run": run_id, "learning": item.learning_id,
         "policy": item.policy_key, "revision": policy_revision, "at": evaluation_time,
         "prior": prior_state.value, "result": result_state.value,
         "reason": reason_code, "inserted": object_inserted})


def persist_input_rejections(conn, org_id: str, run_id: str | None,
                             rejections: tuple[InputRejection, ...], at: datetime) -> int:
    for rejection in rejections:
        conn.execute(text(
            "insert into learning_input_rejections (rejection_id,org_id,source_run_id,"
            "source_kind,source_ref,payload_hash,reason_code,occurred_at) values "
            "(:id,:o,:run,:kind,:ref,:hash,:reason,:at) on conflict (org_id,source_kind,"
            "source_ref,payload_hash,reason_code) where source_ref is not null "
            "and payload_hash is not null do nothing"),
            {"id": stable_id("lreject", {"org_id": org_id, "run_id": run_id,
                                          "source_kind": rejection.source_kind,
                                          "source_ref": rejection.source_ref,
                                          "payload_hash": rejection.payload_hash,
                                          "reason": rejection.reason_code}),
             "o": org_id, "run": run_id, "kind": rejection.source_kind,
             "ref": rejection.source_ref, "hash": rejection.payload_hash,
             "reason": rejection.reason_code, "at": at})
    return len(rejections)


def persist_preflight_rejection(conn, item: LearningObject, run_id: str | None,
                                reason_code: str, at: datetime) -> None:
    """Audit a refusal without retaining the proposal's potentially forbidden value."""
    conn.execute(text(
        "insert into learning_input_rejections (rejection_id,org_id,source_run_id,"
        "proposed_learning_id,semantic_hash,unit_name,target_brain,subject_key,trace_id,"
        "visibility,reason_code,occurred_at) values "
        "(:id,:o,:run,:learning,:hash,:unit,:target,:subject,:trace,cast(:visibility as jsonb),"
        ":reason,:at) on conflict (org_id,proposed_learning_id,reason_code) "
        "where proposed_learning_id is not null do nothing"),
        {"id": stable_id("lreject", {"org_id": item.org_id,
                                      "learning_id": item.learning_id,
                                      "reason": reason_code}),
         "o": item.org_id, "run": run_id, "learning": item.learning_id,
         "hash": item.semantic_hash, "unit": item.unit.value, "target": item.target.value,
         "subject": item.subject_key, "trace": item.trace_id,
         "visibility": canonical_dumps(dict(item.visibility)), "reason": reason_code, "at": at})


def load_learning_object(conn, org_id: str, learning_id: str, *,
                         for_update: bool = False) -> tuple[LearningObject, LearningState]:
    suffix = " for update" if for_update else ""
    row = conn.execute(text(
        "select org_id,learning_id,semantic_hash,payload,current_state from learning_objects "
        "where org_id=:o and learning_id=:id" + suffix),
        {"o": org_id, "id": learning_id}).first()
    if row is None:
        raise LookupError("learning object not found")
    payload = _json(_get(row, "payload"), {})
    try:
        item = LearningObject.from_semantic_dict(payload)
        item.verify_round_trip()
    except (KeyError, TypeError, ValueError) as exc:
        raise RuntimeError("stored learning payload failed contract verification") from exc
    if item.org_id != org_id:
        raise RuntimeError("stored learning payload tenant mismatch")
    if item.learning_id != str(_get(row, "learning_id")):
        raise RuntimeError("stored learning payload identity mismatch")
    if item.semantic_hash != str(_get(row, "semantic_hash")):
        raise RuntimeError("stored learning payload hash mismatch")
    return item, LearningState(str(_get(row, "current_state")))


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
    verdict = ({LearningState.HUMAN_REVIEW: "requires_approval",
                LearningState.REJECTED: "forbidden",
                LearningState.TEMPORARY: "allowed",
                LearningState.PROMOTED: "allowed",
                LearningState.PUBLISHED: "allowed",
                LearningState.ROLLED_BACK: "forget"}.get(target))
    promotion = ({LearningState.TEMPORARY: "temporary",
                  LearningState.HUMAN_REVIEW: "human_review",
                  LearningState.PROMOTED: "permanent",
                  LearningState.PUBLISHED: "permanent"}.get(target))
    changed = conn.execute(text(
        "update learning_objects set current_state=:target,requires_review=:review,updated_at=:at,"
        "governance_verdict=coalesce(cast(:verdict as text),governance_verdict),"
        "promotion_state=coalesce(cast(:promotion as text),promotion_state) "
        "where org_id=:o and learning_id=:id and current_state=:current"),
        {"target": target.value, "review": target is LearningState.HUMAN_REVIEW,
         "verdict": verdict, "promotion": promotion,
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


def _publish_brain(conn, item: LearningObject, at: datetime) -> bool:
    lock_key = f"learning-brain:{item.org_id}:{item.target.value}:{item.subject_key}"
    conn.execute(text("select pg_advisory_xact_lock(hashtextextended(:key,0))"),
                 {"key": lock_key})
    latest = conn.execute(text(
        "select entry_id,learning_id,version,active,value,confidence_bp,visibility "
        "from learned_brain_entries where org_id=:o and brain=:brain and subject_key=:subject "
        "order by version desc limit 1 for update"),
        {"o": item.org_id, "brain": item.target.value, "subject": item.subject_key}).first()
    prior = conn.execute(text(
        "select entry_id,learning_id,version,value,confidence_bp,visibility,"
        "(select o.last_seen_at from learning_objects o where o.org_id=:o "
        "and o.learning_id=learned_brain_entries.learning_id) as last_seen_at "
        "from learned_brain_entries "
        "where org_id=:o and brain=:brain and subject_key=:subject and active for update"),
        {"o": item.org_id, "brain": item.target.value, "subject": item.subject_key}).first()
    version = int(_get(latest, "version", 0)) + 1 if latest is not None else 1
    if prior is not None:
        prior_seen = _get(prior, "last_seen_at")
        if prior_seen is None:
            raise RuntimeError("active brain entry lacks learning observation lineage")
        if prior_seen > item.last_seen_at:
            raise RuntimeError("a newer learning value is already active for this subject")
    if (prior is not None
            and canonical_dumps(_json(_get(prior, "value"), {}))
                == canonical_dumps(dict(item.value))
            and canonical_dumps(_json(_get(prior, "visibility"), {}))
                == canonical_dumps(dict(item.visibility))
            and int(_get(prior, "confidence_bp", -1)) == item.evidence.confidence_bp):
        return False
    if prior is not None:
        conn.execute(text(
            "update learned_brain_entries set active=false,ended_at=:at,ended_reason='superseded' "
            "where org_id=:o and entry_id=:id and active"),
            {"at": at, "o": item.org_id, "id": _get(prior, "entry_id")})
        old_item, old_state = load_learning_object(
            conn, item.org_id, str(_get(prior, "learning_id")), for_update=True)
        if old_state is LearningState.PUBLISHED:
            transition(conn, old_item, LearningState.SUPERSEDED, "newer_learning_published",
                       at=at, detail={"superseded_by": item.learning_id})
    entry_id = stable_id("brain", {"org_id": item.org_id, "brain": item.target.value,
                                   "subject_key": item.subject_key, "version": version})
    conn.execute(text(
        "insert into learned_brain_entries (org_id,entry_id,brain,subject_key,version,value,"
        "confidence_bp,learning_id,active,effective_at,visibility,trace_id,supersedes_entry_id) "
        "values (:o,:id,:brain,:subject,:version,cast(:value as jsonb),:confidence,:learning,"
        "true,:at,cast(:visibility as jsonb),:trace,:supersedes)"),
        {"o": item.org_id, "id": entry_id, "brain": item.target.value,
         "subject": item.subject_key, "version": version,
         "value": canonical_dumps(dict(item.value)), "confidence": item.evidence.confidence_bp,
         "learning": item.learning_id, "at": at,
         "visibility": canonical_dumps(dict(item.visibility)), "trace": item.trace_id,
         # Version allocation follows latest history; restoration follows the value this
         # publication actually displaced. Those rows differ after an earlier rollback.
         "supersedes": _get(prior, "entry_id") if prior is not None else None})
    conn.execute(text(
        "update learning_objects set supersedes_learning_id=:prior where org_id=:o "
        "and learning_id=:id"),
        {"prior": _get(prior, "learning_id") if prior is not None else None,
         "o": item.org_id, "id": item.learning_id})
    return True


def publish_result(conn, item: LearningObject, at: datetime) -> ValidationResult:
    """Publish once and return the exact sink-level state/reason for the audit ledger."""
    if item.target in BRAIN_TARGETS - {LearningTarget.RUNTIME}:
        if not _publish_brain(conn, item, at):
            transition(conn, item, LearningState.REJECTED, "no_material_change", at=at)
            return ValidationResult(LearningState.REJECTED, "no_material_change")
    elif item.target is LearningTarget.RUNTIME:
        conn.execute(text(
            "insert into temporary_memories (org_id,memory_id,subject_key,value,learning_id,"
            "confidence_bp,observed_at,expires_at,visibility,trace_id) values "
            "(:o,:id,:subject,cast(:value as jsonb),:learning,:confidence,:observed,:expires,"
            "cast(:visibility as jsonb),:trace) "
            "on conflict (org_id,learning_id) do nothing"),
            {"o": item.org_id, "id": stable_id("memory", item.learning_id),
             "subject": item.subject_key, "value": canonical_dumps(dict(item.value)),
             "learning": item.learning_id, "confidence": item.evidence.confidence_bp,
             "observed": item.observed_at, "expires": item.expires_at,
             "visibility": canonical_dumps(dict(item.visibility)), "trace": item.trace_id})
        return ValidationResult(LearningState.TEMPORARY, "temporary_memory_published")
    elif item.target is LearningTarget.METRICS:
        start = item.observed_at - timedelta(days=SOURCE_WINDOW_DAYS)
        inserted = conn.execute(text(
            "insert into learning_metrics (org_id,metric_id,metric_key,period_start,period_end,"
            "value,learning_id,visibility,trace_id) values "
            "(:o,:id,:key,:start,:end,cast(:value as jsonb),:learning,"
            "cast(:visibility as jsonb),:trace) "
            "on conflict (org_id,metric_key,period_start,period_end) do nothing "
            "returning metric_id"),
            {"o": item.org_id, "id": stable_id("lmetric", item.learning_id),
             "key": item.subject_key, "start": start, "end": item.observed_at,
             "value": canonical_dumps(dict(item.value)), "learning": item.learning_id,
             "visibility": canonical_dumps(dict(item.visibility)), "trace": item.trace_id}).first()
        if inserted is None:
            transition(conn, item, LearningState.REJECTED, "metric_identity_conflict", at=at)
            return ValidationResult(LearningState.REJECTED, "metric_identity_conflict")
    elif item.target is LearningTarget.KNOWLEDGE_SUGGESTION:
        raise ValueError("knowledge suggestions must enter human review, never publish")
    transition(conn, item, LearningState.PUBLISHED, "published_to_dynamic_target", at=at)
    conn.execute(text(
        "update learning_objects set published_at=:at where org_id=:o and learning_id=:id"),
        {"at": at, "o": item.org_id, "id": item.learning_id})
    return ValidationResult(LearningState.PUBLISHED, "published_to_dynamic_target")


def publish(conn, item: LearningObject, at: datetime) -> LearningState:
    """Evolution Publisher. The closed target enum makes an Expert write impossible."""
    return publish_result(conn, item, at).state


def enqueue_review(conn, item: LearningObject) -> None:
    if item.target is not LearningTarget.KNOWLEDGE_SUGGESTION:
        return
    conn.execute(text(
        "insert into knowledge_suggestions (org_id,suggestion_id,learning_id,subject_key,"
        "suggestion,evidence,visibility,trace_id) values "
        "(:o,:id,:learning,:subject,cast(:suggestion as jsonb),cast(:evidence as jsonb),"
        "cast(:visibility as jsonb),:trace) "
        "on conflict (org_id,learning_id) do nothing"),
        {"o": item.org_id, "id": stable_id("ksug", item.learning_id),
         "learning": item.learning_id, "subject": item.subject_key,
         "suggestion": canonical_dumps(dict(item.value)),
         "evidence": canonical_dumps(item.evidence.to_semantic_dict()),
         "visibility": canonical_dumps(dict(item.visibility)), "trace": item.trace_id})


def apply_path_result(conn, item: LearningObject, path: tuple[ValidationResult, ...],
                      at: datetime, *, actor: str = "system",
                      initial_state: LearningState = LearningState.OBSERVED,
                      audit_detail: dict[str, Any] | None = None) -> ValidationResult:
    state = initial_state
    reason_code = "state_held_by_current_policy"
    for decision in path:
        reason_code = decision.reason_code
        if decision.state is state:
            continue
        # Tightening repetition policy never regresses an already-candidate object to Observed.
        # The evaluation ledger still records the held result and exact policy revision.
        if state is LearningState.CANDIDATE and decision.state is LearningState.OBSERVED:
            continue
        transition(conn, item, decision.state, decision.reason_code, actor=actor, at=at,
                   detail=audit_detail)
        state = decision.state
    if state is LearningState.HUMAN_REVIEW:
        enqueue_review(conn, item)
    elif state is LearningState.PROMOTED:
        return publish_result(conn, item, at)
    elif state is LearningState.TEMPORARY:
        return publish_result(conn, item, at)
    return ValidationResult(state, reason_code)


def apply_path(conn, item: LearningObject, path: tuple[ValidationResult, ...],
               at: datetime, *, actor: str = "system",
               initial_state: LearningState = LearningState.OBSERVED,
               audit_detail: dict[str, Any] | None = None) -> LearningState:
    return apply_path_result(
        conn, item, path, at, actor=actor, initial_state=initial_state,
        audit_detail=audit_detail).state


def expire_memories(conn, org_id: str, at: datetime) -> int:
    # This function is also a public maintenance entrypoint, so it cannot assume the caller has
    # established the erasure-safe tenant-root lock order. Re-taking FOR SHARE is transaction-local
    # and harmless when ``run_learning`` already acquired it.
    lock_learning_tenant(conn, org_id)
    rows = conn.execute(text(
        "select m.learning_id from temporary_memories m join learning_objects o "
        "on o.org_id=m.org_id and o.learning_id=m.learning_id "
        "where m.org_id=:o and m.expired_at is null and m.expires_at<=:at "
        "for update of m,o"), {"o": org_id, "at": at}).all()
    for row in rows:
        item, state = load_learning_object(
            conn, org_id, str(_get(row, "learning_id", row[0])), for_update=True)
        if state is not LearningState.TEMPORARY:
            raise RuntimeError("active temporary memory has inconsistent lifecycle state")
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


def record_failed_run(conn, org_id: str, evaluated_at: datetime, policy_revision: int,
                      error_class: str) -> str:
    period = (evaluated_at - timedelta(days=evaluated_at.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0, tzinfo=timezone.utc)
    run_id = stable_id("learnrun", {"org_id": org_id, "period_start": period})
    conn.execute(text(
        "insert into learning_runs (run_id,org_id,period_start,evaluation_time,status,"
        "policy_revision,attempt_count,last_error) values "
        "(:id,:o,:period,:at,'failed',:revision,1,:error) "
        "on conflict (org_id,period_start) do update set status='failed',"
        "evaluation_time=excluded.evaluation_time,policy_revision=excluded.policy_revision,"
        "attempt_count=learning_runs.attempt_count+1,last_error=excluded.last_error "
        "where learning_runs.status<>'completed'"),
        {"id": run_id, "o": org_id, "period": period, "at": evaluated_at,
         "revision": policy_revision, "error": error_class[:192]})
    return run_id


__all__ = ["SOURCE_WINDOW_DAYS", "apply_path", "apply_path_result", "claim_run", "complete_run",
           "enqueue_review", "ensure_policy", "expire_memories", "load_batch",
           "load_learning_object", "load_policy", "lock_learning_tenant",
           "persist_input_rejections",
           "persist_object", "persist_preflight_rejection", "publish", "publish_result",
           "record_evaluation", "record_failed_run", "transition"]
