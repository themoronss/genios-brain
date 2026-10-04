r"""Which tables each package WRITES, who reads them, and which nobody reads — measured.

⛔ WHY THIS EXISTS. `S7` turned "receipts per package" into data and the number pointed at
`context/`: **50,877 lines, 124 files, 2 receipts.** ⛔ The first thing the audit found is that the
headline is wrong — `context/` is heavily unit-tested (306 test files import it) and **both** its
receipts are CORRECTNESS receipts. What it does not have is any check that the **36 tables it
writes** are behaving in production. `receipt_coverage.py` answers *"which package does each
receipt guard"*; this answers *"which table does nothing guard, and does anything even read it"*.

⛔⛔ FOUR RESOLVER TRAPS WERE HIT BUILDING THIS, AND EVERY ONE WOULD HAVE PRODUCED A CONFIDENT
WRONG ANSWER. They are why the shape of this module is what it is:

  1. ⛔ `[a-z_]+` CANNOT MATCH A DIGIT. `l2_convergence` resolved as table `l`, and `l2_model_runs`
     did not appear at all — **one of the three real findings was invisible.** Second time that
     exact pattern has lied in this programme, so `_TABLE` is asserted against a digit below.
  2. ⛔ THE ENGINE IS NOT THE WHOLE READER SET. `situation_admission_decisions` looked written-and-
     unread; it is read by **five scripts** (`activate_tenant`, `l2_refusal_report`,
     `pipeline_funnel_report`, `speedrun008_layer2_measurements`). **An operator-read table is a
     read table**, so `_ROOTS` includes `scripts/`.
  3. ⛔ A BARE-NAME GREP HANDS OVER A SENTENCE WITHOUT ITS SUBJECT. `context_node_lifecycle` looked
     unread; `context/runner.py` reads it. Every mention is classified by VERB, and a mention in a
     docstring is not a read.
  4. ⛔⛔ A WRITE CAN HAPPEN THROUGH A NAME CONSTANT. `context/merge.py` holds
     `_NODE_REFERENCES = (("graph_facts", "subject_node_id"), …)` and repoints every one of them in
     a generic loop, so the table name never appears in any SQL literal. That is the
     `authority_rules` / `AUTHORITY_TABLE` trap in the WRITE direction, and
     `NAME_CONSTANT_TABLE_SITES` is how it is accounted for — **declared, because a heuristic that
     treats any tuple of table names as a write would read the tenant DELETE LIST as 36 writers.**
"""
from __future__ import annotations

import ast
import re
from functools import lru_cache
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_ENGINE = _ROOT / "genios_engine"
#: ⛔ `scripts/` is in here because of trap 2. An operator report is a reader.
_ROOTS: tuple[Path, ...] = (_ENGINE, _ROOT / "scripts")

#: A table identifier. ⛔ The digit class is trap 1 and is asserted by the guard.
_TABLE = r"([a-z_][a-z_0-9]*)"
_VERBS: dict[str, str] = {
    "insert": rf"insert into {_TABLE}",
    "update": rf"update {_TABLE} set",
    "delete": rf"delete from {_TABLE}",
    "read": rf"(?:from|join) {_TABLE}",
}
WRITE_VERBS: frozenset[str] = frozenset({"insert", "update"})

#: Where the tenant erasure loop gets its table names. ⛔ Read off the AST rather than imported:
#: `api/` importing `platform/` is the normal direction, and reversing it for a list of strings
#: would be a cycle for no gain.
_DELETE_LIST = ("api/account_routes.py", "_ORG_SCOPED_TABLES")

#: ⛔⛔ Writes that happen through a NAME CONSTANT, so no SQL literal names the table —
#: `{module: (constant, verb, why)}`. Declared, never inferred (see trap 4 above).
NAME_CONSTANT_TABLE_SITES: dict[str, tuple[str, str, str]] = {
    "context/merge.py": (
        "_NODE_REFERENCES", "update",
        "⛔ Entity merge repoints every reference to the absorbed node in a GENERIC LOOP over "
        "`(table, column)` pairs, so `graph_facts`, `graph_observations`, `graph_aliases`, "
        "`source_identity_map` and `context_situations` are each written by a statement that "
        "never spells their name. The module's own comment states the stake: a row left pointing "
        "at the absorbed node is *'invisible in the UI, still returned by any query that joins "
        "on node_id'*"),
    "feedback/store.py": (
        "QUARANTINABLE_SEAMS", "read",
        "⛔⛔ THE CASE THAT PROVES WHY THIS TABLE IS DECLARED AND NOT INFERRED. `store.py` passes "
        "`_OPTIONAL_INBOX_TABLE` as an ARGUMENT to `_read_optional_seam`, which builds "
        "`f\"select * from {table} …\"` from the PARAMETER — so the name reaches the SQL through a "
        "function boundary that no amount of module-level constant substitution can follow. "
        "⛔ Without this entry the measurement called `learning_event_inbox` write-only, and `S5` "
        "had already PROVEN it is loaded into every weekly learning batch. *A name-constant is a "
        "read* — and a name-constant passed as an argument is a read nothing static can see"),
}

#: ⛔⛔ TABLES A PACKAGE WRITES THAT NOTHING READS — `{table: (writer, why, mover)}`.
#:
#: ⛔ Membership here means: no `select`/`join` anywhere in `genios_engine/` or `scripts/`, no
#: receipt, and no name-constant read. The ONLY other reference is the tenant delete list — which
#: is the third time this programme has found that shape, after `macv_ledger` (the North Star
#: number, `S2`) and `counterfactual_ledger` (which turned out to be a VIEW and was NOT one).
#:
#: ⛔ The delete list's own comment states what is at stake in it: *"the loop below runs with no
#: try/except by design, so a name missing here leaks silently."* A write-only table is therefore
#: correctly deleted and otherwise inert: it costs storage, it is in the erasure path, and no
#: decision has ever been made from it.
UNREAD_WRITES: dict[str, tuple[str, str, str]] = {
    # ── context/ ────────────────────────────────────────────────────────────────────────
    "contract_spend_attributions": (
        "context/correlation_resource.py",
        "⛔ Written when resource correlation attributes spend to a contract. Every other mention "
        "in the repo is prose. ⛔ So the attribution is COMPUTED, STORED and never consulted — no "
        "card, no situation and no report has ever been shaped by it",
        "MOVES WHEN a spend-attribution surface reads it. ⛔ Not mine: deleting a written ledger "
        "destroys history, and building the reader is a product decision about whether contract "
        "spend belongs in the product"),
    "source_identity_map": (
        "context/graph_store.py + context/merge.py",
        "⛔ TWO writers, and the second is only visible because of `NAME_CONSTANT_TABLE_SITES`: "
        "`merge.py` repoints it in the generic node-reference loop. Read by nothing. ⛔ An "
        "identity map that nothing resolves against is maintained correctly for no consumer",
        "MOVES WHEN identity resolution reads back its own map — the natural caller is "
        "`context/identity.py`, which resolves alias candidates and does not consult it"),
    "situation_interpretations": (
        "context/interpretation_store.py",
        "⛔ `record_interpretation` inserts; the module exports exactly `TABLE` and that function, "
        "and nothing selects from it. `contracts/situation.py` and `platform/l4_activation.py` "
        "name it in prose only. ⛔ The L4 activation note is the tell: an interpretation written "
        "for a layer that was being brought up, and the reader never arrived",
        "MOVES WHEN L4 reads the interpretation it was given, or the write is retired with the "
        "shadow path"),

    # ── other packages — the same measurement, engine-wide ──────────────────────────────
    "learning_metrics": (
        "feedback/publisher.py",
        "⛔⛔ THIS IS `F11`'s LAST UNREAD LEDGER, REDISCOVERED FROM THE OTHER SIDE. L6 counted "
        "four ledgers nothing read and `S5`/`S6` closed three of them; this audit found the "
        "fourth without looking for it, which is the cross-check that makes both measurements "
        "worth trusting. Every `METRICS` proposal the eleven analysis units produce lands here "
        "and no reader exists",
        "MOVES WHEN a precision-by-layer surface exists. ⛔ `feedback/calibrate` consumes the RAW "
        "judgments directly, so the metric rows are for a reader rather than for the loop — the "
        "same conclusion `feedback_health` reached about `attribution.ranked_precision`"),
    "human_events": (
        "capture/events_store.py + deliver/actions.py",
        "⛔ Two packages write it and nothing reads it. A human action ledger spanning capture and "
        "delivery is exactly the join an outcome question needs, and `execution_outcomes` answers "
        "that question from a different table",
        "MOVES WHEN outcome reconciliation (Atlas L7 #3) needs a human-action timeline, or the "
        "second writer is removed"),
    "card_feedback_revisions": (
        "api/intelligence_routes.py",
        "⛔ A revision history for card feedback, written by the API and read by nothing — while "
        "`card_feedback_verdicts`, the table beside it, is read by every weekly learning batch. "
        "⛔ So the verdict is consumed and its REVISIONS are not: a human who corrects their own "
        "correction is recorded and never heard",
        "MOVES WHEN the learning batch reads revisions as well as verdicts — which is Atlas L7 "
        "#3's *'correction retracts derived proposal'* clause, and is Rohit's"),
    "agent_metering": (
        "deliver/agent_api.py",
        "⛔ Per-call metering for the Agent API. Read by nothing, and ⛔ **not named in the "
        "`/reset` erasure loop either** — so it survives a tenant reset. That may be deliberate "
        "for billing-shaped data; it is not written down anywhere, which is the finding",
        "MOVES WHEN metering is billed from or reported on. ⛔ Whether it should survive `/reset` "
        "is a product decision and belongs in `RETAINED_AFTER_ERASURE`'s reasoning if the answer "
        "is yes"),
    "delivery_rate_windows": (
        "deliver/rate_limiter.py",
        "⛔ The rate limiter's own window state: written, never read back. ⛔ A limiter that does "
        "not read its windows is not limiting from them — `S8`'s `test_the_hourly_ceiling_is_"
        "exact_at_one_worker` proves the ceiling holds, so the enforcement is elsewhere and this "
        "table is a record of it",
        "MOVES WHEN the limiter reads its own history (a multi-worker ceiling needs exactly "
        "that), or the write is retired"),
    "domain_requests": (
        "api/expertise_routes.py",
        "⛔ A tenant asking for a domain that does not exist yet. Written by the request handler "
        "and read by nobody — ⛔ so the request is recorded and no human or job is ever shown it. "
        "*A refusal nobody can see is a silent stop*, and this is its product-side twin: a "
        "REQUEST nobody can see",
        "MOVES WHEN domain requests reach an operator surface. ⛔ The write is correct; the queue "
        "has no reader"),
}

#: ⛔⛔ RETRACTED FROM THE TABLE ABOVE, AND WHY IT MATTERS THAT THEY ARE NAMED HERE.
#:
#: The audit's first pass called six tables write-only. ⛔ **Every broadening of the resolver
#: killed a finding**, and these two died last — after the extractor learned to read SQL held in
#: a module-level constant rather than only SQL passed to `text(...)`:
#:
#:   * `edge_coverage_declarations` — read by its OWN writer, `context/patterns/store.py`;
#:   * `l2_model_runs` — read by `context/lifecycle/resolution.py`.
#:
#: ⛔ They are recorded rather than deleted because the next reader of this module will be
#: tempted to re-derive the list with a simpler scan and will get them back. *An invalid finding
#: is not a finding* — and the measurement that produced them is in `resolution()`.
RETRACTED_UNREAD_WRITES: dict[str, str] = {
    "edge_coverage_declarations":
        "⛔ RETRACTED — read by its own writer `context/patterns/store.py`. A self-read is a read: "
        "the pattern store consults the coverage it declared",
    "l2_model_runs":
        "⛔ RETRACTED — read by `context/lifecycle/resolution.py`. The first classification pass "
        "sampled line 103 of that module, which is prose; the READ is in a SQL constant further "
        "down. *A bare-name grep hands over a sentence without its subject*",
}


#: A string literal that IS a SQL statement, rather than one that mentions a table.
_SQL_SHAPE = re.compile(r"^\s*(?:select|insert|update|delete|with)\b", re.IGNORECASE)


def _known_tables() -> frozenset[str]:
    """Every table the migrations create. The vocabulary a name constant is matched against."""
    sql = "\n".join(p.read_text(encoding="utf-8")
                    for p in sorted((_ROOT / "migrations").glob("*.sql")))
    return frozenset(re.findall(r"create table (?:if not exists )?" + _TABLE, sql, re.IGNORECASE))


def _template(node: ast.AST) -> str | None:
    """A string-ish expression rendered with ``{NAME}`` where a variable was interpolated.

    ⛔⛔ THIS IS THE WHOLE POINT OF THE MODULE AND IT WAS THE SEVENTH TRAP OF THE AUDIT. A table
    whose name lives in a constant never appears in any SQL literal:
    `f"insert into {COVERAGE_TABLE} …"`, `"select … from " + AUTHORITY_TABLE`. Engine-wide there
    are **51** such constants, and before this function existed the measurement called
    `learning_event_inbox` write-only — a table `S5` had already PROVEN is loaded into every weekly
    learning batch, through `store._OPTIONAL_INBOX_TABLE`.

    ⛔ *A name-constant is a read* — third time this programme has paid for that, after
    `authority_rules` (read 3 readers as 1) and `_NODE_REFERENCES` (a write nothing could see).
    """
    if isinstance(node, ast.Constant):
        return node.value if isinstance(node.value, str) else None
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                inner = value.value
                parts.append("{" + inner.id + "}" if isinstance(inner, ast.Name) else "{?}")
            else:                                  # pragma: no cover - JoinedStr has 2 node kinds
                parts.append("{?}")
        return "".join(parts)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _template(node.left), _template(node.right)
        if left is None or right is None:
            return None
        return left + right
    if isinstance(node, ast.Name):
        return "{" + node.id + "}"
    return None


def _module_table_constants(tree: ast.Module, known: frozenset[str]) -> dict[str, tuple[str, ...]]:
    """``{constant: (table, …)}`` for every module-level constant naming known tables."""
    out: dict[str, tuple[str, ...]] = {}
    for node in tree.body:
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign) else [])
        value = getattr(node, "value", None)
        if value is None:
            continue
        for target in targets:
            if not isinstance(target, ast.Name):
                continue
            names = tuple(n for n in _string_elements(value) if n in known)
            if names:
                out[target.id] = names
    return out


@lru_cache(maxsize=1)
def _exported_table_constants() -> dict[str, dict[str, tuple[str, ...]]]:
    """``{dotted.module: {CONSTANT: (table, …)}}`` for every module in the tree.

    ⛔ WHY THIS EXISTS. `_module_table_constants` answers for ONE module, and
    `*a name-constant is a read*` — the rule this module's own `_template` docstring says the
    programme has now paid for three times. ⛔ It paid a fourth time, one import away:
    `HISTORY_TABLE = "metric_history"` lives in `context/analytic/history.py`, and the **fifteen**
    statements interpolating it live in `anomaly.py`, which imports it on line 68. The resolver
    could not see across the import, so those fifteen were counted as tables nobody could name.

    Measured 2026-10-04: **27 of the 49** table-position holes were an imported constant of
    exactly this kind — `HISTORY_TABLE` (15), `COHORT_MEMBERSHIP_TABLE` (6), `_TABLE` (3),
    `COHORT_DEFINITION_TABLE`, `L1_SEMANTIC_TABLE`, `BUNDLE_TABLE`.
    """
    known = _known_tables()
    out: dict[str, dict[str, tuple[str, ...]]] = {}
    for rel, source in _sources():
        try:
            tree = ast.parse(source)
        except SyntaxError:                        # pragma: no cover - the tree parses
            continue
        found = _module_table_constants(tree, known)
        if found:
            out[rel[:-3].replace("/", ".")] = found
    return out


def _imported_table_constants(tree: ast.Module) -> dict[str, tuple[str, ...]]:
    """``{local name: (table, …)}`` for table constants this module IMPORTS.

    ⛔ ONE HOP, AND DIRECT `from X import NAME` ONLY — bounded on purpose. No transitive
    resolution, no `import X` plus `X.NAME`, and no re-exports: *a re-export is not a definition*,
    and a resolver that chases arbitrarily far is one nobody can predict. The two forms left out
    are declared rather than forgotten, and `3.1`'s audit names them.

    An `as` alias is honoured, because the interpolation uses the local name.
    """
    exported = _exported_table_constants()
    out: dict[str, tuple[str, ...]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom) or node.level or not node.module:
            continue
        table_constants = exported.get(node.module)
        if not table_constants:
            continue
        for alias in node.names:
            tables = table_constants.get(alias.name)
            if tables:
                out[alias.asname or alias.name] = tables
    return out


def _local_table_aliases(tree: ast.Module,
                         resolved: dict[str, tuple[str, ...]]) -> dict[str, tuple[str, ...]]:
    """``{local name: (table, …)}`` for `local = CONSTANT` where CONSTANT names known tables.

    ⛔ THE THIRD WAY A NAME-CONSTANT HIDES A TABLE, and it accounted for **eight** of the
    twenty-four holes left after imports were resolved. All three activation modules do the same
    thing::

        table = L3_ACTIVATION_TABLE                 # a module constant, already resolvable
        f"insert into {table} (org_id, domain, …)"  # interpolates the LOCAL name

    So the constant was found and the statement still read as unresolved, because the hole carries
    the alias rather than the constant. ⛔ *A name-constant is a read* — the rule this module says
    the programme paid for three times, and this step paid for it twice more: once across an
    import, once across an assignment inside a function.

    ⛔ AMBIGUITY IS REFUSED, NOT GUESSED. A local name bound to two different table constants in
    one module resolves to NOTHING and the hole stays — the same answer `resolve_alias` gives a
    contended person name, and for the same reason: picking one would be a silent re-attribution
    that nothing records. One hop only; no reassignment tracking and no control flow.
    """
    out: dict[str, set[str]] = {}
    for node in ast.walk(tree):
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign) else [])
        value = getattr(node, "value", None)
        if not isinstance(value, ast.Name):
            continue
        tables = resolved.get(value.id)
        if not tables:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id != value.id:
                out.setdefault(target.id, set()).update(tables)
    # ⛔ A local bound to two different tables answers for neither.
    settled: dict[str, tuple[str, ...]] = {}
    for name, tables in out.items():
        seen = {t for t in tables}
        if len(seen) == 1:
            settled[name] = tuple(sorted(seen))
    return settled


def _statements(source: str, known: frozenset[str]) -> tuple[tuple[str, int], ...]:
    """``(sql, unresolved placeholders)`` for every SQL statement in the module.

    Constants naming tables are substituted; a literal whose enclosing call is ``print`` is
    skipped, because **printing a query is not running one** (`scripts/activate_tenant.py` prints
    `select … from situation_admission_decisions` for a human to paste).
    """
    tree = ast.parse(source)
    # ⛔ THE IMPORTED ONES FIRST, so a same-module constant of the same name WINS. A module that
    # redefines an imported name means the local value, and resolving to the far one would be a
    # measurement of a module that is not running.
    constants = {**_imported_table_constants(tree), **_module_table_constants(tree, known)}
    # ⛔ AFTER the two above, because a local alias resolves THROUGH them: `table = HISTORY_TABLE`
    # needs `HISTORY_TABLE` already known, whether it was defined here or imported.
    constants = {**_local_table_aliases(tree, constants), **constants}
    printed: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "print":
            printed.update(id(n) for n in ast.walk(node))
    out: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if id(node) in printed or not isinstance(node, (ast.Constant, ast.JoinedStr, ast.BinOp)):
            continue
        rendered = _template(node)
        if rendered is None or not _SQL_SHAPE.match(rendered):
            continue
        for name, tables in constants.items():
            if "{" + name + "}" in rendered:
                rendered = rendered.replace("{" + name + "}", tables[0])
        out.append((rendered, rendered.count("{")))
    return tuple(out)


#: ⛔⛔ TABLES WHOSE ROWS ARE WRITE-ONCE EXCEPT FOR NAMED COLUMNS —
#: `{table: (mutable columns, why, mover)}`.
#:
#: ⛔ WHY THIS IS A GUARD AND NOT A RECEIPT. The claim is about what the CODE may do, and the data
#: cannot answer it: a value rewritten in place leaves no trace unless the hash beside it is
#: recomputed, and recomputing `semantic_hash` in SQL would mean reimplementing the canonical
#: serialisation in a second language. ⛔ *A gate derived from an invented claim is a gate nobody
#: reads* — so this is a build-time guard and the absence of a receipt is deliberate, the same
#: decision the `context/` audit took for `graph_nodes`.
#:
#: ⛔ `learning_objects` IS THE WHOLE LEARNING LEDGER'S FOUNDATION, AND NOTHING GUARDED IT.
#: `feedback/publisher.persist` states the contract in its first line — *"Insert an **immutable**
#: proposal at `state`"* — and keeps it: it never updates an existing row, returning `reevaluated`
#: or `unchanged` instead, so an object that reached a later state can never be reopened. Measured
#: 2026-10-03: the engine holds exactly TWO `update learning_objects` statements,
#: `api/learning_routes.py` (human approval) and `feedback/org_rule_ingest.py` (discovery), and
#: **both set only `state`**. Nothing touches `proposed_value`, `semantic_hash`, `evidence` or
#: `visibility`.
#:
#: ⛔ THE DAY SOMEBODY WRITES `set proposed_value = …` — to "fix" a bad proposal, which is the
#: obvious thing to want — every downstream guarantee goes with it: `semantic_hash` is content-
#: derived, `learning_transitions` points at a row that no longer says what it said when the
#: transition was logged, and the Atlas's *"immutable proposal storage"* becomes a sentence about
#: the past. **That is the whole reason this table exists.**
WRITE_ONCE_TABLES: dict[str, tuple[frozenset[str], str, str]] = {
    "learning_objects": (
        frozenset({"state"}),
        "⛔ `publisher.persist`'s own first line: *'Insert an **immutable** proposal at `state`'*. "
        "The value columns are the proposal; `state` is the lifecycle, and `learning_transitions` "
        "records every move of it. Two updaters, both state-only: `api/learning_routes` (a human "
        "approving or rejecting a `human_review` object, under `for update`, 409 if the state is "
        "anything else) and `feedback/org_rule_ingest` (the discovery path's own lifecycle)",
        "MOVES WHEN a proposal legitimately needs a mutable field — ⛔ and then the field is named "
        "here with its reason, never added by widening this set to make a build pass"),
}


def set_columns(sql: str, table: str) -> frozenset[str]:
    """The columns an ``update <table> set …`` statement assigns. Pure, so it can be tested.

    ⛔ THE IDENTIFIER FILTER IS WHAT MAKES THIS SAFE, AND IT IS LOAD-BEARING. The clause is split
    on every comma, so `set active = false, expires_at = least(expires_at, :at)` — which
    `feedback/reset.py` really writes — yields a third fragment, `:at)`. The `fullmatch` below
    drops it, because anything following a comma inside a call is an expression fragment and never
    `identifier =`. That case is pinned by a parametrised test, so removing the filter fails.

    ⛔ A PAREN-DEPTH SPLIT WAS HERE AND WAS REMOVED. Its mutation **survived**: turning the
    depth-aware split back into a plain one changed no answer, because the filter catches the same
    wreckage. *A mutation that survives because something else catches it is a guard nobody is
    checking* — and a branch whose mutation cannot fail is complexity, not safety. The filter is
    the safeguard, so the filter is what the tests assert.

    ⛔ And it is a FUNCTION rather than a loop body because the first guard over it reimplemented
    the parse and asserted against its own copy — which is how a test ends up proving the thing it
    duplicated rather than the thing that ships. *One implementation, tested directly.*
    """
    out: set[str] = set()
    for match in re.finditer(rf"update\s+{re.escape(table)}\s+set\s+(.+?)(?:\s+where\s|$)",
                             " ".join(sql.lower().split())):
        for piece in match.group(1).split(","):
            name = piece.split("=")[0].strip()
            if re.fullmatch(r"[a-z_][a-z_0-9]*", name):
                out.add(name)
    return frozenset(out)


def update_columns(table: str) -> dict[str, frozenset[str]]:
    """``{file: {column, …}}`` for every ``update <table> set …`` in the engine and scripts."""
    known = _known_tables()
    out: dict[str, set[str]] = {}
    for rel, source in _sources():
        try:
            statements = _statements(source, known)
        except SyntaxError:                        # pragma: no cover - the tree parses
            continue
        for blob, _unresolved in statements:
            columns = set_columns(blob, table)
            if columns:
                out.setdefault(rel, set()).update(columns)
    return {f: frozenset(c) for f, c in out.items()}


def illegal_column_updates() -> tuple[tuple[str, str, str], ...]:
    """``(table, file, column)`` for every update of a write-once table outside its allowlist."""
    out: list[tuple[str, str, str]] = []
    for table, (mutable, _why, _mover) in WRITE_ONCE_TABLES.items():
        for file, columns in update_columns(table).items():
            for column in sorted(columns - mutable):
                out.append((table, file, column))
    return tuple(out)


def _sources() -> tuple[tuple[str, str], ...]:
    out: list[tuple[str, str]] = []
    for root in _ROOTS:
        if not root.exists():                      # pragma: no cover - both exist in-tree
            continue
        for path in sorted(root.rglob("*.py")):
            out.append((str(path.relative_to(_ROOT)), path.read_text(encoding="utf-8")))
    return tuple(out)


@lru_cache(maxsize=1)
def _table_usage() -> dict[str, dict[str, frozenset[str]]]:
    """⛔ CACHED, AND THAT IS NOT AN OPTIMISATION — IT IS WHAT MAKES THE MODULE USABLE. The first
    version re-parsed every file in `genios_engine/` and `scripts/` once per table lookup, and
    `written_without_a_receipt` calls `writers_of` in a loop: a single call took minutes and was
    killed. The answer is a property of one checkout, so computing it once is also the only
    honest reading of it."""
    known = _known_tables()
    acc: dict[str, dict[str, set[str]]] = {}
    for rel, source in _sources():
        try:
            statements = _statements(source, known)
        except SyntaxError:                        # pragma: no cover - the tree parses
            continue
        for blob, _unresolved in statements:
            sql = " ".join(blob.lower().split())
            for verb, pattern in _VERBS.items():
                for match in re.finditer(pattern, sql):
                    if match.group(1) in known:
                        acc.setdefault(match.group(1), {}).setdefault(verb, set()).add(rel)
    for site, (constant, verb, _why) in NAME_CONSTANT_TABLE_SITES.items():
        for table in _name_constant_tables(site, constant):
            acc.setdefault(table, {}).setdefault(verb, set()).add(f"genios_engine/{site}")
    return {t: {v: frozenset(f) for v, f in verbs.items()} for t, verbs in acc.items()}


#: ⛔⛔ A HOLE THAT IS ACTUALLY HIDING A TABLE — the only kind that weakens table coverage.
#:
#: ⛔ WHY THIS REGEX IS THE WHOLE OF `3.1`. Before it, `resolution()["unresolved"]` counted a
#: statement as unresolved if it carried ANY `{placeholder}`, and reported the total as though it
#: measured tables the resolver could not see. Measured 2026-10-04 over 645 such statements:
#:
#:     hole in a TABLE POSITION      49    7%
#:     holes ELSEWHERE ONLY         596   92%
#:
#: The 596 are predicates, column lists, join clauses and bind parameters assembled from shared
#: fragment constants — `{AUTHORITATIVE_SIGNAL_JOINS}` 133 times, `{AUTHORITATIVE_SCORE_SQL}` 116,
#: `{_COLUMNS}` 27 — and resolving them would lengthen the rendered SQL while answering no question
#: this module asks.
#:
#: ⛔ **AND SEVENTEEN OF THEM WERE OURS.** `{o}` in `platform/receipts.py` is `_org_filter`'s
#: output, the string `" and org_id = :org"`. The metric counted a correctly parameterised org
#: filter as an unresolved SQL statement, seventeen times, one module over from the one that
#: defines this measurement. ⛔ The org filter is CORRECT; the metric was wrong, and the fix
#: belongs here rather than in the code that flattered it.
#:
#: One number answering two questions is how `3.1` came to be scoped as *"639 unresolved SQL
#: statements"* when the figure that bears on table coverage was 49.
_TABLE_HOLE = re.compile(r"\b(?:from|join|into|update)\s+\{([^{}]*)\}", re.IGNORECASE)


#: ⛔⛔ **THE RATCHET — `{key: (ceiling, why)}`.**
#:
#: ⛔ The plan's sentence for this step ended *"the share is asserted so it cannot grow silently."*
#: It **was** asserted, and it **did** grow silently, from 639 to 645. Both halves are true because
#: the assertion was `unresolved / statements <= 0.30` against an actual share of **22.4%** —
#: ⛔ **eight percentage points of slack, about 220 statements of headroom.** A ceiling that loose
#: is a ceiling that cannot notice, and the test's own docstring still said *"639 of 2,867"*.
#:
#: ⛔⛔ SO THE RATCHET IS ABSOLUTE AND ON THE NUMBER THAT MATTERS. `unresolved_table` is small
#: enough that an exact ceiling is readable: a new hole is +1 and fails. The fragment count is
#: deliberately NOT ratcheted — fragments are predicates and column lists assembled from shared
#: constants, they are not a gap in this module's knowledge of tables, and ratcheting them would
#: fail the build for an ordinary refactor that extracts a `where` clause.
#:
#: ⛔ RAISING A CEILING IS A DECISION, NOT A FIX. The guard's message says so, because the first
#: instinct on a red ratchet is to edit the number — and the whole point is that doing so has to be
#: deliberate and visible in a diff.
RESOLUTION_CEILINGS: dict[str, tuple[int, str]] = {
    "unresolved_table": (
        16,
        "⛔ Holes where a TABLE belongs, after three resolver hops (imported constants, this "
        "module's own regexes, local aliases of a constant). All 16 are accounted for in "
        "`TABLE_HOLES_NOT_CLOSED` and `NAME_CONSTANT_TABLE_SITES`. ⛔ A 17th means a table the "
        "measurement cannot see — declare it with a category, or close it"),
}

#: ⛔ The FLOOR under the resolver's own reach. *A resolver that answers for 1 of 104 answers
#: nothing* — so a drop in how much it reads fails the build rather than quietly shrinking every
#: finding that depends on it. ⛔ The number is a floor and not an equality because adding SQL to
#: the engine is ordinary; losing the ability to read it is not.
STATEMENT_FLOOR = 2_800


#: ⛔ **EVERY TABLE-POSITION HOLE THE RESOLVER DOES NOT CLOSE, AND WHY** —
#: `{site: (category, why, mover)}`.
#:
#: ⛔ The number this step was scoped around was *"639 unresolved SQL statements (22%)"*. Measured:
#: 645 statements carried a placeholder, **49** had one where a TABLE belongs, and 596 were
#: predicates and column lists assembled from shared fragment constants. Three resolver hops later
#: (imported constants, this module's own regexes, local aliases of a constant) the table figure is
#: **16**, in 11 modules, and each one is accounted for below.
#:
#: ⛔⛔ THE CATEGORIES MATTER MORE THAN THE COUNT, because they are different problems:
#:
#:   `resolved-elsewhere`   a purpose-built reader already answers for it; the generic resolver
#:                          not closing the hole costs nothing
#:   `resolvable-deferred`  a loop over a constant collection of literal table names. ⛔ RESOLVABLE
#:                          AND DELIBERATELY NOT RESOLVED HERE — a fourth resolver hop with a
#:                          102-table blast radius is its own unit with its own baseline, not a
#:                          silent addition to this one
#:   `runtime`              the table is genuinely not knowable from the source
#:   `not-a-table`          the hole is not an engine table at all
#:
#: ✅ `context/merge.py` and `feedback/store.py` are not listed: they are already declared in
#: `NAME_CONSTANT_TABLE_SITES`, which resolves them by name-constant rather than leaving them open.
#:
#: Checked in BOTH directions by `tests/platform/test_every_table_hole_is_accounted_for.py`: a
#: declared site whose hole has closed is as much a lie as a hole nobody declared.
TABLE_HOLES_NOT_CLOSED: dict[str, tuple[str, str, str]] = {
    "api/account_routes.py": (
        "resolved-elsewhere",
        "⛔ `for tbl in _ORG_SCOPED_TABLES: delete from {tbl}` — the tenant erasure loop. ✅ The "
        "102 tables ARE read, by `deletion_list()`, which reads the constant off this module's AST "
        "on purpose. The generic resolver leaving the hole open costs nothing because the one "
        "question that matters about this loop already has a dedicated reader",
        "MOVES WHEN the erasure loop stops being a loop over a module constant — at which point "
        "`deletion_list()` breaks loudly, which is the right failure"),
    "capture/journey.py": (
        "resolvable-deferred",
        "⛔ `for table, when in _LEDGERS` — tuple unpacking over a module constant of "
        "`(table, column)` pairs. Resolvable, and the unpacking makes it the hardest of the "
        "deferred set: a resolver would have to know which element of the pair is the table",
        "MOVES WITH context/backfill.py and the two scripts/ loops — one unit, one baseline"),
    "context/backfill.py": (
        "resolvable-deferred",
        '⛔ `for table in ("context_situations", "context_correlation_members", '
        '"context_correlations")` — an INLINE TUPLE OF LITERAL TABLE NAMES, the most trivially '
        "resolvable hole in the engine. ⛔ It is open only because the resolver reads module-level "
        "assignments and not loop targets",
        "MOVES WITH capture/journey.py — see that entry"),
    "scripts/e2e_verify.py": (
        "resolvable-deferred",
        "⛔ `for t in _GRAPH_TABLES` — a module-level list of literal table names. Resolvable: the "
        "collection is a constant and every element is a literal",
        "MOVES WITH capture/journey.py — see that entry"),
    "scripts/equivalence_check.py": (
        "resolvable-deferred",
        "⛔ `for t in TABLES` — a module-level tuple of literal table names. Resolvable, same shape "
        "as `scripts/e2e_verify.py`",
        "MOVES WITH capture/journey.py — see that entry"),
    "api/home_routes.py": (
        "runtime",
        "⛔ `_weekly(conn, org, table: str, …)` — the table is a FUNCTION PARAMETER, which is the "
        "dataflow case: closing it needs the call graph, not constant substitution. ✅ Every caller "
        "passes a literal, so the tables ARE attributed from the call sites; what is unknowable "
        "here is which one this statement is about",
        "MOVES WHEN a resolver walks call sites. ⛔ That is dataflow analysis and it is not worth "
        "it for one statement"),
    "capture/connectors/database.py": (
        "runtime",
        "⛔ `f\"select * from {self._table}\"` ×3 — the table comes from TENANT CONFIGURATION and "
        "cannot be known from the source at all. ✅ And it is the one site with a real injection "
        "surface, which the module already guards: an identifier validator runs first "
        "(*\"unsafe {what} identifier\"*) and the comment beside the query says *\"table = trusted "
        "config, not user input\"*. ⛔ A different risk class from every other entry here",
        "MOVES WHEN a tenant can name a table the validator admits and the engine does not own — "
        "which is the validator's job, not this resolver's"),
    "scripts/wipe_org_data.py": (
        "runtime",
        "⛔ `for t in [t for t in tables if …]`, where `tables` is read from `information_schema` "
        "**at run time**. ✅ Unresolvable BY DESIGN and the script says why: *\"A positive selection "
        "cannot be out of date\"* — it asks the live database which tables carry `org_id` rather "
        "than keeping a list somebody must remember to extend",
        "MOVES WHEN never. ⛔ Resolving this would mean replacing a correct design with a stale "
        "list, which is the inversion this module exists to prevent"),
    "scripts/rebuild_graph.py": (
        "not-a-table",
        "⛔ `create table if not exists {tbl}_bak_{ts} as …` — the hole is part of a name being "
        "MINTED, not an engine table being read. The table does not exist until the script runs "
        "and is a timestamped backup",
        "MOVES WHEN never — there is nothing here for a table-coverage measurement to know"),
}


#: ⛔⛔ **THE RESOLVER'S OWN REGEXES, WHICH IT WAS COUNTING AS SQL** — `{site: (constant, why)}`.
#:
#: ⛔⛔ THE OBSERVER WAS MEASURING ITS OWN INSTRUMENT. `_VERBS` is built out of `_TABLE`, this
#: module's table-name **regex**::
#:
#:     _TABLE = r"([a-z_][a-z_0-9]*)"
#:     "insert": rf"insert into {_TABLE}"
#:
#: Those templates match `_SQL_SHAPE`, carry a `{_TABLE}` hole in a table position, and are not SQL
#: at all — so **three of the twenty-seven remaining table-position holes were the measurement's
#: own patterns.** The same family as `{o}` in `platform/receipts.py`, which is `_org_filter`'s
#: output and was counted seventeen times, except that this one is in the measuring module itself.
#:
#: ⛔ WHY A DECLARATION AND NOT A HEURISTIC. The obvious filter is *"skip a statement containing a
#: regex character class"* — and **SQL contains them**: `0047_l3_domain_compiler.sql` has
#: `expertise_id ~ '^expertise_[0-9a-f]{64}$'`. A heuristic that cannot tell a `check` constraint
#: from a regex would hide real statements, which is the failure this module exists to prevent.
#: Three named sites are cheaper to read and impossible to over-apply.
#:
#: ⛔ `_table_usage` IS NOT AFFECTED and that is worth saying: its verb regexes look for
#: `([a-z_][a-z_0-9]*)` after the keyword, and `{_TABLE}` does not match a class without `{`. Only
#: the COUNT was wrong, never the attribution — so nothing in the coverage findings moves when this
#: is excluded.
#:
#: Checked in BOTH directions by `tests/platform/test_the_resolver_does_not_count_itself.py`: a
#: declared site that no longer holds a pattern is as much a lie as a pattern counted as SQL.
SELF_MEASURED_PATTERNS: dict[str, tuple[str, str]] = {
    "platform/table_coverage.py": (
        "_TABLE",
        "⛔ `_VERBS` interpolates this module's own table-name regex into four templates that look "
        "exactly like SQL (`insert into {_TABLE}`, `update {_TABLE} set`, `delete from {_TABLE}`, "
        "`(?:from|join) {_TABLE}`). Counting them made the instrument part of its own reading"),
}


def _rel_key(rel: str) -> str:
    """`genios_engine/platform/x.py` → `platform/x.py`, the spelling every declaration here uses."""
    return rel[len("genios_engine/"):] if rel.startswith("genios_engine/") else rel


def table_holes(sql: str) -> tuple[str, ...]:
    """The placeholder names sitting where a TABLE belongs, in order.

    ⛔ `{NAME}` is a bare variable and `{?}` is any other expression — `_template`'s own spelling.
    Both count: `f"select * from {self._table}"` hides a table exactly as `f"… {TABLE}"` does, and
    the connector that does it says so in a comment beside the validator it runs first.
    """
    return tuple(_TABLE_HOLE.findall(sql))


@lru_cache(maxsize=1)
def resolution() -> dict[str, int]:
    """⛔ COVERAGE, REPORTED BESIDE THE VERDICT. How many SQL statements were read, how many still
    carry an unresolved `{placeholder}`, and how many table-name constants were resolved.

    *A resolver that answers for 1 of 104 answers nothing* — so the guard asserts this, and a drop
    in resolution fails the build rather than quietly shrinking the findings.

    ⛔⛔ `unresolved` IS KEPT AND IS NO LONGER THE NUMBER TO QUOTE. It counts a statement carrying
    ANY placeholder, which conflates *"a table we cannot see"* with *"a predicate assembled from a
    constant"*. The split:

    * **`unresolved_table`** — a hole where a table belongs. ⛔ **This is the one that weakens
      table coverage**, and the one the guard ratchets.
    * **`unresolved_fragment`** — holes only elsewhere: predicates, column lists, joins, bind
      parameters. Not a gap in this module's knowledge of tables.

    The old key stays because `scripts/context_coverage_report.py` and the coverage guard both read
    it, and because a measurement that changes its own definition without keeping the old one is
    how two numbers come to mean one thing.
    """
    known = _known_tables()
    statements = constants = unresolved = modules = 0
    unresolved_table = unresolved_fragment = 0
    for _rel, source in _sources():
        try:
            tree = ast.parse(source)
        except SyntaxError:                        # pragma: no cover - the tree parses
            continue
        found = _module_table_constants(tree, known)
        if found:
            modules += 1
            constants += len(found)
        for sql, holes in _statements(source, known):
            statements += 1
            if not holes:
                continue
            unresolved += 1
            # ⛔ TWO QUESTIONS, TWO NUMBERS. A statement can hold both kinds of hole; it counts
            # once, under the table question, because that is the one that weakens coverage.
            # ⛔ THE INSTRUMENT IS NOT PART OF THE READING. See `SELF_MEASURED_PATTERNS`.
            declared = SELF_MEASURED_PATTERNS.get(_rel_key(_rel))
            names = [h for h in table_holes(sql)
                     if not (declared and h == declared[0])]
            if names:
                unresolved_table += 1
            else:
                unresolved_fragment += 1
    return {"statements": statements, "unresolved": unresolved,
            "unresolved_table": unresolved_table,
            "unresolved_fragment": unresolved_fragment,
            "table_name_constants": constants, "modules_with_constants": modules,
            "known_tables": len(known)}


def table_usage() -> dict[str, dict[str, frozenset[str]]]:
    """``{table: {verb: {file, …}}}`` over every ``text(...)`` literal in the engine and scripts.

    A fresh outer dict each call so a caller cannot poison the cache; the inner frozensets are
    already immutable.
    """
    return {t: dict(v) for t, v in _table_usage().items()}


def _string_elements(node: ast.AST) -> tuple[str, ...]:
    """The table names in a constant. ⛔ A TUPLE OF PAIRS CONTRIBUTES ITS FIRST ELEMENT ONLY.

    `context/merge.py:_NODE_REFERENCES` is `(("graph_facts", "subject_node_id"), …)`. Taking every
    string made `node_id` and `anchor_node_id` into TABLES, and both then appeared in the
    written-and-unread list — ⛔ two invented tables in a report whose whole purpose is to name
    tables nothing reads.
    """
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        out: list[str] = []
        for element in node.elts:
            if isinstance(element, (ast.Tuple, ast.List)) and element.elts:
                head = element.elts[0]
                if isinstance(head, ast.Constant) and isinstance(head.value, str):
                    out.append(head.value)
            elif isinstance(element, ast.Constant) and isinstance(element.value, str):
                out.append(element.value)
        return tuple(out)
    return tuple(n.value for n in ast.walk(node)
                 if isinstance(n, ast.Constant) and isinstance(n.value, str))


def _module_constant(rel_to_engine: str, name: str) -> ast.AST | None:
    path = _ENGINE / rel_to_engine
    if not path.exists():                          # pragma: no cover - guarded by the test
        return None
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target] if isinstance(node, ast.AnnAssign) else [])
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name:
                return node.value
    return None


def _name_constant_tables(rel_to_engine: str, constant: str) -> tuple[str, ...]:
    """The tables a declared constant names, following ONE level of indirection.

    ⛔ `feedback/store.QUARANTINABLE_SEAMS` is `(_OPTIONAL_FEEDBACK_TABLE, _OPTIONAL_INBOX_TABLE)`
    — a tuple of NAMES, not of strings. Reading only string literals returned nothing and left
    `learning_event_inbox` looking unread for the second time in one audit. Same rule as
    `target_policy._scope_of`: resolve one hop, and report what is still unresolved rather than
    assuming it away.
    """
    node = _module_constant(rel_to_engine, constant)
    if node is None:
        return ()
    found = list(_string_elements(node))
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        for element in node.elts:
            if isinstance(element, ast.Name):
                inner = _module_constant(rel_to_engine, element.id)
                if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                    found.append(inner.value)
    known = _known_tables()
    return tuple(s for s in found if s in known)


def deletion_list() -> tuple[str, ...]:
    """The tables the tenant erasure loop names, read off `api/account_routes.py`'s AST."""
    return _name_constant_tables(*_DELETE_LIST)


def tables_with_a_receipt() -> frozenset[str]:
    from genios_engine.platform.receipts import receipts

    blob = " ".join(r.sql.lower() for r in receipts("org_probe"))
    return frozenset(t for t in _table_usage() if re.search(rf"\b{t}\b", blob))


def writers_of(table: str) -> frozenset[str]:
    verbs = _table_usage().get(table, {})
    return frozenset().union(*(verbs.get(v, frozenset()) for v in WRITE_VERBS)) \
        if any(v in verbs for v in WRITE_VERBS) else frozenset()


def readers_of(table: str) -> frozenset[str]:
    return _table_usage().get(table, {}).get("read", frozenset())


def written_and_unread() -> tuple[str, ...]:
    """Tables with a writer and no reader anywhere.

    ⛔ A RECEIPT IS NOT A READER, AND THE FIRST VERSION OF THIS EXCLUDED RECEIPTED TABLES. Adding
    the merge receipt — whose SQL names `source_identity_map` as one of `_NODE_REFERENCES`'s pairs
    — made a DECLARED write-only table look like it had gained a reader, and the both-ways guard
    went red. ⛔ The two questions are different: *"does any code consult this table"* and *"does
    anything check its contents in production"*. Conflating them meant writing a receipt could
    silently retire a finding about readership. `written_without_a_receipt` asks the second
    question and is where the receipt condition belongs.
    """
    return tuple(sorted(t for t in _table_usage() if writers_of(t) and not readers_of(t)))


def undeclared_unread_writes() -> tuple[str, ...]:
    return tuple(t for t in written_and_unread() if t not in UNREAD_WRITES)


def stale_unread_declarations() -> tuple[str, ...]:
    """Declared write-only tables that now have a reader or a receipt — the declaration is a lie."""
    live = set(written_and_unread())
    return tuple(sorted(t for t in UNREAD_WRITES if t not in live))


def written_without_a_receipt(package: str) -> tuple[tuple[str, int], ...]:
    """``(table, external reader count)`` for one package's writes that no receipt covers,
    busiest first — the ranking that says which missing receipt costs the most."""
    receipted = tables_with_a_receipt()
    prefix = f"genios_engine/{package}/"
    out = []
    for table, verbs in _table_usage().items():
        writers = frozenset().union(*(verbs.get(v, frozenset()) for v in WRITE_VERBS)) \
            if any(v in verbs for v in WRITE_VERBS) else frozenset()
        if not any(w.startswith(prefix) for w in writers) or table in receipted:
            continue
        external = sum(1 for r in verbs.get("read", ()) if not r.startswith(prefix))
        out.append((table, external))
    return tuple(sorted(out, key=lambda row: (-row[1], row[0])))


__all__ = ["NAME_CONSTANT_TABLE_SITES", "RETRACTED_UNREAD_WRITES", "UNREAD_WRITES", "WRITE_VERBS", "deletion_list",
           "illegal_column_updates", "readers_of", "set_columns", "stale_unread_declarations",
           "table_usage", "tables_with_a_receipt", "update_columns",
           "resolution", "undeclared_unread_writes", "writers_of", "written_and_unread",
           "written_without_a_receipt"]
