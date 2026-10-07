"""STEP-07 · R-1's test-mode reader reads the company brief — before the items, and in its key.

Tree `yc2_w27_s07 · M25.C5.L-logic.V2.U07`. With the LLM decision maker on, R-1 is one batched model
call per situation (`reason/llm_interpretation.py`). It is shown the tenant's company brief as its own
paragraph after the opening one and before the items it reads, read once per reading through the
decider's own read of `platform/company_brief.current` (`speedrun008/YC-II W27/` STEP-07 §8.3). Its
in-process cache keys on a version string, not the prompt, so the brief's version joins the key
(§8.2) — only when there is a brief, so a tenant without one is sent the prompt it was sent before and
keyed exactly as before. Hermetic: `current` and the decider's engine are stubbed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from genios_engine.context.llm.client import LLMResult
from genios_engine.contracts.company_brief import CompanyBrief, CompanyBriefLine, compose
from genios_engine.contracts.reasoning import (
    CapabilityManifest,
    ContextSnapshot,
    Goal,
    PlayDefinition,
    ReasonerSpec,
    ReasoningRequest,
)
from genios_engine.platform import company_brief as company_brief_module
from genios_engine.platform.canonical import semantic_hash
from genios_engine.reason import llm_decision_maker as llm_dm
from genios_engine.reason import llm_interpretation as r1

NOW = datetime(2026, 10, 7, 9, tzinfo=timezone.utc)
ORG = "org_1"
#: Stands in for the decider's engine. `current` is stubbed, so nothing ever connects to it.
ENGINE = object()
OPENING_END = "do not guess."
HEDGED = "We might revisit a pilot next quarter, not sure yet."

BRIEF = compose(org_id=ORG, company="Nimbus Labs", founder="Arjun Rao",
                us=("arjun@nimbuslabs.test",),
                lines=[CompanyBriefLine(line_id="l1", section="goals",
                                        text="raise the pre-seed round")])
BRIEF_2 = compose(org_id=ORG, company="Nimbus Labs", founder="Arjun Rao",
                  us=("arjun@nimbuslabs.test",),
                  lines=[CompanyBriefLine(line_id="l1", section="goals",
                                          text="raise the pre-seed round"),
                         CompanyBriefLine(line_id="l2", section="goals",
                                          text="get DPIIT recognition")])
NO_BRIEF = CompanyBrief(org_id=ORG)

BUSINESS = ["- this is a person: Maria Exconde",
            "- message 2026-08-11 from Maria Exconde: questions=['Shall we talk next week?']"]


def _request() -> ReasoningRequest:
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling", version="1.0.0", domain="sales",
        root_entity_type="deal", goal=Goal("g", "Restore healthy deal momentum"),
        reasoners=(ReasonerSpec("core.confidence", "1"),),
        plays=(PlayDefinition(play_id="nudge", version="1", label="Nudge",
                              steps=("Prepare a grounded draft",)),),
        policies=(), metadata={})
    context = ContextSnapshot(
        org_id=ORG, graph_version=1, root_entity_id="deal_1", root_entity_type="deal",
        evaluation_time=NOW, selector_version="s.v1",
        facts={"deal.status": "open", "thread.last_note": HEDGED})
    return ReasoningRequest(org_id=ORG, capability=capability, context=context,
                            evaluation_time=NOW, trigger_kind="email.received",
                            config_snapshot_id="cfg_1")


def _readings():
    return {"readings": [{"item": 1, "ambiguous": True, "confidence_bp": 6_000,
                          "classification": "EVALUATING_ALTERNATIVES"}]}


class FakeLLM:
    """The client's shape: `.model` and `.call(prompt, max_tokens=…)` -> `LLMResult`."""

    model = "fake-model"

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts: list[str] = []

    def call(self, prompt, *, max_tokens=4096):
        self.prompts.append(prompt)
        answer = self.answers.pop(0)
        return LLMResult(parsed=answer, raw=json.dumps(answer), input_tokens=5,
                         output_tokens=5, model=self.model)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    r1._reset_for_tests()
    llm_dm._reset_for_tests()
    monkeypatch.setattr(llm_dm, "_record_cost", lambda **_kw: None)
    yield
    r1._reset_for_tests()
    llm_dm._reset_for_tests()


@pytest.fixture
def tenant(monkeypatch):
    """The tenant's brief as `current` would answer it — `tenant["brief"]` — every read recorded."""
    state = {"brief": BRIEF, "reads": []}

    def fake_current(source, org_id):
        state["reads"].append((source, org_id))
        return state["brief"]

    monkeypatch.setattr(company_brief_module, "current", fake_current)
    monkeypatch.setattr(llm_dm, "_engine", lambda: ENGINE)
    monkeypatch.setattr(llm_dm, "business_context", lambda _request: list(BUSINESS))
    return state


def _read(llm) -> ReasoningRequest:
    """`interpret_request` never raises — so every test also checks a prompt really went out."""
    return r1.interpret_request(_request(), llm)


def test_the_two_briefs_are_real_and_differ():
    assert BRIEF.version and BRIEF_2.version and BRIEF.version != BRIEF_2.version
    assert BRIEF.prompt_block().startswith(f"COMPANY BRIEF {BRIEF.version}")
    assert NO_BRIEF.prompt_block() == "" and NO_BRIEF.version == ""


# ── (a) and (c): the tenant's brief reaches the model, before the items it reads ─────────────────

def test_the_reading_prompt_carries_the_tenants_brief_before_the_items(tenant):
    fake = FakeLLM(_readings())

    read = _read(fake)

    assert len(fake.prompts) == 1
    prompt, block = fake.prompts[0], BRIEF.prompt_block()
    assert prompt.startswith("You are R1")              # the opening is still the opening
    at = prompt.index(block)
    for content in ("ITEMS:", "thread.last_note", "mailbox.message_1"):
        assert at + len(block) <= prompt.index(content), content
    assert f"{OPENING_END}\n\n{block}\nITEMS:" in prompt  # its own paragraph
    assert tenant["reads"] == [(ENGINE, ORG)]
    assert any(name.startswith("interpretation.") for name in read.context.facts)   # it landed


def test_the_correction_attempt_carries_the_same_brief_read_once(tenant):
    fake = FakeLLM({"readings": "not a list"}, _readings())

    _read(fake)

    assert len(fake.prompts) == 2 and "CORRECTION" in fake.prompts[1]
    assert all(BRIEF.prompt_block() in prompt for prompt in fake.prompts)
    assert tenant["reads"] == [(ENGINE, ORG)]


# ── (b): no brief, no change ─────────────────────────────────────────────────────────────────────

def test_without_a_brief_the_prompt_is_what_the_builder_gives_without_the_parameter(
        tenant, monkeypatch):
    tenant["brief"] = NO_BRIEF
    built = []
    original = r1.build_prompt

    def spy(*args, **kwargs):
        built.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(r1, "build_prompt", spy)
    fake = FakeLLM(_readings())

    _read(fake)

    assert len(fake.prompts) == 1
    args, kwargs = built[0]
    assert kwargs["company_brief"] == ""
    without = {name: value for name, value in kwargs.items() if name != "company_brief"}
    assert fake.prompts[0] == original(*args, **without)
    assert "COMPANY BRIEF" not in fake.prompts[0]


def test_a_brief_adds_its_paragraph_and_moves_nothing_else(tenant):
    without, with_brief = FakeLLM(_readings()), FakeLLM(_readings())
    tenant["brief"] = NO_BRIEF
    _read(without)
    tenant["brief"] = BRIEF
    _read(with_brief)

    block = BRIEF.prompt_block()
    assert with_brief.prompts[0] == without.prompts[0].replace(
        f"{OPENING_END}\n\nITEMS:", f"{OPENING_END}\n\n{block}\nITEMS:", 1)


def test_no_database_means_no_brief_and_no_read(tenant, monkeypatch):
    monkeypatch.setattr(llm_dm, "_engine", lambda: None)
    fake = FakeLLM(_readings())

    _read(fake)

    assert len(fake.prompts) == 1 and "COMPANY BRIEF" not in fake.prompts[0]
    assert tenant["reads"] == []


# ── (d): the cache key moves with the brief's version, and only with a brief ─────────────────────

def _items():
    return r1.candidate_items(_request(), BUSINESS)


def test_without_a_brief_the_key_is_the_one_it_was_before_step_07():
    """The material spelled out as it stood before STEP-07, so this cannot pass by comparing the
    function with itself. Change this only on purpose — a new key re-reads every situation."""
    request, items = _request(), _items()
    pre_step_07 = semantic_hash({"prompt": r1.PROMPT_VERSION, "model": "fake-model", "org": ORG,
                                 "context": request.context.context_snapshot_id,
                                 "items": list(items)})

    assert r1._cache_key(request, items, "fake-model") == pre_step_07
    assert r1._cache_key(request, items, "fake-model",
                         company_brief_version=NO_BRIEF.version) == pre_step_07


def test_the_cache_key_takes_the_version_only_when_there_is_a_brief(tenant):
    request, items = _request(), _items()
    before = r1._cache_key(request, items, "fake-model")
    first = r1._cache_key(request, items, "fake-model", company_brief_version=BRIEF.version)
    second = r1._cache_key(request, items, "fake-model", company_brief_version=BRIEF_2.version)
    assert len({before, first, second}) == 3

    # And `_consult` keys — and receipts — what the tenant's brief says.
    _readings_out, meta = r1._consult(request, items, FakeLLM(_readings()))
    assert meta["key"] == first


def test_a_changed_brief_is_never_answered_from_the_cache(tenant):
    fake = FakeLLM(_readings(), _readings(), _readings())

    _read(fake)
    _read(fake)                                      # the same brief: answered from the cache
    assert len(fake.prompts) == 1
    tenant["brief"] = BRIEF_2
    _read(fake)                                      # a changed brief: read again
    assert len(fake.prompts) == 2 and BRIEF_2.prompt_block() in fake.prompts[1]
    tenant["brief"] = NO_BRIEF
    _read(fake)
    assert len(fake.prompts) == 3 and "COMPANY BRIEF" not in fake.prompts[2]
    assert r1._cache_key(_request(), _items(), "fake-model") in r1._cache
