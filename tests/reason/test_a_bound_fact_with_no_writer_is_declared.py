r"""`B4` · every fact path a reasoning unit binds is written, or declared unwritten with a mover.

⛔ WHAT THIS CATCHES. Measured 2026-10-01 against production: `expertise._ROSTER` binds **22** fact
paths and **14 have zero rows** in `graph_facts`. One root — no CRM connector — and fourteen symptoms.
`core.policy` has skipped all 165 of its rows with `no_declared_input_available`, and **all four of its
essential fields are in that list**: it is not failing, it is correctly refusing to run on nothing.

⛔ AND THAT SKIP REASON CANNOT SAY WHICH IT IS. It conflates *"this situation did not carry the field"*
with *"nothing has ever written the field anywhere"* — different movers, and the second is not fixable
by looking at the situation at all.

⛔ TWO CORRECTIONS TO `07-DOES-IT-ACTUALLY-WORK.md` ARE PINNED HERE. B5 said
`core.signal_composition` is *"scheduled by nothing"* — `deal_health.py:16` schedules it, in a
capability that is not swept. And B3 said `deal.status` has *"no writer"* — it has **3 rows**.
"""
from __future__ import annotations

import ast
import importlib.util
import pathlib
import re

import pytest

from genios_engine.reason.unit_health import (DECLARED_UNWRITTEN, DECLARED_UNWRITTEN_PATHS,
                                              roster_fact_paths, undeclared_unwritten,
                                              written_after_all)

REPO = pathlib.Path(__file__).resolve().parents[2]
PROBE = REPO / "scripts/l2_fact_writers.py"
BOUND = roster_fact_paths()


# ── the declaration ──────────────────────────────────────────────────────────────────────────

def test_the_roster_binds_more_paths_than_it_declares_unwritten():
    """The census must be non-trivial in both directions: some paths written, some not."""
    assert len(BOUND) == 22, f"the roster now binds {len(BOUND)} paths — re-measure the census"
    assert len(DECLARED_UNWRITTEN_PATHS) == 14


@pytest.mark.parametrize("path", sorted(DECLARED_UNWRITTEN_PATHS))
def test_every_declared_path_is_actually_bound_by_the_roster(path):
    """⛔ A declaration for a path nothing reads is dead paperwork — and it would make the receipt
    exclude a path that was never at risk, hiding a real one behind the count."""
    assert path in BOUND, f"{path} is declared unwritten and no unit role binds it"


@pytest.mark.parametrize("path", sorted(DECLARED_UNWRITTEN_PATHS))
def test_every_declaration_names_a_reason_a_mover_its_binders_and_a_date(path):
    fact = DECLARED_UNWRITTEN[path]
    assert len(fact.reason.split()) >= 10, fact.reason
    assert fact.mover.strip() and len(fact.mover) > 8
    assert fact.bound_by, path
    assert fact.measured_on == "2026-10-01"


@pytest.mark.parametrize("path", sorted(DECLARED_UNWRITTEN_PATHS))
def test_a_declarations_binders_match_what_the_roster_actually_says(path):
    """⛔ TWO EXPRESSIONS OF ONE FACT, COMPARED. `bound_by` is written by hand and `roster_fact_paths`
    is derived. Two lists that are supposed to agree and are never compared eventually disagree —
    this programme has found that shape five times."""
    assert set(DECLARED_UNWRITTEN[path].bound_by) == set(BOUND[path]), (
        f"{path}: declared {sorted(DECLARED_UNWRITTEN[path].bound_by)} "
        f"vs roster {sorted(BOUND[path])}")


def test_a_declaration_without_a_mover_or_binders_is_refused():
    from genios_engine.reason.unit_health import UnwrittenFact

    ok = dict(reason="nothing writes it anywhere in the product today", mover="Harsh — a connector",
              bound_by=("core.policy.approval_value_field",), measured_on="2026-10-01")
    UnwrittenFact(**ok)
    with pytest.raises(ValueError, match="mover|close it"):
        UnwrittenFact(**{**ok, "mover": " "})
    with pytest.raises(ValueError, match="dead paperwork|unit roles"):
        UnwrittenFact(**{**ok, "bound_by": ()})
    with pytest.raises(ValueError, match="reason|undeclared"):
        UnwrittenFact(**{**ok, "reason": " "})
    with pytest.raises(ValueError, match="date|measurement"):
        UnwrittenFact(**{**ok, "measured_on": ""})


def test_core_policys_four_essential_fields_are_all_declared():
    """⛔ THE UNIT B4 IS ABOUT. All four of its `essential` roles bind paths nothing writes, which is
    why it has skipped on every one of its 165 production rows."""
    policy_paths = {p for p, binders in BOUND.items()
                    if any(b.startswith("core.policy.") for b in binders)}
    assert policy_paths <= DECLARED_UNWRITTEN_PATHS, sorted(policy_paths - DECLARED_UNWRITTEN_PATHS)
    assert len(policy_paths) >= 4


def test_the_movers_are_grouped_rather_than_repeated_per_path():
    """⛔ ONE ROOT, FOURTEEN SYMPTOMS. If every path named its own private mover, a reader would see
    fourteen problems instead of the five that exist. The CRM connector alone unblocks four."""
    movers = {fact.mover for fact in DECLARED_UNWRITTEN.values()}
    assert len(movers) <= 6, sorted(movers)
    crm = [p for p, f in DECLARED_UNWRITTEN.items() if "CRM" in f.mover]
    assert len(crm) >= 4, crm


# ── the helpers answer both directions ────────────────────────────────────────────────────────

def test_an_undeclared_empty_path_is_reported():
    counts = {p: 1 for p in BOUND}
    counts["thread.last_inbound"] = 0
    assert undeclared_unwritten(counts) == ("thread.last_inbound",)


def test_a_declared_empty_path_is_not_reported():
    """⛔ Only the DECLARED fourteen are zeroed here. My first version zeroed all 22 and then
    asserted nothing was reported — which correctly reported the eight written ones as undeclared.
    The test was wrong, not the helper: a fixture that makes everything missing proves nothing about
    a filter on what is declared missing."""
    counts = {p: (0 if p in DECLARED_UNWRITTEN_PATHS else 7) for p in BOUND}
    assert undeclared_unwritten(counts) == ()


def test_a_declared_path_that_starts_being_written_is_surfaced():
    """The good direction, and still a thing to go and update."""
    assert written_after_all({"deal.value": 12}) == ("deal.value",)
    assert written_after_all({p: 0 for p in DECLARED_UNWRITTEN_PATHS}) == ()


# ── one declaration, two readers, derived not copied ──────────────────────────────────────────

def test_the_path_list_is_derived_from_the_roster_and_not_copied():
    """⛔ A seventh role added to a unit must enter the census without an edit — the rule `S5.U02`
    established for `AXIS_SOURCES`, one level up."""
    import inspect

    src = inspect.getsource(roster_fact_paths)
    assert "_ROSTER" in src
    assert "roles" in src and "list_roles" in src
    assert '"deal.' not in src, "a fact path is hard-coded in the derivation"


def test_the_probe_keeps_no_copy_of_the_declaration():
    tree = ast.parse(PROBE.read_text())
    assigned = {t.id for node in ast.walk(tree) if isinstance(node, ast.Assign)
                for t in node.targets if isinstance(t, ast.Name)}
    for forbidden in ("DECLARED_UNWRITTEN", "BOUND", "ROSTER_FACT_PATHS"):
        assert forbidden not in assigned, f"the probe re-defines {forbidden}"


def test_both_readers_import_the_one_declaration():
    for path in (PROBE, REPO / "genios_engine/platform/receipts.py"):
        mods = {(n.module or "") for n in ast.walk(ast.parse(path.read_text()))
                if isinstance(n, ast.ImportFrom)}
        assert any("unit_health" in m for m in mods), f"{path.name} does not read the declaration"


def test_the_declaration_lives_beside_the_silence_one_and_not_in_a_parallel_module():
    """⛔ *Every silent lane carries a reason and a mover* is one doctrine at two grains. A reader
    looking for what is declared absent must find ONE file; a second module would be the fifth
    instance of two declarations of one idea in this programme."""
    assert not (REPO / "genios_engine/reason/fact_health.py").exists()
    src = (REPO / "genios_engine/reason/unit_health.py").read_text()
    assert "DECLARED_SILENT" in src and "DECLARED_UNWRITTEN" in src


# ── the receipt ───────────────────────────────────────────────────────────────────────────────

def test_the_receipt_exists_and_passes_on_zero():
    from genios_engine.platform import receipts as R

    found = [r for r in R.receipts("org_1") if "fact path" in r.claim]
    assert len(found) == 1
    assert found[0].layer == "L2"
    assert found[0].expect(0) is True and found[0].expect(1) is False


def test_the_receipt_asks_only_about_UNdeclared_paths():
    """⛔ It must exclude the declared fourteen, or it is permanently red for a reason this layer
    cannot clear — and `api/routes.py:161` computes `ready = not failed` from this list."""
    from genios_engine.platform.receipts import _UNDECLARED_UNWRITTEN_FACTS_SQL

    sql = _UNDECLARED_UNWRITTEN_FACTS_SQL(None)
    for declared in DECLARED_UNWRITTEN_PATHS:
        assert f"'{declared}'" not in sql, f"{declared} is declared and still queried"
    expected = len(BOUND) - len(DECLARED_UNWRITTEN_PATHS)
    assert f"select {expected} -" in sql, sql[:80]


def test_every_inlined_path_is_a_constant_of_fixed_shape():
    """⛔ The paths are SQL literals because `evaluate()` binds exactly one parameter. That is only
    safe because they are derived from module constants of a fixed shape."""
    for path in BOUND:
        assert re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+", path), path


def test_the_receipt_does_not_claim_that_no_bound_path_is_empty():
    from genios_engine.platform import receipts as R

    receipt = [r for r in R.receipts("org_1") if "fact path" in r.claim][0]
    assert "declared unwritten" in receipt.claim
    assert "mover" in receipt.detail


# ── the two corrections to 07, pinned ─────────────────────────────────────────────────────────

def test_core_signal_composition_IS_scheduled_by_a_capability():
    """⛔ `07` said *"scheduled by nothing"*. `DEAL_HEALTH_V1` schedules it — it is simply not swept,
    which is `ALARM A2` and not a defect in the unit."""
    from genios_engine.packs.capabilities import BUILTIN_CAPABILITIES
    from genios_engine.packs.capabilities.deal_health import DEAL_HEALTH_V1

    scheduled = {spec.reasoner_id for spec in DEAL_HEALTH_V1.reasoners}
    assert "core.signal_composition" in scheduled
    assert DEAL_HEALTH_V1 not in BUILTIN_CAPABILITIES, (
        "DEAL_HEALTH_V1 is now swept — B5 changed from an activation gap to a live lane; re-measure")


def test_deal_status_is_bound_and_is_not_declared_unwritten():
    """⛔ `07`'s B3 said `deal.status` has *"no writer"*. It has **3 rows**. A writer that reached 3 of
    293 nodes is a coverage problem, not an absent connector, and the two have different fixes."""
    assert "deal.status" in BOUND
    assert "deal.status" not in DECLARED_UNWRITTEN_PATHS, (
        "deal.status has 3 production rows — declaring it unwritten would state something false")
