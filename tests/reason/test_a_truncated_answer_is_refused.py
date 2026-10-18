"""STEP-12 · `03` F140 — an answer cut at the token ceiling is a refusal, recorded; and a gate may repair syntax only.

    pytest tests/reason/test_a_truncated_answer_is_refused.py -q

`reason/bundle/gate.RSiteGate.consult` (tree `yc2_w27_s12` M32.C4.L-logic.V0.U01). `LLMClient.call` sets
`truncated` when the API stopped at `max_tokens` (`2caf88aa`) — and nothing read it: the gate checked
`ok`, so a leniently closed JSON from a cut answer was used as whole, and an unparseable cut answer was
retried at the same ceiling, to be cut again. Now a truncated answer ends the consult as `truncated`: no
retry, never validated, never parsed into anything, recorded with its cost. And a caller may say
`repair="syntax"`: the one retry is for an answer that was not JSON, never for one the validator
refused on substance — STEP-12 §8.4 item 4, "one repair for syntax only, never on substance".

M32.C4.L-logic.V0.U03: an answer that is JSON but not the shape asked for — a refusal coded `malformed`
— is syntax too (STEP-12 §3.4, "schema-checked; one repair on syntax only"): repaired once, the retry
told what was misshapen; a malformed answer the validator ALSO refused on substance is not repaired.
"""
from __future__ import annotations

import pytest

from genios_engine.context.llm.client import LLMResult
from genios_engine.reason import llm_sites as L
from genios_engine.reason.bundle import gate as G
from genios_engine.reason.bundle import sites as S

pytestmark = pytest.mark.unit

ORG = "org_f140"


class _Client:
    model = "claude-sonnet-5"

    def __init__(self, *answers: LLMResult):
        self.answers = list(answers)
        self.calls = 0

    def call(self, prompt, *, max_tokens=400):
        self.calls += 1
        return self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]


class _Store:
    def __init__(self):
        self.calls: list[dict] = []

    def record_call(self, **row):
        self.calls.append(row)


def _cut(parsed: dict | None = None) -> LLMResult:
    """What `LLMClient.call` returns when the API stopped at max_tokens — parsed leniently or not."""
    return LLMResult(parsed=parsed or {}, raw="{\"mode\": \"act\", \"facts\": [", ok=parsed is not None,
                     model="claude-sonnet-5", input_tokens=9000, output_tokens=4000, truncated=True,
                     error=None if parsed is not None else "truncated: the model hit max_tokens")


def _good(payload: dict | None = None) -> LLMResult:
    return LLMResult(parsed=payload or {"mode": "wait"}, raw="{}", ok=True, model="claude-sonnet-5",
                     input_tokens=9000, output_tokens=900)


def _junk() -> LLMResult:
    return LLMResult(parsed={}, raw="not json", ok=False, model="claude-sonnet-5",
                     input_tokens=9000, output_tokens=50, error="unparseable JSON")


def _gate(client, store=None) -> G.RSiteGate:
    from genios_engine.reason.bundle.budget import NarrativeBudget
    return G.RSiteGate(org_id=ORG, engine=None, client=client, store=store,
                       activated=frozenset({"expert_review"}),
                       budget=NarrativeBudget.for_site(S.SITE_EXPERT, org_id=ORG))


def _consult(gate, *, validate=None, repair=G.REPAIR_ANY):
    seen = []

    def _validate(payload):
        seen.append(payload)
        if validate is None:
            return dict(payload), (), {"accepted": True}
        return validate(payload)
    result = gate.consult(site=S.SITE_EXPERT, cache_key="k", build_prompt=lambda fb: "the dossier",
                          validate=_validate, feature="expert_review", repair=repair)
    return result, seen


def test_a_cut_answer_that_did_not_parse_is_truncated_and_never_retried():
    client, store = _Client(_cut()), _Store()
    result, seen = _consult(_gate(client, store))
    assert result.outcome == S.OUTCOME_TRUNCATED == "truncated"
    assert client.calls == 1 and seen == [] and result.value is None
    assert result.reason_codes == ("truncated_at_the_token_ceiling",)
    assert result.attempts == 1 and result.cost_micro_usd > 0          # what it cost is still counted
    assert store.calls[-1]["outcome"] == "truncated"


def test_a_cut_answer_that_parsed_leniently_is_never_used_as_whole():
    """`parse_json_lenient` closes an unterminated object: a cut answer can come back ok=True."""
    client = _Client(_cut(parsed={"mode": "act", "facts": []}))
    result, seen = _consult(_gate(client))
    assert result.outcome == S.OUTCOME_TRUNCATED and seen == [] and client.calls == 1


def test_a_truncated_consult_falls_back_and_its_receipt_says_so():
    assert S.OUTCOME_TRUNCATED in S.OUTCOMES and S.OUTCOME_TRUNCATED in S.FALLBACK_OUTCOMES
    receipt = L.SiteReceipt(site=S.SITE_EXPERT, outcome=S.OUTCOME_TRUNCATED,
                            generation="template_fallback", cache_key="k")
    assert receipt.fell_back


def _refuse(payload):
    return None, ("number_not_in_dossier",), {"refused": "number_not_in_dossier",
                                              "feedback": "use only the dossier's numbers"}


def test_syntax_only_never_retries_a_substantive_refusal():
    client = _Client(_good(), _good())
    result, seen = _consult(_gate(client), validate=_refuse, repair=G.REPAIR_SYNTAX)
    assert result.outcome == S.OUTCOME_FAILED_VALIDATION and client.calls == 1 and len(seen) == 1
    assert result.reason_codes == ("number_not_in_dossier",)


def test_syntax_only_repairs_an_answer_that_was_not_json_once():
    client = _Client(_junk(), _good())
    result, seen = _consult(_gate(client), repair=G.REPAIR_SYNTAX)
    assert result.outcome == S.OUTCOME_RAN and client.calls == 2 and result.attempts == 2


def test_by_default_a_refusal_is_still_retried_once_as_before():
    client = _Client(_good(), _good())
    result, _seen = _consult(_gate(client), validate=_refuse)
    assert result.outcome == S.OUTCOME_FAILED_VALIDATION and client.calls == 2


def _misshapen(detail="an expert review says its frame"):
    return None, (G.MALFORMED,), {"refused": G.MALFORMED, "detail": detail,
                                  "feedback": "Your previous answer did not meet the stated rules."}


def _consult_seeing(gate, validate, *, repair=G.REPAIR_SYNTAX):
    """`_consult`, also keeping the feedback each prompt was built with."""
    told = []

    def _prompt(feedback):
        told.append(feedback)
        return "the dossier"
    result = gate.consult(site=S.SITE_EXPERT, cache_key="k", build_prompt=_prompt, validate=validate,
                          feature="expert_review", repair=repair)
    return result, told


def test_syntax_only_repairs_a_misshapen_answer_once_and_says_what_was_wrong():
    client = _Client(_good(), _good())
    answers = [_misshapen(), ({"mode": "wait"}, (), {"accepted": True})]
    result, told = _consult_seeing(_gate(client), lambda payload: answers.pop(0))
    assert result.outcome == S.OUTCOME_RAN and client.calls == 2 and result.attempts == 2
    assert told[0] is None and "an expert review says its frame" in told[1]
    assert "shape" in told[1]
    assert G.MALFORMED == "malformed"                  # the ledger's word: reason codes are counted by it


def test_a_misshapen_answer_twice_ends_refused_after_its_one_repair():
    client = _Client(_good(), _good(), _good())
    result, told = _consult_seeing(_gate(client), lambda payload: _misshapen())
    assert result.outcome == S.OUTCOME_FAILED_VALIDATION and client.calls == 2
    assert result.reason_codes == (G.MALFORMED,) and len(told) == 2


def test_a_misshapen_answer_also_refused_on_substance_is_not_repaired():
    client = _Client(_good(), _good())
    both = (None, (G.MALFORMED, "number_not_in_dossier"), {"refused": G.MALFORMED, "detail": "x"})
    result, told = _consult_seeing(_gate(client), lambda payload: both)
    assert result.outcome == S.OUTCOME_FAILED_VALIDATION and client.calls == 1 and len(told) == 1


def test_run_site_carries_a_misshapen_answers_detail_to_its_one_repair():
    client = _Client(_good(), _good())
    told: list = []
    calls = []

    def _parse(payload):
        calls.append(payload)
        if len(calls) == 1:
            raise L.SiteRejection(G.MALFORMED, "an expert review states at least one fact")
        return {"review": "ok"}

    def _prompt(feedback):
        told.append(feedback)
        return "the dossier"
    result = L.run_site(site=S.SITE_EXPERT, org_id=ORG, seed={"file": "f"}, precondition=True,
                        build_prompt=_prompt, parse=_parse, fallback=lambda: {"review": None},
                        gate=_gate(client), feature="expert_review", repair=G.REPAIR_SYNTAX)
    assert result.receipt.outcome == S.OUTCOME_RAN and client.calls == 2
    assert "an expert review states at least one fact" in told[1]


def test_a_repair_nobody_named_is_refused():
    with pytest.raises(ValueError, match="repair"):
        _consult(_gate(_Client(_good())), repair="substance")


def test_run_site_carries_the_repair_to_the_gate():
    client = _Client(_good(), _good())

    def _parse(payload):
        raise L.SiteRejection("number_not_in_dossier", "32")
    result = L.run_site(site=S.SITE_EXPERT, org_id=ORG, seed={"file": "f"}, precondition=True,
                        build_prompt=lambda fb: "the dossier", parse=_parse,
                        fallback=lambda: {"review": None}, gate=_gate(client),
                        feature="expert_review", repair=G.REPAIR_SYNTAX)
    assert result.receipt.outcome == S.OUTCOME_FAILED_VALIDATION and client.calls == 1
