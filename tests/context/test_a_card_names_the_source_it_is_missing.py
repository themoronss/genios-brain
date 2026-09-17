"""18 cards held because a source family is not connected, and not one of them says which.

    pytest tests/context/test_a_card_names_the_source_it_is_missing.py -q

THE GATE IS RIGHT, AGAIN. `source_coverage_insufficient` holds a candidate whose domain requires
complete coverage while a required source family is missing — a card asserting completeness on a
tenant that has not connected the system the claim depends on is exactly the overclaim the gate
exists to stop.

MEASURED ON THE PILOT, 2026-09-16. The tenant has connected `gmail` and `gcal` and nothing else:

    admin        required [finance, communication]   connected [calendar, communication]  NOT READY
    sales        required [communication, crm]       connected [calendar, communication]  NOT READY
    support      required [...]                                                           NOT READY
    fundraising  required [communication]            connected [calendar, communication]  READY

So `admin` waits on a finance source and `sales` on a CRM, and neither exists. 18 situations are
held on that — 8 support, 6 admin `condition_in_review`, 4 admin `awaiting_response`.

AND NOT ONE OF THE 18 NAMES THE SOURCE. Their `missing` lists read "a per-customer entitlement",
"public holidays and coverage handovers", "condition.predicate" — every one of them a fact-level
gap, none of them the reason the card is actually held. Measured: 0 of 18 mention a source family
at all.

That is the same shape as `l1_refusal`, the meeting lane, the five dead readings and the conflict
summary: a refusal that is correct and invisible. This unit does not open the gate — opening it
would publish a card that asserts what the tenant has no system of record for. It makes the card
able to say "this waits on a finance source you have not connected", which is the one sentence
that turns a silent absence into something a founder can act on in an afternoon.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context.situations import unmet_source_families

pytestmark = pytest.mark.unit

ORG = "org1"


@pytest.fixture
def conn():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text("create table source_coverage (org_id text, domain text, required text, "
                       "connected text, coverage_ready boolean)"))
        yield c


def coverage(conn, domain, required, connected, ready=False):
    import json
    conn.execute(text("insert into source_coverage values (:o,:d,:r,:c,:k)"),
                 {"o": ORG, "d": domain, "r": json.dumps(required),
                  "c": json.dumps(connected), "k": ready})


def test_it_names_the_family_that_is_missing(conn) -> None:
    """THE SENTENCE THE CARD COULD NOT SAY. `admin` waits on finance; the card said
    "condition.predicate"."""
    coverage(conn, "admin", ["finance", "communication"], ["calendar", "communication"])
    assert unmet_source_families(conn, ORG, "admin") == ("finance",)


def test_several_missing_families_are_all_named(conn) -> None:
    coverage(conn, "sales", ["communication", "crm", "billing"], ["communication"])
    assert unmet_source_families(conn, ORG, "sales") == ("billing", "crm")


def test_a_covered_domain_names_nothing(conn) -> None:
    """`fundraising` needs only communication and has it. A card there must not gain a gap it
    does not have — a false "you are missing something" is worse than silence."""
    coverage(conn, "fundraising", ["communication"], ["calendar", "communication"], ready=True)
    assert unmet_source_families(conn, ORG, "fundraising") == ()


def test_a_domain_with_no_coverage_row_names_nothing(conn) -> None:
    """Never assessed is not the same as under-connected, and only the second is a statement
    about the tenant. The engine behaves exactly as it does today for a domain nobody measured."""
    assert unmet_source_families(conn, ORG, "admin") == ()


def test_an_unreadable_table_costs_the_sentence_and_never_the_sweep(conn) -> None:
    conn.execute(text("drop table source_coverage"))
    assert unmet_source_families(conn, ORG, "admin") == ()


def test_it_reads_and_never_writes() -> None:
    """It reports which source is missing. Connecting one is the tenant's decision and has its own
    route; a reader that could mark a domain covered would be asserting a system exists."""
    import ast
    import inspect

    from genios_engine.context import situations

    tree = ast.parse(inspect.getsource(situations.unmet_source_families))
    sql = " ".join(lit.value.lower()
                   for call in ast.walk(tree)
                   if isinstance(call, ast.Call) and getattr(call.func, "id", "") == "text"
                   for lit in ast.walk(call)
                   if isinstance(lit, ast.Constant) and isinstance(lit.value, str))
    assert sql, "no SQL found"
    for forbidden in ("insert", "update", "delete"):
        assert forbidden not in sql, f"this reader writes: {forbidden}"


def test_the_answer_is_ordered(conn) -> None:
    """It reaches a card's `missing` list, which is compared between sweeps. An unstable order
    would make an unchanged card look changed."""
    coverage(conn, "admin", ["zeta", "alpha", "communication"], ["communication"])
    assert unmet_source_families(conn, ORG, "admin") == ("alpha", "zeta")


def test_both_situation_writers_add_it_to_the_card() -> None:
    """Wired where a card's `missing` is composed, in BOTH writers. `support_situations` holds 8
    of the 18 and `outreach_situations` the other 10, so wiring one leaves half the cards still
    unable to say why they are held — the same half-fix the correlation seam had."""
    import ast
    import importlib
    import inspect

    missing = []
    for name in ("outreach_situations", "support_situations"):
        module = importlib.import_module(f"genios_engine.context.{name}")
        tree = ast.parse(inspect.getsource(module))
        called = {getattr(n.func, "id", "") for n in ast.walk(tree) if isinstance(n, ast.Call)}
        if "unmet_source_families" not in called:
            missing.append(name)
    assert missing == [], f"these writers never name the missing source: {missing}"


def test_the_coverage_table_is_read_once_per_domain_not_once_per_situation() -> None:
    """`source_coverage` holds four rows for a tenant and the composing loop runs over every
    finding of every reading. A read inside it is the per-situation shape
    `PERFORMANCE_HARDENING.md` records taking a pass past thirty minutes — and the sweep this
    lands in already takes three hours."""
    import ast
    import importlib
    import inspect

    for name in ("outreach_situations", "support_situations"):
        module = importlib.import_module(f"genios_engine.context.{name}")
        tree = ast.parse(inspect.getsource(module))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
                 and getattr(n.func, "id", "") == "unmet_source_families"]
        assert calls, f"{name} does not call it"
        for call in calls:
            memoised = [a for a in ast.walk(tree) if isinstance(a, ast.Call)
                        and getattr(a.func, "attr", "") == "setdefault"
                        and any(c is call for c in ast.walk(a))]
            assert memoised, (
                f"{name} calls unmet_source_families outside a memo — that is one database read "
                f"per situation against a four-row table")
