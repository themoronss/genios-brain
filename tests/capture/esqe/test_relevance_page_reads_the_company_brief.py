"""STEP-07 · the relevance page is told WHICH company's operation it is judging.

    pytest tests/capture/esqe/test_relevance_page_reads_the_company_brief.py -q

Tree `yc2_w27_s07 · M25.C5.L-logic.V2.U02`. LLM-5 asks "is this message about this company's own
operation?" and was never told which company (`speedrun008/YC-II W27/` STEP-07 §8.1). The page now
carries the tenant's brief block — read once when the lane is built (`platform/wiring.
make_semantic_lane`) — after its opening line and before the items; a tenant with no brief is asked
exactly what it was asked before.
"""
from __future__ import annotations

import re

from genios_engine.capture.esqe import relevance as R
from genios_engine.context.llm.client import LLMResult
from genios_engine.contracts.company_brief import CompanyBriefLine, compose

BRIEF = compose(org_id="o", company="Nimbus Labs", founder="Arjun Rao", us=(),
                lines=[CompanyBriefLine(line_id="l1", section="goals", text="raise the pre-seed round")])


class _Model:
    model = "fake"

    def __init__(self):
        self.prompts = []

    def call(self, prompt, *, max_tokens=1024, **_kw):
        self.prompts.append(prompt)
        return LLMResult(parsed={"verdicts": [{"item": 1, "business": True, "category": "working"}]},
                         raw="", model=self.model)


def _candidate():
    return R.RelevanceCandidate(event_id="e1", page_key="m1", sender="someone@fund.test",
                                sender_known=False, headers={}, subject="Following up",
                                snippet="Would love to see the deck.")


def test_the_page_prompt_carries_the_brief_before_the_items():
    model = _Model()
    R._judge_batch([_candidate()], model, company_brief=BRIEF.prompt_block())
    prompt = model.prompts[0]
    assert prompt.startswith("You are classifying messages for a company's business-intelligence")
    assert prompt.index("COMPANY BRIEF " + BRIEF.version) < prompt.index("ITEMS:\n")
    assert prompt.index("raise the pre-seed round") < prompt.index("item 1:")


def test_no_brief_is_the_prompt_as_it_was():
    with_empty, without = _Model(), _Model()
    R._judge_batch([_candidate()], with_empty, company_brief="")
    R._judge_batch([_candidate()], without)
    # Each prompt mints its own fence nonce; with it held equal the two are the same string.
    unfenced = [re.sub(r"<<<(CONTENT|END)_[0-9a-f]+>>>", r"<<<\1>>>", p)
                for p in with_empty.prompts + without.prompts]
    assert unfenced[0] == unfenced[1] and "COMPANY BRIEF" not in without.prompts[0]


def test_the_page_built_with_a_brief_asks_with_it():
    model = _Model()
    page = R.RelevancePage(llm=model, org_id="o", company_brief=BRIEF.prompt_block())
    page.prime([_candidate()], claims_unknown=True)
    assert model.prompts and "COMPANY BRIEF " + BRIEF.version in model.prompts[0]
