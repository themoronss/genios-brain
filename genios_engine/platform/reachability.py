r"""Who calls what, measured from the AST — the shared machinery every package's declaration uses.

⛔ WHY THIS IS IN `platform/` AND NOT IN A LAYER. `executive/unreached.py` wrote this first and
`deliver/delivery_health.py` imported it from there, which was correct while there were two users:
`deliver/` is PRODUCT layer 6 and `executive/` is 5, so that import is DOWNWARD and legal. ⛔ But
`capture/` is layer **1**, and `capture/ -> executive/` is an UPWARD import that
`tests/test_layer_topology.py` fails the build over. **Two users is an import; eleven is an
extraction**, and the only place every layer may import from is `CROSS_CUTTING`.

⛔ THIS MODULE IMPORTS NOTHING FROM THE ENGINE, ON PURPOSE. Pure `ast` and `pathlib`. A reachability
tool that imported a layer could not be used by the layer below it, which is the whole reason it
moved.

⛔ WHAT IT COST TO GET THE RESOLVER RIGHT, recorded because both mistakes are easy to make again:

  * `called_names` counts by NAME ALONE, so every function sharing a name shares one count.
    `queue.claim_due()` in `capture/parked/refetch.py` — a method of `InMemoryRefetchQueue` — made
    `deliver/spine.claim_due` read as reached, and a whole tier of the v2 delivery path was
    invisible. Switching `executive/`'s own guard to the qualified resolver grew its declared
    inventory from FIVE to TEN; `readiness.read` had **11** apparent callers and none.
    **A call resolved by name alone is a call to any function with that name.**
  * ⛔ AND THE FIRST FIX WAS WORSE THAN THE BUG. It credited every imported module with every call
    name in the file — 443,610 pairs — and reported `lane_display.describe` and `runner.run_all` as
    unreached, because both are called through an alias. **A resolver that is merely stricter is not
    more correct.** Aliases are resolved to `(module, original)` here, which is what makes the
    answer trustworthy in BOTH directions.

Both resolvers stay, and the asymmetry is deliberate — see `qualified_call_counts`.
"""
from __future__ import annotations

import ast
from pathlib import Path

# ---------------------------------------------------------------------------------------------
# the two policy decisions every package's scan depends on
# ---------------------------------------------------------------------------------------------

#: ⛔ DOES A SCRIPT COUNT AS A CALLER? **Yes**, and this is the one line to flip if that is wrong.
#:
#: `tests/` is excluded because nobody runs a test to learn something about production. A script an
#: operator runs is exactly that, so the same reasoning points the other way. Measured 2026-10-01:
#: counting `scripts/` makes **13** of 147 engine-wide unreached functions reached, and every one of
#: the thirteen is a diagnostic or an ops read — `reason/unit_health` ×5, `uncited_lanes` ×2,
#: `context/slice_weight` ×2, `platform/l2_activation`, `platform/stage_timer`, `capture/journey`,
#: `context/lane_health`.
#:
#: ⛔ RECORDED AS MY CALL, NOT AS A FACT. It is a policy across all eleven packages and it was
#: taken while the question was open with Rohit. Flipping it is one constant and a re-run; nothing
#: else in this module or any declaration reads `scripts/` directly.
#:
#: ⛔ And seven of the thirteen are a package's own declaration-module helpers, which
#: `SELF_DECLARING` excludes anyway — so this constant genuinely decides **six**.
SCRIPTS_ARE_CALLERS: bool = True

#: ⛔ A declaration module's own helpers are called by the test that enforces the declaration, and
#: by nothing else — BY DESIGN. `tests/test_the_executive_says_what_it_does_not_call.py` already
#: skips `unreached.py` with the reason written in: *"its callers are this file by design. Scanning
#: it would demand a declared silence for each of its own helpers — noise that says nothing about
#: the layer."* `delivery_health.package_functions` does the same for itself.
#:
#: Applying that existing rule to the other packages removes **11** more of the 147. It is not a new
#: policy; it is the same one, stated once instead of per package.
#: ⛔ NAMED ONLY FOR THE ONES THAT PREDATE THIS MODULE. Everything written after it is detected
#: instead, by `_is_declaration_module` below — because the first thing I did after writing this set
#: was add a new declaration module and forget to add its name, and the scan immediately reported
#: that module's own four helpers as undeclared. **A list you must remember to extend is a list that
#: will be wrong**, and the evidence arrived within the minute.
SELF_DECLARING: frozenset[str] = frozenset({
    "unit_health.py",          # reason/      — four grains of declared silence
    "uncited_lanes.py",        # reason/
    "situation_binding.py",    # reason/
    "lane_health.py",          # context/     — DORMANT_LANES
    "slice_silence.py",        # context/
    "reachability.py",         # platform/    — this file; it cannot import itself
})


def _is_declaration_module(module_path: Path) -> bool:
    """Does this module declare its own package's silences?

    ⛔ DERIVED, NOT LISTED. A declaration module is one that imports this one — that is what makes
    it a declaration module rather than ordinary code, and it is a fact about the file rather than a
    name somebody has to remember. `tests/test_the_executive_says_what_it_does_not_call.py` already
    gave the reason for the exclusion: *"its callers are this file by design. Scanning it would
    demand a declared silence for each of its own helpers — noise that says nothing about the
    layer."*

    `unreached.py` and `delivery_health.py` are detected this way once they import from here; the
    handful in `SELF_DECLARING` predate this module and declare silences of a different shape
    (lanes, eras, grains) without using any of this machinery.
    """
    if module_path.name in SELF_DECLARING:
        return True
    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):                            # pragma: no cover
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.endswith("platform.reachability"):
                return True
        elif isinstance(node, ast.Import):
            if any(a.name.endswith("platform.reachability") for a in node.names):
                return True
    return False


# ---------------------------------------------------------------------------------------------
# reading the source
# ---------------------------------------------------------------------------------------------

def engine_sources(engine_root: Path, *, include_scripts: bool | None = None) -> dict[str, str]:
    """Every source file that counts as a CALLER — `{path: text}`.

    ⛔ THE SOURCE SET IS THE WHOLE CONVENTION, AND IT LIVES IN CODE FOR THAT REASON. A reachability
    number is meaningless without it: passing `tests/` in alongside the engine makes every
    unit-tested function look reached, and that is how `deliver/`'s unreached count was first
    reported as **4** when the engine-only answer is **24**.

    `include_scripts` defaults to `SCRIPTS_ARE_CALLERS`; pass it explicitly only to measure the
    difference the policy makes.
    """
    use_scripts = SCRIPTS_ARE_CALLERS if include_scripts is None else include_scripts
    out: dict[str, str] = {}
    roots = [engine_root]
    if use_scripts:
        candidate = engine_root.parent / "scripts"
        if candidate.is_dir():
            roots.append(candidate)
    for root in roots:
        for path in root.rglob("*.py"):
            try:
                out[str(path)] = path.read_text(encoding="utf-8")
            except OSError:                                   # pragma: no cover - unreadable file
                continue
    return out


def public_functions(module_path: Path) -> tuple[str, ...]:
    """Every module-level public function in `module_path`, read from the AST.

    ⛔ THE AST, NOT THE TEXT, and module scope only — so a nested helper, a method, or a name that
    appears in a docstring cannot enter the inventory. Ten assertions on the branch that wrote this
    went green or red on a word that lived only in prose; a structural read cannot.
    """
    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):                            # pragma: no cover - unreadable file
        return ()
    return tuple(node.name for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                 and not node.name.startswith("_"))


def decorated_functions(module_path: Path) -> frozenset[str]:
    """Public functions carrying a decorator — ⛔ **a route handler has no Python caller by design.**

    Measured 2026-10-01: **25** public functions in `api/` are registered by a FastAPI decorator.
    Both resolvers correctly return zero qualified callers for them, so a naive engine-wide guard
    reports a working HTTP surface as dead and asks `api/` for 25 declarations that all say the same
    thing. `executive/` and `deliver/` have no routes, which is why neither declaration module ever
    had to care.

    ⛔ Pinned in `tests/executive/test_a_call_resolved_by_name_is_not_a_call.py`, because
    discovering this after writing 25 declarations is the expensive order.
    """
    try:
        tree = ast.parse(module_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):                            # pragma: no cover
        return frozenset()
    return frozenset(
        node.name for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.decorator_list and not node.name.startswith("_"))


def package_functions(package_dir: Path) -> dict[str, str]:
    """`{"module.function": module}` for every declarable public function in one package.

    `glob`, not `rglob` — top-level files only. Adapters behind a registry seam (`deliver/channels/`
    reached through `get_channel`) are not called by name, so a by-name walk reports them dead and
    they are not. ⛔ Excludes `SELF_DECLARING` modules and decorator-registered functions, so a
    caller gets the set that actually needs a reason.
    """
    out: dict[str, str] = {}
    for path in sorted(package_dir.glob("*.py")):
        if path.name == "__init__.py" or _is_declaration_module(path):
            continue
        skip = decorated_functions(path)
        for name in public_functions(path):
            if name in skip:
                continue
            out[f"{path.stem}.{name}"] = path.stem
    return out


# ---------------------------------------------------------------------------------------------
# the two resolvers, and why both stay
# ---------------------------------------------------------------------------------------------

def call_sites(name: str, sources: dict[str, str]) -> int:
    """How many times `name` is CALLED across `sources`, ignoring its own definition.

    Counts `ast.Call` nodes whose callee resolves to `name`, whether called bare (`f()`) or through
    an attribute (`mod.f()`). A definition, an `__all__` entry and a mention in prose are none of
    them calls — the distinction the hand-written grep that preceded this could not make, and it
    reported two functions as dead that are called on live paths.
    """
    total = 0
    for source in sources.values():
        try:
            tree = ast.parse(source)
        except SyntaxError:                                   # pragma: no cover
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name) and func.id == name:
                total += 1
            elif isinstance(func, ast.Attribute) and func.attr == name:
                total += 1
    return total


def called_names(sources: dict[str, str]) -> dict[str, int]:
    """Every name CALLED anywhere in `sources`, counted — in ONE pass over each file.

    ⛔ WHY THIS EXISTS BESIDE `call_sites`. The first version of this guard asked `call_sites` once
    per candidate, so it re-parsed ~600 modules for each of ~80 functions — roughly 48,000 parses,
    and the test ran for minutes. A correctness guard too slow to run is one people skip, which is a
    worse failure than the one it catches. Same answer, one pass.
    """
    counts: dict[str, int] = {}
    for source in sources.values():
        try:
            tree = ast.parse(source)
        except SyntaxError:                                   # pragma: no cover
            continue
        # ⛔ ALIASES FIRST, AND THIS IS NOT OPTIONAL. `deliver/actions.py` does
        # `from genios_engine.executive.execution_store import link_card as _link_execution_card`
        # and then calls the ALIAS. Counting only the bare name reported `link_card` — a function on
        # the live card-completion path — as dead, which is precisely the false verdict this guard
        # exists to prevent.
        aliases: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    if alias.asname:
                        aliases[alias.asname] = alias.name.split(".")[-1]
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (func.id if isinstance(func, ast.Name)
                    else func.attr if isinstance(func, ast.Attribute) else None)
            if name is None:
                continue
            resolved = aliases.get(name, name)
            counts[resolved] = counts.get(resolved, 0) + 1
    return counts


def _file_bindings(tree: ast.Module, own_stem: str) -> tuple[dict[str, tuple[str, str]],
                                                             dict[str, str]]:
    """What the names in one file resolve to — `(direct, modules)`.

    `direct` maps a local name to `(module_stem, original_name)`, so `from x.spine import f as g`
    makes `g()` resolve to `spine.f`. `modules` maps a local name to a module stem, so
    `from pkg import delegation as DLG` makes `DLG.propose()` resolve to `delegation.propose`.
    A file's own stem is always in `modules`, because ⛔ **no file imports itself** — requiring an
    import once reported `outbox.shadow_resolve_v2`, called inside its own file, as unreached.
    """
    direct: dict[str, tuple[str, str]] = {}
    modules: dict[str, str] = {own_stem: own_stem}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            stem = mod.split(".")[-1] if mod else ""
            for alias in node.names:
                local = alias.asname or alias.name
                if node.level and not mod:                    # from . import spine
                    modules[local] = alias.name
                elif stem:
                    # `alias.name` is either a function in `stem`, or itself a module in a package.
                    # Both readings are recorded; only the one matching a real call is used.
                    direct[local] = (stem, alias.name)
                    modules[local] = alias.name
        elif isinstance(node, ast.Import):
            for alias in node.names:
                modules[alias.asname or alias.name.split(".")[-1]] = alias.name.split(".")[-1]
    return direct, modules


def qualified_call_counts(sources: dict[str, str]) -> dict[tuple[str, str], int]:
    """Calls counted per `(module_stem, function_name)` — ONE pass, and the module is not collapsed.

    ⛔ USE THIS, NOT `called_names`, TO ASK WHETHER SOMETHING IS REACHED. `called_names` resolves
    aliases correctly and then counts by NAME ALONE, so every function sharing a name shares one
    count. The shortest names are the least visible: `read` had **11** apparent callers and none,
    `resolve` 48, `extend` 96 (`list.extend`).

    ⛔ BOTH RESOLVERS STAY, AND THE ASYMMETRY IS DELIBERATE. `called_names` is still correct for
    *"what names does this file call"*. For reachability the failure directions differ: a false
    REACHED hides a problem from us, while a false UNREACHED demands a declaration for genuinely
    wired code — and a declaration nobody can justify is how a table fills with entries that mean
    nothing.
    """
    counts: dict[tuple[str, str], int] = {}

    def bump(module: str, name: str) -> None:
        counts[(module, name)] = counts.get((module, name), 0) + 1

    for path, source in sources.items():
        try:
            tree = ast.parse(source)
        except SyntaxError:                                   # pragma: no cover
            continue
        stem = Path(path).stem
        direct, modules = _file_bindings(tree, stem)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            if isinstance(func, ast.Name):
                if func.id in direct:
                    module, original = direct[func.id]
                    bump(module, original)
                else:
                    bump(stem, func.id)                       # ⛔ no file imports itself
            elif isinstance(func, ast.Attribute):
                value = func.value
                if isinstance(value, ast.Name) and value.id in modules:
                    bump(modules[value.id], func.attr)
    return counts


def qualified_value_refs(sources: dict[str, str]) -> dict[tuple[str, str], int]:
    """Uses of a function as a VALUE rather than a call — `{(module, name): count}`.

    ⛔ THE THIRD WIRING MECHANISM, AND IT IS THE BIGGEST ONE. A function can be reached three ways,
    and only the first is an `ast.Call`:

        f()                            a call          -> `qualified_call_counts`
        @router.get("/x") def f()      a decorator     -> `decorated_functions`
        Depends(f) · {"k": f} · key=f  A REFERENCE     -> here

    ⛔ MEASURED 2026-10-01, BEFORE ANY DECLARATION WAS WRITTEN: of 123 engine-wide functions that
    looked unreached, **46 are wired by reference** — and calling them unreached would have been
    absurd for most of them:

        platform/auth.require_owner          35 references   the whole API runs on it
        platform/auth.get_auth_ctx           29
        platform/auth.require_admin          25
        api/device_routes.require_session_seat 8             Depends(...) in three routes
        context/outreach_situations.read_*_for_dispatch      a dispatch table, 12 of them
        context/support_situations.read_*                     the same, 7
        feedback/units.unit_*                                a unit registry, 12
        mcp/server.tool_*                                    a tool registry, 5

    **The dominant pattern across this engine is REGISTRY WIRING** — a function put into a dispatch
    table by name. ⛔ Had the 123 been declared without this measurement, **46 of the entries would
    have been lies**, and each one would have read as a considered decision about live code.

    ⛔ A LOAD IN A FILE THAT IMPORTS THE NAME IS A USE. The call node's own `func` is excluded, so a
    call is never double-counted. A local variable shadowing an imported name would be miscounted —
    toward *reached* — which is the comfortable direction and the reason this is used ONLY to rescue
    a function from the unreached set, never to put one into it.
    """
    out: dict[tuple[str, str], int] = {}
    for path, source in sources.items():
        try:
            tree = ast.parse(source)
        except SyntaxError:                                   # pragma: no cover
            continue
        stem = Path(path).stem
        direct, _modules = _file_bindings(tree, stem)
        callee_ids = {id(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)}
        for node in ast.walk(tree):
            if not isinstance(node, ast.Name) or not isinstance(node.ctx, ast.Load):
                continue
            if id(node) in callee_ids:
                continue                                      # that is a call, counted elsewhere
            if node.id in direct:
                module, original = direct[node.id]
            else:
                module, original = stem, node.id
            key = (module, original)
            out[key] = out.get(key, 0) + 1
    return out


def qualified_call_sites(qualified: str, sources: dict[str, str]) -> int:
    """`"module.function"` -> how many qualified calls. One-off convenience over the counts above."""
    module, _, name = qualified.partition(".")
    return qualified_call_counts(sources).get((module, name), 0)


# ---------------------------------------------------------------------------------------------
# the inventory, both directions
# ---------------------------------------------------------------------------------------------

def unreached_in(package_dir: Path, sources: dict[str, str]) -> frozenset[str]:
    """`{"module.function"}` for every declarable public function the engine reaches NO WAY at all.

    ⛔ THREE MECHANISMS, NOT ONE. A call, a decorator, or a reference — `package_functions` already
    drops the decorated, and this subtracts both of the other two. Counting only calls reported
    **46** functions as unreached that are wired by reference, including
    `platform/auth.require_owner` with 35 of them.
    """
    calls = qualified_call_counts(sources)
    refs = qualified_value_refs(sources)
    out = set()
    for qualified, module in package_functions(package_dir).items():
        name = qualified.split(".", 1)[1]
        if calls.get((module, name), 0) == 0 and refs.get((module, name), 0) == 0:
            out.add(qualified)
    return frozenset(out)


def undeclared(package_dir: Path, sources: dict[str, str],
               declared: frozenset[str]) -> tuple[str, ...]:
    """Unreached functions with no entry — a silence nobody wrote down."""
    return tuple(sorted(unreached_in(package_dir, sources) - declared))


def missing(package_dir: Path, declared: frozenset[str]) -> tuple[str, ...]:
    """⛔ Declared entries naming a function that does not exist — the second direction.

    Declared and written are two directions, and one alone is half a guard: an entry for a deleted
    function reads as a considered decision about live code.
    """
    present = set(package_functions(package_dir))
    return tuple(sorted(q for q in declared if q not in present))


def now_called(sources: dict[str, str], declared: frozenset[str]) -> tuple[str, ...]:
    """⛔ Declared entries the engine HAS started calling — the entry that has become a lie.

    One pass, not one per entry. L4 shipped `PULL_ONLY` with only the first direction and
    `summary.build_summary` sat in it after `outbox._drain_claimed` started sending it on a tick.
    """
    counts = qualified_call_counts(sources)
    return tuple(sorted(q for q in declared
                        if counts.get((q.partition(".")[0], q.partition(".")[2]), 0) > 0))


__all__ = ["SCRIPTS_ARE_CALLERS", "SELF_DECLARING", "call_sites", "called_names",
           "decorated_functions", "engine_sources", "missing", "now_called", "package_functions",
           "public_functions", "qualified_call_counts", "qualified_call_sites",
           "qualified_value_refs", "undeclared",
           "unreached_in"]
