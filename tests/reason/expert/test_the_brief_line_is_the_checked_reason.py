"""STEP-13 · the expert pass proposes a kind in its CHECKED reason (crosscheck X19).

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/expert/test_the_brief_line_is_the_checked_reason.py -q

Tree `yc2_w27_s13` M35.C3.L-integration.V2.U05 (`reason/expert/sweep`). The pass wrote a proposed kind into the
brief's pending line from the review's RAW `why` (`kind_proposal.propose_kind` read `pk.why`): a number the
check corrected went to the founder uncorrected. The pass now hands the proposal the reason as checked
(`CardWords.kind`) — here a quiet of "30 days" its calculator says is 10 (Kunal's file) and 20 (Asha's).
"""
from __future__ import annotations

import pytest

from genios_engine.reason.expert import sweep as P
from tests.reason.expert.test_the_expert_pass import _Expert, _pass, world  # noqa: F401 — the fixture

pytestmark = pytest.mark.pg


def test_the_pass_proposes_the_kind_in_the_words_the_check_let_stand(world, monkeypatch):
    store, now = world

    class _Proposing(_Expert):
        def call(self, prompt, *, max_tokens=400):
            answer = super().call(prompt, max_tokens=max_tokens)
            answer.parsed["facts"] = [{"claim": "the file has gone quiet 30 days",
                                       "evidence": ["num:days_quiet"]}]
            answer.parsed["proposed_kind"] = {"kind": "investor", "evidence": ["num:days_quiet"],
                                              "why": "the file has gone quiet 30 days, as a fund does"}
            return answer
    asked: list[dict] = []
    monkeypatch.setattr(P, "propose_kind", lambda *a, **kw: asked.append(kw))
    receipt, _ = _pass(store, now, llm=_Proposing())
    assert receipt["checked"] == {"shown": 2}, receipt
    assert sorted(kw["why"] for kw in asked) == ["the file has gone quiet 10 days, as a fund does",
                                                 "the file has gone quiet 20 days, as a fund does"]
    assert all("30" not in kw["why"] and kw["review"].proposed_kind.why.endswith("30 days, as a fund does")
               for kw in asked), "the raw reason rides on the review; the line is written from the checked one"
