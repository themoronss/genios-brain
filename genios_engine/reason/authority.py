"""Shared SQL authority boundary for projections of Layer 4 decisions.

Signals are convenient read models, not decision authority by themselves.  Every
consumer that can surface or compose a recommendation must prove that the signal
still points at the exact live, unexpired winner from a completed reasoning run.
Keeping that proof in one fragment prevents query, composition, and delivery from
quietly drifting apart.
"""

from __future__ import annotations

from datetime import datetime, timezone


AUTHORITATIVE_SIGNAL_JOINS = (
    " join reasoning_runs rr on rr.org_id=s.org_id "
    "and rr.run_id=s.reasoning_run_id and rr.config_snapshot_id=s.config_snapshot_id "
    "join reasoning_run_outputs ro on ro.org_id=rr.org_id and ro.run_id=rr.run_id "
    "join reasoning_candidates selected_rc on selected_rc.org_id=ro.org_id "
    "and selected_rc.run_id=ro.run_id "
    "and selected_rc.candidate_id=ro.selected_candidate_id "
    "and selected_rc.candidate_id=s.reasoning_candidate_id "
    "join reasoning_capability_snapshots rcap on rcap.org_id=rr.org_id "
    "and rcap.capability_snapshot_id=rr.capability_snapshot_id "
    "join lateral (select declared_play from jsonb_array_elements(rcap.manifest->'plays') "
    "declared_play where declared_play->>'play_id'=selected_rc.play_id "
    "and declared_play->>'version'=selected_rc.play_version limit 1) authority_play on true "
    "join reasoning_reasoner_results authority_constraint on "
    "authority_constraint.org_id=rr.org_id and authority_constraint.run_id=rr.run_id "
    "and authority_constraint.reasoner_id='core.constraint' "
    "and authority_constraint.status='completed' "
    "join reasoning_context_snapshots authority_ctx on authority_ctx.org_id=rr.org_id "
    "and authority_ctx.context_snapshot_id=rr.context_snapshot_id "
    "join config_snapshots authority_cfg on authority_cfg.org_id=s.org_id "
    "and authority_cfg.snapshot_id=s.config_snapshot_id "
    "join tenant_packs authority_pack on authority_pack.org_id=s.org_id "
    "and authority_pack.pack_id=authority_cfg.pack_id "
    "join lateral (select ar.output from reasoning_reasoner_results ar "
    "where ar.org_id=rr.org_id and ar.run_id=rr.run_id and ar.status='completed' "
    "order by case when ar.reasoner_id in ('legacy.rule','core.signal_composition') "
    "then 0 else 1 end, ar.ordinal asc limit 1) authority_source on true "
)


AUTHORITATIVE_REASON_CODE_SQL = (
    "case when rr.capability_id like 'legacy.%' "
    "then coalesce(authority_source.output->'reason_codes'->>0, "
    "regexp_replace(rr.capability_id, '^.*\\.', '')) "
    "else regexp_replace(rr.capability_id, '^.*\\.', '') end"
)


# Signals/cards retain the historical integer 0..100 score shape while native candidates use
# basis points. Non-negative half-up rounding is the single projection law in Python and SQL.
AUTHORITATIVE_SCORE_SQL = "((selected_rc.final_utility_bp + 50) / 100)"


def _published_metric(name: str) -> str:
    """The value of `name` as published by whichever completed reasoner in this run owns it.

    Safe because publication is exclusive: `tests/test_unit_roster.py` proves no two units declare
    the same metric, so at most one row can match and the `limit 1` is a formality rather than a
    tie-break. `is not null` is used in place of the jsonb `?` operator on purpose — `?` collides
    with parameter markers in some drivers, and a query that only breaks on the production driver
    is the worst kind.
    """
    return ("(select (published_metric.output->'metrics'->>'" + name + "')::int "
            "from reasoning_reasoner_results published_metric "
            "where published_metric.org_id=rr.org_id and published_metric.run_id=rr.run_id "
            "and published_metric.status='completed' "
            "and (published_metric.output->'metrics'->>'" + name + "') is not null "
            "order by published_metric.ordinal limit 1)")


# Legacy runs answer from `authority_source` — the `legacy.rule` / `core.signal_composition` row
# that carries U, I and R together — and that term stays first in every chain below, so a legacy
# card's breakdown is byte-identical to what it was before natives existed.
#
# A native run has no such row: urgency belongs to `core.priority`, impact to `core.impact`,
# freshness to `core.context`, and no unit aggregates them. Without the middle terms every native
# card would render U = I = the final score and R = 50 — not wrong enough to fail the authority
# predicate, which never reads this, but wrong enough to make a human distrust a correct decision.
# `freshness_bp` backs `recency_bp` because it is the same question asked in native vocabulary:
# how stale is the evidence under this claim.
AUTHORITATIVE_SCORE_INPUTS_SQL = (
    "jsonb_build_object("
    "'U', (coalesce((authority_source.output->'metrics'->>'urgency_bp')::int, "
    + _published_metric("urgency_bp") + ", "
    "selected_rc.final_utility_bp) + 50) / 100, "
    "'I', (coalesce((authority_source.output->'metrics'->>'impact_bp')::int, "
    + _published_metric("impact_bp") + ", "
    "selected_rc.final_utility_bp) + 50) / 100, "
    "'R', (coalesce((authority_source.output->'metrics'->>'recency_bp')::int, "
    + _published_metric("recency_bp") + ", " + _published_metric("freshness_bp") + ", "
    "5000) + 50) / 100, "
    "'C', (selected_rc.confidence_bp + 50) / 100)"
)


AUDITED_SIGNAL_PREDICATE = (
    "s.reasoning_run_id is not null "
    "and s.authority_binding_version=1 "
    "and rr.status='completed' and rr.mode='live' "
    "and rr.root_node_id=s.subject_node_id "
    "and authority_ctx.capability_id=rr.capability_id "
    "and authority_ctx.capability_version=rr.capability_version "
    "and authority_ctx.capability_snapshot_id=rr.capability_snapshot_id "
    "and authority_ctx.evaluation_time=rr.evaluation_time "
    "and rcap.capability_id=rr.capability_id "
    "and rcap.capability_version=rr.capability_version "
    "and authority_constraint.reasoner_version=(select authority_constraint_spec->>'version' "
    "from jsonb_array_elements(coalesce(rcap.manifest->'reasoners','[]'::jsonb)) "
    "authority_constraint_spec where "
    "authority_constraint_spec->>'reasoner_id'='core.constraint' limit 1) "
    "and ro.outcome_kind='decision' "
    "and ro.decision_hash=s.reasoning_decision_hash "
    "and ro.ranked_candidate_ids->>0=ro.selected_candidate_id "
    "and selected_rc.disposition='eligible' and selected_rc.rank_position=1 "
    "and selected_rc.play_id=s.play "
    "and s.score=(" + AUTHORITATIVE_SCORE_SQL + ") "
    "and s.rule_id=regexp_replace(rr.capability_id, '^.*\\.', '') "
    "and s.reason_code=(" + AUTHORITATIVE_REASON_CODE_SQL + ") "
    "and not exists (select 1 from jsonb_array_elements(" 
    "coalesce(rcap.manifest->'reasoners','[]'::jsonb)) authority_required_spec "
    "where coalesce(authority_required_spec->>'failure_policy','required')='required' "
    "and not exists (select 1 from reasoning_reasoner_results authority_required_result "
    "where authority_required_result.org_id=rr.org_id "
    "and authority_required_result.run_id=rr.run_id "
    "and authority_required_result.reasoner_id=authority_required_spec->>'reasoner_id' "
    "and authority_required_result.reasoner_version=authority_required_spec->>'version' "
    "and authority_required_result.status='completed')) "
    "and not exists (select 1 from jsonb_array_elements(" 
    "coalesce(rcap.manifest->'reasoners','[]'::jsonb)) authority_gating_spec "
    "where coalesce((authority_gating_spec->>'gating')::boolean,false) "
    "and not exists (select 1 from reasoning_reasoner_results authority_gating_result "
    "where authority_gating_result.org_id=rr.org_id "
    "and authority_gating_result.run_id=rr.run_id "
    "and authority_gating_result.reasoner_id=authority_gating_spec->>'reasoner_id' "
    "and authority_gating_result.reasoner_version=authority_gating_spec->>'version' "
    "and authority_gating_result.status='completed' "
    "and authority_gating_result.output->'matched'='true'::jsonb)) "
    "and selected_rc.parameters->'read_only' = 'true'::jsonb "
    "and authority_play.declared_play->'read_only' = 'true'::jsonb "
    # Candidate-check rows must be an exact index of core.constraint's immutable output for the
    # selected play.  This prevents a forged pass row or a hidden elimination from becoming live
    # authority even if child tables are corrupted independently.
    "and not exists (select 1 from reasoning_candidate_checks authority_extra_check "
    "where authority_extra_check.org_id=rr.org_id "
    "and authority_extra_check.run_id=rr.run_id "
    "and authority_extra_check.candidate_id=selected_rc.candidate_id "
    "and authority_extra_check.evaluator_id='core.constraint' "
    "and not exists (select 1 from jsonb_array_elements(" 
    "coalesce(authority_constraint.output->'checks','[]'::jsonb)) authority_embedded_check "
    "where authority_embedded_check->>'play_id'=selected_rc.play_id "
    "and authority_embedded_check->>'stage'=authority_extra_check.stage "
    "and authority_embedded_check->>'outcome'=authority_extra_check.outcome "
    "and authority_embedded_check->>'reason_code'=authority_extra_check.reason_code "
    "and authority_embedded_check->>'evaluator_id'=authority_extra_check.evaluator_id "
    "and authority_embedded_check->>'evaluator_version'=authority_extra_check.evaluator_version "
    "and coalesce(authority_embedded_check->'detail','{}'::jsonb)=authority_extra_check.detail "
    "and (authority_embedded_check->>'score_before_bp')::int "
    "is not distinct from authority_extra_check.score_before_bp "
    "and (authority_embedded_check->>'score_after_bp')::int "
    "is not distinct from authority_extra_check.score_after_bp)) "
    "and not exists (select 1 from jsonb_array_elements(" 
    "coalesce(authority_constraint.output->'checks','[]'::jsonb)) authority_missing_check "
    "where authority_missing_check->>'play_id'=selected_rc.play_id "
    "and authority_missing_check->>'evaluator_id'='core.constraint' "
    "and not exists (select 1 from reasoning_candidate_checks authority_indexed_check "
    "where authority_indexed_check.org_id=rr.org_id "
    "and authority_indexed_check.run_id=rr.run_id "
    "and authority_indexed_check.candidate_id=selected_rc.candidate_id "
    "and authority_indexed_check.stage=authority_missing_check->>'stage' "
    "and authority_indexed_check.outcome=authority_missing_check->>'outcome' "
    "and authority_indexed_check.reason_code=authority_missing_check->>'reason_code' "
    "and authority_indexed_check.evaluator_id=authority_missing_check->>'evaluator_id' "
    "and authority_indexed_check.evaluator_version="
    "authority_missing_check->>'evaluator_version' "
    "and authority_indexed_check.detail="
    "coalesce(authority_missing_check->'detail','{}'::jsonb) "
    "and authority_indexed_check.score_before_bp is not distinct from "
    "(authority_missing_check->>'score_before_bp')::int "
    "and authority_indexed_check.score_after_bp is not distinct from "
    "(authority_missing_check->>'score_after_bp')::int)) "
    # Every declared policy has one distinct semantic pass. Counting arbitrary pass rows is not a
    # policy proof: the stage/reason/version and embedded constraint bytes must all agree.
    "and not exists (select 1 from jsonb_array_elements_text(" 
    "coalesce(rcap.manifest->'policies','[]'::jsonb)) authority_policy(policy_id) "
    "where not exists (select 1 from reasoning_candidate_checks authority_policy_check "
    "where authority_policy_check.org_id=rr.org_id "
    "and authority_policy_check.run_id=rr.run_id "
    "and authority_policy_check.candidate_id=selected_rc.candidate_id "
    "and authority_policy_check.evaluator_id='core.constraint' "
    "and authority_policy_check.evaluator_version=authority_constraint.reasoner_version "
    "and authority_policy_check.outcome='pass' "
    "and authority_policy_check.stage=case authority_policy.policy_id "
    "when 'read_only' then 'policy' when 'human_approval_required' then 'permission' "
    "when 'evidence_required' then 'policy' when 'no_unverified_recipient' then 'permission' end "
    "and authority_policy_check.reason_code=case authority_policy.policy_id "
    "when 'read_only' then 'read_only_policy_pass' "
    "when 'human_approval_required' then 'human_approval_boundary_pass' "
    "when 'evidence_required' then 'evidence_policy_pass' "
    "when 'no_unverified_recipient' then 'verified_recipient_guard_pass' end "
    "and exists (select 1 from jsonb_array_elements(" 
    "coalesce(authority_constraint.output->'checks','[]'::jsonb)) authority_policy_effect "
    "where authority_policy_effect->>'play_id'=selected_rc.play_id "
    "and authority_policy_effect->>'stage'=authority_policy_check.stage "
    "and authority_policy_effect->>'outcome'=authority_policy_check.outcome "
    "and authority_policy_effect->>'reason_code'=authority_policy_check.reason_code "
    "and authority_policy_effect->>'evaluator_id'=authority_policy_check.evaluator_id "
    "and authority_policy_effect->>'evaluator_version'="
    "authority_policy_check.evaluator_version))) "
    "and rcap.manifest->'live_delivery_enabled' = 'true'::jsonb "
    "and s.authority_pack_revision > 0 "
    "and s.pack_id=authority_cfg.pack_id "
    "and s.pack_version=authority_cfg.effective->>'version' "
    "and authority_cfg.effective->>'pack_id'=authority_cfg.pack_id "
    "and authority_cfg.effective->>'state'='active' "
    "and ((rr.capability_id like 'legacy.%' and "
    "rcap.manifest->'metadata'->>'pack_id'=authority_cfg.pack_id and "
    "rcap.manifest->'metadata'->>'pack_version'=authority_cfg.effective->>'version' and "
    "rcap.manifest->'metadata'->>'config_snapshot_id'=rr.config_snapshot_id) or "
    "(rr.capability_id not like 'legacy.%' and "
    "rcap.manifest->>'domain'=authority_cfg.pack_id)) "
    "and s.authority_expires_at is not null "
    "and ro.decision_core->'expires_at'->>'$datetime' is not null "
    "and s.authority_expires_at = "
    "(ro.decision_core->'expires_at'->>'$datetime')::timestamptz"
)


AUTHORITATIVE_SIGNAL_PREDICATE = (
    AUDITED_SIGNAL_PREDICATE + " "
    "and authority_pack.state='active' "
    "and s.authority_pack_revision=authority_pack.authority_revision "
    "and authority_cfg.effective->>'version'=authority_pack.version "
    "and rr.completed_at >= authority_pack.updated_at "
    "and authority_ctx.graph_version = (select coalesce(max(gv.graph_version),0) "
    "from graph_versions gv where gv.org_id=s.org_id) "
    "and s.authority_expires_at > :authority_time"
)


# Historical learning has one canonical human judgment per audited card. Retries, corrections,
# unrelated event kinds, and multiple feedback verbs must never turn one recommendation into
# several wins/losses. Callers prepend ``WITH`` and provide ``:o`` plus ``:as_of``.
AUDITED_CARD_JUDGMENTS_CTES = (
    "audited_cards as ("
    "select k.card_id, k.created_at as card_created_at, s.authority_expires_at, "
    "authority_cfg.pack_id, authority_cfg.effective->>'version' as pack_version, "
    "s.authority_pack_revision, "
    "rr.capability_id, rr.capability_version, "
    "regexp_replace(rr.capability_id, '^.*\\.', '') as rule_id, "
    "selected_rc.play_id as play "
    "from cards k join signals s on s.org_id=k.org_id and s.signal_id=k.signal_id "
    + AUTHORITATIVE_SIGNAL_JOINS +
    "where k.org_id=:o and " + AUDITED_SIGNAL_PREDICATE +
    "), audited_impressions as ("
    "select ac.pack_id, ac.pack_version, ac.authority_pack_revision, "
    "ac.capability_id, ac.capability_version, "
    "ac.rule_id, ac.card_id, max(ce.occurred_at) as occurred_at "
    "from audited_cards ac "
    "join card_events ce on ce.org_id=:o and ce.card_id=ac.card_id "
    "where ce.kind='card.surfaced' and ce.occurred_at >= ac.card_created_at "
    "and ce.occurred_at <= :as_of and ce.occurred_at < ac.authority_expires_at "
    "group by ac.pack_id, ac.pack_version, ac.authority_pack_revision, "
    "ac.capability_id, ac.capability_version, "
    "ac.rule_id, ac.card_id"
    "), judgment_events as ("
    "select ac.pack_id, ac.pack_version, ac.authority_pack_revision, "
    "ac.capability_id, ac.capability_version, "
    "ac.rule_id, ac.play, ac.card_id, ce.cause, ce.detail, ce.occurred_at, ce.id "
    "from audited_cards ac join card_events ce "
    "on ce.org_id=:o and ce.card_id=ac.card_id "
    "where ce.kind='human.card_action' "
    "and ce.cause in ('run_play','do_it_myself','wrong') "
    "and ce.occurred_at >= ac.card_created_at and ce.occurred_at <= :as_of "
    "and ce.occurred_at < ac.authority_expires_at "
    "union all "
    "select ac.pack_id, ac.pack_version, ac.authority_pack_revision, "
    "ac.capability_id, ac.capability_version, "
    "ac.rule_id, ac.play, ac.card_id, fv.cause, "
    "case when fv.reason is null then fv.detail else "
    "fv.detail || jsonb_build_object('reason',fv.reason) end as detail, "
    "fv.occurred_at, fv.feedback_id as id "
    "from audited_cards ac join card_feedback_verdicts fv "
    "on fv.org_id=:o and fv.card_id=ac.card_id "
    "and fv.pack_id=ac.pack_id and fv.pack_version=ac.pack_version "
    "and fv.authority_pack_revision=ac.authority_pack_revision "
    "and fv.capability_id=ac.capability_id "
    "and fv.capability_version=ac.capability_version "
    "and fv.rule_id=ac.rule_id "
    "where fv.occurred_at >= ac.card_created_at and fv.occurred_at <= :as_of "
    "and fv.occurred_at < ac.authority_expires_at"
    "), ranked_judgments as ("
    "select je.*, row_number() over (partition by je.card_id "
    "order by je.occurred_at desc, je.id desc) as judgment_position "
    "from judgment_events je"
    "), canonical_judgments as ("
    "select pack_id, pack_version, authority_pack_revision, "
    "capability_id, capability_version, "
    "rule_id, play, card_id, cause, detail, occurred_at, id "
    "from ranked_judgments where judgment_position=1"
    ")"
)


def authority_time(value: datetime | None = None) -> datetime:
    """Normalize the caller's decision time for deterministic expiry checks."""
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("authority_time must be timezone-aware")
    return result.astimezone(timezone.utc)


def projected_score(utility_bp: int) -> int:
    """Project a bounded basis-point utility into the legacy integer score column."""
    if isinstance(utility_bp, bool) or not isinstance(utility_bp, int):
        raise TypeError("utility_bp must be an integer")
    if not 0 <= utility_bp <= 10_000:
        raise ValueError("utility_bp must be between 0 and 10000")
    return (utility_bp + 50) // 100


__all__ = [
    "AUTHORITATIVE_SIGNAL_JOINS",
    "AUTHORITATIVE_SIGNAL_PREDICATE",
    "AUDITED_SIGNAL_PREDICATE",
    "AUTHORITATIVE_REASON_CODE_SQL",
    "AUTHORITATIVE_SCORE_SQL",
    "AUTHORITATIVE_SCORE_INPUTS_SQL",
    "AUDITED_CARD_JUDGMENTS_CTES",
    "authority_time",
    "projected_score",
]
