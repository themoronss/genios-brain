"""L1.6.9-U1 (ALG-19) · the signal lifecycle state machine.

Doc 06's four acceptance lines are the spine of this file:

    # supersede sets both sides' pointers
    # a lower-authority newer signal does NOT supersede a higher-authority older one
    # expiry is computed from the signal's own date fields, not from ingest time
    # revive creates a new signal id and does not mutate the expired row

and the task's five, which are about the MACHINE rather than the rules it encodes: every legal
transition one row each, every illegal one refused with a NAMED reason, a chain A -> B -> C that
resolves to C with no way back to A, an expiry that replays identically from `eval_time`, a
resolved signal that cannot silently reactivate, and a table that is exhaustive over the state
set rather than permissive by default.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.esqe import lifecycle as L
from genios_engine.capture.esqe.normalize import NormalizedSignal
from genios_engine.capture.esqe.source_analyzer import ActorBasis, SourceAttribution
from genios_engine.capture.validate.authority import AuthorityBasis, AuthorityWeight
from genios_engine.contracts.conflict import Authority
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import ExtractionResult
from genios_engine.contracts.signal import (SIGNAL_STATES, QualifiedEnterpriseSignal, SignalType)
from genios_engine.contracts.units import DateCertainty, ResolvedDate
from genios_engine.contracts.visibility import Visibility

NOW = datetime(2026, 4, 2, 9, 0, tzinfo=timezone.utc)
ORG = "org_lifecycle"

E = L.LifecycleEvent
R = L.RefusalReason


# =============================================================================================
# factories — real contract objects, never stand-ins
# =============================================================================================
def _span(ref: str = "prepared_content:p1") -> EvidenceSpan:
    return EvidenceSpan(source_ref=ref, quote="Kestrel", start_offset=0, end_offset=7,
                        verified=True)


def _attribution(rank: Authority = Authority.EMAIL_PROSE) -> SourceAttribution:
    return SourceAttribution(
        evidence=AuthorityWeight(authority=rank, basis=AuthorityBasis.OBJECT_TYPE),
        actor_authority_bp=6000, actor_basis=ActorBasis.ROLE_LADDER,
        actor_email="cfo@kestrel.example")


def _normalized(*, event_id: str = "evt_1", occurred_at: datetime | None = None,
                signal_type: SignalType = SignalType.CONTRACT_RENEWAL,
                subject_key: str = "org:kestrel",
                authority: Authority = Authority.EMAIL_PROSE,
                primary_date: ResolvedDate | None = None,
                org_id: str = ORG) -> NormalizedSignal:
    return NormalizedSignal(
        org_id=org_id, event_id=event_id, source="gmail", object_type="email_message",
        occurred_at=occurred_at or (NOW - timedelta(hours=3)),
        visibility=Visibility(scope="org", derived_from="source:gmail"),
        recipients=("ops@genios.ai",), internal_kind=None,
        signal_type=signal_type, predicate="renewal_window_open",
        subject_key=subject_key, subject_label="Kestrel MSA renewal",
        primary_entity="Kestrel Systems", primary_date=primary_date, primary_amount=None,
        evidence_refs=(_span(),), attribution=_attribution(authority))


def _resolved_date(latest: datetime, earliest: datetime | None = None) -> ResolvedDate:
    return ResolvedDate(as_written="on 30 June", earliest=earliest or latest, latest=latest,
                        certainty=DateCertainty.EXACT if earliest is None
                        else DateCertainty.RANGE,
                        resolved_against=NOW, evidence=[_span()])


def _record(signal_id: str, *, state: str = L.ACTIVE, rank: int = 3,
            occurred_at: datetime | None = None, supersedes: str | None = None,
            expires_at: datetime | None = None, subject_key: str = "org:kestrel",
            signal_type: str = SignalType.CONTRACT_RENEWAL.value,
            org_id: str = ORG) -> L.LifecycleRecord:
    return L.LifecycleRecord(
        org_id=org_id, signal_id=signal_id, subject_key=subject_key, signal_type=signal_type,
        authority_rank=rank, occurred_at=occurred_at or (NOW - timedelta(days=1)), state=state,
        supersedes=supersedes,
        expires_at=expires_at if expires_at is not None or state != L.EXPIRED
        else NOW - timedelta(days=1),
        evaluated_at=NOW)


def _qes(signal_id: str = "sig_1", *, state: str = L.ACTIVE, supersedes: str | None = None,
         expires_at: datetime | None = None,
         signal_type: SignalType = SignalType.CONTRACT_RENEWAL) -> QualifiedEnterpriseSignal:
    return QualifiedEnterpriseSignal(
        org_id=ORG, trace_id="trace_alg19", visibility=Visibility(), signal_id=signal_id,
        event_id="evt_alg19", source="gmail", object_type="email_message",
        occurred_at=NOW - timedelta(days=1), signal_type=signal_type, importance_bp=7800,
        triage_lane="P1",
        extraction=ExtractionResult(intent="inform", stance="neutral",
                                    model_snapshot="claude-3-5-haiku-20241022",
                                    prompt_version="l1.s2.email.v3", schema_version="l1.v2.0",
                                    extraction_profile="email", input_tokens=10,
                                    output_tokens=5),
        evidence_refs=[_span()], conflicts=[], confidence_bp=6200,
        confidence_vector={"evidence": 6200, "expertise": 6200, "freshness": 6200,
                           "coverage": 6200},
        coverage_ready=True, state=state, supersedes=supersedes, expires_at=expires_at,
        internal_kind=None, recipients=("rohit@antler.co",),
        versions={"prompt": "l1.s2.email.v3", "schema": "l1.v2.0"})


# =============================================================================================
# THE TABLE — exhaustive by construction, illegal by default
# =============================================================================================
def test_the_table_answers_every_state_crossed_with_every_event():
    """Totality is the whole safety argument: a lookup that can MISS is a lookup with a default,
    and the default of a state machine nobody wrote a row for is "allowed"."""
    expected = {(state, event) for state in SIGNAL_STATES for event in E}
    assert set(L.TRANSITIONS) == expected
    assert L.unruled_pairs(SIGNAL_STATES) == ()
    assert len(L.TRANSITIONS) == len(SIGNAL_STATES) * len(E) == 16


def test_a_state_added_to_the_enum_without_a_rule_fails_rather_than_defaulting(monkeypatch):
    """The task's hardest line. A fifth state in `contracts.signal.SIGNAL_STATES` must break
    something LOUDLY, not quietly acquire permissive behaviour.

    Three assertions, because there are three ways it could go quiet: the coverage check could
    not see it, the table build could accept it, and the runtime lookup could fall through.
    """
    widened = SIGNAL_STATES | {"archived"}
    assert L.unruled_pairs(widened) == tuple(
        sorted((("archived", event) for event in E), key=lambda p: p[1].value)), (
        "the coverage check did not notice a state with no rules")

    monkeypatch.setattr(L, "SIGNAL_STATES", widened)
    with pytest.raises(ValueError, match="not exhaustive"):
        L._build_transitions()

    with pytest.raises(L.UnknownLifecycleState):
        L.evaluate("archived", E.EXPIRE)


def test_a_rule_cannot_both_allow_and_refuse_and_must_say_why():
    with pytest.raises(ValueError, match="exactly one of allowed"):
        L.TransitionRule(L.ACTIVE, E.EXPIRE, L.EXPIRED, R.ALREADY_EXPIRED, "both")
    with pytest.raises(ValueError, match="exactly one of allowed"):
        L.TransitionRule(L.ACTIVE, E.EXPIRE, None, None, "neither")
    with pytest.raises(ValueError, match="states why"):
        L.TransitionRule(L.ACTIVE, E.EXPIRE, L.EXPIRED, None, "")


def test_the_terminal_states_are_derived_from_the_table_and_not_listed_beside_it():
    assert L.TERMINAL_STATES == {L.SUPERSEDED, L.EXPIRED, L.RESOLVED}
    assert L.ACTIVE not in L.TERMINAL_STATES


# =============================================================================================
# EVERY LEGAL TRANSITION — one row each
# =============================================================================================
@pytest.mark.parametrize(
    "from_state, event, to_state, creates_new",
    [
        (L.ACTIVE, E.SUPERSEDE, L.SUPERSEDED, False),
        (L.ACTIVE, E.EXPIRE, L.EXPIRED, False),
        (L.ACTIVE, E.RESOLVE, L.RESOLVED, False),
        # Doc 06's fourth: a revive is legal ON an expired signal and moves it nowhere — the
        # answer is a NEW row, which is why `creates_new_signal` is part of the rule.
        (L.EXPIRED, E.REVIVE, L.EXPIRED, True),
    ],
)
def test_every_legal_transition(from_state, event, to_state, creates_new):
    rule = L.evaluate(from_state, event)
    assert rule.allowed and rule.to_state == to_state
    assert rule.creates_new_signal is creates_new
    assert L.can(from_state, event) is True
    assert L.require(from_state, event) is rule


def test_the_legal_transitions_are_exactly_four():
    """Doc 06: `active -> superseded | expired | resolved`, plus revive's new-row rule. Any
    fifth legal cell is a route into `active` that ALG-19 does not have."""
    allowed = {(state, event) for (state, event), rule in L.TRANSITIONS.items() if rule.allowed}
    assert allowed == {(L.ACTIVE, E.SUPERSEDE), (L.ACTIVE, E.EXPIRE), (L.ACTIVE, E.RESOLVE),
                       (L.EXPIRED, E.REVIVE)}
    assert not any(rule.to_state == L.ACTIVE for rule in L.TRANSITIONS.values()), (
        "nothing may transition INTO active — that is what revive's new row exists to avoid")


# =============================================================================================
# EVERY ILLEGAL TRANSITION — refused with a NAMED reason
# =============================================================================================
@pytest.mark.parametrize(
    "from_state, event, reason",
    [
        (L.ACTIVE, E.REVIVE, R.REVIVE_REQUIRES_EXPIRED),
        (L.SUPERSEDED, E.SUPERSEDE, R.ALREADY_SUPERSEDED),
        (L.SUPERSEDED, E.EXPIRE, R.TERMINAL_STATE),
        (L.SUPERSEDED, E.RESOLVE, R.TERMINAL_STATE),
        (L.SUPERSEDED, E.REVIVE, R.REVIVE_REQUIRES_EXPIRED),
        (L.EXPIRED, E.SUPERSEDE, R.TERMINAL_STATE),
        (L.EXPIRED, E.EXPIRE, R.ALREADY_EXPIRED),
        (L.EXPIRED, E.RESOLVE, R.TERMINAL_STATE),
        (L.RESOLVED, E.SUPERSEDE, R.ALREADY_RESOLVED),
        (L.RESOLVED, E.EXPIRE, R.ALREADY_RESOLVED),
        (L.RESOLVED, E.RESOLVE, R.ALREADY_RESOLVED),
        (L.RESOLVED, E.REVIVE, R.REVIVE_REQUIRES_EXPIRED),
    ],
)
def test_every_illegal_transition_is_refused_with_a_named_reason(from_state, event, reason):
    assert L.can(from_state, event) is False
    with pytest.raises(L.IllegalTransition) as caught:
        L.require(from_state, event, signal_id="sig_x")
    assert caught.value.reason is reason, "a refusal must NAME its cause, not return False"
    assert caught.value.why, "every refusal carries the prose a human reads at 3am"
    assert "sig_x" in str(caught.value) and reason.value in str(caught.value)


def test_the_twelve_illegal_and_four_legal_cells_account_for_the_whole_table():
    refused = {key for key, rule in L.TRANSITIONS.items() if not rule.allowed}
    assert len(refused) == 12
    assert all(L.TRANSITIONS[key].refusal is not None for key in refused)


def test_a_refused_transition_never_writes_a_state_on_the_record():
    record = _record("sig_a", state=L.RESOLVED)
    with pytest.raises(L.IllegalTransition):
        L.advance(record, E.EXPIRE, eval_time=NOW)
    assert record.state == L.RESOLVED, "the record was mutated by a refused transition"


# =============================================================================================
# THE RESOLVED SIGNAL — no silent reactivation, at the contract object too
# =============================================================================================
@pytest.mark.parametrize("event", list(E))
def test_a_resolved_signal_cannot_reactivate_through_any_event(event):
    signal = _qes(state=L.RESOLVED)
    with pytest.raises(L.IllegalTransition):
        L.apply_to_signal(signal, event, eval_time=NOW)
    assert signal.state == L.RESOLVED and signal.is_live is False


def test_a_resolved_signal_cannot_be_revived_into_a_replacement_either():
    """The other door into reactivation: not a state write, but a new signal claiming to
    succeed a closed loop. Doc 06 gives revive one source state, and it is `expired`."""
    with pytest.raises(L.IllegalTransition) as caught:
        L.revive(_qes("sig_closed", state=L.RESOLVED), _qes("sig_new"))
    assert caught.value.reason is R.REVIVE_REQUIRES_EXPIRED


# =============================================================================================
# THE CONTRACT OBJECT — C-12's own three fields, written through the machine
# =============================================================================================
def test_a_transition_on_a_signal_goes_through_c12s_validators_rather_than_around_them():
    """`apply_to_signal` ASSIGNS, because C-12 is `validate_assignment=True` and
    `model_copy(update=...)` skips validators. This asserts the validator actually runs."""
    signal = _qes()
    L.apply_to_signal(signal, E.RESOLVE, eval_time=NOW)
    assert signal.state == L.RESOLVED
    with pytest.raises(Exception):
        signal.state = "closed"


def test_expiring_a_signal_writes_the_clock_before_the_state():
    """C-12 refuses `expired` with no `expires_at`. The order is the unit's problem, not the
    caller's — a caller that got it wrong would see a validation error about a field it did set."""
    signal = _qes(expires_at=None)
    L.apply_to_signal(signal, E.EXPIRE, eval_time=NOW, expires_at=NOW - timedelta(days=1))
    assert signal.state == L.EXPIRED and signal.expires_at == NOW - timedelta(days=1)


def test_a_signal_whose_clock_has_not_run_out_cannot_be_expired():
    signal = _qes(expires_at=NOW + timedelta(days=1))
    with pytest.raises(ValueError, match="after eval_time"):
        L.apply_to_signal(signal, E.EXPIRE, eval_time=NOW)
    assert signal.state == L.ACTIVE


def test_a_signal_with_no_clock_at_all_cannot_be_expired():
    with pytest.raises(ValueError, match="carries no expires_at"):
        L.apply_to_signal(_qes(expires_at=None), E.EXPIRE, eval_time=NOW)


def test_the_pointer_is_written_on_the_new_signal_and_never_on_the_old_one():
    """The direction decision, asserted where it is observable. `supersedes` on the OLD signal
    would be the forward reading; this module picked backward and says so in one place."""
    with pytest.raises(ValueError, match="belongs on the NEW signal"):
        L.apply_to_signal(_qes("sig_old"), E.SUPERSEDE, eval_time=NOW, supersedes="sig_new")


# =============================================================================================
# REVIVE — a new row, and the expired one untouched
# =============================================================================================
def test_revive_creates_a_new_signal_id_and_does_not_mutate_the_expired_row():
    """Doc 06's fourth acceptance line, in full."""
    expired = _qes("sig_old", state=L.EXPIRED, expires_at=NOW - timedelta(days=2))
    before = expired.model_dump(mode="json")

    replacement = L.revive(expired, _qes("sig_new"))

    assert replacement.signal_id == "sig_new" and replacement.supersedes == "sig_old"
    assert replacement.state == L.ACTIVE
    assert expired.model_dump(mode="json") == before, "the expired row was mutated"


def test_a_revive_that_reuses_the_expired_signals_id_is_refused():
    expired = _qes("sig_old", state=L.EXPIRED, expires_at=NOW - timedelta(days=2))
    with pytest.raises(ValueError, match="NEW signal id"):
        L.revive(expired, _qes("sig_old"))


def test_reviving_through_the_signal_api_names_the_replacement_seam():
    """`apply_to_signal(..., REVIVE)` is the mistake a caller makes once: it looks like the way
    to revive and is a write to the wrong row. It is refused by name."""
    expired = _qes("sig_old", state=L.EXPIRED, expires_at=NOW - timedelta(days=2))
    with pytest.raises(L.IllegalTransition, match="never writes to the old signal"):
        L.apply_to_signal(expired, E.REVIVE, eval_time=NOW)
    assert expired.state == L.EXPIRED


# =============================================================================================
# THE CHAIN — A -> B -> C resolves to C, and A stays dead
# =============================================================================================
def _chain() -> tuple[L.LifecycleRecord, ...]:
    a = _record("sig_a", state=L.SUPERSEDED, occurred_at=NOW - timedelta(days=3))
    b = _record("sig_b", state=L.SUPERSEDED, occurred_at=NOW - timedelta(days=2),
                supersedes="sig_a")
    c = _record("sig_c", state=L.ACTIVE, occurred_at=NOW - timedelta(days=1), supersedes="sig_b")
    return a, b, c


def test_a_supersession_chain_resolves_to_its_head():
    a, b, c = _chain()
    assert L.resolve_chain([a, b, c]).signal_id == "sig_c"
    assert L.resolve_chain([a, b, c], "sig_a").signal_id == "sig_c"
    assert L.resolve_chain([a, b, c], b).signal_id == "sig_c"
    assert L.resolve_chain([c]).signal_id == "sig_c", "a chain of one is already current"


def test_the_head_of_the_chain_is_the_only_live_row():
    a, b, c = _chain()
    assert [r.signal_id for r in (a, b, c) if r.is_live] == ["sig_c"]


@pytest.mark.parametrize("event", list(E))
def test_a_cannot_be_revived_through_b(event):
    """The task's sharpest line. Every route back into A is refused, and the refusals are
    named: A is superseded, and a superseded signal is not revivable, expirable or resolvable —
    its subject moved forward two rows ago."""
    a, _b, _c = _chain()
    with pytest.raises(L.IllegalTransition) as caught:
        L.advance(a, event, eval_time=NOW)
    assert caught.value.reason in {R.ALREADY_SUPERSEDED, R.TERMINAL_STATE,
                                   R.REVIVE_REQUIRES_EXPIRED}
    assert a.state == L.SUPERSEDED


def test_a_forked_chain_is_an_error_and_not_a_silent_pick():
    a, b, c = _chain()
    fork = replace(c, signal_id="sig_c2")
    with pytest.raises(ValueError, match="forked"):
        L.resolve_chain([a, b, c, fork])


def test_a_cycle_in_the_chain_raises_rather_than_looping():
    a = _record("sig_a", occurred_at=NOW - timedelta(days=2), supersedes="sig_b")
    b = _record("sig_b", occurred_at=NOW - timedelta(days=1), supersedes="sig_a")
    with pytest.raises(ValueError, match="cycle"):
        L.resolve_chain([a, b])


def test_a_record_may_not_supersede_itself():
    with pytest.raises(ValueError, match="supersede itself"):
        _record("sig_a", supersedes="sig_a")


# =============================================================================================
# EXPIRY — doc 06's windows, from the signal's OWN dates, replayed against eval_time
# =============================================================================================
@pytest.mark.parametrize(
    "signal_type, window",
    [
        (SignalType.COMMITMENT_DUE, 30),
        (SignalType.DEADLINE_STATED, 30),
        (SignalType.CONTRACT_RENEWAL, 30),
        (SignalType.DECISION_PENDING, 90),
        (SignalType.COMMITMENT_MADE, 180),
        (SignalType.DECISION_MADE, 180),
        (SignalType.APPROVAL_REQUESTED, 180),
        (SignalType.FINANCIAL_OBLIGATION, 180),
        (SignalType.RISK_FLAGGED, 180),
        (SignalType.OPPORTUNITY_SIGNAL, 180),
        (SignalType.RELATIONSHIP_CHANGE, 180),
        (SignalType.INFORMATION_CONFLICT, 180),
        (SignalType.ESCALATION, 180),
        (SignalType.ANOMALY, 180),
        # Not doc 06: member fifteen. Short, because the durable record is the L2 fact.
        (SignalType.AVAILABILITY_CHANGE, 30),
    ],
)
def test_doc_06s_expiry_window_for_every_signal_type(signal_type, window):
    """All fifteen, because "others -> 180d" is only checkable by naming the others."""
    assert L.expiry_window_days(signal_type) == window
    plan = L.plan_expiry(signal_type, occurred_at=NOW)
    assert plan.expires_at == NOW + timedelta(days=window)


@pytest.mark.parametrize(
    "signal_type, stated, expected_basis, expected_days",
    [
        # a dated type with a stated date measures from THE DATE
        (SignalType.CONTRACT_RENEWAL, NOW + timedelta(days=60), L.ExpiryBasis.STATED_DATE, 60),
        (SignalType.COMMITMENT_DUE, NOW + timedelta(days=5), L.ExpiryBasis.STATED_DATE, 5),
        (SignalType.DEADLINE_STATED, NOW - timedelta(days=10), L.ExpiryBasis.STATED_DATE, -10),
        # a dated type whose date the resolver could not pin falls back, and RECORDS that it did
        (SignalType.CONTRACT_RENEWAL, None, L.ExpiryBasis.OCCURRED_AT, 0),
        # an undated type ignores a stated date entirely — its window is 90d from the event
        (SignalType.DECISION_PENDING, NOW + timedelta(days=60), L.ExpiryBasis.OCCURRED_AT, 0),
    ],
)
def test_expiry_is_measured_from_the_signals_own_dates(signal_type, stated, expected_basis,
                                                       expected_days):
    plan = L.plan_expiry(signal_type, occurred_at=NOW,
                         stated_date=_resolved_date(stated) if stated else None)
    assert plan.basis is expected_basis
    assert plan.basis_at == NOW + timedelta(days=expected_days)
    assert plan.expires_at == plan.basis_at + timedelta(days=plan.window_days)
    assert plan.explain().startswith(signal_type.value)


def test_an_ambiguous_date_expires_from_its_LATEST_bound():
    """Stale beats wrong, and the grace period must not be shortened by ambiguity: expiring
    "sometime in Q3" at the start of Q3 kills a live signal."""
    window = _resolved_date(NOW + timedelta(days=90), earliest=NOW + timedelta(days=30))
    plan = L.plan_expiry(SignalType.CONTRACT_RENEWAL, occurred_at=NOW, stated_date=window)
    assert plan.basis_at == NOW + timedelta(days=90)


def test_expiry_is_not_measured_from_ingest_time():
    """Doc 06's third acceptance line, as the behaviour that proves it: the same signal swept
    today and swept in six months expires at the same instant, because nothing in this call
    reads a clock. `eval_time` is not even an argument to the plan."""
    old_event = NOW - timedelta(days=200)
    plan = L.plan_expiry(SignalType.COMMITMENT_MADE, occurred_at=old_event)
    assert plan.expires_at == old_event + timedelta(days=180)
    assert plan.expires_at < NOW, "a 200-day-old signal is already past its 180-day window"


@pytest.mark.parametrize(
    "expires_at, eval_time, expired",
    [
        (NOW - timedelta(seconds=1), NOW, True),
        (NOW, NOW, True),                                   # inclusive: the boundary expires
        (NOW + timedelta(seconds=1), NOW, False),
        (None, NOW, False),                                 # nothing is timing it
    ],
)
def test_the_expiry_comparison_is_a_parameter_and_inclusive(expires_at, eval_time, expired):
    assert L.has_expired(expires_at, eval_time) is expired


def test_expiry_replays_identically_from_the_same_eval_time():
    """Two evaluations of the same sweep at the same instant produce the same states — the
    property the whole layer is built on, checked as a digest rather than by eye."""
    records = [_record("sig_a", expires_at=NOW - timedelta(days=1)),
               _record("sig_b", expires_at=NOW + timedelta(days=1))]
    first = L.apply_expiries(records, eval_time=NOW)
    second = L.apply_expiries(records, eval_time=NOW)
    assert first == second
    assert {r.signal_id: r.state for r in first[1]} == {"sig_a": L.EXPIRED, "sig_b": L.ACTIVE}

    later = L.apply_expiries(records, eval_time=NOW + timedelta(days=2))
    assert {r.signal_id: r.state for r in later[1]} == {"sig_a": L.EXPIRED, "sig_b": L.EXPIRED}, (
        "a later eval_time must expire more, and only through the parameter")


def test_an_expired_record_must_carry_the_clock_it_passed():
    with pytest.raises(ValueError, match="names no clock"):
        L.LifecycleRecord(org_id=ORG, signal_id="s", subject_key="k", signal_type="anomaly",
                          authority_rank=1, occurred_at=NOW, state=L.EXPIRED, supersedes=None,
                          expires_at=None, evaluated_at=NOW)


# =============================================================================================
# SUPERSESSION — doc 06's authority rule, both directions
# =============================================================================================
@pytest.mark.parametrize(
    "newer_rank, older_rank, supersedes",
    [
        (6, 3, True),      # a signed contract retires an email
        (3, 3, True),      # EQUAL rank: doc 06 says >=, and the newer of two emails must win
        (1, 6, False),     # a Slack aside does NOT retire a signed contract
        (2, 3, False),
    ],
)
def test_a_newer_signal_supersedes_only_at_equal_or_higher_authority(newer_rank, older_rank,
                                                                    supersedes):
    older = _record("sig_old", rank=older_rank, occurred_at=NOW - timedelta(days=2))
    newer = _record("sig_new", rank=newer_rank, occurred_at=NOW - timedelta(days=1))
    assert L.supersedes_predecessor(newer, older) is supersedes

    moves, final = L.apply_supersessions([older, newer], eval_time=NOW)
    states = {r.signal_id: (r.state, r.supersedes) for r in final}
    if supersedes:
        assert states == {"sig_old": (L.SUPERSEDED, None), "sig_new": (L.ACTIVE, "sig_old")}
        assert moves[0].caused_by == "sig_new" and moves[0].event is E.SUPERSEDE
    else:
        assert states == {"sig_old": (L.ACTIVE, None), "sig_new": (L.ACTIVE, None)}
        assert moves == ()


def test_supersede_sets_both_sides_and_only_one_of_them_stores_an_id():
    """Doc 06's first acceptance line — *"supersede sets both sides' pointers"* — honoured in
    the direction this module picked: the old row gets the STATE, the new row gets the ID."""
    older = _record("sig_old", occurred_at=NOW - timedelta(days=2))
    newer = _record("sig_new", occurred_at=NOW - timedelta(days=1))
    _moves, final = L.apply_supersessions([older, newer], eval_time=NOW)
    old_after = next(r for r in final if r.signal_id == "sig_old")
    new_after = next(r for r in final if r.signal_id == "sig_new")
    assert old_after.state == L.SUPERSEDED and old_after.supersedes is None
    assert new_after.state == L.ACTIVE and new_after.supersedes == "sig_old"


@pytest.mark.parametrize(
    "subject_key, signal_type",
    [
        ("org:other", SignalType.CONTRACT_RENEWAL.value),           # different subject
        ("org:kestrel", SignalType.DECISION_PENDING.value),         # different type
    ],
)
def test_a_different_subject_or_type_is_a_different_loop(subject_key, signal_type):
    """The key is the PAIR. A renewal does not supersede a pending decision about the same
    customer, and conflating them is how a live open loop silently disappears."""
    older = _record("sig_old", occurred_at=NOW - timedelta(days=2))
    newer = _record("sig_new", occurred_at=NOW - timedelta(days=1),
                    subject_key=subject_key, signal_type=signal_type)
    assert L.supersedes_predecessor(newer, older) is False
    _moves, final = L.apply_supersessions([older, newer], eval_time=NOW)
    assert all(r.state == L.ACTIVE for r in final)


def test_supersession_builds_a_chain_across_three_signals_in_world_time_order():
    records = [_record(f"sig_{n}", occurred_at=NOW - timedelta(days=days))
               for n, days in (("a", 3), ("b", 2), ("c", 1))]
    _moves, final = L.apply_supersessions(list(reversed(records)), eval_time=NOW)
    by_id = {r.signal_id: r for r in final}
    assert by_id["sig_a"].state == L.SUPERSEDED and by_id["sig_b"].state == L.SUPERSEDED
    assert by_id["sig_c"].state == L.ACTIVE
    assert L.resolve_chain(final).signal_id == "sig_c"
    assert by_id["sig_b"].supersedes == "sig_a" and by_id["sig_c"].supersedes == "sig_b"


def test_an_expired_row_is_not_a_supersession_target():
    """Expiry runs first and the row must keep saying it died of its clock. The next live
    signal simply takes over."""
    dead = _record("sig_dead", state=L.EXPIRED, occurred_at=NOW - timedelta(days=2),
                   expires_at=NOW - timedelta(days=1))
    fresh = _record("sig_fresh", occurred_at=NOW - timedelta(days=1))
    moves, final = L.apply_supersessions([dead, fresh], eval_time=NOW)
    assert moves == ()
    assert {r.signal_id: r.state for r in final} == {"sig_dead": L.EXPIRED,
                                                     "sig_fresh": L.ACTIVE}


def test_a_stored_pointer_is_never_rewritten_by_a_later_sweep():
    a = _record("sig_a", occurred_at=NOW - timedelta(days=3))
    b = _record("sig_b", occurred_at=NOW - timedelta(days=2), supersedes="sig_a")
    c = _record("sig_c", occurred_at=NOW - timedelta(days=1))
    _moves, final = L.apply_supersessions([a, b, c], eval_time=NOW)
    by_id = {r.signal_id: r for r in final}
    assert by_id["sig_b"].supersedes == "sig_a", "a historical link was moved"
    assert by_id["sig_c"].supersedes == "sig_b"


# =============================================================================================
# THE SWEEP SEAM — a whole sync's signals, aged and superseded
# =============================================================================================
@dataclass
class _Event:
    event_id: str
    occurred_at: datetime


@dataclass
class _Esqe:
    normalized: tuple


@dataclass
class _Result:
    event: _Event
    esqe: object


@dataclass
class _Summary:
    results: list
    conflicts: object = None


def _summary(*signals) -> _Summary:
    return _Summary(results=[
        _Result(event=_Event(event_id=s.event_id, occurred_at=s.occurred_at), esqe=_Esqe((s,)))
        for s in signals])


def test_the_sweep_files_a_lifecycle_row_per_signal_with_its_expiry_planned():
    store = L.InMemoryLifecycleStore()
    signal = _normalized(occurred_at=NOW - timedelta(days=1))
    outcome = L.sweep_lifecycle(_summary(signal), org_id=ORG, store=store)

    rows = store.list(ORG)
    assert len(rows) == 1 and rows[0].state == L.ACTIVE
    assert rows[0].subject_key == "org:kestrel"
    assert rows[0].expires_at == (NOW - timedelta(days=1)) + timedelta(days=30)
    assert outcome.eval_time == NOW - timedelta(days=1)


def test_the_sweep_supersedes_what_this_tenant_already_holds():
    """The whole reason the row is persisted: today's signal has to be judged against a signal
    captured last month, which is not in memory."""
    store = L.InMemoryLifecycleStore()
    first = _normalized(event_id="evt_1", occurred_at=NOW - timedelta(days=30))
    L.sweep_lifecycle(_summary(first), org_id=ORG, store=store)

    second = _normalized(event_id="evt_2", occurred_at=NOW - timedelta(days=1))
    outcome = L.sweep_lifecycle(_summary(second), org_id=ORG, store=store)

    rows = {r.signal_id: r for r in store.list(ORG)}
    assert len(rows) == 2
    old_id = L.signal_row_id(first)
    new_id = L.signal_row_id(second)
    assert rows[old_id].state == L.SUPERSEDED
    assert rows[new_id].state == L.ACTIVE and rows[new_id].supersedes == old_id
    assert [t.event for t in outcome.transitions] == [E.SUPERSEDE]


def test_the_sweep_expires_a_stored_signal_whose_clock_ran_out():
    store = L.InMemoryLifecycleStore()
    store.put([_record("sig_stale", occurred_at=NOW - timedelta(days=400),
                       expires_at=NOW - timedelta(days=200))])
    fresh = _normalized(event_id="evt_new", subject_key="org:kestrel",
                        occurred_at=NOW - timedelta(days=1))
    outcome = L.sweep_lifecycle(_summary(fresh), org_id=ORG, store=store)

    assert store.get(ORG, "sig_stale").state == L.EXPIRED
    assert [t.event for t in outcome.transitions] == [E.EXPIRE], (
        "an expired row must keep saying it died of its clock, not be relabelled superseded")


def test_a_replayed_sweep_produces_the_identical_lifecycle():
    """Replayability, as a digest over two independent runs of the same input."""
    signals = [_normalized(event_id="evt_1", occurred_at=NOW - timedelta(days=3)),
               _normalized(event_id="evt_2", occurred_at=NOW - timedelta(days=2)),
               _normalized(event_id="evt_3", occurred_at=NOW - timedelta(days=1),
                           subject_key="org:other")]
    first = L.sweep_lifecycle(_summary(*signals), org_id=ORG, store=L.InMemoryLifecycleStore())
    second = L.sweep_lifecycle(_summary(*reversed(signals)), org_id=ORG,
                               store=L.InMemoryLifecycleStore())
    assert L.outcome_digest(first) == L.outcome_digest(second), (
        "the lifecycle depended on the order events arrived in, not on world time")


def test_a_replayed_sweep_upserts_its_own_rows_rather_than_appending_a_second_copy():
    store = L.InMemoryLifecycleStore()
    signal = _normalized()
    L.sweep_lifecycle(_summary(signal), org_id=ORG, store=store)
    L.sweep_lifecycle(_summary(signal), org_id=ORG, store=store)
    assert len(store.list(ORG)) == 1


def test_an_empty_sweep_and_a_failed_sweep_are_both_quiet():
    assert L.sweep_lifecycle(_Summary(results=[]), org_id=ORG).records == ()
    broken = type("Broken", (), {"results": property(lambda self: 1 / 0)})()
    assert L.sweep_lifecycle(broken, org_id=ORG).transitions == ()


def test_the_seam_never_raises_into_the_ingestion_path():
    """A store that is down costs the lifecycle its row, never the tenant their mail."""
    class _Broken:
        def put(self, rows):
            raise RuntimeError("db down")

        def open_for(self, org_id, keys):
            raise RuntimeError("db down")

        def list(self, org_id, subject_key=None):
            return []

        def get(self, org_id, signal_id):
            return None

    assert L.sweep_lifecycle(_summary(_normalized()), org_id=ORG,
                             store=_Broken()).transitions == ()


def test_one_unreadable_signal_does_not_cost_the_others_their_rows():
    good = _normalized(event_id="evt_ok")
    broken = replace(_normalized(event_id="evt_bad"), occurred_at=None)
    rows = L.lifecycle_records_for(_Summary(results=[
        _Result(event=_Event("evt_bad", NOW), esqe=_Esqe((broken,))),
        _Result(event=_Event("evt_ok", NOW), esqe=_Esqe((good,)))]), eval_time=NOW)
    assert [r.signal_id for r in rows] == [L.signal_row_id(good)]


def test_the_lifecycle_row_carries_alg_14s_rank_rather_than_a_second_reading_of_it():
    signed = _normalized(authority=Authority.SIGNED_DOCUMENT)
    chat = _normalized(authority=Authority.CHAT_ASIDE, event_id="evt_chat")
    assert L.record_of_normalized(signed, evaluated_at=NOW).authority_rank == 6
    assert L.record_of_normalized(chat, evaluated_at=NOW).authority_rank == 1


def test_a_qualified_signals_record_ranks_from_its_own_provenance():
    record = L.record_of(_qes(), subject_key="org:kestrel", evaluated_at=NOW)
    assert record.signal_id == "sig_1" and record.state == L.ACTIVE
    assert record.authority_rank == L.record_of(_qes(), subject_key="org:kestrel",
                                                evaluated_at=NOW, executed=True).authority_rank - 4


# =============================================================================================
# WIRED — driven from `api/routes._run_ledger`, the request-path hook every run_sync uses
# =============================================================================================
def test_the_request_path_hook_ages_the_tenants_signals(monkeypatch):
    """WIRING. Nothing here calls `sweep_lifecycle`, `apply_supersessions` or the machine: a
    summary goes into `api/routes._run_ledger` — the hook every `run_sync` caller in the HTTP
    layer passes as `run_ledger=` — and a superseded row comes out of the tenant's store.

    This is the test that separates "a unit exists" from "a unit runs in production".
    """
    from genios_engine.api import routes

    store = L.InMemoryLifecycleStore()
    monkeypatch.setattr(routes, "_lifecycle_store", store)
    monkeypatch.setattr(routes, "_graph", None)      # the sync ledger is a different subsystem

    old = _normalized(event_id="evt_old", occurred_at=NOW - timedelta(days=20), org_id="org_wire")
    new = _normalized(event_id="evt_new", occurred_at=NOW - timedelta(days=1), org_id="org_wire")

    routes._run_ledger(org_id="org_wire", connection_id="con", source="gmail",
                       mode="incremental", summary=_summary(old))
    routes._run_ledger(org_id="org_wire", connection_id="con", source="gmail",
                       mode="incremental", summary=_summary(new))

    rows = {r.signal_id: r for r in store.list("org_wire")}
    assert len(rows) == 2, "the request-path hook did not file the sweep's lifecycle"
    assert rows[L.signal_row_id(old)].state == L.SUPERSEDED
    assert rows[L.signal_row_id(new)].supersedes == L.signal_row_id(old)


def test_the_request_path_hook_expires_a_stale_signal_of_this_tenant(monkeypatch):
    from genios_engine.api import routes

    store = L.InMemoryLifecycleStore()
    store.put([_record("sig_stale", org_id="org_stale", occurred_at=NOW - timedelta(days=400),
                       expires_at=NOW - timedelta(days=300))])
    monkeypatch.setattr(routes, "_lifecycle_store", store)
    monkeypatch.setattr(routes, "_graph", None)

    routes._run_ledger(org_id="org_stale", connection_id="con", source="gmail",
                       mode="incremental",
                       summary=_summary(_normalized(event_id="evt_s", org_id="org_stale",
                                                    occurred_at=NOW - timedelta(days=1))))
    assert store.get("org_stale", "sig_stale").state == L.EXPIRED


def test_a_total_sync_failure_reports_no_lifecycle_rather_than_crashing(monkeypatch):
    """`_run_ledger` is also the FAILURE reporter — `summary=None` when a connector never
    returned a batch. There is nothing to age and nothing may explode."""
    from genios_engine.api import routes

    store = L.InMemoryLifecycleStore()
    monkeypatch.setattr(routes, "_lifecycle_store", store)
    monkeypatch.setattr(routes, "_graph", None)
    routes._run_ledger(org_id="org_dead", connection_id="con", source="gmail",
                       mode="incremental", summary=None, error="invalid_grant")
    assert store.list("org_dead") == []


def test_the_hook_still_files_when_the_l2_graph_store_is_absent(monkeypatch):
    """The early return in `_run_ledger` is about the sync LEDGER. Two unrelated subsystems must
    not share one off-switch — the defect D8 already had to fix once for conflicts."""
    from genios_engine.api import routes

    store = L.InMemoryLifecycleStore()
    monkeypatch.setattr(routes, "_lifecycle_store", store)
    monkeypatch.setattr(routes, "_graph", None)
    routes._run_ledger(org_id="org_nograph", connection_id="con", source="gmail",
                       mode="incremental",
                       summary=_summary(_normalized(event_id="evt_ng", org_id="org_nograph")))
    assert len(store.list("org_nograph")) == 1


# =============================================================================================
# pg — the real store and tenant erasure
# =============================================================================================
@pytest.fixture
def pg_url(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres lifecycle tests skipped")
    return live_db_url


def _seed_org(url: str, org_id: str) -> None:
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine
    with get_engine(url).begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": org_id})
        cols = conn.execute(text(
            "select column_name, data_type from information_schema.columns "
            "where table_name='orgs'")).all()
        names = {c.column_name for c in cols}
        payload = {"id": org_id}
        if "name" in names:
            payload["name"] = "lifecycle test"
        if "email" in names:
            payload["email"] = f"{org_id}@example.test"
        columns = ", ".join(payload)
        values = ", ".join(f":{k}" for k in payload)
        conn.execute(text(f"insert into orgs ({columns}) values ({values})"), payload)


def test_the_postgres_store_round_trips_a_lifecycle_and_upserts_a_replay(pg_url):
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine
    org = "org_lc_pg"
    _seed_org(pg_url, org)
    store = L.PostgresLifecycleStore(pg_url)

    a = _record("sig_a", org_id=org, occurred_at=NOW - timedelta(days=2))
    b = _record("sig_b", org_id=org, occurred_at=NOW - timedelta(days=1))
    _moves, final = L.apply_supersessions([a, b], eval_time=NOW)
    assert store.put(final) == 2

    assert store.get(org, "sig_a").state == L.SUPERSEDED
    assert store.get(org, "sig_b").supersedes == "sig_a"
    assert [r.signal_id for r in store.open_for(org, [("org:kestrel",
                                                       SignalType.CONTRACT_RENEWAL.value)])
            ] == ["sig_b"]

    store.put(final)      # the replay
    assert len(store.list(org)) == 2

    with get_engine(pg_url).begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": org})
    assert store.list(org) == [], "the lifecycle rows did not leave with their tenant"


def test_the_table_refuses_a_state_outside_the_closed_set(pg_url):
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine
    org = "org_lc_check"
    _seed_org(pg_url, org)
    engine = get_engine(pg_url)
    with pytest.raises(Exception):
        with engine.begin() as conn:
            conn.execute(text(
                "insert into signal_lifecycle (org_id, signal_id, subject_key, signal_type, "
                "authority_rank, occurred_at, state, evaluated_at) values "
                "(:o, 'sig_x', 'k', 'anomaly', 1, :t, 'dead', :t)"), {"o": org, "t": NOW})
    with engine.begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": org})
