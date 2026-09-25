"""Which writers of `signals` bind the row to the L2 situation its subject already holds.

⛔ A COLUMN NO WRITER NAMES IS NULL FOREVER. Migration 0182 added `signals.situation_id` in L2-7 so
that a card could say which business situation it came from. FIVE functions insert into `signals`.
ONE of them names the column. The other four leave it null on every row they have ever written, and
`deliver/card_source.classify` reads null as `UNINTERPRETED` — so the main path's cards are all
labelled "no situation" by a schema that has had the column for two migrations.

WHY THIS IS A DECLARATION AND NOT A FIX. The four silent writers are not silent by oversight, and
three of them CAN see a situation for their subject: `reason/runner.run` already loads every node's
situation in one query (`_bulk_load_situations`, line 318) and all three call sites sit inside that
same function with the map in scope. Wiring them would cost zero extra queries and zero migrations.

⛔ IT IS NOT DONE HERE BECAUSE CO-LOCATION IS NOT PROVENANCE. A pack rule fires on graph nodes. It
never reads the situation. Writing that situation's id onto the signal would assert "this card came
from that situation" about a decision that was made without it — the same class of untruth as
`graph_edges.valid_from` carrying event time under a knowledge-time predicate (L3-04), and worse
here, because `classify` is BINARY: any non-empty id reads as `CardSource.SITUATION`, so there is
no value that means "the situation is on the subject but the rule did not use it".

⛔ AND IT WOULD CORRUPT THE MEASUREMENT THAT DECIDES THE CUTOVER. `card_source.COMPARISON_KEYS`
grades the new path against the old on `cards_from_situation` vs `cards_uninterpreted`. Binding
co-located situations moves rows from the second to the first without changing a single decision —
the old path would appear to have become the new one. `reason/uncited_lanes.UNCITED_LANES` measured
the size of that on 2026-09-16: 9 of 11 OPEN general-pack signals sit on a subject that also holds
an active L2 situation, and recorded that binding them "is an architecture decision, not a repair,
and it is the user's to make."

⛔ DECIDED 2026-09-25 — HOLD. The decision was put to the product owner with three options and the
answer was to change nothing for now. It is recorded here rather than only in a plan document
because this module is what a future reader will find first, and a silence whose reason lives
somewhere else is a silence that gets "fixed" by the next person who notices it.

  REFUSED · wiring the three main-path lanes to the co-located situation. It is three lines and it
           would move 82% of the pilot's uninterpreted cards, which is exactly what makes it
           dangerous: nothing about any decision would change, so `card_source.COMPARISON_KEYS`
           would report the old path as having become the new one.
  MOVES WHEN · `CardSource` gains a third value meaning "a situation sits on this subject but the
           rule did not read it". That is a PRODUCT question before it is a code one — whether a
           founder is helped or confused by a card that says so — and it is not answered yet.
           `test_classify_is_binary_which_is_what_makes_co_location_a_lie` fails the day the
           answer arrives, which is the signal to come back and rewrite this paragraph.

SO THE GAP IS DECLARED, MEASURED, AND HELD — the same discipline as `DARK_DOMAINS`, `SILENT_LANES`
and `LINEAGE_UNPROTECTED`. What this module adds is that it can no longer be LOST: the totality
guard below reads the real column list out of each writer's AST, so a fifth writer that appears
without a declaration is a build failure, and the day the decision is revisited the change is one
line per writer with a test already standing over it.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SignalWriter:
    """One function that inserts into `signals`, and whether its row can name a situation."""

    module: str
    function: str
    binds: bool
    why: str


#: ⛔ CLOSED, AND CHECKED IN BOTH DIRECTIONS by `tests/test_the_situation_reaches_the_signal.py`:
#: every writer declared here must really contain the statement, and every module in the tree that
#: contains the statement must be declared here. One direction alone is how `mcp/` escaped the
#: import ratchet in L3-01 — declared-but-gone and present-but-undeclared are different failures.
SIGNAL_WRITERS: tuple[SignalWriter, ...] = (
    SignalWriter(
        "genios_engine.reason.runner", "_emit", False,
        "THE PACK LANE, AND THE LARGEST ONE. Authored rules evaluated against graph nodes. The "
        "situation for the subject is already in scope — `run()` loads `situations_by_node` at "
        "line 885 and calls `_emit` at line 1310 inside the same function — so this is a one-line "
        "change whose only cost is the truth of the claim it would make. HELD ON THE DECISION."),
    SignalWriter(
        "genios_engine.reason.publication", "publish_native_signal", False,
        "THE NATIVE LANE. Called from `run()` at line 1347 with the same map in scope, keyed by "
        "`publication.subject_node_id`. Same decision, same one line. HELD ON THE DECISION."),
    SignalWriter(
        "genios_engine.reason.composer", "compose_deal_health", False,
        "THE COMPOSITE LANE. Called from `run()` at line 1365; its subject is `p['deal_id']`, so "
        "it needs the map passed rather than a single id. ⛔ ITS CLAIM WOULD BE THE WEAKEST OF "
        "THE THREE — a composite reasons over several member signals across a deal's cluster, so "
        "'the situation on the deal node' is one of several and the composite used none of them. "
        "If the decision is yes, this lane is the one to wire LAST and measure separately."),
    SignalWriter(
        "genios_engine.reason.domain_shadow", "_emit_capability_signal", True,
        "⛔ THE ONLY WRITER THAT BINDS, AND THE ONLY ONE ENTITLED TO. The compiled lane resolves "
        "a corpus FOR THE SITUATION'S DOMAIN and reasons over the situation itself, so the id it "
        "writes is provenance rather than co-location. It is also feature-flagged, which is why "
        "the column reads as null on almost every row in production today."),
    SignalWriter(
        "genios_engine.reason.team.emit", "_write_card", False,
        "⛔ A DIFFERENT VOCABULARY, AND IT MUST NOT BE WIRED. The team lane's 'situation' is a "
        "`team_situations` row — a verify/QA item — not a `context_situations` business "
        "situation. Binding it would put a foreign key's worth of meaning on a word that matches "
        "by spelling only. `uncited_lanes.UNCITED_LANES['']` already declares this lane's other "
        "boundary (no pack, no audited run). MOVES WHEN: never, by this route."),
)


def signal_insert_columns(source: str) -> tuple[frozenset[str], ...]:
    """Every `insert into signals` column list in `source`, read out of the AST.

    ⛔ THE AST, NOT THE TEXT, AND THAT IS THE WHOLE POINT. Python concatenates adjacent string
    literals at PARSE time, so a statement wrapped across eight source lines arrives here as one
    `ast.Constant` — and comments never enter the tree at all. Four assertions in this project
    went green on a word that appeared only in a comment (L3-04 twice, L3-05, L3-10) and one went
    red on a correct file for the same reason. A structural read cannot make either mistake.
    """
    tree = ast.parse(source)
    return tuple(
        _columns(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
        and _is_insert_statement(node.value))


def _is_insert_statement(text: str) -> bool:
    """Whether `text` IS the statement, rather than prose that names it.

    ⛔ FOUND BY THE GUARD ITSELF, ON ITS FIRST RUN. A docstring is an `ast.Constant` like any
    other, so this module's own explanation of what it parses registered as a fifth writer of
    `signals` and the totality check went red on a correct tree. Requiring the VALUES clause is
    what makes the discriminator structural: prose describes an insert, an insert has a column
    list and then supplies them. Nothing here asks whether a word is nearby.
    """
    if "insert into signals" not in text:
        return False
    tail = text.split("insert into signals", 1)[1]
    return tail.lstrip().startswith("(") and "values" in tail.lower()


def _columns(sql: str) -> frozenset[str]:
    """The parenthesised column list that opens `insert into signals (...)`, split on commas."""
    depth, out = 0, []
    for char in sql.split("insert into signals", 1)[1]:
        if char == "(":
            depth += 1
            if depth == 1:
                continue
        elif char == ")":
            depth -= 1
            if depth == 0:
                break
        if depth >= 1:
            out.append(char)
    return frozenset(part.strip() for part in "".join(out).split(",") if part.strip())


def binding_drift(columns_by_module: dict[str, frozenset[str]]) -> tuple[str, ...]:
    """Writers whose real column list disagrees with what this file declares about them.

    Returns a sentence per disagreement, in declaration order — a writer that started binding
    without its entry being updated, and one that stopped. Both are the declaration going stale,
    which is the only way a declared silence becomes a lie nobody notices.
    """
    drifted = []
    for writer in SIGNAL_WRITERS:
        if writer.module not in columns_by_module:
            continue
        real = "situation_id" in columns_by_module[writer.module]
        if real != writer.binds:
            drifted.append(
                f"{writer.module}.{writer.function} declares binds={writer.binds} "
                f"but its insert {'names' if real else 'omits'} situation_id")
    return tuple(drifted)


def undeclared(modules_writing_signals: frozenset[str]) -> tuple[str, ...]:
    """Modules that insert into `signals` and are not declared above — a sixth writer."""
    return tuple(sorted(modules_writing_signals - {w.module for w in SIGNAL_WRITERS}))


def missing(modules_writing_signals: frozenset[str]) -> tuple[str, ...]:
    """Declared writers whose statement is gone — the other direction, and the one L3-01 lost."""
    return tuple(sorted({w.module for w in SIGNAL_WRITERS} - modules_writing_signals))


#: ⛔ The one number that says how large the silence is, so it is read as a held decision rather
#: than as a healthy lane. Recomputed by the test from `SIGNAL_WRITERS`, never hand-maintained.
def bound_fraction() -> tuple[int, int]:
    """`(writers that bind, writers total)` — 1 of 5 until the decision in the docstring is made."""
    return sum(1 for w in SIGNAL_WRITERS if w.binds), len(SIGNAL_WRITERS)


__all__ = ["SIGNAL_WRITERS", "SignalWriter", "binding_drift", "bound_fraction", "missing",
           "signal_insert_columns", "undeclared"]
