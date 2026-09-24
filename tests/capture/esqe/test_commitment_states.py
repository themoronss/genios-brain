"""Step 12 · did the promise get kept — and the difference between BROKEN and UNKNOWN.

    pytest tests/capture/esqe/test_commitment_states.py -q

P2 is the prompt Layer 1 is strongest on, and this is the half it cannot answer. Step 11's harness
scores it **7 of 9**, with both misses classed `not_carried`: `fulfilment_link` and
`commitment_state`.

`esqe/lifecycle.py` ALG-19 has four generic states — `active` / `superseded` / `expired` /
`resolved` — and that machine is correct: supersession keyed on `(subject_key, signal_type)`,
authority-gated, world-time ordered. **But it is one machine for sixteen signal types**, and a
commitment needs words it does not have.

⛔ **E1 IS THE WHOLE STEP, and everything else here is scaffolding around it:**

> *"No fulfilment evidence found → `UNKNOWN`, **never `BROKEN`**, unless coverage over the window
> is high enough to make absence meaningful."*

Claude's benchmark run marked four promises **Broken** — correctly, because it could read nearly
the whole sent folder. On a mailbox where coverage is 8%, **the identical absence means UNKNOWN**.

> **Telling a founder they broke a promise they actually kept is worse than saying nothing.**
> An absence of evidence is evidence of absence only when you can prove you looked.

That is Gemini's *"18 threads of 18 that exist"* one level down: a conclusion drawn from a
denominator nobody checked. Step 5 built the denominator; this step is the first consumer that
would be dangerous without it.

**THE PREDICTION THAT DEFINES SUCCESS** (§3): on the pilot, most commitments must land in
`UNKNOWN`. *"If most land in `BROKEN`, the coverage gate is not wired and the step has produced a
confident lie."*
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


# =============================================================================================
# 12-U1 + 12-U2 · the vocabulary, as DATA, validated at import
# =============================================================================================
def test_a_commitment_has_its_own_states():
    """`active`/`superseded`/`expired`/`resolved` cannot say *"the promise was kept"*. Four words
    for sixteen types is four words too few for this one."""
    from genios_engine.capture.esqe.signal_states import CommitmentState

    assert {s.value for s in CommitmentState} == {"open", "fulfilled", "broken", "unknown"}


def test_the_per_type_map_is_validated_at_import():
    """12-U2, on the same terms as `ImportanceWeights`' sum-to-10000 check: a map that could be
    half-filled is a map where a type silently falls back to a vocabulary that cannot describe it.

    Import-time, not test-time, so the failure is at startup rather than in whichever test happens
    to touch the type first."""
    from genios_engine.capture.esqe.signal_states import STATES_FOR_TYPE, states_for

    from genios_engine.contracts.signal import SignalType

    for member in SignalType:
        assert states_for(member), f"{member.name} resolves to no state vocabulary"
    assert STATES_FOR_TYPE, "the map is empty"


def test_every_other_type_keeps_the_four_generic_states():
    """T8 — THE REGRESSION GUARD, and §9's *"do not build a second state machine"*.

    ALG-19 is correct and careful. This step adds WORDS for three types; it does not replace the
    machine, and every other type must come back byte-identical.
    """
    from genios_engine.capture.esqe.signal_states import states_for
    from genios_engine.contracts.signal import SIGNAL_STATES, SignalType

    assert states_for(SignalType.RISK_FLAGGED) == SIGNAL_STATES
    assert states_for(SignalType.ESCALATION) == SIGNAL_STATES
    assert states_for(SignalType.ANOMALY) == SIGNAL_STATES


def test_the_three_types_that_need_their_own_words_have_them():
    """A conditional trigger and an availability window are the other two the step names. Their
    vocabularies are different from each other and from a commitment's — folding them would be the
    same mistake as using the generic four."""
    from genios_engine.capture.esqe.signal_states import states_for
    from genios_engine.contracts.signal import SignalType

    assert states_for(SignalType.COMMITMENT_MADE) == {"open", "fulfilled", "broken", "unknown"}
    assert states_for(SignalType.AVAILABILITY_CHANGE) == {"active", "ended", "unknown"}


# =============================================================================================
# ⛔ E1 · THE COVERAGE GATE — the single most important rule in this step
# =============================================================================================
def _promise(*, due_days: int = -3, fulfilled: bool = False, coverage_bp: int | None = None):
    """One commitment as the resolver sees it: a deadline, a fulfilment link or not, and what we
    know about how much of the window we could actually read."""
    from genios_engine.capture.esqe.signal_states import CommitmentFacts

    return CommitmentFacts(
        due_latest=NOW + timedelta(days=due_days),
        fulfilment_event_id="evt_later" if fulfilled else None,
        coverage_bp=coverage_bp,
        eval_time=NOW)


def test_an_overdue_promise_with_low_coverage_is_UNKNOWN_not_broken():
    """T3 — **THE CASE THAT MATTERS, AND THE REASON THIS STEP EXISTS.**

    The deadline passed and we found nothing. On a mailbox where we read 8% of the window, that
    absence says nothing at all about the promise — it says something about us.

    Claude marked four promises Broken on a corpus it had nearly all of, and was right. The same
    inference on this corpus would be a confident lie, and the founder on the other end of it has
    no way to know.
    """
    from genios_engine.capture.esqe.signal_states import CommitmentState, resolve_commitment_state

    assert resolve_commitment_state(_promise(coverage_bp=800)) is CommitmentState.UNKNOWN


def test_an_overdue_promise_with_high_coverage_is_broken():
    """T2, and the SENSITIVITY that keeps the rule honest. A gate that returned `UNKNOWN` for
    everything would satisfy the row above and make the state useless — *"we never say broken"* is
    not caution, it is silence.

    Absence of evidence IS evidence of absence, once you can show you looked.
    """
    from genios_engine.capture.esqe.signal_states import CommitmentState, resolve_commitment_state

    assert resolve_commitment_state(_promise(coverage_bp=9500)) is CommitmentState.BROKEN


def test_no_coverage_figure_at_all_is_UNKNOWN():
    """T4 / E2. *"A state asserted without a denominator is Gemini's 18-of-18."*

    `None` is not zero and not a reason to guess: it means nobody measured, and the honest state
    for "we did not look at whether we looked" is `unknown`.
    """
    from genios_engine.capture.esqe.signal_states import CommitmentState, resolve_commitment_state

    assert resolve_commitment_state(_promise(coverage_bp=None)) is CommitmentState.UNKNOWN


def test_the_threshold_is_a_named_constant_and_high():
    """The gate is only as good as where it sits. It must be HIGH — a 50% threshold would let a
    coin-flip corpus accuse people — and it must be findable, because it is the number an operator
    will want to argue with."""
    from genios_engine.capture.esqe.signal_states import BROKEN_REQUIRES_COVERAGE_BP

    assert BROKEN_REQUIRES_COVERAGE_BP >= 9000


# =============================================================================================
# The rest of the state table
# =============================================================================================
def test_a_promise_whose_deadline_has_not_passed_is_open():
    """Not overdue, not fulfilled, and nothing to conclude yet. `OPEN` is the only honest answer
    and it does not depend on coverage at all."""
    from genios_engine.capture.esqe.signal_states import CommitmentState, resolve_commitment_state

    assert resolve_commitment_state(
        _promise(due_days=+5, coverage_bp=9500)) is CommitmentState.OPEN


def test_a_fulfilled_promise_is_fulfilled_whatever_the_coverage():
    """T1. Finding the evidence is a POSITIVE observation: it does not depend on how much else we
    read, because we are not reasoning from an absence. The coverage gate guards one direction
    only, and a gate that also suppressed `FULFILLED` would be caution applied where there is
    nothing to be cautious about."""
    from genios_engine.capture.esqe.signal_states import CommitmentState, resolve_commitment_state

    assert resolve_commitment_state(
        _promise(fulfilled=True, coverage_bp=100)) is CommitmentState.FULFILLED


def test_fulfilled_late_is_fulfilled_and_the_delta_is_recorded():
    """E3. **Late is not broken.** A system that conflated them would tell a founder they failed at
    something they did, three days after they did it — and the delta is what lets a reader see the
    difference without re-deriving it."""
    from genios_engine.capture.esqe.signal_states import CommitmentState, resolve_commitment_state

    facts = _promise(due_days=-2, fulfilled=True, coverage_bp=9500)
    assert resolve_commitment_state(facts) is CommitmentState.FULFILLED
    assert facts.days_late == 2


def test_a_low_certainty_deadline_is_not_overdue_until_its_far_end_passes():
    """E9. *"Sometime next week"* is a RANGE, and ALG-09 already stores its certainty and its far
    end. Calling a promise broken on the near end of a range the speaker never committed to is
    inventing a deadline — the failure `Commitment`'s own contract warns about: *"an invented
    deadline must not be able to produce a false overdue."*
    """
    from genios_engine.capture.esqe.signal_states import CommitmentState, resolve_commitment_state

    not_yet = _promise(due_days=+1, coverage_bp=9500)
    assert resolve_commitment_state(not_yet) is CommitmentState.OPEN


def test_a_withdrawn_promise_is_not_broken():
    """E5. *"Never mind"* retires a promise; it does not fail one. Reporting it as BROKEN would
    punish somebody for a conversation that went well."""
    from genios_engine.capture.esqe.signal_states import (CommitmentState,
                                                          resolve_commitment_state)

    facts = _promise(coverage_bp=9500)
    facts = facts.withdrawn()

    assert resolve_commitment_state(facts) is not CommitmentState.BROKEN


# =============================================================================================
# 12-U4 / 12-U5 · the machine commits, the model only proposes
# =============================================================================================
def test_a_fulfilment_link_must_come_after_the_promise():
    """12-U4. A "fulfilment" dated before the promise is not one, and a link the machine did not
    check is a link a model asserted."""
    from genios_engine.capture.esqe.signal_states import is_valid_fulfilment

    assert is_valid_fulfilment(promised_at=NOW, event_at=NOW + timedelta(hours=1)) is True
    assert is_valid_fulfilment(promised_at=NOW, event_at=NOW - timedelta(hours=1)) is False


def test_the_resolver_takes_no_model_and_reads_no_clock():
    """§9: *"Do not let the model commit a transition."* It proposes the fulfilment candidate; the
    machine decides legality. And `eval_time` is a parameter — a resolver that read a clock could
    not be replayed, and a replay of last week must produce last week's answer."""
    import inspect

    from genios_engine.capture.esqe import signal_states

    source = inspect.getsource(signal_states)
    for forbidden in ("datetime.now", "utcnow", "llm", "LLMClient", "requests"):
        assert forbidden not in source, f"`{forbidden}` in the state machine"


def test_layer_one_does_not_evaluate_a_condition_against_company_state():
    """T7 / E8 — the boundary in §9. *"Do not evaluate a condition against company state — that
    needs the graph, and the graph is Layer 2's. L1 says the condition exists and that its
    satisfaction is UNKNOWN."*"""
    from genios_engine.capture.esqe.signal_states import ConditionState, resolve_condition_state

    assert resolve_condition_state(satisfied=None) is ConditionState.UNKNOWN


def test_the_extraction_cache_fingerprint_is_untouched():
    """Lifecycle and state resolution are post-extraction and deterministic. No prompt, no cost."""
    from genios_engine.capture.semantic.vocabulary import vocabulary_fingerprint

    assert vocabulary_fingerprint() == "a3d5496aa0d3"


# =============================================================================================
# The correction six Layer 2 tests forced — a vocabulary EXTENDS, it never replaces
# =============================================================================================
def test_a_commitment_can_still_be_active():
    """⛔ THE ROW THAT EXISTS BECAUSE I GOT THIS WRONG.

    The first version of `STATES_FOR_TYPE` listed only the fulfilment words for a commitment.
    **Six Layer 2 tests went red immediately**, including
    `test_every_lifecycle_state_the_contract_allows_can_be_built[active]`, and they were right:
    **every commitment signal ever stored carries `state="active"`**, so a vocabulary that
    excluded it would have refused the entire existing corpus at the contract on deploy day.

    The reason is not backward compatibility — it is that these are TWO AXES sharing one column:

        lifecycle    active · superseded · expired · resolved   has this signal been REPLACED?
        fulfilment   open · fulfilled · broken · unknown        was the PROMISE kept?

    A commitment is legitimately `active` (nothing superseded it) AND legitimately `fulfilled`
    (the promise was kept). §9's *"do not build a second state machine"* is what a union honours
    and a replacement does not.
    """
    from genios_engine.contracts.signal import SIGNAL_STATES, states_for_type

    for signal_type in ("commitment_made", "commitment_due", "availability_change"):
        legal = states_for_type(signal_type)
        assert SIGNAL_STATES <= legal, (
            f"{signal_type} dropped a generic lifecycle state — every stored signal of this type "
            f"carries one, and the contract would now refuse them all")


def test_a_word_from_another_types_vocabulary_is_still_refused():
    """SENSITIVITY, and the reason the per-type check exists at all.

    Widening `_known_state` to the union of every vocabulary was necessary — a field validator on
    `state` alone cannot see `signal_type` — but on its own it would let `availability_change`
    carry `broken`: a word from another type's vocabulary, legal-looking and meaningless.

    `_state_belongs_to_this_type` is the model validator that catches it, and this row is what
    stops someone deleting it as redundant.
    """
    from genios_engine.contracts.signal import states_for_type

    assert "broken" not in states_for_type("availability_change")
    assert "fulfilled" not in states_for_type("escalation")
    assert "ended" not in states_for_type("commitment_made")


def test_the_contract_refuses_a_state_that_is_legal_for_no_type():
    """The cheap first rung — the one a typo produces. `fulfiled` is nobody's vocabulary."""
    from genios_engine.contracts.signal import _ALL_STATES

    assert "fulfiled" not in _ALL_STATES
    assert {"active", "fulfilled", "broken", "ended", "unknown"} <= _ALL_STATES
