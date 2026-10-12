"""STEP-16 · what learning from you may not do — written FIRST, so every later unit of the block runs it.

    .venv/bin/python -m pytest -q tests/feedback/test_learning_from_you_arms_nothing.py \
        tests/feedback/test_the_declared_violation_is_blocked_by_arithmetic.py \
        tests/feedback/test_calibration_is_shadow_until_armed.py

`yc2_w27_s16` M46.C1.L-integration.V0.U01 (L6 Learning, `feedback/`).

⛔ WHY IT COMES FIRST. STEP-16 makes your verdicts and your words reach the expert. Every road that
does that runs beside two traps the plan names in its own words (`STEP-16` §8.4.10):

  * **calibration stays shadow** (`06` D13, S16-D5) — no unit of this block mutes a rule, nudges a
    gate or moves a pack's authority revision; arming waits for a tenant that asks, after `STEP-18`
    B22–B24;
  * **the `distinct_days` gate is never touched** (*do not fix it before ADR-10*) — no unit touches
    `feedback/units.unit_recommendation_learning`, `validate_learning`'s place before `govern`, or a
    stored policy floor; no correction goes through L6's evidence route; no expert commitment is
    marked `succeeded` (S16-D6), so no new graded ending reaches the one Adaptive unit that constant
    holds shut. The tripwire, `test_the_declared_violation_is_blocked_by_arithmetic.py`, is in this
    unit's verify and must stay a file this guard can name.

And calibration never scores an expert card: the expert's rule (`file_review`) and a question's
(`founder_question`) are rules of no pack manifest — calibration scores manifest rules only
(`feedback/calibrate.py`), so a verdict on an expert card or a question card can never become a mute.

⛔ HOW "A MODULE OF THE BLOCK" IS KNOWN. Read from `tree.yaml`'s `yc2_w27_s16` block — every unit's
`artifact` that is an engine module — never from a hand list that a later unit forgets to extend. The
statements are `platform/table_coverage`'s (the AST, constants resolved across modules, a loop over a
table-name constant expanded), so a write assembled from a constant is seen as the database sees it.
A module the block names and has not built yet is counted, not skipped: it is held the day it lands.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

from genios_engine.platform import table_coverage as tc

pytestmark = pytest.mark.unit

_REPO = Path(__file__).resolve().parents[2]
_BLOCK = "yc2_w27_s16"

#: ⛔ The tables that ARE calibration's teeth and the learned brains (`STEP-16` §8.4.10): a mute, a
#: gate nudge, a pack's authority (a row of `tenant_packs` carries its `authority_revision` and its
#: `lvl3_config` offsets), a durable brain entry, an Adaptive lease. Plus the stored learning policy
#: (its floors are the second way past `distinct_days`) and the executive commitment and its ending
#: (`succeeded` is the graded label the Adaptive unit learns from — S16-D6).
ARMING_TABLES: tuple[str, ...] = (
    "rule_mutes",
    "calibration_nudges",
    "tenant_packs",
    "learned_brain_entries",
    "temporary_memories",
    "learning_policies",
    "executions",
    "execution_outcomes",
)

#: ⛔ L6's evidence route — what a learning unit proposes from, governs and publishes. A correction is
#: your word on a file, read by the expert (S16-D1); it never enters this route. The verdict ledger
#: (`card_feedback_verdicts`) is NOT here on purpose: one ledger both doors write, read by every
#: verdict reader including the learning batch, is what M46.C2 builds.
EVIDENCE_ROUTE_TABLES: tuple[str, ...] = (
    "learning_objects",
    "learning_object_evaluations",
    "learning_transitions",
    "learning_runs",
    "learning_metrics",
    "learning_event_inbox",
    "learning_input_rejections",
    "knowledge_suggestions",
    "user_model_proposals",
    "user_models",
)

#: The modules this block ADDS — none exists at the block's base (`6650b1c4`), each is a unit's
#: artifact. A new module may not write L6's evidence route either, nor import a module that writes
#: an arming table (its write would be one call away and invisible to the statement check).
NEW_MODULES: tuple[str, ...] = (
    "genios_engine/deliver/verdicts.py",
    "genios_engine/context/founder_corrections.py",
    "genios_engine/reason/expert/correction_delta.py",
    "genios_engine/context/file_outcomes.py",
    "genios_engine/context/kind_numbers.py",
    "genios_engine/feedback/scorecard.py",
)

#: ⛔ The one file outside the block's artifacts that a unit of it edits: the extension's door, whose
#: two statements `M46.C2.L-data.V1.U02` moves into `deliver/verdicts`. Held like an artifact.
EDITED_BESIDE_AN_ARTIFACT: tuple[str, ...] = (
    "genios_engine/api/intelligence_routes.py",
)

#: ⛔ The tenant wipe (`/reset`, `api/account_routes._ORG_SCOPED_TABLES`) deletes every org table,
#: these included; the block adds its new table to that list (`0241`). A wipe is not learning, and
#: `account_routes` is no module of the block — it is named here so nobody adds it and reads its
#: deletes as arming.
NOT_A_WRITER_FOR_THIS_GUARD = "genios_engine/api/account_routes.py"


def _block_artifacts() -> tuple[str, ...]:
    data = yaml.safe_load((_REPO / "tree.yaml").read_text(encoding="utf-8"))
    out: list[str] = []
    for milestone in data[_BLOCK]["milestones"]:
        for category in milestone["categories"]:
            for layer in category["layers"]:
                for level in layer["levels"]:
                    for unit in level["units"]:
                        out.append(unit["artifact"])
    return tuple(out)


def _block_modules() -> tuple[str, ...]:
    names = {a for a in _block_artifacts() if a.startswith("genios_engine/") and a.endswith(".py")}
    return tuple(sorted(names | set(EDITED_BESIDE_AN_ARTIFACT)))


def _writes(module: str, tables: tuple[str, ...]) -> list[str]:
    usage = tc.table_usage()
    out = []
    for table in tables:
        for verb in ("insert", "update", "delete"):
            if module in usage.get(table, {}).get(verb, frozenset()):
                out.append(f"{verb} {table}")
    return out


# =================================================================================================
# 1 · what the guard is about is what the tree says
# =================================================================================================
def test_the_block_names_the_modules_this_guard_holds():
    modules = _block_modules()
    assert len(modules) >= 20, modules
    assert NOT_A_WRITER_FOR_THIS_GUARD not in modules
    # Every module the guard calls NEW is a unit's artifact, so the two lists cannot drift apart.
    assert set(NEW_MODULES) <= set(_block_artifacts()), sorted(set(NEW_MODULES) - set(_block_artifacts()))


def test_the_statement_reader_reads_the_tables_it_is_asked_about():
    """⛔ A guard over a reader that stopped reading passes on nothing. Each arming table has a known
    writer outside the block today; if the reader no longer sees it, this fails first."""
    for table, writer in (("rule_mutes", "genios_engine/feedback/calibrate.py"),
                          ("calibration_nudges", "genios_engine/feedback/calibrate.py"),
                          ("learned_brain_entries", "genios_engine/feedback/publisher.py"),
                          ("temporary_memories", "genios_engine/feedback/publisher.py"),
                          ("learning_policies", "genios_engine/feedback/orchestrator.py"),
                          ("executions", "genios_engine/executive/execution_store.py")):
        assert writer in tc.writers_of(table), (table, sorted(tc.writers_of(table)))
    assert "authority_revision" in tc.update_columns("tenant_packs")["genios_engine/feedback/calibrate.py"]


# =================================================================================================
# 2 · ⛔ no module of the block arms anything
# =================================================================================================
def test_no_module_of_the_block_writes_a_mute_a_nudge_an_authority_a_brain_a_lease_a_floor_or_a_commitment():
    armed = {m: w for m in _block_modules() if (w := _writes(m, ARMING_TABLES))}
    assert not armed, (
        f"⛔ a module of STEP-16 writes what calibration or a learned brain owns: {armed}. Calibration "
        "stays shadow (06 D13, S16-D5), nothing here writes a learned brain, the distinct_days gate "
        "and its policy floor are not touched, and no expert commitment is marked `succeeded` (S16-D6)")


def test_no_module_of_the_block_moves_a_packs_authority_revision():
    moved = {m: sorted(c) for m, c in tc.update_columns("tenant_packs").items()
             if m in _block_modules() and {"authority_revision", "lvl3_config"} & c}
    assert not moved, moved


def test_a_new_module_never_enters_l6s_evidence_route():
    routed = {m: w for m in NEW_MODULES if (w := _writes(m, EVIDENCE_ROUTE_TABLES))}
    assert not routed, (
        f"⛔ a module STEP-16 adds writes L6's evidence route: {routed}. A correction is your word on a "
        "file, read by the expert (S16-D1) — never a learning object beside the distinct_days gate")


def _arming_writers() -> set[str]:
    out: set[str] = set()
    usage = tc.table_usage()
    for table in ARMING_TABLES:
        for verb in ("insert", "update", "delete"):
            out |= set(usage.get(table, {}).get(verb, frozenset()))
    out.discard(NOT_A_WRITER_FOR_THIS_GUARD)
    return {p for p in out if p.startswith("genios_engine/")}


def _imported_modules(path: Path, *, package: str | None = None) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    if package is None:
        package = ".".join(path.relative_to(_REPO).with_suffix("").parts[:-1])
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                parts = package.split(".")
                parent = ".".join(parts[:len(parts) - node.level + 1])
                base = f"{parent}.{base}" if base else parent
            out.add(base)
            out |= {f"{base}.{alias.name}" for alias in node.names}
    return out


def test_the_import_reader_sees_each_way_a_writer_is_imported(tmp_path):
    """⛔ A positive control: the fence below reads modules that do not all exist yet, so the reader
    itself is proved on a module that imports calibration three ways."""
    sample = tmp_path / "sample.py"
    sample.write_text("import genios_engine.feedback.publisher\n"
                      "from genios_engine.feedback import calibrate\n"
                      "from ..feedback.reset import x\n", encoding="utf-8")
    seen = _imported_modules(sample, package="genios_engine.context")
    assert {"genios_engine.feedback.publisher", "genios_engine.feedback.calibrate",
            "genios_engine.feedback.reset"} <= seen, sorted(seen)


def test_a_new_module_imports_no_module_that_arms():
    writers = {w[:-3].replace("/", ".") for w in _arming_writers()}
    assert "genios_engine.feedback.calibrate" in writers, sorted(writers)
    reached = {}
    for module in NEW_MODULES:
        path = _REPO / module
        if path.exists():
            hit = sorted(_imported_modules(path) & writers)
            if hit:
                reached[module] = hit
    assert not reached, (
        f"⛔ a module STEP-16 adds imports a writer of a mute, a nudge, an authority, a brain, a lease, "
        f"a policy floor or a commitment: {reached}")


def test_what_is_held_and_what_is_not_built_yet_is_counted_not_skipped():
    """A module the block names and has not built yet holds nothing yet — counted here, so the count
    moves as the block is built and a module that vanished is seen. Never a skip."""
    modules = _block_modules()
    built = [m for m in modules if (_REPO / m).exists()]
    assert len(built) >= 15, built
    missing_new = [m for m in NEW_MODULES if not (_REPO / m).exists()]
    assert set(missing_new) <= set(NEW_MODULES)


# =================================================================================================
# 3 · ⛔ calibration stays shadow (06 D13, S16-D5)
# =================================================================================================
def test_calibration_apply_is_never_on_by_default():
    from genios_engine.platform.intelligence_onboarding import L4_DEFAULT_FEATURES, NOT_DEFAULT_ON
    from genios_engine.platform.l4_activation import FEATURE_CALIBRATION_APPLY

    assert FEATURE_CALIBRATION_APPLY in NOT_DEFAULT_ON, "06 D13: calibration_apply is never default-on"
    assert FEATURE_CALIBRATION_APPLY not in L4_DEFAULT_FEATURES


def _shipped_pack_rules() -> set[str]:
    from genios_engine.packs.wiring import BUILTIN_PACKS, _corpus_packs

    rules: set[str] = set()
    for pack in [*BUILTIN_PACKS, *_corpus_packs()]:
        for rule in pack.get("rules") or ():
            if isinstance(rule, dict) and rule.get("id"):
                rules.add(str(rule["id"]))
    return rules


def test_calibration_never_scores_an_expert_card_or_a_question_card():
    """Calibration scores the rules of a pack's manifest (`feedback/calibrate.py`). The expert's signal
    carries its capability's last segment as its rule (`reason/domain_shadow`), a question's carries
    `founder_question` — and no shipped pack names either, so a verdict on either card can never
    become a mute."""
    from genios_engine.reason.expert.asks import QUESTION_RULE
    from genios_engine.reason.expert.decide import CAPABILITY_ID

    expert_rule = CAPABILITY_ID.rsplit(".", 1)[-1]
    assert (expert_rule, QUESTION_RULE) == ("file_review", "founder_question")
    rules = _shipped_pack_rules()
    assert rules, "the packs name no rule at all — the reader broke, not the property"
    assert {expert_rule, QUESTION_RULE}.isdisjoint(rules), sorted({expert_rule, QUESTION_RULE} & rules)


def test_calibration_filters_by_the_manifest_it_scores():
    """The property above holds only while calibration keeps scoring manifest rules only."""
    src = (_REPO / "genios_engine" / "feedback" / "calibrate.py").read_text(encoding="utf-8")
    assert 'manifest.get("rules", [])' in src and 'if value["rule_id"] in current_rules' in src


# =================================================================================================
# 4 · ⛔ the distinct_days gate is never touched (do not fix it before ADR-10)
# =================================================================================================
def test_the_recommendation_unit_still_pins_one_day():
    from genios_engine.feedback import target_policy as TP

    pinned = {u: d for u, _t, d in TP.hardcoded_distinct_days()}
    assert pinned["recommendation_learning"] == 1, (
        "⛔ unit_recommendation_learning no longer passes distinct_days=1 — read "
        "target_policy.BLOCKED_BY_ARITHMETIC: this opens an auto-promoted durable ADAPTIVE write (ADR-10)")


def test_the_tripwire_is_still_there_to_run():
    """The tripwire is in this unit's verify: deleting it, or one of the three gates it holds, fails
    here too."""
    tripwire = _REPO / "tests" / "feedback" / "test_the_declared_violation_is_blocked_by_arithmetic.py"
    names = {n.name for n in ast.walk(ast.parse(tripwire.read_text(encoding="utf-8")))
             if isinstance(n, ast.FunctionDef)}
    assert {"test_the_durable_adaptive_proposal_is_held_before_governance_sees_it",
            "test_validation_still_runs_before_governance",
            "test_a_failed_validation_still_short_circuits",
            "test_the_loader_still_takes_the_stored_floor_verbatim",
            "test_the_schema_still_has_no_floor_either"} <= names, sorted(names)


def test_the_blocks_migrations_name_no_learning_table():
    """`0241` and `0242` are the block's own (`0210` is STEP-18's): neither alters, seeds or floors a
    table calibration, a learned brain, the policy or the commitment owns."""
    import re

    for artifact in _block_artifacts():
        if not artifact.startswith("migrations/") or "0210_" in artifact:
            continue
        path = _REPO / artifact
        if not path.exists():
            continue
        sql = path.read_text(encoding="utf-8").lower()
        sql = "\n".join(line.split("--", 1)[0] for line in sql.splitlines())
        named = [t for t in (*ARMING_TABLES, *EVIDENCE_ROUTE_TABLES) if re.search(rf"\b{t}\b", sql)]
        assert not named, (artifact, named)
