r"""L6 · a wrong card names the layer that failed, and a timing complaint still never grades accuracy.

⛔ `M14.C1.U03` was NARROWED. Its second clause — *"`bad_timing` reaches L5 timing rather than the
rule's precision"* — was already true in three independent places before this work:
`calibrate.TAXONOMY`, `units.py:135`, and `_PRECISION_SQL`'s reason list. Building it would have meant
building it twice. What was absent is the LAYER attribution, and what was UNGUARDED is the property
that already worked — a property enforced in three places can be broken in three places.
"""
from __future__ import annotations

import ast
import inspect
import textwrap
import pathlib

import pytest

from genios_engine.LAYERS import LAYERS
from genios_engine.contracts import learning_attribution as LA
from genios_engine.contracts.learning_attribution import (ALL_REASONS, ATTRIBUTION,
                                                          DEBITABLE_LAYERS, LAYER_ORDER,
                                                          LEGACY_REASONS, PrecisionRole,
                                                          WrongReason, attribute,
                                                          reasons_for_layer)
from genios_engine.feedback.attribution import (AttributionReport,
                                                every_legacy_reason_still_grades_the_way_it_did,
                                                route, timing_never_grades_accuracy)

REPO = pathlib.Path(__file__).resolve().parents[2]


# ── the vocabulary ────────────────────────────────────────────────────────────────────────────

def test_no_model_decides_an_attribution():
    """§4: "if the output is a number, a route or a permission, no model produces it." """
    for module in (LA.__file__, __import__(
            "genios_engine.feedback.attribution", fromlist=["route"]).__file__):
        mods = {(n.module or "") for n in ast.walk(ast.parse(pathlib.Path(module).read_text()))
                if isinstance(n, ast.ImportFrom)}
        assert not any("llm" in m or "anthropic" in m or "openai" in m for m in mods), mods


# ── nothing that already worked was broken ────────────────────────────────────────────────────


def test_every_legacy_reason_still_grades_the_way_it_did():
    assert every_legacy_reason_still_grades_the_way_it_did() == ()



def test_a_timing_or_fit_complaint_never_grades_accuracy():
    """⛔ THE MILESTONE'S OWN PROMISE, GUARDED FOR THE FIRST TIME. It was already true in three
    places and failed no build if it stopped being."""
    assert timing_never_grades_accuracy() == ()



def test_the_guard_reads_the_taxonomy_rather_than_restating_it():
    """A copy of a rule passes forever while the rule drifts.

    ⛔ AST, NOT A GREP — AND THE FIRST VERSION OF THIS TEST WAS THE GREP. It asserted
    `"denominator" not in src` and failed on its own docstring, which uses the phrase *"the precision
    denominator"* to explain the rule. That is the blunt-grep family exactly: *"never assert on text
    that happens to sit near a thing."* The structure is what matters — the function must LOAD
    `TAXONOMY`, and no string literal inside it may be a precision role.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(timing_never_grades_accuracy)))
    loaded = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
    assert "TAXONOMY" in loaded

    body = [n for n in ast.walk(tree) if isinstance(n, ast.Constant)
            and isinstance(n.value, str) and n.value != (timing_never_grades_accuracy.__doc__ or "")]
    assert "denominator" not in {c.value for c in body}, (
        "the role is restated as a literal instead of being read from the map")



@pytest.mark.parametrize("reason", ["bad_timing", "stale_data", "wrong_playbook", "wrong_person",
                                    "badly_written"])
def test_the_five_reasons_that_say_the_card_was_right_stay_out_of_the_denominator(reason):
    """⛔ THE HOLE THE WIDENING WOULD HAVE FALLEN INTO. `units.py` tested one literal —
    `reason == "bad_timing"` — and FOUR of these five would have landed in the `else` and debited
    the rule's accuracy: the exact defect this milestone exists to end, created for four new reasons
    by the step meant to fix it for one."""
    from genios_engine.feedback.units import _grades_accuracy

    assert ATTRIBUTION[WrongReason(reason)].precision is PrecisionRole.NONE
    assert _grades_accuracy(reason) is False



@pytest.mark.parametrize("reason", ["not_relevant", "wrong_facts", "misread_source",
                                    "wrong_subject", "bad_link", "bad_reasoning"])
def test_the_six_quality_failures_do_reach_the_denominator(reason):
    """⛔ THE OTHER DIRECTION, AND THE HARDER ONE TO NOTICE. `_PRECISION_SQL` held two reasons. Four
    real quality failures could have been recorded by a founder and counted by nothing — nothing
    breaks and precision merely looks better than it is."""
    from genios_engine.feedback.calibrate import _PRECISION_DENOMINATOR_SQL
    from genios_engine.feedback.units import _grades_accuracy

    assert _grades_accuracy(reason) is True
    assert f"'{reason}'" in _PRECISION_DENOMINATOR_SQL



def test_the_counter_asks_the_map_instead_of_comparing_a_literal():
    from genios_engine.feedback import units

    src = inspect.getsource(units)
    assert 'elif reason == "bad_timing"' not in src
    assert "_grades_accuracy(reason)" in src



def test_an_unknown_reason_still_grades_accuracy_in_the_counter():
    """Conservative in this one direction, deliberately: a client sending a word this build has
    never heard of must not be able to make a bad rule look good. `route` counts the unknowns
    separately so the disagreement is visible rather than merely safe."""
    from genios_engine.feedback.units import _grades_accuracy

    assert _grades_accuracy("something_new") is True


# ── both doors open together ──────────────────────────────────────────────────────────────────


def _wrong(reason: str) -> dict:
    return {"cause": "wrong", "reason": reason}



def test_a_report_over_nothing_says_no_layer_was_named():
    report = route([])
    assert report.worst is None and report.total == 0
    assert "no layer" in report.explain()



def test_the_layer_named_most_often_comes_first():
    report = route([_wrong("bad_link"), _wrong("wrong_subject"), _wrong("bad_timing")])
    assert report.worst.layer == "context" and report.worst.debits == 2



def test_the_tie_break_is_the_earliest_layer_not_the_alphabet():
    """⛔ When capture and deliver are named equally often, capture is where to look first: a bad
    input reaches the reader through every layer after it, and fixing the last one fixes one
    symptom."""
    report = route([_wrong("misread_source"), _wrong("bad_timing")])
    assert [d.layer for d in report.by_layer] == ["capture", "deliver"]



def test_accuracy_debits_are_carried_apart_from_the_total():
    """"Which layer is failing" and "which rule should get quieter" have different answers, and a
    single number cannot give both."""
    report = route([_wrong("stale_data"), _wrong("misread_source")])
    capture = report.by_layer[0]
    assert capture.debits == 2
    assert capture.accuracy_debits == 1 and capture.timing_or_fit_debits == 1



def test_an_unknown_reason_is_counted_and_said_out_loud():
    """⛔ Filing it against a layer nobody chose produces a confident number pointing at the wrong
    team; dropping it makes a client sending garbage look like a quiet week."""
    report = route([_wrong("escalate_to_legal"), _wrong("bad_link")])
    assert report.unattributed == 1
    assert "does not know" in report.explain()
    assert all(d.layer != "unattributed" for d in report.by_layer)



def test_a_judgment_that_is_not_a_complaint_is_counted_apart_so_the_totals_close():
    report = route([{"cause": "snooze"}, {"cause": "run_play"}, _wrong("bad_link")])
    assert report.not_a_complaint == 2 and report.total == 3



def test_the_same_fix_said_forty_times_is_one_thing_to_do():
    report = route([_wrong("bad_link")] * 40)
    assert report.by_layer[0].debits == 40
    assert len(report.by_layer[0].fixes) == 1



def test_the_report_changes_no_weight_anywhere():
    """⛔ A debit is a direction to look. Wiring it to a weight would let one founder's
    misclassification retune a whole layer — and a founder classifying OUR failure, given eleven
    options, is the least reliable input in the system.

    ⛔ AST, NOT A GREP — the first version matched `OFFSET_BOUND` in this module's own docstring,
    where it appears to EXPLAIN that learning is bounded and an attribution is not. Twice in one
    file, which is why the rule is written as "assert on structure" and not as a preference.
    """
    from genios_engine.feedback import attribution

    tree = ast.parse(pathlib.Path(attribution.__file__).read_text())
    referenced = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {
        n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    for knob in ("OFFSET_STEP", "OFFSET_BOUND", "MUTE_PRECISION", "run_calibration"):
        assert knob not in referenced, f"an attribution that touches {knob} is no longer a report"
    assert "store" not in referenced, "an attribution that writes is not a direction to look"
    assert isinstance(route([]), AttributionReport)
