"""⛔⛔ STEP 3.1b · the fourth resolver hop — and the pre-existing bug it amplified 102-fold.

`3.1` deferred this hop in writing: *"a fourth resolver hop with a 102-table blast radius is its
own unit with its own baseline."* Doing it found two things larger than the hop.

⛔⛔ **`delete from X` WAS COUNTED AS A READ OF X.** `_VERBS["read"]` was `(?:from|join) (…)` and
`delete from cards` contains `from cards`. Latent for as long as the module has existed; the loop
hop amplified it a hundredfold, because `api/account_routes.py`'s erasure loop runs
`delete from {tbl}` over 102 tables. ⛔ **Four tables stopped being reported write-only on the
strength of it**, and the baseline comparison this step committed to in writing is the only reason
that was caught before four correct declarations were retired.

⛔ **And the naive implementation of the hop was wrong.** Expanding each loop statement into one
per table inflates `statements` 2,885 → 3,036 and makes `unresolved` **rise** — a real improvement
reading as a regression, on a number the share assertion divides by. So the loop map feeds
attribution only.

```
unresolved_table    16 → 7      ceiling re-ratcheted, slack 0
statements           2,885      ✅ unchanged, and that is the measured decision
written_and_unread   9 → 9      ⛔ SAME COUNT, MEMBERS TURNED OVER
```
"""

from __future__ import annotations

import ast
import re

from genios_engine.platform import table_coverage as TC


def _const(name: str) -> str:
    return getattr(TC, name)


# ------------------------------------------------------- U02b · a delete is not a read

def test_a_delete_is_not_counted_as_a_read():
    """⛔⛔ THE BUG. `delete from cards` must attribute a delete and nothing else."""
    sql = "delete from cards where org_id=:o"
    hits = {verb: re.findall(pattern, sql) for verb, pattern in TC._VERBS.items()
            if re.findall(pattern, sql)}
    assert hits == {"delete": ["cards"]}, hits


def test_a_real_read_is_still_a_read():
    sql = "select 1 from cards where org_id=:o"
    assert re.findall(TC._VERBS["read"], sql) == ["cards"]
    assert re.findall(TC._VERBS["read"], "select 1 from a join cards on a.id=cards.id") \
        == ["a", "cards"]


def test_a_subquerys_from_inside_a_delete_IS_still_a_read():
    """⛔ The lookbehind must block only the `from` immediately after `delete `. A reader nested in
    a delete's predicate is a genuine read, and losing it would trade one mis-attribution for
    another."""
    sql = "delete from a where x in (select 1 from b)"
    hits = {verb: re.findall(pattern, sql) for verb, pattern in TC._VERBS.items()
            if re.findall(pattern, sql)}
    assert hits == {"delete": ["a"], "read": ["b"]}, hits


def test_the_lookbehind_is_in_the_pattern_and_not_only_in_its_effect():
    """⛔ By source: a future refactor that reproduced the effect another way is fine, but one that
    deleted the guard and happened to pass these three cases is not."""
    assert "(?<!delete )" in TC._VERBS["read"], TC._VERBS["read"]


def test_the_fix_is_explained_where_the_pattern_is():
    source = (TC._ROOT / "genios_engine" / "platform" / "table_coverage.py") \
        .read_text(encoding="utf-8")
    assert "load-bearing" in source.split('"read": rf')[0].rsplit("_VERBS", 1)[-1] \
        or "`(?<!delete )`" in source, (
        "the lookbehind carries no explanation at the pattern; the next person to simplify it has "
        "nothing to read")


# --------------------------------------------------------------- U02a · the loop hop and its bounds

def _loops(src: str) -> dict[str, tuple[str, ...]]:
    return TC._loop_table_targets(src, TC._known_tables())


def test_a_loop_over_literal_table_names_resolves():
    assert _loops('for t in ("cards", "signals"):\n    q = f"select 1 from {t}"\n') \
        == {"t": ("cards", "signals")}


def test_a_loop_over_a_module_constant_resolves():
    assert _loops('TABLES = ("cards", "signals")\nfor t in TABLES:\n    pass\n') \
        == {"t": ("cards", "signals")}


def test_a_loop_over_an_IMPORTED_constant_resolves_through_the_earlier_hops():
    """⛔ One hop for the loop, and the iterable itself resolves through the three hops `3.1`
    built. No further."""
    src = ("from genios_engine.api.account_routes import _ORG_SCOPED_TABLES\n"
           "for tbl in _ORG_SCOPED_TABLES:\n    pass\n")
    got = _loops(src)
    assert "tbl" in got and len(got["tbl"]) >= 100, {k: len(v) for k, v in got.items()}


def test_a_MIXED_collection_answers_for_NOTHING():
    """⛔⛔ ALL OR NOTHING, and it is the most important bound. A collection holding one name we do
    not recognise is as likely to be columns, statuses or file names — and half-resolving it would
    attribute real tables out of a list that happens to share a word with one."""
    assert _loops('for t in ("cards", "not_a_table_at_all"):\n    pass\n') == {}
    assert _loops('for t in ("status", "cards"):\n    pass\n') == {}


def test_an_empty_collection_answers_for_nothing():
    """⛔ An empty iterable makes the loop vacuous -- the `1.4` hole, in a new place."""
    assert _loops("for t in ():\n    pass\n") == {}
    assert _loops("for t in []:\n    pass\n") == {}


def test_a_non_literal_element_is_refused_even_beside_literals():
    """⛔ `("cards", SOMETHING)` has two elements and one literal; counting the literal would be
    answering for a collection we cannot see all of."""
    assert _loops('X = "signals"\nfor t in ("cards", X):\n    pass\n') == {}


def test_the_FIRST_element_of_a_tuple_target_resolves_and_the_second_does_not():
    """⛔ `for table, when in _LEDGERS` — which position holds the table is not knowable from the
    shape, so only the first is taken and the second is never guessed.

    ⛔⛔ FOUND BY A SURVIVING MUTATION, AND THE TEST'S OWN NAME WAS THE FALSE WITNESS. The first
    version of this test asserted a `zip(...)` case and a plain `Name` case — **it never tested a
    tuple target at all**, so guessing the second element passed it. The name said `tuple target`
    and the body did not contain one. *Assert the thing the name claims.*
    """
    src = ('PAIRS = (("cards", "created_at"), ("signals", "at"))\n'
           'for table, when in PAIRS:\n'
           '    q = f"select 1 from {table} order by {when}"\n')
    got = _loops(src)
    assert "table" in got, got
    assert got["table"] == ("cards", "signals"), got
    assert "when" not in got, (
        "the SECOND element of the tuple target resolved. Which position holds the table is not "
        "knowable from the shape, so taking both attributes `created_at` and `at` as tables the "
        "moment either happens to match a real name")


def test_zip_stays_out_of_bounds():
    """⛔ A separate test, because the one above used to carry this case and hide the gap."""
    assert _loops('P = ("cards", "signals")\nfor a, b in zip(P, P):\n    pass\n') == {}


def test_a_plain_name_target_over_a_constant_resolves():
    assert _loops('P = ("cards", "signals")\nfor a in P:\n    pass\n') \
        == {"a": ("cards", "signals")}


def test_a_comprehension_resolves_and_a_while_does_not():
    assert _loops('q = [f"select 1 from {t}" for t in ("cards",)]\n') == {"t": ("cards",)}
    assert _loops('t = "cards"\nwhile t:\n    break\n') == {}


def test_enumerate_and_dict_items_are_out_of_bounds():
    """⛔ Declared bounds, tested so they stay bounds rather than becoming an oversight."""
    assert _loops('P = ("cards",)\nfor i, t in enumerate(P):\n    pass\n') == {}
    assert _loops('D = {"cards": 1}\nfor k, v in D.items():\n    pass\n') == {}


# --------------------------------------------- U02a · the statement count is the measured decision

def test_the_statement_count_did_NOT_move():
    """⛔⛔ THE WHOLE DESIGN. Measured before building: the naive expansion takes `statements`
    2,885 → 3,036 and makes `unresolved` RISE from 621 to 631, because expanding one statement
    into five leaves five each still carrying the other holes.

    `statements` is the denominator of the share assertion and a number
    `scripts/context_coverage_report.py` prints. ⛔ A number other things read does not change
    meaning for a resolver improvement.
    """
    r = TC.resolution()
    assert r["statements"] == 2_910, (
        f"`statements` is {r['statements']}. If the engine genuinely gained SQL, say so in a diff "
        "that moves this number deliberately -- but if the loop hop started expanding the "
        "statement LIST, that is the design this unit measured and rejected")
    # ⛔ MOVED 2,885 → 2,888 by `3.2`, deliberately: `receipts.witness_sql` and
    # `WITNESS_EXCEPTIONS` add three real SQL statements to the engine. That is the engine gaining
    # SQL, which is ordinary; what this test exists to catch is the loop hop EXPANDING the
    # statement list, which would have added 151 at once.
    # ⛔ MOVED 2,888 → 2,902 on 2026-10-05, deliberately, by the `origin/harsh/mvp` merge
    # (YC-II W27 STEP-00). Measured per file on a pre-merge archive and on the merge: +2
    # `api/routes.py` (the known-sender read from the sent folder, `48768ca7`, two statements by
    # design), +1 `platform/warm_lane.py` (the lapsed-plan gate, `7075014c`), +11
    # `scripts/pipeline_health.py` (`5ebfef8e`). Fourteen real statements; the loop hop expanded
    # nothing.
    # ⛔ MOVED 2,902 → 2,908 the same day by `scripts/workstream_funnel.py` (STEP-00's baseline
    # probe): six SELECTs, each a literal at its own `sql()` call site.
    # ⛔ MOVED 2,908 → 2,910 by yc2_w27/M17.C2.U02 (STEP-18 B20/B18):
    # `capture/screen/fingerprint._without_set_aside_claims` reads which claiming events were set
    # aside and deletes their claims — one SELECT, one DELETE, both literals at their own call.


def test_the_loop_hop_closed_nine_table_holes_and_moved_them_to_the_fragment_bucket():
    """⛔ Measured, not asserted: 16 → 7 table holes, and the nine still carry `{column}`-shaped
    holes, so they move buckets rather than disappearing."""
    r = TC.resolution()
    # ⛔ 7 → 8 by `3.2`: `witness_sql` derives a table from a regex over another receipt's SQL,
    # which is a genuinely runtime name. Declared in `TABLE_HOLES_NOT_CLOSED` and the ceiling was
    # raised in the same diff. ✅ The ratchet caught its own author.
    assert r["unresolved_table"] == 8, r
    assert r["unresolved_table"] + r["unresolved_fragment"] == r["unresolved"]


# ----------------------------------------------------------- U03 · the two declarations that moved

def test_the_stale_declaration_was_retired_and_says_who_retired_it():
    """⛔ `source_identity_map` was declared write-only and `context/merge.py` has always read it,
    inside the loop this hop resolves."""
    assert "source_identity_map" not in TC.UNREAD_WRITES
    reason = TC.RETRACTED_UNREAD_WRITES["source_identity_map"]
    assert "3.1b" in reason and "merge.py" in reason
    assert sorted(f.replace("genios_engine/", "")
                  for f in TC.readers_of("source_identity_map")) == ["context/merge.py"]


def test_the_newly_visible_write_only_table_is_declared():
    """⛔⛔ `warm_lane_slots` was HIDDEN BY ITS OWN DELETE: `platform/warm_lane.py` deletes its own
    rows, and `delete from` read as a read, so the table looked read by its writer."""
    assert "warm_lane_slots" in TC.UNREAD_WRITES
    writer, why, mover = TC.UNREAD_WRITES["warm_lane_slots"]
    assert writer == "platform/warm_lane.py"
    assert TC.readers_of("warm_lane_slots") == frozenset()
    assert "returning" in why.lower() and "rowcount" in why.lower(), (
        "the entry must record HOW the state is read -- through `returning` and `rowcount`, which "
        "no verb pattern here can express. Without that it reads as a gap rather than a design")


def test_the_lease_table_is_graded_by_design_and_not_as_a_gap():
    """⛔ Its mover must say never. A `select` over a lease table is a race: the answer is stale
    before the caller acts on it, which is why the claim is a conditional write."""
    _w, why, mover = TC.UNREAD_WRITES["warm_lane_slots"]
    assert "BY DESIGN" in why
    assert mover.startswith("MOVES WHEN never"), mover


def test_the_declarations_are_clean_in_both_directions():
    assert TC.undeclared_unread_writes() == ()
    assert TC.stale_unread_declarations() == ()


def test_the_write_only_count_held_while_its_MEMBERSHIP_turned_over():
    """⛔⛔ THE FINDING A BARE COUNT WOULD HAVE HIDDEN. Nine before, nine after — and one left and
    one arrived. A step that reported only the count would have reported *no change*."""
    now = set(TC.written_and_unread())
    assert len(now) == 9, sorted(now)
    assert "source_identity_map" not in now
    assert "warm_lane_slots" in now


# ---------------------------------------------- U01 · two categories retired, and a misfiled entry

def test_both_emptied_categories_are_gone():
    """⛔ An empty category makes every assertion over it vacuous -- the `1.4` hole. `not-a-table`
    had one misfiled member and `resolvable-deferred` had its whole membership closed."""
    categories = {category for category, _why, _mover in TC.TABLE_HOLES_NOT_CLOSED.values()}
    assert categories == {"runtime"}, sorted(categories)


def test_the_misfiled_entry_is_gone_and_the_correction_is_recorded_somewhere():
    """⛔ `3.1` filed `scripts/rebuild_graph.py` as `not-a-table`, describing a `create table`
    statement that was never counted. The counted one was a plain `delete` of eight real tables."""
    assert "scripts/rebuild_graph.py" not in TC.TABLE_HOLES_NOT_CLOSED
    source = (TC._ROOT / "genios_engine" / "platform" / "table_coverage.py") \
        .read_text(encoding="utf-8")
    assert "RETIRED 2026-10-04" in source, (
        "the retired categories carry no record of why; a reader finding `runtime` alone cannot "
        "tell a deliberate retirement from a category nobody thought of")


def test_only_the_three_runtime_sites_remain_and_each_is_genuinely_unknowable():
    # ⛔ FOUR now, not three: `3.2` added `platform/receipts.py`, where `witness_sql` derives a
    # table from a regex over another receipt's SQL. ✅ The ratchet caught its own author and the
    # ceiling moved 7 → 8 in the same diff, which is what its message demands.
    expected = {"api/home_routes.py", "capture/connectors/database.py",
                "platform/receipts.py", "scripts/wipe_org_data.py"}
    assert set(TC.TABLE_HOLES_NOT_CLOSED) == expected, sorted(TC.TABLE_HOLES_NOT_CLOSED)


# ---------------------------------------------------------------------------- U04 · the ratchet

def test_the_ceiling_TRACKS_the_actual_in_both_directions():
    """⛔ A ceiling only ratchets while it sits on the actual. Leaving it at 16 after the hop took
    the figure to 7 would be nine statements of headroom -- the exact failure `3.1` fixed.

    ⛔ RENAMED 2026-10-04. This was `test_the_ceiling_came_DOWN_with_the_actual`, and then `3.2`
    raised it 7 → 8 for a declared reason — so the name asserted a direction the code no longer
    had. *Assert the thing the name claims*, which is that the ceiling TRACKS the actual, either
    way. ⛔ `3.1b`'s mutations produced that rule from a test whose name promised a tuple target
    and whose body had none; this is the same rule applied to a name that aged.
    """
    ceiling, why = TC.RESOLUTION_CEILINGS["unresolved_table"]
    assert TC.resolution()["unresolved_table"] == ceiling, (
        f"ceiling {ceiling} against an actual {TC.resolution()['unresolved_table']}. Any gap is "
        "headroom, and headroom is how the number grew unnoticed before `3.1`")
    assert "FOUR resolver hops" in why
    assert "RAISED 7 → 8" in why, (
        "a ceiling that moved without saying why is a number somebody edited to go green")


# ------------------------------------------------- the redundancy this hop created, measured

def test_merges_name_constant_declaration_is_now_redundant_and_that_is_known():
    """⛔ Measured: removing `context/merge.py` from `NAME_CONSTANT_TABLE_SITES` loses **zero**
    facts, because the loop hop provides everything it did and the `read` verb it missed.

    ✅ It is KEPT, because its prose states something a generic resolver does not — that merge
    repoints every node reference — and this test exists so a future reader meets the redundancy
    as a measured fact rather than discovering it as dead code. ⛔ If the hop ever stops providing
    those facts, the declaration becomes load-bearing again and this test fails, which is the
    notification wanted.
    """
    assert "context/merge.py" in TC.NAME_CONSTANT_TABLE_SITES

    def snapshot() -> dict[str, dict[str, frozenset[str]]]:
        for fn in (TC._table_usage, TC._exported_table_constants, TC.resolution,
                   TC.open_table_holes):
            fn.cache_clear()
        return {t: {v: frozenset(f) for v, f in d.items()} for t, d in TC.table_usage().items()}

    whole = snapshot()
    original = dict(TC.NAME_CONSTANT_TABLE_SITES)
    try:
        TC.NAME_CONSTANT_TABLE_SITES = {k: v for k, v in original.items()
                                        if k != "context/merge.py"}
        without = snapshot()
    finally:
        TC.NAME_CONSTANT_TABLE_SITES = original
        for fn in (TC._table_usage, TC._exported_table_constants, TC.resolution,
                   TC.open_table_holes):
            fn.cache_clear()

    unique = {t: sorted(v for v, files in verbs.items()
                        if files - without.get(t, {}).get(v, frozenset()))
              for t, verbs in whole.items()}
    unique = {t: v for t, v in unique.items() if v}
    assert unique == {}, (
        f"`context/merge.py`'s name-constant declaration is load-bearing again for {unique}. The "
        "loop hop has stopped providing those facts -- find out why before trusting either")
