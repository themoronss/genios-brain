"""STEP-07 · the drafter proposes the company brief from patterns — and can only propose.

    pytest tests/reason/test_brief_drafter.py -q

Tree `yc2_w27_s07 · M25.C3.L-logic.V3.U02`. One Sonnet-class call (`06` D28) over memory patterns and
the brief in force. Every line it returns is a PROPOSAL with the patterns it rests on; nothing is
accepted here. Refuse, never repair: a line in no section, a line with no evidence, an address or a
domain the patterns never showed — each is refused with its reason, so the drafter cannot introduce a
sender the memory never saw. The call is billed as `company_brief_draft`, a refused answer too.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from genios_engine.context.llm.client import LLMResult
from genios_engine.contracts.company_brief import CompanyBrief
from genios_engine.reason import brief_drafter as D

NOW = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)

PATTERNS = {
    "company": "Nimbus Labs", "founder": "Arjun Rao", "us": ["arjun@nimbus.test"], "window_days": 180,
    "items": [
        {"id": "p1", "kind": "correspondent", "address": "pankaj@fund1.test", "name": "Pankaj",
         "from_them": 3, "to_them": 1, "first": "2026-09-01", "last": "2026-10-04"},
        {"id": "p2", "kind": "domain", "domain": "sampark.gov.in", "mail": 2, "archived": 2,
         "senders": 1, "looks": "government"},
        {"id": "p3", "kind": "introducer", "address": "boardy@boardy.ai", "intros": 2, "people": 2,
         "followed_up": 1, "called_introducer": 1},
        {"id": "p4", "kind": "wave", "day": "2026-08-11",
         "domains": ["fund1.test", "fund2.test", "fund3.test", "fund4.test", "fund5.test"]},
    ],
}


def _line(section, text, *, address=None, domain=None, evidence=("p1",)):
    return {"section": section, "text": text, "address": address, "domain": domain,
            "evidence": list(evidence)}


GOOD = [
    _line("goals", "Raise the pre-seed round", evidence=("p4",)),
    _line("connectors", "Boardy introduces the founder to investors", address="boardy@boardy.ai",
          evidence=("p3",)),
    _line("watchlist", "Startup India portal — DPIIT recognition", domain="sampark.gov.in",
          evidence=("p2",)),
]


def test_the_prompt_carries_every_pattern_and_the_company():
    prompt = D.build_prompt(PATTERNS)
    assert "THE COMPANY: Nimbus Labs, founder Arjun Rao" in prompt
    assert '"address": "boardy@boardy.ai"' in prompt and '"day": "2026-08-11"' in prompt
    assert "You are not shown any message." in prompt and "already holds" not in prompt


def test_the_weekly_prompt_carries_the_brief_in_force():
    prompt = D.build_prompt(PATTERNS, company_brief="COMPANY BRIEF cb-0123456789ab — …\nEND\n")
    assert "Propose only what is missing" in prompt and "COMPANY BRIEF cb-0123456789ab" in prompt


def test_good_lines_survive_with_their_evidence():
    kept, refused = D.parse({"lines": GOOD}, PATTERNS)
    assert refused == []
    assert [(p.section, p.address, p.domain, p.evidence) for p in kept] == [
        ("goals", None, None, ("p4",)), ("connectors", "boardy@boardy.ai", None, ("p3",)),
        ("watchlist", None, "sampark.gov.in", ("p2",))]


@pytest.mark.parametrize("line, why", [
    (_line("people", "Silas at Fund Two", address="silas@invented.test"), "is not in the patterns"),
    (_line("watchlist", "A portal", domain="madeup.gov.in"), "is not in the patterns"),
    (_line("goals", "Raise", evidence=()), "evidence names no pattern"),
    (_line("goals", "Raise", evidence=("p99",)), "evidence names no pattern"),
    (_line("us", "arjun@nimbus.test is us"), "is not one a line may be filed under"),
    (_line("mood", "Optimistic"), "is not one a line may be filed under"),
    (_line("connectors", "Boardy introduces people"), "names the address it writes from"),
    (_line("watchlist", "Government mail", evidence=("p2",)), "a watchlist line names a domain"),
    (_line("goals", "x" * 161), "longer than 160 characters"),
])
def test_a_bad_line_is_refused_with_its_reason_never_repaired(line, why):
    kept, refused = D.parse({"lines": [line]}, PATTERNS)
    assert kept == [] and len(refused) == 1 and why in refused[0], refused


def test_repeats_and_lines_over_the_budget_are_refused():
    many = [_line("goals", f"Goal number {n}") for n in range(D.MAX_PER_SECTION + 1)]
    kept, refused = D.parse({"lines": many + [_line("goals", "Goal number 0")]}, PATTERNS)
    assert len(kept) == D.MAX_PER_SECTION
    assert refused == [f"line {D.MAX_PER_SECTION + 1}: over the line budget",
                       f"line {D.MAX_PER_SECTION + 2}: over the line budget"]
    kept, refused = D.parse({"lines": [GOOD[0], GOOD[0]]}, PATTERNS)
    assert len(kept) == 1 and refused == ["line 2: a repeat of a line above"]


def test_an_answer_without_a_lines_list_is_refused_whole():
    assert D.parse({"brief": "…"}, PATTERNS) == ([], ["the answer has no 'lines' list"])
    assert D.parse(None, PATTERNS) == ([], ["the answer has no 'lines' list"])


# ── the draft: one call, proposals only, billed ──────────────────────────────────────────────

class _Engine:
    @contextmanager
    def connect(self):
        yield object()

    @contextmanager
    def begin(self):
        yield object()


class _Model:
    model = "claude-sonnet-5"

    def __init__(self, result):
        self.result, self.prompts = result, []

    def call(self, prompt, *, max_tokens=4096, **_kw):
        self.prompts.append((prompt, max_tokens))
        return self.result


@pytest.fixture
def seams(monkeypatch):
    from genios_engine.platform import company_brief, company_brief_store
    from genios_engine.reason import brief_patterns

    proposed, accepted = [], []
    monkeypatch.setattr(brief_patterns, "patterns_for", lambda c, org, *, now: PATTERNS)
    monkeypatch.setattr(company_brief, "brief_for", lambda c, org: CompanyBrief(org_id=org))
    monkeypatch.setattr(company_brief_store, "propose",
                        lambda c, **kw: proposed.append(kw) or f"cbl_{len(proposed)}")
    monkeypatch.setattr(company_brief_store, "accept", lambda *a, **kw: accepted.append(kw))
    return proposed, accepted


def _ok(lines):
    return LLMResult(parsed={"lines": lines}, raw="", model="claude-sonnet-5", input_tokens=900,
                     output_tokens=300)


def test_a_draft_writes_proposals_with_their_patterns_and_accepts_nothing(seams):
    proposed, accepted = seams
    costs = []
    model = _Model(_ok(GOOD + [_line("people", "Invented", address="x@invented.test")]))
    out = D.draft_company_brief(_Engine(), "org_1", model, now=NOW,
                                cost_sink=lambda **row: costs.append(row))
    assert (out.proposed, len(out.refused), out.skipped) == (3, 1, None)
    assert accepted == [] and len(model.prompts) == 1 and model.prompts[0][1] == D.MAX_TOKENS
    assert [p["proposed_by"] for p in proposed] == ["drafter"] * 3
    assert proposed[1]["address"] == "boardy@boardy.ai"
    assert proposed[1]["evidence"] == [{"pattern": "p3", "kind": "introducer",
                                        "address": "boardy@boardy.ai", "intros": 2, "people": 2,
                                        "followed_up": 1, "called_introducer": 1}]
    assert costs == [{"org_id": "org_1", "model": "claude-sonnet-5", "purpose": "company_brief_draft",
                      "input_tokens": 900, "output_tokens": 300, "success": True, "error": None}]


def test_a_dry_run_says_what_it_would_propose_and_writes_nothing(seams):
    proposed, _ = seams
    out = D.draft_company_brief(_Engine(), "org_1", _Model(_ok(GOOD)), now=NOW, apply=False)
    assert proposed == [] and out.proposed == 0 and len(out.lines) == 3


def test_a_failed_call_is_billed_and_proposes_nothing(seams):
    proposed, _ = seams
    costs = []
    failed = LLMResult(parsed={}, raw="", model="claude-sonnet-5", input_tokens=900, output_tokens=0,
                       ok=False, error="overloaded")
    out = D.draft_company_brief(_Engine(), "org_1", _Model(failed), now=NOW,
                                cost_sink=lambda **row: costs.append(row))
    assert out.skipped == "model:overloaded" and proposed == []
    assert costs[0]["success"] is False and costs[0]["error"] == "overloaded"


def test_no_model_and_no_patterns_spend_nothing(seams, monkeypatch):
    from genios_engine.reason import brief_patterns

    assert D.draft_company_brief(_Engine(), "org_1", None, now=NOW).skipped == "no_model"
    monkeypatch.setattr(brief_patterns, "patterns_for",
                        lambda c, org, *, now: {**PATTERNS, "items": []})
    model = _Model(_ok(GOOD))
    assert D.draft_company_brief(_Engine(), "org_1", model, now=NOW).skipped == "no_patterns"
    assert model.prompts == []


def test_the_drafter_is_registered_as_a_metered_site_and_off_in_the_golden_chain():
    from tests.replays.model_sites import CHAIN_SITES
    from tests.test_every_llm_call_site_is_metered import _SITES

    assert _SITES["reason/brief_drafter.py"] == {"records": True, "purpose": ("company_brief_draft",)}
    assert CHAIN_SITES["reason/brief_drafter.py"][0] == "off"
