"""STEP-07 · R-6 reads the company brief — before the situation's context, and in its seed.

Tree `yc2_w27_s07 · M25.C5.L-logic.V2.U05`. The Context Reasoner (`reason/situation_reasoner.py`) is
PURE, so the sweep that calls it (`reason/domain_shadow.shadow_compile`) reads the tenant's company
brief once, beside the R-site gate, and hands it in like the gate (`speedrun008/YC-II W27/` STEP-07
§8.3). The block is its own paragraph after the opening line and before the CONTEXT; the R-site
generation cache keys on the SEED, not the prompt, so the brief's version joins the seed (§8.2) —
only when there is a brief, so a reading made without one keeps the key it always had. Hermetic but
for the last case, which ran the sweep on real Postgres and captured the prompt R-6 was sent.

⛔ THAT LAST CASE LEFT 2026-10-11: R-6 is RETIRED (`06` D51, STEP-12 `yc2_w27_s12` M32.C4.L-logic.V0.U02) —
the sweep sends it nothing, so there is no prompt to capture; `tests/reason/test_r6_is_retired.py` holds
that, on the same tenant, with R-6's feature row present. The cases above test the module itself, and
(c) the brief the sweep still reads once.
"""
from __future__ import annotations

import ast
import inspect
import json
import textwrap
from types import SimpleNamespace

import pytest

from genios_engine.contracts.company_brief import CompanyBrief, CompanyBriefLine, compose
from genios_engine.platform.l4_activation import FEATURE_SITUATION_REASONER
from genios_engine.reason import situation_reasoner as SR
from genios_engine.reason.bundle.sites import SITE_SITUATION
from genios_engine.reason.llm_sites import (
    OUTCOME_CACHED,
    InMemorySiteCache,
    cache_key,
    make_gate,
)

ORG = "org_1"
SITUATION = "sit_1"
SLICE = SimpleNamespace(semantic_hash="5e" * 32)
SLICE_JSON = json.dumps({"facts": {"deal.status": "open"}, "members": ["node_1"]})
OPENING_END = "interpretation of it."

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
    """A model that proposes nothing — an empty object, R-6's "valid and useful answer"."""

    model = "claude-sonnet-5"

    def __init__(self):
        self.prompts: list[str] = []

    def call(self, prompt, *, max_tokens=400):
        from genios_engine.context.llm.client import LLMResult
        self.prompts.append(prompt)
        return LLMResult(parsed={}, raw="{}", ok=True, model=self.model,
                         input_tokens=900, output_tokens=10)


def gate(client):
    """The ONE C5 gate, wired for a test — R-6's feature passed in, so nothing reads a database."""
    return make_gate(org_id=ORG, client=client,
                     activated=frozenset({FEATURE_SITUATION_REASONER}))


def reason(client, *, company_brief=None, cache=None, confidence_bp=6_000):
    return SR.reason_over_situation(
        org_id=ORG, situation_id=SITUATION, situation_type="deal_cooling",
        context_slice=SLICE, slice_json=SLICE_JSON, confidence_bp=confidence_bp,
        importance_bp=6_000, resolve_refs=lambda refs: frozenset(refs), gate=gate(client),
        cache=cache, company_brief=company_brief)


def test_the_two_briefs_are_real_and_differ():
    assert BRIEF.version and BRIEF_2.version and BRIEF.version != BRIEF_2.version
    assert BRIEF.prompt_block().startswith(f"COMPANY BRIEF {BRIEF.version}")
    assert NO_BRIEF.prompt_block() == "" and NO_BRIEF.version == ""


# ── (a): the brief reaches the model, before the situation's context ─────────────────────────────

def test_the_r6_prompt_carries_the_brief_before_the_context():
    client = Client()

    reason(client, company_brief=BRIEF)

    prompt, block = client.prompts[0], BRIEF.prompt_block()
    assert prompt.startswith("You are reading ONE business situation")
    at = prompt.index(block)
    for content in ("CONTEXT (the only thing you may reason from):", SLICE_JSON, "RULES:"):
        assert at + len(block) <= prompt.index(content), content
    assert f"{OPENING_END}\n\n{block}\nCONTEXT" in prompt            # its own paragraph


def test_a_situation_not_worth_asking_about_asks_nothing_brief_or_not():
    client = Client()

    step, result = reason(client, company_brief=BRIEF, confidence_bp=None)

    assert step is SR.Step.UNKNOWN and result is None and client.prompts == []


# ── (b): no brief, no change ─────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("no_brief", [None, NO_BRIEF])
def test_without_a_brief_the_prompt_is_what_the_builder_gives_without_the_parameter(
        no_brief, monkeypatch):
    built = []
    original = SR.build_prompt

    def spy(**kwargs):
        built.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(SR, "build_prompt", spy)
    client = Client()

    reason(client, company_brief=no_brief)

    assert built[0]["company_brief"] == ""
    without = {name: value for name, value in built[0].items() if name != "company_brief"}
    assert client.prompts[0] == original(**without)
    assert "COMPANY BRIEF" not in client.prompts[0]


def test_a_brief_adds_its_paragraph_and_moves_nothing_else():
    without, with_brief = Client(), Client()
    reason(without)
    reason(with_brief, company_brief=BRIEF)

    block = BRIEF.prompt_block()
    assert with_brief.prompts[0] == without.prompts[0].replace(
        f"{OPENING_END}\n\nCONTEXT", f"{OPENING_END}\n\n{block}\nCONTEXT", 1)


# ── (d): the cache key moves with the brief's version, and only with a brief ─────────────────────

def _pre_step_07_seed():
    return {"situation": SITUATION, "slice": SR.slice_digest(SLICE), "prompt": SR.PROMPT_VERSION}


def test_without_a_brief_the_seed_and_key_are_the_ones_they_were_before_step_07():
    """The seed spelled out as it stood before STEP-07, so this cannot pass by comparing the code
    with itself. Change it only on purpose — a new key re-reads every situation, durably cached."""
    digest = SR.slice_digest(SLICE)
    assert dict(SR.consult_seed(situation_id=SITUATION, slice_digest=digest)) == _pre_step_07_seed()
    assert dict(SR.consult_seed(situation_id=SITUATION, slice_digest=digest,
                                company_brief_version="")) == _pre_step_07_seed()

    pre_step_07 = cache_key(site=SITE_SITUATION, org_id=ORG, seed=_pre_step_07_seed())
    for no_brief in (None, NO_BRIEF):
        _step, result = reason(Client(), company_brief=no_brief)
        assert result.receipt.cache_key == pre_step_07


def test_the_key_takes_the_version_only_when_there_is_a_brief():
    keys = {name: reason(Client(), company_brief=brief)[1].receipt.cache_key
            for name, brief in (("none", NO_BRIEF), ("one", BRIEF), ("two", BRIEF_2))}

    assert len(set(keys.values())) == 3
    assert keys["one"] == cache_key(site=SITE_SITUATION, org_id=ORG, seed={
        **_pre_step_07_seed(), "company_brief": BRIEF.version})


def test_a_changed_brief_is_never_answered_from_the_cache():
    """A reading cached under one brief is served under that brief and under no other."""
    cache = InMemorySiteCache()
    under_brief = cache_key(site=SITE_SITUATION, org_id=ORG,
                            seed={**_pre_step_07_seed(), "company_brief": BRIEF.version})
    cache.put(ORG, SITE_SITUATION, under_brief, {}, "llm:claude-sonnet-5@l4-r-sites.v1")

    client = Client()
    assert reason(client, company_brief=BRIEF, cache=cache)[1].receipt.outcome == OUTCOME_CACHED
    assert client.prompts == []                                    # the same brief: from the cache
    assert reason(client, company_brief=BRIEF_2, cache=cache)[1].receipt.outcome != OUTCOME_CACHED
    assert client.prompts and BRIEF_2.prompt_block() in client.prompts[-1]   # changed: asked again
    asked = len(client.prompts)
    assert reason(client, company_brief=NO_BRIEF, cache=cache)[1].receipt.outcome != OUTCOME_CACHED
    assert len(client.prompts) > asked and "COMPANY BRIEF" not in client.prompts[-1]


# ── (c): the sweep reads the tenant's brief once — and, since R-6 retired, hands it to `file_kinds` ──

def _shadow_compile_ast() -> ast.FunctionDef:
    from genios_engine.reason import domain_shadow
    return ast.parse(textwrap.dedent(inspect.getsource(domain_shadow.shadow_compile))).body[0]


def test_the_sweep_reads_the_brief_once_outside_the_loop():
    """By the AST, not the text: the brief the sweep hands on is a name it assigned exactly once, from
    `platform/company_brief.current` on the sweep's own store and tenant, outside every loop — one
    read per sweep, never one per situation.

    ⛔ MOVED 2026-10-11: this read the brief handed to R-6's `reason_over_situation`. R-6 is RETIRED
    (`06` D51, STEP-12 `yc2_w27_s12` M32.C4.L-logic.V0.U02) and the sweep calls it no more; the brief
    it still reads is handed to `file_kinds` (a programme's file is never decided as an investor,
    `yc2_w27_align` M34.C2 U10), and that is the call held here."""
    fn = _shadow_compile_ast()
    parents = {child: node for node in ast.walk(fn) for child in ast.iter_child_nodes(node)}

    assert not [node for node in ast.walk(fn) if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name) and node.func.id == "reason_over_situation"]
    calls = [node for node in ast.walk(fn) if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == "file_kinds"]
    assert len(calls) == 1
    handed = calls[0].args[2]
    assert isinstance(handed, ast.Name), "file_kinds is not handed the company brief"

    assigned = [node for node in ast.walk(fn) if isinstance(node, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == handed.id for t in node.targets)]
    assert len(assigned) == 1, f"{handed.id} is assigned {len(assigned)} times"
    read = assigned[0].value
    assert isinstance(read, ast.Call) and isinstance(read.func, ast.Name)
    imported = {alias.asname or alias.name: (node.module, alias.name)
                for node in ast.walk(fn) if isinstance(node, ast.ImportFrom)
                for alias in node.names}
    assert imported.get(read.func.id) == ("genios_engine.platform.company_brief", "current")
    # The sweep's own store (or its engine — `current` takes either) and the sweep's own tenant.
    source, tenant = [ast.unparse(arg) for arg in read.args]
    assert source in {"store.engine", "store"} and tenant == "org_id"

    node = assigned[0]
    while node in parents:
        node = parents[node]
        assert not isinstance(node, (ast.For, ast.AsyncFor, ast.While)), \
            "the brief is read inside a loop — once per situation instead of once per sweep"
