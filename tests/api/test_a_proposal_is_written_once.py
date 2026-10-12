"""`learning_objects` rows are write-once except for `state` — and nothing guarded that.

⛔ `feedback/publisher.persist` states the contract in its own first line: *"Insert an **immutable**
proposal at `state`."* It keeps it — an existing row is never updated, only reported as
`reevaluated` or `unchanged`, so an object that reached a later state can never be reopened.
Measured 2026-10-03: the engine holds exactly two `update learning_objects` statements and **both
set only `state`**.

⛔⛔ **Nothing asserted any of it.** The day somebody writes `set proposed_value = …` — to "fix" a
bad proposal, which is the obvious thing to want — `semantic_hash` stops describing the row,
`learning_transitions` points at an object that no longer says what it said when the transition was
logged, and *"immutable proposal storage"* becomes a sentence about the past.

⛔ THIS IS A GUARD AND NOT A RECEIPT, DELIBERATELY. The data cannot answer it: a value rewritten in
place leaves no trace unless `semantic_hash` is recomputed, and recomputing it in SQL would mean
reimplementing the canonical serialisation in a second language. *A gate derived from an invented
claim is a gate nobody reads* — the same decision the `context/` audit took for `graph_nodes`.

⛔ AND IT IS `api/`'s FIRST GUARD ABOUT ITS OWN WRITES. The package has 44 files, 19,498 lines and
zero receipts, and one of the two updaters below is `api/learning_routes.py`.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from genios_engine.contracts.learning import LearningState
from genios_engine.platform import table_coverage as TC

_ENGINE = Path(__file__).resolve().parents[2] / "genios_engine"
_TABLE = "learning_objects"
#: The statements that exist, measured. A new one is a finding, not a formatting change.
#: ⛔ MOVED 2 → 3 by yc2_w27_s18/M48.C1.L-data.V0.U02 (STEP-18 B4), read and deliberate:
#: `feedback/publisher._rest_for_review` rests a weekly-sweep object that governance sends to a human
#: at `human_review` — the state the ledger already logged for it, and the one state the review route
#: takes. State only, and only on that road: `persist` still writes nothing to an existing row (the
#: `_Conn` tests below), and the two tests after this one hold where the new statement may live.
_UPDATERS = {"genios_engine/api/learning_routes.py", "genios_engine/feedback/org_rule_ingest.py",
             "genios_engine/feedback/publisher.py"}


# ── the invariant, both directions ─────────────────────────────────────────────────────────────

def test_no_write_once_table_is_updated_outside_its_allowlist():
    illegal = TC.illegal_column_updates()
    assert illegal == (), (
        f"⛔ a write-once table's value column is being updated: {illegal}. Read "
        "`table_coverage.WRITE_ONCE_TABLES` before widening the allowlist — for "
        "`learning_objects` the value columns ARE the proposal, and `semantic_hash` is derived "
        "from them, so rewriting one silently invalidates every transition already logged "
        "against it")


def test_the_updaters_are_exactly_the_ones_that_were_measured():
    assert set(TC.update_columns(_TABLE)) == _UPDATERS, (
        f"the set of modules updating {_TABLE} changed: {sorted(TC.update_columns(_TABLE))}. ⛔ A "
        "third updater is a new authority over the learning ledger and needs reading, even if it "
        "only sets `state`")


@pytest.mark.parametrize("updater", sorted(_UPDATERS))
def test_each_updater_sets_only_state(updater):
    assert TC.update_columns(_TABLE)[updater] == frozenset({"state"})


def test_state_is_the_only_column_the_declaration_allows():
    mutable, why, mover = TC.WRITE_ONCE_TABLES[_TABLE]
    assert mutable == frozenset({"state"})
    assert len(why) > 100
    assert mover.startswith(("MOVES WHEN", "MOVES WITH", "⛔ MOVES"))
    assert "never added by widening this set" in mover, (
        "the mover must say what must NOT happen — widening the set to make a build pass is "
        "exactly how this guard would be defeated")


# ── the producer never rewrites, which is the other half ───────────────────────────────────────

def _publisher_functions_updating_the_proposal_table() -> dict[str, int]:
    """{function name: how many `update learning_objects` statements it holds} in the publisher."""
    tree = ast.parse((_ENGINE / "feedback" / "publisher.py").read_text(encoding="utf-8"))
    out: dict[str, int] = {}
    for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
        found = sum(1 for node in ast.walk(fn)
                    if isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and " ".join(node.value.lower().split()).startswith("update learning_objects"))
        if found:
            out[fn.name] = found
    return out


def test_the_publisher_holds_no_update_of_the_proposal_table_but_the_review_rest():
    """`persist` returns a verdict instead of updating — the half of this guard that has not moved.
    ⛔ RESTATED by yc2_w27_s18/M48.C1.L-data.V0.U02 (STEP-18 B4): it asserted that the publisher holds
    no `update learning_objects` at all. Since B4 it holds exactly one, in `_rest_for_review`, which
    sets `state` alone (`test_each_updater_sets_only_state`) — and none in `persist`, nor anywhere
    else in the module."""
    assert _publisher_functions_updating_the_proposal_table() == {"_rest_for_review": 1}


def test_the_review_rest_runs_only_for_an_object_sent_to_a_human():
    """The one caller of `_rest_for_review` is `publish`, under its `HUMAN_REVIEW` test — a sink that
    needs no human never moves the row through it."""
    tree = ast.parse((_ENGINE / "feedback" / "publisher.py").read_text(encoding="utf-8"))
    publish = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "publish")
    callers = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
               and getattr(n.func, "id", None) == "_rest_for_review"]
    assert len(callers) == 1, "one caller, `publish`"
    guards = [n for n in ast.walk(publish) if isinstance(n, ast.If)
              and any(c is callers[0] for b in n.body for c in ast.walk(b))]
    assert guards and "HUMAN_REVIEW" in ast.unparse(guards[-1].test), (
        "the rest must sit under `if target_state is LearningState.HUMAN_REVIEW`")


class _Conn:
    """A connection double that RECORDS what it was asked to run.

    ⛔ A double that cannot fail the way production fails proves nothing — so this one does not
    merely return rows, it keeps every statement, and the test asserts that the second one never
    happens. A `persist` that quietly rewrote a row would be invisible to a double that only
    checked the return value.
    """

    def __init__(self, existing_state: str | None):
        self.existing_state = existing_state
        self.statements: list[str] = []

    def execute(self, statement, params=None):           # noqa: ARG002 - mirrors SQLAlchemy
        self.statements.append(" ".join(str(statement).lower().split()))
        conn = self

        class _Result:
            def mappings(self):
                return self

            def first(self):
                return ({"state": conn.existing_state}
                        if conn.existing_state is not None else None)

            @property
            def rowcount(self):
                return 1
        return _Result()


@pytest.mark.parametrize("state,verdict", [
    (LearningState.OBSERVED.value, "reevaluated"),
    (LearningState.CANDIDATE.value, "reevaluated"),
    (LearningState.GOVERNED.value, "unchanged"),
    (LearningState.PUBLISHED.value, "unchanged"),
    (LearningState.REJECTED.value, "unchanged"),
])
def test_persist_reports_an_existing_row_and_writes_nothing(state, verdict):
    from datetime import datetime, timezone

    from genios_engine.feedback.publisher import persist

    conn = _Conn(state)
    result = persist(conn, _proposal(), state=LearningState.GOVERNED,
                     at=datetime(2026, 10, 3, tzinfo=timezone.utc))
    assert result == verdict
    assert len(conn.statements) == 1, (
        f"⛔ persist ran {len(conn.statements)} statements against an EXISTING row: "
        f"{conn.statements[1:]}. It must read and report, never write")
    assert conn.statements[0].startswith("select state from learning_objects")


def test_persist_inserts_when_there_is_no_existing_row():
    """The negative half: the guard above must not pass by `persist` never writing at all."""
    from datetime import datetime, timezone

    from genios_engine.feedback.publisher import persist

    conn = _Conn(None)
    assert persist(conn, _proposal(), state=LearningState.GOVERNED,
                   at=datetime(2026, 10, 3, tzinfo=timezone.utc)) == "inserted"
    inserts = [s for s in conn.statements if s.startswith("insert into learning_objects")]
    assert inserts, conn.statements
    assert "update learning_objects" not in " ".join(conn.statements)


def _proposal():
    from datetime import datetime, timezone

    from genios_engine.contracts.learning import (LearningEvidence, LearningObject, LearningTarget,
                                                  Visibility, VisibilityScope)
    now = datetime(2026, 10, 3, tzinfo=timezone.utc)
    return LearningObject(
        org_id="org_1", unit="outcome_analysis", target=LearningTarget.METRICS,
        subject="play:demo", proposed_value={"observations": 3},
        evidence=LearningEvidence(observations=3, independent_refs=3, distinct_days=2,
                                  positive=3, negative=0, confidence_bp=9_000,
                                  business_value_bp=9_000),
        visibility=Visibility(scope=VisibilityScope.ORGANIZATION),
        first_seen_at=now, last_seen_at=now, policy_key="pk_1")


# ── the approval route's own gates, since it is one of the two updaters ─────────────────────────

def test_the_approval_route_locks_the_row_and_refuses_a_wrong_state():
    src = (_ENGINE / "api" / "learning_routes.py").read_text(encoding="utf-8")
    assert "for update" in src, "the approval path no longer locks the row it is about to move"
    assert 'raise HTTPException(404' in src and "raise HTTPException(409" in src, (
        "the approval path must 404 on a missing object and 409 on one that is not in "
        "`human_review` — without both, a human approval can move an object twice")


# ── the extractor may not be satisfied by prose ────────────────────────────────────────────────

def test_a_sentence_about_an_update_is_not_an_update():
    """⛔ Four guards in this programme broke on their own documentation. This module's declaration
    quotes `set proposed_value = …` in order to forbid it, and must not thereby become a violator."""
    assert "genios_engine/platform/table_coverage.py" not in TC.update_columns(_TABLE)


@pytest.mark.parametrize("sql,expected", [
    ("update t set a = :x where org_id = :o", {"a"}),
    ("update t set a = :x, b = :y where org_id = :o", {"a", "b"}),
    # ⛔ THE CASE THAT CAUGHT THE FIRST VERSION. `feedback/reset.py` really writes this shape, and
    # splitting the clause on every comma made the second part `:at)`.
    ("update t set active = false, expires_at = least(expires_at, :at) where org_id = :o",
     {"active", "expires_at"}),
    ("update t set a = coalesce(b, c) where org_id = :o", {"a"}),
    ("update t set a = :x", {"a"}),
    ("select a from t where b = :x", set()),
    ("update other set a = :x where org_id = :o", set()),
])
def test_the_column_parser_is_the_one_that_ships(sql, expected):
    """⛔ Calls `table_coverage.set_columns`, not a copy of it. The first version of this test
    reimplemented the parse and asserted against its own copy — which is how a guard ends up
    proving the thing it duplicated rather than the thing that ships."""
    assert TC.set_columns(sql, "t") == frozenset(expected)


def test_the_engine_still_has_a_proposal_table_to_guard():
    """A guard whose subject disappears must fail loudly rather than pass on an empty set."""
    assert TC.update_columns(_TABLE), "no module updates learning_objects any more — re-read this"
    assert ast.parse((_ENGINE / "feedback" / "publisher.py").read_text(encoding="utf-8"))
