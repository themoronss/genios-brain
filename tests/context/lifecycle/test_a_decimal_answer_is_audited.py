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

`yc2_w27_s18` M48.C2.L-logic.V1.U15 (S18-X05). The hash was mended and the ROW was not: the parser
lets `NaN`, `Infinity` and `-Infinity` in (`context/llm/parse.py` is `json.loads`), `json.dumps` wrote
them back as bare tokens, and `cast(:parsed as jsonb)` refuses them — the audit row, the `llm_costs`
row of the same transaction and the rest of the org's resolution pass were lost again. A non-finite
number is stored as its name and a Decimal as its text; a finite answer is stored byte for byte as
before.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from genios_engine.context import model_audit as MA
from genios_engine.context.lifecycle.prompt import parse_description
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


# ── the row: what the hash reads, Postgres must store ─────────────────────────────────────────

def test_a_finite_answer_is_stored_exactly_as_before():
    parsed = {"verdict": "RESOLVED", "confidence": 0.85, "scope": ["c1"], "n": [1, 2.5e-07],
              "flag": True, "none": None}
    assert MA._stored(parsed) == json.dumps(parsed, sort_keys=True)


def test_a_non_finite_number_is_stored_as_its_name_and_a_decimal_as_its_text():
    stored = json.loads(MA._stored({"x": float("nan"), "y": [float("inf"), {"z": float("-inf")}],
                                    "d": Decimal("1.10"), "k": True}))
    assert stored == {"x": "nan", "y": ["inf", {"z": "-inf"}], "d": "1.10", "k": True}


def test_a_value_json_cannot_hold_is_refused_before_the_transaction(monkeypatch):
    """`allow_nan=False`: whatever slips past the mapping is a ValueError in Python, never a
    statement Postgres refuses inside the transaction that holds the cost row."""
    class Weird(float):
        pass
    assert MA._stored({"x": Weird("nan")}) == '{"x": "nan"}', "a float subclass is still mapped"
    monkeypatch.setattr(MA, "_storable", lambda value: value)       # a mapping that missed one
    with pytest.raises(ValueError):
        MA._stored({"x": float("nan")})


def test_an_answer_with_nan_is_stored_and_costed(world):
    """S18-X05's breaking input, on Postgres: `{"x": NaN}` and its kin."""
    result = type("R", (), {"parsed": {"x": float("nan"), "y": float("inf"), "z": float("-inf"),
                                       "ok": 0.5, "d": Decimal("2.50")},
                            "raw": '{"x": NaN}', "ok": True, "input_tokens": 3,
                            "output_tokens": 2, "model": "m"})()
    at = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)
    MA.record_model_run(world.engine, org_id=ORG, site="resolution", subject_ref="s_nan",
                        prompt_version="v", prompt="p", result=result, called_at=at, max_tokens=10)
    with world.engine.connect() as c:
        row = c.execute(text(
            "select parsed_output->>'x' as x, parsed_output->>'y' as y, parsed_output->>'z' as z, "
            "jsonb_typeof(parsed_output->'ok') as ok_type, parsed_output->>'d' as d, raw_output "
            "from l2_model_runs where org_id = :o and subject_ref = 's_nan'"), {"o": ORG}).one()
        costs = c.execute(text("select count(*) from llm_costs where org_id = :o "
                               "and subject_ref = 's_nan'"), {"o": ORG}).scalar()
    assert (row.x, row.y, row.z, row.ok_type, row.d) == ("nan", "inf", "-inf", "number", "2.50")
    assert row.raw_output == '{"x": NaN}', "the raw text is kept as the model wrote it"
    assert costs == 1, "the paid call reaches the ledger the daily caps read"


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


def test_a_resolution_answer_with_nan_is_audited_and_the_pass_goes_on(world):
    """S18-X05 through the pass: a `NaN` in the answer no longer ends the org's resolution pass."""
    answer = answer_for(RESOLUTION_TEXT, verdict="RESOLVED", certainty="EXPLICIT_COMPLETION",
                        scope=[_ids(ORG)["commitment"]], quote="we signed yesterday")
    answer["confidence"] = float("nan")
    model = ScriptedModel(answers={_ids(ORG)["reply"]: answer})
    out = detect_resolutions(world, ORG, llm=model, eval_time=AT)
    assert model.calls == 2
    assert out.claims_written == 1, "the answer was judged after it was audited"
    with world.engine.connect() as c:
        runs = c.execute(text(
            "select success, parsed_output->>'confidence' as confidence from l2_model_runs "
            "where org_id = :o and site = 'resolution' order by success"), {"o": ORG}).all()
    assert [(r.success, r.confidence) for r in runs] == [(False, None), (True, "nan")]


# ── F-3 (`yc2_w27_s1718` M48.C2.L-logic.V2.U20, second crosscheck) ────────────────────────────
# `int(float("inf"))` raises OverflowError, not ValueError — NaN above is caught by the existing
# `except (TypeError, ValueError)`; Infinity, -Infinity and 1e999 (which `float()` reads as inf
# with no error) were not, and the exception reached `detect_resolutions` uncaught and ended the
# rest of the org's resolution pass. `parse_description` now treats a non-finite offset or
# confidence the same as any other unusable shape: `None`, never a raise.

def test_parse_description_rejects_a_non_finite_offset_as_a_shape_failure():
    base = {"verdict": "RESOLVED", "certainty": "EXPLICIT_COMPLETION", "scope": ["c1"],
            "quote": "we signed yesterday", "start_offset": 3, "end_offset": 24}
    for bad in (float("inf"), float("-inf"), float(1e999)):
        assert parse_description({**base, "end_offset": bad}) is None
        assert parse_description({**base, "start_offset": bad}) is None


def test_parse_description_drops_a_non_finite_confidence_but_keeps_the_rest():
    base = {"verdict": "RESOLVED", "certainty": "EXPLICIT_COMPLETION", "scope": ["c1"],
            "quote": "we signed yesterday", "start_offset": 3, "end_offset": 24}
    for bad in (float("inf"), float("-inf"), float(1e999)):
        described = parse_description({**base, "confidence_bp": bad})
        assert described is not None and described.raw_confidence_bp is None


def test_a_resolution_answer_with_infinity_confidence_is_audited_and_the_pass_goes_on(world):
    """Infinity in `confidence` alone: `parse_description` drops just that field (as NaN does
    above) — audited, judged, the pass goes on."""
    answer = answer_for(RESOLUTION_TEXT, verdict="RESOLVED", certainty="EXPLICIT_COMPLETION",
                        scope=[_ids(ORG)["commitment"]], quote="we signed yesterday")
    answer["confidence"] = float("inf")
    model = ScriptedModel(answers={_ids(ORG)["reply"]: answer})
    out = detect_resolutions(world, ORG, llm=model, eval_time=AT)
    assert model.calls == 2
    assert out.claims_written == 1, "the answer was judged after it was audited"
    with world.engine.connect() as c:
        runs = c.execute(text(
            "select success, parsed_output->>'confidence' as confidence from l2_model_runs "
            "where org_id = :o and site = 'resolution' order by success"), {"o": ORG}).all()
    assert [(r.success, r.confidence) for r in runs] == [(False, None), (True, "inf")]


def test_a_resolution_answer_with_infinity_end_offset_is_audited_and_the_pass_goes_on(world):
    """F-3's own shape: Infinity in `end_offset` makes the WHOLE description unusable — the audit
    row still writes (paid, kept), the message is logged `unusable answer` and skipped, and —
    unlike before the fix, which raised OverflowError out of `detect_resolutions` — every other
    message of the org's pass is still read (`model.calls == 2`, not 1 or an exception)."""
    answer = answer_for(RESOLUTION_TEXT, verdict="RESOLVED", certainty="EXPLICIT_COMPLETION",
                        scope=[_ids(ORG)["commitment"]], quote="we signed yesterday")
    answer["end_offset"] = float("inf")
    model = ScriptedModel(answers={_ids(ORG)["reply"]: answer})
    out = detect_resolutions(world, ORG, llm=model, eval_time=AT)
    assert model.calls == 2, "the pass was not aborted by the non-finite offset"
    assert out.claims_written == 0, "an unusable description is never judged"
    with world.engine.connect() as c:
        runs = c.execute(text(
            "select success, parsed_output->>'end_offset' as end_offset from l2_model_runs "
            "where org_id = :o and site = 'resolution' order by success"), {"o": ORG}).all()
    assert [(r.success, r.end_offset) for r in runs] == [(False, None), (True, "inf")], (
        "the call is still paid and still audited even though the answer could not be used")
