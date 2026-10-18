"""STEP-07 · draft review reads the company brief — before the facts it checks a draft against.

    .venv/bin/python -m pytest tests/reason/moments/test_draft_review_reads_the_company_brief.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… (adds the route, end to end)

Tree `yc2_w27_s07 · M25.C5.L-logic.V2.U10`. Draft review checked a draft against "what the sender's
company knows" while knowing nothing about the company itself (`speedrun008/YC-II W27/` STEP-07 §1,
§8.1). Its one model call now carries the tenant's brief as its own paragraph after the role, before
the facts, the findings and the fenced draft. The route reads the brief once per draft, and the
draft's dedupe key carries the brief's version, so notes made under a changed brief are not
suppressed as duplicates of the old brief's. A tenant with no accepted line sees the prompt and the
key exactly as they were.
"""
from __future__ import annotations

import os
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.api import moment_routes
from genios_engine.contracts.company_brief import CompanyBrief, CompanyBriefLine, compose
from genios_engine.reason.moments import draft_review as DR
from genios_engine.reason.moments import store as M
from tests.test_moments_pg import H, _engine, _evaluate, _workspace, client  # noqa: F401

URL = os.environ.get("GENIOS_TEST_DATABASE_URL")
ORG = "org_s07_draft_review"
DRAFT = "Hi Priya, great that we are still in negotiation - sending the order form today."
FACTS = [{"node_id": "n_deal", "name": "Acme deal", "field": "deal.stage",
          "value": "closed lost"}]
FINDINGS = [{"text": "Your draft says “negotiation”, but the deal stage changed to “closed lost”."}]
BRIEF = compose(org_id=ORG, company="Nimbus Labs", founder="Arjun Rao",
                us=("arjun@nimbuslabs.test",),
                lines=[CompanyBriefLine(line_id="l1", section="goals",
                                        text="raise the pre-seed round")])
BLOCK = BRIEF.prompt_block()
NOTE = '{"notes": [{"text": "The deal is marked closed lost.", "facts": ["F1"]}]}'


def _transport(monkeypatch, *, answer: str = '{"notes": []}') -> list[str]:
    """Stand in the model's transport (and only it): every prompt sent lands in the list."""
    sent: list[str] = []

    class FakeAnthropic:
        def __init__(self, **_kw):
            self.messages = SimpleNamespace(create=self._create)

        def _create(self, **kw):
            sent.append(kw["messages"][0]["content"])
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text=answer)],
                usage=SimpleNamespace(input_tokens=10, output_tokens=2,
                                      cache_read_input_tokens=0, cache_creation_input_tokens=0))

    monkeypatch.setattr("anthropic.Anthropic", FakeAnthropic)
    return sent


def _hermetic_settings(monkeypatch) -> None:
    monkeypatch.setattr("genios_engine.platform.config.get_settings",
                        lambda: SimpleNamespace(use_real_llm=True, anthropic_api_key="sk-test"))


def _prompt(monkeypatch, **kw) -> str:
    sent = _transport(monkeypatch)
    _hermetic_settings(monkeypatch)
    DR.llm_notes(None, org_id=ORG, facts=FACTS, findings=FINDINGS, draft=DRAFT,
                 digest=DR.draft_digest(DRAFT), deadline=time.monotonic() + 3, **kw)
    (prompt,) = sent
    return prompt


def test_the_block_is_its_own_paragraph_before_the_facts(monkeypatch):
    """(a) After the role, before the facts, the findings and the fenced draft."""
    p = _prompt(monkeypatch, company_brief=BLOCK)
    at = p.index(BLOCK)
    assert p.index("You check an email/chat DRAFT") < at < p.index("FACTS (current")
    assert at < p.index("FINDINGS ALREADY MADE") < p.index("DRAFT (sha256")
    assert at < p.index("<<<") < p.index(DRAFT), "the brief is never inside the draft's fence"
    assert "\n\n" + BLOCK.strip() + "\n\n" in p, "the brief is its own paragraph"


def test_no_brief_leaves_the_prompt_byte_for_byte(monkeypatch):
    """(b) No accepted line: the prompt is the one `llm_notes` sends without the parameter."""
    plain = _prompt(monkeypatch)
    assert _prompt(monkeypatch, company_brief="") == plain
    assert _prompt(monkeypatch, company_brief=CompanyBrief(org_id=ORG).prompt_block()) == plain
    assert "COMPANY BRIEF" not in plain
    # The slot is the template's only change: emptied, the role and the facts touch again.
    assert ("replacement wording.\n\nFACTS (current"
            in DR._PROMPT.replace("{company_brief}", ""))


class _Engine:
    @contextmanager
    def connect(self):
        yield SimpleNamespace()


def test_review_hands_the_block_to_its_one_model_call(monkeypatch):
    """(c) `review` → `_compute` → `llm_notes` → the prompt the model is sent. Only the graph
    reads and the transport are stood in."""
    from genios_engine.reason.moments import recall as R
    from genios_engine.reason.moments import slice as S
    monkeypatch.setattr(R, "resolve", lambda c, **kw: ([SimpleNamespace(node_id="n_priya")], None))
    monkeypatch.setattr(DR, "owed_notes", lambda c, **kw: [])
    monkeypatch.setattr(DR, "related_nodes", lambda c, **kw: ["n_priya", "n_deal"])
    monkeypatch.setattr(S, "recent_changes", lambda c, **kw: [])
    monkeypatch.setattr(DR, "current_facts", lambda c, **kw: FACTS)
    monkeypatch.setattr(DR, "critique_notes", lambda *a, **kw: [])
    sent = _transport(monkeypatch, answer=NOTE)
    _hermetic_settings(monkeypatch)
    out = DR.review(_Engine(), org_id=ORG, email="arjun@nimbuslabs.test", participants=[],
                    entities=["Priya Shah"], draft=DRAFT, seat_id="seat_1", company_brief=BLOCK)
    assert out is not None and out["subject_ids"] == ["n_priya"]
    (prompt,) = sent
    assert prompt.index(BLOCK) < prompt.index("FACTS (current") < prompt.index(DRAFT)


def test_the_draft_key_moves_with_the_brief_version_and_not_without_one():
    """(d) Notes made under one brief are not duplicates of the notes the next brief makes."""
    seat, subjects = "seat_s07", ["n_priya"]
    before = M.cache_key(seat_id=seat, capability_id=DR.CAPABILITY_ID, subject_ids=subjects,
                         trigger=M.trigger_digest(DR.CAPABILITY_ID, DR.draft_digest(DRAFT)),
                         subject_version="draft")           # the key as it was before STEP-07
    assert moment_routes._draft_key(seat, subjects, DRAFT) == before
    assert moment_routes._draft_key(seat, subjects, DRAFT, "") == before
    one = moment_routes._draft_key(seat, subjects, DRAFT, BRIEF.version)
    other = compose(org_id=ORG, company="Nimbus Labs", founder="Arjun Rao",
                    lines=[CompanyBriefLine(line_id="l2", section="goals",
                                            text="land three design partners")]).version
    assert one != before
    assert moment_routes._draft_key(seat, subjects, DRAFT, other) not in (one, before)
    assert moment_routes._draft_key(seat, subjects, DRAFT, BRIEF.version) == one


# ── the route, end to end, on real Postgres ──────────────────────────────────────────────────────
@pytest.mark.pg
@pytest.mark.skipif(not URL, reason="GENIOS_TEST_DATABASE_URL not set")
def test_the_route_reads_the_tenants_brief_and_the_model_receives_it(client, monkeypatch):  # noqa: F811
    """(c) + (d) through `POST /v1/moments/evaluate` with `draft_text`: the same draft before and
    after the founder accepts a line — first the old prompt and the old key, then the brief in the
    prompt and its version in the key."""
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.platform import company_brief as CB
    from genios_engine.platform import company_brief_store as store
    from genios_engine.platform.config import get_settings

    ws = _workspace(client)
    org, seat = ws["org"], ws["member"]["seat_id"]
    for token, path, body in ((ws["owner"]["token"], "/v1/capture/policy",
                               {"draft_assist_allowed": True}),
                              (ws["member"]["token"], "/v1/capture/settings",
                               {"draft_assist": True})):
        assert client.put(path, json=body, headers=H(token)).status_code == 200
    graph = GraphStore(engine=_engine())
    now = datetime.now(timezone.utc)
    with graph.engine.begin() as c:
        comp = graph.find_or_create_node(c, org_id=org, node_type="company",
                                         canonical_key="acme.test", display_name="Acme",
                                         event_id="seed")
        priya = graph.find_or_create_node(c, org_id=org, node_type="person",
                                          canonical_key="priya@acme.test",
                                          display_name="Priya Shah", event_id="seed")
        deal = graph.find_or_create_node(c, org_id=org, node_type="deal",
                                         canonical_key="deal:" + comp, display_name="Acme deal",
                                         event_id="seed")
        for verb, frm, to in (("works_at", priya, comp), ("owns", comp, deal)):
            graph.write_edge(c, org_id=org, edge_type=verb, from_node_id=frm, to_node_id=to,
                             confidence=0.9, occurred_at=now - timedelta(days=3),
                             event_id="seed", evidence={}, source="gmail")
        for value, at in (("negotiation", now - timedelta(days=3)),
                          ("closed lost", now - timedelta(days=1))):
            graph.write_fact(c, org_id=org, subject_node_id=deal, field="deal.stage",
                             value=value, value_type="string", confidence=0.85, occurred_at=at,
                             event_id=f"seed_{uuid.uuid4().hex[:6]}", evidence={},
                             source="gmail", authority_rank=2)
    sent = _transport(monkeypatch)
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "sk-test-not-a-real-key")
    participants = [{"name": "Priya Shah", "email": "priya@acme.test"}]

    def keys() -> set[str]:
        with _engine().connect() as c:
            return {r[0] for r in c.execute(text("select key from moment_cache where org_id = :o"),
                                            {"o": org})}

    first = _evaluate(client, ws["member_dev"], participants=participants, draft_text=DRAFT)
    assert first.status_code == 200, first.text
    assert len(sent) == 1 and "COMPANY BRIEF" not in sent[0]
    with _engine().connect() as c:                  # the subjects the review resolved, as stored
        subjects = list(c.execute(text(
            "select subject_node_ids from moments where org_id = :o and capability_id = :cap"),
            {"o": org, "cap": DR.CAPABILITY_ID}).scalar() or [])
    assert priya in subjects
    assert moment_routes._draft_key(seat, subjects, DRAFT) in keys()

    with _engine().begin() as c:
        store.add(c, org_id=org, section="goals", words="raise the pre-seed round",
                  decided_by="founder", at=now)
    with _engine().connect() as c:
        brief = CB.brief_for(c, org)
    assert brief.version and "raise the pre-seed round" in brief.prompt_block()

    again = _evaluate(client, ws["member_dev"], participants=participants, draft_text=DRAFT)
    assert again.status_code == 200, again.text
    assert len(sent) == 2
    prompt, block = sent[1], brief.prompt_block()
    assert prompt.index(block) < prompt.index("FACTS (current") < prompt.index(DRAFT)
    assert moment_routes._draft_key(seat, subjects, DRAFT, brief.version) in keys()
