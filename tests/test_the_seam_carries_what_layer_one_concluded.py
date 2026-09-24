"""Step 3 · the L1 → L2 seam — Layer 1 does the work and drops it on the floor.

    pytest tests/test_the_seam_carries_what_layer_one_concluded.py -q

THE DEFECT, MEASURED. Layer 1's code is fully wired — an AST audit of all 119 modules in
`capture/` on 2026-09-23 found **zero** genuinely dead ones. What is not wired is the **data**:

    L1 produces      26 ExtractionResult fields + 29 QES fields
    L1 persists      28 columns in `qualified_signals`
    L2 reads          9                                    <- context/situation_bso.py:516

Eight values are computed correctly every sweep and then discarded at the seam. The one that costs
most is `subject_key`: ALG-22 derives it, ALG-19 supersedes on `(subject_key, signal_type)`, it has
a column on `qualification_drops` (0088) and on `signal_lifecycle` (0093) — and **no column on
`qualified_signals` (0089)**. A REFUSED signal records what it was about; a PUBLISHED one does not.
So Layer 2 can walk a supersession chain by pointer and cannot ask *"give me every signal about
the AWS renewal."*

WHY THIS FILE IS MOSTLY HERMETIC. The end-to-end proof needs Postgres and is marked `pg`
elsewhere. Everything here is a claim about SHAPE — a contract field, a column list, two SQL
strings agreeing — and shape is exactly what drifted. `situation_bso.py`'s own comment says so:

    "Two hand-written copies of this select is how the two paths end up disagreeing about which
     signals a situation rests on, and only one of them has a test."

There are two copies. Neither had that test. This file is it.
"""
from __future__ import annotations

import re

import pytest

pytestmark = pytest.mark.unit


# =============================================================================================
# The contract — `subject_key` reaches the object that crosses the seam
# =============================================================================================
def test_c12_carries_the_subject_it_is_superseded_on():
    """ALG-19's supersession key is `(subject_key, signal_type)`. Publishing the type and not the
    subject means the seam carries half a key.

    SUPPLIED, NEVER DERIVED. `contracts/signal.py` argued the field should not exist because
    re-deriving it here would be a second answer to a question `NormalizedSignal.subject_key` has
    already answered. That reasoning is right about *deriving* and wrong about *carrying*:
    `esqe/lifecycle.record_of` already takes it as a parameter for exactly this reason.
    """
    from genios_engine.contracts.signal import QualifiedEnterpriseSignal

    assert "subject_key" in QualifiedEnterpriseSignal.model_fields


def test_the_publisher_passes_the_subject_rather_than_recomputing_it():
    """`build_signal` already holds the `NormalizedSignal`. One kwarg, no second derivation."""
    import inspect

    from genios_engine.capture.esqe import publisher

    source = inspect.getsource(publisher.build_signal)
    assert "subject_key=signal.subject_key" in source, (
        "the subject must be PASSED from the normalized signal, not re-derived from the "
        "extraction — two answers to one question is what the field note warns about")


def test_the_store_writes_the_subject_column():
    """A field on the contract that the store does not persist is a field Layer 2 never sees."""
    from genios_engine.capture.esqe.signal_store import _COLUMNS

    assert "subject_key" in _COLUMNS


# =============================================================================================
# The projection — and the drift its own file warned about
# =============================================================================================
def _selected_columns(sql: str) -> frozenset[str]:
    """The `qs.<column>` names a select reads, whatever order they are written in."""
    return frozenset(re.findall(r"qs\.([a-z_]+)", sql))


def test_the_two_projections_select_exactly_the_same_columns():
    """THE DRIFT GUARD, and the reason this whole file exists.

    `_L1_SELECT` feeds the single-situation read; `_L1_BY_EVENT_SELECT` feeds the sweep, which is
    what every situation in production is actually composed from. They are two hand-written copies
    of one projection and nothing has ever asserted they agree — so one could gain a column and
    the other not, and only the tested path would show it.
    """
    from genios_engine.context.situation_bso import _L1_BY_EVENT_SELECT, _L1_SELECT

    assert _selected_columns(_L1_SELECT) == _selected_columns(_L1_BY_EVENT_SELECT)


def test_the_projection_carries_what_layer_two_cannot_rederive():
    """The widening itself, named column by column rather than counted.

    A column nothing reads is not a win — it is noise with a migration attached. Each of these has
    a consumer that cannot get the value any other way:

      subject_key        grouping and ALG-19 correlation. The headline.
      domain_hints       which corpus L3 should select. Read from the TOP signal only today,
                         via `runner.py`'s `array_agg(...)[1]`, so a situation's second signal
                         contributes no domain at all.
      confidence_bp      how sure Layer 1 was. L2 currently cannot tell a 9000 from a 1000.
      occurred_at        the signal's WORLD time. L2 has the event's, not the signal's.
      expires_at         ALG-19 already decided it; L2 re-guesses.
      secondary_types    a signal is often several kinds; only the primary crosses.
      extraction_ref     the claims behind the signal, per signal — see the next test.
      internal_kind      company canon, which outranks observed traffic and is invisible here.
    """
    from genios_engine.context.situation_bso import _L1_SELECT

    required = {"subject_key", "domain_hints", "confidence_bp", "occurred_at",
                "expires_at", "secondary_types", "extraction_ref", "internal_kind"}
    missing = required - _selected_columns(_L1_SELECT)
    assert not missing, f"the seam still drops: {sorted(missing)}"


def test_the_row_shape_exposes_the_subject_to_layer_two():
    """Selecting a column and not putting it on `L1Signals` moves the loss one line later."""
    from genios_engine.context.situation_bso import L1Signals

    assert "subject_keys" in L1Signals.__dataclass_fields__


# =============================================================================================
# The array_agg[1] that turned out NOT to be a defect
# =============================================================================================
def test_one_extraction_per_event_is_what_makes_the_array_agg_safe():
    """WITHDRAWN AS A DEFECT, 2026-09-23 — and replaced by the invariant that justifies it.

    This step was planned believing `runner.py`'s

        (array_agg(qs.extraction_ref order by qs.importance_bp desc, qs.signal_id))[1]

    lost every signal but the loudest: *"an EVENT-level answer to a SIGNAL-level question."*
    Production says otherwise. Measured on the pilot org, over every event carrying more than one
    qualified signal:

        signals 107 · DISTINCT extraction_ref 32 · DISTINCT domain_hints 7
        per event: signals=5 → distinct_refs=1, distinct_domains=1   (every such event)

    **LLM-2 runs once per event, not once per signal**, and `domain_hints` are computed per event
    in `capture/pipeline.py` too. So all five signals from one email share one extraction and one
    hint set, `[1]` picks the only distinct value, and nothing is lost.

    THIS TEST PINS THE INVARIANT RATHER THAN THE SQL. `[1]` is safe *because* one event has one
    extraction. The day that stops being true — an attachment extracted separately under its
    parent's event id would do it — `[1]` becomes a silent loss with no error and no row missing.
    So the assertion is on the thing that has to stay true, not on the expression that depends on
    it.

    The second premise this plan got wrong, and the second one production corrected. Step 2's was
    "the gate deletes bounces"; it did not. Both were caught by measuring.
    """
    import inspect

    from genios_engine.capture import pipeline

    source = inspect.getsource(pipeline.capture_event)
    # One assignment, one call: `run_semantic_lane` is invoked once per event, so there is one
    # `processing_key` and therefore one `extraction_ref` for every signal the event yields.
    assert source.count("run_semantic_lane(") == 1, (
        "more than one semantic call per event would break the invariant that makes "
        "runner.py's array_agg[1] safe — see this test's docstring")
