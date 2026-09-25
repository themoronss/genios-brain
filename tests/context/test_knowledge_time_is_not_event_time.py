"""L3-04 · the as-of read asks when we KNEW, and one of its three tables answered when it HAPPENED.

`GET /graph/as-of` says in its own docstring that it answers "what did GeniOS know when it made
that decision?" — the question doc 02 says every enterprise security review asks. It answered it
with ONE predicate over three tables, and the three did not agree about what `valid_from` means:
nodes and facts take the column's now() default (knowledge time), while `write_edge` binds it to
`coalesce(occurred_at, now())` — THE EVENT'S OWN TIME.
"""
from __future__ import annotations

import re
from pathlib import Path

_STORE = Path(__file__).resolve().parents[2] / "genios_engine/context/graph_store.py"
_MIGRATION = Path(__file__).resolve().parents[2] / "migrations/0184_graph_recorded_at.sql"
_SRC = _STORE.read_text()


def _insert_columns_and_values(table: str) -> dict[str, str]:
    """The INSERT's column -> value mapping, parsed rather than grepped.

    ⛔ THIS HELPER EXISTS BECAUSE THE FIRST DRAFT OF THIS FILE FAILED ITS OWN MUTATION PROBES.
    Two of five mutations applied cleanly and every test stayed green:

        removing `recorded_at` from the edges INSERT — because the EXPLANATORY COMMENT this step
        added directly above the statement contains the word, and the assertion sliced 1,400
        characters from the `insert into` and asked whether the word appeared ANYWHERE in them;

        redefining `valid_from` to `now()` on edges — because the assertion looked for
        `coalesce(:vf, now())` anywhere in the statement, and it survived on `last_seen_at`.

    Sixth occurrence of one family (L1-14, L1-18, L2-6, L3-00, L3-02b, here). The shape never
    changes: AN ASSERTION ABOUT TEXT NEAR A THING RATHER THAN ABOUT THE THING'S STRUCTURE. So this
    reads the concatenated SQL string literals, strips the Python comments that are not part of
    them, and zips the column list to the values list POSITIONALLY.
    """
    i = _SRC.index(f'"insert into {table} (')
    raw = _SRC[i:i + 2600]
    # ⛔ `graph_facts` composes its statement with Python conditionals —
    # `+ (", valid_to" if status == "historical" else "") +` — so a naive literal scan picks up
    # `historical` as if it were SQL and a naive end-boundary stops inside the conditional. Strip
    # the conditional's tail first; what remains concatenates to the fullest variant, which is the
    # one worth asserting on because it is the one with the most columns.
    raw = re.sub(r'\s+if\s+[^\n]*?\s+else\s+""', "", raw)
    sql = "".join(re.findall(r'"([^"]*)"', raw))
    # Cut at the close of the values list, balanced from the `values (`.
    v = sql.index("values (")
    depth, end = 0, len(sql)
    for k in range(v + len("values "), len(sql)):
        if sql[k] == "(":
            depth += 1
        elif sql[k] == ")":
            depth -= 1
            if depth == 0:
                end = k + 1
                break
    sql = sql[:end]
    cols = re.search(r"\(([^()]*)\)\s*values\s*\((.*)\)", sql, re.S)
    assert cols, f"could not parse the {table} insert"
    names = [c.strip() for c in cols.group(1).split(",") if c.strip()]
    # Values can contain commas inside function calls, so split at depth 0.
    vals, depth, cur = [], 0, ""
    for ch in cols.group(2):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            vals.append(cur.strip()); cur = ""
        else:
            cur += ch
    vals.append(cur.strip())
    assert len(names) == len(vals), f"{table}: {len(names)} columns, {len(vals)} values"
    return dict(zip(names, vals))



# =================================================================================================
# 1 · ⛔ THE PREDICATE NO LONGER ASKS THE WRONG COLUMN
# =================================================================================================

def test_the_as_of_predicate_reads_knowledge_time():
    """The whole defect in one line. `valid_from` alone let a backdated edge appear in an as-of
    read of a date before we learned it."""
    from genios_engine.context.graph_store import _WINDOW_AT
    assert "coalesce(recorded_at, valid_from)" in _WINDOW_AT
    assert not re.search(r"(?<!,\s)\bvalid_from <= :t", _WINDOW_AT), \
        "the bare valid_from comparison is back — a backdated edge is visible before we knew it"


def test_the_close_side_of_the_window_is_untouched():
    """`valid_to` is stamped at close time on all three tables, so it was already knowledge time.
    Changing it would have been a change with no defect behind it."""
    from genios_engine.context.graph_store import _WINDOW_AT
    assert "(valid_to is null or valid_to > :t)" in _WINDOW_AT


def test_one_predicate_still_spans_all_three_tables():
    """⛔ `_view`'s stated property: "one connection, three selects, one immutable view... the two
    can only ever differ in the window predicate they are given". A per-table predicate would have
    fixed edges by giving up the property that makes an as-of answer coherent."""
    view = _SRC[_SRC.index("def _view("):]
    view = view[:view.index("return GraphView")]
    assert view.count("{where}") == 3, "the three selects must share one window predicate"


# =================================================================================================
# 2 · ⛔ ALL THREE WRITERS STAMP IT, AND THE DATABASE DOES THE STAMPING
# =================================================================================================

def test_every_graph_writer_records_when_we_learned():
    """POSITIONAL. `recorded_at` must be a real column in the statement whose value is `now()` —
    not a word that happens to appear somewhere near it."""
    for table in ("graph_nodes", "graph_facts", "graph_edges"):
        mapping = _insert_columns_and_values(table)
        assert "recorded_at" in mapping, \
            f"{table} inserts without recording when we learned it"
        assert mapping["recorded_at"] == "now()", \
            f"{table}.recorded_at is written as {mapping['recorded_at']!r}, not the database clock"


def test_recorded_at_is_never_a_bind_parameter():
    """⛔ A caller that could supply it could BACKDATE WHAT WE KNEW — the one thing an audit read
    must be unable to express. `now()` is inlined in the SQL on purpose; there is no `:recorded`."""
    assert ":recorded" not in _SRC and ":rec_at" not in _SRC


# =================================================================================================
# 3 · ⛔ THE EDGE COLUMN KEEPS ITS OTHER MEANING
# =================================================================================================

def test_edges_still_stamp_valid_from_with_the_event_time():
    """`reason/moments/recall` takes max(valid_from) as "when did we last relate to this node" and
    `.../slice` orders by it. Redefining the column would have moved every one of those answers to
    a different question WITH NOTHING FAILING — the worst kind of change, and the reason this step
    added a column instead of repurposing one."""
    mapping = _insert_columns_and_values("graph_edges")
    assert mapping["valid_from"] == "coalesce(:vf, now())", (
        f"graph_edges.valid_from is written as {mapping['valid_from']!r}. It must stay the EVENT "
        "time: reason/moments reads it as 'when did we last relate to this node', and moving it "
        "to write time changes every one of those answers with nothing failing.")
    assert mapping["recorded_at"] == "now()"


def test_the_moments_readers_are_untouched_and_still_read_valid_from():
    root = Path(__file__).resolve().parents[2] / "genios_engine/reason/moments"
    joined = "".join(p.read_text() for p in root.glob("*.py"))
    assert "valid_from) from graph_edges" in joined or "e.valid_from from graph_edges" in joined, \
        "the moments readers moved; re-check whether valid_from still means event time to them"


# =================================================================================================
# 4 · ⛔ THE MIGRATION REFUSES TO FABRICATE HISTORY
# =================================================================================================

def test_recorded_at_is_nullable_and_never_backfilled():
    """⛔ `default now()` would assert we learned a tenant's whole history at the instant this
    deployed; `default valid_from` would assert the very thing the step exists to stop believing.
    WE DO NOT KNOW WHEN WE LEARNED THE EXISTING ROWS — the same rule that makes claimed_total null
    rather than zero, and completeness_bp None rather than 10000.
    """
    sql = _MIGRATION.read_text()
    for line in sql.splitlines():
        if "add column if not exists recorded_at" in line:
            assert "default" not in line.lower(), f"recorded_at must not be backfilled: {line!r}"
            assert "not null" not in line.lower(), f"recorded_at must stay nullable: {line!r}"
    assert "update graph_" not in sql.lower(), "the migration must not stamp existing rows"


def test_all_three_tables_get_the_column():
    sql = _MIGRATION.read_text()
    for table in ("graph_nodes", "graph_facts", "graph_edges"):
        assert f"alter table {table}" in sql, f"{table} has no recorded_at — the coalesce would " \
                                             "fail on it and the predicate spans all three"


def test_the_indexes_are_partial_on_not_null():
    """Pre-migration rows cannot answer the audit question, and an index over their nulls would be
    dead weight on the largest part of the table for as long as the oldest tenant lives."""
    sql = _MIGRATION.read_text()
    assert sql.count("where recorded_at is not null") == 3


def test_the_migration_is_idempotent():
    sql = _MIGRATION.read_text()
    assert sql.count("add column if not exists") == 3
    assert sql.count("create index if not exists") == 3
