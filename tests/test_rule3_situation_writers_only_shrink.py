"""Rule 3.2 · THE RATCHET: the places that create or refresh a situation can only SHRINK.

GeniOS-011 S04.U1 builds the second of the three CI guards `speedrun008/GeniOS-008/01-RULES.md`
Rule 3 requires (`02-MIGRATION-PLAN.md` L0-5: "the situation-writer ratchet (starts at the 9 writers
in §3.3)"), over the list `02-MIGRATION-PLAN.md` L3-2 names.

WHY IT EXISTS. In the target architecture a situation is formed by L2's reasoning and only ADMITTED
by L3 (`00-ARCHITECTURE.md`, "How today's code differs"). Today nine sweep writers in `context/`
form and refresh `context_situations` rows BEFORE any reasoning runs. The migration retires them
one switched type at a time (Rule 2.5), so the list has exactly one legal direction: down. A tenth
writer, or a new call that forms a situation from somewhere else, is the old flow growing back —
and nothing stopped it. The nearest guard, `tests/context/test_situation_importance.py`
(`test_a_new_writer_of_context_situations_has_to_be_ranked_too`), greps five modules for the text
`insert into context_situations`: it cannot see a writer that UPDATEs a row
(`age_uncorrelated_situations`, `refresh_situation_importance`, `apply_lifecycle`), nor one that
writes through another module's helper (`refresh_state_situations` through
`support_situations._upsert`), and it is not shrink-only.

WHAT IT MEASURES — the AST of `genios_engine/` and `scripts/` (a script an operator runs is a
caller, as `platform/reachability.SCRIPTS_ARE_CALLERS` decided), never the text:

  * every string literal that INSERTs into or UPDATEs `context_situations` (a docstring is prose,
    not a statement, and is skipped), credited to the function holding it — or, for a statement
    kept in a module constant, to the functions that read that constant;
  * every call of — and every reference to — the nine writers and their helpers, resolved to the
    QUALIFIED function through `import`, `from … import … as …`, module aliases and package
    re-exports. A call resolved by name alone is a call to any function with that name
    (`platform/reachability.py` paid for that lesson twice); a same-named function elsewhere is
    not a writer here, and the negative controls below prove it.

WHAT TO DO WHEN IT FAILS.

  * "a new …" — a situation is being formed somewhere new. Under Rule 2 it belongs in L2: propose
    it as a situation mutation in a `ReasoningResult` and let `context/situation_publisher` admit
    it. Do not add it to the lists below; that is the one edit this file exists to refuse.
  * "no longer …" — a writer (or a call of one) is gone, usually because its type switched to L2.
    Delete its line here. That is the ratchet turning, and it is the only edit this file invites.
"""
from __future__ import annotations

import ast
import functools
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[1]
#: The callers that count: the engine, and the scripts an operator runs. `tests/` is excluded —
#: nobody runs a test to change production.
_SCANNED = ("genios_engine", "scripts")
_PLAN = _ROOT / "speedrun008" / "GeniOS-008" / "02-MIGRATION-PLAN.md"

_CTX = "genios_engine.context."

# ── the ratchet ──────────────────────────────────────────────────────────────────────────────

#: Where the ratchet STARTED: the nine sweep writers `02-MIGRATION-PLAN.md` L3-2 names. Frozen
#: history — never edited, never extended. `SITUATION_WRITERS` below must stay inside it.
_RATCHET_START: frozenset[str] = frozenset({
    _CTX + "situations.refresh_situations",
    _CTX + "situations.age_uncorrelated_situations",
    _CTX + "support_situations.refresh_support_situations",
    _CTX + "outreach_situations.refresh_state_situations",
    _CTX + "periodic.refresh_period_situations",
    _CTX + "meeting_touch.refresh_channel_touch_situations",
    _CTX + "document_register.refresh_document_situations",
    _CTX + "situation_bso.refresh_situation_importance",
    _CTX + "lifecycle.store.apply_lifecycle",
})
#: "starts at the 9 writers" (L0-5). A number, so that growing the start set is an edit of a
#: literal the docstring forbids rather than a quiet extra line in a set.
_RATCHET_STARTED_AT = 9

#: THE LIVE LIST — the writers that still form or refresh a situation before reasoning runs.
#: Delete a line when its type switches to L2 (Rule 2.5). Never add one.
SITUATION_WRITERS: dict[str, str] = {
    _CTX + "situations.refresh_situations":
        "the correlation sweep: one situation per correlated thread (INSERT … ON CONFLICT)",
    _CTX + "situations.age_uncorrelated_situations":
        "ages situations whose correlation went quiet (UPDATE, through `_SET_STATUS`)",
    _CTX + "support_situations.refresh_support_situations":
        "the support state readings (INSERT, through `_upsert` and `_reconcile`)",
    _CTX + "outreach_situations.refresh_state_situations":
        "the outreach readings, run twice per sweep (through `support_situations._upsert`)",
    _CTX + "periodic.refresh_period_situations":
        "tenant window aggregates, one per period domain (INSERT, then UPDATE to resolve)",
    _CTX + "meeting_touch.refresh_channel_touch_situations":
        "the calendar channel (INSERT, then UPDATE to resolve)",
    _CTX + "document_register.refresh_document_situations":
        "records control gaps (INSERT, through `_upsert` and `_reconcile`)",
    _CTX + "situation_bso.refresh_situation_importance":
        "ranks every live situation, run twice per sweep (UPDATE, through `_STORE_IMPORTANCE`)",
    _CTX + "lifecycle.store.apply_lifecycle":
        "applies a detected resolution to a situation's status (UPDATE)",
}

#: A statement of `context_situations` held OUTSIDE a writer, and exactly who reaches it. Each is a
#: helper of the ratchet: every user must be a writer above. This is the line that pins
#: "refresh_state_situations via support_situations._upsert" — a new caller of `_upsert` is a new
#: situation writer however it is spelled.
_HELPERS: dict[str, frozenset[str]] = {
    _CTX + "support_situations._upsert": frozenset({
        _CTX + "support_situations.refresh_support_situations",
        _CTX + "outreach_situations.refresh_state_situations"}),
    _CTX + "support_situations._reconcile": frozenset({
        _CTX + "support_situations.refresh_support_situations",
        _CTX + "outreach_situations.refresh_state_situations"}),
    _CTX + "document_register._upsert": frozenset({
        _CTX + "document_register.refresh_document_situations"}),
    _CTX + "document_register._reconcile": frozenset({
        _CTX + "document_register.refresh_document_situations"}),
    _CTX + "situations._SET_STATUS": frozenset({
        _CTX + "situations.age_uncorrelated_situations"}),
    _CTX + "situation_bso._STORE_IMPORTANCE": frozenset({
        _CTX + "situation_bso.refresh_situation_importance"}),
}

#: The two writers of `context_situations` that are NOT the ratchet, because neither forms nor
#: refreshes a situation (`l3-nine-situation-writers-and-missing-ratchet`: "writers outside the
#: list"). Pinned with their users, so the exception cannot quietly become a formation path.
_NOT_A_FORMATION: dict[str, tuple[str, frozenset[str]]] = {
    _CTX + "merge._merge_correlations": (
        "an identity merge folds the merged node's situations into the survivor's: it moves or "
        "removes rows a merge made duplicate, it never forms one",
        frozenset({_CTX + "merge.apply_merge"})),
    _CTX + "situations.resolve_situation": (
        "a person closes a situation from the API: a human decision, not a sweep",
        frozenset({"genios_engine.api.lifecycle_routes.settle_review",
                   "genios_engine.api.situation_routes.mark_resolved"})),
}

#: Every place that calls (or holds a reference to) a writer, and how many times — the
#: "create/refresh call" the brief forbids anywhere new. `process_pending` is the sweep; the
#: history replay and three L4 pilot scripts are the other callers measured at 0cc8d83c.
_WRITER_CALL_SITES: dict[str, dict[str, int]] = {
    _CTX + "situations.refresh_situations": {
        _CTX + "runner.process_pending": 1,
        _CTX + "backfill.backfill_layer2": 1,
        "scripts.l4_confidence_pilot.main": 1,
        "scripts.l4_pilot_seed.main": 1,
        "scripts.l4_urgency_floor_pilot.main": 1},
    _CTX + "situations.age_uncorrelated_situations": {_CTX + "runner.process_pending": 1},
    _CTX + "support_situations.refresh_support_situations": {_CTX + "runner.process_pending": 1},
    # The second reading pass (`runner.py`, L2.7) is the second call.
    _CTX + "outreach_situations.refresh_state_situations": {_CTX + "runner.process_pending": 2},
    _CTX + "periodic.refresh_period_situations": {_CTX + "runner.process_pending": 1},
    _CTX + "meeting_touch.refresh_channel_touch_situations": {_CTX + "runner.process_pending": 1},
    _CTX + "document_register.refresh_document_situations": {_CTX + "runner.process_pending": 1},
    # Ranked once after the analytic passes and again after the second reading pass.
    _CTX + "situation_bso.refresh_situation_importance": {
        _CTX + "runner.process_pending": 2,
        "scripts.l4_confidence_pilot.main": 1,
        "scripts.l4_pilot_seed.main": 1,
        "scripts.l4_urgency_floor_pilot.main": 1},
    # Reached on every drain through `context/lifecycle.detect_resolutions`.
    _CTX + "lifecycle.store.apply_lifecycle": {_CTX + "lifecycle.resolution.detect_resolutions": 1},
}

#: The table's NAME as a bare string — how a statement is built with a variable table
#: (`f"update {table} set …"`), which the statement scan cannot read. Each holder says what its
#: dynamic statement does. A new one has to be declared, or a dynamic UPDATE would walk past.
_TABLE_NAME_HOLDERS: dict[str, str] = {
    _CTX + "merge._NODE_REFERENCES":
        "apply_merge repoints anchor_node_id from the merged node to the survivor (UPDATE)",
    _CTX + "backfill.backfill_correlations": "the rebuild DELETEs a tenant's rows before re-deriving",
    "genios_engine.api.account_routes._ORG_SCOPED_TABLES":
        "the workspace /reset DELETEs a tenant's rows",
    "genios_engine.api.home_routes.home_summary": "a weekly COUNT for the home page (read only)",
    "genios_engine.api.routes._confidence_block": "a provenance label in a response (no SQL)",
    "scripts.equivalence_check.TABLES": "a read-only diff of two tenants",
}

# ── reading the source (AST only) ───────────────────────────────────────────────────────────

#: A statement that writes a situation row. Applied only to string LITERALS the AST finds — never
#: to comments, and never to a docstring.
_WRITES_A_SITUATION = re.compile(
    r"\b(?:insert\s+into|update|merge\s+into)\s+(?:only\s+)?(?:\"?\w+\"?\.)?\"?context_situations\b",
    re.IGNORECASE)
_TABLE = "context_situations"


@dataclass(frozen=True)
class _Module:
    """One parsed file, before any cross-module resolution."""
    name: str                                    # dotted: genios_engine.context.situations
    is_package: bool
    defines: frozenset[str]                      # module-level def / class / assigned name
    binds: dict[str, frozenset[str]]             # local name -> dotted target(s)
    uses: tuple[tuple[str, frozenset[str]], ...]  # (user scope, raw dotted targets), per use
    statements: tuple[tuple[str, int], ...]      # (holder, line) of a situation write
    table_names: tuple[tuple[str, int], ...]     # (holder, line) of a bare table name


def _dotted(path: Path, root: Path) -> tuple[str, bool]:
    parts = list(path.relative_to(root).with_suffix("").parts)
    is_package = parts[-1] == "__init__"
    if is_package:
        parts = parts[:-1]
    return ".".join(parts), is_package


def _read(name: str, is_package: bool, source: str) -> _Module:
    tree = ast.parse(source)
    parent: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[child] = node

    defines: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            defines.add(node.name)
        elif isinstance(node, ast.Assign):
            defines.update(t.id for t in node.targets if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defines.add(node.target.id)

    # Imports ANYWHERE in the file — `context/runner.py` imports most of its passes inside
    # `process_pending`, so a module-level-only reading would see none of them.
    binds: dict[str, set[str]] = {}
    package = name if is_package else name.rpartition(".")[0]
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.asname:
                    binds.setdefault(alias.asname, set()).add(alias.name)
                else:
                    head = alias.name.split(".")[0]
                    binds.setdefault(head, set()).add(head)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package
                for _ in range(node.level - 1):
                    base = base.rpartition(".")[0]
                base = f"{base}.{node.module}" if node.module else base
            else:
                base = node.module or ""
            for alias in node.names:
                if alias.name != "*":
                    binds.setdefault(alias.asname or alias.name, set()).add(f"{base}.{alias.name}")
    for own in defines:
        binds.setdefault(own, set()).add(f"{name}.{own}")      # no file imports itself

    def scope(node: ast.AST) -> str:
        chain: list[str] = []
        while node in parent:
            node = parent[node]
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                chain.append(node.name)
        return ".".join([name, *reversed(chain)]) if chain else name

    def holder(node: ast.AST) -> str:
        """The function holding `node`; at module level, the constant it is assigned to."""
        inner = scope(node)
        if inner != name:
            return inner
        top = node
        while parent.get(top) is not tree and top in parent:
            top = parent[top]
        targets: list[ast.expr] = []
        if isinstance(top, ast.Assign):
            targets = list(top.targets)
        elif isinstance(top, ast.AnnAssign):
            targets = [top.target]
        named = [t.id for t in targets if isinstance(t, ast.Name)]
        return f"{name}.{named[0]}" if named else name

    def qualify(expr: ast.AST) -> set[str]:
        if isinstance(expr, ast.Name):
            return set(binds.get(expr.id, ()))
        if isinstance(expr, ast.Attribute):
            return {f"{q}.{expr.attr}" for q in qualify(expr.value)}
        return set()

    callee_nodes = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    prose = {id(n.value) for n in ast.walk(tree)
             if isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant)}
    uses: list[tuple[str, frozenset[str]]] = []
    statements: list[tuple[str, int]] = []
    table_names: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            targets = qualify(node.func)
            if targets:
                uses.append((scope(node), frozenset(targets)))
        elif (isinstance(node, (ast.Name, ast.Attribute)) and isinstance(node.ctx, ast.Load)
              and id(node) not in callee_nodes and not isinstance(parent.get(node), ast.Attribute)):
            # A function or constant used as a VALUE — a dispatch table, `key=f`, a statement
            # constant handed to `conn.execute`. Only the outermost node of a dotted chain.
            targets = qualify(node)
            if targets:
                uses.append((scope(node), frozenset(targets)))
        elif (isinstance(node, ast.Constant) and isinstance(node.value, str)
              and id(node) not in prose):
            if _WRITES_A_SITUATION.search(node.value):
                statements.append((holder(node), node.lineno))
            elif node.value.strip() == _TABLE:
                table_names.append((holder(node), node.lineno))
    return _Module(name=name, is_package=is_package, defines=frozenset(defines),
                   binds={k: frozenset(v) for k, v in binds.items()}, uses=tuple(uses),
                   statements=tuple(statements), table_names=tuple(table_names))


@functools.lru_cache(maxsize=1)
def _repository_modules() -> dict[str, _Module]:
    out: dict[str, _Module] = {}
    for top in _SCANNED:
        for path in sorted((_ROOT / top).rglob("*.py")):
            name, is_package = _dotted(path, _ROOT)
            out[name] = _read(name, is_package, path.read_text(encoding="utf-8"))
    return out


@dataclass(frozen=True)
class _Analysis:
    statements: dict[str, tuple[int, ...]]       # holder -> lines
    table_names: dict[str, tuple[int, ...]]
    uses: dict[str, Counter]                     # canonical target -> Counter(user scope -> n)


def _canonical(target: str, modules: dict[str, _Module], depth: int = 0) -> str:
    """`target` with any package re-export followed to where the name is defined —
    `genios_engine.context.lifecycle.detect_resolutions` is `…lifecycle.resolution.detect_resolutions`."""
    parts = target.split(".")
    for cut in range(len(parts), 0, -1):
        module = modules.get(".".join(parts[:cut]))
        if module is None:
            continue
        rest = parts[cut:]
        if not rest or rest[0] in module.defines or depth > 8:
            return target
        onward = module.binds.get(rest[0], frozenset())
        if len(onward) == 1:
            (nxt,) = onward
            if nxt != f"{module.name}.{rest[0]}":
                return _canonical(".".join([nxt, *rest[1:]]), modules, depth + 1)
        return target
    return target


def _analyse(modules: dict[str, _Module]) -> _Analysis:
    statements: dict[str, list[int]] = {}
    table_names: dict[str, list[int]] = {}
    uses: dict[str, Counter] = {}
    for module in modules.values():
        for holder, line in module.statements:
            statements.setdefault(holder, []).append(line)
        for holder, line in module.table_names:
            table_names.setdefault(holder, []).append(line)
        for user, targets in module.uses:
            for target in {_canonical(t, modules) for t in targets}:
                uses.setdefault(target, Counter())[user] += 1
    return _Analysis(statements={k: tuple(v) for k, v in statements.items()},
                     table_names={k: tuple(v) for k, v in table_names.items()}, uses=uses)


@functools.lru_cache(maxsize=1)
def _repository() -> _Analysis:
    return _analyse(_repository_modules())


def _with_planted(planted: dict[str, str]) -> _Analysis:
    """The repository plus planted modules (`{dotted name: source}`) — the negative controls."""
    modules = dict(_repository_modules())
    for name, source in planted.items():
        modules[name] = _read(name, False, source)
    return _analyse(modules)


# ── the checks, each returning what is wrong (empty = green) ─────────────────────────────────

def _ratchet_problems(writers: dict[str, str] | frozenset[str]) -> list[str]:
    problems: list[str] = []
    if len(_RATCHET_START) != _RATCHET_STARTED_AT:
        problems.append(f"the ratchet's start set holds {len(_RATCHET_START)} writers; it started "
                        f"at {_RATCHET_STARTED_AT} and is frozen history")
    grown = sorted(set(writers) - _RATCHET_START)
    if grown:
        problems.append(f"a new situation writer joined the ratchet: {grown}. The list only "
                        "shrinks — propose the situation from L2 instead (Rule 2)")
    if len(writers) > _RATCHET_STARTED_AT:
        problems.append(f"the ratchet grew to {len(writers)} writers (it started at "
                        f"{_RATCHET_STARTED_AT} and may only fall)")
    return problems


def _statement_problems(found: _Analysis) -> list[str]:
    declared = set(_HELPERS) | set(_NOT_A_FORMATION)
    problems = [
        f"a new INSERT/UPDATE of context_situations in {holder} (line "
        f"{', '.join(map(str, lines))}): a situation is being written outside the ratchet"
        for holder, lines in sorted(found.statements.items())
        if holder not in SITUATION_WRITERS and holder not in declared]
    problems += [f"{holder} no longer writes context_situations — delete its line here"
                 for holder in sorted(declared - set(found.statements))]
    return problems


def _still_writing_problems(found: _Analysis) -> list[str]:
    """Each writer on the list writes a row itself or through one of its helpers."""
    through_helpers = {writer for owners in _HELPERS.values() for writer in owners}
    return [f"{writer} no longer writes a situation — the ratchet turns: delete it from "
            "SITUATION_WRITERS and from _WRITER_CALL_SITES"
            for writer in sorted(SITUATION_WRITERS)
            if writer not in found.statements and writer not in through_helpers]


def _user_problems(found: _Analysis, expected: dict[str, frozenset[str]], what: str) -> list[str]:
    problems: list[str] = []
    for target, users in sorted(expected.items()):
        actual = set(found.uses.get(target, Counter()))
        for new in sorted(actual - users):
            problems.append(f"a new use of {what} {target} in {new}: that makes {new} a "
                            "situation writer however it is spelled")
        for gone in sorted(users - actual):
            problems.append(f"{gone} no longer uses {target} — delete it here")
    return problems


def _call_site_problems(found: _Analysis) -> list[str]:
    problems: list[str] = []
    for writer in sorted(set(SITUATION_WRITERS) | set(_WRITER_CALL_SITES)):
        if writer not in SITUATION_WRITERS or writer not in _WRITER_CALL_SITES:
            problems.append(f"{writer} is in one of SITUATION_WRITERS / _WRITER_CALL_SITES and "
                            "not the other")
            continue
        actual = found.uses.get(writer, Counter())
        pinned = _WRITER_CALL_SITES[writer]
        for user in sorted(set(actual) | set(pinned)):
            have, want = actual.get(user, 0), pinned.get(user, 0)
            if have > want:
                problems.append(f"a new create/refresh call: {user} calls {writer} {have}× "
                                f"(pinned {want}×)")
            elif have < want:
                problems.append(f"{user} calls {writer} {have}× (pinned {want}×) — lower the "
                                "pin; the ratchet turns")
    return problems


def _table_name_problems(found: _Analysis) -> list[str]:
    problems = [f"a new bare '{_TABLE}' in {holder} (line {', '.join(map(str, lines))}): a "
                "statement built around a variable table name is invisible to the statement "
                "scan — say what it does in _TABLE_NAME_HOLDERS"
                for holder, lines in sorted(found.table_names.items())
                if holder not in _TABLE_NAME_HOLDERS]
    problems += [f"{holder} no longer names the table — delete its line here"
                 for holder in sorted(set(_TABLE_NAME_HOLDERS) - set(found.table_names))]
    return problems


# ── the guard ───────────────────────────────────────────────────────────────────────────────

def test_the_ratchet_only_shrinks() -> None:
    problems = _ratchet_problems(SITUATION_WRITERS)
    assert not problems, "\n".join(problems)


def test_every_writer_on_the_list_is_one_the_plan_names() -> None:
    """The list is the migration plan's L3-2 row, not one this file invented: each live writer is
    named there by its function or its module (backticked). A plan edit that retires a writer
    keeps this green; a writer the plan never named cannot join."""
    row = next((line for line in _PLAN.read_text(encoding="utf-8").splitlines()
                if line.startswith("| L3-2 |")), "")
    assert row, f"no L3-2 row in {_PLAN.relative_to(_ROOT)}"
    named = set(re.findall(r"`([^`]+)`", row))
    tails = {token.replace("/", ".").split(".")[-1] for token in named}
    stems = {token.replace("/", ".").split(".")[0] for token in named}
    unnamed = sorted(writer for writer in SITUATION_WRITERS
                     if writer.split(".")[-1] not in tails
                     and writer.split(".")[-2] not in stems | tails)
    assert not unnamed, f"writers the plan's L3-2 row does not name: {unnamed}"


def test_no_situation_is_written_outside_the_ratchet() -> None:
    problems = _statement_problems(_repository())
    assert not problems, "\n".join(problems)


def test_every_writer_on_the_list_still_writes_a_situation() -> None:
    problems = _still_writing_problems(_repository())
    assert not problems, "\n".join(problems)


def test_a_helper_that_writes_is_reached_only_from_its_writers() -> None:
    """`refresh_state_situations` writes through `support_situations._upsert` — so `_upsert` is
    pinned to its two writers, and a third caller is a new writer however it is spelled."""
    for owners in _HELPERS.values():
        assert owners <= set(SITUATION_WRITERS), f"a helper owned by a non-writer: {owners}"
    problems = _user_problems(_repository(), _HELPERS, "the situation-writing helper")
    assert not problems, "\n".join(problems)


def test_the_writes_that_are_not_formations_keep_their_callers() -> None:
    expected = {holder: users for holder, (_why, users) in _NOT_A_FORMATION.items()}
    problems = _user_problems(_repository(), expected, "the non-forming writer")
    assert not problems, "\n".join(problems)


def test_no_new_call_creates_or_refreshes_a_situation() -> None:
    problems = _call_site_problems(_repository())
    assert not problems, "\n".join(problems)


def test_a_variable_table_name_cannot_hide_a_write() -> None:
    problems = _table_name_problems(_repository())
    assert not problems, "\n".join(problems)


def test_the_scan_sees_every_kind_of_writer_the_old_guard_missed() -> None:
    """A guard that matches nothing passes for ever. The three kinds the text guard in
    `test_situation_importance.py` could not see are each visible here: an UPDATE inside a
    writer, an UPDATE kept in a module constant, and a write through another module's helper."""
    found = _repository()
    assert _CTX + "lifecycle.store.apply_lifecycle" in found.statements
    assert _CTX + "situations._SET_STATUS" in found.statements
    assert _CTX + "outreach_situations.refresh_state_situations" in found.uses[
        _CTX + "support_situations._upsert"]
    # and the package re-export is followed: runner imports `detect_resolutions` from the package
    assert _CTX + "runner.process_pending" in found.uses[
        _CTX + "lifecycle.resolution.detect_resolutions"]


# ── negative controls: a planted violation turns each check red ────────────────────────────

_PLANTED = "genios_engine.reason.planted_rule3_writer"


def test_control_a_tenth_writer_turns_the_ratchet_red() -> None:
    grown = dict(SITUATION_WRITERS)
    grown["genios_engine.context.planted.refresh_planted_situations"] = "planted"
    assert any("joined the ratchet" in p for p in _ratchet_problems(grown))
    assert any("grew to 10" in p for p in _ratchet_problems(grown))
    shrunk = dict(SITUATION_WRITERS)
    shrunk.pop(_CTX + "periodic.refresh_period_situations")
    assert not _ratchet_problems(shrunk), "a writer retired must pass — that is the ratchet"


@pytest.mark.parametrize("source", [
    # a plain import
    "from genios_engine.context.situations import refresh_situations\n"
    "def form(store, org):\n    return refresh_situations(store, org)\n",
    # an alias
    "from genios_engine.context.situations import refresh_situations as again\n"
    "def form(store, org):\n    return again(store, org)\n",
    # a module alias
    "from genios_engine.context import situations as S\n"
    "def form(store, org):\n    return S.refresh_situations(store, org)\n",
    # the full dotted path
    "import genios_engine.context.situations\n"
    "def form(store, org):\n    return genios_engine.context.situations.refresh_situations(store, org)\n",
    # a reference in a dispatch table, called later
    "from genios_engine.context.situations import refresh_situations\n"
    "PASSES = (refresh_situations,)\n",
], ids=["import", "alias", "module-alias", "dotted", "dispatch-table"])
def test_control_a_new_call_of_a_writer_turns_the_guard_red(source: str) -> None:
    problems = _call_site_problems(_with_planted({_PLANTED: source}))
    assert any(_PLANTED in p and "refresh_situations" in p for p in problems), problems


def test_control_a_name_alone_is_not_a_call_of_the_writer() -> None:
    """Qualified, not by name: a same-named function in another module is not the writer."""
    source = ("def refresh_situations(store, org):\n    return 0\n"
              "def run(store, org):\n    return refresh_situations(store, org)\n")
    problems = _call_site_problems(_with_planted({_PLANTED: source}))
    assert not [p for p in problems if _PLANTED in p], problems


def test_control_a_call_through_a_submodule_alias_is_resolved() -> None:
    source = ("from genios_engine.context.lifecycle import store as L\n"
              "def close(conn, org):\n    return L.apply_lifecycle(conn, org, situation_id='x', "
              "status='resolved')\n")
    problems = _call_site_problems(_with_planted({_PLANTED: source}))
    assert any("apply_lifecycle" in p and _PLANTED in p for p in problems), problems


def test_control_a_call_through_a_re_export_is_resolved() -> None:
    """A writer re-exported by another module is still the writer when called from there."""
    relay = "genios_engine.reason.planted_rule3_relay"
    problems = _call_site_problems(_with_planted({
        relay: "from genios_engine.context.periodic import refresh_period_situations\n",
        _PLANTED: (f"from {relay} import refresh_period_situations\n"
                   "def form(store, org):\n    return refresh_period_situations(store, org)\n"),
    }))
    assert any("refresh_period_situations" in p and _PLANTED in p for p in problems), problems


@pytest.mark.parametrize("source", [
    "def bump(conn):\n    conn.execute(\"UPDATE context_situations SET status = 'x'\")\n",
    "def mint(conn):\n    conn.execute('insert into context_situations (situation_id) values (:s)')\n",
    "def mint(conn, cols):\n    conn.execute(f'insert into context_situations ({cols}) values (1)')\n",
    "_STMT = ('update context_situations '\n         'set importance_bp = 0')\n"
    "def rank(conn):\n    conn.execute(_STMT)\n",
], ids=["update", "insert", "f-string", "module-constant"])
def test_control_a_new_statement_turns_the_guard_red(source: str) -> None:
    problems = _statement_problems(_with_planted({_PLANTED: source}))
    assert any(_PLANTED in p for p in problems), problems


def test_control_prose_about_a_statement_is_not_a_statement() -> None:
    source = ('"""This module never runs `update context_situations set …` itself."""\n'
              "def explain():\n    '''nor does `insert into context_situations` here.'''\n"
              "    return 1\n")
    problems = _statement_problems(_with_planted({_PLANTED: source}))
    assert not [p for p in problems if _PLANTED in p], problems


def test_control_a_new_caller_of_a_writing_helper_turns_the_guard_red() -> None:
    source = ("from genios_engine.context.support_situations import _upsert\n"
              "def mint(conn, org):\n    return _upsert(conn, org_id=org)\n")
    problems = _user_problems(_with_planted({_PLANTED: source}), _HELPERS,
                              "the situation-writing helper")
    assert any(_PLANTED in p and "_upsert" in p for p in problems), problems


def test_control_a_new_variable_table_name_turns_the_guard_red() -> None:
    source = ("TABLE = 'context_situations'\n"
              "def touch(conn):\n    conn.execute(f'update {TABLE} set status = 1')\n")
    problems = _table_name_problems(_with_planted({_PLANTED: source}))
    assert any(_PLANTED in p for p in problems), problems
