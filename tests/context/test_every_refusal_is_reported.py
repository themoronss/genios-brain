"""L2-0 · every way Layer 2 declines, counted and named — with nothing silent.

    pytest tests/context/test_every_refusal_is_reported.py -q

⛔ **THE DEFECT THIS CLOSES, IN THE CODE'S OWN WORDS.** `situation_bso.l1_refusal`:

> *"THE REFUSAL IS CORRECT. The 71 events behind those cards scored 528-1920 basis points against a
> floor of 2500... **THE SILENCE IS NOT.** Such a card today simply exists, ranks, and quietly never
> becomes anything, while no surface says 'its best evidence scored 1360 against a floor of 2500'.
> That is **the fifth time** this codebase has carried a refusal that was right and invisible, and
> the other four were each found by accident."*

Layer 1 wrote the rule for signals — **`DROP ≠ DELETE`** — and logs why, which rule, which
threshold. **Layer 2 has the refusals and no ledger that anyone reads.** Every number this report
needs already exists: `l1_refusal()` returns `highest_bp` and `floor_bp`,
`situation_admission_decisions` stores `outcome` and `reasons` with the candidate's own bytes.
**Nothing assembles them.**

PURE, and that is the point. The report's shape is computed from rows, so it is testable without a
database — the property that makes `capture/validate/` the strongest package in Layer 1.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


def _rows():
    """Three decisions, one of each outcome, shaped as the ledger stores them."""
    return [
        {"situation_id": "s1", "outcome": "hold",
         "reasons": ["qes_required", "verified_evidence_required"]},
        {"situation_id": "s2", "outcome": "hold", "reasons": ["conflict_open"]},
        {"situation_id": "s3", "outcome": "admit", "reasons": []},
    ]


# =================================================================================================
# Totality — a reason nobody reports is the sixth time
# =================================================================================================
def test_every_hold_reason_has_a_row_even_at_zero():
    """⛔ **The guard that makes a sixth invisible refusal harder.** A reason that only appears
    when it fires is a reason nobody knows exists. All seven are always present, zeros included —
    the same totality idiom as `PRECEDENCE` and `ANCHOR_FAMILIES`."""
    from genios_engine.context.quality.refusals import refusal_report
    from genios_engine.context.situation_publisher import HoldReason

    report = refusal_report(decisions=_rows(), refusals=(), dark=())

    for reason in HoldReason:
        assert reason.value in report.by_reason, f"{reason.value} can fire and is never reported"


def test_a_new_hold_reason_cannot_escape_the_report():
    """The other direction. If someone adds an eighth `HoldReason`, this fails until the report
    knows about it — because the report is built FROM the enum, not from a second hand-kept list.
    Two lists of the same fact drift; this repository has caught that five times."""
    from genios_engine.context.quality.refusals import refusal_report
    from genios_engine.context.situation_publisher import HoldReason

    report = refusal_report(decisions=(), refusals=(), dark=())

    assert set(report.by_reason) == {r.value for r in HoldReason}


# =================================================================================================
# Counting
# =================================================================================================
def test_one_decision_with_two_reasons_counts_under_both():
    """A situation held for two reasons is held for two reasons. Picking one would make the
    totals add up and the diagnosis wrong."""
    from genios_engine.context.quality.refusals import refusal_report

    report = refusal_report(decisions=_rows(), refusals=(), dark=())

    assert report.by_reason["qes_required"] == 1
    assert report.by_reason["verified_evidence_required"] == 1
    assert report.by_reason["conflict_open"] == 1


def test_outcomes_are_counted_separately_from_reasons():
    """`held` is a count of situations. `by_reason` is a count of reasons. They are different
    numbers and conflating them is how 63 becomes 71."""
    from genios_engine.context.quality.refusals import refusal_report

    report = refusal_report(decisions=_rows(), refusals=(), dark=())

    assert report.held == 2
    assert report.admitted == 1
    assert sum(report.by_reason.values()) == 3


# =================================================================================================
# ⛔ The sentence the code says is missing
# =================================================================================================
def test_a_held_situation_can_state_its_score_against_the_floor():
    """⛔ *"no surface says 'its best evidence scored 1360 against a floor of 2500'."* This is that
    surface. `l1_refusal()` already returns both numbers; nothing rendered them."""
    from genios_engine.context.quality.refusals import refusal_report

    report = refusal_report(
        decisions=_rows(), dark=(),
        refusals=({"situation_id": "s1", "highest_bp": 1360, "floor_bp": 2500},))

    assert report.scored_refusals
    said = report.scored_refusals[0].sentence
    assert "1360" in said and "2500" in said


def test_a_refusal_with_no_score_says_so_rather_than_guessing():
    """*"`None` when there is nothing to report: a live signal exists, or the events were never
    scored at all. Never assessed and assessed-then-refused are different facts."*"""
    from genios_engine.context.quality.refusals import refusal_report

    report = refusal_report(
        decisions=_rows(), dark=(),
        refusals=({"situation_id": "s2", "highest_bp": None, "floor_bp": None},))

    said = report.scored_refusals[0].sentence
    assert "not scored" in said.lower() or "never" in said.lower()
    assert "0" not in said.split("scored")[0]


# =================================================================================================
# Dark domains travel with the report
# =================================================================================================
def test_a_dark_domain_is_named_in_the_report_not_merely_missing():
    """A tenant whose only domain is dark reads as 'nothing is happening'. It is not the same
    fact, and the report must not let the two look alike."""
    from genios_engine.context.quality.refusals import refusal_report

    report = refusal_report(decisions=(), refusals=(),
                            dark=({"domain": "fundraising", "situations": 14},))

    assert report.dark_domains
    assert report.dark_domains[0].domain == "fundraising"
    assert report.dark_domains[0].situations == 14
    assert report.dark_domains[0].reason, "a dark domain with no reason is a label"


def test_the_report_is_empty_and_valid_when_nothing_was_refused():
    """A clean tenant produces a report, not an exception — and its reason table is still total."""
    from genios_engine.context.quality.refusals import refusal_report
    from genios_engine.context.situation_publisher import HoldReason

    report = refusal_report(decisions=(), refusals=(), dark=())

    assert report.held == 0 and report.admitted == 0
    assert len(report.by_reason) == len(list(HoldReason))
    assert all(v == 0 for v in report.by_reason.values())


# =================================================================================================
# L2-0-U4/U5 · the authored corpus is a REFUSAL PATH, and it belongs in the same report.
#
# ⛔ The plan budgeted 334 capabilities going dark at `require_admission=True`. Measured: zero.
# The number was wrong because nothing printed it. `packs/compiler/capability_resolver.corpus_health`
# now computes it from the compiler's own rule; this is where it becomes visible next to the
# other three refusals, because the plan says ONE report and not four dashboards.
# =================================================================================================

def test_a_domain_whose_corpus_cannot_be_read_is_in_the_same_report():
    from genios_engine.context.quality.refusals import refusal_report, render

    report = refusal_report(decisions=(), refusals=(), dark=(), corpus=[
        {"domain": "admin", "total": 59, "admitted": 59, "inadmissible": 0, "hollow": 0},
    ])
    assert report.corpus[0].domain == "admin"
    assert report.corpus[0].admitted == 59
    body = "\n".join(render(report))
    assert "admin" in body and "59" in body


def test_an_inadmissible_capability_is_counted_as_producing_nothing():
    """It is authored, it is in the corpus, and no compile may read it. That is a silence."""
    from genios_engine.context.quality.refusals import refusal_report

    report = refusal_report(decisions=(), refusals=(), dark=(), corpus=[
        {"domain": "sales", "total": 47, "admitted": 40, "inadmissible": 7, "hollow": 0},
    ])
    assert report.corpus_unreadable == 7


def test_a_hollow_capability_is_counted_apart_from_an_inadmissible_one():
    """⛔ Different repairs. An inadmissible capability needs a REVIEWER; a hollow one needs an
    AUTHOR. Summing them into one number tells whoever reads it to do the wrong thing."""
    from genios_engine.context.quality.refusals import refusal_report, render
    report = refusal_report(decisions=(), refusals=(), dark=(), corpus=[
        {"domain": "admin", "total": 59, "admitted": 59, "inadmissible": 0, "hollow": 12},
    ])
    assert report.corpus_unreadable == 0
    assert report.corpus_hollow == 12
    body = "\n".join(render(report))
    assert "hollow" in body.lower()


def test_a_healthy_corpus_still_prints_its_row():
    """A section that appears only when something is wrong is a section nobody trusts is running.

    The same declared-silence rule as the zeros in `BY REASON`: the shape of the answer must not
    depend on the data, or a blank report and a clean one look identical.
    """
    from genios_engine.context.quality.refusals import refusal_report, render
    report = refusal_report(decisions=(), refusals=(), dark=(), corpus=[
        {"domain": "admin", "total": 59, "admitted": 59, "inadmissible": 0, "hollow": 0},
        {"domain": "customer_support", "total": 49, "admitted": 49, "inadmissible": 0, "hollow": 0},
        {"domain": "sales", "total": 47, "admitted": 47, "inadmissible": 0, "hollow": 0},
    ])
    body = "\n".join(render(report))
    assert "AUTHORED CORPUS" in body
    assert "155" in body, "the corpus total must be stated even when nothing is wrong"


def test_corpus_silence_does_not_leak_into_the_situation_total():
    """`silent_total` counts SITUATIONS. A capability is not a situation, and adding the two
    would produce a number that means nothing — the exact conflation the report's own docstring
    warns about for `held` vs `by_reason`."""
    from genios_engine.context.quality.refusals import refusal_report, render
    report = refusal_report(decisions=(), refusals=(), dark=(), corpus=[
        {"domain": "sales", "total": 47, "admitted": 40, "inadmissible": 7, "hollow": 3},
    ])
    assert report.silent_total == 0


def test_a_situation_that_cannot_instruct_is_reported_apart_from_one_that_cannot_be_read():
    """⛔ **Two corpus refusals, two consequences, and collapsing them hides the cheap one.**

    An inadmissible CAPABILITY is dropped — the answer loses its material. An unreviewed
    SITUATION is flagged: `review_state='draft'` → `_apply_abstention` → the card becomes an
    OBSERVATION. *"The intelligence still ships; it stops instructing."*

    Measured 2026-09-24: **24 of 69 authored situations**, 16 of them Customer Support's. One
    word per file. It is the cheapest quality win in Layer 2 and nothing was printing it.
    """
    from genios_engine.context.quality.refusals import refusal_report, render

    report = refusal_report(decisions=(), refusals=(), dark=(), corpus=[
        {"domain": "customer_support", "total": 49, "admitted": 49, "inadmissible": 0,
         "hollow": 0, "situations": 20, "situations_unreviewed": 16},
    ])
    assert report.corpus_unreadable == 0, "its capabilities are fine and must not read as broken"
    assert report.situations_cannot_instruct == 16
    body = "\n".join(render(report))
    assert "instruct" in body.lower(), "the report must say what the number COSTS, not just the number"


def test_situation_counts_default_to_zero_for_a_caller_that_omits_them():
    """The three database sections pass no corpus, and a missing count is not a zero finding."""
    from genios_engine.context.quality.refusals import refusal_report

    report = refusal_report(decisions=(), refusals=(), dark=(), corpus=[
        {"domain": "admin", "total": 59, "admitted": 59, "inadmissible": 0, "hollow": 0},
    ])
    assert report.situations_cannot_instruct == 0


def test_an_observed_law_is_printed_and_not_merely_counted():
    """⛔ Counting without printing is the defect this whole report exists to end. L2-2's V-9 and
    V-10 fire on situations that were ADMITTED, so they appear nowhere else at all."""
    from genios_engine.context.quality.refusals import refusal_report, render

    report = refusal_report(decisions=[
        {"situation_id": "s1", "outcome": "admit", "reasons": ["observed:V-9:anomalies[0]"]},
        {"situation_id": "s2", "outcome": "admit", "reasons": ["observed:V-9:trends[0]"]},
    ], refusals=(), dark=())
    body = "\n".join(render(report))
    assert "V-9" in body
    assert "2" in body


def test_a_law_that_never_fired_still_gets_its_row():
    """The same declared-silence rule as `BY REASON`. A law that appears only when it fires is a
    law nobody knows exists — and V-9 and V-10 are precisely laws waiting for their number."""
    from genios_engine.context.quality.refusals import refusal_report, render

    body = "\n".join(render(refusal_report(decisions=(), refusals=(), dark=())))
    assert "V-1" in body and "V-10" in body


def test_an_observation_is_not_added_to_the_silent_total():
    """⛔ An observed situation PUBLISHED. Counting it as producing nothing would overstate the
    silence by exactly the number of situations that worked."""
    from genios_engine.context.quality.refusals import refusal_report

    report = refusal_report(decisions=[
        {"situation_id": "s1", "outcome": "admit", "reasons": ["observed:V-9:anomalies[0]"]},
    ], refusals=(), dark=())
    assert report.admitted == 1
    assert report.silent_total == 0
