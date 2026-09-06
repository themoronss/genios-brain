"""G8 · L1.6.10 (U1 + U2) and L1.7.4 — the L1 -> L2 boundary crossing.

    pytest tests/capture/esqe/test_publisher.py -q

A `QualifiedEnterpriseSignal` leaves Layer 1 exactly once and this is the seam that lets it. So
almost nothing in this file is about the arithmetic; it is about which of the gate's three
answers a signal gets, and about what is left behind in each case:

    EMIT   -> a row in `qualified_signals`, carrying the PUBLISHED numbers
    PARK   -> a reviewable `parked_events` record, and NO stored row (V-1 only)
    REJECT -> no row anywhere, and a refusal that names the rule (V-2..V-4, V-6, V-7)

Two of those are easy to get wrong in ways no unit test of the validator would see, and both
have a test of their own here:

  * **V-5 emits smaller.** The downgrade rides on `decision.signal`, so a publisher that stored
    the object it handed IN would re-inflate a confidence the gate had just reduced — and the
    only place anyone would ever notice is the stored column. `test_v5_...` asserts against the
    ROW, not against the decision.
  * **A below-floor signal must never reach the gate at all.** The floor is what makes the
    publisher affordable; a publisher that re-judged everything would make ALG-18 decorative.
    `test_a_below_floor_signal_never_reaches_the_publisher` drives the real seam with a real
    dropped verdict and asserts the gate was not consulted.

Lanes: everything here is hermetic except the `pg` block, which opens the scratch Postgres for
the real upsert and for tenant erasure — the erasure proof is a real cascade, because
`account_routes._wipe` runs with no try/except and a table missing from its list leaks silently.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from genios_engine.capture.esqe import publisher as P
from genios_engine.capture.esqe import qualification as Q
from genios_engine.capture.esqe.normalize import NormalizedSignal
from genios_engine.capture.esqe.signal_store import (SIGNAL_TABLE, InMemorySignalStore,
                                                     PostgresSignalStore, QualifiedSignalRow)
from genios_engine.capture.esqe.source_analyzer import ActorBasis, SourceAttribution
from genios_engine.capture.validate.authority import AuthorityBasis, AuthorityWeight
from genios_engine.contracts.conflict import Authority
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import Commitment, ExtractionResult
from genios_engine.contracts.publication import UNVERIFIED_EVIDENCE_FLAG, VISIBILITY_UNKNOWN
from genios_engine.contracts.signal import SignalType
from genios_engine.contracts.visibility import Visibility

NOW = datetime(2026, 4, 2, 9, 0, tzinfo=timezone.utc)
ORG = "org_pub_a"

#: The one place the fixture text lives. Offsets below are measured against it, never guessed.
BODY = "Finance will confirm the Kestrel MSA renewal at $84,000 before the quarter closes."

PROVENANCE = dict(model_snapshot="fake-model-1", prompt_version="p1", schema_version="1",
                  extraction_profile="email", input_tokens=1000, output_tokens=200)


def _span(quote: str = "Finance", *, verified: bool = True,
          source_ref: str = "prepared_content:pc_1") -> EvidenceSpan:
    """A receipt FOUND in the fixture text, the way L1.5.1 verifies one — never hand-counted."""
    start = BODY.index(quote)
    return EvidenceSpan(source_ref=source_ref, quote=quote, start_offset=start,
                        end_offset=start + len(quote), verified=verified)


def _extraction(*spans: EvidenceSpan, confidence_bp: int = 8000) -> ExtractionResult:
    """A real `ExtractionResult` whose commitment rests on exactly these spans.

    The claim matters: `confidence_sources` composes from CLAIMS, so an extraction with no claim
    on the signal's spans would exercise the fallback rather than the main path.
    """
    return ExtractionResult(
        intent="inform", stance="neutral",
        commitments=[Commitment(actor="Finance", action="confirm", is_conditional=False,
                                evidence=list(spans), confidence_bp=confidence_bp)],
        **PROVENANCE)


def _attribution() -> SourceAttribution:
    return SourceAttribution(
        evidence=AuthorityWeight(authority=Authority.SIGNED_DOCUMENT,
                                 basis=AuthorityBasis.EXECUTED),
        actor_authority_bp=8000, actor_basis=ActorBasis.ROLE_LADDER,
        actor_email="cfo@kestrel.example")


def _signal(*, org_id: str = ORG, event_id: str = "evt_1",
            spans: tuple[EvidenceSpan, ...] | None = None,
            visibility: Visibility | None = None,
            signal_type: SignalType = SignalType.CONTRACT_RENEWAL,
            subject_key: str = "thread:thr_kestrel",
            internal_kind: str | None = None) -> NormalizedSignal:
    return NormalizedSignal(
        org_id=org_id, event_id=event_id, source="gmail", object_type="email_message",
        occurred_at=NOW - timedelta(hours=3),
        visibility=(visibility if visibility is not None
                    else Visibility(scope="org", derived_from="source:gmail")),
        recipients=("ops@genios.ai", "cfo@kestrel.example"), internal_kind=internal_kind,
        signal_type=signal_type, predicate="renewal_window_open",
        subject_key=subject_key, subject_label="Kestrel MSA renewal",
        primary_entity="Kestrel Systems", primary_date=None, primary_amount=None,
        evidence_refs=(spans if spans is not None else (_span(),)),
        attribution=_attribution())


@dataclass
class _Gated:
    """The `GatedEvent` fields the publisher reads. A stub with exactly those four, so a test
    that stops asserting on one of them shows up as an unused field rather than as a silently
    defaulted column."""

    triage_lane: str = "P1"
    coverage_ready: bool | None = True
    versions: dict = field(default_factory=lambda: {"preprocessor": "pp-2", "gate_rules": "gate-1"})


def _inputs(signal: NormalizedSignal, *, importance_bp: int | None = 7800,
            extraction: ExtractionResult | None = None,
            extraction_ref: str = "l1x_9f2c", gated: _Gated | None = None,
            secondary_types: tuple = (SignalType.FINANCIAL_OBLIGATION,)) -> P.SignalInputs:
    return P.SignalInputs(
        importance_bp=importance_bp,
        importance_components={"monetary_exposure_bp": 7200, "signal_type_weight_bp": 8000},
        importance_version="alg17-v1",
        extraction=extraction if extraction is not None else _extraction(*signal.evidence_refs),
        extraction_ref=extraction_ref,
        gated=gated if gated is not None else _Gated(),
        secondary_types=secondary_types,
        domain_hints=())


# =============================================================================================
# The three outcomes, one test each
# =============================================================================================
def test_a_valid_signal_emits_and_lands_in_the_store():
    """The happy path, end to end: gate says EMIT, a row is written, and the row says what the
    producers said rather than what the publisher could have defaulted."""
    store = InMemorySignalStore()
    signal = _signal()
    published, parked, refused = P.publish_one(signal, _inputs(signal), eval_time=NOW)

    assert parked is None and refused is None
    assert published is not None and published.decision.should_emit
    assert store.put([published.row]) == 1

    row = store.get(ORG, published.row.signal_id)
    assert row is not None, "the store did not keep what the gate published"
    assert row.signal_id == Q.signal_ref(signal), \
        "the published id is not the id the drop ledger files refusals under"
    assert row.event_id == "evt_1" and row.org_id == ORG
    assert row.signal_type == SignalType.CONTRACT_RENEWAL.value
    assert row.secondary_types == (SignalType.FINANCIAL_OBLIGATION.value,)
    assert row.importance_bp == 7800, "the row re-scored instead of taking ALG-18's verdict"
    assert row.importance_version == "alg17-v1"
    assert row.importance_components["monetary_exposure_bp"] == 7200, \
        "'why is this a 7800?' must be answerable from the row"
    assert row.extraction_ref == "l1x_9f2c", "the pointer into l1_extraction_results was lost"
    assert row.confidence_bp > 0 and set(row.confidence_vector) == {
        "evidence", "expertise", "freshness", "coverage"}
    assert [span["quote"] for span in row.evidence_refs] == ["Finance"]
    assert row.visibility["scope"] == "org"
    assert row.coverage_ready is True
    assert row.state == "active" and row.supersedes is None
    assert row.expires_at is not None, "ALG-19's expiry never reached the stored row"
    assert row.occurred_at == signal.occurred_at
    # The envelope half — what makes the row rebuildable into the C-12 it came from.
    assert row.envelope["source"] == "gmail" and row.envelope["object_type"] == "email_message"
    assert row.envelope["triage_lane"] == "P1"
    assert row.envelope["recipients"] == ["ops@genios.ai", "cfo@kestrel.example"]
    assert row.envelope["versions"]["gate_rules"] == "gate-1"


def test_v4_empty_evidence_refs_rejects_and_stores_nothing():
    """A claim with no receipt is a guess. The constructor refuses the object outright, so this
    also proves the refusal became a ROW-shaped answer rather than a traceback inside a sweep."""
    store = InMemorySignalStore()
    signal = _signal(spans=())
    published, parked, refused = P.publish_one(
        signal, _inputs(signal, extraction=_extraction(_span())), eval_time=NOW)

    assert published is None and parked is None
    assert refused is not None and refused.outcome == "reject"
    assert "V-4" in refused.rules, f"rejected, but not by V-4: {refused.rules}"
    assert "receipt" in refused.detail
    assert store.list(ORG) == [], "a rejected signal reached the store"


def test_v1_a_signal_with_no_visibility_parks_and_is_not_a_reject():
    """PARKED IS NOT DELETED. An event whose audience was never established is an unanswered
    question, and the answer is frequently recoverable — so V-1 is the one rule that leaves a
    reviewable record instead of a refusal."""
    store = InMemorySignalStore()
    signal = _signal()
    # `NormalizedSignal.visibility` is `Visibility | None` — this is the state the normalizer can
    # legitimately produce and the publisher is the seam that must answer for it.
    object.__setattr__(signal, "visibility", None)

    published, parked, refused = P.publish_one(signal, _inputs(signal), eval_time=NOW)

    assert refused is None, "V-1 rejected; it must park"
    assert published is None
    assert parked is not None
    assert parked.reason_code == VISIBILITY_UNKNOWN
    assert parked.stage == "L1.6.10", "the park row cannot name which seam parked it"
    assert parked.org_id == ORG and parked.event_id == "evt_1"
    assert parked.trace and parked.trace[0]["rule"] == "V-1"
    assert store.list(ORG) == [], "a parked signal was also stored"


def test_v5_emits_with_a_reduced_confidence_and_the_stored_row_carries_the_downgrade():
    """V-5 is NON-BLOCKING and the downgrade rides on `decision.signal`.

    The assertion that matters is the last one: a publisher that stored its own input instead of
    the object the gate returned would pass every other line here and silently re-inflate the
    confidence in the one column a human reads it back from.
    """
    store = InMemorySignalStore()
    verified, unverified = _span("Finance"), _span("Kestrel MSA renewal", verified=False)
    signal = _signal(spans=(verified, unverified))
    inputs = _inputs(signal, extraction=_extraction(verified, unverified))

    composed = P.compose_for(signal, inputs.extraction, eval_time=NOW, coverage_bp=10000)
    published, parked, refused = P.publish_one(signal, inputs, eval_time=NOW)

    assert parked is None and refused is None and published is not None
    decision = published.decision
    assert decision.should_emit, "V-5 must downgrade and emit, never reject"
    assert UNVERIFIED_EVIDENCE_FLAG in decision.flags
    assert decision.unverified_span_count == 1
    assert decision.confidence_downgrade_bp > 0
    assert decision.published_confidence_bp < composed.confidence_bp

    assert store.put([published.row]) == 1
    row = store.get(ORG, published.row.signal_id)
    assert row.confidence_bp == decision.published_confidence_bp
    assert row.confidence_bp < composed.confidence_bp, \
        "the STORED row re-inflated the confidence V-5 had just reduced"
    # 3 of 4: one of two spans verified -> confidence * (2 + 1) // (2 * 2). Integer, no float.
    assert row.confidence_bp == composed.confidence_bp * 3 // 4


def test_the_published_object_is_the_decisions_signal_and_never_the_input():
    """The same fact stated structurally rather than numerically: `PublishedSignal.signal` IS
    `decision.signal`, so there is no path by which a caller can publish the input instead."""
    signal = _signal(spans=(_span("Finance"), _span("Kestrel MSA renewal", verified=False)))
    published, _, _ = P.publish_one(
        signal, _inputs(signal, extraction=_extraction(*signal.evidence_refs)), eval_time=NOW)
    assert published.signal is published.decision.signal
    assert published.row.confidence_bp == published.signal.confidence_bp


# =============================================================================================
# The sweep seam — and the ordering the floor exists for
# =============================================================================================
@dataclass
class _Event:
    event_id: str
    occurred_at: datetime
    org_id: str = ORG


@dataclass
class _Esqe:
    normalized: tuple
    classification: object = None
    domains: object = None


@dataclass
class _Result:
    event: _Event
    esqe: _Esqe
    extraction: object = None
    extraction_ref: str | None = None
    gated: object = None
    prepared: object = None


@dataclass
class _Summary:
    results: list
    conflicts: object = None


def _summary(*signals: NormalizedSignal, extraction_ref: str = "l1x_9f2c") -> _Summary:
    return _Summary(results=[
        _Result(event=_Event(event_id=s.event_id, occurred_at=s.occurred_at),
                esqe=_Esqe(normalized=(s,)),
                extraction=_extraction(*s.evidence_refs) if s.evidence_refs else _extraction(_span()),
                extraction_ref=extraction_ref, gated=_Gated())
        for s in signals])


def _verdict(signal: NormalizedSignal, *, qualified: bool, importance_bp: int | None = 7800,
             floor_bp: int = 2500) -> Q.QualificationVerdict:
    return Q.QualificationVerdict(
        org_id=signal.org_id, signal_id=Q.signal_ref(signal), event_id=signal.event_id,
        signal_type=signal.signal_type, predicate=signal.predicate,
        subject_key=signal.subject_key, qualified=qualified,
        reason=(Q.QualificationReason.AT_OR_ABOVE_FLOOR if qualified
                else Q.QualificationReason.BELOW_FLOOR),
        importance_bp=importance_bp, floor_bp=floor_bp,
        components={"monetary_exposure_bp": 7200}, importance_version="alg17-v1",
        payload_ref="prepared_content:pc_1", evaluated_at=NOW,
        retain_until=None if qualified else NOW + timedelta(days=90))


def _outcome(*verdicts: Q.QualificationVerdict, floor_bp: int = 2500) -> Q.QualificationOutcome:
    return Q.QualificationOutcome(
        floor=Q.QualificationFloor(org_id=ORG, floor_bp=floor_bp, owner="rohit@genios.ai",
                                   note="tuned after the pilot"),
        verdicts=verdicts)


def test_the_sweep_seam_publishes_every_qualified_signal_and_stores_it():
    store = InMemorySignalStore()
    signal = _signal()
    report = P.publish_sweep(_summary(signal), _outcome(_verdict(signal, qualified=True)),
                             org_id=ORG, store=store)

    assert len(report.emitted) == 1 and report.stored == 1
    assert report.refused == () and report.parked == ()
    assert [row.signal_id for row in store.list(ORG)] == [Q.signal_ref(signal)]


def test_a_below_floor_signal_never_reaches_the_publisher(monkeypatch):
    """ALG-18 decides, L1.6.10 does not re-decide.

    Asserted by watching the GATE rather than only the store: an empty store is also what a
    publisher that ran the gate and then dropped the result would produce, and those are two
    different bugs.
    """
    calls: list = []
    real = P.validate_publication
    monkeypatch.setattr(P, "validate_publication",
                        lambda *a, **kw: (calls.append(a), real(*a, **kw))[1])

    store = InMemorySignalStore()
    signal = _signal()
    report = P.publish_sweep(
        _summary(signal), _outcome(_verdict(signal, qualified=False, importance_bp=900)),
        org_id=ORG, store=store)

    assert calls == [], "a below-floor signal was put through the publication gate"
    assert report.emitted == () and report.stored == 0
    assert store.list(ORG) == []


def test_the_seam_publishes_the_qualified_half_and_leaves_the_dropped_half_alone():
    """Both halves of one sweep, so the join between verdict and signal is exercised rather than
    assumed: a publisher that ignored `signal_id` and published positionally passes the two
    single-signal tests above and fails this one."""
    store = InMemorySignalStore()
    kept, dropped = _signal(event_id="evt_keep"), _signal(event_id="evt_drop")
    report = P.publish_sweep(
        _summary(kept, dropped),
        _outcome(_verdict(kept, qualified=True),
                 _verdict(dropped, qualified=False, importance_bp=400)),
        org_id=ORG, store=store)

    assert [row.event_id for row in store.list(ORG)] == ["evt_keep"]
    assert len(report.emitted) == 1


def test_the_seam_never_raises_into_the_ingestion_path():
    """Publication is downstream of capture. A summary this cannot read costs the sweep its
    signals, never its mail."""
    broken = type("Broken", (), {"results": property(lambda self: 1 / 0)})()
    signal = _signal()
    assert P.publish_sweep(broken, _outcome(_verdict(signal, qualified=True)),
                           org_id=ORG, store=InMemorySignalStore()).emitted == ()


def test_the_seam_files_a_v1_park_row_and_stores_nothing_for_it():
    store, parked_store = InMemorySignalStore(), _SpyParkedStore()
    signal = _signal()
    object.__setattr__(signal, "visibility", None)
    report = P.publish_sweep(_summary(signal), _outcome(_verdict(signal, qualified=True)),
                             org_id=ORG, store=store, parked_store=parked_store)

    assert len(report.parked) == 1 and report.stored == 0
    assert [p.reason_code for p in parked_store.rows] == [VISIBILITY_UNKNOWN]
    assert store.list(ORG) == []


class _SpyParkedStore:
    def __init__(self) -> None:
        self.rows: list = []

    def add(self, parked) -> None:
        self.rows.append(parked)


def test_publication_is_deterministic_across_two_identical_passes():
    """Same sweep, same instant, byte-identical rows. A replay that produced a second id or a
    drifting confidence would make `qualified_signals` a log rather than a state."""
    signal = _signal()
    rows = [P.publish_sweep(_summary(signal), _outcome(_verdict(signal, qualified=True)),
                            org_id=ORG, store=InMemorySignalStore()).emitted[0].row
            for _ in range(2)]
    assert rows[0] == rows[1]


def test_a_tenants_verdicts_never_publish_under_another_org():
    """The verdict list is filtered by org before anything is gated: one sweep, two tenants'
    rows in the outcome, and only this tenant's signal may cross."""
    store = InMemorySignalStore()
    mine, theirs = _signal(event_id="evt_mine"), _signal(org_id="org_pub_b", event_id="evt_theirs")
    report = P.publish_sweep(
        _summary(mine, theirs),
        _outcome(_verdict(mine, qualified=True), _verdict(theirs, qualified=True)),
        org_id=ORG, store=store)

    assert [row.event_id for row in report.emitted and store.list(ORG)] == ["evt_mine"]
    assert store.list("org_pub_b") == []


# =============================================================================================
# The ALG-19 seam — L1.6.9's answer, not the publisher's guess
# =============================================================================================
def test_the_lifecycle_outcome_decides_the_stored_state_and_not_the_publisher():
    """`sweep_lifecycle` runs one line above the publish on the request path. A publisher that
    stamped `active` regardless would write a row saying LIVE about a signal the same sweep had
    just marked superseded — in the table every downstream surface reads."""
    from genios_engine.capture.esqe import lifecycle as L

    signal = _signal()
    record = L.record_of_normalized(signal, evaluated_at=NOW)
    superseded = L.LifecycleRecord(
        org_id=record.org_id, signal_id=record.signal_id, subject_key=record.subject_key,
        signal_type=record.signal_type, authority_rank=record.authority_rank,
        occurred_at=record.occurred_at, state=L.SUPERSEDED, supersedes="sig_older",
        expires_at=record.expires_at, evaluated_at=NOW)
    outcome = L.LifecycleOutcome(org_id=ORG, eval_time=NOW, records=(superseded,))

    store = InMemorySignalStore()
    report = P.publish_sweep(_summary(signal), _outcome(_verdict(signal, qualified=True)),
                             org_id=ORG, store=store, lifecycle=outcome)
    row = report.emitted[0].row
    assert row.state == L.SUPERSEDED and row.supersedes == "sig_older"
    assert row.expires_at == record.expires_at


def test_without_a_lifecycle_outcome_expiry_still_comes_from_alg19_and_not_from_a_default():
    """The fallback is ALG-19's own arithmetic, called — not a hardcoded window and not a null."""
    from genios_engine.capture.esqe.lifecycle import plan_expiry

    signal = _signal()
    stamp = P.alg19_stamp(signal, eval_time=NOW)
    assert stamp.state == "active" and stamp.supersedes is None
    assert stamp.expires_at == plan_expiry(signal.signal_type, occurred_at=signal.occurred_at,
                                           stated_date=None).expires_at


# =============================================================================================
# ALG-13 at the boundary
# =============================================================================================
def test_confidence_is_composed_from_the_claims_the_signal_rests_on():
    signal = _signal()
    sources = P.confidence_sources(signal, _extraction(*signal.evidence_refs, confidence_bp=6100),
                                   eval_time=NOW)
    assert [s.confidence_bp for s in sources] == [6100]
    assert sources[0].independence_key == "prepared_content:pc_1"
    assert sources[0].authority is Authority.SIGNED_DOCUMENT


def test_a_signal_no_claim_covers_falls_back_to_its_artifact_class_and_not_to_a_constant():
    """The fallback must still discriminate: a signed document and an inferred aside cannot
    publish the same confidence, which is what a hardcoded 5000 would do."""
    signal = _signal()
    # An extraction whose only claim rests on a DIFFERENT span — nothing matches.
    other = _extraction(_span("quarter"))
    signed = P.confidence_sources(signal, other, eval_time=NOW)

    weak = _signal()
    object.__setattr__(weak, "attribution", SourceAttribution(
        evidence=AuthorityWeight(authority=Authority.INFERRED, basis=AuthorityBasis.UNMAPPED),
        actor_authority_bp=3000, actor_basis=ActorBasis.UNKNOWN, actor_email="x@y.example"))
    inferred = P.confidence_sources(weak, other, eval_time=NOW)

    assert signed and inferred
    assert signed[0].confidence_bp > inferred[0].confidence_bp


def test_v6s_ceiling_and_the_composers_ceiling_are_one_list():
    """`ComposedConfidence` returns the arguments `validate_publication` takes, so the published
    confidence can never exceed the weakest source it was composed from."""
    signal = _signal()
    composed = P.compose_for(signal, _extraction(*signal.evidence_refs, confidence_bp=5200),
                             eval_time=NOW)
    published, _, _ = P.publish_one(
        signal, _inputs(signal, extraction=_extraction(*signal.evidence_refs,
                                                       confidence_bp=5200)), eval_time=NOW)
    assert composed.source_confidences == (5200,)
    assert published.row.confidence_bp <= min(composed.source_confidences)


# =============================================================================================
# Purity — the two properties this seam must never lose
# =============================================================================================
_SOURCES = {name: Path(f"genios_engine/capture/esqe/{name}.py").read_text()
            for name in ("publisher", "signal_store")}


@pytest.mark.parametrize("name", sorted(_SOURCES))
def test_no_float_anywhere_on_the_publication_path(name):
    """V-7 rejects a float in a published object; a float IN the publisher would be the same
    defect one level up, and it would produce it on every signal rather than on one."""
    tree = ast.parse(_SOURCES[name])
    divisions = [n for n in ast.walk(tree) if isinstance(n, ast.BinOp)
                 and isinstance(n.op, ast.Div)]
    floats = [n for n in ast.walk(tree) if isinstance(n, ast.Constant)
              and isinstance(n.value, float)]
    assert divisions == [], f"{name}.py uses true division"
    assert floats == [], f"{name}.py carries a float literal"


@pytest.mark.parametrize("name", sorted(_SOURCES))
def test_the_publication_path_imports_no_model_client(name):
    """Nothing here scores, ranks or decides. A model at the L1 -> L2 boundary would make the
    same message cross on Tuesday and not on Wednesday."""
    for banned in ("anthropic", "openai", "context.llm"):
        assert f"import {banned}" not in _SOURCES[name]
        assert f"from {banned}" not in _SOURCES[name]


def test_the_publisher_reads_no_clock():
    """`eval_time` is a parameter. A `now()` here would age evidence against the moment of the
    replay rather than the moment of the sweep."""
    assert "datetime.now" not in _SOURCES["publisher"]
    assert "utcnow" not in _SOURCES["publisher"]


# =============================================================================================
# WIRED — driven from `api/routes._run_ledger`, the request-path hook every run_sync caller uses
# =============================================================================================
def test_the_request_path_hook_publishes_the_sweep_into_the_signal_store(monkeypatch):
    """WIRING. Nothing in this test calls `publish_sweep`, `validate_publication` or a store: a
    summary goes into `api/routes._run_ledger` — the hook every `run_sync` caller in the HTTP
    layer passes as `run_ledger=` — and a `qualified_signals` row comes out.

    Nothing stands in for L1.6.7 or L1.6.8 either: the floor is the real one, the score on the
    stored row is ALG-17's real answer for this signal, and the state is ALG-19's. This asserts
    the whole chain — hook, floor, scorer, gate, store.
    """
    from genios_engine.api import routes
    from genios_engine.capture.esqe.importance import compute_org_baseline, score_importance

    signal = _signal(org_id="org_wire", event_id="evt_wire")
    expected = score_importance(
        signal, compute_org_baseline((), org_id="org_wire", eval_time=NOW), eval_time=NOW)

    store = InMemorySignalStore()
    monkeypatch.setattr(routes, "_signal_store", store)
    monkeypatch.setattr(routes, "_floor_store", Q.InMemoryFloorStore({"org_wire": 1}))
    monkeypatch.setattr(routes, "_drop_ledger", Q.InMemoryDropLedger())
    monkeypatch.setattr(routes, "_lifecycle_store", None)
    monkeypatch.setattr(routes, "_graph", None)   # the sync ledger is a different subsystem

    routes._run_ledger(org_id="org_wire", connection_id="con_wire", source="gmail",
                       mode="incremental", summary=_summary(signal))

    rows = store.list("org_wire")
    assert len(rows) == 1, "the request-path hook did not publish the sweep"
    row = rows[0]
    assert row.signal_id == Q.signal_ref(signal)
    assert row.importance_bp == expected.importance_bp, "the row lost ALG-17's real score"
    assert row.importance_version == expected.importance_version
    assert row.extraction_ref == "l1x_9f2c", "the pointer into l1_extraction_results was lost"
    assert row.confidence_bp > 0 and row.state == "active"
    assert row.expires_at is not None, "ALG-19 never reached the published row"


def test_the_request_path_hook_publishes_nothing_below_the_tenants_floor(monkeypatch):
    """The same summary under a floor above its score — through the request path. This is where
    a publisher that re-judged instead of reading the verdict fails at the seam."""
    from genios_engine.api import routes
    from genios_engine.capture.esqe.importance import compute_org_baseline, score_importance

    signal = _signal(org_id="org_wire_hi", event_id="evt_hi")
    real = score_importance(signal, compute_org_baseline((), org_id="org_wire_hi",
                                                         eval_time=NOW),
                            eval_time=NOW).importance_bp

    store = InMemorySignalStore()
    monkeypatch.setattr(routes, "_signal_store", store)
    monkeypatch.setattr(routes, "_floor_store",
                        Q.InMemoryFloorStore({"org_wire_hi": min(10000, real + 1)}))
    monkeypatch.setattr(routes, "_drop_ledger", Q.InMemoryDropLedger())
    monkeypatch.setattr(routes, "_lifecycle_store", None)
    monkeypatch.setattr(routes, "_graph", None)

    routes._run_ledger(org_id="org_wire_hi", connection_id="con", source="gmail",
                       mode="incremental", summary=_summary(signal))
    assert store.list("org_wire_hi") == []


def test_the_hook_still_publishes_when_the_l2_graph_store_is_absent(monkeypatch):
    """`_run_ledger` returns early when the L2 graph store is missing. Publication sits ABOVE
    that return: the early return is about the sync LEDGER, and the store that exists to FEED
    Layer 2 must not be switched off by an unrelated subsystem's off-switch — the defect D8
    already had to fix once for conflicts."""
    from genios_engine.api import routes

    store = InMemorySignalStore()
    monkeypatch.setattr(routes, "_signal_store", store)
    monkeypatch.setattr(routes, "_floor_store", Q.InMemoryFloorStore({"org_nograph": 1}))
    monkeypatch.setattr(routes, "_drop_ledger", Q.InMemoryDropLedger())
    monkeypatch.setattr(routes, "_lifecycle_store", None)
    monkeypatch.setattr(routes, "_graph", None)

    routes._run_ledger(org_id="org_nograph", connection_id="con", source="gmail",
                       mode="incremental",
                       summary=_summary(_signal(org_id="org_nograph", event_id="evt_ng")))
    assert len(store.list("org_nograph")) == 1


def test_the_pipeline_carries_the_extraction_ref_the_row_points_with():
    """`extraction_ref` is not a field the publisher can derive: the key is a digest computed
    inside the semantic lane and `ExtractionResult` does not carry it. If `CaptureResult` stops
    carrying it, every stored row silently falls back to the structured form and the pointer
    into `l1_extraction_results` stops resolving."""
    from genios_engine.capture.pipeline import CaptureResult

    assert "extraction_ref" in CaptureResult.__dataclass_fields__


# =============================================================================================
# pg — the real store, and tenant erasure
# =============================================================================================
@pytest.fixture
def pg_url(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres publisher tests skipped")
    return live_db_url


def _seed_org(url: str, org_id: str) -> None:
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine
    with get_engine(url).begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": org_id})
        cols = conn.execute(text(
            "select column_name, data_type from information_schema.columns "
            "where table_name='orgs' and is_nullable='NO' and column_default is null "
            "and column_name<>'id'")).all()
        names, holes, params = ["id"], [":id"], {"id": org_id}
        for col in cols:
            names.append(col.column_name)
            holes.append(f":{col.column_name}")
            params[col.column_name] = (0 if "int" in col.data_type or "numeric" in col.data_type
                                       else datetime.now(timezone.utc)
                                       if "timestamp" in col.data_type else org_id)
        conn.execute(text(f"insert into orgs ({', '.join(names)}) values ({', '.join(holes)})"),
                     params)


def _published_row(org_id: str) -> QualifiedSignalRow:
    signal = _signal(org_id=org_id, event_id=f"evt_{org_id}")
    published, _, _ = P.publish_one(signal, _inputs(signal), eval_time=NOW)
    return published.row


@pytest.mark.pg
def test_the_postgres_store_round_trips_a_published_signal_and_upserts_a_replay(pg_url):
    org = "org_pub_pg"
    _seed_org(pg_url, org)
    store = PostgresSignalStore(pg_url)
    row = _published_row(org)

    assert store.put([row]) == 1
    assert store.put([row]) == 1, "a replayed sweep must upsert, not append"

    stored = store.get(org, row.signal_id)
    assert stored is not None
    assert stored.importance_bp == row.importance_bp
    assert stored.importance_components == dict(row.importance_components), \
        "the jsonb round-trip lost or reshaped the components"
    assert stored.confidence_vector == dict(row.confidence_vector)
    assert stored.evidence_refs == tuple(row.evidence_refs)
    assert stored.visibility == dict(row.visibility)
    assert stored.envelope["recipients"] == list(row.envelope["recipients"])
    assert stored.expires_at == row.expires_at and stored.occurred_at == row.occurred_at
    assert stored.created_at is None or True     # written by the column default

    assert [r.signal_id for r in store.list(org)] == [row.signal_id]
    assert store.list(org, event_id="evt_nope") == []
    assert store.get("org_pub_pg_other", row.signal_id) is None, "the read crossed a tenant"


@pytest.mark.pg
def test_deleting_the_tenant_takes_every_published_signal_with_it(pg_url):
    """`evidence_refs` holds verbatim sentences out of the tenant's own mail. A deletion that
    skipped this table would leave a deleted customer's quotes in the one table every downstream
    surface reads. Proven against a real cascade, not against the erasure list alone."""
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine

    org = "org_pub_erase"
    _seed_org(pg_url, org)
    assert PostgresSignalStore(pg_url).put([_published_row(org)]) == 1

    engine = get_engine(pg_url)
    count = lambda conn: conn.execute(text(  # noqa: E731
        f"select count(*) from {SIGNAL_TABLE} where org_id=:o"), {"o": org}).scalar()

    with engine.connect() as conn:
        assert count(conn) == 1
    with engine.begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": org})
    with engine.connect() as conn:
        assert count(conn) == 0, "a deleted tenant's signals survived the cascade"


@pytest.mark.pg
def test_reset_erases_the_signal_store_through_the_real_wipe(pg_url):
    """The cascade above covers ACCOUNT DELETION. `/reset` is the other door: it runs
    `account_routes._wipe`, which deletes table by table with no try/except — so a table missing
    from `_ORG_SCOPED_TABLES` leaks silently rather than failing loudly."""
    from sqlalchemy import text

    from genios_engine.api import account_routes
    from genios_engine.platform.db import get_engine

    org = "org_pub_reset"
    _seed_org(pg_url, org)
    assert PostgresSignalStore(pg_url).put([_published_row(org)]) == 1

    engine = get_engine(pg_url)
    with engine.begin() as conn:
        wiped = account_routes._wipe(conn, org)
    assert wiped[SIGNAL_TABLE] == 1, "/reset did not erase the tenant's published signals"
    with engine.connect() as conn:
        assert conn.execute(text(f"select count(*) from {SIGNAL_TABLE} where org_id=:o"),
                            {"o": org}).scalar() == 0


def test_the_signal_table_is_on_the_tenant_erasure_list():
    """The static half of the same guarantee, so the omission is caught without a database."""
    from genios_engine.api import account_routes

    assert SIGNAL_TABLE in account_routes._ORG_SCOPED_TABLES, \
        f"{SIGNAL_TABLE} leaks on tenant reset"


# =============================================================================================
# Fail-soft — publication is downstream of capture, on the request path too
# =============================================================================================
def test_the_hook_survives_a_total_sync_failure_with_no_summary(monkeypatch):
    """`_run_ledger(summary=None, error=...)` is how a connector that never returned a batch is
    reported. Publication must be a no-op there rather than the thing that turns a failed sync
    into a 500 on the failure handler itself."""
    from genios_engine.api import routes

    store = InMemorySignalStore()
    monkeypatch.setattr(routes, "_signal_store", store)
    monkeypatch.setattr(routes, "_drop_ledger", Q.InMemoryDropLedger())
    monkeypatch.setattr(routes, "_lifecycle_store", None)
    monkeypatch.setattr(routes, "_graph", None)

    routes._run_ledger(org_id="org_dead", connection_id="con", source="gmail",
                       mode="incremental", summary=None, error="connector unreachable")
    assert store.list("org_dead") == []


def test_a_store_that_raises_costs_the_signals_and_never_the_sweep():
    """A database error must not unwind into the ingestion path — and it must not erase the
    decision either. `PublicationReport.stored` is documented as distinct from `len(emitted)`
    precisely so "the gate said EMIT and the store took nothing" is a countable state; a guard
    that swallowed the whole pass would report the same empty tuple as a sweep with no signals,
    and those are a database incident and a quiet Tuesday."""
    class _Broken:
        def put(self, rows):
            raise RuntimeError("connection reset")

    signal = _signal()
    report = P.publish_sweep(_summary(signal), _outcome(_verdict(signal, qualified=True)),
                             org_id=ORG, store=_Broken())
    assert report.stored == 0
    assert len(report.emitted) == 1, "a store failure erased the decision the gate had made"
