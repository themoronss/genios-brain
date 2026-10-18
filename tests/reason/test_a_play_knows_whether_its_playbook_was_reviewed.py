"""STEP-11 · a compiled play knows whether its playbook was reviewed — read off the package, never re-derived.

    .venv/bin/python -m pytest tests/reason/test_a_play_knows_whether_its_playbook_was_reviewed.py -q

Tree `yc2_w27_s11 · M30.C2.L-logic.V1.U06`, `06` D3. The builder already counts the artifacts a
package rests on that no named human reviewed (`metadata.unreviewed_artifact_ids`, via
`capability_resolver.artifact_admission_reason`), and the count stopped there: no play, no signal and
no card could say *"playbook not yet reviewed"*. Each play now carries `review_state` — `accepted` or
`unreviewed` — taken from the PACKAGE's own list, so the manifest and the package cannot disagree about
which playbook was reviewed.
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packs" / "compiler"))

from l3_inputs import CAPABILITY, build_authoring_root, build_situation, build_slice  # noqa: E402

from genios_engine.packs.compiler import (  # noqa: E402
    DomainCompiler, ExpertBrainCatalog, InMemoryRuntimeBrains)
from genios_engine.reason.adapters.expertise import expertise_capability_manifest  # noqa: E402

def _playbook(root: Path, name: str, *, reviewed: bool) -> None:
    pid = f"sales.pb.lead_qualification.{name}"
    folder = root / "Sales Expertise" / "playbooks" / "lead_qualification"
    folder.mkdir(parents=True, exist_ok=True)
    status, review, reviewer = (("stable", "approved", "rohit") if reviewed
                                else ("draft", "unreviewed", ""))
    (folder / f"{name}.yaml").write_text(f"""
identity:
  id: {pid}
  name: {name.replace('_', ' ').title()}
  kind: playbook
  domain: sales
  scope: capability
  owner_capability: {CAPABILITY}
  version: 0.1.0
  status: {status}
purpose:
  statement: Carry the work from where it stands to the next decision.
when_to_use:
  situations: [sales.sit.anchor]
steps:
  - order: 1
    name: Note the date the decision is due
metadata:
  owner: Sales
  last_updated: "2026-10-09"
  review_status: {review}
  reviewed_by: "{reviewer}"
""")
    knowledge = (root / "Sales Expertise" / "capabilities/01-qualification/lead-qualification"
                 / "knowledge.yaml")
    text = knowledge.read_text()
    marker = "playbooks: {core: [], scoped: ["
    if marker in text:
        text = text.replace(marker, f"{marker}{pid}, ")
    else:
        text = text.replace("playbooks: {core: [], scoped: []}",
                            f"playbooks: {{core: [], scoped: [{pid}]}}")
    knowledge.write_text(text)


def _compiled(root: Path):
    compiler = DomainCompiler(catalog=ExpertBrainCatalog(root),
                              runtime_brains=InMemoryRuntimeBrains(), require_admission=False)
    situation, context = build_situation(), build_slice()
    return compiler.compile(situation, context), situation, context


def _states(package, situation, context) -> dict[str, str]:
    manifest = expertise_capability_manifest(package, root_entity_type="company",
                                             situation=situation, context=context)
    return {play.play_id.split(".")[-1]: play.metadata.get("review_state")
            for play in manifest.plays}


@pytest.fixture
def root(tmp_path):
    root = build_authoring_root(tmp_path)
    _playbook(root, "reviewed_play", reviewed=True)
    _playbook(root, "draft_play", reviewed=False)
    return root


def test_each_play_says_whether_its_playbook_was_reviewed(root):
    package, situation, context = _compiled(root)
    assert _states(package, situation, context) == {"reviewed_play": "accepted",
                                                     "draft_play": "unreviewed"}


def test_the_package_s_own_list_decides_not_a_second_reading(root):
    """Empty the package's list and the draft reads accepted; fill it and the reviewed one reads
    unreviewed — the adapter re-derives nothing, so the two records cannot drift apart."""
    package, situation, context = _compiled(root)
    ids = {r["id"].split(".")[-1]: r["id"] for r in package.expert_rules}
    cleared = dataclasses.replace(package, metadata={**package.metadata,
                                                     "unreviewed_artifact_ids": ()})
    assert set(_states(cleared, situation, context).values()) == {"accepted"}
    flagged = dataclasses.replace(package, metadata={
        **package.metadata, "unreviewed_artifact_ids": (ids["reviewed_play"], ids["draft_play"])})
    assert set(_states(flagged, situation, context).values()) == {"unreviewed"}


def test_a_package_that_names_no_list_reads_unreviewed(root):
    """Fail closed: a package from before the builder counted carries no list, and silence about a
    review is not a review."""
    package, situation, context = _compiled(root)
    bare = dataclasses.replace(package, metadata={
        k: v for k, v in package.metadata.items() if k != "unreviewed_artifact_ids"})
    assert set(_states(bare, situation, context).values()) == {"unreviewed"}
