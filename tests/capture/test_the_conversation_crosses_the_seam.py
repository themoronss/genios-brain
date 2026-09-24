"""Layer 1 · the conversation a signal was qualified inside must reach Layer 2.

    pytest tests/capture/test_the_conversation_crosses_the_seam.py -q

⛔ **THE PREMISE CHECK MOVED THIS UNIT BEFORE A LINE WAS WRITTEN, TWICE.**

The failure log recorded `S01b` as Layer 1's one OPEN defect: *"`pipeline.py` hands
`reconstruct_thread` a list of ONE message, so ALG-03's parent resolution has never run on real
data."* True — and **it is not the defect**, because of one sentence in `reconstruct_thread`:

> *"`ball_in_court` is derived from the most recent message BY TIME, not from the last link of the
> walk."*

At capture the event **is** the newest message of its thread, so a one-message list and the full
thread give **the identical answer**. Verified by execution, not by reading: a four-message thread
and its newest message alone both return `us`; a three-message thread and its newest both return
`them`.

**So the value is computed correctly. It simply never leaves.**

`ThreadContext` holds five facts — `thread_key`, `direction`, `turn_index`, `thread_depth`,
`ball_in_court` — and its own docstring says *"NONE of it reached S4"*. It now reaches S4. What it
still does not reach is `QualifiedEnterpriseSignal`: `NormalizedSignal.thread` sits **right there**
in `build_signal` and the builder does not read it.

That is exactly the leak step 14 found in `domain_hints` — a value present at the seam that the
builder forgets — and it is what the plan's own diagnosis says out loud:

> *"Every measured loss is a value that is computed correctly and then not carried: `ball_in_court`
> and `turn_index` reach only the trace."*

**Four benchmark objects turn on these four fields**, all classed `not_carried`:
`message_direction`, `ball_in_court`, `turn_index` and `activity_count`.

**`last_inbound_at` is deliberately NOT here.** It needs messages other than this one — from a
single message you know only that message's time — so it is the honest remainder of `S01b` and
stays open rather than being guessed.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


# =================================================================================================
# The contract — a field that does not exist cannot be carried
# =================================================================================================
def test_the_signal_contract_has_somewhere_to_put_the_conversation():
    """`QualifiedEnterpriseSignal` carried **none** of the four. A value with nowhere to go is
    stranded however correctly it was computed."""
    from genios_engine.contracts.signal import QualifiedEnterpriseSignal

    fields = set(QualifiedEnterpriseSignal.model_fields)

    assert {"thread_key", "direction", "turn_index", "thread_depth",
            "ball_in_court"} <= fields


def test_the_conversation_fields_default_to_refusal_and_not_to_a_guess():
    """`direction` is `None` and `ball_in_court` is `"unknown"` when no identity for "us" was
    supplied — *"with no identity every message looks inbound, which is how a product's own
    onboarding mail got modelled as a prospect asking for a demo."*

    The defaults must carry that refusal forward, not replace it with a cheerful `inbound`.
    """
    from genios_engine.contracts.signal import QualifiedEnterpriseSignal

    fields = QualifiedEnterpriseSignal.model_fields

    assert fields["direction"].default is None
    assert fields["ball_in_court"].default == "unknown"
    assert fields["turn_index"].default == 0
    assert fields["thread_depth"].default == 1


# =================================================================================================
# The wiring — the builder must READ the ThreadContext it is handed
# =================================================================================================
def test_build_signal_carries_the_thread_context_it_was_given():
    """⛔ **THE WIRING CHECK, and it is the whole unit.** `NormalizedSignal.thread` is present at
    `build_signal` and was never read — the same shape as step 14's `domain_hints` leak, where the
    builder rebuilt the value by hand and dropped a field.

    *"A unit is done when a real request path reaches it and a test drives that path."*
    """
    from genios_engine.capture.esqe.normalize import ThreadContext

    built = _build(ThreadContext(thread_key="thread:t1", direction="inbound", turn_index=3,
                                 thread_depth=4, ball_in_court="us"))

    assert built.thread_key == "thread:t1"
    assert built.direction == "inbound"
    assert built.turn_index == 3
    assert built.thread_depth == 4
    assert built.ball_in_court == "us"


def test_a_signal_with_no_thread_context_still_publishes():
    """`NormalizedSignal.thread` is optional — a calendar event or an uploaded document is not a
    conversation. A missing thread must produce the refusing defaults, never an exception."""
    built = _build(None)

    assert built.thread_key is None
    assert built.ball_in_court == "unknown"
    assert built.direction is None


def test_the_turn_index_that_crosses_is_the_one_step_sixteen_corrected():
    """Step 16 fixed `turn_index` at its source — every event read turn 0 because no connector
    stated a thread position. Carrying it now would be worthless if it still read 0 for a reply."""
    from genios_engine.capture.esqe.normalize import ThreadContext
    from genios_engine.capture.pipeline import _thread_place

    position, depth = _thread_place({"thread_position": 4, "thread_depth": 4})
    built = _build(ThreadContext(turn_index=position - 1, thread_depth=depth))

    assert (built.turn_index, built.thread_depth) == (3, 4)


# =================================================================================================
# Storage — a column no writer names is null forever
# =================================================================================================
def test_the_store_names_the_conversation_columns_in_its_insert():
    """*"`started_at` on `l1_sync_runs` is the cautionary tale: the column existed from the day the
    table did, the insert never mentioned it, and every row in production recorded a finish with no
    start. A column no writer names is null forever."*"""
    from genios_engine.capture.esqe.signal_store import _COLUMNS

    for column in ("thread_key", "direction", "turn_index", "thread_depth", "ball_in_court"):
        assert column in _COLUMNS, f"{column} is on the contract and no writer names it"


def test_migration_0181_adds_the_columns_nullably():
    """Every signal written before this carries no conversation, and the honest reading of that is
    *"we do not know"*. A NOT NULL with a default would have to invent a direction."""
    import pathlib
    import re

    sql = pathlib.Path("migrations/0181_signal_conversation.sql").read_text().lower()

    assert "add column if not exists" in sql
    for column in ("thread_key", "direction", "turn_index", "thread_depth", "ball_in_court"):
        assert column in sql
    # ⛔ MATCHED AGAINST A COLUMN DECLARATION, NOT THE WHOLE FILE. A bare `"not null" in sql`
    # was tried first and failed — on this migration's own COMMENT explaining why `direction`
    # must stay nullable. Step 14 made the identical mistake against the 0179 partial index and
    # recorded the fix; making it a second time is what this narrower form is for.
    declarations = re.findall(r"add column if not exists\s+\w+\s+\w+([^,;]*)", sql)

    assert declarations, "no column declarations parsed — the pattern no longer matches"
    for tail in declarations:
        assert "not null" not in tail, (
            "a nullable column is what lets an older signal say 'we do not know'")


# =================================================================================================
# The benchmark — the reason this unit was chosen over the other ten
# =================================================================================================
def test_four_stranded_benchmark_objects_now_cross_the_seam():
    """⛔ **11 of the benchmark's 18 misses are `not_carried`** — computed in L1, never crossing.
    These four are the block that one `ThreadContext` closes.

    `who_sent_last` and `p3_who_sent_last` are **not** here: both read `last_inbound_at`, which
    needs messages other than this one. That is the honest remainder of S01b.
    """
    from genios_engine.capture.benchmark import score_benchmark

    stranded = {m.name for m in score_benchmark().misses}

    assert {"message_direction", "ball_in_court", "turn_index",
            "activity_count"} & stranded == set()


def test_the_benchmark_moved_and_the_calibration_still_explains_it():
    """*"Present now, absent in the audit, and NO step claims it"* is the signature of a harness
    bug — the population `calibrate` exists to detect, and which caught one within a minute of
    being written. A jump with unexplained rows is not progress."""
    from genios_engine.capture.benchmark import calibrate, score_benchmark

    report = score_benchmark()
    calibration = calibrate()

    assert report.present >= 24, f"expected 20 → 24, got {report.present}"
    assert calibration.unexplained == (), f"unexplained gains: {calibration.unexplained}"
    assert calibration.regressed == (), f"regressions: {calibration.regressed}"


# =================================================================================================
def _build(thread):
    """One C-12 through the REAL `build_signal`, with a thread context or without one.

    ⛔ **NO TEST IN THIS REPOSITORY CALLS `build_signal`.** Step 14's `due_at` check and step 6's
    `domain_hints` check both assert by reading the function's SOURCE. That is the weaker form —
    a source grep passes on a builder nobody calls — so this drives the function and asserts on
    what comes out.

    The scaffolding below is what a publishable signal costs: V-4 refuses an empty
    `evidence_refs`, the vector must carry all four components, and `versions` must name what
    produced the signal or it cannot be replayed. Paying that is the point.
    """
    from genios_engine.capture.esqe.normalize import NormalizedSignal
    from genios_engine.capture.esqe.publisher import SignalInputs, build_signal
    from genios_engine.contracts.evidence import EvidenceSpan
    from genios_engine.contracts.extraction import Commitment, ExtractionResult
    from genios_engine.contracts.visibility import Visibility

    text = "I will send the renewal on Friday."
    span = EvidenceSpan(source_ref="prepared_content:e1", quote="send the renewal",
                        start_offset=text.index("send the renewal"),
                        end_offset=text.index("send the renewal") + len("send the renewal"))
    extraction = ExtractionResult(
        intent="commit", stance="positive", model_snapshot="test", prompt_version="test",
        schema_version="test", extraction_profile="email", input_tokens=0, output_tokens=0,
        commitments=[Commitment(actor="me", action="send the renewal", is_conditional=False,
                                confidence_bp=8000, evidence=[span])])

    class _Gated:
        versions = {"prompt": "test", "schema": "test", "model": "test", "vocabulary": "test"}
        coverage_ready = True
        triage_lane = "P2"

    normalized = NormalizedSignal(
        org_id="o", event_id="e1", source="gmail", object_type="email_message",
        occurred_at=NOW,
        visibility=Visibility(scope="participants", principals=["a@x.com"],
                              derived_from="test"),
        recipients=("a@x.com",), internal_kind=None,
        signal_type="commitment_made", predicate="test", subject_key="thread:t1",
        subject_label="renewal", primary_entity=None, primary_date=None, primary_amount=None,
        evidence_refs=(span,), attribution=None, thread=thread)

    signal, _, error = build_signal(
        normalized, SignalInputs(importance_bp=5000, extraction=extraction, gated=_Gated()),
        eval_time=NOW)
    assert error is None, f"the contract refused the signal: {error}"
    return signal
