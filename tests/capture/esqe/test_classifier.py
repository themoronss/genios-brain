"""G6 · ALG-16, L1.6.3-U1 — primary type selection over the closed taxonomy.

    pytest tests/capture/esqe -q

Doc 06's acceptance line for this unit is one sentence: *"an event firing 4 predicates gets
exactly one `signal_type` and 3 `secondary_types`, deterministically, in two separate runs."*
Everything here is that sentence taken literally, plus the two properties that make it hold —
the order is a CONSTANT and it is TOTAL over the 14-member taxonomy.

Why totality is asserted rather than assumed: `contracts/signal.py` says a fifteenth member
added without touching ALG-16 is "a type that can be classified and then scored as if it were
nothing in particular". A missing member would sort as unknown, silently outranking or
under-ranking everything, and the failure would surface as a mis-ordered card months later.
"""

from __future__ import annotations

import pytest

from genios_engine.capture.esqe.classifier import (PRECEDENCE, classify_signals, precedence_rank)
from genios_engine.contracts.signal import SignalType

T = SignalType

#: Doc 06's order, retyped from the plan document rather than imported, so this file DISAGREES
#: with `classifier.py` if either is edited alone. Importing the constant and asserting it equals
#: itself would be a test that cannot fail.
DOC_ORDER = [
    "information_conflict", "escalation", "approval_requested", "contract_renewal",
    "commitment_due", "decision_pending", "financial_obligation", "deadline_stated",
    "risk_flagged", "commitment_made", "decision_made", "opportunity_signal",
    # `availability_change` is not in doc 06 — member fifteen, placed last among the real types.
    "relationship_change", "availability_change", "anomaly",
]


def test_the_precedence_order_is_doc_06s_order(): 
    assert [kind.value for kind in PRECEDENCE] == DOC_ORDER


def test_the_precedence_order_is_total_over_the_taxonomy():
    """Every one of the 15 members has a position, and no member has two."""
    assert set(PRECEDENCE) == set(SignalType)
    assert len(PRECEDENCE) == len(set(PRECEDENCE)) == len(SignalType) == 15


def test_nothing_detected_is_not_classified_as_anything():
    """`None`, never a default kind. ANOMALY is a predicate the detector fires or does not —
    manufacturing it here would put a type on the seam no predicate ever claimed."""
    assert classify_signals([]) is None


def test_a_single_kind_is_its_own_primary_with_no_secondaries():
    classification = classify_signals([T.DEADLINE_STATED])
    assert classification.primary is T.DEADLINE_STATED
    assert classification.secondary_types == ()


@pytest.mark.gate
def test_four_predicates_give_one_primary_and_three_ordered_secondaries():
    """Doc 06's acceptance sentence, verbatim. Input order is deliberately scrambled: a
    classifier that returned the first thing it was handed would pass a sorted input."""
    fired = [T.DECISION_PENDING, T.ANOMALY, T.ESCALATION, T.CONTRACT_RENEWAL]
    classification = classify_signals(fired)

    assert classification.primary is T.ESCALATION
    assert classification.secondary_types == (T.CONTRACT_RENEWAL, T.DECISION_PENDING, T.ANOMALY)
    assert len(classification.secondary_types) == 3
    assert classification.all_types == (T.ESCALATION, T.CONTRACT_RENEWAL, T.DECISION_PENDING,
                                        T.ANOMALY)


def test_two_separate_runs_over_the_same_set_agree():
    """"...deterministically, in two separate runs." Precedence is a constant, so this holds
    without pinning a seed or freezing a clock."""
    fired = [T.OPPORTUNITY_SIGNAL, T.RISK_FLAGGED, T.INFORMATION_CONFLICT, T.COMMITMENT_MADE]
    assert classify_signals(fired) == classify_signals(list(reversed(fired)))


def test_a_repeated_kind_collapses_to_one():
    """Two commitments both due inside the horizon are one KIND, not two. A duplicate in
    `secondary_types` would render the same word twice on one card."""
    classification = classify_signals([T.COMMITMENT_DUE, T.COMMITMENT_DUE, T.DECISION_PENDING])
    assert classification.primary is T.COMMITMENT_DUE
    assert classification.secondary_types == (T.DECISION_PENDING,)


def test_the_primary_is_never_repeated_in_the_secondaries():
    classification = classify_signals(list(SignalType))
    assert classification.primary not in classification.secondary_types
    assert len(classification.all_types) == len(SignalType)


@pytest.mark.parametrize("higher, lower", [
    # the three the doc gives a rationale for: false statement, time-bound, blocking a human
    (T.INFORMATION_CONFLICT, T.ESCALATION),
    (T.ESCALATION, T.APPROVAL_REQUESTED),
    (T.APPROVAL_REQUESTED, T.CONTRACT_RENEWAL),
    # ...and the boundary that proves "descriptive loses": the most commercially valuable kind
    # still sits below a request that is blocking somebody right now.
    (T.APPROVAL_REQUESTED, T.FINANCIAL_OBLIGATION),
    (T.COMMITMENT_DUE, T.COMMITMENT_MADE),
    (T.DECISION_PENDING, T.DECISION_MADE),
    (T.RISK_FLAGGED, T.OPPORTUNITY_SIGNAL),
    (T.RELATIONSHIP_CHANGE, T.ANOMALY),
])
def test_each_stated_precedence_pair_resolves_to_the_higher_one(higher, lower):
    assert precedence_rank(higher) < precedence_rank(lower)
    assert classify_signals([lower, higher]).primary is higher


def test_the_classification_is_frozen():
    """A classification is a record of what an event was judged to be. A record that can be
    edited after the fact is not one."""
    classification = classify_signals([T.ANOMALY])
    with pytest.raises(Exception):
        classification.primary = T.ESCALATION
