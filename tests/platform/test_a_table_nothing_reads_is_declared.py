"""Every table a package writes and nothing reads is declared — and the resolver reports itself.

⛔ WHY THE COVERAGE ASSERTIONS COME FIRST. This audit's first pass named **six** write-only tables.
Each time the resolver was broadened, a finding died: the digit-aware table pattern added one,
reading `scripts/` removed one, classifying mentions by VERB removed another, reading SQL held in a
module constant removed two more, and following a name constant through a function argument removed
`learning_event_inbox` — a table `S5` had already proven is read.

> ⛔⛔ **Nine findings survived three broadenings of the measurement. That is the only reason to
> believe them.** *A resolver that answers for 1 of 104 answers nothing* — so `resolution()` is
> asserted here, and a drop in it fails the build instead of quietly shrinking the findings.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from genios_engine.platform import table_coverage as TC

_REPO = Path(__file__).resolve().parents[2]


# ── the resolver reports its own coverage, and it may not degrade ──────────────────────────────

def test_the_resolver_reads_most_of_the_sql_in_the_repo():
    r = TC.resolution()
    assert r["statements"] >= 2_800, r
    assert r["known_tables"] >= 185, r
    assert r["table_name_constants"] >= 60, (
        "the table-name constants this resolver follows have dropped; a constant it cannot see is "
        "a read it cannot see, and every one of those became a false finding in this audit")


def test_the_unresolved_share_is_declared_rather_than_hidden():
    """⛔⛔ THIS CEILING IS WHY THE NUMBER GREW SILENTLY, and the docstring below used to say
    *"639 of 2,867"* — a count in prose, stale by six.

    The share assertion is kept and is deliberately the LOOSE guard: 22.4% against a 30% ceiling is
    about 220 statements of headroom, and fragment SQL grows for ordinary reasons. ⛔ The guard that
    actually ratchets is `test_the_table_hole_count_cannot_grow_silently`, on an absolute ceiling
    over `unresolved_table`. Counts in this docstring are now DERIVED, because a comment's count
    ages faster than its claim.

    ⛔ Originally: 639 of 2,867 statements still carry a `{placeholder}` this module cannot resolve — a
    table name passed through a FUNCTION ARGUMENT needs dataflow, not constant substitution. The
    share is asserted so it cannot grow silently; the known cases are in
    `NAME_CONSTANT_TABLE_SITES`."""
    r = TC.resolution()
    assert r["unresolved"] / r["statements"] <= 0.30, r


# ── both directions over the declaration ───────────────────────────────────────────────────────

def test_no_write_only_table_is_undeclared():
    assert TC.undeclared_unread_writes() == (), (
        "a package now writes a table nothing reads and it is not declared. ⛔ Before declaring "
        "it, check the five things that made six of this audit's findings wrong: a reader in "
        "scripts/, a mention that is prose, SQL held in a module constant, a table name in a "
        "name constant, and that same name passed as a function argument")


def test_no_declaration_has_quietly_gained_a_reader():
    assert TC.stale_unread_declarations() == (), (
        "a declared write-only table now has a reader or a receipt — remove the entry "
        "deliberately and add it to RETRACTED_UNREAD_WRITES rather than leaving a lie")


@pytest.mark.parametrize("table", sorted(TC.UNREAD_WRITES))
def test_every_declaration_names_a_real_writer_and_what_moves_it(table):
    writer, why, mover = TC.UNREAD_WRITES[table]
    for part in writer.split(" + "):
        assert (_REPO / "genios_engine" / part.strip()).exists(), part
    assert len(why) > 80
    assert mover.startswith(("MOVES WHEN", "MOVES WITH", "⛔ MOVES"))


@pytest.mark.parametrize("table", sorted(TC.UNREAD_WRITES))
def test_every_declared_table_really_has_a_writer_and_no_reader(table):
    assert TC.writers_of(table), f"{table} is declared write-only and has no writer"
    assert not TC.readers_of(table), f"{table} now has readers: {sorted(TC.readers_of(table))}"


@pytest.mark.parametrize("table", sorted(TC.RETRACTED_UNREAD_WRITES))
def test_every_retraction_is_true(table):
    """⛔ A retraction needs its own measurement. These two were called write-only and are not."""
    assert TC.readers_of(table), (
        f"{table} is recorded as a RETRACTED finding, which claims it has a reader — and it does "
        "not. Either the reader went away (move it back) or the retraction was wrong")
    assert table not in TC.UNREAD_WRITES


# ── one case per trap this audit hit ───────────────────────────────────────────────────────────

def test_a_digit_inside_a_table_name_resolves():
    """⛔ `[a-z_]+` resolved `l2_convergence` as table `l`, and `l2_model_runs` vanished entirely.
    Second time that pattern has lied in this programme."""
    usage = TC.table_usage()
    assert "l2_convergence" in usage
    assert "l" not in usage


def test_a_column_name_in_a_pair_tuple_is_not_a_table():
    """⛔ `_NODE_REFERENCES` is `(("graph_facts", "subject_node_id"), …)`. Taking every string made
    `node_id` and `anchor_node_id` into tables, and both appeared in a report whose entire purpose
    is to name tables nothing reads."""
    usage = TC.table_usage()
    assert "node_id" not in usage and "anchor_node_id" not in usage
    assert "graph_facts" in usage


def test_the_pair_tuple_branch_is_guarded_directly_not_only_by_its_effect():
    """⛔ A MUTATION SURVIVED HERE AND THE REASON IS WORTH KEEPING. Disabling the pair-handling in
    `_string_elements` changed nothing, because `_name_constant_tables` also filters against the
    migrations' table set and `node_id` is not a table. The defence is real but it is the SECOND
    one, so the effect test above cannot see the first failing.

    ⛔ *A guard whose mutation survives because something else catches it is a guard nobody is
    checking.* This asserts the branch itself, so the redundancy is intentional rather than lucky.
    """
    import ast as _ast

    pairs = _ast.parse('(("graph_facts", "subject_node_id"), ("graph_aliases", "node_id"))',
                       mode="eval").body
    assert TC._string_elements(pairs) == ("graph_facts", "graph_aliases"), (
        "the pair-tuple branch no longer takes the FIRST element of each pair; column names will "
        "reach the table vocabulary and only the migrations filter will stop them")
    flat = _ast.parse('("graph_facts", "graph_edges")', mode="eval").body
    assert TC._string_elements(flat) == ("graph_facts", "graph_edges")


def test_an_operator_report_in_scripts_counts_as_a_reader():
    """⛔ `situation_admission_decisions` looked write-only because the resolver read only
    `genios_engine/`. An operator-read table is a read table."""
    readers = TC.readers_of("situation_admission_decisions")
    assert any(r.startswith("scripts/") for r in readers), sorted(readers)
    assert "situation_admission_decisions" not in TC.UNREAD_WRITES


def test_printing_a_query_is_not_running_one():
    """⛔ `scripts/activate_tenant.py` prints `select outcome, count(*) from
    situation_admission_decisions …` for a human to paste. The mirror of the trap above, and the
    reason the extractor skips a literal whose enclosing call is `print`."""
    assert "scripts/activate_tenant.py" not in TC.readers_of("situation_admission_decisions")
    src = (_REPO / "scripts" / "activate_tenant.py").read_text(encoding="utf-8")
    assert "situation_admission_decisions" in src, (
        "the fixture this test relies on is gone; pick another printed query or delete this test")


def test_sql_held_in_a_module_constant_is_still_sql():
    """⛔ `context/runner.py` builds its state hash from a triple-quoted module constant and passes
    it by name, so no `text(...)` call contains the literal — and `context_node_lifecycle` read as
    write-only."""
    assert "genios_engine/context/runner.py" in TC.readers_of("context_node_lifecycle")


def test_a_table_name_reached_through_a_function_argument_is_declared():
    """⛔⛔ The limit of static resolution: `store.py` passes `_OPTIONAL_INBOX_TABLE` INTO
    `_read_optional_seam`, which interpolates the parameter. `S5` proved the inbox is read, so the
    site is declared — and the declaration is what makes the reader visible."""
    assert "feedback/store.py" in TC.NAME_CONSTANT_TABLE_SITES
    assert TC.readers_of("learning_event_inbox"), (
        "the inbox reads as write-only again — NAME_CONSTANT_TABLE_SITES stopped resolving")


def test_a_write_through_a_name_constant_is_counted():
    """⛔ `merge.py` repoints `source_identity_map` in a generic loop, so no SQL names it."""
    assert "genios_engine/context/merge.py" in TC.writers_of("source_identity_map")


def test_the_prose_that_documents_a_table_is_not_a_use_of_it():
    """Four guards in this programme broke on their own documentation. This module names tables in
    its own declarations, and must not thereby become their reader."""
    assert "genios_engine/platform/table_coverage.py" not in TC.readers_of(
        "contract_spend_attributions")


# ── the erasure invariant: already declared, already guarded ───────────────────────────────────

def test_the_erasure_loop_names_only_real_tables():
    names = TC.deletion_list()
    assert len(names) >= 100
    known = {t for t in TC.table_usage()} | set(TC.UNREAD_WRITES)
    unknown = [n for n in names if n not in known]
    assert len(unknown) <= 12, (
        f"the erasure loop names tables nothing in the repo touches: {unknown}. ⛔ Harmless at "
        "runtime (the delete is a no-op) and a sign the list and the schema have drifted")


def test_a_deleted_tenant_leaving_nothing_behind_is_a_RECEIPT_not_a_list():
    """⛔⛔ THE AUDIT'S LARGEST FALSE FINDING WAS STOPPED HERE. 77 of 183 org-scoped tables are in
    neither `_ORG_SCOPED_TABLES` nor `RETAINED_AFTER_ERASURE`, which reads as a 77-table retention
    hole. ⛔ It is not: `_ORG_SCOPED_TABLES` governs `/reset`, whose own docstring says it *"keeps
    the account, connections, tasks"*; ACCOUNT erasure is done by migration 0033's foreign keys,
    and `RETAINED_AFTER_ERASURE`'s docstring says the receipt below is what asks the deployed
    schema whether anything else survives. **Read the endpoint's contract before calling a list
    incomplete.**"""
    from genios_engine.platform.receipts import receipts

    claims = [r.claim for r in receipts("org_probe")]
    assert "a deleted tenant leaves nothing behind" in claims, (
        "the receipt that makes the erasure invariant answerable against the DEPLOYED schema is "
        "gone — the four `reasoning_*` children cascade through a parent, which no code-level "
        "list can show")


def test_the_reasoning_children_still_cascade_through_a_parent():
    """⛔ Verified, not trusted: `RETAINED_AFTER_ERASURE` claims the four `reasoning_*` children go
    *"through a parent that does"*. They do — `reasoning_candidates -> reasoning_runs ->
    reasoning_context_snapshots -> reasoning_capability_snapshots -> orgs`."""
    import re

    sql = "\n".join(p.read_text(encoding="utf-8")
                    for p in sorted((_REPO / "migrations").glob("*.sql")))
    edges: dict[str, set[str]] = {}
    for m in re.finditer(r"alter table (?:only )?([a-z_][a-z_0-9]*)[^;]*?references\s+"
                         r"([a-z_][a-z_0-9]*)", sql, re.IGNORECASE | re.DOTALL):
        edges.setdefault(m.group(1).lower(), set()).add(m.group(2).lower())
    # ⛔ AND THE INLINE ONES. The first version of this test read only `alter table … references`
    # and failed on `reasoning_candidates`, whose FK is declared inside its own CREATE TABLE —
    # a weaker copy of the measurement that had already verified the claim. *Before trusting a
    # guard, check it against the measurement it is standing in for.*
    body, current, buf = {}, None, []
    for line in sql.splitlines():
        s = line.strip()
        start = re.match(r"create table (?:if not exists )?([a-z_][a-z_0-9]*)", s, re.IGNORECASE)
        if start:
            current, buf = start.group(1).lower(), []
            continue
        if current is not None:
            if s.startswith(");"):
                body[current] = "\n".join(buf)
                current = None
            else:
                buf.append(s)
    for table, text_body in body.items():
        for m in re.finditer(r"references\s+([a-z_][a-z_0-9]*)", text_body, re.IGNORECASE):
            edges.setdefault(table, set()).add(m.group(1).lower())

    def reaches(table: str, seen: frozenset[str] = frozenset()) -> bool:
        if table in seen:
            return False
        return any(p == "orgs" or reaches(p, seen | {table}) for p in edges.get(table, ()))

    for child in ("reasoning_candidates", "reasoning_candidate_checks",
                  "reasoning_reasoner_results", "reasoning_run_outputs"):
        assert reaches(child), f"{child} no longer cascades to orgs — erasure is now incomplete"


# ── the ranking that says which missing receipt costs the most ──────────────────────────────────

def test_the_busiest_unreceipted_tables_are_named_and_ordered():
    ranked = TC.written_without_a_receipt("context")
    assert ranked, "context/ now has a receipt for every table it writes"
    assert [n for _, n in ranked] == sorted((n for _, n in ranked), reverse=True)
    assert ranked[0][0] in {"graph_nodes", "graph_edges"}, ranked[:3]
