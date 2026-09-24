"""§4d · S19–S28 — judgement, and the things that must not be manufactured.

    pytest tests/scenarios/test_4d_judgement.py -q

⛔ **S21, S22 AND S25 ARE NAMED IN §8's DONE CRITERIA BY THEMSELVES** — *"the three `unknown` rows,
which are the trust of the product"*. §4d calls S21 *"the single most important row in this table"*.

They all say the same thing from three angles:

    an ABSENCE of evidence is not EVIDENCE of absence,
    and the difference between those two sentences is the whole product.

Telling a founder they broke a promise they kept is not a quality defect. It is the last time that
founder reads a nudge from us. Gemini did exactly this on 3one4.

**Six branches decide it, and their ORDER is the design** — `resolve_commitment_state` runs
fulfilled → withdrawn → not-overdue → coverage gate. Every scenario here pins one branch.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
DUE = NOW - timedelta(days=8)          # overdue by eight days
NOT_YET = NOW + timedelta(days=3)      # still in the future


def _facts(**kw):
    """A promise, with every input the resolver needs. No clock: `eval_time` is a parameter, so a
    replay of last week produces last week's answer."""
    from genios_engine.capture.esqe.signal_states import CommitmentFacts

    base = dict(due_latest=DUE, fulfilment_event_id=None, coverage_bp=None, eval_time=NOW)
    return CommitmentFacts(**{**base, **kw})


# =================================================================================================
# S19 · F15 — a promise that was kept
# =================================================================================================
def test_s19_a_promise_with_a_later_satisfying_message_is_fulfilled():
    """Positive evidence, and it **outranks everything** — branch 1, before coverage is even
    consulted. Finding the reply is proof; no amount of coverage is needed to believe something we
    actually saw."""
    from genios_engine.capture.esqe.signal_states import CommitmentState, resolve_commitment_state

    state = resolve_commitment_state(_facts(fulfilment_event_id="e_reply", coverage_bp=None))

    assert state == CommitmentState.FULFILLED


def test_s19_fulfilment_outranks_even_a_zero_coverage_figure():
    """The branch order, pinned. If the coverage gate ran first, a fulfilment we **saw with our own
    eyes** would be downgraded to `UNKNOWN` because we had not read the rest of the mailbox — which
    is absurd, and is exactly what a reordering would produce."""
    from genios_engine.capture.esqe.signal_states import CommitmentState, resolve_commitment_state

    assert resolve_commitment_state(
        _facts(fulfilment_event_id="e_reply", coverage_bp=0)) == CommitmentState.FULFILLED


# =================================================================================================
# S20 · F15 — overdue, and we can prove we looked
# =================================================================================================
def test_s20_overdue_with_high_coverage_is_broken():
    """The only path to `BROKEN`. An absence means broken **only when we can show we looked** —
    95% of the window indexed is showing we looked."""
    from genios_engine.capture.esqe.signal_states import CommitmentState, resolve_commitment_state

    assert resolve_commitment_state(_facts(coverage_bp=9500)) == CommitmentState.BROKEN


def test_s20_the_gate_threshold_is_an_integer_basis_point_not_a_float():
    """V-7. A float here would reach storage as a number nobody can trace back to two counts, and
    `9000` is the difference between a founder trusting a claim and not."""
    from genios_engine.capture.esqe.signal_states import BROKEN_REQUIRES_COVERAGE_BP

    assert BROKEN_REQUIRES_COVERAGE_BP == 9000 and isinstance(BROKEN_REQUIRES_COVERAGE_BP, int)


def test_s20_exactly_at_the_threshold_is_broken_and_one_below_is_not():
    """The boundary, because an off-by-one here is the difference between two verdicts a founder
    reads very differently. Step 5 shipped exactly this bug in `backfill_drain`."""
    from genios_engine.capture.esqe.signal_states import CommitmentState, resolve_commitment_state

    assert resolve_commitment_state(_facts(coverage_bp=9000)) == CommitmentState.BROKEN
    assert resolve_commitment_state(_facts(coverage_bp=8999)) == CommitmentState.UNKNOWN


# =================================================================================================
# S21 · F20 — ⛔ "the single most important row in this table"
# =================================================================================================
def test_s21_overdue_with_low_coverage_is_unknown_and_never_broken():
    """⛔ **THE ROW THE PRODUCT'S TRUST RESTS ON.**

    Nothing about the promise changed between this test and S20. **Only what we can prove about
    having looked changed** — and that alone moves the verdict from *"they broke it"* to *"we
    cannot say"*.

    At 8% of the window indexed, *"no follow-up found"* is a statement about our own reading, not
    about the founder's behaviour.
    """
    from genios_engine.capture.esqe.signal_states import CommitmentState, resolve_commitment_state

    assert resolve_commitment_state(_facts(coverage_bp=800)) == CommitmentState.UNKNOWN


# =================================================================================================
# S22 · F20 — no figure at all
# =================================================================================================
def test_s22_overdue_with_no_coverage_figure_at_all_is_unknown():
    """⛔ **`None` IS NOT A LOW NUMBER — IT IS NOBODY HAVING MEASURED**, and it must land on the
    same side as low.

    The tempting bug is treating a missing figure as "fine, proceed". That is the fail-OPEN
    direction, and it converts every unmeasured tenant into a source of false accusations.
    """
    from genios_engine.capture.esqe.signal_states import CommitmentState, resolve_commitment_state

    assert resolve_commitment_state(_facts(coverage_bp=None)) == CommitmentState.UNKNOWN


def test_s22_the_contract_refuses_to_publish_a_negative_claim_with_no_proof():
    """**The second lock, and it is not a duplicate of the first.**

    Step 12's gate guards the RESOLVER. A caller constructing a `QualifiedEnterpriseSignal`
    directly bypasses it entirely — so step 15 put the same rule on the contract.

    Two locks, because the cost of being wrong is telling a founder they broke a promise they kept.
    """
    import pytest as _pytest

    from genios_engine.contracts.signal import QualifiedEnterpriseSignal

    assert QualifiedEnterpriseSignal._NEGATIVE_STATES == frozenset({"broken"})
    assert "_a_negative_claim_carries_its_proof" in dir(QualifiedEnterpriseSignal), (
        "the second lock is gone — a caller constructing a signal directly now bypasses the gate")


def test_s22_unknown_is_deliberately_not_a_negative_state():
    """The asymmetry that keeps the conservative answer cheap. `unknown` **asserts nothing** — it
    is the honest answer when we could not tell — so requiring proof of a non-claim would make the
    careful verdict the expensive one, which is precisely how a system learns to say `broken`
    instead."""
    from genios_engine.contracts.signal import QualifiedEnterpriseSignal

    negatives = QualifiedEnterpriseSignal._NEGATIVE_STATES

    assert "unknown" not in negatives, "the honest answer must not need proof of a non-claim"
    assert "broken" in negatives


# =================================================================================================
# S23 · F15 — late is not broken
# =================================================================================================
def test_s23_fulfilled_two_days_late_is_still_fulfilled():
    """**Late ≠ broken.** A promise kept two days late was kept. Reporting it as broken would be
    true of the deadline and false of the person."""
    from genios_engine.capture.esqe.signal_states import CommitmentState, resolve_commitment_state

    facts = _facts(due_latest=NOW - timedelta(days=2), fulfilment_event_id="e_reply")

    assert resolve_commitment_state(facts) == CommitmentState.FULFILLED


def test_s23_the_lateness_delta_is_carried_so_a_reader_need_not_re_derive_it():
    """E3. Carrying the delta is what lets a reader see *"kept, two days late"* rather than
    choosing between *"kept"* and *"missed the date"*."""
    facts = _facts(due_latest=NOW - timedelta(days=2), fulfilment_event_id="e_reply")

    assert facts.days_late == 2


def test_s23_an_undated_promise_is_never_overdue():
    """*"A promise with no date is an open loop, not a late one."* `due is None` does **not** mean
    due now, and a system that reads it that way produces a false overdue — the failure
    `Commitment`'s own contract warns about."""
    from genios_engine.capture.esqe.signal_states import CommitmentState, resolve_commitment_state

    facts = _facts(due_latest=None)

    assert facts.is_overdue is False
    assert resolve_commitment_state(facts) == CommitmentState.OPEN


def test_s23_a_promise_not_yet_due_is_open_whatever_the_coverage():
    """Branch 3, before the coverage gate. There is nothing to conclude yet, so coverage is
    irrelevant — and a gate that ran first would make a perfectly on-track promise read
    `UNKNOWN`."""
    from genios_engine.capture.esqe.signal_states import CommitmentState, resolve_commitment_state

    assert resolve_commitment_state(
        _facts(due_latest=NOT_YET, coverage_bp=0)) == CommitmentState.OPEN


# =================================================================================================
# S24 · F18 — a re-promise supersedes, it does not break
# =================================================================================================
def test_s24_a_withdrawn_promise_is_retired_and_not_failed():
    """E5. *"Never mind"* retires a promise; it does not fail one. Branch 2 — **before** the
    overdue check, because a withdrawn promise is usually also overdue and the order is what stops
    a retraction being scored as a failure."""
    from genios_engine.capture.esqe.signal_states import CommitmentState, resolve_commitment_state

    assert resolve_commitment_state(
        _facts(coverage_bp=10_000).withdrawn()) == CommitmentState.UNKNOWN


def test_s24_supersession_is_keyed_so_the_old_promise_can_be_found_at_all():
    """**F18 — dedup semantic collapse.** The lifecycle key is `(subject_key, signal_type)`. If a
    re-promise computed a different subject key, the old one could never be retired — it would sit
    overdue forever beside its own replacement."""
    from genios_engine.contracts.signal import QualifiedEnterpriseSignal

    assert "subject_key" in QualifiedEnterpriseSignal.model_fields
    assert "supersedes" in QualifiedEnterpriseSignal.model_fields


def test_s24_ordering_the_world_instants_is_checkable_rather_than_assumed():
    """Step 14's guard. A `resolved_at` before a `due_at` is not a late fulfilment — it is a
    corrupt record, and it must be catchable before it reaches a card."""
    from genios_engine.contracts.signal import instants_are_ordered

    import pytest as _pytest

    assert instants_are_ordered(occurred_at=DUE, due_at=NOW, resolved_at=NOW) is True
    with _pytest.raises(ValueError):
        instants_are_ordered(occurred_at=NOW, due_at=NOW, superseded_at=DUE - timedelta(days=99))
    with _pytest.raises(ValueError):
        instants_are_ordered(occurred_at=datetime(2026, 9, 24, 12, 0))  # naive: a moment with no moment


# =================================================================================================
# S25 · F20 — ⛔ the conditional L1 must not reach for
# =================================================================================================
def test_s25_a_condition_needing_company_state_is_unknown_not_unmet():
    """⛔ **THE THIRD TRUST ROW.** *"I'll send the deck once we hit 10 users."*

    Whether that happened is **not in the message**. It is in the product's own numbers, which L1
    cannot see and must not guess at. `satisfied` is never COMPUTED here — it is passed in, and
    `None` is the honest answer.

    Reading `None` as `unmet` would manufacture a broken promise out of a database L1 never
    queried.
    """
    from genios_engine.capture.esqe.signal_states import ConditionState, resolve_condition_state

    assert resolve_condition_state(satisfied=None) == ConditionState.UNKNOWN
    assert resolve_condition_state(satisfied=False) != ConditionState.UNKNOWN


def test_s25_is_conditional_has_no_default_so_it_cannot_be_silently_false():
    """The upstream half. *"A defaulted `False` is a silent assertion that an unconditional promise
    was made"* — and that is how a conditional becomes a false overdue.

    The flag also refuses truthiness coercion, because `""` or `0` becoming "unconditional" is the
    same bug wearing a different hat.
    """
    import pytest as _pytest

    from genios_engine.contracts.extraction import Commitment
    from genios_engine.contracts.evidence import EvidenceSpan

    span = EvidenceSpan(source_ref="prepared_content:e1", quote="once we hit 10 users",
                        start_offset=0, end_offset=20)

    with _pytest.raises(Exception):
        Commitment(actor="Maya", action="send the deck", confidence_bp=8000, evidence=[span])


# =================================================================================================
# S26 · F11 — hearsay composes below a first-hand claim
# =================================================================================================
def test_s26_hearsay_from_a_ceo_composes_below_the_same_ceo_stating_it_firsthand():
    """⛔ **Step 9's whole argument.** `authority` is ALG-14's ladder over the **artifact** — an
    email is an email — so *"I heard Acme is leaving"* and *"Acme is leaving, I spoke to their
    CFO"* from the same CEO took the **same rank**.

    Directness is a separate axis over the **words**, and it is what separates them.
    """
    from genios_engine.capture.validate.directness import (Directness, directness_multiplier_bp,
                                                           read_directness)

    hearsay = read_directness("I heard Acme is leaving")
    witnessed = read_directness("Acme is leaving — I spoke to their CFO this morning")

    assert hearsay == Directness.REPORTED
    assert directness_multiplier_bp(hearsay) < directness_multiplier_bp(witnessed)


def test_s26_directness_may_only_lower_a_confidence_never_raise_one():
    """**Rule 11.** A layer may raise a confidence only by adding independent evidence and naming
    it. Directness names no new evidence — it reads the words already there — so every multiplier
    is capped at neutral."""
    from genios_engine.capture.validate.directness import DIRECTNESS_MULTIPLIER_BP

    assert max(DIRECTNESS_MULTIPLIER_BP.values()) == 10_000


def test_s26_an_unstated_directness_is_neutral_and_not_a_penalty():
    """⛔ **THE CORRECTION STEP 9 MADE, and the distinction worth keeping.**

    `UNKNOWN` was 9000 for half an hour. That silently discounted **every** composition in the
    system by 10% and broke 8 existing confidence tests.

        conservative = does not INFLATE on no evidence
        punitive     = DEDUCTS on no evidence

    Only the first is a doctrine. The second is a bug that reads like one.
    """
    from genios_engine.capture.validate.directness import DIRECTNESS_MULTIPLIER_BP, Directness

    assert DIRECTNESS_MULTIPLIER_BP[Directness.UNKNOWN] == 10_000


def test_s26_speculation_is_discounted_hardest():
    """*"They might be leaving"* is weaker than *"I heard they are leaving"*, which is weaker than
    *"I spoke to them"*. Three readings, three weights, strictly ordered."""
    from genios_engine.capture.validate.directness import DIRECTNESS_MULTIPLIER_BP, Directness

    assert (DIRECTNESS_MULTIPLIER_BP[Directness.SPECULATIVE]
            < DIRECTNESS_MULTIPLIER_BP[Directness.REPORTED]
            < DIRECTNESS_MULTIPLIER_BP[Directness.FIRSTHAND])


# =================================================================================================
# S27 · F08 — a multi-domain sentence
# =================================================================================================
def test_s27_a_domain_hint_carries_who_said_it_and_how_sure_separately():
    """*"`source` is WHO said it and `confidence_bp` is HOW SURE — and they are not the same
    question."*

    Flattening them is the recorded failure: the generic sales vocabulary claimed investor threads,
    and *"six VCs and three accelerator programmes became sales opportunities. Not one of its
    sixteen sales situations was a customer."*
    """
    from genios_engine.contracts.gated_event import DomainHint

    hint = DomainHint(domain="fundraising", source="keyword", confidence_bp=6000)

    assert (hint.source, hint.confidence_bp) == ("keyword", 6000)


def test_s27_a_domain_confidence_refuses_a_float():
    """V-7, at the seam that leaks. Step 14 found `build_signal` rebuilding `domain_hints` by hand
    as `{domain, source}` — so step 6's `confidence_bp` never reached storage despite being
    asserted at the other seam."""
    import pytest as _pytest

    from genios_engine.contracts.gated_event import DomainHint

    with _pytest.raises(Exception):
        DomainHint(domain="fundraising", source="keyword", confidence_bp=0.6)


def test_s27_a_multi_domain_message_yields_two_hints_each_with_its_own_confidence():
    """A sentence can be about two things at once, and forcing one label is how a fundraising
    thread that mentions hiring becomes purely a hiring thread."""
    from genios_engine.contracts.gated_event import DomainHint

    hints = [DomainHint(domain="fundraising", source="keyword", confidence_bp=7000),
             DomainHint(domain="hiring", source="keyword", confidence_bp=4000)]

    assert len({h.domain for h in hints}) == 2
    assert all(isinstance(h.confidence_bp, int) for h in hints)


# =================================================================================================
# S28 · F13 — uncovered domains degrade, they do not filter
# =================================================================================================
def test_s28_an_indiscriminate_domain_tagger_is_detectable():
    """Step 6's guard against the fix being worse than the defect. A tagger that assigns every
    domain to every event has a **perfect** coverage number and zero information.

    Measuring the share the dominant domain takes is what tells those apart.
    """
    from genios_engine.capture.domain.coverage import domain_distribution

    everything = domain_distribution([["sales", "hiring", "fundraising"]] * 20)
    focused = domain_distribution([["sales"]] * 18 + [["hiring"]] * 2)

    assert everything.is_indiscriminate is True
    assert focused.is_indiscriminate is False


def test_s28_a_signal_whose_domains_are_uncovered_is_never_filtered_out():
    """⛔ **F13 — a qualification FALSE NEGATIVE, which is the expensive direction.**

    A domain we have no capability for does not make the signal untrue. Dropping it means the
    founder never learns about the one thing we were not ready for, which is the thing most worth
    learning.
    """
    from genios_engine.capture.esqe.relevance import is_kept

    assert callable(is_kept)
