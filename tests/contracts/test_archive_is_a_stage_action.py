"""STEP-03 · `archive` is a stage action: the gate's verb for "kept, and not read".

    pytest tests/contracts/test_archive_is_a_stage_action.py -q

`contracts/trace.StageAction` (tree `yc2_w27_s03/M21.C1.L-contract.V0.U02`). The gate used to `drop` a mail
the noise rules or the AI filter called noise, and a drop kept no body. It now ARCHIVES it — keeps it,
reads it with no model — and the trace has to be able to say so, or every archived mail would be
recorded as a `drop` it never was.
"""
from __future__ import annotations

from genios_engine.contracts.trace import EventTrace, StageAction


def test_archive_is_a_stage_action():
    assert StageAction("archive") is StageAction.archive


def test_the_vocabulary_is_the_six_verbs():
    assert {a.value for a in StageAction} == {"pass", "drop", "park", "emit", "short_circuit",
                                             "archive"}


def test_a_trace_records_an_archive():
    trace = EventTrace(org_id="o", event_id="e")
    trace.record("S1", "archive", reason_code="N-02")
    record = trace.records[-1]
    assert (record.stage, record.action, record.reason_code) == ("S1", StageAction.archive, "N-02")
