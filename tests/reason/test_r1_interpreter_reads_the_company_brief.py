"""STEP-07 · R-1 through the gate reads the company brief — before the sentence, and in its seed.

Tree `yc2_w27_s07 · M25.C5.L-logic.V2.U04`. The ambiguity interpreter (`reason/interpretation.py`)
shows the model ONE sentence; it now shows the tenant's company brief first, as its own paragraph
after the opening and before the sentence (`speedrun008/YC-II W27/` STEP-07 §8.3). The brief is read
once per run, through the engine `make_interpreter` is handed by the sweep, and only when there is a
flag to read. The R-site generation cache keys on the SEED, not the prompt, so the brief's version
joins the seed (§8.2) — only when there is a brief, so a reading made without one keeps the key it
always had. Hermetic: the gate is the real one with a fake client, and `current` is stubbed.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

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
from genios_engine.reason import interpretation as I
from genios_engine.reason import llm_sites
from genios_engine.reason.evidence import build_evidence_ref
from genios_engine.reason.llm_sites import (
    OUTCOME_CACHED,
    OUTCOME_RAN,
    SITE_R1,
    InMemorySiteCache,
    cache_key,
    make_gate,
)

NOW = datetime(2026, 10, 7, 9, tzinfo=timezone.utc)
ORG = "org_1"
#: Stands in for the sweep's engine. `current` is stubbed, so nothing ever connects to it.
ENGINE = object()
OPENING_END = "urgency or risk."
HEDGED = "They are considering moving some workloads to another vendor next quarter."
HEDGED_TOO = "We might need a second pilot before anyone signs, probably in the spring."
SETTLED = "The renewal has been signed and countersigned by both parties this morning."

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


class Client:
    """A model that answers every prompt with one reading, and keeps every prompt it was sent."""

    model = "claude-sonnet-5"

    def __init__(self):
        self.prompts: list[str] = []

    def call(self, prompt, *, max_tokens=400):
        from genios_engine.context.llm.client import LLMResult
        self.prompts.append(prompt)
        return LLMResult(parsed={"classification": I.EVALUATING_ALTERNATIVES,
                                 "confidence_bp": 7000},
                         raw="", ok=True, model=self.model, input_tokens=900, output_tokens=150)


def gate(client):
    """The ONE C5 gate, wired for a test — activation passed in, so nothing reads a database."""
    return make_gate(org_id=ORG, client=client, activated=frozenset({"bundle"}))


def request(facts, *, declared=("deal.note",)):
    spec = ReasonerSpec(reasoner_id="core.risk", version="1.0.0", required_fields=tuple(declared))
    capability = CapabilityManifest(
        capability_id="test.capability", version="1.0.0", domain="test",
        root_entity_type="entity",
        goal=Goal(goal_id="g", statement="Prove the brief reaches R-1."), reasoners=(spec,),
        plays=(PlayDefinition(play_id="do_it", version="1.0.0", label="Do it", steps=("a",)),),
        policies=(), live_delivery_enabled=False)
    evidence = tuple(build_evidence_ref(org_id=ORG, entity_ref="node_1", field=name,
                                        value=record["value"], source_ref=f"src:{name}")
                     for name, record in facts.items())
    context = ContextSnapshot(
        org_id=ORG, graph_version=1, root_entity_id="node_1", root_entity_type="entity",
        evaluation_time=NOW, selector_version="v1", facts=facts, evidence=evidence)
    return ReasoningRequest(org_id=ORG, capability=capability, context=context,
                            evaluation_time=NOW, trigger_kind="test.trigger")


def hedged():
    return request({"deal.note": {"value": HEDGED}})


@pytest.fixture
def tenant(monkeypatch):
    """The tenant's brief as `current` would answer it — `tenant["brief"]` — every read recorded."""
    state = {"brief": BRIEF, "reads": []}

    def fake_current(source, org_id):
        state["reads"].append((source, org_id))
        return state["brief"]

    monkeypatch.setattr(company_brief_module, "current", fake_current)
    return state


def interpreter(client, *, engine=ENGINE, cache=None):
    return I.AmbiguityInterpreter(org_id=ORG, gate=gate(client), cache=cache, engine=engine)


def test_the_two_briefs_are_real_and_differ():
    assert BRIEF.version and BRIEF_2.version and BRIEF.version != BRIEF_2.version
    assert BRIEF.prompt_block().startswith(f"COMPANY BRIEF {BRIEF.version}")
    assert NO_BRIEF.prompt_block() == "" and NO_BRIEF.version == ""


# ── (a) and (c): the tenant's brief reaches the model, before the sentence it reads ──────────────

def test_the_reading_prompt_carries_the_tenants_brief_before_the_sentence(tenant):
    client = Client()

    out = interpreter(client)(hedged())

    assert len(client.prompts) == 1
    prompt, block = client.prompts[0], BRIEF.prompt_block()
    assert prompt.startswith("You are reading ONE sentence")
    at = prompt.index(block)
    for content in ("FIELD: deal.note", f"TEXT: {HEDGED}", "Choose exactly one classification"):
        assert at + len(block) <= prompt.index(content), content
    assert f"{OPENING_END}\n\n{block}\nFIELD:" in prompt      # its own paragraph
    assert tenant["reads"] == [(ENGINE, ORG)]
    assert "interpretation.deal.note" in out.context.facts     # the reading still lands


def test_the_sweeps_engine_reaches_the_brief_through_make_interpreter(tenant, monkeypatch):
    """What `reason/domain_shadow.py` calls: `make_interpreter(org_id=…, engine=store.engine, …)`.
    The gate and the cache are swapped for hermetic ones; the engine is the sweep's, untouched."""
    client = Client()
    monkeypatch.setattr(llm_sites, "make_gate",
                        lambda *, org_id, client=None, **_kw: gate(client))
    monkeypatch.setattr(llm_sites, "PostgresSiteCache", lambda *, engine: InMemorySiteCache())

    built = I.make_interpreter(org_id=ORG, engine=ENGINE, client=client)
    built(request({"deal.note": {"value": HEDGED}, "deal.other": {"value": HEDGED_TOO}},
                  declared=("deal.note", "deal.other")))

    assert built.engine is ENGINE
    assert len(client.prompts) == 2                            # two flags, two readings …
    assert all(BRIEF.prompt_block() in prompt for prompt in client.prompts)
    assert tenant["reads"] == [(ENGINE, ORG)]                  # … and the brief read once


def test_nothing_ambiguous_reads_no_brief_and_costs_nothing(tenant):
    client = Client()

    interpreter(client)(request({"deal.note": {"value": SETTLED}}))

    assert client.prompts == [] and tenant["reads"] == []


def test_no_engine_bound_means_no_brief_and_no_read(tenant):
    client = Client()

    interpreter(client, engine=None)(hedged())

    assert len(client.prompts) == 1 and "COMPANY BRIEF" not in client.prompts[0]
    assert tenant["reads"] == []


# ── (b): no brief, no change ─────────────────────────────────────────────────────────────────────

def test_without_a_brief_the_prompt_is_what_the_builder_gives_without_the_parameter(
        tenant, monkeypatch):
    tenant["brief"] = NO_BRIEF
    built = []
    original = I._prompt

    def spy(*args, **kwargs):
        built.append((args, kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(I, "_prompt", spy)
    client = Client()

    interpreter(client)(hedged())

    assert len(client.prompts) == 1
    args, kwargs = built[0]
    assert kwargs["company_brief"] == ""
    without = {name: value for name, value in kwargs.items() if name != "company_brief"}
    assert client.prompts[0] == original(*args, **without)
    assert "COMPANY BRIEF" not in client.prompts[0]


def test_a_brief_adds_its_paragraph_and_moves_nothing_else(tenant):
    without, with_brief = Client(), Client()
    tenant["brief"] = NO_BRIEF
    interpreter(without)(hedged())
    tenant["brief"] = BRIEF
    interpreter(with_brief)(hedged())

    block = BRIEF.prompt_block()
    assert with_brief.prompts[0] == without.prompts[0].replace(
        f"{OPENING_END}\n\nFIELD:", f"{OPENING_END}\n\n{block}\nFIELD:", 1)


# ── (d): the cache key moves with the brief's version, and only with a brief ─────────────────────

def test_without_a_brief_the_key_is_the_one_it_was_before_step_07():
    """The seed spelled out as it stood before STEP-07, so this cannot pass by comparing the code
    with itself. Change it only on purpose — a new key re-reads every claim, durably cached."""
    flag = I.find_ambiguities(hedged())[0]
    pre_step_07 = cache_key(site=SITE_R1, org_id=ORG,
                            seed={"digest": flag.digest, "kind": flag.kind})

    for no_brief in (None, NO_BRIEF):
        result = I.interpret(flag, org_id=ORG, gate=gate(Client()), company_brief=no_brief)
        assert result.receipt.cache_key == pre_step_07


def test_the_key_takes_the_version_only_when_there_is_a_brief():
    flag = I.find_ambiguities(hedged())[0]
    keys = {name: I.interpret(flag, org_id=ORG, gate=gate(Client()),
                              company_brief=brief).receipt.cache_key
            for name, brief in (("none", NO_BRIEF), ("one", BRIEF), ("two", BRIEF_2))}

    assert len(set(keys.values())) == 3
    assert keys["one"] == cache_key(site=SITE_R1, org_id=ORG, seed={
        "digest": flag.digest, "kind": flag.kind, "company_brief": BRIEF.version})


def test_a_changed_brief_is_never_answered_from_the_cache(tenant):
    client, cache = Client(), InMemorySiteCache()
    reader = interpreter(client, cache=cache)
    flag = I.find_ambiguities(hedged())[0]

    def outcome():
        return I.interpret(flag, org_id=ORG, gate=reader.gate, cache=cache,
                           company_brief=reader._company_brief()).receipt.outcome

    assert outcome() == OUTCOME_RAN
    assert outcome() == OUTCOME_CACHED                        # the same brief: from the cache
    tenant["brief"] = BRIEF_2
    assert outcome() == OUTCOME_RAN                           # a changed brief: read again
    assert BRIEF_2.prompt_block() in client.prompts[-1]
    tenant["brief"] = NO_BRIEF
    assert outcome() == OUTCOME_RAN
    assert "COMPANY BRIEF" not in client.prompts[-1] and len(client.prompts) == 3
