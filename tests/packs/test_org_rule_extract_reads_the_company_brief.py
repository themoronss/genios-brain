"""STEP-07 · org-rule extraction reads the company brief — before the document it reads.

    .venv/bin/python -m pytest tests/packs/test_org_rule_extract_reads_the_company_brief.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… (adds a real sweep over a real canon document)

Tree `yc2_w27_s07 · M25.C5.L-logic.V2.U11`. N-3's T2 read of a policy document was told the document
and nothing about the company that wrote it (`speedrun008/YC-II W27/` STEP-07 §1, §8.1). Its prompt
now carries the tenant's brief as its own paragraph after the role, before the document's kind, title
and fenced text — background only: every field asked back is still a token from a closed set or a
span of the document. The sweep reads the brief once, when it builds its extractor, and hands it to
the factory, so `propose(text, kind, title)` — the protocol every fake implements — is unchanged. A
tenant with no accepted line sends exactly the prompt it sent before.

No key moves in this unit: a document is read once per VERSION (`org_rule_discovery_runs`), which is
the document's identity, not a cache of an answer.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.contracts.company_brief import CompanyBrief, CompanyBriefLine, compose
from genios_engine.feedback import org_rule_ingest
from genios_engine.packs.brains import org_rule_extract as X
from genios_engine.packs.brains.org_discovery import ORG_RULE_CATEGORIES

URL = os.environ.get("GENIOS_TEST_DATABASE_URL")
ORG = "org_s07_org_rules"
NOW = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)
DOC = ("Nimbus Labs Approvals Policy.\n"
       "Contracts above $50,000 require founder approval before signature.\n")
BRIEF = compose(org_id=ORG, company="Nimbus Labs", founder="Arjun Rao",
                us=("arjun@nimbuslabs.test",),
                lines=[CompanyBriefLine(line_id="l1", section="goals",
                                        text="raise the pre-seed round")])
BLOCK = BRIEF.prompt_block()
ARGS = dict(text=DOC, kind="policy", title="Approvals Policy")


class _Model:
    """The transport under the PRODUCTION extractor: records every prompt, finds no rule."""

    model = "fake-t2"

    def __init__(self):
        self.prompts: list[str] = []

    def call(self, prompt, *, max_tokens=4096):
        self.prompts.append(prompt)
        return SimpleNamespace(ok=True, parsed={"rules": []}, error=None, model=self.model,
                               input_tokens=10, output_tokens=2, cache_read_tokens=0,
                               cache_write_tokens=0)


def test_the_block_is_its_own_paragraph_before_the_document():
    """(a) After the role, before the kind, the title and the fenced text."""
    p = X.build_prompt(**ARGS, company_brief=BLOCK)
    at = p.index(BLOCK)
    assert p.index("You are reading ONE internal company document") < at
    assert at < p.index("DOCUMENT KIND: policy") < p.index("DOCUMENT TITLE:")
    assert at < p.index("<<<DOC") < p.index(DOC), "the brief is never inside the document's fence"
    assert "\n\n" + BLOCK.strip() + "\n\n" in p, "the brief is its own paragraph"
    assert X.PROMPT.count("{company_brief}") == 1


def test_no_brief_leaves_the_prompt_byte_for_byte():
    """(b) No accepted line: the prompt is the builder's own without the parameter — and the one
    `propose` formatted before STEP-07."""
    plain = X.build_prompt(**ARGS)
    assert X.build_prompt(**ARGS, company_brief="") == plain
    assert X.build_prompt(**ARGS, company_brief=CompanyBrief(org_id=ORG).prompt_block()) == plain
    assert "COMPANY BRIEF" not in plain
    before = X.PROMPT.replace("{company_brief}", "").format(
        kind="policy", title="Approvals Policy", text=DOC[:X.MAX_DOCUMENT_CHARS],
        categories=json.dumps(sorted(ORG_RULE_CATEGORIES)), max_rules=X.MAX_RULES)
    assert plain == before
    assert "the RULES it states.\n\nDOCUMENT KIND:" in X.PROMPT.replace("{company_brief}", "")


def test_the_extractor_and_its_factory_carry_the_block_to_the_model():
    """(c) The brief rides on the extractor, so the protocol call stays `propose(text, kind,
    title)` — and an extractor built without one sends the prompt it always sent."""
    model = _Model()
    X.LLMOrgRuleExtractor(model, company_brief=BLOCK).propose(**ARGS)
    X.make_org_rule_extractor(model, company_brief=BLOCK).propose(**ARGS)
    X.make_org_rule_extractor(model).propose(**ARGS)
    with_brief = X.build_prompt(**ARGS, company_brief=BLOCK)
    assert model.prompts == [with_brief, with_brief, X.build_prompt(**ARGS)]


class _Engine:
    """Never reached: the sweep's reads are stood in below."""

    def connect(self):
        return self

    def begin(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_the_sweep_reads_the_tenants_brief_once_and_its_extractor_carries_it(monkeypatch):
    """(c) `sweep_org_rule_discovery` → the factory → the extractor → the prompt the model is
    sent, for every document of the sweep; the brief is read once, through the engine."""
    model, asked = _Model(), []

    def current(source, org_id):
        asked.append((source, org_id))
        return BRIEF

    def run(c, *, org_id, event_id, extractor, now):
        extractor.propose(**ARGS)
        return {"proposed": 0}

    engine = _Engine()
    monkeypatch.setattr("genios_engine.platform.company_brief.current", current)
    monkeypatch.setattr("genios_engine.platform.wiring.make_llm_client", lambda: model)
    monkeypatch.setattr(org_rule_ingest, "undiscovered_events",
                        lambda c, *, org_id, limit=25: ["evt_1", "evt_2"])
    monkeypatch.setattr(org_rule_ingest, "run_org_discovery", run)
    out = org_rule_ingest.sweep_org_rule_discovery(ORG, engine=engine, now=NOW)
    assert out["documents"] == 2
    assert model.prompts == [X.build_prompt(**ARGS, company_brief=BLOCK)] * 2
    assert asked == [(engine, ORG)], "once per sweep, through the engine"


def test_an_extractor_handed_in_is_used_as_it_is(monkeypatch):
    """The brief is read only when the sweep builds its own extractor."""
    monkeypatch.setattr("genios_engine.platform.company_brief.current",
                        lambda *a: pytest.fail("the brief was read for an extractor handed in"))
    monkeypatch.setattr(org_rule_ingest, "undiscovered_events", lambda c, *, org_id, limit=25: [])
    out = org_rule_ingest.sweep_org_rule_discovery(ORG, engine=_Engine(), now=NOW,
                                                   extractor=X.LLMOrgRuleExtractor(_Model()))
    assert out["considered"] == 0


# ── a real sweep over a real canon document, on real Postgres ───────────────────────────────────
def _reset(engine, orgs) -> None:
    from genios_engine.api.account_routes import _wipe
    from genios_engine.platform import company_brief as CB
    with engine.begin() as c:
        for org in orgs:
            _wipe(c, org)
            c.execute(text("delete from orgs where id = :o"), {"o": org})
    for org in orgs:
        CB.invalidate(org)


def _seed_policy(c, org: str) -> None:
    """A canon policy document, as the knowledge door files one (`policy:approvals`)."""
    event_id = f"evt_policy_{org}"
    c.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, "
        "source_object_id, dedup_key, actor, occurred_at, internal_kind) values "
        "(:e, :o, 'knowledge', 'internal', 'policy', 'policy:approvals', :dk, "
        "cast('{}' as jsonb), :at, 'policy')"),
        {"e": event_id, "o": org, "dk": f"policy:approvals@v1:{org}", "at": NOW})
    c.execute(text(
        "insert into prepared_content (event_id, org_id, prepared_content_id, clean_text) "
        "values (:e, :o, :p, :t)"), {"e": event_id, "o": org, "p": f"pc_{event_id}", "t": DOC})


@pytest.mark.pg
@pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")
def test_a_real_sweep_reads_the_tenants_brief_into_the_documents_prompt(monkeypatch):
    """(c) The real chain — `undiscovered_events`, `run_org_discovery`, `load_canon_document` —
    with only the transport stood in: the brief the founder accepted is the one the model reads,
    and a tenant without one sends the prompt it always sent."""
    from genios_engine.platform import company_brief as CB
    from genios_engine.platform import company_brief_store as store
    from genios_engine.platform.db import get_engine

    with_brief, without = "org_s07_rules_brief", "org_s07_rules_plain"
    engine = get_engine(URL)
    _reset(engine, (with_brief, without))
    try:
        with engine.begin() as c:
            for org in (with_brief, without):
                c.execute(text("insert into orgs (id, name, locale) values (:o, :o, 'en-US')"),
                          {"o": org})
                _seed_policy(c, org)
            store.add(c, org_id=with_brief, section="goals", words="raise the pre-seed round",
                      decided_by="founder", at=NOW)
        with engine.connect() as c:
            brief = CB.brief_for(c, with_brief)
        assert brief.version and "raise the pre-seed round" in brief.prompt_block()

        for org in (with_brief, without):
            model = _Model()
            monkeypatch.setattr("genios_engine.platform.wiring.make_llm_client", lambda: model)
            out = org_rule_ingest.sweep_org_rule_discovery(org, engine=engine, now=NOW)
            assert (out["documents"], out["failed"]) == (1, 0), out
            (prompt,) = model.prompts
            plain = X.build_prompt(text=DOC, kind="policy", title="Approvals")
            if org == with_brief:
                block = brief.prompt_block()
                assert prompt == X.build_prompt(text=DOC, kind="policy", title="Approvals",
                                                company_brief=block)
                assert prompt.index(block) < prompt.index("DOCUMENT KIND: policy")
            else:
                assert prompt == plain and "COMPANY BRIEF" not in prompt
    finally:
        _reset(engine, (with_brief, without))
