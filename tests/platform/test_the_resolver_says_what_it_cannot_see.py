"""⛔⛔ STEP 3.1 · the "639 unresolved SQL statements" — and why that was the wrong number.

The plan scoped this step as *"the 639 unresolved SQL statements (22%) — a table name passed
through a function argument needs dataflow… the share is asserted so it cannot grow silently."*
⛔ Measured, three of those four clauses were wrong.

```
"unresolved SQL statements"            645   ⛔ the plan said 639; it grew and nothing noticed
  hole in a TABLE POSITION              49   7%
  holes ELSEWHERE ONLY                 596   92%  predicates, column lists, bind parameters
after three resolver hops               16   imported constants · own regexes · local aliases
```

⛔ **And seventeen of the 596 were ours.** `{o}` in `platform/receipts.py` is `_org_filter`'s
output, the string `" and org_id = :org"` — a correctly parameterised filter counted as unresolved
SQL, one module from the one defining this measurement.

⛔⛔ **And three of the 49 were this module's own regexes.** `_VERBS` interpolates `_TABLE`, the
table-name pattern, into four templates shaped exactly like SQL. **The observer was counting its
own instrument.**

⛔ The ratchet the plan describes **existed** — `unresolved / statements <= 0.30` against an actual
22.4%, which is about 220 statements of headroom. A ceiling that loose cannot notice, which is how
639 became 645. It is now absolute and on `unresolved_table`.
"""

from __future__ import annotations

import ast
import re

import pytest

from genios_engine.platform import table_coverage as TC

RESOLUTION = TC.resolution()


# ------------------------------------------------------------------- U01 · the metric is split

def test_the_two_counts_partition_the_old_one():
    """⛔ The old key is KEPT. A measurement that redefines itself without keeping the old number
    is how two figures come to mean one thing."""
    assert RESOLUTION["unresolved_table"] + RESOLUTION["unresolved_fragment"] \
        == RESOLUTION["unresolved"]


def test_the_table_count_is_a_small_fraction_of_the_old_headline():
    """⛔ THE POINT OF THE SPLIT. If these were close, one number would have been fine."""
    assert RESOLUTION["unresolved_table"] * 4 < RESOLUTION["unresolved_fragment"], RESOLUTION


def test_table_holes_finds_a_hole_where_a_table_belongs():
    assert TC.table_holes("select * from {HISTORY_TABLE} where o = :o") == ("HISTORY_TABLE",)
    assert TC.table_holes("insert into {T} (a) values (1)") == ("T",)
    assert TC.table_holes("update {T} set x = 1") == ("T",)
    assert TC.table_holes("select 1 from a join {T} on a.id = {T}.id") == ("T",)


def test_table_holes_ignores_our_OWN_org_filter():
    """⛔ `{o}` is `_org_filter`'s output and was counted seventeen times. The filter is CORRECT;
    the metric was wrong, and the fix belongs in the metric."""
    assert TC.table_holes("select count(*) from cards where true{o}") == ()
    assert TC.table_holes("select count(*) from cards where x = {y} and z = {w}") == ()


def test_table_holes_is_case_insensitive_because_sql_is():
    assert TC.table_holes("SELECT * FROM {T}") == ("T",)
    assert TC.table_holes("INSERT INTO {T} VALUES (1)") == ("T",)


# ------------------------------------------------------- U02 · constants across an import and an alias

def test_an_imported_table_constant_resolves():
    """⛔ `HISTORY_TABLE = "metric_history"` is in `context/analytic/history.py` and the fifteen
    statements using it are in `anomaly.py`, which imports it. *A name-constant is a read.*"""
    tree = ast.parse("from genios_engine.context.analytic.history import HISTORY_TABLE\n"
                     "q = f'select 1 from {HISTORY_TABLE}'\n")
    assert TC._imported_table_constants(tree) == {"HISTORY_TABLE": ("metric_history",)}


def test_an_import_alias_is_honoured_because_the_hole_carries_the_local_name():
    tree = ast.parse("from genios_engine.context.analytic.history import HISTORY_TABLE as HT\n")
    assert TC._imported_table_constants(tree) == {"HT": ("metric_history",)}


def test_a_relative_import_is_NOT_followed():
    """⛔ One hop, direct `from X import NAME` only — bounded on purpose. A resolver that chases
    arbitrarily far is one nobody can predict, and *a re-export is not a definition*.

    ⛔ THE BOUND IS ENFORCED TWICE AND THIS TEST ONLY REACHES ONE HALF — found by a mutation that
    deleted the `node.level` check and **survived**. It survived because the export map is keyed by
    FULL dotted path, so a relative import's bare `node.module` ("history") matches no key either
    way. So `node.level` is belt and the key format is braces, and deleting the belt changes
    nothing observable. The guard below asserts the belt is still in the source, because a check
    that cannot be caught by behaviour can at least be caught by absence.
    """
    tree = ast.parse("from .history import HISTORY_TABLE\n")
    assert TC._imported_table_constants(tree) == {}
    source = (TC._ROOT / "genios_engine" / "platform" / "table_coverage.py") \
        .read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(source))
              if isinstance(n, ast.FunctionDef) and n.name == "_imported_table_constants")
    levels = [n for n in ast.walk(fn)
              if isinstance(n, ast.Attribute) and n.attr == "level"]
    assert levels, (
        "`node.level` is no longer checked in `_imported_table_constants`. Nothing observable "
        "changes today because the export map is keyed by full dotted path -- but the bound is "
        "then resting on one mechanism instead of two, and the next person to change the key "
        "format removes it by accident")


def test_a_module_attribute_access_is_NOT_followed():
    """⛔ `import X; X.NAME` is the second form left out, declared rather than forgotten."""
    tree = ast.parse("import genios_engine.context.analytic.history as h\n"
                     "q = f'select 1 from {h.HISTORY_TABLE}'\n")
    assert TC._imported_table_constants(tree) == {}


def test_a_local_alias_of_a_table_constant_resolves():
    """⛔ All three activation modules do `table = L3_ACTIVATION_TABLE` and interpolate the LOCAL
    name -- eight of the holes left after imports."""
    tree = ast.parse("T = 'cards'\ndef f():\n    table = T\n    return f'select 1 from {table}'\n")
    resolved = TC._module_table_constants(tree, TC._known_tables())
    assert TC._local_table_aliases(tree, resolved) == {"table": ("cards",)}


def test_an_ambiguous_local_alias_is_REFUSED_rather_than_guessed():
    """⛔⛔ A local bound to two different table constants answers for NEITHER -- the same answer
    `resolve_alias` gives a contended person name, and for the same reason: picking one is a silent
    re-attribution that nothing records."""
    tree = ast.parse("A = 'cards'\nB = 'signals'\n"
                     "def f(flag):\n    t = A\n    if flag:\n        t = B\n    return t\n")
    resolved = TC._module_table_constants(tree, TC._known_tables())
    assert TC._local_table_aliases(tree, resolved) == {}


def test_a_same_module_constant_WINS_over_an_imported_one_of_the_same_name():
    """⛔ A module that redefines an imported name means the local value; resolving to the far one
    would measure a module that is not running."""
    source = ("from genios_engine.context.analytic.history import HISTORY_TABLE\n"
              "HISTORY_TABLE = 'cards'\n"
              "q = f'select 1 from {HISTORY_TABLE}'\n")
    rendered = [sql for sql, _n in TC._statements(source, TC._known_tables())]
    assert any("from cards" in s for s in rendered), rendered


# ----------------------------------------------- U03a · the instrument is not part of the reading

def test_the_self_measured_pattern_site_is_declared_and_real():
    """Forward: the declared constant must actually be a regex this module interpolates."""
    assert set(TC.SELF_MEASURED_PATTERNS) == {"platform/table_coverage.py"}
    constant, why = TC.SELF_MEASURED_PATTERNS["platform/table_coverage.py"]
    assert constant == "_TABLE"
    assert constant not in TC._known_tables(), (
        f"{constant} is a known table now, so excluding it hides real SQL")
    value = getattr(TC, constant)
    assert any(ch in value for ch in "([\\"), (
        f"{constant} = {value!r} is no longer a regex; the exclusion has nothing to exclude")
    assert "instrument" in why


def test_the_verb_patterns_still_look_like_sql_which_is_why_they_were_counted():
    """⛔ Not a style point: in SOURCE they match `_SQL_SHAPE` and carry a hole in a table
    position. If they stopped doing so the exclusion would be dead weight.

    ⛔ READ FROM THE SOURCE, NOT FROM `_VERBS`. The first version of this test asserted
    `table_holes(_VERBS["read"])` and failed, because the f-string is evaluated at import:
    `_VERBS["read"]` is already `"(?:from|join) ([a-z_][a-z_0-9]*)"` with no hole left. **The
    resolver reads the file, so the test must read the file too** — asserting against the runtime
    value was testing a different object than the one being measured.
    """
    source = (TC._ROOT / "genios_engine" / "platform" / "table_coverage.py") \
        .read_text(encoding="utf-8")
    verbs = set(re.findall(r'"(?:insert|update|delete|read)":\s*rf"([^"]*)"', source))
    assert len(verbs) == 4, (
        f"found {len(verbs)} distinct verb patterns in source, not 4 -- `_VERBS` changed shape")
    counted = {p for p in verbs if TC.table_holes(p) == ("_TABLE",)}
    # ⛔ THREE OF THE FOUR, AND THE FOURTH IS INSTRUCTIVE. `"(?:from|join) {_TABLE}"` is NOT
    # counted, because `_TABLE_HOLE` wants whitespace directly after the keyword and this pattern
    # has `join)` — the alternation's closing paren. ✅ So the declaration's claim of exactly three
    # is right, and it is right for a reason worth knowing: the resolver's own `read` pattern is
    # the one shape of SQL-looking text it cannot see.
    # ⛔ `3.1b` gave `read` a `(?<!delete )` lookbehind, so its template no longer BEGINS with
    # the keyword and `table_holes` cannot see it either. One pattern is still missed and it
    # is still the read one -- asserted by shape, not by its exact text, because the text now
    # changes whenever the lookbehind does.
    assert len(counted) == 3, sorted(verbs - counted)
    missed = verbs - counted
    assert len(missed) == 1 and "(?:from|join)" in next(iter(missed)), sorted(missed)


def test_the_declaration_quoting_the_pattern_is_counted_by_a_regex_over_the_file():
    """⛔⛔ FOUND BY THE TEST ABOVE FAILING WITH 5 WHERE I EXPECTED 4, AND IT IS THE FOURTH TIME
    THIS FAMILY HAS BITTEN.

    `SELF_MEASURED_PATTERNS`' comment quotes `"insert": rf"insert into {_TABLE}"` as its example,
    so a regex counting verb patterns in the file finds **five**: four real and one inside the
    declaration that explains them. The declaration about an instrument being measured is itself
    matched by a measurement of that instrument.

    The family so far: a declaration that falsifies its own count (`use_restriction`, "0 files");
    a declaration that satisfies the test that its source exists (the quoted contract rule); a
    correction whose names nothing checked; and now a quoted example counted as a real one. ⛔ The
    fix each time is to COUNT DISTINCTLY or to EXCLUDE THE BLOCK — never to delete the quote,
    because the quote is what makes the declaration readable.
    """
    source = (TC._ROOT / "genios_engine" / "platform" / "table_coverage.py") \
        .read_text(encoding="utf-8")
    occurrences = re.findall(r'"insert":\s*rf"insert into \{_TABLE\}"', source)
    assert len(occurrences) >= 2, (
        "the declaration no longer quotes the pattern it excludes. That is allowed, but then this "
        "test has nothing to say -- delete it deliberately rather than leaving it green")


def test_excluding_them_moves_the_count_by_exactly_three():
    """Backward, and measured rather than asserted: the declaration claims three."""
    known = TC._known_tables()
    counted = 0
    for rel, source in TC._sources():
        if TC._rel_key(rel) != "platform/table_coverage.py":
            continue
        for sql, n in TC._statements(source, known):
            if n and "_TABLE" in TC.table_holes(sql):
                counted += 1
    assert counted == 3, (
        f"{counted} of this module's own patterns are shaped like SQL, not 3. The declaration's "
        "number is stale -- re-read it before changing this test")


# --------------------------------------------------------- U03b · every hole left is accounted for

# ⛔ TWO CATEGORIES RETIRED 2026-10-04. `not-a-table` had one member and it was misfiled;
# `resolvable-deferred` had four (plus two the measurement found) and `3.1b`'s loop hop
# closed every one. ⛔ An empty category makes every assertion over it vacuous -- the hole
# that let a mutation survive in `1.4` -- so neither is kept for symmetry.
CATEGORIES = {"runtime"}


def _open_holes() -> dict[str, tuple[str, ...]]:
    """⛔⛔ THE MODULE'S OWN ANSWER, NOT A SECOND IMPLEMENTATION OF IT.

    This helper used to re-derive the exclusions beside `resolution()`'s copy, and cache them. ⛔
    When `3.1b` added the loop hop the metric stopped counting nine holes and **this copy did
    not**, so the guard went on asserting that declared sites still held holes the metric had
    already closed. *Two implementations of one question will disagree on the day one of them is
    right.* `table_coverage.open_table_holes()` is now the single answer and both read it — which
    also removes the cache this file was keeping, and with it the poisoning hazard the first
    version introduced.
    """
    return dict(TC.open_table_holes())


def test_no_table_hole_is_undeclared():
    """⛔⛔ Backward, and the direction that matters. ✅ `context/merge.py` and
    `feedback/store.py` count as declared through `NAME_CONSTANT_TABLE_SITES`."""
    accounted = set(TC.TABLE_HOLES_NOT_CLOSED) | set(TC.NAME_CONSTANT_TABLE_SITES)
    undeclared = sorted(set(_open_holes()) - accounted)
    assert not undeclared, (
        f"modules with a table-position hole and no declaration: {undeclared}. Give each one a "
        "category -- resolved-elsewhere, resolvable-deferred, runtime or not-a-table -- or close "
        "the hole")


def test_every_declared_site_still_has_a_hole():
    """Forward: a declaration that outlived its hole sends the next reader after nothing."""
    open_now = _open_holes()
    stale = sorted(s for s in TC.TABLE_HOLES_NOT_CLOSED if s not in open_now)
    assert not stale, f"declared sites whose hole has closed: {stale}"


def test_every_entry_is_categorised_and_carries_a_house_form_mover():
    for site, (category, why, mover) in TC.TABLE_HOLES_NOT_CLOSED.items():
        assert category in CATEGORIES, f"{site}: {category!r}"
        assert mover.startswith(("MOVES WHEN", "MOVES WITH")), f"{site}: {mover[:40]!r}"
        # ⛔ FOUND BY THIS TEST FAILING ON A CORRECT ENTRY. The first version was
        # `any(tok in why for tok in ("for ", "{", "information_schema", "parameter"))` — an OR
        # over a hand-listed set, case-sensitive, which rejected an entry saying "FUNCTION
        # PARAMETER". `2.1` produced the rule that such a list is not a check, and `2.2` wrote one
        # anyway; this is the third time. The derived form: a reason has to QUOTE CODE, which the
        # house style spells with backticks, and a reader can then go and look at it.
        assert why.count("`") >= 2, (
            f"{site}'s reason quotes no code. A category without the construct beside it is an "
            "opinion, and the next reader cannot check it")


# ⛔ `test_the_deferred_ones_say_they_are_resolvable_and_name_their_unit` was DELETED
# 2026-10-04 with the `resolvable-deferred` category it guarded: `3.1b` closed every
# member. ⛔ A test over an empty set passes vacuously, which is worse than no test --
# it reads as coverage. Deleted deliberately rather than left green.


def test_the_runtime_ones_say_why_they_cannot_be_known():
    for site, (category, why, _mover) in TC.TABLE_HOLES_NOT_CLOSED.items():
        if category != "runtime":
            continue
        # ⛔⛔ THE SIXTH TIME AN `or` OVER A HAND-LISTED TOKEN SET HAS FAILED IN THIS PROGRAMME,
        # and the second time in this very file. `3.2` added a `runtime` entry saying "REGEX
        # MATCH" — a perfectly good reason that was not on the list, so a correct entry was
        # rejected. ⛔ A list of allowed phrasings is a list somebody has to keep, which is the
        # thing every declaration table here exists to avoid.
        #
        # ✅ DERIVED INSTEAD: a `runtime` entry has to quote CODE that is actually in the module it
        # is about. A reader can then go and look at it, and no phrasing is privileged.
        quoted = re.findall(r"`([^`]+)`", why)
        assert quoted, f"{site}: the reason quotes no code"
        source = (TC._ROOT / ("genios_engine/" + site if not site.startswith("scripts/")
                              else site)).read_text(encoding="utf-8")
        # ⛔ MATCHED ON THE IDENTIFIER, NOT THE WHOLE FRAGMENT. A first version demanded the
        # quoted text verbatim and rejected `_weekly(conn, org, table: str, …)` — an honest
        # citation written with an ellipsis. ⛔ A derived check that is too strict rejects a true
        # statement, which is the mirror of a token list that is too loose: both replace reading
        # with a rule, and both are wrong in one direction.
        idents = {re.match(r"[A-Za-z_][A-Za-z_0-9.]*", q.lstrip("{")).group(0)
                  for q in quoted if re.match(r"[A-Za-z_]", q.lstrip("{"))}
        found = [i for i in idents if i.split(".")[-1] in source]
        assert found, (
            f"{site}: its reason quotes {sorted(idents)[:3]} and none of them appear in the "
            "module. A citation that does not resolve reads as a measurement and is not one")


def test_the_erasure_loop_needs_no_entry_now_and_its_own_reader_still_works():
    """⛔ RE-WRITTEN 2026-10-04. The entry said `resolved-elsewhere` -- `deletion_list()` reads
    `_ORG_SCOPED_TABLES` off the AST, so the generic resolver leaving the hole open cost nothing.
    `3.1b`'s loop hop closes that hole outright, so the entry is retired.

    ✅ But `deletion_list()` is still the only thing that answers *which* tables tenant erasure
    names, so it is asserted here rather than dropped with the entry.
    """
    assert "api/account_routes.py" not in TC.TABLE_HOLES_NOT_CLOSED, (
        "the erasure loop's hole is open again -- re-read whether the loop hop still resolves "
        "`_ORG_SCOPED_TABLES` before re-adding a declaration")
    assert len(TC.deletion_list()) >= 100, (
        "`deletion_list()` no longer reads the erasure loop's constant")


def test_the_connector_hole_is_the_one_with_a_validator_beside_it():
    """⛔ A different risk class from every other entry, and the entry has to say so."""
    category, why, _mover = TC.TABLE_HOLES_NOT_CLOSED["capture/connectors/database.py"]
    assert category == "runtime"
    # ⛔ FOUND BY A SURVIVING MUTATION, AND IT IS THE FOURTH TIME AN `or` HAS DONE THIS. Removing
    # the claim that a validator runs first left `unsafe` standing in the quoted message, and the
    # disjunction passed. BOTH halves are the evidence: that a check runs, and what it says.
    assert "validator" in why, f"the entry no longer claims a check runs first: {why[:80]!r}"
    assert "unsafe" in why, "the entry no longer quotes the validator's own message"
    source = (TC._ROOT / "genios_engine" / "capture" / "connectors" / "database.py") \
        .read_text(encoding="utf-8")
    assert "unsafe" in source, (
        "the identifier validator this entry credits is gone -- that changes the risk class")


# ------------------------------------------------------------------------------ U04 · the ratchet

def test_the_table_hole_count_cannot_grow_silently():
    """⛔⛔ THE RATCHET THE PLAN ASKED FOR. The old guard was `unresolved / statements <= 0.30`
    against an actual 22.4% -- about 220 statements of headroom -- which is why 639 became 645 with
    nothing noticing.

    ⛔ RAISING THIS CEILING IS A DECISION, NOT A FIX. If a hole is genuinely new and genuinely
    unresolvable, declare it in `TABLE_HOLES_NOT_CLOSED` with a category and then raise the number
    in the same change, so both appear in one diff.
    """
    ceiling, why = TC.RESOLUTION_CEILINGS["unresolved_table"]
    assert RESOLUTION["unresolved_table"] <= ceiling, (
        f"{RESOLUTION['unresolved_table']} table-position holes against a ceiling of {ceiling}. "
        f"{why}")


def test_the_ceiling_is_absolute_and_not_a_share():
    """⛔ A share is what failed. 16 is small enough that +1 is visible."""
    ceiling, _why = TC.RESOLUTION_CEILINGS["unresolved_table"]
    assert isinstance(ceiling, int) and ceiling < 100, ceiling


def test_the_ceiling_is_not_slack():
    """⛔ A ceiling far above the actual is the old failure wearing a new number."""
    ceiling, _why = TC.RESOLUTION_CEILINGS["unresolved_table"]
    assert ceiling - RESOLUTION["unresolved_table"] <= 2, (
        f"ceiling {ceiling} against an actual {RESOLUTION['unresolved_table']} is slack, and "
        "slack is exactly how the number grew unnoticed")


def test_the_fragment_count_is_deliberately_NOT_ratcheted():
    """⛔ Fragments are predicates and column lists assembled from shared constants. Ratcheting
    them would fail the build for an ordinary refactor that extracts a `where` clause."""
    assert "unresolved_fragment" not in TC.RESOLUTION_CEILINGS


def test_the_resolver_still_reads_what_it_used_to():
    """*A resolver that answers for 1 of 104 answers nothing* — so a DROP fails the build.

    ⛔⛔ FOUND BY A SURVIVING MUTATION, AND IT WAS A REAL HOLE. The first version asserted only
    `statements >= STATEMENT_FLOOR` — and the floor IS the constant, so **lowering the constant
    weakened the test**. Dropping it to 100 passed. A threshold a test reads from the thing it is
    guarding is not a threshold; it is a variable with a confident name.

    The same shape as the ratchet this step was built to fix, which asserted a 30% share against a
    22.4% actual. ⛔ *A ceiling with slack is not a ratchet* — and a floor that moves with its own
    assertion is not a floor.
    """
    assert TC.STATEMENT_FLOOR >= 2_500, (
        f"STATEMENT_FLOOR is {TC.STATEMENT_FLOOR}, which is not a floor under a codebase with "
        f"{RESOLUTION['statements']} SQL statements. Lowering it hides a resolver regression -- "
        "if the engine genuinely shrank, say so in a diff that changes both this and the floor")
    assert RESOLUTION["statements"] >= TC.STATEMENT_FLOOR, RESOLUTION


# ----------------------------------------- the findings the resolver change did NOT move, pinned

def test_the_resolver_change_moved_no_coverage_verdict():
    """⛔⛔ THE OBSERVER ALTERING WHAT IT MEASURES, GUARDED. Three resolver hops recovered 16
    (table, file) attributions and changed **no** verdict, because every affected table already had
    a visible reference. ⛔ That was luck, not design -- a table referenced ONLY through an imported
    constant would have been reported write-only, which is the bug the module says it has already
    paid for three times.

    These are pinned at their measured values so a future resolver change cannot move them quietly.
    """
    assert sorted(TC.written_and_unread()) == [
        "agent_metering", "card_feedback_revisions", "contract_spend_attributions",
        "delivery_rate_windows", "domain_requests", "human_events", "learning_metrics",
        "situation_interpretations", "warm_lane_slots"], (
        "⛔ RE-PINNED 2026-10-04 by `3.1b`. The COUNT is still 9 and the MEMBERS turned over: "
        "`source_identity_map` left, because the loop hop made `context/merge.py`'s read visible; "
        "`warm_lane_slots` arrived, because the read-verb fix stopped its own `delete from` "
        "reading as a read. ⛔ A count that holds while its membership changes is exactly what a "
        "baseline comparison is for, and exactly what a bare count would have hidden")
    assert TC.undeclared_unread_writes() == ()
    assert TC.stale_unread_declarations() == ()
    # ⛔ RE-PINNED 186 → 187 on 2026-10-05 by the `origin/harsh/mvp` merge (YC-II W27 STEP-00):
    # `signal_bundles` gained its first reference — the tenant reset's `delete` list
    # (`api/account_routes.py`, `50c50073`). An engine change, not a resolver change; the nine
    # write-only members above did not move.
    assert len(TC.table_usage()) == 187
    assert len(TC._known_tables()) == 189
