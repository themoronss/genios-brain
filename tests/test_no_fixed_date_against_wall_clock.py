"""GeniOS-011 S04.U3 · no test seeds a fixed calendar date and reads the wall clock beside it.

    .venv/bin/python -m pytest -q tests/test_no_fixed_date_against_wall_clock.py

WHY THIS TEST EXISTS (audit item `process-python-and-calendar-time-bombs`). Twice in four days a test
that had passed for weeks went red on every commit, with no change to the code it tested:

  * 14 Oct (e3dd389b). `tests/test_p10_nudges.py` seeded one follow-up at `_ist(2026, 9, 14, 11)` —
    the day the test was written — and the rest at `now - timedelta(hours=2)`, with
    `now = datetime.now(timezone.utc)`. The profile reads `now - seat_profile.WINDOW` (30 days). At
    11:00 IST on 14 Oct the fixed seed left the window and Priya counted 1, not 2.
  * 17 Oct (aaba9bf2, 125c90c2). `tests/test_llm_cost_attribution.py` wrote its spend at a fixed
    20 Sep and `top_spending_seats(days=30)` read its window from the wall clock; on 17 Oct the
    oldest row fell out (0.75 != 1.0) and CI's database job went red.

The shape is the same both times: a date that never moves, measured against a clock that always
does. A DISTANCE between them ("inside the last 30 days") is true on the day the test is written and
false some day after, and nothing about the commit that turns it red is wrong.

THE RULE, read from the AST. In one test function (everything nested inside it included), a literal
calendar date may not appear beside a wall-clock read:

  * a LITERAL DATE is a call whose first three arguments are integer constants shaped like a year,
    a month and a day (`datetime(2026, 9, 14)`, `date(2026, 9, 14)`, and a module's own helper —
    `_ist(2026, 9, 14, 11)` is how the 14 Oct one was written); `fromisoformat` / `strptime` of a
    constant ISO string; a string constant that is exactly an ISO date or instant; or a module-level
    name bound to any of those (`NOW = datetime(2026, 9, 20, …)` is how the 17 Oct one was written);
  * a WALL-CLOCK READ is `datetime.now()`, `datetime.utcnow()`, `datetime.today()`, `date.today()`,
    `time.time()` — resolved through the module's imports, as `tests/test_no_test_reads_the_clock_at_
    import.py` resolves them, and with that file's own `_imports` / `_dotted` so the two guards agree
    on what a name means — or SQL text that reads the database's clock (`now()`, `current_date`,
    `current_timestamp`, …). `time.monotonic()` and `time.perf_counter()` are NOT wall-clock reads
    here: they measure a duration inside the test, and no calendar date is ever compared with one.

A docstring is prose, never a read: "no `now()` is being read" is not SQL.

WHAT IT CANNOT SEE, measured on 2026-10-23 and declared rather than guessed. The 17 Oct shape had no
clock read in the TEST at all — the window lived inside `top_spending_seats`. Following each call a
test makes into `genios_engine/` and flagging the ones whose product function reads the clock
flagged 85 test functions, almost all of them a product stamping `created_at = now()` that no
assertion ever measures against the fixed date. A guard that red is read as noise, so this one stays
on the side it can be exact about. The same measurement, one step nearer: following the module's
OWN helpers from each test adds 13 functions when the dates are followed (message `ts` payloads,
filler for an `orgs` row's required columns), 15 when the clock is (fixtures and seeders stamping
`created_at = now()`), and 43 with both — against the 10 the rule finds in the test's own body. Of
the added ones, the date lines of 8 were read on 2026-10-23 (and the retention test of
`tests/test_device_api_pg.py` in full): payload timestamps and filler, none measured against the
clock. The other ones are unread, so this is a declared gap, not a clearance. The guard reads the
test's own body, and `test_a_helper_is_read_on_its_own` pins that boundary.

The rule for a test author is the same either way: seed relative to the instant the product is
handed (`now - timedelta(days=3)`), or hand the product the fixed instant itself (`now=NOW`,
`eval_time=NOW`, or pin its `_now`) — never a fixed date and the wall clock together.

THE DECLARED LIST. `DECLARED` is every test function the rule flags today, each with a dated reason
it is not a time bomb — and the reason is always one of two kinds: the wall clock is compared with
the fixed date only by ORDER ("after"), which a clock moving forward can never flip, or the two never
meet in any comparison at all. A distance between them would be a bomb, and is fixed, not listed.
The list must equal what the scan finds in BOTH directions: a new offender is red, and an entry
that no longer offends is red too, so the list can only shrink when the code does.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from tests.test_no_test_reads_the_clock_at_import import _dotted
from tests.test_no_test_reads_the_clock_at_import import _imports

pytestmark = pytest.mark.unit

TESTS = Path(__file__).resolve().parent
ROOT = TESTS.parent

#: The wall-clock reads, by their full name once the module's imports are resolved. No
#: `monotonic` / `perf_counter`: a duration is measured against itself, never against a date.
WALL_CLOCK_READS = frozenset({
    "datetime.datetime.now", "datetime.datetime.utcnow", "datetime.datetime.today",
    "datetime.date.today", "time.time", "time.time_ns"})
#: A bare call by one of these names that no import binds is still the clock: `time()`.
BARE_WALL_CLOCK_NAMES = frozenset({"time", "time_ns"})
#: Owners nothing in the module imports, read by name as the import-time guard reads them — so
#: `clock.now()` on a fake, or `self.today()`, is not the wall clock.
WALL_CLOCK_CALLS = frozenset({"now", "utcnow", "today", "time", "time_ns"})
CLOCK_OWNERS = frozenset({"datetime", "date", "time", "dt"})

#: SQL that reads the database's clock — and the keyword that says the string IS SQL, so a
#: parametrize id or a log message that says "now()" is not taken for a query.
SQL_CLOCK = re.compile(
    r"\b(?:now|clock_timestamp|statement_timestamp|transaction_timestamp)\s*\(\s*\)"
    r"|\bcurrent_(?:date|timestamp)\b|\blocaltimestamp\b", re.I)
SQL_KEYWORD = re.compile(r"\b(?:select|insert|update|delete|where|values|interval|set)\b", re.I)

#: A string that is exactly a calendar date or instant: "2026-09-14", "2026-09-14T11:00:00Z".
ISO_DATE = re.compile(
    r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?")
ISO_PARSERS = frozenset({"fromisoformat", "strptime"})


# ── the two halves of the rule ────────────────────────────────────────────────────────────────
def _is_date_shaped(args: list[ast.expr]) -> bool:
    """The first three positional arguments are integer constants shaped like a year, a month and
    a day — `datetime(2026, 9, 14)`, and any helper written the same way (`_ist(2026, 9, 14, 11)`)."""
    if len(args) < 3:
        return False
    values = []
    for arg in args[:3]:
        if not (isinstance(arg, ast.Constant) and type(arg.value) is int):
            return False
        values.append(arg.value)
    year, month, day = values
    return 1900 <= year <= 2200 and 1 <= month <= 12 and 1 <= day <= 31


def _is_literal_date(node: ast.AST, docstrings: set[int]) -> bool:
    if isinstance(node, ast.Call):
        if _is_date_shaped(node.args):
            return True
        func = node.func
        return (isinstance(func, ast.Attribute) and func.attr in ISO_PARSERS and bool(node.args)
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)
                and ISO_DATE.match(node.args[0].value) is not None)
    return (isinstance(node, ast.Constant) and isinstance(node.value, str)
            and id(node) not in docstrings and ISO_DATE.fullmatch(node.value) is not None)


def _is_wall_clock_read(node: ast.AST, names: dict[str, set[str]], docstrings: set[int]) -> bool:
    if isinstance(node, ast.Constant):
        return (isinstance(node.value, str) and id(node) not in docstrings
                and SQL_CLOCK.search(node.value) is not None
                and SQL_KEYWORD.search(node.value) is not None)
    if not isinstance(node, ast.Call):
        return False
    resolved = _dotted(node.func, names)
    if resolved is None:
        return False
    full, bound = resolved
    if full & WALL_CLOCK_READS:
        return True
    if bound:
        return False
    if isinstance(node.func, ast.Name):
        return node.func.id in BARE_WALL_CLOCK_NAMES
    if node.func.attr not in WALL_CLOCK_CALLS:
        return False
    owner = node.func.value
    while isinstance(owner, ast.Attribute):      # datetime.datetime.now
        if owner.attr in CLOCK_OWNERS:
            return True
        owner = owner.value
    return isinstance(owner, ast.Name) and owner.id in CLOCK_OWNERS


# ── what a test function reaches ──────────────────────────────────────────────────────────────
def _docstrings(tree: ast.Module) -> set[int]:
    """The ids of every docstring constant: prose, never a date seed and never a query."""
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                found.add(id(body[0].value))
    return found


def _module_literal_dates(tree: ast.Module, docstrings: set[int]) -> set[str]:
    """Module-level names bound to a literal date — directly (`NOW = datetime(2026, 9, 20)`) or
    through another such name (`WROTE = tuple(NOW - timedelta(days=d) for d in …)`), in the order
    the module binds them."""
    found: set[str] = set()
    for stmt in tree.body:
        if isinstance(stmt, ast.Assign):
            targets, value = stmt.targets, stmt.value
        elif isinstance(stmt, ast.AnnAssign) and stmt.value is not None:
            targets, value = [stmt.target], stmt.value
        else:
            continue
        if any(_is_literal_date(n, docstrings)
               or (isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id in found)
               for n in ast.walk(value)):
            for target in targets:
                for n in ast.walk(target):
                    if isinstance(n, ast.Name):
                        found.add(n.id)
    return found


def _test_scopes(tree: ast.Module):
    """`(qualified name, node)` for every module-level function and every method of a module-level
    class — the units a test runs, each read with everything nested inside it."""
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node.name, node
        elif isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    yield f"{node.name}.{item.name}", item


def fixed_dates_beside_the_wall_clock(source: str) -> dict[str, tuple[int, int]]:
    """{test function: (line of its first literal date, line of its first wall-clock read)} for
    every function of `source` that has both."""
    tree = ast.parse(source)
    names = _imports(tree)
    docstrings = _docstrings(tree)
    module_dates = _module_literal_dates(tree, docstrings)
    found: dict[str, tuple[int, int]] = {}
    for qualname, func in _test_scopes(tree):
        date_lines, clock_lines = [], []
        for node in ast.walk(func):
            line = getattr(node, "lineno", 0)
            if _is_literal_date(node, docstrings) or (
                    isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
                    and node.id in module_dates):
                date_lines.append(line)
            if _is_wall_clock_read(node, names, docstrings):
                clock_lines.append(line)
        if date_lines and clock_lines:
            found[qualname] = (min(date_lines), min(clock_lines))
    return found


def _scan_the_tree() -> dict[str, tuple[int, int]]:
    found: dict[str, tuple[int, int]] = {}
    for path in sorted(TESTS.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        for qualname, lines in fixed_dates_beside_the_wall_clock(
                path.read_text(encoding="utf-8")).items():
            found[f"{rel}::{qualname}"] = lines
    return found


# ── the declared list: every function the rule flags today, and why it is not a time bomb ───────
# Measured 2026-10-23 on g011 (ae33b10c). ORDER = the wall clock is compared with the fixed date only
# as "after", which a clock moving forward cannot flip. APART = the two never meet in a comparison.
DECLARED: dict[str, str] = {
    "tests/capture/acquire/test_scheduler.py::test_postgres_cursor_round_trips_the_last_success_timestamp":
        "2026-10-23 · APART: the fixed NOW (14 Jan 2026) is only the cursor's watermark, which "
        "`catchup.plan_catch_up` resumes from as it is (`since = watermark`, no lookback clamp); the "
        "24 h gap is measured between the database's own `now()` and the row it back-dated with "
        "`now() - interval '24 hours'`.",
    "tests/capture/connectors/test_backfill_window.py::test_widening_the_backfill_window_lands_history_without_duplicating_it":
        "2026-10-23 · APART: '2026-09-01T00:00:00Z' / '2026-09-04…' are `content_version` labels "
        "compared only with each other (two versions land); every message age is relative to "
        "`datetime.now()`.",
    "tests/context/analytic/test_peer_baseline.py::test_the_baselines_route_reads_the_table_the_drain_writes":
        "2026-10-23 · APART: '2026-03-11T09:00:00' is a NAIVE instant sent to prove the route refuses "
        "it (422); the seed, the sweep and `as_of` are all the test's own `now`.",
    "tests/context/test_point_in_time.py::timeline":
        "2026-10-23 · APART: in this fixture JANUARY / FEBRUARY are only written as `occurred_at`; "
        "t0..t3 are read from the transaction clock (`select now()`) and asserted only against each "
        "other (`t0 < t1 < t2 < t3`).",
    "tests/reason/l2/test_the_l2_pass_pg.py::test_a_met_need_reasons_the_subject_again_once":
        "2026-10-23 · ORDER: the need's `closed_at = now()` is read as `closed_at > since` "
        "(`l2/evidence.py`), where `since` is the watermark the first pass wrote from bundles seeded "
        "at the fixed NOW (18 Oct 2026); the wall clock is after NOW and stays after.",
    "tests/reason/l2/test_the_l2_pass_pg.py::test_the_shadow_report_reads_what_the_pass_kept":
        "2026-10-23 · ORDER: `report(days=36500)` reads from `datetime.now() - 100 years`; the pass's "
        "rows at the fixed NOW (18 Oct 2026) stay inside it until 2126.",
    "tests/reason/test_a_defer_keeps_the_card.py::test_a_shadow_pack_still_keeps_nothing_alive":
        "2026-10-23 · APART: `tenant_packs.updated_at = now()` is bookkeeping for the shadow flip; the "
        "run is handed `eval_time=NOW + 6h` and nothing reads `updated_at` against it.",
    "tests/test_account_contact_metrics.py::test_the_account_query_finds_companies_on_the_real_graph":
        "2026-10-23 · APART: `now()` stamps `valid_from` on the seeded nodes and edges; "
        "`baselines._account_rows` filters on `valid_to is null` only, and the contact times are "
        "`NOW - days`, measured against the same NOW.",
    "tests/test_deal_node_from_correspondence.py::test_the_backfill_reanchors_a_situation_that_was_already_correlated":
        "2026-10-23 · ORDER: `valid_to = now()` closes the deal nodes after the fixed NOW (1 Aug 2026) "
        "and stays after it; the backfill and the refresh are handed `eval_time=NOW` (the 45-day "
        "dormancy this test once tripped on is read from NOW, not the wall clock).",
    "tests/test_deal_node_from_correspondence.py::test_the_incremental_path_alone_cannot_correct_an_anchor":
        "2026-10-23 · ORDER: `valid_to = now()` closes the deal nodes after the fixed NOW (1 Aug 2026) "
        "and stays after it; every refresh is handed `eval_time=NOW`.",
}

#: A declared reason starts with the day it was measured and says which of the two kinds it is.
_REASON = re.compile(r"\d{4}-\d{2}-\d{2} · (?:ORDER|APART): \S")


# ── the guard's own tests: each shape, on samples built to have it ─────────────────────────────
def test_the_14_oct_shape_is_caught():
    """e3dd389b's own lines: a module helper called with a fixed date, beside `datetime.now()`."""
    sample = (
        "from datetime import datetime, timedelta, timezone\n"
        "IST = timezone(timedelta(hours=5, minutes=30))\n"
        "def _ist(y, m, d, h, mi=0):\n"
        "    return datetime(y, m, d, h, mi, tzinfo=IST).astimezone(timezone.utc)\n"
        "def test_the_weekly_profile(client):\n"
        "    now = datetime.now(timezone.utc)\n"                                       # 6
        "    rows = [{'cr': _ist(2026, 9, 14, 11) if i == 0 else now - timedelta(hours=2)}\n"  # 7
        "            for i in range(2)]\n"
        "    assert gather(rows, now=now)\n"
        "def test_relative_is_fine():\n"
        "    now = datetime.now(timezone.utc)\n"
        "    assert gather([now - timedelta(days=3)], now=now)\n")
    assert fixed_dates_beside_the_wall_clock(sample) == {"test_the_weekly_profile": (7, 6)}


def test_a_module_constant_a_string_seed_and_sql_are_each_caught():
    sample = (
        "import datetime as dt\n"
        "import time\n"
        "from datetime import date\n"
        "NOW = dt.datetime(2026, 9, 20, 12, tzinfo=dt.timezone.utc)\n"
        "LATER = NOW + dt.timedelta(days=1)\n"                     # bound through NOW
        "def test_constant_and_now():\n"
        "    assert LATER < dt.datetime.now(dt.timezone.utc)\n"     # 7
        "def test_string_seed_and_sql(c):\n"
        "    c.execute(text(\"insert into t (at) values ('2026-09-14')\"))\n"   # 9 SQL text, not a date constant
        "    c.execute(text('select count(*) from t where at > now() - interval \\'30 days\\''),\n"
        "              {'at': '2026-09-14T11:00:00Z'})\n"           # 11 the seed
        "def test_today_and_iso_parse():\n"
        "    assert date.fromisoformat('2026-09-14') < date.today()\n"   # 13
        "def test_epoch_and_time():\n"
        "    assert date(2026, 9, 14) and time.time()\n"            # 15
        "class TestGrouped:\n"
        "    def test_method(self):\n"
        "        assert dt.date.today() > dt.date(2026, 1, 1)\n")   # 18
    found = fixed_dates_beside_the_wall_clock(sample)
    assert found == {"test_constant_and_now": (7, 7), "test_string_seed_and_sql": (11, 10),
                     "test_today_and_iso_parse": (13, 13), "test_epoch_and_time": (15, 15),
                     "TestGrouped.test_method": (18, 18)}


def test_a_helper_is_read_on_its_own():
    """THE DECLARED BOUNDARY (see the module docstring): a helper is a function of its own, read
    alone; the seed in `_seed()` and the clock in `_clock()` are not added to the test that calls
    both. A helper that has both itself is flagged like any test."""
    sample = (
        "from datetime import datetime, timezone\n"
        "def _seed():\n"
        "    return datetime(2026, 9, 14, tzinfo=timezone.utc)\n"
        "def _clock():\n"
        "    return _deeper()\n"
        "def _deeper():\n"
        "    return datetime.now(timezone.utc)\n"
        "def test_x():\n"
        "    assert _seed() < _clock()\n"
        "def _both():\n"
        "    return datetime(2026, 9, 14) < datetime.now()\n")                 # 11
    assert fixed_dates_beside_the_wall_clock(sample) == {"_both": (11, 11)}


def test_what_is_not_a_time_bomb_is_not_flagged():
    """Durations, fakes, prose, a pinned instant, and a date with no clock beside it."""
    sample = (
        "import time\n"
        "from datetime import datetime, timezone\n"
        "from mylib import now\n"                                  # bound elsewhere: not the clock
        "NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)\n"
        "def test_a_duration():\n"
        "    t0 = time.monotonic()\n"
        "    assert run(now=NOW) and time.monotonic() - t0 < 1 and time.perf_counter()\n"
        "def test_a_fake_clock(clock):\n"
        "    assert clock.now() > NOW and clock.today()\n"
        "def test_prose():\n"
        "    \"\"\"Two instants; no `now()` is read where values are compared.\"\"\"\n"
        "    assert run(eval_time=NOW)\n"
        "def test_a_bound_name():\n"
        "    assert now() and NOW\n"
        "def test_sqlish_words_alone(c):\n"
        "    assert run(NOW, ids=['now()'])\n"                      # not SQL: no keyword
        "def test_only_the_clock():\n"
        "    assert datetime.now(timezone.utc)\n"
        "def test_not_date_shaped():\n"
        "    assert range(2026, 13, 40) and datetime.now(timezone.utc)\n")  # day 40: not a date
    assert fixed_dates_beside_the_wall_clock(sample) == {}


def test_every_declared_reason_is_dated_and_names_its_kind():
    bad = {k: v for k, v in DECLARED.items() if not _REASON.match(v)}
    assert not bad, f"a declared reason must start 'YYYY-MM-DD · ORDER|APART: …': {bad}"


def test_the_guard_parses_on_the_python_ci_runs():
    """CI and production are Python 3.11 (ci.yml, Dockerfile); the local venv is 3.13."""
    ast.parse(Path(__file__).read_text(encoding="utf-8"), feature_version=(3, 11))


# ── the guard ─────────────────────────────────────────────────────────────────────────────────
def test_no_test_seeds_a_fixed_date_beside_the_wall_clock():
    found = _scan_the_tree()
    new = sorted(set(found) - set(DECLARED))
    stale = sorted(set(DECLARED) - set(found))
    assert not new, (
        f"{len(new)} test function(s) seed a fixed calendar date beside a wall-clock read — the "
        "shape that went red on 14 Oct and 17 Oct with no change to the code (GeniOS-011 S04.U3). "
        "Seed relative to the instant you hand the product (`now - timedelta(days=3)`), or hand the "
        "product the fixed instant (`now=NOW`). Only if the clock is compared with the date by "
        "ORDER alone, or never at all, declare it in DECLARED with a dated reason:\n  "
        + "\n  ".join(f"{k}  (date line {found[k][0]}, clock line {found[k][1]})" for k in new))
    assert not stale, (
        "declared but no longer flagged — the code changed, so the list shrinks; delete:\n  "
        + "\n  ".join(stale))
