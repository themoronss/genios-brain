"""Fixtures for the Layer 3 weld tests — built from the SHIPPED corpus, never from mocks.

Every test in this directory compiles a real `ExpertisePackage` out of `Domain Expertise/`. That
is deliberate and it is the point: the defect wave Y1 closes was not that a function was wrong, it
was that 446 authored artifacts reached nobody. A test suite that hand-builds a package with one
invented heuristic can prove the plumbing and cannot prove the unlock, and a green suite over
invented data is exactly the "activation would LOOK successful" state doc 03 warns about.

Hermetic all the same: `DomainCompiler` reads YAML off disk, `InMemoryRuntimeBrains` supplies the
three learned brains, `publisher=None` writes nothing. No database, no network, no clock — every
instant is `NOW`, passed in.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Sequence

import pytest

from genios_engine.context.quality.inference import ABSENT_FIELDS_KEY
from genios_engine.context.situation_bso import (
    build_business_situation,
    build_context_slice,
    gather_evidence_and_signals,
)
from genios_engine.packs.compiler import DomainCompiler, InMemoryRuntimeBrains
from genios_engine.packs.compiler.authoring import ExpertBrainCatalog, default_authoring_root
from genios_engine.packs.compiler.context_adapter import ContextAdapter

#: The one instant. `eval_time` is a parameter everywhere in this engine and the clock is read at
#: the process boundary; a test that called `utcnow()` would be testing the calendar.
NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)

#: The route that carries the corpus's blocking closing doctrine. `deal` + `verbal_yes` opens
#: `sales.closing.closing` (see `agreement-without-a-signature.yaml`), whose scoped rule
#: `urgency_must_belong_to_the_buyer` is `severity: blocking, enforced_by: L4_constraint` — the
#: artifact doc 03 names as the acceptance fixture, used here as itself rather than as a copy.
DEAL_FACTS = {"deal.status": "open", "thread.ball_in_court": "them"}
DEAL_OBSERVATIONS = ("proposal_sent", "verbal_yes")

#: The rule and the play the tests below name. Constants because three tests assert on the same
#: pair and a typo in one of them should not read as a passing test of something else.
URGENCY_RULE = "sales.rule.closing.urgency_must_belong_to_the_buyer"
CLOSING_PLAY = "sales.pb.closing.assume_forward__confirm_the_path"


class Compiled:
    """One compiled situation, with everything the weld needs to bind against it."""

    def __init__(self, package, situation, context) -> None:
        self.package = package
        self.situation = situation
        self.context = context

    @property
    def adapter(self) -> ContextAdapter:
        return ContextAdapter(self.situation, self.context)


def compile_situation(*, situation_type: str = "deal", domain: str = "sales",
                      facts: dict[str, Any] | None = None,
                      observations: Sequence[str] = DEAL_OBSERVATIONS,
                      edge_count: int = 4, absent: Sequence[str] = (),
                      unknowable: Sequence[str] = (),
                      composed: Any = None) -> Compiled:
    """Compile one situation through the shipped corpus.

    `absent` is L2.5.5's typed absence — the fact paths a connected source COULD have carried and
    none did. It is what turns `{absent: commitment.due_at}` from UNKNOWN into TRUE, which is the
    difference between the blocking rule abstaining and the blocking rule firing. Both states are
    tested, so both are reachable from this one argument.

    `composed` is BLG-18's stored `ComposedImportance` — the analytic stratum the sweep already
    ran. Optional and defaulting to None, so every existing caller compiles exactly the situation
    it compiled before; supplied, the BSO carries `importance_components` and wave Z5's
    projection has an analytic stratum to project. It is a `ComposedImportance`, never a dict,
    because the number and the arithmetic that produced it must not be able to arrive separately.
    """
    row = {
        "situation_id": f"sit_{situation_type}", "situation_type": situation_type,
        "domain": domain, "status": "active", "correlation_id": None,
        "confidence_overall": 82, "coverage": 70, "first_seen_at": NOW, "last_seen_at": NOW,
        "anchor_node_id": "node_1", "anchor_name": "Fixture", "anchor_type": "company",
    }
    signal_ids, evidence = gather_evidence_and_signals(None, "org_weld", None,
                                                       row["situation_id"])
    situation = build_business_situation(
        org_id="org_weld", situation=row, signal_ids=signal_ids, evidence=evidence,
        trace_id="trace_weld", composed=composed)
    context = build_context_slice(
        org_id="org_weld", situation=row,
        facts={path: {"value": value}
               for path, value in (DEAL_FACTS if facts is None else facts).items()},
        observations=[{"kind": kind} for kind in observations],
        neighbor=(edge_count, set(), {}), graph_version=1, eval_time=NOW,
        trace_id="trace_weld")
    metadata = dict(context.metadata)
    if absent:
        metadata[ABSENT_FIELDS_KEY] = list(absent)
    if unknowable:
        metadata["unknowable_fields"] = list(unknowable)
    context = replace(context, metadata=metadata)
    compiler = DomainCompiler(
        catalog=ExpertBrainCatalog(default_authoring_root()),
        runtime_brains=InMemoryRuntimeBrains(), publisher=None,
        # The shipped corpus is all-draft in measurement mode, which is how the live shadow pass
        # runs it too.
        require_admission=False)
    return Compiled(compiler.compile(situation, context), situation, context)


@pytest.fixture(scope="module")
def deal_with_absence() -> Compiled:
    """`commitment.due_at` typed GENUINELY_ABSENT -> the blocking rule's `when` is TRUE."""
    return compile_situation(absent=("commitment.due_at",))


@pytest.fixture(scope="module")
def deal_without_absence() -> Compiled:
    """No typed absence -> `{absent: commitment.due_at}` is UNKNOWN, and the rule abstains."""
    return compile_situation()


def code_identifiers(module) -> set[str]:
    """Every NAME a module's code mentions, with prose excluded.

    Structural checks in this directory ("zero LLM", "no embeddings") must read the code and not
    the docstrings, because the docstrings are where the absence is EXPLAINED — the citation
    binder's own opening quotes MAP B's *"embeddings: none"*, and a substring search over the file
    therefore fails on the sentence that promises the thing it is checking for. Parsing to an AST
    and collecting identifiers is the check the prose cannot fool in either direction.
    """
    import ast

    tree = ast.parse(Path(module.__file__).read_text())
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.FunctionDef):
            names.add(node.name)
        elif isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module or "")
            names.update(alias.name for alias in node.names)
    return {name.lower() for name in names}
