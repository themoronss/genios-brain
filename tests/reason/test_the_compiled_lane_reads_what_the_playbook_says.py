"""STEP-11 · the compiled lane reads what the playbook and the situation say, and names every fallback.

    .venv/bin/python -m pytest tests/reason/test_the_compiled_lane_reads_what_the_playbook_says.py -q

Tree `yc2_w27_s11 · M30.C2.L-logic.V1.U02`. STEP-11 §8.2 measured three runtime values no corpus
could state: every compiled decision's consequence of doing nothing was the adapter's template
sentence (`reason/adapters/expertise.py`), every play's outcome window the 7-day default of
`PlayDefinition.window_days`, and every success signal empty. And every compiled play was LABELLED
BY ITS ID — `definition.get("name")` read a key no playbook has; the name is `identity.name` — so
the decider was shown `founder_office.pb.x.y` where the author wrote a name (`03` F121's "labels
fall back to ids").

A playbook may now declare `success_signal` and `outcome_window_days` (M30.C2.L-contract.V0.U01),
and the route plan carries a situation's own `do_nothing_consequence` (M30.C2.L-logic.V0.U04). The
adapter reads all three onto the manifest; where nothing was authored the old value remains, and
the manifest SAYS it is the fallback — per play (`window_source`, `success_signal_source`) and in
`metadata.runtime_sources`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "packs" / "compiler"))

from l3_inputs import CAPABILITY, build_authoring_root, build_situation, build_slice  # noqa: E402

from genios_engine.packs.compiler import (  # noqa: E402
    DomainCompiler, ExpertBrainCatalog, InMemoryRuntimeBrains)
from genios_engine.reason.adapters.expertise import (  # noqa: E402
    DEFAULT_WINDOW_DAYS, TEMPLATE_CONSEQUENCE, expertise_capability_manifest)

CONSEQUENCE = "The programme's cohort fills, and the next intake is six months away."
SUCCESS = "The programme's decision mail arrives."


def _playbook(root: Path, name: str, *, label: str, extra: str = "") -> str:
    """One capability-scoped playbook on the fixture's capability, listed in its knowledge."""
    pid = f"sales.pb.lead_qualification.{name}"
    folder = root / "Sales Expertise" / "playbooks" / "lead_qualification"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.yaml").write_text(f"""
identity:
  id: {pid}
  name: {label}
  kind: playbook
  domain: sales
  scope: capability
  owner_capability: {CAPABILITY}
  version: 0.1.0
  status: draft
purpose:
  statement: Carry the work from where it stands to the next decision.
when_to_use:
  situations: [sales.sit.anchor]
steps:
  - order: 1
    name: Note the date the decision is due
    done_when: The date is on file.
{extra}metadata:
  owner: Sales
  last_updated: "2026-10-09"
  review_status: unreviewed
""")
    knowledge = (root / "Sales Expertise" / "capabilities/01-qualification/lead-qualification"
                 / "knowledge.yaml")
    text = knowledge.read_text()
    marker = "playbooks: {core: [], scoped: ["
    if marker in text:
        text = text.replace(marker, f"{marker}{pid}, ")
    else:
        old = "playbooks: {core: [], scoped: []}"
        assert text.count(old) == 1
        text = text.replace(old, f"playbooks: {{core: [], scoped: [{pid}]}}")
    knowledge.write_text(text)
    return pid


def _consequence_on_anchor(root: Path, sentence: str) -> None:
    anchor = (root / "Sales Expertise" / "capabilities/01-qualification/lead-qualification"
              / "situations/anchor.yaml")
    anchor.write_text(anchor.read_text() + f"do_nothing_consequence: {sentence!r}\n")


def _manifest(root: Path):
    compiler = DomainCompiler(catalog=ExpertBrainCatalog(root),
                              runtime_brains=InMemoryRuntimeBrains(), require_admission=False)
    situation, context = build_situation(), build_slice()
    package = compiler.compile(situation, context)
    return expertise_capability_manifest(package, root_entity_type="company",
                                         situation=situation, context=context)


def _play(manifest, play_id: str):
    [play] = [p for p in manifest.plays if p.play_id.endswith(play_id.split(".")[-1])]
    return play


@pytest.fixture
def root(tmp_path):
    return build_authoring_root(tmp_path)


def test_a_playbook_s_success_and_window_reach_its_play(root):
    pid = _playbook(root, "follow_an_application", label="Follow an application",
                    extra=f"success_signal: {SUCCESS!r}\noutcome_window_days: 30\n")
    play = _play(_manifest(root), pid)
    assert (play.success_events, play.window_days) == ((SUCCESS,), 30)
    assert (play.metadata["success_signal_source"], play.metadata["window_source"]) == (
        "authored", "authored")


def test_nothing_authored_keeps_the_old_values_and_says_they_are_fallbacks(root):
    pid = _playbook(root, "plain", label="A plain play")
    manifest = _manifest(root)
    play = _play(manifest, pid)
    assert (play.success_events, play.window_days) == ((), DEFAULT_WINDOW_DAYS)
    assert (play.metadata["success_signal_source"], play.metadata["window_source"]) == (
        "none_authored", "default")
    sources = manifest.metadata["runtime_sources"]
    assert list(sources["plays_with_authored_window"]) == []
    assert list(sources["plays_with_authored_success"]) == []


def test_a_window_the_contract_cannot_hold_falls_back_and_says_why(root):
    """`PlayDefinition` refuses a window over 365 days; the schema only says ≥ 1. The play must not be
    lost to it, and the fallback must not pass for an authored value."""
    pid = _playbook(root, "too_long", label="Too long", extra="outcome_window_days: 400\n")
    play = _play(_manifest(root), pid)
    assert play.window_days == DEFAULT_WINDOW_DAYS
    assert play.metadata["window_source"] == "out_of_range"


def test_a_blank_success_signal_is_none(root):
    pid = _playbook(root, "blank", label="Blank", extra="success_signal: '   '\n")
    play = _play(_manifest(root), pid)
    assert play.success_events == ()
    assert play.metadata["success_signal_source"] == "none_authored"


def test_the_play_is_labelled_by_its_name_not_its_id(root):
    pid = _playbook(root, "named", label="Follow an application through to a decision")
    assert _play(_manifest(root), pid).label == "Follow an application through to a decision"


def test_the_situation_s_own_consequence_replaces_the_template(root):
    _playbook(root, "plain", label="A plain play")
    _consequence_on_anchor(root, CONSEQUENCE)
    manifest = _manifest(root)
    assert manifest.do_nothing_consequence == CONSEQUENCE
    assert manifest.metadata["runtime_sources"]["do_nothing_consequence"] == "situation"
    assert manifest.metadata["runtime_sources"]["do_nothing_situation_id"] == "sales.sit.anchor"


def test_without_one_the_template_remains_and_is_named(root):
    _playbook(root, "plain", label="A plain play")
    manifest = _manifest(root)
    situation_type = manifest.metadata["situation_type"]
    assert manifest.do_nothing_consequence == TEMPLATE_CONSEQUENCE.format(
        situation_type=situation_type)
    assert manifest.metadata["runtime_sources"]["do_nothing_consequence"] == "template"
    assert manifest.metadata["runtime_sources"]["do_nothing_situation_id"] is None


def test_the_sources_list_names_the_authored_plays(root):
    """Each list names exactly the plays that authored ITS field — a window alone is not a success."""
    _playbook(root, "both", label="Both",
              extra=f"success_signal: {SUCCESS!r}\noutcome_window_days: 14\n")
    _playbook(root, "window_only", label="Window only", extra="outcome_window_days: 21\n")
    _playbook(root, "plain", label="Plain")
    sources = _manifest(root).metadata["runtime_sources"]
    windows = [p.split(".")[-1] for p in sources["plays_with_authored_window"]]
    successes = [p.split(".")[-1] for p in sources["plays_with_authored_success"]]
    assert sorted(windows) == ["both", "window_only"]
    assert successes == ["both"]
