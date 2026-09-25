"""L3-13 · the Intelligence Graph is already foreign keys, and one column decides whether it fills.

⛔ THE PLAN FOR THIS STEP WAS WRONG AND THIS FILE IS WHERE THAT IS RECORDED. It asked for
`intel_nodes` + `intel_edges` — five node kinds, six edge kinds, a migration — on the premise that
"no table holds both a situation and a decision". Measured, the premise is false in three separate
ways:

  * `signals` holds BOTH — `situation_id` (0182) beside `reasoning_run_id` (0029) and
    `reasoning_decision_hash` (0031, FK'd to `reasoning_run_outputs`).
  * the plan's fallback — "it dies when a signal is archived" — is false too. There is no
    `delete from signals` anywhere in the tree; every lifecycle move is
    `update signals set status=...` (`open · acted · expired · resolved`), which is the repo's
    own soft-delete doctrine. Nothing purges the reasoning spine either.
  * the chain does not stop at the decision. `executions` carries `decision_hash` and
    `execution_outcomes` inherits it, so situation → decision → delivery → outcome is four of the
    five planned node kinds, joined, today.

Building two tables over that would have been a SECOND COPY of a graph the schema already
enforces — the over-scaffolding this plan has now refused twelve times. What is genuinely missing
is smaller and worse: four of the five writers of `signals` never name `situation_id`, so the
column is null on almost every row in production and `card_source.classify` calls the result
UNINTERPRETED. See `reason/situation_binding` for why that is held rather than fixed.
"""
from __future__ import annotations

import ast
from pathlib import Path

from genios_engine.deliver.card_source import CardSource, classify
from genios_engine.reason import situation_binding as sb

ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "genios_engine"
MIGRATIONS = ROOT / "migrations"


def _modules_writing_signals() -> frozenset[str]:
    """Every module in the tree whose AST contains an `insert into signals` statement.

    ⛔ READ FROM THE AST, so a module that merely NAMES the statement in a comment — this file's
    own subject matter does exactly that — is not counted as a writer."""
    found = set()
    for path in ENGINE.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:                                     # pragma: no cover - unreadable file
            continue
        if "insert into signals" not in text:               # cheap pre-filter, AST decides
            continue
        if sb.signal_insert_columns(text):
            found.add(str(path.relative_to(ROOT).with_suffix("")).replace("/", "."))
    return frozenset(found)


# =================================================================================================
# 1 · ⛔ THE TOTALITY GUARD, CHECKED IN BOTH DIRECTIONS
# =================================================================================================

def test_every_writer_of_signals_is_declared():
    """⛔ A SIXTH WRITER MUST NOT BE ABLE TO APPEAR QUIETLY. This is the direction that matters
    most: a new lane that inserts signals without an entry would be null on `situation_id` and
    would look exactly like the four that are null ON PURPOSE."""
    extra = sb.undeclared(_modules_writing_signals())
    assert extra == (), (
        f"{len(extra)} module(s) insert into signals with no entry in SIGNAL_WRITERS: {extra}. "
        "Add one saying whether the lane can honestly name a situation, and why.")


def test_every_declared_writer_still_writes_signals():
    """⛔ THE OTHER DIRECTION, AND THE ONE L3-01 LOST. `mcp/` escaped the import ratchet because
    only one side was checked. A declaration for a writer that no longer exists is a silence
    nobody will ever end, because the thing it describes is gone."""
    gone = sb.missing(_modules_writing_signals())
    assert gone == (), (
        f"SIGNAL_WRITERS names {gone}, which no longer insert into signals. Delete the entries "
        "rather than leaving them — a stale declaration reads as a live gap.")


def test_what_each_writer_declares_matches_the_column_list_it_actually_has():
    """⛔ THE DECLARATION CANNOT GO STALE SILENTLY. `binds` is checked against the real parsed
    column list, so the day somebody wires one of the four the build tells them to update the
    reason beside it — which is where the architecture decision is written down."""
    columns = {}
    for writer in sb.SIGNAL_WRITERS:
        path = ROOT / (writer.module.replace(".", "/") + ".py")
        lists = sb.signal_insert_columns(path.read_text(encoding="utf-8"))
        assert len(lists) == 1, f"{writer.module} has {len(lists)} signal inserts, expected 1"
        columns[writer.module] = lists[0]
    assert sb.binding_drift(columns) == ()


def test_exactly_one_of_the_five_writers_binds_a_situation_today():
    """⛔ THE NUMBER, PINNED, so the gap is a measurement rather than an impression. When the
    decision in `situation_binding`'s docstring is made this goes to 4 of 5 — never 5, because
    the team lane's 'situation' is a different word that happens to match."""
    assert sb.bound_fraction() == (1, 5)
    binder = [w for w in sb.SIGNAL_WRITERS if w.binds]
    assert [w.module for w in binder] == ["genios_engine.reason.domain_shadow"], (
        "the compiled lane is the only writer that reasons OVER the situation, and therefore the "
        "only one whose situation_id is provenance rather than co-location")


# =================================================================================================
# 2 · ⛔ THE PARSER IS STRUCTURAL — the blunt-grep family cannot reach it
# =================================================================================================

def test_a_comment_naming_the_column_does_not_count_as_naming_it():
    """⛔ THE ASSERTION THAT MAKES EVERY ASSERTION ABOVE MEAN SOMETHING. Five checks in this
    project went green — or red — on a word that lived only in a comment (L1-14, L1-18, L2-6,
    L3-00, L3-02b, L3-04 twice, L3-05, L3-10). Comments are not in the AST, so this one cannot."""
    lying = ('# situation_id is written here, honestly\n'
             'q = ("insert into signals (signal_id, org_id) values (:a,:b)")\n')
    (cols,) = sb.signal_insert_columns(lying)
    assert "situation_id" not in cols
    assert cols == frozenset({"signal_id", "org_id"})


def test_a_statement_wrapped_across_many_lines_is_read_as_one():
    """Adjacent string literals concatenate at PARSE time, which is why every writer above yields
    exactly one column list despite being wrapped across six to nine source lines. A regex over
    the text would have found the first fragment and stopped."""
    wrapped = ('q = ("insert into signals (signal_id, "\n'
               '     "org_id, situation_id) "\n'
               '     "values (:a,:b,:c)")\n')
    (cols,) = sb.signal_insert_columns(wrapped)
    assert cols == frozenset({"signal_id", "org_id", "situation_id"})


def test_prose_that_names_the_statement_is_not_a_writer():
    """⛔ THE DEFECT THIS GUARD FOUND ON ITS OWN FIRST RUN, PINNED SO IT CANNOT RETURN.

    A docstring is an `ast.Constant` like any other, so `situation_binding`'s own explanation of
    what it parses was counted as a fifth writer of `signals` and the totality check went red on a
    correct tree. The discriminator is now the statement's SHAPE — a column list, then VALUES —
    which is a structural question. Had it instead been "ignore strings that look like prose",
    this file would have joined the nine blunt greps it was written to avoid.
    """
    assert sb.signal_insert_columns(
        '"""Parses the insert into signals column list out of the AST."""\n') == ()
    assert sb.signal_insert_columns('x = "insert into signals is what runner does"') == ()
    assert sb.signal_insert_columns(
        'x = "insert into signals (a) values (:a)"') == (frozenset({"a"}),)


def test_the_values_list_is_not_mistaken_for_the_column_list():
    """The statement has two parenthesised lists and only the first one names columns. Reading the
    second would report every writer as binding, since `:sit` is not `situation_id`."""
    (cols,) = sb.signal_insert_columns(
        'q = "insert into signals (a, b) values (:x, cast(:y as jsonb))"')
    assert cols == frozenset({"a", "b"}), "nested parens in VALUES must not leak into the columns"


# =================================================================================================
# 3 · ⛔ THE CHAIN THE PLAN WANTED TO BUILD ALREADY EXISTS — pinned so nobody builds it twice
# =================================================================================================

def _column_exists(table: str, column: str) -> bool:
    """True if any migration adds `column` to `table`, by create or by alter."""
    for path in sorted(MIGRATIONS.glob("*.sql")):
        sql = path.read_text(encoding="utf-8").lower()
        if f"alter table {table} add column if not exists {column} " in sql:
            return True
        if f"alter table {table} add column {column} " in sql:
            return True
        block = sql.split(f"create table if not exists {table} (", 1)
        if len(block) == 2 and any(
                line.strip().startswith(column + " ")
                for line in block[1].split(");", 1)[0].splitlines()):
            return True
    return False


def test_situation_to_decision_to_delivery_to_outcome_is_already_foreign_keys():
    """⛔ FOUR OF THE FIVE PLANNED NODE KINDS, JOINED, WITH NO NEW TABLE. This is the measurement
    that deleted a migration and two tables from the Layer 3 plan. If any link here disappears the
    argument for `intel_nodes`/`intel_edges` comes back, and this test is where that is noticed."""
    assert _column_exists("signals", "situation_id"), "situation → signal (0182)"
    assert _column_exists("signals", "reasoning_decision_hash"), "signal → decision (0031)"
    assert _column_exists("executions", "decision_hash"), "decision → delivery (0041)"
    assert _column_exists("execution_outcomes", "decision_hash"), "delivery → outcome (0041)"


def test_nothing_deletes_a_signal_so_the_join_cannot_die():
    """⛔ THE PLAN'S OWN FALLBACK ARGUMENT, MEASURED AND FALSE. L3-14 justified new tables with
    'it dies when a signal is archived'. Every lifecycle transition is an UPDATE of `status`; a
    hard delete appearing here would restore the argument, so it must fail the build instead."""
    offenders = sorted(
        str(path.relative_to(ROOT))
        for path in ENGINE.rglob("*.py")
        if "delete from signals" in path.read_text(encoding="utf-8").lower())
    assert offenders == [], (
        f"{offenders} hard-delete signals. That destroys the only situation → decision edge the "
        "system has; retire with status instead.")


# =================================================================================================
# 4 · ⛔ WHY THE GAP IS HELD — the shape of the decision, pinned
# =================================================================================================

def test_classify_is_binary_which_is_what_makes_co_location_a_lie():
    """⛔ THE REASON THE FOUR WRITERS STAY SILENT. There is no value meaning "a situation sits on
    this subject but the rule did not read it" — any non-empty id reads as provenance. If a third
    source is ever added, the decision changes shape and `situation_binding`'s docstring is stale.
    """
    assert classify(situation_id="sit_1") is CardSource.SITUATION
    assert classify(situation_id=None) is CardSource.UNINTERPRETED
    assert classify(situation_id="   ") is CardSource.UNINTERPRETED
    assert len(list(CardSource)) == 2, (
        "CardSource gained a member — re-read situation_binding's held decision, which assumes "
        "there is no way to say 'co-located but not reasoned from'")


def test_the_held_decision_names_both_a_reason_and_a_mover():
    """Every declared silence in this codebase carries both. One without a mover is a silence
    nobody ever ends; one without a reason gets 'fixed' by the next reader."""
    for writer in sb.SIGNAL_WRITERS:
        if writer.binds:
            continue
        assert len(writer.why) > 120, f"{writer.module} has no real reason recorded"
        assert ("HELD ON THE DECISION" in writer.why
                or "MOVES WHEN" in writer.why
                or "wire LAST" in writer.why), f"{writer.module} declares no mover"
