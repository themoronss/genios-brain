"""STEP-07 · the AI junk filter reads the company brief, skips its senders, and never sees a raw subject.

    pytest tests/capture/gate/test_the_junk_filter_reads_the_company_brief.py -q

Tree `yc2_w27_s07 · M25.C4.L-logic.V2.U05`. The filter decided keep-or-archive blind: no company, no
sender, one email at a time (`speedrun008/YC-II W27/` STEP-03 §8.2, STEP-07 §8.1). Now, once its tenant
is bound (`bind_costs(…, brief_source=…)`, as `platform/wiring.make_relevance_classifier` binds it):

  * both prompts carry the brief's block after their opening paragraph, before the mail they judge —
    and a tenant with no brief is asked exactly what it was asked before;
  * its batch is not spent on a sender the brief names (W-07 never asks it; `03` F79's brief half);
  * the single-mail prompt sends the subject MASKED, as the batch always did (`03` F78).
"""
from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.gate import relevance as R
from genios_engine.capture.gate.context import GateContext
from genios_engine.capture.preprocess.preprocess import preprocess
from genios_engine.context.llm.client import LLMResult
from genios_engine.contracts.company_brief import CompanyBrief, CompanyBriefLine, compose
from genios_engine.contracts.source_event import Actor, SourceEvent

T = datetime(2026, 9, 24, tzinfo=timezone.utc)
BRIEF = compose(org_id="o", company="Nimbus Labs", founder="Arjun Rao", us=("arjun@nimbuslabs.test",),
                lines=[CompanyBriefLine(line_id="l1", section="goals", text="raise the pre-seed round")])


class _Model:
    model = "fake"

    def __init__(self, answer):
        self.answer, self.prompts = answer, []

    def call(self, prompt, *, max_tokens=4096, **_kw):
        self.prompts.append(prompt)
        return LLMResult(parsed=self.answer, raw="", model=self.model)


def _objs():
    return [RawObject("gmail", "email_message", "m1", T, actor_email="updates@startupsetu.gov.test",
                      raw={"subject": "Application status", "snippet": "Under Examination."}),
            RawObject("gmail", "email_message", "m2", T, actor_email="deals@shop.test",
                      raw={"subject": "50% off", "snippet": "This week only."})]


def test_the_batch_prompt_carries_the_brief_before_the_mail(monkeypatch):
    model = _Model([{"i": 0, "disposition": "keep", "relevance": 0.9, "reason": "x"},
                    {"i": 1, "disposition": "drop", "relevance": 0.05, "reason": "x"}])
    monkeypatch.setattr("genios_engine.platform.company_brief.current", lambda source, org: BRIEF)
    gate = R.LLMRelevanceClassifier(model)
    gate.bind_costs(lambda **_k: None, "o", brief_source=SimpleNamespace(engine=None))
    gate.prime(_objs())
    prompt = model.prompts[0]
    assert prompt.startswith("You are a junk filter deciding which of SEVERAL emails")
    assert prompt.index("COMPANY BRIEF " + BRIEF.version) < prompt.index("EMAILS:\n")
    assert prompt.index("raise the pre-seed round") < prompt.index("EMAILS:\n")


def test_with_no_brief_the_prompts_are_what_they_were(monkeypatch):
    monkeypatch.setattr("genios_engine.platform.company_brief.current",
                        lambda source, org: CompanyBrief(org_id=org))
    model = _Model([{"i": 0, "disposition": "keep", "relevance": 0.9, "reason": "x"},
                    {"i": 1, "disposition": "keep", "relevance": 0.9, "reason": "x"}])
    gate = R.LLMRelevanceClassifier(model)
    gate.bind_costs(lambda **_k: None, "o", brief_source=SimpleNamespace(engine=None))
    gate.prime(_objs())
    unbound = _Model(model.answer)
    R.LLMRelevanceClassifier(unbound).prime(_objs())
    assert model.prompts == unbound.prompts and "COMPANY BRIEF" not in model.prompts[0]


def test_the_batch_is_not_spent_on_a_sender_the_brief_names(monkeypatch):
    monkeypatch.setattr("genios_engine.platform.company_brief.current",
                        lambda source, org: CompanyBrief(org_id=org))
    model = _Model([{"i": 0, "disposition": "drop", "relevance": 0.05, "reason": "x"}])
    resolver = lambda raw: True                                     # noqa: E731
    resolver.named = lambda raw: ("watchlist:startupsetu.gov.test"
                                  if raw.actor_email.endswith("startupsetu.gov.test") else None)
    gate = R.LLMRelevanceClassifier(model)
    gate.bind_senders(resolver)
    gate.prime(_objs())
    assert len(model.prompts) == 1 and "Application status" not in model.prompts[0]
    assert "50% off" in model.prompts[0]
    assert gate.verdict_for("m1") is None and gate.verdict_for("m2") is not None


def _ctx(subject, body):
    event = SourceEvent(event_id="e", org_id="o", connection_id="c", source="gmail",
                        object_type="email_message", source_object_id="m9",
                        dedup_key="gmail:email_message:m9",
                        actor=Actor(type="external_contact", email="someone@else.test"),
                        occurred_at=T)
    return GateContext(event=event, raw={"subject": subject, "snippet": body},
                       prepared=preprocess(f"{subject}\n\n{body}", mask_phone=False))


def test_the_single_prompt_carries_the_brief_and_only_the_masked_subject(monkeypatch):
    monkeypatch.setattr("genios_engine.platform.company_brief.current", lambda source, org: BRIEF)
    model = _Model({"disposition": "keep", "relevance": 0.9, "reason": "a person"})
    gate = R.LLMRelevanceClassifier(model)
    gate.bind_costs(lambda **_k: None, "o", brief_source=SimpleNamespace(engine=None))
    ctx = _ctx("Invoice for card 4111 1111 1111 1111", "Please pay by Friday.")
    gate.classify(ctx, ctx.prepared)
    prompt = model.prompts[0]
    assert "4111 1111 1111 1111" not in prompt and "[CARD]" in prompt
    assert prompt.index("COMPANY BRIEF") < prompt.index("EMAIL:\n")


def test_without_a_prepared_text_the_snippet_is_masked_too(monkeypatch):
    monkeypatch.setattr("genios_engine.platform.company_brief.current",
                        lambda source, org: CompanyBrief(org_id=org))
    model = _Model({"disposition": "keep", "relevance": 0.9, "reason": "a person"})
    gate = R.LLMRelevanceClassifier(model)
    ctx = _ctx("Invoice for card 4111 1111 1111 1111", "Please pay by Friday.")
    gate.classify(GateContext(event=ctx.event, raw=ctx.raw), None)
    assert "4111 1111 1111 1111" not in model.prompts[0]
