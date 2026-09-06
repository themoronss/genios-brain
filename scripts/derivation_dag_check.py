#!/usr/bin/env python3
"""CI gate · **a derived fact may never be an input to its own computation** (doc 13, L-4).

    python scripts/derivation_dag_check.py            # exits non-zero on a cycle
    python scripts/derivation_dag_check.py --print    # and prints the whole graph it built

Doc 13's structural rule, and the reason it is a script rather than a paragraph:

> Left unguarded this does not terminate. Worse, it does not *obviously* not terminate — it looks
> like a slow sweep, then a slower one.
>
> **The trap this catches, concretely:** trending `account.open_situation_count` would create a
> cycle — situation count feeds importance, importance feeds lifecycle, lifecycle changes situation
> count. It looks like an obviously useful metric to trend, and it is a cycle. `TRENDED_METRICS`
> must contain **only** facts derived from L1 signals, never from L2's own situation state. The DAG
> test is what stops someone adding it in six months.

**The graph is DERIVED FROM THE CODE, never from a list kept next to it.** A hand-maintained
adjacency table is a second source of truth about what the code reads, it drifts on the first
refactor, and it cannot catch a cycle somebody introduces later — which is the only thing this
check is for. Every edge below comes from parsing the modules' own SQL and their own constants.

X7's adversarial review checked ONE instance of this by hand: *"both correlators read
`l1_extraction_results` + `source_events` and never their own `derived.*` — the acyclicity argument
checked against the read SQL, not asserted in prose."* This script is that argument, generalised
and re-run on every commit.

---

## CHECK A — the derived-fact DAG

**Nodes.** Exactly the things Layer 2 DERIVES, and only where the derivation is attributable:

* `derived.<family>` — every `derived.*` namespace found as a string constant in the source
  (docstrings excluded: these modules quote each other's field names constantly, and a sentence
  about `derived.trend.*` is not a read of it);
* every table written by **exactly one** module in `genios_engine/context/`.

**Why the single-writer rule, and it is the load-bearing decision in this file.** Reads are
attributed at module grain, so a module that writes several stores and reads several stores
contributes the CROSS PRODUCT of the two — which is sound only when the module has one derivation
in it. `merge.py` has none: it is an identity REWRITE that repoints eight stores at once when two
entities turn out to be one, and doc 13 files it under L-3, a different and already-bounded loop,
not under L-4. Modelling it as a derivation makes `graph_nodes`, `context_situations`,
`context_attention` and `context_correlations` a clique, and a check that reports a cycle on any
codebase whatsoever is a check nobody runs. A store with several writers has several derivations
and module grain cannot tell them apart, so it stays a LEAF here — and the runtime guard
(`runner.MAX_PASSES` and the state hash) is what covers that class instead. That division is doc
13's own: the DAG assertion "prevents most of this", the bounded fixpoint catches the rest.

**`graph_facts` is not a node either.** It is an EAV store: its rows are `(subject, field, value)`
and its identity is the FIELD. Reads of it resolve to the `derived.*` families the reading module
actually names, and unnamed raw fields (`deal.amount`, `thread.ball_in_court`) are L1 leaves,
which is what they are.

**Ownership.** A module OWNS a family if it names the family AND it writes `graph_facts` (directly
or through `analytic/publish`). Everything else it names, it reads. That rule needs no list: it
follows from the code, and it is why `importance.py` — which names all four analytic families and
writes no fact — is read as a pure consumer of them.

**Pure-computation modules fold into their importers.** `importance.py` executes the reads that
`situation_bso.py`'s write depends on, so attributing those reads to its importers is what keeps a
computation split across two files from hiding an edge.

**Self-edges are reported, not failed.** A module that reads and writes one store is doing
`insert ... on conflict do update`, which is an upsert, not a derivation from itself. They are
printed so nobody has to take that on trust.

## CHECK B — trended-metric provenance (doc 13's named trap)

Check A cannot catch `account.open_situation_count` on its own, and pretending otherwise would be
the worst outcome here. The sampler ALREADY reads `context_situations` — for its CADENCE decision,
BLG-07 rule 2, "sample daily while this node anchors an active situation" — so at module grain the
edge exists whether or not any metric's VALUE comes from situation state, and a module-grain check
would either fail today for a benign reason or pass tomorrow for a fatal one.

So check B separates the two the way the sampler's own code already does: `decide()` chooses WHEN
to sample and `measure()` chooses WHAT the number is. It taints each `OrgSnapshot` field with the
tables the query that fills it reads, walks every function reachable from the probe registry, and
fails if any metric's VALUE is measured from a snapshot field fed by an L2-derived store.

Add `account.open_situation_count` to `TRENDED_METRICS` with a probe over the situation snapshot
and check B fails on the next commit; add it with no probe and the sampler's own import-time
assertion fails first.

**What this script cannot see, stated plainly.** Dynamic SQL built at runtime, reads performed by
an ORM rather than by a string, and a read whose table name arrives as a bound parameter — none of
which exist in `genios_engine/context/` today, where every statement is a literal. And, by the
single-writer rule above, cycles that run through a store several modules write. Check A prints its
node and edge counts precisely so a reviewer can see the graph did not quietly become empty, and
the runtime convergence guard is what stands behind the part check A declines to model.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTEXT = ROOT / "genios_engine" / "context"
SAMPLER = CONTEXT / "analytic" / "sampler.py"

#: The EAV store. See the module docstring: its identity is the `field`, so it is represented by
#: the `derived.*` families rather than by its own name.
EAV_TABLE = "graph_facts"

#: SQL keywords that follow `from` / `join` / `into` and are not table names. Kept small on
#: purpose: a name that is not a real table simply becomes an isolated node and cannot create a
#: cycle, so over-collecting is safe and under-collecting is not.
_NOT_A_TABLE = {"select", "set", "values", "where", "on", "as", "lateral", "only", "distinct"}

_WRITE_RE = re.compile(r"\b(?:insert\s+into|update|delete\s+from)\s+([a-z_][a-z0-9_]*)", re.I)
_READ_RE = re.compile(r"\b(?:from|join)\s+([a-z_][a-z0-9_]*)", re.I)
_FAMILY_RE = re.compile(r"derived\.[a-z_][a-z0-9_]*")
#: A string is treated as SQL only if it opens with a statement keyword. Without this, prose in a
#: prompt template ("...update the customer...") contributes phantom tables, which is exactly how a
#: derived graph turns into noise nobody trusts.
_SQL_START_RE = re.compile(r"^\s*\(?\s*(select|insert|update|delete|with)\b", re.I)
#: A statement that only READS. A `derived.*` family named inside one is being consumed, whatever
#: else its module publishes — see `Module.owns`.
_SELECT_START_RE = re.compile(r"^\s*\(?\s*(select|with)\b", re.I)

#: Python container methods that write INTO the receiver. Check B's taint pass follows these and
#: nothing else — see the comment at the rule for what happens when it follows everything.
_CONTAINER_MUTATORS = frozenset({"append", "extend", "add", "update", "setdefault", "insert"})


# =================================================================================================
# SOURCE EXTRACTION — strings that are SQL, families that are namespaces, imports that are edges
# =================================================================================================

def _docstrings(tree: ast.AST) -> set[str]:
    """Every docstring in the module. Excluded from the scan: these files quote each other's
    field names and SQL constantly, and a sentence about `derived.trend.*` is not a read of it."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            doc = ast.get_docstring(node, clean=False)
            if doc:
                found.add(doc)
    return found


def _simple_string_bindings(tree: ast.AST) -> dict[str, str]:
    """`NAME -> "literal"` for module-level string constants.

    Needed to read f-string SQL. `cohort.py` writes `f"insert into {COHORT_MEMBERSHIP_TABLE} ..."`
    and `peer_baseline.py` writes `f"insert into {BASELINE_TABLE} ..."`, so an extractor that only
    saw literal constants would find the statement and not the table it writes — and would then
    report those two modules as deriving nothing at all, which is the silent-empty-graph failure
    this whole script has to avoid.
    """
    out: dict[str, str] = {}
    for node in getattr(tree, "body", []):
        if isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        elif isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        else:
            continue
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            for target in targets:
                if isinstance(target, ast.Name):
                    out[target.id] = value.value
    return out


def _joined(node: ast.JoinedStr, bindings: dict[str, str]) -> str:
    """An f-string rendered with its module-level constants substituted; anything else becomes a
    placeholder that no table pattern can match."""
    parts: list[str] = []
    for value in node.values:
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            parts.append(value.value)
        elif isinstance(value, ast.FormattedValue) and isinstance(value.value, ast.Name):
            parts.append(bindings.get(value.value.id, " ? "))
        else:
            parts.append(" ? ")
    return "".join(parts)


def _constants(tree: ast.AST, shared: dict[str, str] | None = None) -> list[str]:
    """Every string this module builds that is not a docstring — f-strings resolved.

    `shared` carries the string constants every context module binds, so an f-string whose table
    name was IMPORTED resolves too: `trend.py` writes `f"... from {HISTORY_TABLE} ..."` and binds
    `HISTORY_TABLE` nowhere — it imports it from `analytic/history.py`. Without the shared map that
    read of `metric_history` is invisible, and the one edge check B's whole closure is seeded from
    does not exist. Local bindings win; the map is only a fallback, and a name two modules bind
    differently would have to be a table name in both to matter.
    """
    skip = _docstrings(tree)
    bindings = dict(shared or {})
    bindings.update(_simple_string_bindings(tree))
    out = [n.value for n in ast.walk(tree)
           if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value not in skip]
    out += [_joined(n, bindings) for n in ast.walk(tree) if isinstance(n, ast.JoinedStr)]
    return out


def _tables(sql: str, pattern: re.Pattern[str]) -> set[str]:
    return {m.lower() for m in pattern.findall(sql) if m.lower() not in _NOT_A_TABLE}


def _sql_strings(constants: list[str]) -> list[str]:
    return [s for s in constants if _SQL_START_RE.match(s)]


class Module:
    """One `genios_engine/context/` module's read/write summary, derived from its own source."""

    def __init__(self, path: Path, shared: dict[str, str] | None = None) -> None:
        self.path = path
        # Relative to the repo when it is in the repo, and the bare path when it is not — so a
        # test can build a summary from a fixture module in a temp directory and prove the cycle
        # search on a graph it wrote itself, rather than by editing a real file in the tree.
        inside = path.is_relative_to(ROOT)
        rel = path.relative_to(ROOT) if inside else path
        self.name = rel.as_posix()
        self.dotted = rel.with_suffix("").as_posix().replace("/", ".")
        tree = ast.parse(path.read_text())
        constants = _constants(tree, shared)
        sql = _sql_strings(constants)
        self.written_tables = {t for s in sql for t in _tables(s, _WRITE_RE)}
        self.read_tables = {t for s in sql for t in _tables(s, _READ_RE)}
        self.families = {f for s in constants for f in _FAMILY_RE.findall(s)}
        #: Families named inside a SELECT. A producer that also reads somebody else's family names
        #: it in a query, and without this split ownership is all-or-nothing per module: the day
        #: the anomaly detector starts reading `derived.trend.*`, a module-level rule would call
        #: it the trend's second OWNER and the edge — the cycle — would vanish instead of failing.
        self.read_families = {f for s in constants if _SELECT_START_RE.match(s)
                              for f in _FAMILY_RE.findall(s)}
        self.imports = self._imports(tree)
        # Writing the EAV store, directly or through the shared publisher, is what makes a module a
        # PRODUCER of the families it names rather than a consumer of them.
        #
        # The publisher is detected through the module's IMPORTS, never through a substring of its
        # text: `importance.py` names `publish_derived_fact` in a comment explaining why it does
        # NOT publish, and a text scan read that as ownership — which made the one pure consumer of
        # all four analytic families their fifth producer, and silently deleted every cross-module
        # family edge from the graph.
        self.writes_facts = EAV_TABLE in self.written_tables or self._imports_publisher(tree)

    @staticmethod
    def _imports_publisher(tree: ast.AST) -> bool:
        """Does this module import the shared derived-fact writer? An import is a fact about the
        code; a substring is a fact about the prose around it."""
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                names = {a.name for a in node.names}
                if names & {"publish_derived_fact", "close_derived_facts"}:
                    return True
        return False

    @staticmethod
    def _imports(tree: ast.AST) -> set[str]:
        """Intra-package imports, as dotted module names. `from x import y` inside a function body
        counts: this tree imports lazily almost everywhere to keep the drain's import graph flat."""
        found: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("genios_engine."):
                    found.add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("genios_engine."):
                        found.add(alias.name)
        return found

    @property
    def owns(self) -> set[str]:
        """The `derived.*` families this module PRODUCES — the ones it names anywhere but in a
        query it runs. A family it selects on is one it reads, even here."""
        return (set(self.families) - self.read_families) if self.writes_facts else set()

    @property
    def consumes(self) -> set[str]:
        """The `derived.*` families this module READS — the ones it names and does not own."""
        return set(self.families) - self.owns

    @property
    def products(self) -> set[str]:
        """Everything this module derives: its families, plus every table it writes (the EAV store
        excluded — it is represented by the families)."""
        return self.owns | (self.written_tables - {EAV_TABLE})

    @property
    def is_pure(self) -> bool:
        """A module that writes nothing. Its reads belong to whoever imports it — see the module
        docstring; this is what makes `importance.py`'s reads visible to `situation_bso.py`."""
        return not self.products


def load_modules() -> dict[str, Module]:
    """Two passes: collect every module's string constants, then parse with the shared map in
    hand. One pass cannot work — a module's f-string may name a constant defined in a file the
    walk has not reached yet, and the order of `rglob` is not the order of the import graph."""
    paths = [p for p in sorted(CONTEXT.rglob("*.py")) if p.name != "__init__.py"]
    shared: dict[str, str] = {}
    for path in paths:
        for name, value in _simple_string_bindings(ast.parse(path.read_text())).items():
            shared.setdefault(name, value)
    return {m.dotted: m for m in (Module(p, shared) for p in paths)}


# =================================================================================================
# CHECK A — the graph, and the cycle search
# =================================================================================================

def _folded_reads(module: Module, modules: dict[str, Module]) -> tuple[set[str], set[str]]:
    """`(tables, families)` this module reads, plus the reads of the pure modules it imports.

    ONE HOP, deliberately, and not transitively. One hop is what a computation split across two
    files needs — `situation_bso.py` writes the situation and `importance.py` does the reading its
    write depends on, and without the hop that edge is invisible. Transitive folding is a different
    thing: it walks an import graph in which `runner.py` reaches every module in the layer, and it
    would attribute every read in Layer 2 to the drain's own bookkeeping tables. An
    over-approximation that large stops being a derivation graph and starts being a reachability
    graph, and its first false cycle is the last time anyone believes this check.
    """
    tables = set(module.read_tables) - {EAV_TABLE}
    families = set(module.consumes)
    for dotted in module.imports:
        imported = modules.get(dotted)
        if imported is not None and imported.is_pure:
            tables |= set(imported.read_tables) - {EAV_TABLE}
            families |= set(imported.consumes)
    return tables, families


def single_writer_tables(modules: dict[str, Module]) -> set[str]:
    """Tables written by exactly ONE module in the tree — the only ones module-grain attribution
    can honestly claim a derivation for. See the module docstring's single-writer rule.

    `graph_facts` is excluded whatever its writer count: it is the EAV store and is represented by
    the `derived.*` families instead.
    """
    writers: dict[str, set[str]] = {}
    for module in modules.values():
        for table in module.written_tables:
            writers.setdefault(table, set()).add(module.dotted)
    return {table for table, who in writers.items() if len(who) == 1 and table != EAV_TABLE}


def build_graph(modules: dict[str, Module]) -> tuple[dict[str, set[str]], list[tuple[str, str]],
                                                     set[str]]:
    """`product -> {derived things its computation reads}`, the self-edges, and the leaves.

    A node exists only for something a module DERIVES and whose derivation is attributable. Reads
    that land on anything else — `source_events`, `graph_nodes`, an L1 store, a multi-writer store
    — are LEAVES: recorded and returned for the operator's benefit, never the head of an edge. That
    is what "acyclic" means here, and a leaf cannot close a cycle by construction.
    """
    attributable = single_writer_tables(modules)
    nodes: set[str] = set(attributable)
    for module in modules.values():
        nodes |= module.owns
    edges: dict[str, set[str]] = {}
    self_edges: list[tuple[str, str]] = []
    leaves: set[str] = set()
    for module in modules.values():
        products = module.owns | (module.written_tables & attributable)
        if not products:
            continue
        tables, families = _folded_reads(module, modules)
        targets = tables | families
        leaves |= targets - nodes
        for product in products:
            reads = edges.setdefault(product, set())
            for target in targets & nodes:
                # A module's OWN products never link to each other. One module is one pass over one
                # read set: whether the row that becomes output A is textually selected from the
                # table output B lives in is an ordering question inside a single file, and it is
                # visible to anyone reading that file. `graph_store.py` writes seven stores and
                # reads all seven; `patterns/store.py` writes three and reads three. Linking them
                # pairwise turns every such module into a clique and reports a cycle on any
                # codebase. The cycles this check exists for are the ones NO single file shows —
                # the ones that run between modules — and those are unaffected by this rule.
                if target in products:
                    if target == product:
                        self_edges.append((module.name, product))
                    continue
                reads.add(target)
    return edges, sorted(set(self_edges)), leaves


def find_cycle(edges: dict[str, set[str]]) -> list[str] | None:
    """The first cycle reachable in the derivation graph, as the path that closes it.

    Iterative DFS with an explicit stack: the graph is small, but a recursive walk that blew the
    interpreter's stack would report a cycle check as an interpreter error, and a CI gate must fail
    for the reason it exists.
    """
    WHITE, GREY, BLACK = 0, 1, 2
    colour: dict[str, int] = {}
    for start in sorted(edges):
        if colour.get(start, WHITE) != WHITE:
            continue
        stack: list[tuple[str, list[str]]] = [(start, [start])]
        colour[start] = GREY
        path_stack: list[list[str]] = []
        while stack:
            node, path = stack[-1]
            pending = [t for t in sorted(edges.get(node, ())) if colour.get(t, WHITE) != BLACK]
            advanced = False
            for target in pending:
                if colour.get(target, WHITE) == GREY:
                    return path[path.index(target):] + [target] if target in path else path + [target]
                colour[target] = GREY
                stack.append((target, path + [target]))
                advanced = True
                break
            if not advanced:
                colour[node] = BLACK
                stack.pop()
        path_stack.clear()
    return None


# =================================================================================================
# CHECK B — trended-metric provenance
# =================================================================================================

def _sql_constant_tables(tree: ast.AST) -> dict[str, set[str]]:
    """`_NAME -> {tables}` for every module-level SQL constant, `text("...")` wrapper included."""
    out: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.AnnAssign) and node.value is not None:
            target, value = node.target, node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        else:
            continue
        if not isinstance(target, ast.Name):
            continue
        literals = [c.value for c in ast.walk(value)
                    if isinstance(c, ast.Constant) and isinstance(c.value, str)]
        sql = [s for s in literals if _SQL_START_RE.match(s)]
        tables = {t for s in sql for t in _tables(s, _READ_RE)}
        # A `derived.*` family named inside the statement travels with it. `graph_facts` is an EAV
        # store, so "which table" is not the question a read of it answers — "which field" is, and
        # a query naming `derived.trend.%` is reading the trend, whatever table it lives in.
        tables |= {f for s in sql for f in _FAMILY_RE.findall(s)}
        if tables:
            out[target.id] = tables
    return out


def _names_in(node: ast.AST) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}


def snapshot_field_sources(tree: ast.AST) -> dict[str, set[str]]:
    """Which TABLES feed each `OrgSnapshot` / `NodeSnapshot` field.

    A taint pass over `read_org_snapshot`: a local assigned from `conn.execute(_X_SQL)` carries
    `_X_SQL`'s tables, a container mutated with a tainted value inherits it, and a dataclass keyword
    argument inherits the taint of the names in its value expression.

    **Loop variables are SCOPED to their loop, and that is what makes the answer usable rather than
    uniform.** `read_org_snapshot` reuses the name `row` in five consecutive `for` statements — over
    the node rows, the activity rows, the timeline rows, the fact rows and the loop rows — so a
    flat name environment merges all five and every container built from `row` comes back carrying
    every table the function ever read. All twelve snapshot fields then report all eight sources,
    the check can no longer distinguish anything from anything, and it passes for the same reason a
    check with no assertions passes. Each `for` body therefore gets a child environment whose loop
    target is local; everything the body writes to an OUTER name still propagates out, because that
    is exactly how these dictionaries are filled.

    It still over-approximates — a container fed inside two different loops carries both, which is
    true — and over-approximation is the safe direction here: a false positive is an argument in a
    review, a false negative is a customer told their healthiest account is churning.
    """
    constants = _sql_constant_tables(tree)
    function = next((n for n in ast.walk(tree)
                     if isinstance(n, ast.FunctionDef) and n.name == "read_org_snapshot"), None)
    if function is None:
        raise SystemExit("sampler.read_org_snapshot is gone — check B has nothing to walk")

    fields: dict[str, set[str]] = {}

    def taint_of(node: ast.AST, env: dict[str, set[str]]) -> set[str]:
        """Everything the names in this expression carry — MINUS the expression's own comprehension
        targets.

        The `OrgSnapshot(...)` construction is one statement holding four dict comprehensions that
        all bind `k, v`. If those targets resolved against the environment, every one of the four
        keyword arguments would inherit the union of all four iterables and the snapshot would
        report every field as fed by every source. A comprehension target is bound and consumed
        inside its own expression; its iterable's names are already counted here.
        """
        bound = {t.id for comprehension in ast.walk(node)
                 if isinstance(comprehension, ast.comprehension)
                 for t in ast.walk(comprehension.target) if isinstance(t, ast.Name)}
        marks: set[str] = set()
        for name in _names_in(node) - bound:
            marks |= constants.get(name, set())
            marks |= env.get(name, set())
        return marks

    def bind(target: ast.AST, marks: set[str], env: dict[str, set[str]]) -> None:
        """Assigning a name DECLARES it, even with nothing to carry. `timeline: dict = {}` taints
        nothing, and the loop below fills it — so the empty declaration is what tells the loop
        scoping that `timeline` is an outer container rather than one of its own temporaries."""
        for name in (t.id for t in ast.walk(target) if isinstance(t, ast.Name)):
            env.setdefault(name, set()).update(marks)

    def record_calls(node: ast.AST, env: dict[str, set[str]]) -> None:
        """Container mutation, and the `OrgSnapshot(...)` / `NodeSnapshot(...)` constructions."""
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            if isinstance(call.func, ast.Name) and call.func.id in ("OrgSnapshot", "NodeSnapshot"):
                for keyword in call.keywords:
                    if keyword.arg:
                        fields.setdefault(keyword.arg, set()).update(taint_of(keyword.value, env))
                continue
            if not (isinstance(call.func, ast.Attribute)
                    and call.func.attr in _CONTAINER_MUTATORS):
                continue
            # RESTRICTED TO CONTAINER MUTATORS. Applied to every method call this also taints
            # `conn`, the receiver of `conn.execute(_NODES_SQL, ...)`, and from there every later
            # `conn.execute` inherits every table the function ever read.
            receiver: ast.AST = call.func.value
            while isinstance(receiver, (ast.Call, ast.Subscript, ast.Attribute)):
                receiver = receiver.func if isinstance(receiver, ast.Call) else receiver.value
            if isinstance(receiver, ast.Name):
                marks: set[str] = set()
                for argument in [*call.args, *(k.value for k in call.keywords)]:
                    marks |= taint_of(argument, env)
                bind(receiver, marks, env)

    def visit(body, env: dict[str, set[str]]) -> None:
        for statement in body:
            if isinstance(statement, ast.For):
                inner = {name: set(marks) for name, marks in env.items()}
                # Only names that already EXISTED are carried back out. A name first assigned
                # inside a loop is one of that loop's temporaries — `read_org_snapshot` reuses
                # `row`, `at`, `direction` and `value` in five consecutive loops — and letting a
                # temporary escape re-contaminates the next loop through a name that has nothing
                # to do with it: `timeline` would end up carrying `open_loops` because the loop
                # after it happened to reuse `at`. Containers are declared before their loop, so
                # everything these loops actually fill still propagates.
                outer = set(env)
                bind(statement.target, taint_of(statement.iter, inner), inner)
                visit(statement.body, inner)
                visit(statement.orelse, inner)
                for name, marks in inner.items():
                    if name in outer:
                        env.setdefault(name, set()).update(marks)
                continue
            if isinstance(statement, (ast.If, ast.While, ast.With, ast.Try)):
                for attribute in ("body", "orelse", "finalbody"):
                    visit(getattr(statement, attribute, []) or [], env)
                for handler in getattr(statement, "handlers", []) or []:
                    visit(handler.body, env)
                continue
            if isinstance(statement, ast.Assign):
                marks = taint_of(statement.value, env)
                for target in statement.targets:
                    bind(target, marks, env)
            elif isinstance(statement, (ast.AnnAssign, ast.AugAssign)) and statement.value is not None:
                bind(statement.target, taint_of(statement.value, env), env)
            record_calls(statement, env)

    # ONE pass, in statement order. A second pass would re-run every loop with the first pass's
    # temporaries already in the environment, which is the same contamination the loop scoping
    # above exists to prevent. Statement order is enough here because the function is written in
    # it: every container is declared, then filled, then read into the snapshot at the end.
    visit(function.body, {})
    return fields


def probe_functions(tree: ast.AST) -> set[str]:
    """Every function reachable from the metric probe registry — the VALUE path.

    Seeded from `_PROBES`' values (a bare name, or a factory call like `_engagement_probe("in")`)
    and closed over intra-module calls. `decide`, `_rule_*` and `_cadence_due` are the CADENCE path
    and are deliberately not reachable from here: the sampler's read of `context_situations` lives
    there, and confusing "when do we sample" with "what is the number" is what makes a module-grain
    check useless on this file.
    """
    by_name = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    seed: set[str] = set()
    for node in ast.walk(tree):
        # `ast.AnnAssign` as well as `ast.Assign`: `_PROBES` carries a type annotation, and a walk
        # that only knew about bare assignment would find no registry and pass vacuously — which
        # is the failure mode a provenance check may least afford.
        if isinstance(node, ast.AnnAssign):
            target, value = node.target, node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        else:
            continue
        if value is None or not (isinstance(target, ast.Name) and target.id == "_PROBES"):
            continue
        for name in _names_in(value):
            if name in by_name:
                seed.add(name)
    if not seed:
        raise SystemExit("sampler._PROBES is gone — check B has no metric probes to walk")

    reached, queue = set(seed), list(seed)
    while queue:
        function = by_name.get(queue.pop())
        if function is None:
            continue
        for call in ast.walk(function):
            if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                name = call.func.id
                if name in by_name and name not in reached:
                    reached.add(name)
                    queue.append(name)
    return reached


def probe_attributes(tree: ast.AST, functions: set[str]) -> set[str]:
    """Every attribute name any probe reads. Attribute-level rather than parameter-tracked: the
    snapshot is the only object these functions receive, and an over-broad set can only ever make
    this check STRICTER."""
    by_name = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    return {node.attr for name in functions for node in ast.walk(by_name[name])
            if isinstance(node, ast.Attribute) and name in by_name}


#: A module writing this many distinct stores is an IDENTITY REWRITE, not a derivation, and is
#: excluded from the downstream closure below. `merge.py` repoints nine stores when two entities
#: turn out to be one and `graph_store.py` writes ten as the capture lane's writer; every actual
#: derivation in this layer writes one, two or three. Without the exclusion the closure walks
#: `context_situations -> merge.py -> graph_nodes` and then every metric in the sampler is
#: "downstream of history", because every metric reads the node table. Doc 13 files merge under
#: L-3, a separate and already-bounded loop, so this is the plan's own taxonomy and not a
#: convenience — and the threshold is stated here rather than spelled at the comparison so a
#: reviewer can argue with it.
IDENTITY_REWRITE_WRITE_COUNT = 5


def downstream_of_history(modules: dict[str, Module]) -> set[str]:
    """Every store and family whose value DEPENDS on `metric_history`, to a fixpoint.

    This is the set a trended metric may not be measured from, because a metric measured from it
    would make `metric_history` an input to its own computation — doc 13's rule, and its named
    trap. Seeded from the history table itself and grown one module at a time: a module that reads
    anything in the set contributes everything it derives.

    Check A's edge set is deliberately NOT reused here. Check A drops multi-writer stores because
    module-grain attribution cannot say WHICH of their writers derived a row — but for THIS
    question over-approximation is the safe direction, since the cost of a false positive is an
    argument in a code review and the cost of a false negative is a customer told their healthiest
    account is churning.
    """
    reachable = {"metric_history"}
    changed = True
    while changed:
        changed = False
        for module in modules.values():
            if len(module.products) >= IDENTITY_REWRITE_WRITE_COUNT:
                continue
            tables, families = _folded_reads(module, modules)
            if not ((tables | families) & reachable):
                continue
            # `graph_facts` never enters the set as a TABLE: it is the EAV store and the sampler
            # reads it under a filter naming raw L1 fields (`deal.amount`, `thread.ball_in_court`),
            # which are leaves. The `derived.*` families that live in it ARE in the set, and a
            # probe that read one is caught by name — see `_sql_constant_tables`.
            grown = module.owns | (module.written_tables - {EAV_TABLE})
            if grown - reachable:
                reachable |= grown
                changed = True
    return reachable - {"metric_history"} | {"metric_history"}


# =================================================================================================
# THE GATE
# =================================================================================================

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--print", dest="show", action="store_true",
                        help="print the derivation graph as well as checking it")
    args = parser.parse_args()

    modules = load_modules()
    edges, self_edges, leaves = build_graph(modules)

    if args.show:
        for product in sorted(edges):
            for target in sorted(edges[product]):
                print(f"  {product} -> {target}")
        for module_name, product in self_edges:
            print(f"  [self] {module_name} reads and writes {product} (upsert, not a derivation)")
        for leaf in sorted(leaves):
            print(f"  [leaf] {leaf} — read, never derived here")

    print(f"check A · derivation graph: {len(edges)} derived products, "
          f"{sum(len(v) for v in edges.values())} edges, {len(self_edges)} self-referencing writes, "
          f"{len(leaves)} leaf stores")
    if not edges:
        print("FAIL: the derivation graph is EMPTY — the extractor found nothing to check, which "
              "means the source moved, not that the code is acyclic")
        return 2

    cycle = find_cycle(edges)
    if cycle is not None:
        print("FAIL: a derived fact is an input to its own computation.")
        print("      " + " -> ".join(cycle))
        print("      Doc 13: a fact derived from a fact derived from itself converges to whatever "
              "it started at and looks stable.")
        return 1
    print("check A · PASS — no derived fact reaches itself")

    tree = ast.parse(SAMPLER.read_text())
    fields = snapshot_field_sources(tree)
    functions = probe_functions(tree)
    attributes = probe_attributes(tree, functions)
    downstream = downstream_of_history(modules)

    offences = sorted(
        (attribute, sorted(fields[attribute] & downstream))
        for attribute in attributes & set(fields)
        if fields[attribute] & downstream)
    print(f"check B · trended-metric provenance: {len(functions)} probe functions read "
          f"{len(attributes & set(fields))} snapshot fields; {len(downstream)} stores are "
          "downstream of metric_history")
    if offences:
        print("FAIL: a trended metric is measured from Layer 2's OWN derived state.")
        for attribute, tables in offences:
            print(f"      snapshot.{attribute} is fed by {', '.join(tables)}")
        print("      Doc 13: TRENDED_METRICS must contain only facts derived from L1 signals, "
              "never from L2's own situation state — that is a cycle, and it looks useful.")
        return 1
    print("check B · PASS — every trended metric is measured from L1-derived state only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
