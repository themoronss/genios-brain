"""The per-workstream funnel: what a hermetic test can honestly assert about it.

    pytest tests/scripts/test_workstream_funnel.py -q

⛔ WHY. `scripts/workstream_funnel.py` is the baseline every step of `speedrun008/YC-II W27/` is
measured against — on 2026-10-05, 365 inbound mails and 27 of them reaching reasoning. A baseline
that can write, that reads across tenants, that quietly drops a mail nobody grouped, or that counts
one mail in two columns would make every later "it moved" claim worthless. Its numbers are only
true against real data; this file asserts the properties that make them trustworthy.
"""
from __future__ import annotations

import ast
import inspect
import itertools
import json

import pytest

from scripts import workstream_funnel as wf

pytestmark = pytest.mark.unit


def _sql_literals() -> list[str]:
    tree = ast.parse(inspect.getsource(wf))
    return [arg.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "sql"
            for arg in node.args
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str)]


def test_the_probe_cannot_write():
    """⛔ On the statements handed to `sql()`, not on the file — a blunt grep would go red on the
    word "update" in a docstring and green on a write built elsewhere."""
    tree = ast.parse(inspect.getsource(wf))
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "read_only_connection" in called, "the probe opens a connection some other way"
    statements = _sql_literals()
    assert len(statements) >= 6, f"expected every query as a literal at its call site, found {len(statements)}"
    for statement in statements:
        assert statement.lstrip().lower().startswith("select"), (
            f"a non-SELECT statement reached the probe: {statement[:70]!r}")


def test_no_statement_is_built_out_of_sight():
    """Every `sql(...)` call is handed a literal. A statement passed by name would escape the
    read-only check above — the exact hole the first draft of this module had."""
    tree = ast.parse(inspect.getsource(wf))
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "sql":
            assert node.args and isinstance(node.args[0], ast.Constant), (
                f"sql() at line {node.lineno} is handed something other than a literal")


def test_every_statement_is_scoped_to_one_tenant():
    """A baseline that reads across tenants measures somebody else's mailbox."""
    for statement in _sql_literals():
        assert "org_id = :o" in statement, f"a statement reads without the org filter: {statement[:70]!r}"


def test_the_target_database_is_never_implicit():
    source = inspect.getsource(wf)
    assert "resolve_database_url" in source
    assert "get_settings" not in source, "the probe resolves its own target again"


def test_no_address_lives_in_the_module():
    """⛔ The grouping is the tenant's knowledge. A sender or domain written into this module is
    one tenant's data shipped to every tenant — and a grouping nobody can change without a deploy."""
    tree = ast.parse(inspect.getsource(wf))
    docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                  if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
                  and n.body and isinstance(n.body[0], ast.Expr)
                  and isinstance(n.body[0].value, ast.Constant)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            assert "@" not in node.value, f"an address is written into the module: {node.value[:60]!r}"
    assert wf.group_of("someone@titancapital.vc", ()) == wf.OTHER, "the module groups without a file"


def _groups(tmp_path, payload) -> tuple:
    path = tmp_path / "groups.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return wf.load_groups(path)


def test_the_first_matching_group_wins_and_nothing_is_dropped(tmp_path):
    groups = _groups(tmp_path, {"groups": [
        {"name": "investors", "patterns": [r"\.vc$", r"@insightpartners\.com$"]},
        {"name": "everything", "patterns": [r".*"]}]})
    assert wf.group_of("manik@titancapital.vc", groups) == "investors"
    assert wf.group_of("x@insightpartners.com", groups) == "investors"
    assert wf.group_of("x@example.org", groups) == "everything"
    narrow = _groups(tmp_path, {"groups": [{"name": "investors", "patterns": [r"\.vc$"]}]})
    assert wf.group_of("x@example.org", narrow) == wf.OTHER
    assert wf.group_of("", narrow) == wf.OTHER


@pytest.mark.parametrize("payload", [
    {},
    {"groups": []},
    {"groups": [{"name": "a", "patterns": ["x"]}, {"name": "a", "patterns": ["y"]}]},
    {"groups": [{"name": "other", "patterns": ["x"]}]},
    {"groups": [{"name": "a", "patterns": []}]},
    {"groups": [{"name": "a", "patterns": ["("]}]},
], ids=["no-key", "empty", "duplicate", "reserved", "no-patterns", "bad-regex"])
def test_a_bad_groups_file_is_refused(tmp_path, payload):
    with pytest.raises(ValueError):
        _groups(tmp_path, payload)


def test_every_mail_lands_in_exactly_one_column():
    """Total and exclusive: every combination of facts yields exactly one known fate."""
    for outcome, active, extracted, junked, content in itertools.product(
            ("emitted", "dropped", "parked", "archived"), (True, False), (True, False), (True, False),
            (True, False)):
        fate = wf.fate_of(outcome=outcome, active_signal=active, extracted=extracted,
                          junked=junked, has_content=content)
        assert fate in wf.FATES


def test_the_fates_are_tested_in_the_documented_order():
    """The column a mail lands in is decided by the strongest fact it carries."""
    f = wf.fate_of
    assert f(outcome="parked", active_signal=True, extracted=True, junked=True, has_content=True) == "parked"
    assert f(outcome="emitted", active_signal=True, extracted=True, junked=True, has_content=True) == "reached_reasoning"
    assert f(outcome="emitted", active_signal=False, extracted=True, junked=True, has_content=True) == "read_no_signal"
    assert f(outcome="archived", active_signal=False, extracted=False, junked=True, has_content=True) == "archived"
    assert f(outcome="emitted", active_signal=False, extracted=False, junked=True, has_content=False) == "junked"
    assert f(outcome="dropped", active_signal=False, extracted=False, junked=False, has_content=False) == "deleted"
    assert f(outcome="emitted", active_signal=False, extracted=False, junked=False, has_content=True) == "kept_unread"


def test_a_groups_columns_add_up_to_its_mails(tmp_path):
    groups = _groups(tmp_path, {"groups": [{"name": "investors", "patterns": [r"\.vc$"]}]})
    rows = [
        {"sender": "a@x.vc", "outcome": "dropped", "active_signal": False, "extracted": False,
         "junked": False, "has_content": False},
        {"sender": "b@x.vc", "outcome": "emitted", "active_signal": False, "extracted": False,
         "junked": True, "has_content": True},
        {"sender": "c@x.vc", "outcome": "emitted", "active_signal": True, "extracted": True,
         "junked": False, "has_content": True},
        {"sender": "d@elsewhere.org", "outcome": "emitted", "active_signal": False,
         "extracted": True, "junked": False, "has_content": True},
    ]
    table = wf.tally(rows, groups)
    assert [r.name for r in table] == ["investors", wf.OTHER]
    for row in table:
        assert sum(row.fates.values()) == row.mails
    assert sum(r.mails for r in table) == len(rows), "a mail was lost between the rows and the table"
    investors = table[0]
    assert (investors.fates["deleted"], investors.fates["junked"],
            investors.fates["reached_reasoning"]) == (1, 1, 1)


def test_an_archived_mail_is_counted_apart_with_the_rule_that_archived_it(tmp_path):
    """STEP-03 (`yc2_w27_s03/M21.C4.L-interface.V4.U05`): the gate archives what it used to delete.
    Counted as `kept_unread` it would hide among the bulk-header short circuits, and counted as
    `deleted` it would be a lie — so it has its own column, and the rule that archived it."""
    groups = _groups(tmp_path, {"groups": [{"name": "boardy", "patterns": [r"@boardy\.test$"]}]})
    base = {"active_signal": False, "extracted": False, "junked": False, "has_content": True}
    rows = [
        {**base, "sender": "intros@boardy.test", "outcome": "archived", "rule": "N-02"},
        {**base, "sender": "intros@boardy.test", "outcome": "archived", "rule": "N-02"},
        {**base, "sender": "hello@boardy.test", "outcome": "archived", "rule": "llm_junk",
         "junked": True},
        {**base, "sender": "old@boardy.test", "outcome": "dropped", "rule": None,
         "has_content": False},
    ]
    boardy = wf.tally(rows, groups)[0]
    assert (boardy.mails, boardy.fates["archived"], boardy.fates["deleted"]) == (4, 3, 1)
    assert boardy.archived_by_rule == {"N-02": 2, "llm_junk": 1}
    assert sum(boardy.fates.values()) == boardy.mails


def test_the_probe_reads_the_rule_off_the_ledger_row():
    """The rule is `source_events.attention_reason` — what the gate wrote — not re-derived here."""
    inbound = next(s for s in _sql_literals() if "from source_events se" in s)
    assert "se.attention_reason" in inbound
