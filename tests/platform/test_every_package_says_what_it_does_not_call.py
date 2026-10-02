r"""Every package states what it does not call — one guard, eleven packages.

⛔ WHAT WAS WRONG. Four packages declared their own silences and seven had never been asked.
Measured 2026-10-01 with the corrected resolver: **147 top-level public functions were unreached by
production and declared nowhere.** Only `executive/` and `deliver/` had a reachability guard, and
**a guard that exists in two places out of eleven reads, from either of those two, as a solved
problem.**

⛔ ONE TEST, NOT NINE COPIES. The invariants are identical across packages — declared both
directions, a reason and a mover per entry, nothing left behind when a function is wired — so this
walks the registry below rather than repeating itself. **And that is what makes a NEW package
forgetting its declaration a build failure**, which nine hand-written copies could never do.

⛔ THE SCOPE FELL FROM 147 TO 109, AND EVERY SUBTRACTION WAS A MEASUREMENT, NOT A POLICY WAIVER:

    147   engine-only callers, nothing excluded
    134   - 13   `scripts/` counts as a caller       (all 13 are diagnostics or ops reads)
    123   - 11   declaration modules exclude themselves
    109   - 14   decorator-registered route handlers, which have no Python caller by design
     ↓
     46 of what remained were wired by REFERENCE — `Depends(f)`, a dispatch table, a registry —
        including `platform/auth.require_owner` with 35 of them. ⛔ Had the 123 been declared
        without that measurement, 46 of the entries would have been lies.

⛔ AND A FOURTH MECHANISM CANNOT BE MEASURED AT ALL. `store.purge_expired()` on a variable is
duck-typed dispatch, invisible to any static walk, so every entry in every table was hand-checked
against it: **one function was rescued** (`realtime.purge_expired` — retention IS enforced) and
**sixteen candidates were name collisions** (`list.extend` with 96 apparent hits, `Path.resolve`
with 74).
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from genios_engine.platform import reachability as R

#: ⛔ THE REGISTRY, AND IT IS THE POINT OF THIS MODULE. `(package, module, accessor prefix)`.
#: A package that gains public functions and no declaration module fails
#: `test_no_package_is_missing_its_declaration` below, which is the one thing nine copies of a test
#: could not have caught.
_DECLARATIONS = [
    ("capture", "genios_engine.capture.capture_health", "capture"),
    ("context", "genios_engine.context.context_health", "context"),
    ("packs", "genios_engine.packs.pack_health", "pack"),
    ("reason", "genios_engine.reason.reasoning_health", "reasoning"),
    ("executive", "genios_engine.executive.unreached", None),       # predates the registry
    ("deliver", "genios_engine.deliver.delivery_health", None),     # predates the registry
    ("feedback", "genios_engine.feedback.feedback_health", "feedback"),
    ("platform", "genios_engine.platform.platform_health", "platform"),
    ("contracts", "genios_engine.contracts.contract_health", "contract"),
    ("api", "genios_engine.api.api_health", "api"),
]

#: ⛔ `mcp/` IS ABSENT ON PURPOSE AND THAT IS A RESULT, NOT AN OMISSION. Its five public functions
#: are all `server.tool_*`, every one wired into a tool registry BY REFERENCE — so after the third
#: mechanism was measured, `mcp/` had **zero** unreached functions and needs no declaration at all.
#: `test_mcp_needs_no_declaration` asserts it, so the day it gains one, this registry must grow.
_NO_DECLARATION_NEEDED = ["mcp"]

_ENGINE = Path(R.__file__).resolve().parents[1]


def _module(dotted: str):
    import importlib
    return importlib.import_module(dotted)


def _tables(mod) -> dict[str, dict]:
    """Every declaration table on a module, whatever it chose to call them."""
    return {name: getattr(mod, name) for name in
            ("UNREACHED", "PULL_ONLY", "KNOWN_UNWIRED", "UNCUT_OVER", "REACHED_BY_DISPATCH")
            if isinstance(getattr(mod, name, None), dict)}


# ---------------------------------------------------------------------------------------------
# 1 · ⛔ the registry itself — the guard nine copies could not be
# ---------------------------------------------------------------------------------------------

def test_no_package_is_missing_its_declaration() -> None:
    """⛔ THE WHOLE REASON THIS IS ONE TEST. A package with public functions and no declaration
    module is the state all eleven were in before `STEP-17`, and it must not be reachable again by
    somebody adding a package."""
    declared = {pkg for pkg, _m, _p in _DECLARATIONS} | set(_NO_DECLARATION_NEEDED)
    from genios_engine.LAYERS import CROSS_CUTTING, LAYERS

    packages = {p for p in (set(LAYERS) | set(CROSS_CUTTING))
                if (_ENGINE / p).is_dir() and any((_ENGINE / p).glob("*.py"))}
    assert packages <= declared, (
        f"these packages have no entry in this registry: {sorted(packages - declared)} -- a "
        "package that is never asked what it does not call is a package where 'built, tested, "
        "green and called by nothing' is invisible")


def test_mcp_needs_no_declaration_because_nothing_is_unreached_there() -> None:
    """⛔ A RESULT, NOT AN OMISSION. `mcp/`'s five `server.tool_*` functions are wired into a tool
    registry by reference, so counting only calls reported all five as unreached and counting
    references reported none. If that changes, `mcp/` needs a declaration and this fails."""
    src = R.engine_sources(_ENGINE)
    for pkg in _NO_DECLARATION_NEEDED:
        found = R.unreached_in(_ENGINE / pkg, src)
        assert found == frozenset(), (
            f"{pkg}/ now has unreached functions and no declaration module: {sorted(found)}")


# ---------------------------------------------------------------------------------------------
# 2 · the invariants, over every package
# ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("pkg,dotted,prefix", _DECLARATIONS, ids=[d[0] for d in _DECLARATIONS])
def test_every_unreached_public_function_is_declared(pkg: str, dotted: str, prefix: str) -> None:
    """The whole point: a function nothing reaches either has a reason, or it is an oversight."""
    mod = _module(dotted)
    declared = frozenset().union(*(frozenset(t) for t in _tables(mod).values()))
    found = R.unreached_in(_ENGINE / pkg, R.engine_sources(_ENGINE))
    assert found <= declared, (
        f"unreached in {pkg}/ and declared nowhere: {sorted(found - declared)}")


@pytest.mark.parametrize("pkg,dotted,prefix", _DECLARATIONS, ids=[d[0] for d in _DECLARATIONS])
def test_no_declared_entry_names_a_function_that_does_not_exist(pkg, dotted, prefix) -> None:
    """⛔ Declared and written are two directions; one alone is half a guard. An entry for a deleted
    function reads as a considered decision about live code."""
    mod = _module(dotted)
    declared = frozenset().union(*(frozenset(t) for t in _tables(mod).values()))
    present = set(R.package_functions(_ENGINE / pkg))
    # ⛔ `executive/`'s PULL_ONLY is keyed by SURFACE, one of which is a bare module name, so a
    # key with no dot is a surface rather than a function and is not expected in `present`.
    gone = sorted(q for q in declared if "." in q and q not in present)
    assert not gone, f"{pkg}/ declares functions that do not exist: {gone}"


@pytest.mark.parametrize("pkg,dotted,prefix", _DECLARATIONS, ids=[d[0] for d in _DECLARATIONS])
def test_no_declared_entry_has_quietly_acquired_a_caller(pkg, dotted, prefix) -> None:
    """⛔ L4's actual bug: `summary.build_summary` sat in `PULL_ONLY` after `outbox._drain_claimed`
    started sending it on a tick, because that table had only the first direction.

    `PULL_ONLY` and `REACHED_BY_DISPATCH` are excluded — those entries are REACHED by design, which
    is what they exist to say.
    """
    mod = _module(dotted)
    tables = _tables(mod)
    silent = frozenset().union(*(frozenset(t) for name, t in tables.items()
                                 if name not in ("PULL_ONLY", "REACHED_BY_DISPATCH"))) \
        if any(n not in ("PULL_ONLY", "REACHED_BY_DISPATCH") for n in tables) else frozenset()
    found = R.unreached_in(_ENGINE / pkg, R.engine_sources(_ENGINE))
    wired = sorted(q for q in silent if "." in q and q not in found)
    assert not wired, (
        f"{pkg}/ declares these as uncalled and the engine now reaches them -- the entry is the "
        f"lie, not the call: {wired}")


@pytest.mark.parametrize("pkg,dotted,prefix", _DECLARATIONS, ids=[d[0] for d in _DECLARATIONS])
def test_every_entry_carries_a_reason_and_a_mover(pkg, dotted, prefix) -> None:
    """`reason/unit_health.DeclaredSilence` refuses construction without a mover, for this reason: a
    silence with no named mover is an undeclared silence with paperwork.

    ⛔ THIS FIRST DEMANDED TWO LONG STRINGS PER ENTRY AND FAILED ON TWO CORRECT TABLES.
    `executive/PULL_ONLY` is keyed `(route, why)` and a route is short by nature — `"GET /briefs"`
    is eleven characters. `deliver/UNCUT_OVER` is a four-tuple whose third element is `None` for
    every unmeasured tier. **The tables deliberately differ in shape**, so the only thing a generic
    guard may assert is what is actually common: every entry says something substantial SOMEWHERE,
    and has at least two parts so a reason is never left without a mover.
    """
    thin = []
    for table_name, table in _tables(_module(dotted)).items():
        for name, value in table.items():
            parts = [s for s in value if isinstance(s, str)]
            if len(parts) < 2 or max((len(s) for s in parts), default=0) < 80:
                thin.append(f"{table_name}:{name}")
    assert not thin, f"{pkg}/ entries whose reason or mover says nothing usable: {thin}"


#: ⛔ THE MOVER VOCABULARY IS EXACTLY TWO FORMS, AND BOTH ARE DELIBERATE.
#:
#:   MOVES WHEN <condition>   the entry moves when something becomes true
#:   MOVES WITH <other entry> the entry moves when its PAIR moves — two guards over one map from
#:                            opposite sides, where naming a separate condition would be a lie
#:
#: ⛔ MEASURED 2026-10-02 BEFORE THIS GUARD WAS WRITTEN, because the obvious version of it was
#: wrong. I had recorded `MOVES WITH` in `feedback_health.py` as a DEVIATION from the house
#: convention (`03-FINDINGS` §F17) — and the distribution refutes it: **29 occurrences across nine
#: of the thirteen declaration modules**, against 115 `MOVES WHEN`. It is a convention, and the
#: existing guard above is right to accept both. *Do not weaken a verify to make it pass, and do
#: not tighten one to make it fail.*
#:
#: ⛔ So this guard does the only thing left that is true: it rejects a THIRD form. One existed —
#: `context_health.py` carried `MOVES ON A SEAM DECISION`, normalised to `MOVES WHEN` in the same
#: step — and a vocabulary of two that nothing enforces becomes a vocabulary of five.
MOVER_FORMS = ("MOVES WHEN", "MOVES WITH")


@pytest.mark.parametrize("pkg,dotted,prefix", _DECLARATIONS, ids=[d[0] for d in _DECLARATIONS])
def test_every_mover_uses_one_of_the_two_recognised_forms(pkg, dotted, prefix) -> None:
    """⛔ A mover-shaped string must say `MOVES WHEN` or `MOVES WITH` — nothing else.

    ⛔ IT DOES NOT DEMAND A MOVER, AND THAT IS THE WHOLE CARE IN IT. Three tables correctly have
    none: `executive/PULL_ONLY` and `deliver/PULL_ONLY` are keyed `(route, why)`, and
    `feedback/target_policy.UNIT_TARGETS` is `(target, why)` — the mover lives in `DELEGATED` and
    `DURABLE_FROM_A_MEASUREMENT` beside it. Demanding one everywhere would fail on all three, which
    is **exactly the mistake the guard above records making** when it demanded two long strings.

    So the assertion is conditional: *where* a string says `MOVES`, it must use a recognised form.
    """
    wrong = []
    for table_name, table in _tables(_module(dotted)).items():
        for name, value in table.items():
            for part in (s for s in value if isinstance(s, str)):
                for idx in (i for i in range(len(part)) if part.startswith("MOVES ", i)):
                    if not any(part.startswith(f, idx) for f in MOVER_FORMS):
                        wrong.append(f"{table_name}:{name} → {part[idx:idx + 24]!r}")
    assert not wrong, (
        f"{pkg}/ movers using a form that is neither {MOVER_FORMS[0]} nor {MOVER_FORMS[1]}: "
        f"{wrong}")


@pytest.mark.parametrize("pkg,dotted,prefix", _DECLARATIONS, ids=[d[0] for d in _DECLARATIONS])
def test_the_declaration_module_is_excluded_from_its_own_scan(pkg, dotted, prefix) -> None:
    """⛔ IT WAS A HAND-MAINTAINED LIST FOR ABOUT A MINUTE. `SELF_DECLARING` named them, and the
    first thing that happened after writing it was adding `capture_health.py` and forgetting to add
    its name — so the scan demanded that module's own four helpers as declared silences.

    **A list you must remember to extend is a list that will be wrong.** A declaration module is now
    detected by the fact that makes it one: it imports `platform/reachability.py`.
    """
    mod = _module(dotted)
    path = Path(mod.__file__)
    assert R._is_declaration_module(path), f"{path.name} is not recognised as a declaration module"
    stem = path.stem
    assert not any(q.startswith(f"{stem}.") for q in R.package_functions(_ENGINE / pkg)), (
        f"{path.name} is being scanned as ordinary code")


# ---------------------------------------------------------------------------------------------
# 3 · ⛔ the two policy decisions, visible rather than buried
# ---------------------------------------------------------------------------------------------

def test_the_script_policy_is_one_named_constant_and_the_default_follows_it() -> None:
    """⛔ `SCRIPTS_ARE_CALLERS` decides whether an ops CLI counts, across all eleven packages. It
    was taken while the question was open, so it is **one constant to flip** and nothing reads
    `scripts/` around it. Measured: counting it rescues **13**, every one a diagnostic or ops read,
    and seven of those would be self-excluded anyway — so it genuinely decides six."""
    assert isinstance(R.SCRIPTS_ARE_CALLERS, bool)
    with_s = len(R.engine_sources(_ENGINE, include_scripts=True))
    without = len(R.engine_sources(_ENGINE, include_scripts=False))
    assert with_s > without, "the scripts directory is no longer read at all"
    assert len(R.engine_sources(_ENGINE)) == (with_s if R.SCRIPTS_ARE_CALLERS else without), (
        "the default stopped following SCRIPTS_ARE_CALLERS, so flipping it would do nothing")


def test_a_reference_is_a_wiring_mechanism_and_rescued_the_auth_dependencies() -> None:
    """⛔ THE MEASUREMENT THAT SAVED 46 ENTRIES FROM BEING LIES. A function reached only as a VALUE
    — `Depends(f)`, a dispatch table, a registry — is wired. `platform/auth.require_owner` has 35
    such references and would otherwise have been declared a silence."""
    refs = R.qualified_value_refs(R.engine_sources(_ENGINE))
    for module, name, floor in (("auth", "require_owner", 20), ("auth", "get_auth_ctx", 20),
                                ("auth", "require_admin", 15)):
        assert refs.get((module, name), 0) >= floor, (
            f"{module}.{name} has fewer than {floor} value references -- if the auth dependencies "
            "stopped being wired this way, every package's scan needs re-measuring")
    calls = R.qualified_call_counts(R.engine_sources(_ENGINE))
    assert calls.get(("auth", "require_owner"), 0) == 0, (
        "require_owner is now CALLED as well, which is fine -- but this test's evidence for the "
        "reference mechanism has gone and should be re-chosen")


def test_a_decorator_registered_route_is_not_demanded_as_a_declaration() -> None:
    """⛔ 14 public functions in `api/` are registered by a FastAPI decorator and have no Python
    caller by design. Asking `api/` for 14 declarations that all say the same thing is paperwork,
    and discovering it AFTER writing them is the expensive order.

    ⛔ AND THE CHECK MUST BE PER MODULE. My first version took the UNION of decorated names across
    all of `api/` and asked whether any scanned function was in it — so a plain `evaluate` in
    `policy_routes` collided with a decorated `evaluate` elsewhere and the test failed on correct
    code. **The same name-collision class the qualified resolver exists to fix**, reproduced in the
    test that documents it.
    """
    per_module = {p.stem: R.decorated_functions(p) for p in (_ENGINE / "api").glob("*.py")}
    assert sum(len(v) for v in per_module.values()) >= 10, (
        "the route handlers stopped being decorator-registered -- re-measure api/ before trusting "
        "its declaration")
    leaked = [q for q, module in R.package_functions(_ENGINE / "api").items()
              if q.split(".", 1)[1] in per_module.get(module, frozenset())]
    assert not leaked, f"decorated functions are in the scanned set: {leaked}"


# ---------------------------------------------------------------------------------------------
# 4 · ⛔ the shape rule, asserted
# ---------------------------------------------------------------------------------------------

def test_a_package_gets_the_tables_its_triage_needs() -> None:
    """⛔ THE RULE, AND IT IS A FINDING RATHER THAN A STYLE. `deliver/` needed FOUR tables because
    it carries a second delivery control plane and five real defects. `capture/` needed ONE,
    because its seven are all tooling and reports. `platform/` needed TWO — the second for the one
    function reached by duck-typed dispatch, since putting a REACHED function into `UNREACHED`
    would be a lie by that table's own name.

    **An empty table asserts nothing, and a table that asserts nothing teaches a reader to skip the
    ones that do.** So this asserts the shapes differ rather than demanding they match.
    """
    shapes = {pkg: sorted(_tables(_module(dotted))) for pkg, dotted, _p in _DECLARATIONS}
    assert shapes["capture"] == ["UNREACHED"]
    assert shapes["platform"] == ["REACHED_BY_DISPATCH", "UNREACHED"]
    assert len(shapes["deliver"]) >= 3, (
        "deliver/ lost a table -- it carried an un-cut-over architecture, deliberate silences and "
        "defects, which is why it needed more than one")
    assert len({tuple(s) for s in shapes.values()}) > 1, (
        "every package now has the same tables, which means either the triages converged or "
        "somebody copied a shape instead of reading their package")


def test_no_table_in_any_package_overlaps_another() -> None:
    """A function in two tables has two reasons and the build cannot say which is current."""
    for pkg, dotted, _p in _DECLARATIONS:
        tables = _tables(_module(dotted))
        seen: dict[str, str] = {}
        for table_name, table in tables.items():
            for name in table:
                assert name not in seen, (
                    f"{pkg}/: {name} is in both {seen[name]} and {table_name}")
                seen[name] = table_name


def test_every_entry_naming_a_step_names_a_real_one() -> None:
    """⛔ A defect parked with a step number is only parked if the step exists. `KNOWN_UNWIRED` in
    `deliver/` is empty now, and this holds for whoever refills it."""
    programme = _ENGINE.parent / "speedrun008" / "YCW27"
    if not programme.is_dir():                                # pragma: no cover
        pytest.skip("the programme folder is not in this checkout")
    steps = {m.group(0) for p in programme.rglob("STEP-*.md")
             for m in [re.match(r"STEP-\d{2}", p.name)] if m}
    for pkg, dotted, _p in _DECLARATIONS:
        for table_name, table in _tables(_module(dotted)).items():
            for name, value in table.items():
                for part in value:
                    if isinstance(part, str):
                        for ref in re.findall(r"STEP-\d{2}", part):
                            assert ref in steps, (
                                f"{pkg}/ {table_name}:{name} points at {ref}, which has no step "
                                "file")
