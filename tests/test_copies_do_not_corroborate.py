"""L3-05 · corroboration counts SYSTEMS, not messages — and the word doing that was untested.

`reason/engine` turns `src_count` into a rung: one:60 / two:85 / three+:100. The difference between
`count(distinct sr.source)` and `count(sr.source)` is therefore the difference between "two systems
agree" and "somebody forwarded an email twice" — and until this file existed the `distinct` was a
keyword in TWO copies of a hand-written subquery that no test drove. Every test in the suite
supplies `src_count` as a literal, so deleting the word would have pushed every fact to the top
rung with nothing failing anywhere.
"""
from __future__ import annotations

import inspect
import re

from genios_engine.reason import engine as reason_engine
from genios_engine.reason import runner as reason_runner


# =================================================================================================
# 1 · ⛔ THE DENOMINATOR COUNTS DISTINCT SOURCES
# =================================================================================================

def test_the_corroboration_denominator_is_distinct_sources():
    """⛔ The whole protection is one word. Ten forwards of one email are ten `graph_source_refs`
    rows carrying the same `source`; `distinct` is what collapses them to one system."""
    sql = reason_runner._SRC_COUNT_SUBQUERY
    assert "count(distinct sr.source)" in sql, (
        "src_count no longer counts DISTINCT sources — ten copies of one message would now read as "
        "ten systems agreeing and every fact would sit on the top corroboration rung")
    assert re.search(r"count\(\s*sr\.source\s*\)", sql) is None


def test_it_counts_over_fact_id_not_fact_version_id():
    """Corroboration accumulates across the VERSIONS of one fact. Counting per version would reset
    it every time a value was superseded, so a second system confirming an already-superseded value
    would read as the only voice in the room."""
    sql = reason_runner._SRC_COUNT_SUBQUERY
    assert "fv.fact_id=f.fact_id" in sql
    assert "sr.fact_version_id=f.fact_version_id" not in sql


def test_the_subquery_has_exactly_one_home():
    """⛔ IT HAD TWO, AND NEITHER WAS PINNED. That is L3-04's `_WINDOW_AT` /
    `FACT_WINDOW_AT` shape — one predicate living in two readers — except that one had a pin
    holding the copies together and this had neither a pin nor a single home. One copy losing the
    word would have silently disagreed with the other about how much a fact is believed.

    ⛔ AND THIS ASSERTION COUNTS CODE, NOT PROSE. Its first draft counted the string anywhere in
    the module and went red at 3 — because the constant's own explanation and the declared-silence
    note beside it both name the SQL they are explaining. That is the seventh occurrence of one
    family in this project (L1-14, L1-18, L2-6, L3-00, L3-02b, L3-04, here) and it is always the
    same shape: an assertion about text rather than about the thing the text describes. Comment
    lines are stripped before counting.
    """
    src = inspect.getsource(reason_runner)
    code = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    literal = code.count("count(distinct sr.source)")
    assert literal == 1, (
        f"the subquery text appears in code {literal} times; it must exist once, in "
        "_SRC_COUNT_SUBQUERY, and be referenced by every reader")
    assert code.count("+ _SRC_COUNT_SUBQUERY +") >= 2, "both readers must use the constant"


# =================================================================================================
# 2 · ⛔ THE RUNGS ARE WHAT MAKES THE WORD LOAD-BEARING
# =================================================================================================

def test_the_ladder_still_has_three_rungs_and_they_still_climb():
    """If these collapse, the `distinct` stops mattering and this whole file is decoration. Read
    from the engine's source so a change to the defaults is visible here."""
    src = inspect.getsource(reason_engine)
    assert 'corr_cfg.get("three_plus", 100)' in src
    assert 'corr_cfg.get("two", 85)' in src
    assert 'corr_cfg.get("one", 60)' in src


def test_a_high_authority_rank_can_reach_the_top_rung_without_corroboration():
    """Deliberate, and worth pinning so it is not read as a bug later: a rank-3+ source (a system
    of record) is trusted alone. That is a statement about AUTHORITY, not about agreement, and it
    is the one path to 100% that copies cannot fake — a forwarded email does not change its rank."""
    src = inspect.getsource(reason_engine)
    assert 'int(trig.get("authority_rank") or 1) >= 3' in src


# =================================================================================================
# 3 · ⛔ WHAT IS STILL NOT PROTECTED, DECLARED RATHER THAN DISCOVERED
# =================================================================================================

def test_cross_channel_lineage_is_declared_unprotected():
    """⛔ THE RESIDUAL HOLE, NAMED SO IT IS NOT MISTAKEN FOR A SOLVED PROBLEM.

    `distinct sr.source` collapses copies WITHIN one channel. It does not collapse one original
    assertion quoted ACROSS channels — CC-27's "a Slack discussion quotes the original email and a
    meeting summary quotes the Slack discussion" is three distinct sources and one lineage, and it
    would reach the top rung.

    `graph_source_refs.independence_group` is the column for that, and it is populated only for the
    narrow screen/email same-message case (`capture/screen/fingerprint`), not for general quoting.

    IT IS NOT BUILT HERE ON PURPOSE: a two-connector tenant cannot produce the case, and building a
    lineage system for an unreachable failure is the over-scaffolding this plan refuses — the same
    reason L3-01 declined to build `DecisionRef`. THE MOVER IS the third connector.
    """
    assert reason_runner.LINEAGE_UNPROTECTED, "the residual hole must stay declared"
    reason, mover = reason_runner.LINEAGE_UNPROTECTED["cross_channel_quote"]
    assert "independence_group" in reason
    assert mover, "a declared silence without a mover is a silence nobody will ever end"
