r"""`U4` · a birthday in 2056 gave three people a cadence baseline they should not have.

⛔ THE FINDING THIS UNIT STARTED FROM WAS WRONG, AND THE FIX IT PROPOSED WOULD HAVE DESTROYED
CORRECT DATA. `03-FINDINGS.md` F9 said: *"`source_events.occurred_at` max = 2056-04-20 — a date 30
years in the future in a production column … It is one row shaped like a parser escape. The bound
is the unit; the row is the symptom."*

Measured 2026-10-01:

    future-dated rows        37, not one
    source / object_type     gcal / calendar_event, every one
    the far ones             2051-04-20 · 2052-04-20 · 2053-04-20 · 2054-04-20 · 2055 · 2056
    captured_at              all 2026-09-19 06:15:11, within milliseconds
    captured_at in future    0
    outcome                  'emitted' on all 37 — already processed

⛔ **An annual recurring calendar event, expanded into yearly instances.** `occurred_at` for a
calendar event is WHEN THE MEETING HAPPENS, so a future value is **correct**, and a bound at
ingest would truncate or reject legitimate calendar data — which is precisely what a calendar
connector must not do. **F9 is retracted.**

⛔ AND THE RETRACTION FOUND A REAL DEFECT ONE LAYER OVER. Three of the four readers that order by
this column already bound it — `capture/esqe/baseline_reader._HISTORY_SQL`,
`context/correlation_timeline._CLAIMS_SQL` and `context/correlation_dependency._CLAIMS_SQL` all
carry `occurred_at <= :until`. `reason/baselines.build_baselines` did not.

⛔ AND THE COST IS NOT WHAT IT LOOKS LIKE. The obvious worry is magnitude — a 30-year gap wrecking
a median. **Measured: it does not.** `anisha@vaultex.in` has 697 events of which 30 are future,
and her median gap is identical either way, because 667 real gaps drown them. **Zero of 222
baselines change value.**

The real cost is at the `MIN_SAMPLES` boundary:

    person                 all  past  future   computed(all)  computed(past)
    aditi@noveum.ai          4     3       1        True          False      ⛔ FLIPS
    asmit@supymem.com        4     3       1        True          False      ⛔ FLIPS
    tejas@tryclean.ai        4     3       1        True          False      ⛔ FLIPS

Three real events is below `MIN_SAMPLES` and must be `cold_start` — *"we do not know this person's
rhythm yet"*. Four crosses it, so each of the three was given a **computed** `reply_cadence` from a
gap set ending in a future year, and `cold_start` stopped being true about them. Downstream, *"this
relationship is going cold"* was judged against that number instead of the honest default.

⛔ MY FIRST MEASUREMENT MISSED THIS. It compared medians and skipped every person whose past-only
sample fell below `MIN_SAMPLES` — which is **exactly the affected population**. A comparison that
skips the cases where the answer changes KIND, rather than value, reports zero and means nothing.

> ⛔ **A statistic can be unchanged while the verdict flips.** 0 of 222 medians moved; 3 of 222
> people stopped being cold-start.

## Living log

    2026-10-01   37 future rows, all gcal calendar_event, all correct
                 0 of 222 median baselines change · 3 of 222 flip cold_start -> computed
"""
from __future__ import annotations

import ast
import inspect
import textwrap
from datetime import datetime, timedelta, timezone

from genios_engine.reason import baselines as B

NOW = datetime(2026, 10, 1, tzinfo=timezone.utc)


def _sql_literals(function) -> list[str]:
    """Each SQL string literal in `function`, from the AST — never from its source text.

    ⛔ TWO REASONS IT IS THE AST. First, this file's sibling unit (U3) shipped an assertion that
    read `inspect.getsource` as text and failed on its own docstring; the comment block inside
    `build_baselines` explains the bound at length and names the column, so a text read would find
    `occurred_at <= :until` in the PROSE and pass with the bound removed from the query. Second,
    adjacent string literals are concatenated by the parser, so one query arrives as one constant
    — which is what makes it possible to ask a question about ONE query rather than about all of
    them at once.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(function)))
    body = tree.body[0]
    assert isinstance(body, ast.FunctionDef)
    docstring = (body.body[0].value if body.body and isinstance(body.body[0], ast.Expr)
                 and isinstance(body.body[0].value, ast.Constant) else None)
    return [" ".join(node.value.split()) for node in ast.walk(body)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
            and node is not docstring]


def _history_read(function) -> str:
    """⛔ THE ONE QUERY THIS FILE IS ABOUT — the person-history read over `source_events`.

    `build_baselines` issues several statements, and one of them legitimately writes
    `computed_at=now()`: that is when the baseline ROW was written, not a cutoff for the
    measurement. The first draft of this file asserted "no `now()` in the function's SQL" and
    failed on exactly that — an over-broad assertion is a false alarm waiting to be silenced by
    weakening it. Scoped to the read instead.
    """
    reads = [sql for sql in _sql_literals(function)
             if "from source_events" in sql and "occurred_at" in sql]
    assert len(reads) == 1, (
        f"expected exactly one read over `source_events.occurred_at` here, found {len(reads)} — "
        "a second one would need its own bound and its own assertion")
    return reads[0]


# ══ the bound ════════════════════════════════════════════════════════════════════

def test_the_history_read_is_bounded_at_eval_time() -> None:
    """⛔ THE FIX. A baseline is a statement about the past; the read is what must say so."""
    sql = _history_read(B.build_baselines)
    assert "occurred_at <= :until" in sql, (
        "the person-history read must bound `occurred_at` at `eval_time`. Unbounded, a recurring "
        "calendar event decades out counts as a communication event — and three people crossed "
        "MIN_SAMPLES on one such row")


def test_the_bound_is_eval_time_and_not_a_clock_read() -> None:
    """`eval_time` is already this function's parameter. ⛔ A `now()` here would make a replay of a
    September sweep use October's cutoff, which is the doctrine `eval_time` exists for."""
    sql = _history_read(B.build_baselines)
    assert "now()" not in sql, (
        "⛔ the bound must be the passed-in `eval_time`, never a clock read in SQL — otherwise a "
        "replay silently re-bounds itself. Note this is scoped to the READ: the write that "
        "records `computed_at=now()` is a row timestamp and is correct")
    source = textwrap.dedent(inspect.getsource(B.build_baselines))
    assert '"until": eval_time' in source, "the parameter must be bound to `eval_time`"


def test_it_matches_what_its_three_sibling_readers_already_do() -> None:
    """⛔ NOT A NEW CONCEPT — a missing one. Three other reads over this column carry the same
    bound; this was the outlier. Pinned so a later edit to any of the four is visibly inconsistent
    with the rest."""
    from genios_engine.capture.esqe import baseline_reader
    from genios_engine.context import correlation_dependency, correlation_timeline

    siblings = {
        "capture.esqe.baseline_reader._HISTORY_SQL": baseline_reader._HISTORY_SQL,
        "context.correlation_timeline._CLAIMS_SQL": correlation_timeline._CLAIMS_SQL,
        "context.correlation_dependency._CLAIMS_SQL": correlation_dependency._CLAIMS_SQL,
    }
    for name, sql in siblings.items():
        assert "occurred_at <= :until" in " ".join(sql.split()), (
            f"{name} lost its bound — the four reads over `source_events.occurred_at` must agree "
            "that a backward-looking question is bounded backwards")


# ══ the behaviour, at the boundary that actually mattered ════════════════════════

def test_a_future_event_does_not_push_a_person_over_MIN_SAMPLES() -> None:
    """⛔ THE MEASURED DEFECT, AS A TEST. Three real events and one future calendar instance.

    Three is below `MIN_SAMPLES` and must stay `cold_start`. This asserts on the arithmetic the
    function performs rather than through the database, because the claim is about which branch
    a sample count selects — and that is a pure property of the filtered list.
    """
    real = [NOW - timedelta(days=d) for d in (30, 20, 10)]
    birthday = NOW + timedelta(days=365 * 25)
    everything = sorted([*real, birthday])

    assert len(everything) > B.MIN_SAMPLES, "unbounded, four samples cross the threshold"
    bounded = [t for t in everything if t <= NOW]
    assert len(bounded) == 3
    assert not len(bounded) > B.MIN_SAMPLES, (
        "⛔ bounded, three samples stay BELOW the threshold — so the person stays cold_start, "
        "which is the honest answer for somebody with three events")


def test_a_person_with_plenty_of_history_was_never_distorted_by_magnitude() -> None:
    """⛔ THE WORRY THAT TURNED OUT TO BE WRONG, kept as a test so it is not re-raised.

    The intuition was that a 30-year gap destroys a median. It does not: `statistics.median` over
    667 real gaps plus 30 yearly ones is unmoved, which is why **0 of 222 baselines changed
    value**. The defect was never magnitude; it was sample count at the threshold.
    """
    import statistics

    real = [NOW - timedelta(days=d) for d in range(60, 0, -1)]          # 60 daily events
    future = [NOW + timedelta(days=365 * y) for y in range(25, 31)]     # 6 yearly instances

    def median_gap(times: list[datetime]) -> float:
        ordered = sorted(times)
        gaps = [(ordered[i + 1] - ordered[i]).total_seconds() / 86_400.0
                for i in range(len(ordered) - 1)]
        return statistics.median(gaps)

    assert median_gap(real) == median_gap([*real, *future]), (
        "a handful of distant events does not move a median over dozens of close ones — which is "
        "why the magnitude argument failed and the threshold argument held")


def test_min_samples_is_the_threshold_this_turns_on() -> None:
    """A literal, so a change to `MIN_SAMPLES` is visibly a change to who gets a baseline."""
    assert B.MIN_SAMPLES == 3
