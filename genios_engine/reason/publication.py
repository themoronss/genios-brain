"""Layer 4 → Layer 5 · the native publication seam.

A `ReasoningExecution` is a decision.  A `signals` row is a *claim on someone's attention*.  This
module is the only place that turns the first into the second for natively-reasoned capabilities,
and it exists because those are genuinely different things: the decision is already immutable and
already audited, while the signal has to survive a SQL predicate that re-proves the decision on
every downstream read (`reason.authority`).

Until this module existed the native path stopped one step short.  It reasoned, it persisted a
complete audit bundle, and then it wrote a `native_shadow` suppression row and threw the conclusion
away.  Everything downstream — cards, briefs, delivery, learning — reads `signals`, so a capability
that never emitted one could not reach a human no matter how good its reasoning was.

Two rules shape everything below.

**Projection, not decision.**  Nothing here may change what was decided.  Every field written to the
row is either copied from the frozen execution or derived from it by a total function, so
publishing twice from the same execution produces byte-identical bindings.  The moment this module
gets to pick a play or move a score, Part 3 has stopped being the only decision authority.

**The row must satisfy the authority predicate, or it is worse than nothing.**  A signal that fails
`AUTHORITATIVE_SIGNAL_PREDICATE` is invisible: every read joins through it, so a mis-bound row
produces silence rather than an error.  The bindings below are therefore written against that
predicate field by field, and `tests/test_native_publication.py` asserts the correspondence rather
than trusting this comment.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.reasoning import DecisionOutcome
from genios_engine.platform.ids import new_id

from .authority import projected_score

#: Signals carry a `level` describing how far the claim goes.  A native capability always resolves
#: to a play with steps a human can execute, which is the definition of prescriptive.  It is a
#: constant rather than capability metadata because a capability that produced anything less would
#: not have reached a `DECISION` outcome in the first place.
NATIVE_SIGNAL_LEVEL = "prescriptive"

#: Capability metadata naming how long one subject must rest between native publications.  Distinct
#: from `expiry_hours`, which bounds how long a decision stays *true*: a decision can remain true
#: long after it stops being worth repeating.  Absent, the capability's own expiry is used, so the
#: default behaviour is "do not say it again until the last one stopped being true".
COOLDOWN_HOURS_KEY = "publication_cooldown_hours"


def native_rule_id(capability_id: str) -> str:
    """The `rule_id` a natively-reasoned capability publishes under.

    This is the Python twin of the SQL in `reason.authority`::

        regexp_replace(rr.capability_id, '^.*\\.', '')

    `.*` is greedy, so the match runs to the **last** dot: `sales.deal_cooling_full` becomes
    `deal_cooling_full`.  The predicate compares `s.rule_id` against that expression, so any
    disagreement between this function and that regex makes every native signal unreadable — which
    is why the two are pinned to each other by test rather than by convention.
    """
    text_value = str(capability_id).strip()
    if not text_value:
        raise ValueError("capability_id is required")
    return text_value.rsplit(".", 1)[-1]


@dataclass(frozen=True, slots=True)
class NativePublication:
    """One decision, projected into the exact shape a `signals` row needs.

    Built without touching the database so it can be asserted against the authority predicate in a
    unit test, and so the decision to publish is separable from the act of publishing.
    """

    rule_id: str
    rule_version: int
    level: str
    subject_node_id: str
    score: int
    score_inputs: Mapping[str, Any]
    reason_code: str
    evidence: tuple[Mapping[str, Any], ...]
    play: str
    reasoning_run_id: str
    reasoning_candidate_id: str
    reasoning_decision_hash: str
    authority_expires_at: datetime
    cooldown_hours: int


def _rule_version(capability_version: str) -> int:
    """Project a semantic capability version onto the integer column `signals.rule_version`.

    The major component is the only part that can change what a decision *means*, and it is the
    only part that fits.  Unparseable versions fall back to 1 rather than raising: this field is
    descriptive — the authority predicate never reads it — so a strange version string must not be
    able to stop a sound decision from reaching a human.
    """
    head = str(capability_version).strip().split(".", 1)[0]
    try:
        value = int(head)
    except ValueError:
        return 1
    return value if value > 0 else 1


def _cooldown_hours(capability: Any) -> int:
    value = capability.metadata.get(COOLDOWN_HOURS_KEY)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return int(capability.expiry_hours)
    return value


def _score_inputs(candidate: Any, confidence_bp: int) -> dict[str, int]:
    """The score, decomposed, on the 0–100 scale the signal column has always used.

    Diagnostic only: every consumer recomputes this from the audit rows through
    `AUTHORITATIVE_SCORE_INPUTS_SQL`, because a value copied into a mutable table is a claim and a
    value re-derived from immutable rows is a proof.  It is still written, because when the two
    disagree the stored copy is what tells you *when* they diverged.
    """
    components = dict(candidate.score_components)
    return {
        "U": projected_score(components.get("urgency", 0)),
        "I": projected_score(components.get("impact", 0)),
        "S": projected_score(components.get("success", 0)),
        "E": projected_score(components.get("effort", 0)),
        "K": projected_score(components.get("risk", 0)),
        "C": projected_score(confidence_bp),
    }


def _evidence(execution: Any, candidate: Any) -> tuple[Mapping[str, Any], ...]:
    """The receipts the decision actually stood on, in the shape cards already render.

    Deliberately driven by `candidate.evidence_ids` rather than by a capability-declared field
    list.  A declared list says what the capability *hoped* to cite; the candidate's ids say what
    the units in this particular run actually did cite.  When a fact was missing, the difference is
    the whole story, and a card that shows the second one cannot quietly overstate its basis.
    """
    cited = set(candidate.evidence_ids)
    return tuple(
        {"field": item.field, "value": item.value}
        for item in sorted(execution.request.context.evidence,
                           key=lambda ref: (ref.field, ref.evidence_id))
        if item.evidence_id in cited
    )


def build_native_publication(*, execution: Any,
                             audit_bundle: Mapping[str, Any]) -> NativePublication | None:
    """Project an authorized execution into a publishable row, or refuse.

    Returns `None` — never raises — for every run that must not reach a human: a shadow run, a
    capability whose delivery flag is still closed, an outcome that is not a decision, a decision
    whose winner is not read-only.  Refusal is the common case during rollout and it is not an
    error, so it is expressed as an absent value rather than as an exception the caller must
    remember to catch.

    `execution.authorizes_delivery` already encodes all four of those conditions; they are not
    re-checked here.  Duplicating the boundary would create a second place where "may this reach a
    human" is answered, and the second place is always the one that drifts.
    """
    if not execution.authorizes_delivery:
        return None
    selected = execution.selected_candidate
    if selected is None or execution.decision.outcome != DecisionOutcome.DECISION:
        return None
    output = audit_bundle.get("output") or {}
    run = audit_bundle.get("run") or {}
    run_id = run.get("run_id")
    candidate_id = output.get("selected_candidate_id")
    decision_hash = output.get("decision_hash")
    if not run_id or not candidate_id or not decision_hash:
        # The bundle is the persisted proof.  Publishing a row that points at an audit trail which
        # does not exist would create exactly the dangling authority the predicate exists to catch.
        return None
    capability = execution.request.capability
    rule_id = native_rule_id(capability.capability_id)
    return NativePublication(
        rule_id=rule_id,
        rule_version=_rule_version(capability.version),
        level=NATIVE_SIGNAL_LEVEL,
        subject_node_id=execution.request.context.root_entity_id,
        # `s.score = ((selected_rc.final_utility_bp + 50) / 100)` in the predicate.  One projection
        # law, expressed once in Python and once in SQL, and asserted equal by test.
        score=projected_score(selected.utility_bp),
        score_inputs=_score_inputs(selected, execution.decision.confidence_bp),
        # Both `s.rule_id` and `s.reason_code` are compared against the same capability-id regex
        # for a non-legacy run.  They are therefore the same string, and that is not a mistake:
        # for native capabilities the capability *is* the reason.
        reason_code=rule_id,
        evidence=_evidence(execution, selected),
        play=selected.play_id,
        reasoning_run_id=str(run_id),
        reasoning_candidate_id=str(candidate_id),
        reasoning_decision_hash=str(decision_hash),
        # The predicate requires this to equal the decision's own expiry to the microsecond.
        authority_expires_at=execution.decision.expires_at,
        cooldown_hours=_cooldown_hours(capability),
    )


def publish_native_signal(store, *, org_id: str, publication: NativePublication,
                          eval_time: datetime, config_snapshot_id: str,
                          pack_id: str, pack_version: str,
                          authority_pack_revision: int) -> str | None:
    """Retire this subject's previous claim and publish the new one, atomically.

    `ON CONFLICT DO NOTHING` against the partial-unique index (one open signal per
    org/pack/rule/subject) makes a concurrent sweep that already published a no-op rather than a
    duplicate; the caller distinguishes the two by the returned id.  Cards belonging to a retired
    signal expire with it, because a card outliving its evidence is the precise failure Rule 08 —
    *stale beats wrong* — exists to prevent.

    `authority_binding_version=1` is written literally.  It is the predicate's declaration that this
    row was bound by a writer that knew the current authority contract; a future contract change
    gets a new number, and rows written under the old one stop being authoritative on their own.
    """
    signal_id = new_id("sig")
    with store.engine.begin() as conn:
        retired = conn.execute(text(
            "update signals set status='expired' where org_id=:o and rule_id=:r "
            "and pack_id=:p and pack_version=:pv "
            "and subject_node_id=:n and status='open' returning signal_id"),
            {"o": org_id, "r": publication.rule_id, "n": publication.subject_node_id,
             "p": pack_id, "pv": pack_version}).fetchall()
        if retired:
            conn.execute(text(
                "update cards set state='expired' where org_id=:o and signal_id=any(:ids) "
                "and state in ('queued','surfaced','snoozed','claimed','delivered')"),
                {"o": org_id, "ids": [item.signal_id for item in retired]})
        row = conn.execute(text(
            "insert into signals (signal_id, org_id, pack_id, pack_version, rule_id, "
            "rule_version, level, "
            "subject_node_id, score, score_inputs, reason_code, evidence, play, eval_time, "
            "config_snapshot_id, reasoning_run_id, reasoning_candidate_id, "
            "reasoning_decision_hash, authority_expires_at, authority_pack_revision, "
            "authority_binding_version) "
            "values (:id,:o,:pack,:packv,:r,:v,:lv,:n,:s,cast(:si as jsonb),:rc,"
            "cast(:ev as jsonb),:play,:et,"
            ":cs,:rr,:candidate,:decision_hash,:expires,:pack_revision,1) "
            "on conflict (org_id,pack_id,pack_version,rule_id,subject_node_id) "
            "where status='open' do nothing "
            "returning signal_id"),
            {"id": signal_id, "o": org_id, "pack": pack_id, "packv": pack_version,
             "r": publication.rule_id, "v": publication.rule_version,
             "lv": publication.level, "n": publication.subject_node_id,
             "s": publication.score,
             "si": json.dumps(dict(publication.score_inputs), default=str),
             "rc": publication.reason_code,
             "ev": json.dumps([dict(item) for item in publication.evidence], default=str),
             "play": publication.play, "et": eval_time, "cs": config_snapshot_id,
             "rr": publication.reasoning_run_id,
             "candidate": publication.reasoning_candidate_id,
             "decision_hash": publication.reasoning_decision_hash,
             "expires": publication.authority_expires_at,
             "pack_revision": authority_pack_revision}).first()
    return row.signal_id if row else None


def native_rule_ids(capabilities: Sequence[Any]) -> set[str]:
    """Rule ids the native path owns, for signal lifecycle.

    Lifecycle retires an open signal when its owner ran and did not re-fire.  A capability that
    published yesterday and reached `NO_ACTION` today must retire the old claim — otherwise the
    first native signal a subject ever received would stay open forever, since the legacy sweep
    only knows about pack rule ids and would never claim it.
    """
    return {native_rule_id(capability.capability_id) for capability in capabilities}


__all__ = ["COOLDOWN_HOURS_KEY", "NATIVE_SIGNAL_LEVEL", "NativePublication",
           "build_native_publication", "native_rule_id", "native_rule_ids",
           "publish_native_signal"]
