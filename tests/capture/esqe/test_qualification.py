"""L1.6.8-U1 (ALG-18) · the qualification FLOOR and its drop ledger.

    pytest tests/capture/esqe/test_qualification.py -q

The arithmetic under test is one comparison, so almost nothing here is about the comparison.
Doc 06's acceptance list is four lines and three of them are about what a REFUSAL leaves behind:

    below floor -> dropped, ledger row written WITH components and payload ref
    below floor + conflict -> qualified anyway
    below floor + internal_kind -> qualified anyway
    a dropped signal is fully reconstructable from its ledger row

That is the shape of this file. A floor that drops the right 92% and records nothing is
indistinguishable, from outside, from a predicate that failed to fire or an extraction that
never ran — an absence looks the same whatever produced it, and two of those three are
incidents. So the assertions that matter are: the row exists, it carries every component the
score was made of, it names the payload, and the payload is still fetchable when somebody comes
to ask.

The other half is the tenant boundary. `test_the_floor_is_a_tenant_row_not_a_module_constant`
runs ONE signal past TWO orgs and demands two different answers; a global constant passes every
other test in this file and fails that one, which is the point of writing it.

Lanes: the hermetic tests need nothing. `pg` marks the ones that open the scratch Postgres —
the ledger's real upsert, the 90-day payload retention it promises, and tenant erasure.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from genios_engine.capture.esqe import qualification as Q
from genios_engine.capture.esqe.importance import (BaselineBasis, EntityStanding,
                                                   ImportanceComponents, ImportanceScore,
                                                   OrgBaseline, compute_org_baseline,
                                                   score_importance)
from genios_engine.capture.esqe.normalize import NormalizedSignal
from genios_engine.capture.esqe.source_analyzer import ActorBasis, SourceAttribution
from genios_engine.capture.validate.authority import AuthorityBasis, AuthorityWeight
from genios_engine.contracts.conflict import Authority
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.signal import SignalType
from genios_engine.contracts.visibility import Visibility

NOW = datetime(2026, 4, 2, 9, 0, tzinfo=timezone.utc)
ORG = "org_floor_a"
OTHER_ORG = "org_floor_b"

#: A real components map in L1.6.7's documented shape (doc 06, L1.6.7-U1's worked example).
#: Written out rather than reduced to one key, because "the row carries the components" is only
#: a meaningful assertion if there is more than one component to lose.
COMPONENTS = {
    "monetary_exposure_bp": 7200,
    "deadline_proximity_bp": 6000,
    "actor_authority_bp": 8000,
    "entity_criticality_bp": 6000,
    "signal_type_weight_bp": 8000,
    "evidence_authority_multiplier_bp": 8500,
    "baseline_used": 4500000,
}


def _attribution() -> SourceAttribution:
    """One real `SourceAttribution` — ALG-14's own object, not a stand-in. The floor never reads
    it, which is exactly why it must be the real type: a signal that could only be built for
    this test would prove the test, not the unit."""
    return SourceAttribution(
        evidence=AuthorityWeight(authority=Authority.SIGNED_DOCUMENT,
                                 basis=AuthorityBasis.EXECUTED),
        actor_authority_bp=8000, actor_basis=ActorBasis.ROLE_LADDER,
        actor_email="cfo@kestrel.example")


def _signal(*, org_id: str = ORG, event_id: str = "evt_1",
            signal_type: SignalType = SignalType.CONTRACT_RENEWAL,
            predicate: str = "renewal_window_open",
            subject_key: str = "thread:thr_kestrel",
            internal_kind: str | None = None) -> NormalizedSignal:
    return NormalizedSignal(
        org_id=org_id, event_id=event_id, source="gmail", object_type="email_message",
        occurred_at=NOW - timedelta(hours=3), visibility=Visibility(scope="org", derived_from="source:gmail"),
        recipients=("ops@genios.ai",), internal_kind=internal_kind,
        signal_type=signal_type, predicate=predicate,
        subject_key=subject_key, subject_label="Kestrel MSA renewal",
        primary_entity="Kestrel Systems", primary_date=None, primary_amount=None,
        evidence_refs=(EvidenceSpan(source_ref="prepared_content:p1", quote="Kestrel",
                                    start_offset=0, end_offset=7, verified=True),),
        attribution=_attribution())


def _scored(importance_bp: int | None, **over) -> Q.ScoredSignal:
    signal_kw = {k: over.pop(k) for k in ("org_id", "event_id", "internal_kind", "signal_type",
                                          "subject_key") if k in over}
    return Q.ScoredSignal(
        signal=over.pop("signal", None) or _signal(**signal_kw),
        importance_bp=importance_bp,
        components=over.pop("components", dict(COMPONENTS)),
        importance_version=over.pop("importance_version", "importance_v1"),
        payload_ref=over.pop("payload_ref", "prepared_content:pc_kestrel_01"),
        carries_conflict=over.pop("carries_conflict", False))


def _floor(bp: int, org_id: str = ORG) -> Q.QualificationFloor:
    return Q.QualificationFloor(org_id=org_id, floor_bp=bp, owner="rohit@genios.ai",
                                note="tuned after the pilot")


# =============================================================================================
# The ladder — doc 06's four lines, one row each
# =============================================================================================
@pytest.mark.parametrize(
    "importance_bp, kwargs, qualified, reason",
    [
        # above the floor
        (7800, {}, True, Q.QualificationReason.AT_OR_ABOVE_FLOOR),
        # EXACTLY at the floor. `>=` in the spec: the floor is the lowest score worth
        # surfacing, not the first score too low to surface. A `>` here silently refuses the
        # boundary case, which is the half of the distribution tuning actually moves.
        (2500, {}, True, Q.QualificationReason.AT_OR_ABOVE_FLOOR),
        (2499, {}, False, Q.QualificationReason.BELOW_FLOOR),
        (0, {}, False, Q.QualificationReason.BELOW_FLOOR),
        # below the floor, but the two overrides
        (400, {"carries_conflict": True}, True, Q.QualificationReason.CONFLICT_OVERRIDE),
        (400, {"internal_kind": "policy"}, True, Q.QualificationReason.INTERNAL_KIND_OVERRIDE),
        # unscored travels — a floor that refuses what it could not measure turns a scorer
        # outage into total, silent signal loss
        (None, {}, True, Q.QualificationReason.UNSCORED),
        # ordering: a conflict on a signal that ALSO clears the floor is still just above-floor,
        # so the reason column stays a cause and not a coincidence
        (9000, {"carries_conflict": True}, True, Q.QualificationReason.AT_OR_ABOVE_FLOOR),
    ],
)
def test_the_ladder_decides_in_doc_06s_order(importance_bp, kwargs, qualified, reason):
    outcome = Q.qualify_signals([_scored(importance_bp, **kwargs)], floor=_floor(2500),
                                eval_time=NOW)
    verdict = outcome.verdicts[0]
    assert verdict.qualified is qualified
    assert verdict.reason is reason


def test_a_signal_above_the_floor_passes_and_leaves_no_ledger_row():
    """The quiet half of the contract: qualification is not a logging exercise. A row per
    QUALIFIED signal would make `qualification_drops` a copy of the signal store and the drop
    rate unreadable."""
    outcome = Q.qualify_signals([_scored(7800)], floor=_floor(2500), eval_time=NOW)
    assert outcome.qualified and not outcome.dropped
    assert Q.drop_rows(outcome) == ()
    assert outcome.verdicts[0].retain_until is None, (
        "a qualified signal's body is about to be read by L2; it needs no drop retention")


# =============================================================================================
# THE LEDGER — a drop that cannot be explained is indistinguishable from a bug
# =============================================================================================
def test_a_dropped_signal_leaves_a_row_carrying_its_components_and_its_payload_ref():
    """Doc 06's sentence, verbatim: *"below floor -> dropped, ledger row written WITH components
    and payload ref"*. Both halves are asserted because both have a separate way of going
    missing — components get summarised into one number, and the payload ref gets dropped as
    "we can find it from the event id" until the payload TTL expires."""
    outcome = Q.qualify_signals([_scored(900)], floor=_floor(2500), eval_time=NOW)
    ledger = Q.InMemoryDropLedger()
    assert ledger.put(Q.drop_rows(outcome)) == 1

    row = ledger.list(ORG)[0]
    assert row.importance_bp == 900 and row.floor_bp == 2500
    assert row.components == COMPONENTS, "the row must carry EVERY component, not a summary"
    assert row.payload_ref == "prepared_content:pc_kestrel_01"
    assert row.importance_version == "importance_v1"


def test_a_dropped_signal_is_fully_reconstructable_from_its_row():
    """Doc 06's fourth acceptance line. "Reconstructable" is not a feeling: every field a human
    needs to re-ask the question — which event, which kind of thing, what it was about, what it
    scored, against what, computed how, and where the body is — comes off this one row."""
    outcome = Q.qualify_signals([_scored(1200)], floor=_floor(3000), eval_time=NOW)
    row = Q.drop_rows(outcome)[0]

    assert row.event_id == "evt_1"
    assert row.signal_type == SignalType.CONTRACT_RENEWAL.value
    assert row.predicate == "renewal_window_open"
    assert row.subject_key == "thread:thr_kestrel"
    assert row.importance_bp == 1200 and row.floor_bp == 3000
    assert row.components and row.payload_ref
    assert row.evaluated_at == NOW
    assert row.retain_until == NOW + timedelta(days=90), (
        "doc 06: DROP, LOGGED, PAYLOAD RETAINED 90d — the row is what promises the 90 days")


def test_the_signal_id_on_a_drop_row_is_the_signals_content_address_not_a_counter():
    """A replayed sweep must file its refusal against the SAME id. An id from a counter or a
    uuid would make "how many signals did this tenant never see" count replays."""
    first = Q.signal_ref(_signal())
    assert first == Q.signal_ref(_signal()), "signal_ref is not stable across two constructions"
    assert first != Q.signal_ref(_signal(event_id="evt_2"))
    assert first != Q.signal_ref(_signal(org_id=OTHER_ORG)), "ids must not cross tenants"
    assert first.startswith("sig_")


def test_two_replays_of_one_refusal_are_one_row_and_a_moved_floor_is_a_new_one():
    """`drop_id` excludes `evaluated_at` and includes the floor. Re-running yesterday's sweep
    upserts one row; re-running it after the floor moved is a DIFFERENT decision and gets its
    own — which is what makes "the floor was raised and misses started" visible in the ledger."""
    ledger = Q.InMemoryDropLedger()
    for _ in range(2):
        ledger.put(Q.drop_rows(Q.qualify_signals([_scored(900)], floor=_floor(2500),
                                                 eval_time=NOW)))
    assert len(ledger.list(ORG)) == 1

    ledger.put(Q.drop_rows(Q.qualify_signals([_scored(900)], floor=_floor(4000),
                                             eval_time=NOW)))
    assert len(ledger.list(ORG)) == 2
    assert {r.floor_bp for r in ledger.list(ORG)} == {2500, 4000}


def test_the_in_memory_ledger_keeps_the_tenant_boundary():
    """Keyed on (org, drop_id) rather than the id alone: a hermetic test must not be able to
    pass against a store that would hand one tenant's subject keys to another."""
    ledger = Q.InMemoryDropLedger()
    ledger.put(Q.drop_rows(Q.qualify_signals([_scored(900)], floor=_floor(2500), eval_time=NOW)))
    ledger.put(Q.drop_rows(Q.qualify_signals(
        [_scored(900, org_id=OTHER_ORG)], floor=_floor(2500, OTHER_ORG), eval_time=NOW)))

    assert len(ledger.list(ORG)) == 1 and len(ledger.list(OTHER_ORG)) == 1
    assert ledger.get(ORG, ledger.list(OTHER_ORG)[0].drop_id) is None


# =============================================================================================
# THE FLOOR IS PER TENANT — the test a module constant fails
# =============================================================================================
def test_the_floor_is_a_tenant_row_not_a_module_constant():
    """ONE signal, TWO orgs, TWO floors, two outcomes. Doc 06: *"floor tuning is a per-tenant
    setting with an owner and a changelog, never a global constant edit"* — a startup's $8K
    renewal is its quarter and a bank's is noise, and a constant hands both the same cut-off."""
    store = Q.InMemoryFloorStore({ORG: 1000, OTHER_ORG: 6000}, owner="rohit@genios.ai")

    startup = Q.qualify_signals([_scored(4200)], floor=Q.resolve_floor(ORG, store),
                                eval_time=NOW)
    enterprise = Q.qualify_signals([_scored(4200, org_id=OTHER_ORG)],
                                   floor=Q.resolve_floor(OTHER_ORG, store), eval_time=NOW)

    assert startup.verdicts[0].qualified is True
    assert enterprise.verdicts[0].qualified is False
    assert startup.verdicts[0].floor_bp == 1000 and enterprise.verdicts[0].floor_bp == 6000


def test_a_tenant_with_no_row_gets_the_default_and_says_so():
    """The default is the value an UNTUNED tenant gets, never the value every tenant gets — and
    `origin` is how a support engineer tells "somebody set 2500" from "nobody set anything"."""
    floor = Q.resolve_floor("org_never_tuned", Q.InMemoryFloorStore())
    assert floor.floor_bp == Q.DEFAULT_FLOOR_BP == 2500
    assert floor.origin == "default" and floor.owner == "genios-default"


def test_no_store_at_all_still_qualifies_against_the_default():
    floor = Q.resolve_floor(ORG, None)
    assert floor.floor_bp == 2500 and floor.origin == "default"


def test_a_settings_read_that_raises_costs_the_tuning_not_the_qualification():
    """A floor lookup is a settings read. Failing it open means a slow database costs this
    tenant its tuning; failing it closed would leave a whole sweep unqualified."""
    class _Broken:
        def get(self, org_id):
            raise RuntimeError("settings database unreachable")

    assert Q.resolve_floor(ORG, _Broken()).origin == "default"


def test_a_floor_without_an_owner_is_refused():
    """The `owner` column is NOT NULL in the DDL for the same reason: an unattributed threshold
    that quietly halved a tenant's signal volume is the incident the column exists to prevent."""
    with pytest.raises(ValueError, match="owner"):
        Q.QualificationFloor(org_id=ORG, floor_bp=2500, owner="")


@pytest.mark.parametrize("bp", [-1, 10001])
def test_a_floor_outside_the_basis_point_range_is_refused(bp):
    with pytest.raises(ValueError, match="floor_bp"):
        Q.QualificationFloor(org_id=ORG, floor_bp=bp, owner="rohit@genios.ai")


def test_moving_the_floor_records_who_moved_it_and_from_what():
    """Doc 06 asks for an owner AND a changelog. The changelog is what makes a drop-rate
    regression diagnosable a month later."""
    store = Q.InMemoryFloorStore()
    store.set(ORG, 2000, owner="rohit@genios.ai", changed_by="rohit@genios.ai", at=NOW,
              reason="pilot tuning")
    store.set(ORG, 4500, owner="rohit@genios.ai", changed_by="pratap@genios.ai",
              at=NOW + timedelta(days=3), reason="too much noise reaching L2")

    history = store.history(ORG)
    assert [(c.from_bp, c.to_bp) for c in history] == [(2000, 4500), (None, 2000)]
    assert history[0].changed_by == "pratap@genios.ai"
    assert history[0].reason == "too much noise reaching L2"
    assert store.get(ORG).floor_bp == 4500


# =============================================================================================
# Determinism — the property the whole score path exists to have
# =============================================================================================
def test_replaying_identical_input_gives_the_identical_decision():
    """Byte-identical, not merely equal: the verdicts are serialised and compared as text, so a
    dict whose key order varied between replays would fail here rather than three layers up
    where two `components` strings for one decision look like two decisions."""
    def _run() -> str:
        outcome = Q.qualify_signals(
            [_scored(900), _scored(7800, event_id="evt_2"),
             _scored(400, event_id="evt_3", internal_kind="policy")],
            floor=_floor(2500), eval_time=NOW)
        return json.dumps([{
            "signal_id": v.signal_id, "qualified": v.qualified, "reason": v.reason.value,
            "importance_bp": v.importance_bp, "floor_bp": v.floor_bp,
            "components": v.components, "payload_ref": v.payload_ref,
            "evaluated_at": v.evaluated_at.isoformat(),
        } for v in outcome.verdicts], sort_keys=True)

    assert _run() == _run()


def test_components_are_stored_in_one_fixed_key_order():
    """The map is written to jsonb and read back by a human. Two replays whose components
    serialise in a different order produce two different strings for one decision."""
    shuffled = dict(reversed(list(COMPONENTS.items())))
    a = Q.qualify_signals([_scored(900, components=dict(COMPONENTS))],
                          floor=_floor(2500), eval_time=NOW).verdicts[0]
    b = Q.qualify_signals([_scored(900, components=shuffled)],
                          floor=_floor(2500), eval_time=NOW).verdicts[0]
    assert list(a.components) == list(b.components) == sorted(COMPONENTS)


def test_the_monitored_rates_are_integer_basis_points_that_sum_to_ten_thousand():
    """Doc 06 monitors `drop_rate` per org with an alert above 95% and `qualify_rate` opposite
    it. Both are counts over counts — a float here would be the only float in the module."""
    outcome = Q.qualify_signals(
        [_scored(900), _scored(900, event_id="evt_2"), _scored(900, event_id="evt_3"),
         _scored(7800, event_id="evt_4")],
        floor=_floor(2500), eval_time=NOW)
    assert outcome.drop_rate_bp == 7500 and isinstance(outcome.drop_rate_bp, int)
    assert outcome.qualify_rate_bp == 2500
    assert outcome.drop_rate_bp + outcome.qualify_rate_bp == 10000


def test_an_empty_pass_has_no_rate_rather_than_a_division_error():
    outcome = Q.qualify_signals([], floor=_floor(2500), eval_time=NOW)
    assert outcome.drop_rate_bp == 0 and outcome.verdicts == ()


# =============================================================================================
# Source laws — no float, no clock, no model, anywhere on this path
# =============================================================================================
_SOURCE = Path(Q.__file__).read_text()


@pytest.mark.parametrize("forbidden, why", [
    ("float(", "a float in the score path makes ranking depend on platform rounding"),
    ("math.log", "log scaling belongs to L1.6.7's integer bucket table, never to a float log"),
    ("datetime.now", "eval_time is a parameter; a clock here re-decides yesterday's drop today"),
    ("time.time", "same rule as datetime.now"),
    ("utcnow", "same rule as datetime.now"),
])
def test_the_module_source_contains_no_float_and_no_clock(forbidden, why):
    assert forbidden not in _SOURCE, why


def test_no_expression_in_the_module_can_produce_a_float():
    """Parsed, not grepped. `/` is true division in Python 3 and returns a float from two ints,
    and a float literal anywhere on this path makes a ranking depend on platform rounding. The
    AST is walked rather than the text scanned because the text is 40% prose — a regex over it
    reports every "capture/parked/" in a docstring and reports nothing anybody would fix."""
    tree = ast.parse(_SOURCE)
    divisions = [n for n in ast.walk(tree) if isinstance(n, ast.BinOp)
                 and isinstance(n.op, ast.Div)]
    floats = [n for n in ast.walk(tree) if isinstance(n, ast.Constant)
              and isinstance(n.value, float)]
    assert divisions == [], "true division on the score path returns a float"
    assert floats == [], "a float literal on the score path"


def test_the_module_imports_no_model_client():
    """The floor may be DESCRIBED by a model and must never be DECIDED by one: the same message
    reaching a founder on Tuesday and not on Wednesday is the failure that ends trust."""
    for banned in ("anthropic", "openai", "llm", "context.llm"):
        assert f"import {banned}" not in _SOURCE
        assert f"from {banned}" not in _SOURCE


# =============================================================================================
# The sweep seam — scoring, flooring and filing over a real SyncSummary shape
# =============================================================================================
@dataclass
class _Event:
    event_id: str
    occurred_at: datetime


@dataclass
class _Prepared:
    prepared_content_id: str


@dataclass
class _Result:
    event: _Event
    esqe: object
    extraction: object = None
    prepared: object = None


@dataclass
class _Esqe:
    normalized: tuple
    #: What `pipeline.run_esqe_stage` stamped on this event at CAPTURE, index-aligned with
    #: `normalized`. Empty here by default, because most rows in this file are about the floor
    #: rather than about the score, and an empty tuple is exactly the shape a summary from
    #: before ALG-17 was wired has — which is the branch the injected scorer serves.
    importance: tuple = ()


@dataclass
class _Summary:
    results: list
    conflicts: object = None


def _summary(*signals, prepared: str | None = "pc_1") -> _Summary:
    return _Summary(results=[
        _Result(event=_Event(event_id=s.event_id, occurred_at=NOW - timedelta(minutes=i)),
                esqe=_Esqe(normalized=(s,)),
                prepared=_Prepared(prepared) if prepared else None)
        for i, s in enumerate(signals)])


def _fixed_scorer(bp: int):
    """L1.6.7's signature with a PINNED number, for the rows that are about the floor rather
    than about the score. Used only where the exact importance is the test's input: the seam's
    default is the real `score_importance`, and the wiring tests below run it end to end."""
    def _score(signal, baseline, *, eval_time):
        return ImportanceScore(importance_bp=bp, components=_components(eval_time),
                               importance_version="alg17-test")
    return _score


def _components(eval_time: datetime) -> ImportanceComponents:
    return ImportanceComponents(
        monetary_exposure_bp=7200, deadline_proximity_bp=6000, actor_authority_bp=8000,
        entity_criticality_bp=6000, signal_type_weight_bp=8000,
        evidence_authority_multiplier_bp=8500, weighted_bp=7040, baseline_used=4_500_000,
        baseline_currency="USD", baseline_basis=BaselineBasis.ORG_HISTORY,
        entity_standing=EntityStanding.ACTIVE, eval_time=eval_time)


def _cold_baseline(org_id: str = ORG) -> OrgBaseline:
    """L1.6.7-U2's cold start — the baseline `qualify_sweep` builds for a tenant with no
    nightly one. Never a fabricated p50."""
    return compute_org_baseline((), org_id=org_id, eval_time=NOW)


def test_the_seam_scores_floors_and_files_a_whole_sweep():
    summary = _summary(_signal(event_id="evt_1"), _signal(event_id="evt_2"))
    ledger = Q.InMemoryDropLedger()
    outcome = Q.qualify_sweep(summary, org_id=ORG,
                              floor_store=Q.InMemoryFloorStore({ORG: 5000}),
                              ledger=ledger, scorer=_fixed_scorer(1200))

    assert len(outcome.dropped) == 2 and outcome.drop_rate_bp == 10000
    assert len(ledger.list(ORG)) == 2
    assert ledger.list(ORG)[0].payload_ref == "prepared_content:pc_1", (
        "the seam must reference the prepared row this event produced, in ALG-14's prefix:id form")


def test_the_seam_takes_its_instant_from_the_sweep_and_never_from_a_clock():
    summary = _summary(_signal(event_id="evt_1"))
    outcome = Q.qualify_sweep(summary, org_id=ORG, scorer=_fixed_scorer(1200),
                              floor_store=Q.InMemoryFloorStore({ORG: 5000}))
    assert outcome.verdicts[0].evaluated_at == NOW, (
        "the sweep's own stored world time is the instant, not the wall clock")


def test_a_scorer_that_raises_costs_that_signal_its_number_and_not_its_passage():
    """One try/except per SIGNAL, not one per sweep: a malformed extraction must not cost the
    other forty-nine their qualification, and an unscorable signal TRAVELS."""
    def _explodes(signal, baseline, *, eval_time):
        if signal.event_id == "evt_2":
            raise ValueError("no baseline for this currency")
        return ImportanceScore(importance_bp=900, components=_components(eval_time),
                               importance_version="alg17-test")

    summary = _summary(_signal(event_id="evt_1"), _signal(event_id="evt_2"))
    ledger = Q.InMemoryDropLedger()
    outcome = Q.qualify_sweep(summary, org_id=ORG, ledger=ledger, scorer=_explodes,
                              floor_store=Q.InMemoryFloorStore({ORG: 2500}))

    by_event = {v.event_id: v for v in outcome.verdicts}
    assert by_event["evt_1"].qualified is False
    assert by_event["evt_2"].qualified is True
    assert by_event["evt_2"].reason is Q.QualificationReason.UNSCORED
    assert len(ledger.list(ORG)) == 1


def test_with_no_scorer_at_all_nothing_is_dropped():
    """The explicit fail-open. A caller with no scorer has no number to compare, and the floor
    must then refuse nothing — the failure mode of the opposite default is silent and total."""
    outcome = Q.qualify_sweep(_summary(_signal()), org_id=ORG, scorer=None,
                              floor_store=Q.InMemoryFloorStore({ORG: 9000}))
    assert outcome.dropped == ()
    assert outcome.verdicts[0].reason is Q.QualificationReason.UNSCORED


def test_the_seam_defaults_to_the_real_alg17_scorer_and_stores_its_components():
    """No `scorer=` argument anywhere in this test. `qualify_sweep` reaches L1.6.7 itself, and
    the row carries ALG-17's own `importance_components` record — the version, the weighted
    mean before the multiplier, the baseline basis — not a reduction of it."""
    signal = _signal()
    expected = score_importance(signal, _cold_baseline(), eval_time=NOW)

    ledger = Q.InMemoryDropLedger()
    outcome = Q.qualify_sweep(
        _summary(signal), org_id=ORG, ledger=ledger,
        floor_store=Q.InMemoryFloorStore({ORG: expected.importance_bp + 1}))

    assert outcome.dropped and outcome.verdicts[0].importance_bp == expected.importance_bp
    row = ledger.list(ORG)[0]
    assert row.importance_version == expected.importance_version
    assert row.components == expected.components.as_record()
    assert row.components["weighted_bp"] == expected.components.weighted_bp
    assert row.components["baseline_basis"] == BaselineBasis.ESTIMATED.value, (
        "a cold-start tenant must be scored on the absolute ladder and SAY so")


def test_the_real_scorer_keeps_a_signal_above_the_tenants_floor_alive():
    """The other half of the same wire: same signal, floor one basis point below the real
    score, nothing filed."""
    signal = _signal()
    expected = score_importance(signal, _cold_baseline(), eval_time=NOW)

    ledger = Q.InMemoryDropLedger()
    outcome = Q.qualify_sweep(
        _summary(signal), org_id=ORG, ledger=ledger,
        floor_store=Q.InMemoryFloorStore({ORG: max(0, expected.importance_bp - 1)}))

    assert outcome.qualified and not outcome.dropped
    assert ledger.list(ORG) == []


def test_a_conflict_between_two_other_events_does_not_grant_this_event_the_override():
    """`ConflictOutcome.detection` covers the WHOLE sweep, so an unfiltered read would hand the
    override to every message on a page because two OTHER messages disagreed — the same defect
    `pipeline._conflicts_for` exists to prevent."""
    @dataclass
    class _Detected:
        event_ids: tuple

    @dataclass
    class _Detection:
        conflicts: tuple
        detected_at: datetime = NOW

    summary = _summary(_signal(event_id="evt_1"), _signal(event_id="evt_2"))
    summary.conflicts = type("O", (), {"detection": _Detection(conflicts=(
        _Detected(event_ids=("evt_2", "evt_9")),))})()

    outcome = Q.qualify_sweep(summary, org_id=ORG, scorer=_fixed_scorer(400),
                              floor_store=Q.InMemoryFloorStore({ORG: 5000}))
    by_event = {v.event_id: v for v in outcome.verdicts}
    assert by_event["evt_1"].qualified is False
    assert by_event["evt_2"].reason is Q.QualificationReason.CONFLICT_OVERRIDE


def test_an_empty_sweep_is_an_empty_outcome_and_not_a_crash():
    outcome = Q.qualify_sweep(_Summary(results=[]), org_id=ORG, scorer=_fixed_scorer(100))
    assert outcome.verdicts == () and outcome.floor.floor_bp == 2500


def test_the_seam_never_raises_into_the_ingestion_path():
    """Qualification is downstream of capture. A summary this cannot read costs the sweep its
    ledger, never its mail."""
    broken = type("Broken", (), {"results": property(lambda self: 1 / 0)})()
    assert Q.qualify_sweep(broken, org_id=ORG, scorer=_fixed_scorer(100)).verdicts == ()


def test_a_structured_event_with_no_prepared_row_still_names_a_payload():
    outcome = Q.qualify_sweep(_summary(_signal(), prepared=None), org_id=ORG,
                              scorer=_fixed_scorer(400),
                              floor_store=Q.InMemoryFloorStore({ORG: 5000}))
    assert outcome.dropped[0].payload_ref == "raw_payload:evt_1"


# =============================================================================================
# WIRED — driven from `api/routes._run_ledger`, the request-path hook every run_sync caller uses
# =============================================================================================
class _SpyLedger:
    def __init__(self) -> None:
        self.rows: list = []

    def put(self, rows) -> int:
        self.rows.extend(rows)
        return len(rows)


def test_the_request_path_hook_qualifies_the_sweep_and_files_its_drops(monkeypatch):
    """WIRING. Nothing in this test calls `qualify_signals`, `drop_rows` or a store: a summary
    goes into `api/routes._run_ledger` — the hook every `run_sync` caller in the HTTP layer
    passes as `run_ledger=` — and a drop row comes out of the tenant's ledger.

    Nothing stands in for L1.6.7 either: the score on the filed row is ALG-17's real answer for
    this signal, so this asserts the whole chain — hook, floor lookup, scorer, ledger.
    """
    from genios_engine.api import routes

    signal = _signal(org_id="org_wire", event_id="evt_wire")
    expected = score_importance(signal, _cold_baseline("org_wire"), eval_time=NOW)

    spy = _SpyLedger()
    monkeypatch.setattr(routes, "_drop_ledger", spy)
    monkeypatch.setattr(routes, "_floor_store",
                        Q.InMemoryFloorStore({"org_wire": expected.importance_bp + 1}))
    monkeypatch.setattr(routes, "_graph", None)   # the sync ledger is a different subsystem

    routes._run_ledger(org_id="org_wire", connection_id="con_wire", source="gmail",
                       mode="incremental", summary=_summary(signal))

    assert len(spy.rows) == 1, "the request-path hook did not qualify the sweep"
    row = spy.rows[0]
    assert row.org_id == "org_wire" and row.importance_bp == expected.importance_bp
    assert row.floor_bp == expected.importance_bp + 1
    assert row.components == expected.components.as_record(), "the row lost its components"
    assert row.payload_ref == "prepared_content:pc_1", "the row lost its payload ref"


def test_the_request_path_hook_uses_the_tenants_floor_and_not_a_constant(monkeypatch):
    """The same summary, twice, under two tenants' floors — through the request path. This is
    the test a module constant fails at the seam rather than in the unit."""
    from genios_engine.api import routes

    monkeypatch.setattr(routes, "_graph", None)
    real = score_importance(_signal(org_id="org_low"), _cold_baseline("org_low"),
                            eval_time=NOW).importance_bp
    monkeypatch.setattr(routes, "_floor_store", Q.InMemoryFloorStore(
        {"org_low": max(0, real - 1), "org_high": min(10000, real + 1)}))

    filed = {}
    for org in ("org_low", "org_high"):
        spy = _SpyLedger()
        monkeypatch.setattr(routes, "_drop_ledger", spy)
        routes._run_ledger(org_id=org, connection_id="con", source="gmail", mode="incremental",
                           summary=_summary(_signal(org_id=org, event_id=f"evt_{org}")))
        filed[org] = len(spy.rows)

    assert filed == {"org_low": 0, "org_high": 1}


def test_the_hook_still_files_when_the_l2_graph_store_is_absent(monkeypatch):
    """`_run_ledger` returns early when the L2 graph store is missing. Qualification sits ABOVE
    that return: the early return is about the sync LEDGER, and two unrelated subsystems must
    not share one off-switch — the defect D8 already had to fix once for conflicts."""
    from genios_engine.api import routes

    spy = _SpyLedger()
    monkeypatch.setattr(routes, "_drop_ledger", spy)
    monkeypatch.setattr(routes, "_floor_store", Q.InMemoryFloorStore({"org_nograph": 10000}))
    monkeypatch.setattr(routes, "_graph", None)

    routes._run_ledger(org_id="org_nograph", connection_id="con", source="gmail",
                       mode="incremental",
                       summary=_summary(_signal(org_id="org_nograph", event_id="evt_ng")))
    assert len(spy.rows) == 1


def test_a_total_sync_failure_reports_no_qualification_rather_than_crashing(monkeypatch):
    """`_run_ledger` is also the FAILURE reporter — called with `summary=None` when a connector
    never returned a batch. There is nothing to qualify and nothing may explode."""
    from genios_engine.api import routes

    spy = _SpyLedger()
    monkeypatch.setattr(routes, "_drop_ledger", spy)
    monkeypatch.setattr(routes, "_graph", None)
    routes._run_ledger(org_id="org_dead", connection_id="con", source="gmail",
                       mode="incremental", summary=None, error="invalid_grant")
    assert spy.rows == []


# =============================================================================================
# pg — the real ledger, the 90-day payload promise, and tenant erasure
# =============================================================================================
@pytest.fixture
def pg_url(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres qualification tests skipped")
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


def _seed_event(url: str, org_id: str, event_id: str) -> None:
    """One `source_events` row — the parent `raw_payloads.event_id` points at."""
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine
    with get_engine(url).begin() as conn:
        conn.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, dedup_key, actor, occurred_at) "
            "values (:e, :o, 'con_qual', 'gmail', 'email_message', :e, :e, "
            "cast('{}' as jsonb), :at) on conflict (event_id) do nothing"),
            {"e": event_id, "o": org_id, "at": NOW})


@pytest.mark.pg
def test_the_postgres_ledger_round_trips_a_refusal_and_upserts_a_replay(pg_url):
    org = "org_qual_pg"
    _seed_org(pg_url, org)
    ledger = Q.PostgresDropLedger(pg_url)

    outcome = Q.qualify_signals([_scored(900, org_id=org)],
                                floor=_floor(2500, org), eval_time=NOW)
    assert ledger.put(Q.drop_rows(outcome)) == 1
    assert ledger.put(Q.drop_rows(outcome)) == 1, "a replay must upsert, not append"

    rows = ledger.list(org)
    assert len(rows) == 1
    row = rows[0]
    assert row.importance_bp == 900 and row.floor_bp == 2500
    assert row.components == COMPONENTS, "jsonb round-trip lost or reshaped the components"
    assert row.payload_ref == "prepared_content:pc_kestrel_01"
    assert row.retain_until == NOW + timedelta(days=90)
    assert ledger.get(org, row.drop_id) == row
    assert ledger.get("org_qual_pg_other", row.drop_id) is None, "the read crossed a tenant"
    assert ledger.list(org, event_id="evt_1") == rows
    assert ledger.list(org, event_id="evt_nope") == []


@pytest.mark.pg
def test_filing_a_drop_extends_the_payload_it_points_at_to_ninety_days(pg_url):
    """Doc 06's "PAYLOAD RETAINED 90d". An emitted event's body is kept 30 days; a ledger row
    that outlived its payload would be a receipt for something nobody can fetch — which is a
    worse answer to "why did I never see X?" than no row at all, because it looks like one."""
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine

    org = "org_qual_ttl"
    _seed_org(pg_url, org)
    engine = get_engine(pg_url)
    short = NOW + timedelta(days=30)
    with engine.begin() as conn:
        conn.execute(text("delete from raw_payloads where org_id=:o"), {"o": org})
        # `raw_payloads.event_id` has a real FK to `source_events`, so the body is seeded the
        # way the pipeline seeds it: an event first, then its payload. Faking the FK away would
        # test an UPDATE that could never run against the real schema.
        _seed_event(pg_url, org, "evt_1")
        conn.execute(text(
            "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, "
            "expires_at) values (:id, :o, :ev, 'text/plain', 'x', :exp)"),
            {"id": "pay_qual_1", "o": org, "ev": "evt_1", "exp": short})

    outcome = Q.qualify_signals([_scored(900, org_id=org)], floor=_floor(2500, org),
                                eval_time=NOW)
    Q.PostgresDropLedger(pg_url).put(Q.drop_rows(outcome))

    with engine.connect() as conn:
        expires = conn.execute(text(
            "select expires_at from raw_payloads where id='pay_qual_1'")).scalar()
    assert expires == NOW + timedelta(days=90), (
        "the drop row promises 90 days of payload; nothing extended the TTL")


@pytest.mark.pg
def test_the_postgres_floor_store_writes_the_floor_and_its_changelog_together(pg_url):
    org = "org_qual_floor"
    _seed_org(pg_url, org)
    store = Q.PostgresFloorStore(pg_url)

    assert store.get(org) is None
    assert Q.resolve_floor(org, store).origin == "default"

    store.set(org, 2000, owner="rohit@genios.ai", changed_by="rohit@genios.ai", at=NOW,
              reason="pilot tuning")
    store.set(org, 4500, owner="rohit@genios.ai", changed_by="pratap@genios.ai",
              at=NOW + timedelta(days=3), reason="too much noise reaching L2")

    floor = store.get(org)
    assert floor.floor_bp == 4500 and floor.origin == "tenant" and floor.owner == "rohit@genios.ai"
    history = store.history(org)
    assert [(c.from_bp, c.to_bp) for c in history] == [(2000, 4500), (None, 2000)]
    assert history[0].changed_by == "pratap@genios.ai"


@pytest.mark.pg
def test_deleting_the_tenant_takes_the_floor_the_changelog_and_every_drop_with_it(pg_url):
    """The ledger holds the tenant's own subject keys and the components computed from their
    amounts — a record of what we decided NOT to show them, which is still their data. Proven
    against a real cascade, not against the erasure list alone."""
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine

    org = "org_qual_erase"
    _seed_org(pg_url, org)
    Q.PostgresFloorStore(pg_url).set(org, 3000, owner="rohit@genios.ai",
                                     changed_by="rohit@genios.ai", at=NOW)
    Q.PostgresDropLedger(pg_url).put(Q.drop_rows(Q.qualify_signals(
        [_scored(900, org_id=org)], floor=_floor(3000, org), eval_time=NOW)))

    engine = get_engine(pg_url)
    counts = lambda conn: tuple(conn.execute(text(  # noqa: E731
        f"select count(*) from {t} where org_id=:o"), {"o": org}).scalar()
        for t in (Q.DROP_TABLE, Q.FLOOR_TABLE, Q.FLOOR_CHANGE_TABLE))

    with engine.connect() as conn:
        assert counts(conn) == (1, 1, 1)
    with engine.begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": org})
    with engine.connect() as conn:
        assert counts(conn) == (0, 0, 0)


def test_the_three_tables_are_on_the_tenant_erasure_list():
    """`api/account_routes._ORG_SCOPED_TABLES` executes with no try/except, so a table missing
    from it leaks on /reset even when the account-deletion cascade would have caught it."""
    from genios_engine.api import account_routes

    for table in (Q.DROP_TABLE, Q.FLOOR_TABLE, Q.FLOOR_CHANGE_TABLE):
        assert table in account_routes._ORG_SCOPED_TABLES, f"{table} leaks on tenant reset"


# =============================================================================================
# ONE EVENT, ONE INSTANT, ONE SCORE — the double-scoring defect.
#
# The score used to be computed TWICE. `pipeline.run_esqe_stage` scores every signal at capture,
# against that event's own frozen instant, and puts the result on `CaptureResult.esqe.importance`
# — the number the trace row and the QES carry. `scored_signals_for` then ignored it and scored
# the signal AGAIN, against `sweep_eval_time(summary)`, and the drop ledger filed THAT.
#
# Two instants, so genuinely two numbers: a deadline that crossed a rung of ALG-17's ladder
# between the event's moment and the sweep's moment scores differently, and the ledger row then
# explains a refusal with an importance that contradicts the one stored on the event it refused.
# Which of the two a founder is shown depends on which table they were shown from.
# =============================================================================================
def _scored_esqe(signal, *, importance_bp: int, at: datetime) -> "_Esqe":
    """One signal WITH the score the pipeline already gave it, at the pipeline's own instant."""
    return _Esqe(normalized=(signal,),
                 importance=(ImportanceScore(importance_bp=importance_bp,
                                             components=_components(at),
                                             importance_version="alg17-pipeline"),))


def _summary_with_pipeline_scores(*pairs, prepared: str | None = "pc_1") -> "_Summary":
    return _Summary(results=[
        _Result(event=_Event(event_id=signal.event_id, occurred_at=NOW - timedelta(minutes=i)),
                esqe=_scored_esqe(signal, importance_bp=bp, at=at),
                prepared=_Prepared(prepared) if prepared else None)
        for i, (signal, bp, at) in enumerate(pairs)])


def test_the_floor_judges_the_score_the_pipeline_computed_and_never_a_second_one():
    """THE FIX. The sweep's instant and the event's instant are deliberately DIFFERENT here, and
    an injected scorer is deliberately present and deliberately wrong.

    If anything re-scores, the verdict reads 9999 — the recomputed number — instead of 1200,
    which is what `capture_event` actually stamped on the event.
    """
    at_capture = NOW - timedelta(days=3)
    signal = _signal(event_id="evt_1")
    ledger = Q.InMemoryDropLedger()

    outcome = Q.qualify_sweep(_summary_with_pipeline_scores((signal, 1200, at_capture)),
                              org_id=ORG, ledger=ledger, scorer=_fixed_scorer(9999),
                              floor_store=Q.InMemoryFloorStore({ORG: 5000}))

    verdict = outcome.verdicts[0]
    assert verdict.importance_bp == 1200, (
        "the floor judged a number the event does not carry — the score was recomputed")
    assert verdict.importance_version == "alg17-pipeline"
    assert ledger.list(ORG)[0].importance_bp == 1200, (
        "the ledger explains this refusal with a different number from the one on the event")


def test_the_ledger_row_is_stamped_with_the_instant_its_score_was_computed_against():
    """One event, one `eval_time`. The row's `evaluated_at`, the `eval_time` inside its stored
    components, and the 90-day retention it promises must all name the same moment — otherwise
    "why is this an 1200?" is answered against one instant and "when did we decide?" against
    another, and neither can be checked from the other."""
    at_capture = NOW - timedelta(days=3)
    ledger = Q.InMemoryDropLedger()

    Q.qualify_sweep(_summary_with_pipeline_scores((_signal(event_id="evt_1"), 400, at_capture)),
                    org_id=ORG, ledger=ledger, scorer=_fixed_scorer(400),
                    floor_store=Q.InMemoryFloorStore({ORG: 5000}))

    row = ledger.list(ORG)[0]
    assert row.evaluated_at == at_capture, (
        f"the row is stamped {row.evaluated_at.isoformat()} but its score was computed "
        f"against {at_capture.isoformat()}")
    assert row.components["eval_time"] == at_capture.isoformat()
    assert row.retain_until == at_capture + timedelta(days=Q.DROP_PAYLOAD_RETENTION_DAYS)


def test_the_scorer_is_not_called_at_all_for_a_signal_the_pipeline_already_scored():
    """Not merely "the right number wins" — the second computation must not HAPPEN.

    ALG-17 is cheap, so the cost is not the argument; determinism is. A second call is a second
    opportunity for the two to disagree, and a fallback that runs and is then discarded is a
    fallback nobody will notice has started disagreeing.
    """
    calls: list = []

    def _counting(signal, baseline, *, eval_time):
        calls.append(signal.event_id)
        return ImportanceScore(importance_bp=9999, components=_components(eval_time),
                               importance_version="alg17-test")

    Q.qualify_sweep(_summary_with_pipeline_scores((_signal(event_id="evt_1"), 1200, NOW)),
                    org_id=ORG, scorer=_counting,
                    floor_store=Q.InMemoryFloorStore({ORG: 5000}))

    assert calls == [], f"ALG-17 ran a second time for {calls}"


def test_a_summary_that_carries_no_scores_still_reaches_the_scorer():
    """The fallback stays live. A caller whose summary predates ALG-17's pipeline wiring — or a
    test pinning a number — must still get a qualification rather than a silent pass."""
    outcome = Q.qualify_sweep(_summary(_signal(event_id="evt_1")), org_id=ORG,
                              scorer=_fixed_scorer(1200),
                              floor_store=Q.InMemoryFloorStore({ORG: 5000}))
    assert outcome.dropped and outcome.verdicts[0].importance_bp == 1200


def test_a_naive_instant_is_refused_by_the_floor_rather_than_written_to_a_timestamptz():
    """`retain_until` and `evaluated_at` are `timestamptz` columns. A naive datetime reaching
    them is interpreted in the SERVER's timezone, so the 90-day payload promise silently becomes
    89 or 91 days and the drop's `evaluated_at` disagrees with the score's own `eval_time` by an
    offset nobody recorded."""
    with pytest.raises(ValueError, match="timezone-aware"):
        Q.qualify_signals([_scored(1200)], floor=_floor(5000),
                          eval_time=datetime(2026, 4, 2, 9, 0))


# =============================================================================================
# THE WEBHOOK DOOR — it must qualify the way the sweep door does.
#
# The sweep qualifies at `api/routes._run_ledger`, the hook every `run_sync` caller passes. The
# push door had no equivalent, so a tenant whose source is webhook-driven — which is the
# always-on lane, the one a customer actually experiences — had NO answer to "why did I never
# see this?", while the same tenant's polled sources had one. Same message, two doors, one of
# them keeping a record.
# =============================================================================================
_PUSH_PROSE = "The $84K fee is due and the cancellation window closes on 26 January 2026."


def _push_payload() -> dict:
    def cite(quote: str) -> list[dict]:
        start = _PUSH_PROSE.index(quote)
        return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]

    return {"intent": "inform", "stance": "neutral",
            "amounts": [{"minor_units": 8_400_000, "currency": "USD", "as_written": "$84K"}],
            "dates_mentioned": [{"as_written": "26 January 2026",
                                 "evidence": cite("26 January 2026")}]}


def _push_once(fake_llm, *, floor_bp: int | None, ledger):
    from genios_engine.capture import pipeline as P
    from genios_engine.capture.connectors.base import RawObject
    from genios_engine.capture.connectors.push_ingest import (PushIngestWiring,
                                                              ingest_pushed_objects)
    from genios_engine.capture.landing.repository import InMemorySourceEventRepository

    raw = RawObject(source="gmail", object_type="email_message", source_object_id="m_push",
                    occurred_at=NOW, actor_email="cfo@northwind.com",
                    recipients=("founder@genios.ai",),
                    raw={"subject": "Renewal", "body": _PUSH_PROSE})
    wiring = PushIngestWiring(
        repo=InMemorySourceEventRepository(), mailbox_owner="founder@genios.ai",
        semantic=P.SemanticLane(llm=fake_llm(_push_payload()), eval_time=NOW),
        esqe=P.EsqeStage(eval_time=NOW),
        floor_store=None if floor_bp is None else Q.InMemoryFloorStore({ORG: floor_bp}),
        drop_ledger=ledger)
    return ingest_pushed_objects((raw,), org_id=ORG, connection_id="con_push", wiring=wiring)


def test_the_webhook_door_qualifies_its_signals_and_files_what_the_floor_refused(fake_llm):
    """WIRING. A pushed message goes in; a `qualification_drops` row comes out of the tenant's
    ledger, carrying the components ALG-17 computed at capture."""
    ledger = Q.InMemoryDropLedger()
    outcome = _push_once(fake_llm, floor_bp=10000, ledger=ledger)

    assert outcome.primary is not None and outcome.primary.outcome == "emitted"
    assert outcome.qualification is not None, "the push door qualified nothing"
    assert outcome.qualification.dropped, "a floor of 10000 refused nothing"
    rows = ledger.list(ORG)
    assert rows, "the push door decided a refusal and left no record of it"
    assert rows[0].components["baseline_basis"], "the row lost ALG-17's components"
    assert rows[0].payload_ref, "the row lost its payload ref, so the drop is not reconstructable"


def test_the_webhook_door_keeps_what_clears_the_tenants_floor(fake_llm):
    """The other half of the wire: the same message under a floor of zero is filed nowhere."""
    ledger = Q.InMemoryDropLedger()
    outcome = _push_once(fake_llm, floor_bp=0, ledger=ledger)

    assert outcome.qualification is not None and outcome.qualification.qualified
    assert outcome.qualification.dropped == ()
    assert ledger.list(ORG) == []


def test_a_push_door_with_no_floor_wired_reports_no_qualification_rather_than_an_empty_one(
        fake_llm):
    """`None` and "an outcome with no verdicts" are different facts. A caller that wired no
    ledger has decided nothing, and reporting an empty `QualificationOutcome` would read as
    "nothing was refused" — which is the sentence a missing wire must not be able to produce."""
    assert _push_once(fake_llm, floor_bp=None, ledger=None).qualification is None


def test_the_push_door_and_the_sweep_door_hand_the_floor_the_same_shaped_input(fake_llm):
    """Parity, at the seam rather than by inspection: both doors reach `qualify_sweep` with an
    object carrying `.results`, and the verdict a push produces is the same shape the sweep's
    is — same signal id derivation, same components, same payload-ref form."""
    outcome = _push_once(fake_llm, floor_bp=10000, ledger=Q.InMemoryDropLedger())
    verdict = outcome.qualification.dropped[0]

    assert verdict.signal_id.startswith("sig_")
    assert verdict.payload_ref.startswith(("prepared_content:", "raw_payload:"))
    assert verdict.org_id == ORG
    assert verdict.evaluated_at == NOW, (
        "the push door judged against something other than the event's own frozen instant")
