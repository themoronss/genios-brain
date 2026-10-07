"""THE GUARD: every model call that judges or reads carries the company brief (STEP-07).

    pytest tests/test_every_prompt_carries_the_company_brief.py -q

Tree `yc2_w27_s07 · M25.C5.L-integration.V3.U13`. The founder's company brief — the company, the
people who are us, goals, work in motion, key people, connectors, a watchlist — rides in every prompt
that JUDGES or READS (`speedrun008/YC-II W27/` STEP-07 §8.3), and in none that writes: card copy and
the other writing sites are STEP-14's. A site is a few lines any layer can add, and a new one that
forgot the brief would judge the founder's mail as a stranger would — silently, because a prompt
without the brief is still a valid prompt.

So the register of model call sites (`tests/test_every_llm_call_site_is_metered._SITES`) is split in
two here, and held equal to it BOTH WAYS:

  * `BRIEF_SITES` — the sites that carry it, each with the AST facts that prove it: the prompt builder
    TAKES the block (`company_brief`), and every caller PASSES it by keyword; or the prompt template is
    formatted only inside `with_company_brief(...)`; or the request type carries the field and every
    construction fills it;
  * `NO_BRIEF` — the sites that do not, each with its reason.

A call that legitimately goes without it is declared in `DECLARED_GAPS`, with the mechanical fact
that keeps the declaration true. And the checker is run on a planted site that omits the brief at
each link, so a checker that has stopped checking fails too.

WHAT TO DO WHEN THIS FAILS. A new model site: decide whether it judges or reads (then give its
builder a `company_brief` parameter, read `platform/company_brief.current` once where the caller has
the tenant, pass the block, and register its carriers here) or writes (then say why in `NO_BRIEF`).
"""
from __future__ import annotations

import ast
import pathlib
from collections.abc import Mapping
from dataclasses import dataclass

import pytest

ENGINE = pathlib.Path(__file__).resolve().parents[1] / "genios_engine"
PARAM = "company_brief"


@dataclass(frozen=True)
class Carries:
    """`function` (in `module`; `Class.method` for a method) takes the block as `param`, and every
    call of it in each module of `callers` passes `param` by keyword. `callee` is the name a caller
    calls it by, when that is not the function's own (a class, for its `__init__`)."""
    module: str
    function: str
    callers: tuple[str, ...]
    param: str = PARAM
    callee: str | None = None


@dataclass(frozen=True)
class Wraps:
    """In `module`, every `.format(...)` of the prompt template `template` sits inside a call of
    `with_company_brief(...)` — the block goes after the template's opening paragraph."""
    module: str
    template: str


@dataclass(frozen=True)
class Field:
    """The request type `cls` (in `module`) carries the block as an annotated `param` field, and
    every construction of it in `callers` fills it by keyword."""
    module: str
    cls: str
    callers: tuple[str, ...]
    param: str = PARAM


# ── the split of the register ──────────────────────────────────────────────────────────────────
BRIEF_SITES: dict[str, tuple[Carries | Wraps | Field, ...]] = {
    # ── L1 capture ───────────────────────────────────────────────────────────────────────────
    # The junk filter: both templates are wrapped, and every bind says where the brief is read
    # from — the sweep's shared classifier is re-bound per tenant in `api/routes` (`740e13bc`).
    "capture/gate/relevance.py": (
        Wraps("capture/gate/relevance.py", "_GATE_PROMPT"),
        Wraps("capture/gate/relevance.py", "_GATE_BATCH_PROMPT"),
        Carries("capture/gate/relevance.py", "LLMRelevanceClassifier.bind_costs",
                callers=("platform/wiring.py", "api/routes.py"), param="brief_source"),
    ),
    # The relevance page (LLM-5): the page is built with the block, and judges with it.
    "capture/esqe/relevance.py": (
        Carries("capture/esqe/relevance.py", "_judge_batch",
                callers=("capture/esqe/relevance.py",)),
        Carries("capture/esqe/relevance.py", "RelevancePage.__init__",
                callers=("platform/wiring.py",), callee="RelevancePage"),
    ),
    # Extraction: the block rides in the per-call envelope; the lane carries it to the request.
    "capture/semantic/extractor.py": (
        Field("capture/semantic/extractor.py", "ExtractionRequest",
              callers=("capture/pipeline.py",)),
        Field("capture/pipeline.py", "SemanticLane", callers=("platform/wiring.py",)),
    ),
    # ── L2 context ───────────────────────────────────────────────────────────────────────────
    "context/lifecycle/resolution.py": (
        Carries("context/lifecycle/prompt.py", "build_prompt",
                callers=("context/lifecycle/resolution.py",)),
    ),
    # ── L4 reasoning ─────────────────────────────────────────────────────────────────────────
    # The R-site gate runs R-1 and R-6, which read; its R-2 bundle narrator WRITES (STEP-14) and
    # takes no block — the gate itself only carries what each site's builder hands it.
    "reason/bundle/gate.py": (
        Carries("reason/interpretation.py", "_prompt", callers=("reason/interpretation.py",)),
        Carries("reason/interpretation.py", "interpret", callers=("reason/interpretation.py",)),
        Carries("reason/situation_reasoner.py", "build_prompt",
                callers=("reason/situation_reasoner.py",)),
        Carries("reason/situation_reasoner.py", "reason_over_situation",
                callers=("reason/domain_shadow.py",)),
    ),
    "reason/llm_decision_maker.py": (
        Carries("reason/llm_decision_maker.py", "build_prompt",
                callers=("reason/llm_decision_maker.py",)),
    ),
    "reason/llm_interpretation.py": (
        Carries("reason/llm_interpretation.py", "build_prompt",
                callers=("reason/llm_interpretation.py",)),
    ),
    "reason/brief_drafter.py": (
        Carries("reason/brief_drafter.py", "build_prompt", callers=("reason/brief_drafter.py",)),
    ),
    # ── moments — the screen lanes ───────────────────────────────────────────────────────────
    "reason/moments/screen_insight.py": (
        Carries("reason/moments/screen_insight.py", "build_prompt",
                callers=("reason/moments/screen_insight.py",)),
        Carries("reason/moments/screen_insight.py", "llm_insight",
                callers=("reason/moments/screen_insight.py",)),
        Carries("reason/moments/screen_insight.py", "insight", callers=("api/moment_routes.py",)),
    ),
    "reason/moments/screen_memory_batch.py": (
        Carries("reason/moments/screen_memory_batch.py", "build_prompt",
                callers=("reason/moments/screen_memory_batch.py",)),
    ),
    "reason/moments/draft_review.py": (
        Carries("reason/moments/draft_review.py", "llm_notes",
                callers=("reason/moments/draft_review.py",)),
        Carries("reason/moments/draft_review.py", "review", callers=("api/moment_routes.py",)),
    ),
    # ── packs / brains ───────────────────────────────────────────────────────────────────────
    "packs/brains/org_rule_extract.py": (
        Carries("packs/brains/org_rule_extract.py", "build_prompt",
                callers=("packs/brains/org_rule_extract.py",)),
        Carries("packs/brains/org_rule_extract.py", "make_org_rule_extractor",
                callers=("feedback/org_rule_ingest.py",)),
    ),
}

NO_BRIEF: dict[str, str] = {
    "capture/domain/proposer.py": "OFF in production: no caller passes a proposer — "
                                  "capture/pipeline.tag_domains runs without one — so this prompt "
                                  "is never sent; it gains the brief the day it is wired",
    "context/llm/client.py": "THE TRANSPORT. It sends the prompt it is handed and composes none; the "
                             "brief is the builder's business, never the client's",
    "context/extract/extractor.py": "the legacy Layer 2 extractor: context/runner.process_event "
                                    "hands it llm=None and adapts Layer 1's extraction instead, so "
                                    "no prompt of its own is ever sent",
    "context/angles/asker.py": "OFF in production: the sweep supplies no asker "
                               "(evaluate_angle(asker=None) is the default), so this prompt is "
                               "never sent",
    "context/analytic/cohort.py": "translates the founder's OWN sentence into a predicate over their "
                                  "records, from the cohort API — it judges nothing about the "
                                  "mailbox; the founder's words are already the context",
    "reason/intelligence.py": "WRITES: the Ask answer to the founder's own question — a writing "
                              "site, STEP-14's to give the brief to with the card copy",
    "reason/moments/seat_profile.py": "WRITES: the seat's weekly profile of the PERSON, from their own "
                                      "screen — a writing site, STEP-14's",
    "deliver/render.py": "WRITES: the card narrator — card copy is STEP-14's, and a brief in the "
                         "narrator would move every card's words before that step decides how",
    "packs/brains/behavior_distill.py": "NOT WIRED in production: brain_pipeline_proposals is always "
                                        "called with labeler=None, so this prompt is never sent",
    "api/intelligence_routes.py": "WRITES: the Ask, analyze and draft answers the founder requested "
                                  "— writing sites, STEP-14's",
}

#: Calls of a carrier that go without the block, with the fact that keeps each true — checked.
#: (caller module, the function the call sits in, the function called) → why.
DECLARED_GAPS: dict[tuple[str, str, str], str] = {
    ("capture/esqe/relevance.py", "assess_relevance", "_judge_batch"):
        "the per-event path, used only when a caller INJECTS a model as EsqeStage.relevance_llm — "
        "and no production code does (checked below: no `relevance_llm=` in genios_engine), so in "
        "production this path is rules-only and never asks the model",
}


# ── the checker ───────────────────────────────────────────────────────────────────────────────
def _source(module: str, sources: Mapping[str, str] | None) -> str:
    if sources is not None and module in sources:
        return sources[module]
    return (ENGINE / module).read_text(encoding="utf-8")


def _defs(tree: ast.Module) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    out: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            out[node.name] = node
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    out[f"{node.name}.{item.name}"] = item
    return out


def _params(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    a = fn.args
    return {p.arg for p in a.posonlyargs + a.args + a.kwonlyargs}


def _module_dotted(module: str) -> str:
    return "genios_engine." + module[:-3].replace("/", ".")


def _aliases(tree: ast.Module, module: str, name: str) -> tuple[set[str], set[str]]:
    """In a caller's tree: the local names bound to `name` from `module`, and the names bound to
    `module` itself — through any import, at the top or inside a function."""
    dotted = _module_dotted(module)
    package, _, leaf = dotted.rpartition(".")
    names, modules = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == dotted:
            names |= {a.asname or a.name for a in node.names if a.name == name}
        elif isinstance(node, ast.ImportFrom) and node.module == package:
            modules |= {a.asname or a.name for a in node.names if a.name == leaf}
        elif isinstance(node, ast.Import):
            modules |= {a.asname for a in node.names if a.name == dotted and a.asname}
    return names, modules


def _enclosing(tree: ast.Module) -> dict[int, str]:
    """`id(call node) → the qualified name of the function it sits in` ("" at module level)."""
    out: dict[int, str] = {}

    def visit(node: ast.AST, where: str) -> None:
        for child in ast.iter_child_nodes(node):
            here = where
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                here = f"{where}.{child.name}" if where else child.name
            elif isinstance(child, ast.ClassDef):
                here = f"{where}.{child.name}" if where else child.name
            if isinstance(child, ast.Call):
                out[id(child)] = where
            visit(child, here)

    visit(tree, "")
    return out


def _calls_of(tree: ast.Module, *, caller: str, module: str, name: str, method: bool = False):
    """Every call, in `caller`'s tree, of `name` defined in `module`. A METHOD is called on an
    instance the AST cannot type, so for one every `<anything>.name(…)` counts — the names guarded
    here (`bind_costs`) are distinctive enough that a stranger's method of that name is a finding."""
    local = caller == module
    names, modules = _aliases(tree, module, name)
    if local:
        names.add(name)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Name) and f.id in names:
            yield node
        elif isinstance(f, ast.Attribute) and f.attr == name and (
                method or (isinstance(f.value, ast.Name)
                           and (f.value.id in modules or (local and f.value.id in ("self", "cls"))))):
            yield node


def carrier_failures(carrier: Carries | Wraps | Field,
                     sources: Mapping[str, str] | None = None) -> list[str]:
    """What is wrong with one carrier — empty when it holds. `sources` overrides files by module
    (the planted control); everything else is read from the engine."""
    failures: list[str] = []
    tree = ast.parse(_source(carrier.module, sources))
    if isinstance(carrier, Wraps):
        wrapped: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "with_company_brief":
                wrapped |= {id(n) for arg in node.args for n in ast.walk(arg)}
        formats = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                   and isinstance(n.func, ast.Attribute) and n.func.attr == "format"
                   and isinstance(n.func.value, ast.Name) and n.func.value.id == carrier.template]
        if not formats:
            failures.append(f"{carrier.module}: {carrier.template} is never formatted")
        failures += [f"{carrier.module}:{n.lineno}: {carrier.template}.format(…) outside "
                     "with_company_brief(…)" for n in formats if id(n) not in wrapped]
        return failures
    if isinstance(carrier, Field):
        cls = next((n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == carrier.cls),
                   None)
        fields = {st.target.id for st in (cls.body if cls else ())
                  if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name)}
        if cls is None or carrier.param not in fields:
            failures.append(f"{carrier.module}: {carrier.cls} carries no `{carrier.param}` field")
        name, callers = carrier.cls, carrier.callers
    else:
        fn = _defs(tree).get(carrier.function)
        if fn is None:
            return [f"{carrier.module}: no function {carrier.function}"]
        if carrier.param not in _params(fn):
            failures.append(f"{carrier.module}:{fn.lineno}: {carrier.function} takes no "
                            f"`{carrier.param}`")
        name = carrier.callee or carrier.function.rsplit(".", 1)[-1]
        callers = carrier.callers
    for caller in callers:
        ctree = ast.parse(_source(caller, sources))
        where = _enclosing(ctree)
        method = isinstance(carrier, Carries) and "." in carrier.function and not carrier.callee
        found = list(_calls_of(ctree, caller=caller, module=carrier.module, name=name,
                               method=method))
        if not found:
            failures.append(f"{caller}: never calls {name}")
        for call in found:
            if any(k.arg == carrier.param for k in call.keywords):
                continue
            inside = where.get(id(call), "")
            if (caller, inside.rsplit(".", 1)[-1], name) in DECLARED_GAPS:
                continue
            failures.append(f"{caller}:{call.lineno}: {name}(…) in {inside or 'module level'} "
                            f"does not pass `{carrier.param}`")
    return failures


# ── the tests ─────────────────────────────────────────────────────────────────────────────────
def test_the_split_is_the_register_both_ways():
    from tests.test_every_llm_call_site_is_metered import _SITES

    split = set(BRIEF_SITES) | set(NO_BRIEF)
    assert not set(BRIEF_SITES) & set(NO_BRIEF), "a site cannot both carry the brief and not"
    assert split == set(_SITES), (
        f"model sites with no brief decision: {sorted(set(_SITES) - split)}\n"
        f"decisions about sites that no longer call a model: {sorted(split - set(_SITES))}")


def test_every_site_without_the_brief_says_why():
    short = [m for m, why in NO_BRIEF.items() if len(why) < 80]
    assert not short, f"say why in a sentence someone can check: {short}"


@pytest.mark.parametrize("site", sorted(BRIEF_SITES))
def test_every_judging_and_reading_site_takes_the_block_and_every_caller_passes_it(site):
    failures = [f for carrier in BRIEF_SITES[site] for f in carrier_failures(carrier)]
    assert not failures, "\n".join(failures)


def test_the_declared_gap_is_still_true():
    """The per-event relevance path goes without the block only because nothing in production
    hands it a model. The day something does, this fails and the gap must close."""
    injected = [f"{p.relative_to(ENGINE)}:{n.lineno}" for p in sorted(ENGINE.rglob("*.py"))
                for n in ast.walk(ast.parse(p.read_text(encoding="utf-8")))
                if isinstance(n, ast.Call) and any(k.arg == "relevance_llm" for k in n.keywords)]
    assert injected == [], f"a production caller now injects LLM-5's model: {injected}"
    for (caller, function, callee) in DECLARED_GAPS:
        tree = ast.parse(_source(caller, None))
        assert function in {k.rsplit(".", 1)[-1] for k in _defs(tree)}, (caller, function)
        assert any(getattr(n.func, "id", None) == callee for n in ast.walk(tree)
                   if isinstance(n, ast.Call)), (caller, callee)


# ── the planted control: a checker that stopped checking fails here ─────────────────────────
_PLANTED = '''
_PROMPT = "You judge one message.\\n\\nMESSAGE:\\n{content}"


def build_prompt(content, *, company_brief=""):
    return with_company_brief(_PROMPT.format(content=content), company_brief)


def forgot(content):
    return _PROMPT.format(content=content)


def builder_without_the_block(content):
    return content


class Request:
    company_brief: str = ""


def ask(content, brief):
    good = build_prompt(content, company_brief=brief)
    bad = build_prompt(content)
    return good, bad, Request(company_brief=brief), Request()
'''


def test_a_planted_site_that_omits_the_brief_is_caught_at_every_link():
    planted = {"planted/site.py": _PLANTED}
    unwrapped = carrier_failures(Wraps("planted/site.py", "_PROMPT"), planted)
    assert len(unwrapped) == 1 and "outside with_company_brief" in unwrapped[0]
    no_param = carrier_failures(Carries("planted/site.py", "builder_without_the_block",
                                        callers=()), planted)
    assert no_param and "takes no `company_brief`" in no_param[0]
    not_passed = carrier_failures(Carries("planted/site.py", "build_prompt",
                                          callers=("planted/site.py",)), planted)
    assert len(not_passed) == 1 and "does not pass `company_brief`" in not_passed[0]
    not_filled = carrier_failures(Field("planted/site.py", "Request",
                                        callers=("planted/site.py",)), planted)
    assert len(not_filled) == 1 and "Request(…) in ask does not pass" in not_filled[0]
    no_field = carrier_failures(Field("planted/site.py", "Missing", callers=()), planted)
    assert no_field == ["planted/site.py: Missing carries no `company_brief` field"]
