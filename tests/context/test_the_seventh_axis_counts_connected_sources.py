"""The readiness axis — Atlas cell L2-07's seventh axis, as a pure score.

`readiness_score` answers the one question the other six do not ask: has the tenant connected the
tools this domain is DEFINED to need? The six ask about the situation (is it true, is it current,
do the sources agree, is it the right entity, how many of its fields do we know, how good were its
comparisons) and every one of them can score perfectly on a tenant with no finance connector.

WHAT THE AUDIT MEASURED, 2026-10-01, and what these tests pin:

    source_coverage      admin FALSE x3 orgs · required [finance, communication]
                         fresh: {calendar, communication}  ->  `finance` never connected
    context_situations   admin 310 of 459 (67%), 103 of them coverage = -1

`admin` is the one activated domain and it has never been coverage-ready. The L2 blocking vector
could not see that, because its `coverage_bp` axis measures FIELD completeness
(`situations.coverage_score`, `known/expected` over a situation's own fields) and not whether the
domain's required capabilities exist at all.

See `speedrun008/YCW27/layer-2-reasoning/16-AUDIT-AND-PLAN-the-readiness-axis.md`.
"""

from __future__ import annotations

import inspect

from genios_engine.context.situations import (COVERAGE_UNKNOWN, coverage_score,
                                              readiness_score)

#: The tenant's live connection set, all three orgs, as `source_coverage.freshness` holds it.
LIVE_FRESHNESS = {"calendar": "fresh", "communication": "fresh"}

#: What each shipped domain requires, as `source_coverage.required` holds it.
ADMIN_REQUIRED = ["finance", "communication"]
FUNDRAISING_REQUIRED = ["communication"]


def test_admin_is_half_ready_because_finance_was_never_connected() -> None:
    """The measurement this axis exists for: the one activated domain, scored.

    1 of 2 required capabilities fresh. If this ever returns 100 without `finance` appearing in
    the freshness map, the axis has stopped reading the requirement it was built to read.
    """
    score, missing = readiness_score(required=ADMIN_REQUIRED, freshness=LIVE_FRESHNESS)

    assert score == 50, (
        f"admin requires {ADMIN_REQUIRED} and only `communication` is fresh, so the honest score "
        f"is 50 — got {score}")
    assert missing == ["finance (not connected)"], (
        f"the axis must name WHICH capability is absent, not just that one is — got {missing}")


def test_the_one_ready_domain_scores_full_and_names_nothing() -> None:
    """`fundraising` requires only `communication`, which is fresh. A full score is correct here
    and is the control: a score of 100 is reachable, so a 50 elsewhere is a measurement and not a
    ceiling the function cannot climb past."""
    score, missing = readiness_score(required=FUNDRAISING_REQUIRED, freshness=LIVE_FRESHNESS)

    assert score == 100 and missing == []


def test_an_unregistered_domain_is_unknown_and_never_zero() -> None:
    """⛔ The third state. A domain nobody registered requirements for has not been ASSESSED.

    Scoring it 0 would publish "nothing is connected" for a tenant nobody ever asked the question
    about — absence read as negative evidence, which this codebase refuses everywhere else.
    `compute_coverage` already fails such a domain closed with "no negative inference is
    licensed", and this agrees with it rather than inventing a second answer.

    This is the same error `capture/esqe/publisher.py:415` makes one layer down, where a tri-state
    `coverage_ready` becomes `10000 if coverage_ready else 0` and `None` lands on 0.
    """
    score, missing = readiness_score(required=[], freshness=LIVE_FRESHNESS)

    assert score == COVERAGE_UNKNOWN, (
        f"an unassessed domain must return COVERAGE_UNKNOWN ({COVERAGE_UNKNOWN}), not a score — "
        f"got {score}")
    assert score != 0, "0 is a score; COVERAGE_UNKNOWN is the absence of one. They are not equal."
    assert missing and "unknown" in missing[0], (
        "the unknown branch must SAY it is unknown — a silent empty list reads as 'nothing is "
        f"missing', the opposite of the truth. Got {missing}")


def test_stale_and_never_connected_cost_the_same_and_read_differently() -> None:
    """One rule for "can we see this", two sentences for why not.

    `compute_coverage` treats anything but `fresh` as missing, and this agrees deliberately — a
    second rule for the same question in a second place is how the two drift. But a tenant whose
    connector broke this morning and a tenant who never had one need the same SCORE and different
    PROSE, because only one of them has something to fix.
    """
    stale, stale_missing = readiness_score(
        required=ADMIN_REQUIRED, freshness={"finance": "stale", "communication": "fresh"})
    absent, absent_missing = readiness_score(
        required=ADMIN_REQUIRED, freshness={"communication": "fresh"})

    assert stale == absent == 50, "stale is missing — the score may not distinguish them"
    assert stale_missing == ["finance (stale)"]
    assert absent_missing == ["finance (not connected)"]
    assert stale_missing != absent_missing, (
        "the two reasons must be legible apart — 'reconnect it' and 'connect it' are different "
        "instructions to a human")


def test_nothing_fresh_is_zero_and_that_zero_is_a_measurement() -> None:
    """All required capabilities present and stale: a real, assessed 0.

    This is the case that makes `COVERAGE_UNKNOWN` necessary. Here 0 means "we asked and the
    answer is nothing" — so 0 cannot also mean "we never asked", and the unknown branch above
    cannot borrow it.
    """
    score, missing = readiness_score(
        required=ADMIN_REQUIRED, freshness={"finance": "stale", "communication": "stale"})

    assert score == 0
    assert missing == ["communication (stale)", "finance (stale)"], (
        f"both are missing and the list is sorted for a stable receipt — got {missing}")


def test_the_measured_five_thousand_carries_its_own_numerator() -> None:
    """⛔ `reason/decision_maker.py:181`: *"Never substitute 5000. A neutral default is exactly the
    bug that made every card score 50."*

    Admin's honest score IS 50 — 5000 in basis points — and that is the forbidden number. A
    MEASURED 5000 is legitimate; a SUBSTITUTED one is the defect; and on a stored column six
    months from now the two are indistinguishable by inspection.

    So the evidence travels with the number. This test is the reason the function returns a tuple
    instead of an int: a 5000 with `['finance (not connected)']` beside it is a measurement that
    can be audited, and a bare 5000 is the bug wearing the measurement's clothes.
    """
    score, missing = readiness_score(required=ADMIN_REQUIRED, freshness=LIVE_FRESHNESS)

    assert score * 100 == 5000, "the basis-point form of admin's score is the forbidden default"
    assert missing, (
        "⛔ a 5000 with an EMPTY missing list is indistinguishable from the neutral default this "
        "codebase refuses. The numerator's evidence is what makes it auditable, and it must never "
        "be reconstructible-only")
    assert len(missing) == len(ADMIN_REQUIRED) - 1, (
        "the missing list must account for exactly the capabilities that are not fresh, so "
        "`fresh = len(required) - len(missing)` is checkable from the stored record alone")


def test_readiness_and_coverage_are_not_the_same_question() -> None:
    """The audit's central finding, pinned so a later reader cannot collapse the two axes.

    `coverage_score` scores a situation's own FIELDS. `readiness_score` scores the DOMAIN's
    required capabilities. A tenant with no finance connector scores a perfect `coverage` on a
    situation whose expected fields are all present — which is exactly what 310 admin situations
    were doing while `source_coverage` said the domain was not ready.
    """
    # A situation whose every expected field is known: coverage is perfect.
    coverage, coverage_missing = coverage_score(
        present_fields={"amount", "due_date"},
        expected={"amount": "amount", "due_date": "due date"})
    # The same tenant's domain readiness: half, because `finance` is not connected.
    readiness, readiness_missing = readiness_score(
        required=ADMIN_REQUIRED, freshness=LIVE_FRESHNESS)

    assert coverage == 100 and coverage_missing == []
    assert readiness == 50 and readiness_missing == ["finance (not connected)"]
    assert coverage != readiness, (
        "⛔ if these ever agree by construction the seventh axis is a second copy of the fifth "
        "and L2-07 is still open")


def test_the_axis_reads_no_clock_and_opens_no_connection() -> None:
    """Pure, like the six beside it. `eval_time` as a parameter never `now()`, and a score
    function that could read a connection would make a replay of a March sweep return October's
    connection set."""
    signature = inspect.signature(readiness_score)

    assert set(signature.parameters) == {"required", "freshness"}, (
        f"the axis takes the tenant's own `source_coverage` columns and nothing else — got "
        f"{list(signature.parameters)}")
    assert all(p.kind is p.KEYWORD_ONLY for p in signature.parameters.values()), (
        "keyword-only, like every other axis in this module: two same-typed positional arguments "
        "are a silent swap waiting to happen")

    body = inspect.getsource(readiness_score)
    body = body[body.index('"""', body.index('"""') + 3):]      # past the docstring
    for forbidden in ("now()", "utcnow", "datetime.now", "connect(", "execute("):
        assert forbidden not in body, (
            f"{forbidden!r} in a confidence axis — this function must be a pure read of its two "
            "arguments")
