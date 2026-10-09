"""STEP-11 · the drafter proposes each in-motion line's kind of work and its counterparty.

    pytest tests/reason/test_the_drafter_names_the_work.py -q

`reason/brief_drafter.py` (tree `yc2_w27_s11 · M30.C4.L-logic.V1.U03`, `06` D31). A founder's file could
not say what kind of work it is, so the next step's expert could not pick its playbook; D31 has the
brief's in-motion lines name it — the drafter proposes, the founder accepts. So the drafter now asks for
each in-motion line's kind (one of `WORK_KINDS`, or none) and its counterparty (an address or a domain
the patterns show), and refuses — never repairs — a kind off the list, a kind on any other section, or a
counterparty the memory never saw. It still accepts nothing: the kind is written with the proposal, and
the founder decides.
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from genios_engine.context.llm.client import LLMResult
from genios_engine.contracts.company_brief import WORK_KINDS, CompanyBrief
from genios_engine.reason import brief_drafter as D

NOW = datetime(2026, 10, 9, 9, 0, tzinfo=timezone.utc)

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
        {"id": "p5", "kind": "domain", "domain": "lakshya.test", "mail": 4, "archived": 0,
         "senders": 2, "looks": None},
    ],
}


def _line(section, text, *, kind=None, address=None, domain=None, evidence=("p1",)):
    return {"section": section, "text": text, "address": address, "domain": domain, "kind": kind,
            "evidence": list(evidence)}


WORK = [
    _line("in_motion", "Fund One — Pankaj asked for the data room", kind="investor",
          domain="fund1.test"),
    _line("in_motion", "Lakshya — the accelerator application is under review", kind="Program",
          domain="lakshya.test", evidence=("p5",)),
    _line("in_motion", "Startup India recognition on the portal", kind="compliance",
          domain="sampark.gov.in", evidence=("p2",)),
    _line("in_motion", "Boardy's introductions to investors", kind="intro",
          address="boardy@boardy.ai", evidence=("p3",)),
    _line("in_motion", "Five funds written to in one wave", evidence=("p4",)),
]


# ── the prompt ──────────────────────────────────────────────────────────────────────────────────

def test_the_prompt_asks_for_each_in_motion_lines_kind_and_counterparty():
    prompt = D.build_prompt(PATTERNS)
    rules = prompt.split("Return JSON only")[0]
    assert "in_motion line names its kind of work" in rules
    for kind in WORK_KINDS:
        assert f"{kind} (" in rules, f"the prompt never offers the kind {kind!r}"
    assert "counterparty" in rules and "or null when none fits" in rules
    shape = json.loads(prompt.split("in exactly this shape:\n", 1)[1].split("\n", 1)[0])
    assert shape["lines"][0]["kind"] is None and set(shape["lines"][0]) == {
        "section", "text", "address", "domain", "kind", "evidence"}


def test_a_new_prompt_is_a_new_prompt_version():
    assert D.PROMPT_VERSION == "company-brief-draft.v2"


# ── what survives ───────────────────────────────────────────────────────────────────────────────

def test_an_in_motion_line_survives_with_its_kind_and_its_counterparty():
    kept, refused = D.parse({"lines": WORK}, PATTERNS)
    assert refused == []
    assert [(p.kind, p.address, p.domain) for p in kept] == [
        ("investor", None, "fund1.test"), ("program", None, "lakshya.test"),
        ("compliance", None, "sampark.gov.in"), ("intro", "boardy@boardy.ai", None),
        (None, None, None)]


@pytest.mark.parametrize("line, why", [
    (_line("in_motion", "Raising the seed", kind="fundraising"), "is not a kind of work"),
    (_line("in_motion", "Boardy", kind="connector", evidence=("p3",)), "is not a kind of work"),
    (_line("goals", "Raise the seed round", kind="investor"), "only an in-motion line"),
    (_line("watchlist", "Startup India portal", kind="compliance", domain="sampark.gov.in",
           evidence=("p2",)), "only an in-motion line"),
    (_line("in_motion", "Silas at Fund Two", kind="investor", address="silas@invented.test"),
     "is not in the patterns"),
    (_line("in_motion", "Madeup Ventures", kind="investor", domain="madeup.vc"),
     "is not in the patterns"),
])
def test_a_kind_or_counterparty_that_cannot_be_is_refused_never_repaired(line, why):
    kept, refused = D.parse({"lines": [line]}, PATTERNS)
    assert kept == [] and len(refused) == 1 and why in refused[0], refused


# ── the draft: the kind is proposed, and nothing is accepted ───────────────────────────────────

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
        self.prompts.append(prompt)
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
    monkeypatch.setattr(company_brief_store, "add", lambda *a, **kw: accepted.append(kw))
    return proposed, accepted


def _ok(lines):
    return LLMResult(parsed={"lines": lines}, raw="", model="claude-sonnet-5", input_tokens=900,
                     output_tokens=300)


def test_a_draft_proposes_each_lines_kind_and_counterparty_and_accepts_nothing(seams):
    proposed, accepted = seams
    out = D.draft_company_brief(_Engine(), "org_1", _Model(_ok(WORK)), now=NOW)
    assert (out.proposed, out.refused, out.skipped) == (5, (), None)
    assert accepted == []
    assert [(p["section"], p["kind"], p["address"], p["domain"]) for p in proposed] == [
        ("in_motion", "investor", None, "fund1.test"), ("in_motion", "program", None, "lakshya.test"),
        ("in_motion", "compliance", None, "sampark.gov.in"),
        ("in_motion", "intro", "boardy@boardy.ai", None), ("in_motion", None, None, None)]
    assert {p["proposed_by"] for p in proposed} == {"drafter"}


def test_a_dry_run_says_the_kind_it_would_propose_and_writes_nothing(seams):
    proposed, _ = seams
    out = D.draft_company_brief(_Engine(), "org_1", _Model(_ok(WORK)), now=NOW, apply=False)
    assert proposed == [] and out.proposed == 0
    assert [p.kind for p in out.lines] == ["investor", "program", "compliance", "intro", None]


def test_a_line_of_another_section_is_proposed_with_no_kind_as_before(seams):
    proposed, _ = seams
    lines = [{k: v for k, v in _line("goals", "Raise the seed round", evidence=("p4",)).items()
              if k != "kind"},                                   # an answer that names no kind at all
             _line("connectors", "Boardy introduces the founder to investors",
                   address="boardy@boardy.ai", evidence=("p3",))]
    out = D.draft_company_brief(_Engine(), "org_1", _Model(_ok(lines)), now=NOW)
    assert out.proposed == 2 and [p["kind"] for p in proposed] == [None, None]
