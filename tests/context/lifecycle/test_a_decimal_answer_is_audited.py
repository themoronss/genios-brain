"""STEP-18 B21 · a decimal number in a parsed model answer is audited — never a refusal after the call.

    GENIOS_TEST_DATABASE_URL=… pytest tests/context/lifecycle/test_a_decimal_answer_is_audited.py -q

`yc2_w27_s18` M48.C2.L-logic.V0.U03 (L3 Context Graph, `context/`), `03` F32.

⛔ WHAT WAS WRONG. `context/model_audit.record_model_run` hashes the parsed answer with
`platform/canonical.semantic_hash`, which refuses a float (*"floats are forbidden in semantic
artifacts"*). The resolution pass audits a call BEFORE it reads `ok` and outside any try
(`context/lifecycle/resolution.py`), so one answer with `"confidence": 0.85` — a shape the prompt's
own reader accepts (`parse_description` reads `confidence`) — raised out of `detect_resolutions`: the
call was paid, nothing was recorded, and every later message of the org's pass was never read. The
angle store and the cohort reader audit through the same function.

The hash now reads a float as its decimal text; an answer with no float hashes exactly as before, so
no stored `response_hash` changes meaning.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from genios_engine.context import model_audit as MA
from genios_engine.context.lifecycle.resolution import detect_resolutions
from genios_engine.platform import company_brief as CB
from genios_engine.platform.canonical import semantic_hash

from .conftest import AT, ScriptedModel, answer_for
from .test_resolution import RESOLUTION_TEXT, _drop, _ids, _seed

ORG = "org_s18_decimal_answer"


# ── the hash: a float is its decimal text, everything else as before ──────────────────────────

def test_an_answer_with_no_float_hashes_exactly_as_it_always_did():
    parsed = {"verdict": "RESOLVED", "scope": ["c1"], "start_offset": 3, "nested": {"n": [1, 2]}}
    raw = '{"verdict": "RESOLVED"}'
    assert MA._response_hash(parsed, raw) == semantic_hash({"parsed": parsed, "raw": raw})


def test_a_float_is_hashed_and_two_floats_are_two_answers():
    one = MA._response_hash({"confidence": 0.85}, "")
    assert one == MA._response_hash({"confidence": 0.85}, "")
    assert one != MA._response_hash({"confidence": 0.86}, "")
    assert one != MA._response_hash({"confidence": 85}, ""), "0.85 is not 85"


def test_a_float_anywhere_in_the_answer_is_read_as_its_decimal_text():
    nested = {"items": [{"score": 0.5}, 2.25], "meta": {"weights": [0.1, 1e-07]}}
    assert MA._response_hash(nested, "") == semantic_hash({"parsed": {
        "items": [{"score": Decimal("0.5")}, Decimal("2.25")],
        "meta": {"weights": [Decimal("0.1"), Decimal("1e-07")]}}, "raw": ""})


def test_a_non_finite_float_is_hashed_too_never_refused():
    assert MA._response_hash({"x": float("nan")}, "") != MA._response_hash({"x": float("inf")}, "")


# ── the pass: a paid call is recorded, and the org's resolution pass goes on ──────────────────

@pytest.fixture
def world(pg_store):
    _clear(pg_store)
    _seed(pg_store, ORG, resolution_text=RESOLUTION_TEXT)
    try:
        yield pg_store
    finally:
        _clear(pg_store)


def _clear(store) -> None:
    _drop(store, ORG)
    with store.engine.begin() as c:
        for table in ("l2_model_runs", "llm_costs"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
    CB.invalidate(ORG)


def test_a_resolution_answer_with_a_decimal_is_audited_and_judged(world):
    answer = answer_for(RESOLUTION_TEXT, verdict="RESOLVED", certainty="EXPLICIT_COMPLETION",
                        scope=[_ids(ORG)["commitment"]], quote="we signed yesterday")
    answer["confidence"] = 0.85
    model = ScriptedModel(answers={_ids(ORG)["reply"]: answer})
    out = detect_resolutions(world, ORG, llm=model, eval_time=AT)
    # Both messages of the correlation are read — the ask (no scripted answer: a failed call) and
    # the reply: the decimal no longer ends the org's pass at whichever came first.
    assert model.calls == 2
    assert out.claims_written == 1, "the answer was judged after it was audited"
    with world.engine.connect() as c:
        runs = c.execute(text(
            "select success, parsed_output->>'confidence' as confidence, response_hash "
            "from l2_model_runs where org_id = :o and site = 'resolution' order by success"),
            {"o": ORG}).all()
        costs = c.execute(text(
            "select count(*) from llm_costs where org_id = :o and purpose = 'l2:resolution'"),
            {"o": ORG}).scalar()
    assert [(r.success, r.confidence) for r in runs] == [(False, None), (True, "0.85")], (
        "every paid call is audited, and the answer is kept as the model gave it")
    assert runs[1].response_hash == MA._response_hash(answer, "")
    assert costs == 2, "each paid call reaches the ledger the daily caps read"


def test_the_audit_row_is_written_once_per_call(world):
    """`record_model_run` is idempotent on its run id: auditing the same call twice is one row."""
    result = type("R", (), {"parsed": {"confidence": 0.5}, "raw": "", "ok": True,
                            "input_tokens": 1, "output_tokens": 1, "model": "m"})()
    at = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)
    first = MA.record_model_run(world.engine, org_id=ORG, site="resolution", subject_ref="s",
                                prompt_version="v", prompt="p", result=result, called_at=at,
                                max_tokens=10)
    again = MA.record_model_run(world.engine, org_id=ORG, site="resolution", subject_ref="s",
                                prompt_version="v", prompt="p", result=result, called_at=at,
                                max_tokens=10)
    assert first == again
    with world.engine.connect() as c:
        assert c.execute(text("select count(*) from l2_model_runs where org_id = :o"),
                         {"o": ORG}).scalar() == 1
