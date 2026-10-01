r"""⛔ A unit that COMPLETED and computed NOTHING is not a working unit.

WHAT THIS CATCHES, AND WHY NO EXISTING TEST COULD. Measured on production 2026-10-01, with the full
suite at 14,397 passed:

    core.impact        1,973 completed   100% silent
    core.opportunity   1,088 completed    94% silent

`core.impact` succeeds on every run and computes nothing. Its status is `completed`, so a probe
asking whether a unit SPEAKS reports it as speaking. Its own docstring is right to defend the
silence — *"Silence is not zero … a fabricated zero silently lies."* The defect is that nothing
downstream can tell an honest silence from a measurement.

⛔ WHAT IT COST. `core.tradeoff`'s `AXIS_SOURCES` names `benefit_source -> core.impact -> impact_bp`.
`core.impact` never publishes `impact_bp`, so `CostVersusBenefitPlugin` returned no observation on
**0 of 1,200** production rows — while `tests/reason/test_tradeoff_cost_axis.py` proves the axis works
on synthetic priors and **passes**.

**A green test proving an axis works, over 1,200 rows where it has never spoken.** The test supplies
the prior; production does not.
"""
from __future__ import annotations

import importlib.util
import pathlib

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]
PROBE_PATH = REPO / "scripts/l2_unit_said_nothing.py"


def _probe():
    spec = importlib.util.spec_from_file_location("l2_unit_said_nothing", PROBE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)                                      # type: ignore[union-attr]
    return module


def _declaration():
    """The ONE declaration. Both the probe and the receipt read this; neither keeps a copy."""
    from genios_engine.reason import unit_health

    return unit_health


def _is_silent(output):
    return _declaration().is_silent(output)


# ── the silence test itself, which is where the first version was wrong ───────────────────────

def test_a_finding_means_the_unit_spoke():
    assert _is_silent({"findings": [{"kind": "x"}]}) is False


def test_a_check_means_the_unit_spoke():
    """⛔ THE MISTAKE THE FIRST VERSION MADE. Counting empty `findings` alone reported
    `core.constraint` (2,681 completions, 0 findings) and `legacy.score_gate` (708, 0) as broken.
    Both are fine: their `output_kind` is `candidate_checks` and they emit CHECKS.

    *A crude slice that happens to fail looks exactly like a real finding.*"""
    assert _is_silent({"checks": [{"candidate_id": "x", "ok": True}]}) is False


def test_a_non_zero_metric_means_the_unit_spoke():
    assert _is_silent({"metrics": {"risk_bp": 1}}) is False


@pytest.mark.parametrize("output", [
    {},
    {"findings": [], "checks": [], "metrics": {}},
    {"metrics": {"impact_signal_count": 0}},
    {"findings": [], "checks": [], "metrics": {"a": 0, "b": 0}},
])
def test_nothing_at_all_is_silent(output):
    """⛔ `{"metrics": {"impact_signal_count": 0}}` is the literal shape `core.impact` emits on every
    one of 1,973 production runs — a count of how many dimensions reported, which is zero."""
    assert _is_silent(output) is True


def test_a_boolean_metric_is_not_mistaken_for_a_number():
    """`True` is an `int` in Python. A unit publishing only `matched: False` has said nothing
    numeric, and a probe that counted `True` as a non-zero metric would call it working."""
    assert _is_silent({"metrics": {"matched": False}}) is True
    assert _is_silent({"metrics": {"matched": True}}) is True


def test_a_json_string_payload_is_parsed_not_assumed():
    """The column comes back as a dict on psycopg and as a string on some drivers. A probe that
    assumed one would report every row silent on the other — and would look like a catastrophe."""
    assert _is_silent('{"findings": [{"kind": "x"}]}') is False
    assert _is_silent('{}') is True


# ── the pinned set ────────────────────────────────────────────────────────────────────────────

def test_the_known_silent_set_is_pinned_with_its_measurement():
    """⛔ PINNED so a NEW silent unit is a finding rather than a number somebody reads past."""
    declared = _declaration().DECLARED_SILENT
    assert set(declared) == {"core.impact", "core.opportunity"}
    assert declared["core.impact"].share_pct == 100
    assert declared["core.opportunity"].share_pct == 94


@pytest.mark.parametrize("unit", ["core.impact", "core.opportunity"])
def test_every_declared_silence_names_a_reason_a_mover_and_a_date(unit):
    """⛔ A declared silence with no mover is an undeclared silence with paperwork, and a share with
    no date is a claim rather than a measurement."""
    entry = _declaration().DECLARED_SILENT[unit]
    assert len(entry.reason.split()) >= 12, entry.reason
    assert entry.mover.strip() and "—" in entry.mover or len(entry.mover) > 8
    assert entry.measured_on == "2026-10-01"


def test_a_declaration_without_a_mover_is_refused():
    from genios_engine.reason.unit_health import DeclaredSilence

    with pytest.raises(ValueError, match="mover"):
        DeclaredSilence(reason="it is quiet", mover="  ", share_pct=100, measured_on="2026-10-01")
    with pytest.raises(ValueError, match="reason"):
        DeclaredSilence(reason=" ", mover="Harsh", share_pct=100, measured_on="2026-10-01")
    with pytest.raises(ValueError, match="date|measurement"):
        DeclaredSilence(reason="it is quiet", mover="Harsh", share_pct=100, measured_on="")


# ── U04 · ONE declaration, TWO readers, never three ───────────────────────────────────────────

def test_the_probe_keeps_no_copy_of_the_declaration():
    """⛔ It had one. A second copy is two declarations of one fact — the shape this programme has
    found five times, most recently `unrouted_l2_types`."""
    import ast

    tree = ast.parse(PROBE_PATH.read_text())
    assigned = {t.id for node in ast.walk(tree) if isinstance(node, ast.Assign)
                for t in node.targets if isinstance(t, ast.Name)}
    for forbidden in ("KNOWN_SILENT", "SILENT_THRESHOLD_PCT", "DECLARED_SILENT"):
        assert forbidden not in assigned, f"the probe re-defines {forbidden}"
    defined = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "_is_silent" not in defined, "the probe re-implements the silence test"


def test_both_readers_import_the_same_module():
    import ast

    for path in (PROBE_PATH, REPO / "genios_engine/platform/receipts.py"):
        mods = {(n.module or "") for n in ast.walk(ast.parse(path.read_text()))
                if isinstance(n, ast.ImportFrom)}
        assert any("unit_health" in m for m in mods), f"{path.name} does not read the declaration"


def test_no_other_module_declares_a_silent_set():
    """The third copy is the one nobody notices."""
    import ast

    offenders = []
    for py in sorted((REPO / "genios_engine").rglob("*.py")):
        if py.name == "unit_health.py":
            continue
        for node in ast.walk(ast.parse(py.read_text())):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id in ("DECLARED_SILENT", "KNOWN_SILENT",
                                                            "DECLARED_SILENT_IDS"):
                        offenders.append(f"{py.name}:{node.lineno}")
    assert offenders == [], offenders


def test_the_receipt_builds_its_sql_from_the_declaration():
    """⛔ Not a restated predicate. `SILENT_SQL` is the same rule `is_silent` applies in Python."""
    from genios_engine.platform.receipts import _UNDECLARED_SILENT_UNITS_SQL
    from genios_engine.reason.unit_health import (DECLARED_SILENT_IDS, SILENT_SQL,
                                                  SILENT_THRESHOLD_PCT)

    sql = _UNDECLARED_SILENT_UNITS_SQL(None)
    assert SILENT_SQL.strip() in sql
    assert str(SILENT_THRESHOLD_PCT) in sql
    for unit in DECLARED_SILENT_IDS:
        assert f"'{unit}'" in sql, f"{unit} is declared and not excluded by the receipt"


def test_the_inlined_unit_ids_cannot_carry_anything_a_caller_influences():
    """⛔ The declared set is inlined as SQL literals because `evaluate()` binds exactly one
    parameter. That is only safe because the ids are module constants of a fixed shape."""
    import re

    from genios_engine.reason.unit_health import DECLARED_SILENT_IDS

    for unit in DECLARED_SILENT_IDS:
        assert re.fullmatch(r"[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+", unit), unit


def test_the_receipt_exists_and_passes_on_zero():
    from genios_engine.platform import receipts as R

    found = [r for r in R.receipts("org_1") if "says nothing" in r.claim]
    assert len(found) == 1
    receipt = found[0]
    assert receipt.layer == "L2"
    assert receipt.expect(0) is True and receipt.expect(1) is False


def test_the_receipt_does_not_claim_that_no_unit_is_silent():
    """⛔ THE DESIGN CHOICE, ASSERTED. `api/routes.py` computes `ready = not failed` from this list.
    A receipt asserting "no unit is silent" would be permanently red for an upstream reason this
    layer cannot clear, and a gate that is always red is a gate nobody reads."""
    from genios_engine.platform import receipts as R

    receipt = [r for r in R.receipts("org_1") if "says nothing" in r.claim][0]
    assert "declared" in receipt.claim
    assert "mover" in receipt.detail


def test_the_undeclared_helper_answers_both_directions():
    d = _declaration()
    assert d.undeclared_silent({"core.risk": 100}) == ("core.risk",)
    assert d.undeclared_silent({"core.impact": 100}) == ()
    assert d.undeclared_silent({"core.risk": 50}) == ()
    assert d.drifted({"core.impact": 0, "core.opportunity": 99}) == ("core.impact",)


def test_the_threshold_is_below_a_hundred_on_purpose():
    """⛔ 90, not 100. A unit that speaks on one run in fifty is not working either, and demanding
    exactly 100% would let `core.opportunity`'s 94% pass as healthy."""
    d = _declaration()
    assert d.SILENT_THRESHOLD_PCT == 90
    assert min(x.share_pct for x in d.DECLARED_SILENT.values()) >= d.SILENT_THRESHOLD_PCT


def test_the_probe_is_read_only_and_says_so_first():
    """⛔ It answers a question; it may never change the thing it is asking about.

    ⛔ AST OVER THE `text(...)` ARGUMENTS, NOT A GREP OVER THE FILE. My first version scanned the
    whole source for write verbs and failed on its own prose — the docstring contains the word
    "update" in *"update KNOWN_SILENT with the new numbers"*. Checking the SQL means checking the
    SQL, which is what the statements are.
    """
    import ast

    src = PROBE_PATH.read_text()
    assert "set transaction read only" in src, "the probe does not declare its transaction read-only"
    # ⛔ IT MUST NOT *SET* IT — and the probe's own comment NAMES it, to explain that it never does.
    # My previous version asserted the string was absent and failed on that explanation. Sixth time
    # this session that a text check matched the prose describing the rule. So: AST, looking for an
    # assignment into `os.environ` or a `setdefault`, which is what "setting" actually is.
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Subscript) and "environ" in ast.unparse(target.value):
                    raise AssertionError(f"the probe writes an env var: {ast.unparse(target)}")
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in ("setdefault", "putenv", "update")
                and "environ" in ast.unparse(node.func.value)):
            raise AssertionError(f"the probe mutates the environment: {ast.unparse(node)[:60]}")

    statements: list[str] = []
    for node in ast.walk(ast.parse(src)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                and node.func.id == "text"):
            for arg in node.args:
                parts = ([arg] if isinstance(arg, ast.Constant)
                         else getattr(arg, "values", []) if isinstance(arg, ast.JoinedStr)
                         else [])
                statements += [str(p.value).lower() for p in parts
                               if isinstance(p, ast.Constant) and isinstance(p.value, str)]
    assert statements, "no SQL found — the AST walk is looking in the wrong place"
    for sql in statements:
        for verb in ("insert", "update", "delete", "truncate", "alter", "drop", "create"):
            assert verb not in sql, f"the probe writes: {verb!r} in {sql[:60]!r}"


def test_the_probe_separates_never_completed_from_completed_and_empty():
    """⛔ TWO DIFFERENT DEFECTS, and mixing them is how one hides the other. `core.relationship`
    (929 rows, never once completed) and `core.impact` (1,973 completions, all empty) need opposite
    investigations: one has no input, the other has input and produces nothing from it."""
    src = PROBE_PATH.read_text()
    assert "Units that have NEVER completed" in src
    assert "so the two are not mixed" in src


def test_the_probe_records_what_the_silence_cost():
    """A probe that reports a number without the consequence gets read as a dashboard. This one
    names the axis that never fired and the test that passes anyway."""
    doc = _probe().__doc__ or ""
    assert "cost_vs_benefit" in doc or "CostVersusBenefitPlugin" in doc
    assert "1,200" in doc or "1200" in doc
