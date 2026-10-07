"""STEP-07 · the decider reads the company brief — before the situation it judges, and in its key.

Tree `yc2_w27_s07 · M25.C5.L-logic.V2.U06`. The LLM decision maker (`reason/llm_decision_maker.py`)
is shown the tenant's company brief as its own paragraph after its role and before the situation,
read once per decision through `platform/company_brief.current` (`speedrun008/YC-II W27/` STEP-07
§8.3). Its in-process cache keys on a version string rather than on the prompt, so the brief's version
joins the key (§8.2) — and only when there is a brief: a tenant without one is sent exactly the prompt
it was sent before, keyed exactly as before. Hermetic: `current` and the module's engine are stubbed.
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
    ReasonerResult,
    ReasonerSpec,
    ReasoningRequest,
    ResultStatus,
)
from genios_engine.platform import company_brief as company_brief_module
from genios_engine.platform.canonical import semantic_hash
from genios_engine.reason import llm_decision_maker as llm_dm

NOW = datetime(2026, 10, 7, 9, tzinfo=timezone.utc)
ORG = "org_1"
#: Stands in for the module's engine. `current` is stubbed, so nothing ever connects to it — it only
#: has to be the very object the stub is handed.
ENGINE = object()
ROLE_END = "they should do about it."

BRIEF = compose(org_id=ORG, company="Nimbus Labs", founder="Arjun Rao",
                us=("arjun@nimbuslabs.test",),
                lines=[CompanyBriefLine(line_id="l1", section="goals",
                                        text="raise the pre-seed round")])
#: The same brief with one more accepted line — a changed brief, so a different version.
BRIEF_2 = compose(org_id=ORG, company="Nimbus Labs", founder="Arjun Rao",
                  us=("arjun@nimbuslabs.test",),
                  lines=[CompanyBriefLine(line_id="l1", section="goals",
                                          text="raise the pre-seed round"),
                         CompanyBriefLine(line_id="l2", section="goals",
                                          text="get DPIIT recognition")])
NO_BRIEF = CompanyBrief(org_id=ORG)

BUSINESS = ["- this is a person: Maria Exconde",
            "- message 2026-08-11 from Maria Exconde: questions=['What are you building?']"]


def _request() -> ReasoningRequest:
    play = PlayDefinition(play_id="restore_momentum", version="1", label="Restore Momentum",
                          steps=("Prepare a grounded draft",), impact_bp=6_000,
                          success_probability_bp=6_000, effort_bp=2_000, risk_bp=1_000)
    capability = CapabilityManifest(
        capability_id="sales.deal_cooling", version="1.0.0", domain="sales",
        root_entity_type="deal", goal=Goal("restore_momentum", "Restore healthy deal momentum"),
        reasoners=(ReasonerSpec("core.confidence", "1"),), plays=(play,), policies=(),
        metadata={})
    context = ContextSnapshot(org_id=ORG, graph_version=17, root_entity_id="deal_1",
                              root_entity_type="deal", evaluation_time=NOW,
                              selector_version="selector.v1", facts={"deal.status": "open"})
    return ReasoningRequest(org_id=ORG, capability=capability, context=context,
                            evaluation_time=NOW, trigger_kind="email.received",
                            config_snapshot_id="cfg_1")


def _results():
    return [ReasonerResult(reasoner_id="core.confidence", reasoner_version="1",
                           status=ResultStatus.COMPLETED, matched=True,
                           metrics={"confidence_bp": 8_000})]


def _answer(utility=6_000):
    return {"outcome": "decision", "scores": {"restore_momentum": utility},
            "confidence_bp": 7_000, "rationale": "Reply today.", "missing": []}


class FakeLLM:
    """The decision client's shape: `.model` and `.call(prompt, max_tokens=…)` -> `LLMResult`."""

    model = "fake-model"

    def __init__(self, *answers):
        self.answers = list(answers)
        self.prompts: list[str] = []

    def call(self, prompt, *, max_tokens=4096):
        self.prompts.append(prompt)
        answer = self.answers.pop(0)
        return LLMResult(parsed=answer, raw=json.dumps(answer), input_tokens=10,
                         output_tokens=5, model=self.model)


def _decide(llm):
    return llm_dm.decide_with_llm(_request(), _results(), uncertainty=(), degraded=False, llm=llm)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    llm_dm._reset_for_tests()
    monkeypatch.setattr(llm_dm, "_record_cost", lambda **_kw: None)
    yield
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


def test_the_two_briefs_are_real_and_differ():
    """The premise of every test below: a non-empty block, and a version that moves with a line."""
    assert BRIEF.version and BRIEF_2.version and BRIEF.version != BRIEF_2.version
    assert BRIEF.prompt_block().startswith(f"COMPANY BRIEF {BRIEF.version}")
    assert BRIEF.prompt_block().endswith("END OF COMPANY BRIEF\n")
    assert NO_BRIEF.prompt_block() == "" and NO_BRIEF.version == ""


# ── (a) and (c): the tenant's brief reaches the model, before what it judges ─────────────────────

def test_the_decision_prompt_carries_the_tenants_brief_before_the_situation(tenant):
    fake = FakeLLM(_answer())

    _decide(fake)

    prompt, block = fake.prompts[0], BRIEF.prompt_block()
    assert block in prompt
    at = prompt.index(block)
    assert prompt.index("You are the chief of staff") < at
    for content in ("Decide:", "SITUATION:", "WHO AND WHAT", "FACTS THE RULE USED:",
                    "PLAYS YOU CAN RECOMMEND:"):
        assert at + len(block) <= prompt.index(content), content
    # Its own paragraph, right after the role line — never inside another section.
    assert f"{ROLE_END}\n\n{block}\nDecide:" in prompt
    # Read once for this decision, through the module's engine, for the request's tenant.
    assert tenant["reads"] == [(ENGINE, ORG)]


def test_the_correction_attempt_carries_the_same_brief_read_once(tenant):
    fake = FakeLLM({"outcome": "maybe"}, _answer())

    _decide(fake)

    assert len(fake.prompts) == 2 and "CORRECTION" in fake.prompts[1]
    assert all(BRIEF.prompt_block() in prompt for prompt in fake.prompts)
    assert tenant["reads"] == [(ENGINE, ORG)]


# ── (b): no brief, no change ─────────────────────────────────────────────────────────────────────

def test_without_a_brief_the_prompt_is_what_the_builder_gives_without_the_parameter(
        tenant, monkeypatch):
    tenant["brief"] = NO_BRIEF
    built = []
    original = llm_dm.build_prompt

    def spy(*args, **kwargs):
        built.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(llm_dm, "build_prompt", spy)
    fake = FakeLLM(_answer())

    _decide(fake)

    args, kwargs = built[0]
    assert kwargs["company_brief"] == ""
    without = {name: value for name, value in kwargs.items() if name != "company_brief"}
    assert fake.prompts[0] == original(*args, **without)
    assert "COMPANY BRIEF" not in fake.prompts[0]


def test_a_brief_adds_its_paragraph_and_moves_nothing_else(tenant):
    without, with_brief = FakeLLM(_answer()), FakeLLM(_answer())
    tenant["brief"] = NO_BRIEF
    _decide(without)
    tenant["brief"] = BRIEF
    _decide(with_brief)

    block = BRIEF.prompt_block()
    assert with_brief.prompts[0] == without.prompts[0].replace(
        f"{ROLE_END}\n\nDecide:", f"{ROLE_END}\n\n{block}\nDecide:", 1)


def test_no_database_means_no_brief_and_no_read(monkeypatch):
    def must_not_read(source, org_id):
        raise AssertionError("the brief was read without an engine")

    monkeypatch.setattr(company_brief_module, "current", must_not_read)
    monkeypatch.setattr(llm_dm, "_engine", lambda: None)
    fake = FakeLLM(_answer())

    _decide(fake)

    assert "COMPANY BRIEF" not in fake.prompts[0]


# ── (d): the cache key moves with the brief's version, and only with a brief ─────────────────────

def test_without_a_brief_the_key_is_the_one_it_was_before_step_07():
    """The material spelled out as it stood before STEP-07, so this cannot pass by comparing the
    function with itself: a key that grew even an empty field would miss every decision a tenant
    without a brief has cached. Change this only on purpose — a new key re-asks every decision."""
    request, results = _request(), _results()
    pre_step_07 = semantic_hash({"prompt": llm_dm.PROMPT_VERSION, "model": "fake-model",
                                 "org_id": ORG,
                                 "capability": request.capability.capability_snapshot_id,
                                 "context": request.context.context_snapshot_id,
                                 "evaluation_time": request.evaluation_time,
                                 "results": [item.semantic_hash for item in results],
                                 "uncertainty": [], "degraded": False})

    assert llm_dm._cache_key(request, results, (), False, "fake-model") == pre_step_07
    assert llm_dm._cache_key(request, results, (), False, "fake-model",
                             company_brief_version=NO_BRIEF.version) == pre_step_07


def test_the_cache_key_takes_the_version_only_when_there_is_a_brief():
    request, results = _request(), _results()
    before = llm_dm._cache_key(request, results, (), False, "fake-model")

    assert llm_dm._cache_key(request, results, (), False, "fake-model",
                             company_brief_version=NO_BRIEF.version) == before
    first = llm_dm._cache_key(request, results, (), False, "fake-model",
                              company_brief_version=BRIEF.version)
    second = llm_dm._cache_key(request, results, (), False, "fake-model",
                               company_brief_version=BRIEF_2.version)
    assert len({before, first, second}) == 3


def test_a_changed_brief_is_never_answered_from_the_cache(tenant):
    fake = FakeLLM(_answer(6_000), _answer(6_500), _answer(7_000))

    _decide(fake)
    _decide(fake)                                    # the same brief: answered from the cache
    assert len(fake.prompts) == 1
    tenant["brief"] = BRIEF_2
    _decide(fake)                                    # a changed brief: asked again
    assert len(fake.prompts) == 2 and BRIEF_2.prompt_block() in fake.prompts[1]
    tenant["brief"] = NO_BRIEF
    _decide(fake)
    assert len(fake.prompts) == 3 and "COMPANY BRIEF" not in fake.prompts[2]

    # The no-brief decision sits under exactly the key it had before STEP-07.
    unchanged = semantic_hash({"base": llm_dm._cache_key(_request(), _results(), [], False,
                                                         "fake-model"),
                               "business": list(BUSINESS)})
    assert unchanged in llm_dm._cache
    assert len(llm_dm._cache) == 3
