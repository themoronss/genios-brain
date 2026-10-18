"""The L5 render records whether its model call worked, and why not.

    pytest tests/test_render_records_how_the_call_ended.py -q

⛔ `yc2_w27_s18` M50.C3.L-logic.V1.U15 (the 13 Oct audit's T5-13, s5t-F6). `deliver/render.render_copy`
handed its cost sink the tokens and nothing else, and `GraphStore.record_cost` defaults `success=True`
— so every `l5_render` call was a success in `llm_costs`: a 400, an unparseable answer, a cut one. No
health check that filters on `not success` could see the lane fail. It records `ok` and `error` now, and
a cut answer (`truncated`) is a failure carrying the truncation, whether or not it parsed.
"""
from __future__ import annotations

import pytest

from genios_engine.context.llm.client import TRUNCATED, LLMResult
from genios_engine.deliver.render import render_copy

pytestmark = pytest.mark.unit

TEMPLATE = {"fallback": {"headline": "{entity}", "situation": "{entity} is open"}}


class _LLM:
    def __init__(self, result: LLMResult) -> None:
        self.result = result

    def call(self, prompt, *, max_tokens=600):
        return self.result


def _rows(result: LLMResult) -> list[dict]:
    rows: list[dict] = []
    render_copy(reason_code="opportunity", template=TEMPLATE, facts={"company": {"value": "Acme"}},
                slots={"entity": "Acme"}, llm=_LLM(result), cost_sink=lambda **row: rows.append(row),
                org_id="org_t5")
    return rows


def test_a_call_that_worked_is_a_success_with_no_error():
    rows = _rows(LLMResult(parsed={"headline": "Acme", "situation": "Acme is open", "artifact": ""},
                           raw="{}", model="claude-haiku-4-5", input_tokens=300, output_tokens=40))
    assert [(r["purpose"], r["success"], r["error"]) for r in rows] == [("l5_render", True, None)]


def test_a_failed_call_is_recorded_as_a_failure_with_its_error():
    rows = _rows(LLMResult(parsed={}, raw="nope", ok=False, error="unparseable JSON",
                           model="claude-haiku-4-5", input_tokens=300, output_tokens=40))
    assert [(r["success"], r["error"]) for r in rows] == [(False, "unparseable JSON")]


def test_a_cut_answer_is_a_failure_whether_or_not_it_parsed():
    parsed_cut = LLMResult(parsed={"headline": "Acme"}, raw="{", ok=True, truncated=True,
                           model="claude-haiku-4-5", input_tokens=300, output_tokens=600)
    rows = _rows(parsed_cut)
    assert [(r["success"], r["error"]) for r in rows] == [(False, f"{TRUNCATED} (max_tokens=600)")]
