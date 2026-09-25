"""L3-03 · a connected source is not a read window, and only one of the two was a gate.

`classify_absence` already refused `GENUINELY_ABSENT` without `coverage_ready=True` and a non-empty
basis — a genuinely strong gate, enforced at the TYPE level in `contracts/quality`. Both those
facts are about the TENANT: is there a source, is it fresh. NEITHER LOOKS AT THE SWEEP. So a tenant
with Gmail connected and a sweep that read 37 of about 465 threads passed both and reached a
licensed negative inference over 8% of a mailbox — the 23 Sept benchmark's failure, surviving
inside the module built to prevent it.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

from genios_engine.context.quality.lens import CoverageLens
from genios_engine.context.quality.missing import (WINDOW_UNCHECKED, AbsenceSubject, Expectation,
                                                   classify_absence)
from genios_engine.contracts.quality import AbsenceType

NOW = datetime(2026, 9, 23, tzinfo=timezone.utc)

_SUBJ = AbsenceSubject(situation_id="s1", subject_node_id="n1", domain="sales",
                       situation_type="deal", present_fields=frozenset())
_EXP = Expectation(field="deal.owner")
_READY = CoverageLens(org_id="o", ready={"sales": True}, basis={"sales": ("gmail",)},
                      epochs={"sales": 1})


def _classify(**kw) -> AbsenceType:
    return classify_absence(_SUBJ, _EXP, _READY, eval_time=NOW, **kw)


# =================================================================================================
# 1 · ⛔ THE HOLE THAT WAS THERE
# =================================================================================================

def test_a_connected_source_alone_no_longer_licenses_an_absence():
    """The exact benchmark failure: Gmail connected, 8% read, "no follow-up found" published as a
    fact about the business."""
    assert _classify(window_ok=False) is AbsenceType.UNKNOWABLE


def test_a_read_window_over_a_connected_source_still_does():
    """The gate must not become a wall. A sweep that exhausted its cursor with a denominator, over
    a fresh connected source, is exactly the case a negative inference is FOR."""
    assert _classify(window_ok=True) is AbsenceType.GENUINELY_ABSENT


def test_not_asking_leaves_the_cascade_exactly_as_it_was():
    """⛔ `None` is a DIFFERENT `None` from `lens.ready_for`'s.

    That one is about a tenant — a domain nobody declared — and refusing is correct. This one is
    about a CALLER. Making it refuse would empty the Ownership surface, which is built entirely on
    typed absence, for every caller not yet updated: a safety improvement turned into an outage.
    """
    assert _classify() is AbsenceType.GENUINELY_ABSENT
    assert _classify(window_ok=None) is AbsenceType.GENUINELY_ABSENT


# =================================================================================================
# 2 · ⛔ ORDER — the window gate is LAST, and that is the safety rule
# =================================================================================================

def test_the_window_gate_never_rescues_a_claim_the_earlier_gates_refused():
    """A perfect sweep over a domain with no coverage is still UNKNOWABLE. If the window check ran
    first, or returned early, a well-read window would launder a tenant that has no source at
    all — which is the more dangerous direction of the two."""
    dark = CoverageLens(org_id="o", ready={"sales": False}, basis={"sales": ("gmail",)})
    undeclared = CoverageLens(org_id="o")
    no_basis = CoverageLens(org_id="o", ready={"sales": True}, basis={})
    for lens in (dark, undeclared, no_basis):
        assert classify_absence(_SUBJ, _EXP, lens, eval_time=NOW,
                                window_ok=True) is AbsenceType.UNKNOWABLE


def test_a_present_fact_is_never_touched_by_the_window():
    """PRESENT and STALE are about a fact we HAVE. Coverage of a window says nothing about them,
    and a window check that reached them would turn a known value into an unknown one."""
    subj = AbsenceSubject(situation_id="s1", subject_node_id="n1", domain="sales",
                          situation_type="deal", present_fields=frozenset({"deal.owner"}))
    assert classify_absence(subj, _EXP, _READY, eval_time=NOW,
                            window_ok=False) is AbsenceType.PRESENT


def test_a_not_expected_fact_is_never_touched_by_the_window():
    exp = Expectation(field="deal.owner", expected_when=lambda _s: False)
    assert classify_absence(_SUBJ, exp, _READY, eval_time=NOW,
                            window_ok=False) is AbsenceType.NOT_EXPECTED


# =================================================================================================
# 3 · ⛔ THE SILENCE IS DECLARED, NOT DEFAULTED
# =================================================================================================

def test_every_caller_either_asks_or_is_declared():
    """⛔ THE SEVENTH OCCURRENCE OF THE "UNIT NOTHING CALLS" DEFECT IS A BUILD FAILURE.

    `window_ok=None` leaves behaviour unchanged, which is correct and is also exactly how a gate
    comes to be reached by nothing on a real path. So the exemption is a list: a module that calls
    into this cascade must either pass `window_ok`/`window_ok_for` or appear in
    `WINDOW_UNCHECKED` with a reason.
    """
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "genios_engine"
    entries = ("classify_absence(", "classify_all(", "detect_missing(", "refresh_typed_absences(")
    offenders: list[str] = []
    for py in root.rglob("*.py"):
        if py.name == "missing.py":
            continue                                    # the cascade itself
        src = py.read_text()
        if not any(e in src for e in entries):
            continue
        module = ".".join(py.relative_to(root).with_suffix("").parts)
        if "window_ok" in src or module in WINDOW_UNCHECKED:
            continue
        offenders.append(module)
    assert not offenders, (
        "modules driving the absence cascade without asking whether the window was read, and "
        f"without declaring why: {offenders}. Add the argument, or add the module to "
        "WINDOW_UNCHECKED with a reason and a mover.")


def test_the_declared_exemptions_carry_reasons_and_still_exist():
    """A declared silence whose module has been deleted is a stale exemption that would hide a real
    caller the day the name is reused."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[2] / "genios_engine"
    for module, reason in WINDOW_UNCHECKED.items():
        assert len(reason) > 30, f"{module} is exempted without a real reason"
        assert (root / Path(*module.split("."))).with_suffix(".py").exists(), \
            f"WINDOW_UNCHECKED names {module}, which no longer exists"


# =================================================================================================
# 4 · ⛔ THE WIRING — per subject, and the same rule as the card
# =================================================================================================

def test_the_producer_asks_per_subject_and_not_per_sweep():
    """A sweep-wide flag would give every situation the first situation's answer — the memo-key
    mistake of L3-02b, one layer up."""
    src = inspect.getsource(__import__("genios_engine.context.situations", fromlist=["x"]))
    assert "window_ok_for=_window_ok" in src, "refresh_situations no longer asks"
    assert "min(times)" in src, "the span must come from the subject's own observed facts"
    assert "if not times:\n                    return None" in src, \
        "undated evidence must return None rather than a guessed window"


def test_the_gate_and_the_card_sentence_share_one_rule():
    """⛔ Two rules would drift within a month, and the drift would be invisible: a card saying
    "we only read part of this" beside an absence asserted as fact."""
    src = inspect.getsource(__import__("genios_engine.context.situations", fromlist=["x"]))
    assert "not window_coverage_gaps(" in src, (
        "the gate must be the same function that produces the card's sentence — `()` means every "
        "source covering the span can support an absence claim")
