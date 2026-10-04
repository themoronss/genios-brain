"""The checks that would have gone red while 14,624 hermetic tests were green.

    pytest tests/scripts/test_the_gate_that_runs_on_real_data.py -q

⛔ WHY THIS FILE AND THE SCRIPT IT GUARDS EXIST. On 2026-10-04 the hermetic suite reported
**14,624 passed, 0 failed** while production was carrying, at the same moment:

    4,076  LLM calls rejected outright (`temperature` deprecated for the model)
       19  calls truncated at max_tokens and filed as "unparseable JSON"
      160  emitted events with no `route` — extraction never ran on one of them
       85  parked attachments whose stored error was 400 characters of id and no reason
        9  cards the pipeline selected and the claim refused, 0 of 9, silently
      255  messages dropped by a whitelist that could not know anybody on a cold graph

Not one test went red, because every test runs against a FAKE LLM and FAKE data. A fake client
never returns a 400, never hits `max_tokens`, never leaves a row half-written. The suite asserts
that the code does what the code says. It has never asserted that the product works.

`scripts/pipeline_health.py` is the other half: read-only, against a real database, failing on the
shapes that were actually true. On its FIRST run against production it failed three checks — two
already known, and one nobody had isolated: `l4_bundle`, 8 failures out of 12, every one at
exactly 1400 output tokens, which is its ceiling to the token.

⛔ THIS FILE IS NOT A SECOND COPY OF THOSE CHECKS. It asserts the things a hermetic test can
honestly assert about them: that the script cannot write, that each known failure mode still has a
check, and that every check tells the reader what to do. The checks themselves are only true
against real data, which is the entire point.
"""

from __future__ import annotations

import ast
import inspect
import textwrap

import pytest

from scripts import pipeline_health as ph

pytestmark = pytest.mark.unit


def _all_checks():
    return list(ph.CHECKS) + [ph.check_llm_failure_rate, ph.check_no_silent_truncation]


def test_every_failure_mode_from_that_day_still_has_a_check():
    """⛔ THE MUTATION THIS FILE REJECTS: quietly dropping a check once its bug is fixed. Each of
    these was live in production while the suite was green, and a gate that only covers today's
    outage is a gate that goes stale by tomorrow."""
    names = {fn.__name__ for fn in _all_checks()}
    for required in ("check_every_emitted_event_is_routed",
                     "check_llm_failure_rate",
                     "check_no_silent_truncation",
                     "check_parked_errors_are_readable",
                     "check_the_known_sender_set_is_not_empty",
                     "check_a_selected_signal_can_be_carded",
                     "check_cards_reach_the_app"):
        assert required in names, f"{required} was removed from the gate"


def test_the_gate_cannot_write():
    """⛔ A health check pointed at production is exactly the kind of "harmless" tool that ends up
    writing. `set transaction read only` is issued by `_gate.read_only_connection` as the FIRST
    statement, so the server refuses — not a reviewer."""
    tree = ast.parse(inspect.getsource(ph))
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "read_only_connection" in called, "the gate opens a connection some other way"

    # ⛔ ON THE STATEMENTS, NOT ON THE FILE. The first version of this test scanned the whole
    # source for "update " and went red on the word UPDATE inside a `fix=` sentence — the
    # blunt-grep failure this repo names by hand. What matters is what is HANDED TO `sql()`.
    statements = [arg.value.lower()
                  for node in ast.walk(tree)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                  and node.func.id == "sql"
                  for arg in node.args
                  if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]
    assert statements, "no SQL literal reached `sql()` — re-point this test"
    for statement in statements:
        assert statement.lstrip().startswith("select"), (
            f"a non-SELECT statement reached the gate: {statement[:70]!r}")


def test_the_target_database_is_never_implicit():
    """`scripts/_db` exists because a script that defaults to `Settings.database_url` is a script
    that silently opens production on every developer machine."""
    source = inspect.getsource(ph)
    assert "resolve_database_url" in source
    assert "get_settings" not in source, "the gate resolves its own target again"


@pytest.mark.parametrize("fn", _all_checks(), ids=lambda f: f.__name__)
def test_every_check_says_what_to_do(fn):
    """⛔ A check whose failure does not name the next move is a check somebody learns to ignore.
    `expected` says what good looks like; `fix` says where to go."""
    source = textwrap.dedent(inspect.getsource(fn))
    assert "expected=" in source, f"{fn.__name__} does not say what it expected"
    assert "fix=" in source, f"{fn.__name__} does not say what to do about a failure"
    assert fn.__doc__ and "⛔" in fn.__doc__, (
        f"{fn.__name__} does not record the production shape it was written for")


@pytest.mark.parametrize("fn", _all_checks(), ids=lambda f: f.__name__)
def test_every_check_is_scoped_to_one_tenant(fn):
    """A gate that reads across tenants would fail one customer's deploy on another's data."""
    source = textwrap.dedent(inspect.getsource(fn))
    assert "org_id = :o" in source or "org_id=:o" in source, (
        f"{fn.__name__} reads without an org filter")


def test_a_failing_check_exits_non_zero():
    """The gate has to be usable as a gate. A script that prints a failure and exits 0 is a
    report, and reports are what we already had."""
    source = textwrap.dedent(inspect.getsource(ph.main))
    assert "return 1 if failed else 0" in source


def test_a_check_result_carries_its_own_evidence():
    """`measured` is printed on PASS as well as FAIL: a number nobody sees while it is healthy is
    a number nobody notices drifting."""
    check = ph.Check(name="n", ok=True, measured="m", expected="e", fix="f")
    assert check.measured == "m" and check.detail == []
    source = textwrap.dedent(inspect.getsource(ph.main))
    assert "measured:" in source
    assert source.index("measured:") < source.index("if not c.ok:"), (
        "`measured` is only printed on failure — a healthy number that nobody reads cannot be "
        "seen to drift")
