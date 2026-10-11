"""STEP-12 · one review — through the one gate, held to its dossier, kept once per fingerprint.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/expert/test_one_review.py -q

`reason/expert/review.py` (tree `yc2_w27_s12` M32.C3.L-logic.V1.U02). R-7 through `run_site` and the gate:
the checklist prompt over the file's dossier; a valid answer is a `valid` row; a refusal on substance a
`refused` row with every problem, never repaired; a misshapen answer repaired once — and `failed` if it
stays misshapen; a cut answer `truncated`, never retried; no budget left `over_budget`, with no call; a
call that raised `failed`. Each row keeps what the file was, what triggered the review, the dossier's
digest, the prompt version and the cost. A fingerprint a standing row answers costs no consult; a
failed one is retried and replaced; a switched-off feature writes nothing.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.llm.client import LLMResult
from genios_engine.reason.bundle import gate as G
from genios_engine.reason.bundle import sites as S
from genios_engine.reason.bundle.budget import NarrativeBudget
from genios_engine.reason.expert import dossier as D
from genios_engine.reason.expert import fingerprint as F
from genios_engine.reason.expert import review as RV
from genios_engine.reason.expert import store as R
from genios_engine.reason.expert import triggers as T
from genios_engine.reason.expert.prompt import PROMPT_VERSION
from tests.reason.expert.test_the_dossier import _parts, _review

pytestmark = pytest.mark.pg

ORG = "org_s12_one_review"
AT = datetime(2026, 10, 10, 12, 30, tzinfo=timezone.utc)
PARTS = _parts()
DOSSIER = D.build_dossier(PARTS)
INPUTS = F.fingerprint_inputs(PARTS, model="claude-sonnet-5", prompt_version=PROMPT_VERSION)
FP = F.file_fingerprint(PARTS, model="claude-sonnet-5", prompt_version=PROMPT_VERSION)
TRIGGERS = T.triggers_for(PARTS, INPUTS)
GOOD = _review("evt_005", "Hi Kunal, booking it now.").as_mapping()


def _answer(payload=None, *, ok=True, truncated=False, raw="{}") -> LLMResult:
    return LLMResult(parsed=payload or {}, raw=raw, ok=ok, model="claude-sonnet-5", input_tokens=9000,
                     output_tokens=900, truncated=truncated,
                     error=None if ok else "unparseable JSON")


class _Client:
    model = "claude-sonnet-5"

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts: list[str] = []

    def call(self, prompt, *, max_tokens=400):
        self.prompts.append(prompt)
        answer = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(answer, Exception):
            raise answer
        return answer


def _gate(client, *, activated=frozenset({"expert_review"}), spent=0) -> G.RSiteGate:
    budget = NarrativeBudget.for_site(S.SITE_EXPERT, org_id=ORG)
    budget.charge(spent)
    return G.RSiteGate(org_id=ORG, engine=None, client=client, store=None, activated=activated,
                       budget=budget)


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'one_review@example.test')"),
                  {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _review_with(engine, client, **gate):
    return RV.review_file(engine, org_id=ORG, dossier=DOSSIER, fingerprint=FP, inputs=INPUTS,
                          triggers=TRIGGERS, gate=_gate(client, **gate), at=AT)


def _row(engine):
    with engine.connect() as c:
        return R.read_review(c, ORG, DOSSIER.file_id, FP)


def test_a_valid_answer_is_one_valid_row_that_keeps_everything(engine):
    client = _Client(_answer(GOOD))
    result = _review_with(engine, client)
    assert (result.status, result.written, result.reason) == (R.VALID, True, None)
    assert result.review == _review("evt_005", "Hi Kunal, booking it now.")
    row = _row(engine)
    assert row.review == result.review and row.inputs == INPUTS and row.dossier_digest == DOSSIER.digest
    assert row.triggers == (("first_look", "never judged"),) and row.prompt_version == PROMPT_VERSION
    assert (row.model, row.input_tokens, row.output_tokens) == ("claude-sonnet-5", 9000, 900)
    assert row.cost_micro_usd == result.receipt.cost_micro_usd > 0 and row.reviewed_at == AT
    assert len(client.prompts) == 1 and DOSSIER.text in client.prompts[0]          # the checklist prompt


def test_a_refusal_on_substance_is_recorded_with_every_problem_and_never_repaired(engine):
    bad = _review("evt_999", "Hi Kunal, booking it at 4317.").as_mapping()
    client = _Client(_answer(bad), _answer(GOOD))
    result = _review_with(engine, client)
    assert result.status == R.REFUSED and len(client.prompts) == 1
    assert "unknown_evidence: fact 1 cites evt_999" in result.reason
    assert "number_not_in_dossier: 4317" in result.reason
    row = _row(engine)
    assert row.status == R.REFUSED and row.review is None and row.raw == bad      # kept as data


def test_a_misshapen_answer_is_repaired_once_and_then_valid(engine):
    client = _Client(_answer({"mode": "act"}), _answer(GOOD))
    result = _review_with(engine, client)
    assert result.status == R.VALID and len(client.prompts) == 2
    assert "an expert review states at least one fact" in client.prompts[1]


def test_still_misshapen_after_its_repair_is_failed_and_may_be_retried(engine):
    client = _Client(_answer({"mode": "act"}), _answer({"mode": "act"}))
    result = _review_with(engine, client)
    assert result.status == R.FAILED and len(client.prompts) == 2
    assert result.reason.startswith("malformed: an expert review states at least one fact")
    again = _review_with(engine, _Client(_answer(GOOD)))
    assert again.status == R.VALID and again.written and _row(engine).status == R.VALID


def test_a_misshapen_answer_whose_repair_the_day_cannot_afford_says_both(engine):
    """The first call fits the day's budget; its repair does not — the row says why it stopped."""
    from genios_engine.reason.bundle.budget import REASON_DAILY_EXHAUSTED, estimate_micro_usd
    from genios_engine.reason.expert.prompt import build_prompt
    estimate = estimate_micro_usd(site=S.SITE_EXPERT, prompt_chars=len(build_prompt(DOSSIER)),
                                  max_output_tokens=S.max_output_tokens(S.SITE_EXPERT))
    client = _Client(_answer({"mode": "act"}), _answer(GOOD))
    result = _review_with(engine, client, spent=2_000_000 - estimate - 1_000)
    assert result.status == R.FAILED and len(client.prompts) == 1
    assert result.reason == ("malformed: an expert review states at least one fact; "
                             f"{REASON_DAILY_EXHAUSTED}")


def test_an_answer_that_is_not_json_twice_is_failed(engine):
    client = _Client(_answer(ok=False, raw="no json"), _answer(ok=False, raw="still none"))
    result = _review_with(engine, client)
    assert result.status == R.FAILED and result.reason == "unparseable_generation"


def test_a_cut_answer_is_truncated_never_retried_and_stands(engine):
    client = _Client(_answer(GOOD, truncated=True))
    result = _review_with(engine, client)
    assert result.status == R.TRUNCATED and len(client.prompts) == 1
    assert result.reason == "truncated_at_the_token_ceiling" and result.receipt.cost_micro_usd > 0
    again = _review_with(engine, _Client(_answer(GOOD)))
    assert again.status == R.TRUNCATED and again.receipt is None and not again.written


def test_no_budget_left_is_over_budget_with_no_call_and_is_carried(engine):
    client = _Client(_answer(GOOD))
    result = _review_with(engine, client, spent=2_000_000)
    assert result.status == R.OVER_BUDGET and client.prompts == [] and result.written
    row = _row(engine)
    assert row.cost_micro_usd == 0 and row.model == "claude-sonnet-5" and row.reason
    tomorrow = _review_with(engine, _Client(_answer(GOOD)))                      # carried, then run
    assert tomorrow.status == R.VALID and tomorrow.written


def test_a_call_that_raised_is_failed(engine):
    client = _Client(RuntimeError("connection reset"), RuntimeError("connection reset"))
    result = _review_with(engine, client)
    assert result.status == R.FAILED and result.reason == "model_call_raised"


def test_a_fingerprint_a_standing_row_answers_costs_no_consult(engine):
    _review_with(engine, _Client(_answer(GOOD)))
    client = _Client(_answer(GOOD))
    again = _review_with(engine, client)
    assert (again.status, again.written, again.receipt) == (R.VALID, False, None)
    assert again.review == _review("evt_005", "Hi Kunal, booking it now.") and client.prompts == []


def test_a_switched_off_feature_writes_nothing_and_says_why(engine):
    client = _Client(_answer(GOOD))
    result = _review_with(engine, client, activated=frozenset())
    assert (result.status, result.written) == (None, False) and client.prompts == []
    assert result.reason == "l4_expert_review_not_activated"
    assert _row(engine) is None


def test_the_force_fail_switch_writes_nothing(engine):
    client = _Client(_answer(GOOD))
    with G.force_failed():
        result = _review_with(engine, client)
    assert result.status is None and result.receipt.outcome == S.OUTCOME_FORCE_FAILED
    assert _row(engine) is None and client.prompts == []
