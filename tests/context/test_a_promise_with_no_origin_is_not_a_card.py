"""A promise the graph cannot trace to a message is not evidence that one was made.

MEASURED ON THE PILOT, 16 Sep 2026. Twenty-one `commitment` nodes and six `company` nodes reach
`read_overdue_commitments` carrying four facts and nothing else — `action`, `due_at`,
`days_overdue`, `owed_to`, every one of them `deterministic_derived`, none with a
`created_by_event_id`, none with a `graph_source_refs` row. Nothing anybody said is underneath
them. Ten prescriptive cards were minted on those anchors.

WHERE THEY CAME FROM. Their display names carry this reading's own headline suffix TWICE —
"confirm availability for a meeting — promise past due — promise past due". They are the
reading's output, read back as its input. `anchor_node_type`'s `reading:` namespacing closed that
loop and the closure is measured: 37 doubled names, 0 tripled, across 418 situation computations
since the last write to one. So this file is NOT about reopening that fix. The residue is still
live, and nothing anywhere said that a promise with no origin may not anchor a card — which is
why the next loop would mint cards for weeks before anybody noticed it had opened.

THE LIMIT IS THE POINT. A `deterministic_derived` fact with no event is CORRECT: it was computed
rather than observed, and its provenance is the source ref instead. This refuses only the subject
that has neither, and only when the gather positively said so — the same discipline the owner
check directly above it keeps, for the same reason.
"""
from datetime import datetime, timedelta, timezone

import pytest

pytest.importorskip("sqlalchemy")

from genios_engine.context.outreach_situations import (  # noqa: E402
    _UNTRACEABLE_COMMITMENTS,
    read_overdue_commitments,
)

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=timezone.utc)
OVERDUE = (NOW - timedelta(days=6)).isoformat()
US = "mrrohitswerashi@gmail.com"


def _rows(**over) -> dict:
    row = {"commitment.due_at": OVERDUE,
           "commitment.action": "confirm availability for a meeting",
           "_name": "confirm availability for a meeting — promise past due",
           "_owner_key": US, "_owner_name": "Rohit Swerashi"}
    row.update(over)
    return {"cmt_1": row, "_mailbox_owner": US}


# =============================================================================================
# the refusal, and the half that must not move
# =============================================================================================
def test_a_promise_with_no_origin_produces_no_finding():
    """The 21. Every fact derived, nothing tying any of them to a message."""
    assert read_overdue_commitments(_rows(_untraceable=True), NOW, {}) == []


def test_a_promise_that_can_be_traced_still_produces_its_finding():
    """The half that must not move: a real overdue promise is still a card."""
    [finding] = read_overdue_commitments(_rows(), NOW, {})

    facts = {name: value for name, value, _kind in finding.facts}
    assert facts["commitment.owner_key"] == US


def test_an_ungathered_guard_refuses_nothing():
    """`_optional` returns `[]` when the query cannot run, so nothing is stamped. That must mean
    "not checked", never "not traceable" — a deployment missing `graph_source_refs` loses the
    guard and keeps its cards, which is what fail-open means here."""
    assert len(read_overdue_commitments(_rows(), NOW, {})) == 1
    assert read_overdue_commitments(_rows(_untraceable=False), NOW, {}) != [], (
        "a stamp that positively says 'traceable' was read as a refusal")


# =============================================================================================
# the query — the part that decides which subjects get the stamp
# =============================================================================================
def _graph(rows_facts, refs=()):
    from sqlalchemy import create_engine, text
    eng = create_engine("sqlite://")
    with eng.begin() as c:
        c.execute(text("create table graph_facts (fact_version_id text, org_id text, "
                       "subject_node_id text, field text, status text, valid_to text, "
                       "created_by_event_id text)"))
        c.execute(text("create table graph_source_refs (org_id text, fact_version_id text)"))
        for fv, node, field, event in rows_facts:
            c.execute(text("insert into graph_facts values (:fv,'o',:n,:f,'active',null,:e)"),
                      {"fv": fv, "n": node, "f": field, "e": event})
        for fv in refs:
            c.execute(text("insert into graph_source_refs values ('o',:fv)"), {"fv": fv})
    return eng


def _untraceable(eng) -> set[str]:
    from sqlalchemy import text
    with eng.connect() as c:
        return {str(r.node_id) for r in c.execute(text(_UNTRACEABLE_COMMITMENTS), {"o": "o"})}


def test_a_subject_with_an_event_on_any_fact_is_traceable():
    """ONE is enough. The extractor writes `commitment.text` with an event and the sweep writes
    `days_overdue` without one; asking every fact to carry provenance would refuse the promise
    for having been kept up to date."""
    eng = _graph([("fv1", "n1", "commitment.text", "evt_1"),
                  ("fv2", "n1", "commitment.days_overdue", None)])

    assert _untraceable(eng) == set()


def test_a_subject_with_a_source_ref_and_no_event_is_traceable():
    """A `deterministic_derived` fact has no event BY DESIGN. Its provenance is the source ref,
    and refusing on the missing event would refuse every derived promise in the graph."""
    eng = _graph([("fv1", "n1", "commitment.due_at", None)], refs=["fv1"])

    assert _untraceable(eng) == set()


def test_a_subject_with_neither_is_the_one_that_is_refused():
    eng = _graph([("fv1", "n1", "commitment.action", None),
                  ("fv2", "n1", "commitment.due_at", None)])

    assert _untraceable(eng) == {"n1"}


def test_provenance_on_a_neighbour_does_not_launder_a_promise():
    """The subjects are independent. A traceable promise next to an invented one says nothing
    about the invented one, and a query grouping too coarsely would clear both."""
    eng = _graph([("fv1", "real", "commitment.text", "evt_1"),
                  ("fv2", "invented", "commitment.action", None)])

    assert _untraceable(eng) == {"invented"}


def test_a_retired_fact_does_not_keep_a_promise_alive():
    """Only live facts are read, so a promise whose evidence was superseded is refused rather
    than propped up by the version that is no longer true."""
    from sqlalchemy import text
    eng = _graph([("fv1", "n1", "commitment.action", None)])
    with eng.begin() as c:
        c.execute(text("insert into graph_facts values "
                       "('fv0','o','n1','commitment.text','superseded','2026-09-01','evt_1')"))

    assert _untraceable(eng) == {"n1"}


# =============================================================================================
# the call site — the stamp has to actually be written
# =============================================================================================
def test_the_gather_actually_stamps_the_subjects():
    """`_untraceable` defaults to absent and absent refuses nothing, so every test above still
    passes if `_gather` never writes the stamp. Twice on this branch that was the whole bug."""
    import ast
    import inspect

    from genios_engine.context import outreach_situations as O

    fn = next(n for n in ast.walk(ast.parse(inspect.getsource(O)))
              if isinstance(n, ast.FunctionDef) and n.name == "_gather")
    src = ast.unparse(fn)

    assert "_UNTRACEABLE_COMMITMENTS" in src, "_gather no longer runs the provenance query"
    assert "'_untraceable'" in src or '"_untraceable"' in src, "_gather no longer writes the stamp"
