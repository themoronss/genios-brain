"""The Layer 6 driver for N-3 — load the canon document, admit the proposal, serve the rule.

`packs/brains/org_discovery.py` holds the JUDGMENT (CLG-09) and is Layer 3, so the import ratchet
forbids it from calling the governance that judges it. This module is the other half: it sits on
the Layer 6 side, loads the document, calls the model site, hands the gated rules to the EXISTING
promotion pipeline, and — after a human confirms one — projects it into the Authority view.

WHY THIS IS NOT `brain_pipeline.admit_proposals`, AND THE DIFFERENCE IS NOT COSMETIC
------------------------------------------------------------------------------------
`feedback/brain_pipeline.admit_proposals` is the EVIDENCE route: validate → preflight → govern →
persist(GOVERNED) → publish, with `units.validate_learning` as a hard gate. That is exactly right
for N-4 and for the weekly units, whose proposals are claims about *what recurred*: the floors
(`min_observations`, `min_distinct_days`, `min_distinct_entities`) ask "did we see it often
enough, on enough days, across enough entities to believe it is a pattern?" and a proposal that
cannot answer is a coincidence.

An N-3 discovery is not a claim about what recurred. It is a sentence the company WROTE DOWN and
uploaded as canon at authority rank 4. Asking "how many distinct days did this policy occur on?"
of a signed approvals policy is a category error — the answer is one, for every real policy that
has ever existed, so routing declarations through the recurrence floors does not make the brain
careful, it makes the brain permanently empty. Its own validation is doc 02 step 3 and it is
strict: the span verifies against the document, the money re-derives from the quote through
ALG-10, the category is in a closed set, the approver resolves to a real node, and the statement
carries deontic force in the document's own words.

So `admit_discovery` below is the DECLARATION route, and it is stricter than the evidence route
in the way that matters — nothing it admits ever publishes on its own:

  * the floors are ALWAYS evaluated, and their verdict is written into the Validated→Governed
    transition's `detail` so a reviewer sees what the evidence would have carried alone;
  * whenever governance would NOT route to a human — i.e. whenever the proposal could reach a
    brain with nobody looking — a failed floor is a refusal and nothing is persisted;
  * under every default policy `govern()` sends an Organization proposal to HUMAN_REVIEW, so a
    discovered rule reaches `learned_brain_entries` only when a named owner approves it through
    `POST /v1/learning/objects/{id}/review`.

Nothing that previously required the floors stops requiring them, and no new governance exists:
`preflight`, `govern`, `validate_learning`, `persist` and `publish` are the same four functions
`orchestrator.run_learning` calls, in the same order.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text

from genios_engine.capture.internal_knowledge import normalize_kind
from genios_engine.contracts.authority import AuthorityRule, AuthoritySource
from genios_engine.contracts.learning import (
    LearningObject,
    LearningPolicy,
    LearningState,
    LearningTarget,
    learning_can_transition,
)
from genios_engine.feedback.governance import govern, preflight
from genios_engine.feedback.publisher import log_transition, persist, publish
from genios_engine.feedback.units import validate_learning
from genios_engine.packs.brains.org_discovery import (
    DISCOVERY_SEAM,
    DISCOVERY_SOURCE,
    DISCOVERY_UNIT,
    SUBJECT_PREFIX,
    CanonDocument,
    OrgRuleExtractor,
    authority_rule_id,
    build_proposal,
    gate_candidates,
    resolve_approver_node,
)
from genios_engine.platform.canonical import canonical_dumps
from genios_engine.platform.ids import new_id

#: The rungs a declaration climbs before governance's destination. Doc 02 is explicit that a
#: discovery ENTERS AT OBSERVED, and the reason is the one this codebase keeps rediscovering: a
#: proposal whose intermediate states were never recorded cannot be asked *where did it stop, and
#: on which gate?*. Every hop is checked against `ALLOWED_LEARNING_TRANSITIONS` before it is
#: written, so this walk cannot invent an edge the lifecycle does not have.
LADDER: tuple[LearningState, ...] = (
    LearningState.OBSERVED,      # the statement was read out of a document
    LearningState.CANDIDATE,     # CLG-09 admitted it
    LearningState.VALIDATED,     # the floors were evaluated and RECORDED
    LearningState.GOVERNED,      # governance chose a destination
)


@dataclass(frozen=True, slots=True)
class Admission:
    """What happened to one declaration at the Layer 6 door. A receipt, not a status guess."""

    learning_id: str
    admitted: bool
    state: LearningState | None
    reason: str
    floors_ok: bool
    floors_reason: str
    sink: str | None = None

    @property
    def awaiting_human(self) -> bool:
        return self.state is LearningState.HUMAN_REVIEW


def _set_state(conn, obj: LearningObject, state: LearningState) -> None:
    conn.execute(text("update learning_objects set state = :st "
                      "where org_id = :o and learning_id = :l"),
                 {"st": state.value, "o": obj.org_id, "l": obj.learning_id})


def admit_discovery(conn, obj: LearningObject, *, policy: LearningPolicy, now: datetime,
                    actor: str | None = None,
                    admission_detail: Mapping[str, Any] | None = None) -> Admission:
    """Hand one declaration to Layer 6. See the module docstring for why this is its own route."""
    floors_ok, floors_reason = validate_learning(obj, policy)

    gate = preflight(obj, policy, now=now)
    if not gate.ok:
        return Admission(obj.learning_id, False, None, gate.reason_code, floors_ok, floors_reason)

    decision = govern(obj, policy)
    if decision.rejected:
        return Admission(obj.learning_id, False, None, decision.reason_code, floors_ok,
                         floors_reason)

    # THE FLOORS BITE WHEREVER NO HUMAN WILL LOOK. `organization_requires_review` defaults true
    # and a tenant may only narrow policy — but the field is settable, and a tenant who turned
    # review off must not thereby have turned the recurrence floors off too.
    if not decision.needs_human and not floors_ok:
        return Admission(obj.learning_id, False, None, floors_reason, floors_ok, floors_reason)

    outcome = persist(conn, obj, state=LearningState.OBSERVED, at=now,
                      policy_revision=policy.revision)
    if outcome == "unchanged":
        # A later or terminal object with this identity already exists. Re-proposing identical
        # content is a no-op — that is what content addressing is for — and counting it as an
        # admission would double-count one rule on every re-read of the same document.
        return Admission(obj.learning_id, False, None, "unchanged", floors_ok, floors_reason)

    rungs: tuple[tuple[LearningState, str, dict], ...] = (
        (LearningState.CANDIDATE, DISCOVERY_SOURCE,
         {"source": DISCOVERY_SOURCE, **dict(admission_detail or {})}),
        (LearningState.VALIDATED, "floors_evaluated",
         {"floors_ok": floors_ok, "floors_reason": floors_reason, "policy_key": obj.policy_key}),
        (LearningState.GOVERNED, "governed", {"governance": decision.reason_code}),
        (decision.target_state, decision.reason_code, {"governance": decision.reason_code}),
    )
    state = LearningState.OBSERVED
    for rung, reason_code, detail in rungs:
        if not learning_can_transition(state, rung):
            raise ValueError(f"{state.value} -> {rung.value} is not an allowed L6 transition")
        log_transition(conn, org_id=obj.org_id, learning_id=obj.learning_id,
                       from_state=state.value, to_state=rung.value, reason_code=reason_code,
                       at=now, actor=actor, detail=detail)
        state = rung
    _set_state(conn, obj, state)

    # HUMAN_REVIEW is a resting place, not a sink: the object waits in the console for a named
    # human, and `publish()` would only log a second Governed→human_review transition and return
    # 'queued_for_review' without writing anything.
    sink: str | None = None
    if decision.target_state is not LearningState.HUMAN_REVIEW:
        sink = publish(conn, obj, target_state=decision.target_state, at=now)
        if obj.target is LearningTarget.ORGANIZATION and str(sink).startswith("published"):
            state = LearningState.PUBLISHED
            _set_state(conn, obj, state)
    return Admission(obj.learning_id, True, state, decision.reason_code, floors_ok, floors_reason,
                     sink)


def record_refusal(conn, *, org_id: str, source_ref: str, reason: str) -> None:
    """Name and count one refusal in `learning_input_rejections` (migration 0046).

    That ledger already carries the words "sanitized isolation of a malformed/lineage-less
    input", which is precisely what a refused candidate is. A refusal that lives only in a return
    value is indistinguishable from a candidate the model never produced.
    """
    conn.execute(text(
        "insert into learning_input_rejections (id, org_id, seam, source_ref, reason_code, "
        "created_at) values (:id, :o, :seam, :ref, :code, now())"),
        {"id": new_id("lrej"), "o": org_id, "seam": DISCOVERY_SEAM, "ref": source_ref[:200],
         "code": reason[:200]})


# =================================================================================================
# Step 1 — TRIGGER: one canon document, as this unit reads it
# =================================================================================================

_LOAD_EVENT = text(
    "select e.event_id, e.internal_kind, e.source_object_id, e.dedup_key, e.occurred_at, "
    "       p.clean_text "
    "from source_events e left join prepared_content p "
    "  on p.org_id = e.org_id and p.event_id = e.event_id "
    "where e.org_id = :o and e.event_id = :e")


def load_canon_document(conn, *, org_id: str, event_id: str) -> CanonDocument | None:
    """One canon event as a `CanonDocument`, or None when it is not canon or has no prepared text.

    The offsets a span carries are into the PREPARED text (L1's masked, replayable form), which is
    the only coordinate system the extractor is ever shown — so a document whose prepared row has
    aged out of its 180-day TTL is unreadable rather than readable against the wrong bytes.
    """
    row = conn.execute(_LOAD_EVENT, {"o": org_id, "e": event_id}).mappings().first()
    if row is None:
        return None
    kind = normalize_kind(row["internal_kind"])
    if kind is None or not row["clean_text"]:
        return None
    slug = (row["source_object_id"].split(":", 1)[1]
            if ":" in row["source_object_id"] else row["source_object_id"])
    return CanonDocument(
        org_id=org_id, event_id=row["event_id"], kind=kind,
        title=slug.replace("-", " ").strip().title() or slug,
        text=row["clean_text"], occurred_at=row["occurred_at"],
        version_key=row["dedup_key"], locale=org_locale(conn, org_id))


def org_locale(conn, org_id: str) -> str | None:
    """The tenant's DECLARED locale, or None. Never guessed.

    ALG-10 needs it to tell "$50,000" (USD, CAD, AUD, …) apart, and refuses rather than picking
    one when nobody has said. A tenant that has declared none gets a COUNTED
    `threshold_unparseable` refusal on dollar thresholds, which is visible, instead of a rule
    denominated in a currency nobody chose.
    """
    return conn.execute(text("select locale from orgs where id = :o"), {"o": org_id}).scalar()


def already_discovered(conn, *, org_id: str, event_id: str, version_key: str) -> bool:
    """Has this exact document VERSION already been read? Editing the policy mints a new key."""
    return bool(conn.execute(text(
        "select 1 from org_rule_discovery_runs "
        "where org_id = :o and event_id = :e and version_key = :v"),
        {"o": org_id, "e": event_id, "v": version_key}).first())


def _record_run(conn, doc: CanonDocument, *, counters: Mapping[str, Any], at: datetime,
                outcome: str) -> None:
    conn.execute(text(
        "insert into org_rule_discovery_runs (org_id, event_id, version_key, kind, outcome, "
        "counters, ran_at) values (:o, :e, :v, :k, :out, cast(:c as jsonb), :at) "
        "on conflict (org_id, event_id, version_key) do update set "
        "outcome = excluded.outcome, counters = excluded.counters, ran_at = excluded.ran_at"),
        {"o": doc.org_id, "e": doc.event_id, "v": doc.version_key, "k": doc.kind,
         "out": outcome, "c": canonical_dumps(dict(counters)), "at": at})


# =================================================================================================
# Steps 2-5 — the run
# =================================================================================================

def run_org_discovery(conn, *, org_id: str, event_id: str, extractor: OrgRuleExtractor,
                      now: datetime, actor: str | None = None,
                      policy: LearningPolicy | None = None) -> dict[str, Any]:
    """N-3 over ONE canon document, inside the caller's transaction.

    Doc 02 §L3.2-U1's six steps in order: trigger, model call, deterministic validation, propose
    into L6 at OBSERVED, govern through the existing pipeline, and — on confirmation, not here —
    serve. Returns a counter dict. Raises only on a programming error; a model failure, a
    non-rule-bearing kind and an unreadable document are all RECORDED outcomes.
    """
    from genios_engine.feedback.orchestrator import load_or_seed_policy

    doc = load_canon_document(conn, org_id=org_id, event_id=event_id)
    if doc is None:
        return {"event_id": event_id, "skipped": "not_canon_or_no_text"}
    if not doc.rule_bearing:
        # THE COST GATE, and it is deliberately before the model call. Paying for a T2 extraction
        # to read a wiki page is how a per-document unit becomes a per-document bill — and doc
        # 02's own counter-example, "a sentence in a handbook is not a rule", is this kind.
        result = gate_candidates(doc, ())
        _record_run(conn, doc, counters=result.counters(), at=now, outcome="kind_not_rule_bearing")
        record_refusal(conn, org_id=org_id, source_ref=doc.source_ref,
                       reason="kind_not_rule_bearing")
        return {"event_id": event_id, "skipped": "kind_not_rule_bearing", "kind": doc.kind}
    if already_discovered(conn, org_id=org_id, event_id=event_id, version_key=doc.version_key):
        return {"event_id": event_id, "skipped": "already_discovered"}

    try:
        candidates = list(extractor.propose(text=doc.text, kind=doc.kind, title=doc.title))
    except Exception as exc:                       # noqa: BLE001 — a model failure is not a run
        _record_run(conn, doc, counters={"candidates": 0, "extractor_error": 1}, at=now,
                    outcome="extractor_failed")
        return {"event_id": event_id, "skipped": "extractor_failed",
                "error": f"{type(exc).__name__}: {exc}"[:200]}

    result = gate_candidates(
        doc, candidates,
        resolve_approver=lambda n: resolve_approver_node(conn, org_id=org_id, name=n))
    for refusal in result.refusals:
        record_refusal(conn, org_id=org_id, source_ref=doc.source_ref,
                       reason=f"{refusal.reason}: {refusal.detail}" if refusal.detail
                       else refusal.reason)

    pinned = policy or load_or_seed_policy(conn, org_id, now=now)
    counters: dict[str, Any] = dict(result.counters())
    counters["proposed"] = 0
    counters["awaiting_human"] = 0
    for rule in result.rules:
        obj = build_proposal(doc, rule, policy=pinned)
        admission = admit_discovery(
            conn, obj, policy=pinned, now=now, actor=actor,
            admission_detail={"subject": rule.subject, "category": rule.category,
                              "span_verdict": rule.verdict.value,
                              "authority_pending": rule.authority_pending})
        if admission.admitted:
            counters["proposed"] += 1
            counters["awaiting_human"] += 1 if admission.awaiting_human else 0
        else:
            key = f"not_admitted_{admission.reason}"
            counters[key] = counters.get(key, 0) + 1
    _record_run(conn, doc, counters=counters, at=now, outcome="ran")
    return {"event_id": event_id, "kind": doc.kind, **counters}


# =================================================================================================
# Step 6 — SERVE. One discovery, two consumers.
# =================================================================================================

#: The same upsert `context/authority_view.PostgresAuthorityRules.put` performs, executed on the
#: CALLER'S connection. That store opens its own `engine.begin()`, and an authority row that
#: commits in a different transaction from the brain version it was derived from is exactly the
#: approved-but-not-published split `learning_routes.review` was fixed for. The column list is
#: pinned to the contract by `test_the_authority_projection_covers_every_contract_field`.
_AUTHORITY_UPSERT = text(
    "insert into authority_rules (org_id, rule_id, subject_type, threshold_minor_units, currency, "
    "threshold_basis_points, "
    "approver_node_id, delegate_node_id, source, evidence_ref, valid_from, valid_until) "
    "values (:org_id, :rule_id, :subject_type, :threshold_minor_units, :currency, "
    ":threshold_basis_points, "
    ":approver_node_id, :delegate_node_id, :source, :evidence_ref, :valid_from, :valid_until) "
    "on conflict (org_id, rule_id, valid_from) do update set "
    "  subject_type = excluded.subject_type, "
    "  threshold_minor_units = excluded.threshold_minor_units, "
    "  currency = excluded.currency, "
    "  threshold_basis_points = excluded.threshold_basis_points, "
    "  approver_node_id = excluded.approver_node_id, "
    "  delegate_node_id = excluded.delegate_node_id, "
    "  source = excluded.source, "
    "  evidence_ref = excluded.evidence_ref, "
    "  valid_until = excluded.valid_until")


def project_authority_rules(conn, *, org_id: str, at: datetime) -> dict[str, int]:
    """Project CONFIRMED Organization-brain approval rules into `authority_rules` (L2.1.4).

    Driven off the PUBLISHED brain entries rather than off the discovery, so it is idempotent,
    order-independent and true whether the confirmation arrived through the console, a rollback
    or a supersession. Three things happen, and all three are the historical-window contract that
    makes "who could approve this in March?" still answerable in September:

      * an active `orgrule:approval:*` entry with a resolved approver becomes a `discovered` rule
        whose `valid_from` is the DOCUMENT's stated time, never `now`;
      * any earlier window for the same `rule_id` is CLOSED at that instant — a superseding
        policy ENDS its predecessor rather than editing it;
      * a rule whose brain entry is no longer active is closed at `at`: a retired policy stops
        binding, and March's answer survives its retirement.

    An entry marked `authority_pending` is deliberately skipped. `AuthorityRule.approver_node_id`
    is required, and a rule whose approver nobody could name must not bind anything — doc 02's
    "route to HUMAN_REVIEW instead of publishing", enforced where it can actually be enforced.
    """
    rows = conn.execute(text(
        "select subject, value from learned_brain_entries "
        "where org_id = :o and brain = 'organization' and active and subject like :p "
        "order by subject"),
        {"o": org_id, "p": f"{SUBJECT_PREFIX}:approval:%"}).mappings().all()

    live: list[str] = []
    upserted = closed = skipped = 0
    for row in rows:
        value = dict(row["value"] or {})
        approver = value.get("approver_node_id")
        valid_from = _as_aware((value.get("document") or {}).get("stated_at"))
        if not approver or valid_from is None:
            skipped += 1
            continue
        rule = AuthorityRule(
            rule_id=authority_rule_id(row["subject"]),
            subject_type=value.get("subject_type") or "",
            threshold_minor_units=value.get("threshold_minor_units"),
            currency=value.get("currency"),
            # The ratio arm. A percentage rule reaches the Authority view with its BOUND intact
            # rather than as an unbounded "any discount needs the founder", which is what
            # projecting it with both threshold columns null would have meant — a rule stricter
            # than the policy it was read from, written by an omission.
            threshold_basis_points=value.get("threshold_basis_points"),
            approver_node_id=approver,
            source=AuthoritySource.DISCOVERED,
            evidence_ref=(value.get("evidence") or {}).get("source_ref"),
            valid_from=valid_from)
        live.append(rule.rule_id)
        closed += conn.execute(text(
            "update authority_rules set valid_until = :vf "
            "where org_id = :o and rule_id = :r and valid_from < :vf "
            "  and (valid_until is null or valid_until > :vf)"),
            {"o": org_id, "r": rule.rule_id, "vf": rule.valid_from}).rowcount
        conn.execute(_AUTHORITY_UPSERT, {
            "org_id": org_id, "rule_id": rule.rule_id, "subject_type": rule.subject_type,
            "threshold_minor_units": rule.threshold_minor_units, "currency": rule.currency,
            "threshold_basis_points": rule.threshold_basis_points,
            "approver_node_id": rule.approver_node_id, "delegate_node_id": rule.delegate_node_id,
            "source": rule.source.value, "evidence_ref": rule.evidence_ref,
            "valid_from": rule.valid_from, "valid_until": rule.valid_until})
        upserted += 1

    retired = conn.execute(text(
        "update authority_rules set valid_until = :at "
        "where org_id = :o and source = 'discovered' and valid_until is null "
        "  and valid_from < :at and rule_id <> all(cast(:live as text[]))"),
        {"o": org_id, "at": at, "live": sorted(set(live))}).rowcount
    return {"upserted": upserted, "closed": closed + retired, "skipped": skipped}


def project_confirmed_rule(conn, *, org_id: str, learning_id: str, at: datetime) -> dict | None:
    """The console hook: after an N-3 discovery is approved, refresh the Authority view.

    A no-op for every other kind of learning object, so `learning_routes.review` can call it
    unconditionally without knowing what Layer 3 is.
    """
    unit = conn.execute(text("select unit from learning_objects "
                             "where org_id = :o and learning_id = :l"),
                        {"o": org_id, "l": learning_id}).scalar()
    if unit != DISCOVERY_UNIT:
        return None
    return project_authority_rules(conn, org_id=org_id, at=at)


def _as_aware(value: Any) -> datetime | None:
    from genios_engine.contracts.validators import require_aware
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value)
        except ValueError:
            return None
    try:
        return require_aware(value, "stated_at")
    except (TypeError, ValueError):
        return None


# =================================================================================================
# The real caller — canon ingest
# =================================================================================================

#: A bounded sweep over the documents this tenant has not had read yet. Both canon doors schedule
#: THIS rather than naming an event id: the upload door emits one event per CHUNK and keeps none
#: of their ids, and a sweep is idempotent by construction because `org_rule_discovery_runs` is
#: keyed on the document VERSION — a re-run of an already-read chunk costs one indexed read.
_UNDISCOVERED = text(
    "select e.event_id from source_events e "
    "join prepared_content p on p.org_id = e.org_id and p.event_id = e.event_id "
    "left join org_rule_discovery_runs r "
    "  on r.org_id = e.org_id and r.event_id = e.event_id and r.version_key = e.dedup_key "
    "where e.org_id = :o and e.internal_kind = any(cast(:kinds as text[])) "
    "  and r.event_id is null "
    "order by e.occurred_at desc limit :lim")


def undiscovered_events(conn, *, org_id: str, limit: int = 25) -> list[str]:
    """Rule-bearing canon events this tenant has never had read, newest first."""
    from genios_engine.packs.brains.org_rule_extract import rule_bearing_kinds
    return [r[0] for r in conn.execute(
        _UNDISCOVERED, {"o": org_id, "kinds": list(rule_bearing_kinds()), "lim": limit})]


def sweep_org_rule_discovery(org_id: str, *, limit: int = 25, engine=None,
                             extractor: OrgRuleExtractor | None = None,
                             now: datetime | None = None) -> dict[str, Any]:
    """Read every not-yet-read rule-bearing canon document for one tenant. The ingest-time caller.

    Runs as an in-process BackgroundTask (never Celery — the broker is quota-limited Upstash), one
    transaction per document so one bad document cannot cost the rest, and it is safe to schedule
    on every canon write because the version key makes a repeat a no-op.
    """
    from genios_engine.packs.brains.org_rule_extract import make_org_rule_extractor
    from genios_engine.platform.logging import get_logger

    log = get_logger("genios.feedback.org_rule_ingest")
    if engine is None:
        from genios_engine.platform.wiring import make_graph_store
        store = make_graph_store()
        if store is None:
            return {"org_id": org_id, "skipped": "no_database"}
        engine = store.engine
    extractor = extractor or make_org_rule_extractor()
    if extractor is None:
        return {"org_id": org_id, "skipped": "no_extractor"}
    # THE CLOCK IS READ AT THE PROCESS BOUNDARY, once, and passed down as a parameter everywhere
    # below it. No function in this pipeline calls `now()` in its own logic.
    evaluated_at = now or datetime.now(timezone.utc)

    with engine.connect() as c:
        event_ids = undiscovered_events(c, org_id=org_id, limit=limit)
    documents = proposed = failed = 0
    for event_id in event_ids:
        try:
            with engine.begin() as c:
                outcome = run_org_discovery(c, org_id=org_id, event_id=event_id,
                                            extractor=extractor, now=evaluated_at)
            documents += 1
            proposed += int(outcome.get("proposed") or 0)
        except Exception:            # noqa: BLE001 — one document's failure is not the rest's
            failed += 1
            log.exception("org-rule discovery failed for %s/%s", org_id, event_id)
    return {"org_id": org_id, "documents": documents, "proposed": proposed,
            "failed": failed, "considered": len(event_ids)}


__all__ = ["Admission", "LADDER", "admit_discovery", "already_discovered", "load_canon_document",
           "org_locale", "project_authority_rules", "project_confirmed_rule", "record_refusal",
           "run_org_discovery", "sweep_org_rule_discovery", "undiscovered_events"]
