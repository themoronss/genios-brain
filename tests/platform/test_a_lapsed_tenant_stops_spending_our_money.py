"""A tenant whose plan lapsed stops costing us model spend — on every background lane.

    pytest tests/platform/test_a_lapsed_tenant_stops_spending_our_money.py -q

⛔ WHY THIS FILE EXISTS. Plan expiry was enforced in exactly TWO places, both inside
`api/intelligence_routes`, on the two calls a PERSON makes. Everything the product does on its own
was ungated: the sweep kept pulling mail, the chain kept reasoning, the warm lane kept building
cards, and `l4_llm_decision`, `l1_extract` and `relevance_gate` kept calling the model.

Measured on production 2026-10-04, counting only calls made AFTER each org's grace window closed:

    Rohit Swerashi   grace closed 21 Sep   12,831 calls
    Harsh Tripathi   grace closed 20 Sep   11,682 calls
    Anisha Prasad    grace closed 03 Oct    1,523 calls
    ─────────────────────────────────────────────────────
                                           26,036 calls
                        ~28.9M input + ~5.3M output tokens, ~$55, running at ~$21/day

Three lapsed tenants, nobody reading the output, and the bill was ours. Model spend is the only
per-unit cost this system has.

⛔ `grace` IS NOT `expired`, and `test_the_grace_window_still_runs` is why. The grace window exists
so a late payment does not interrupt the product; a gate that stopped work during grace would
delete the window's entire reason to exist.

⛔ AND IT FAILS OPEN, deliberately — `test_an_unreadable_billing_row_never_stops_a_payer`. Every
other gate on this path (`_org_paused`, `_sync_headroom`, `_llm_over_daily_cap`) fails open on the
same argument: a billing row that cannot be read must never be the reason a PAYING customer's mail
stops arriving. The failure mode of being wrong in the other direction is silent and unbounded.

⛔ READS ARE NOT GATED. `platform/billing.py` says it in its own words — *"locking an unpaid
customer out of the page they would pay on is the one failure that cannot recover itself"* — so a
lapsed tenant still signs in, still sees the cards it has, and still finds the renew button. What
stops is the spending, nothing else.
"""

from __future__ import annotations

import ast
import inspect
import textwrap
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.platform import billing as B

pytestmark = pytest.mark.unit

NOW = datetime(2026, 10, 4, 12, 0, tzinfo=timezone.utc)


# ── the shared authority ────────────────────────────────────────────────────────────────────────

def test_both_lanes_ask_the_same_authority():
    """⛔ THE MUTATION THIS REJECTS: one lane growing its own idea of "expired". The sweep and the
    warm lane must both route through `billing.expiry_state`, which is pure and is the only place
    that knows what those three columns mean together."""
    from genios_engine.api import routes
    from genios_engine.platform import warm_lane

    for fn in (routes._plan_expired, warm_lane.plan_expired):
        src = textwrap.dedent(inspect.getsource(fn))
        calls = {n.func.attr for n in ast.walk(ast.parse(src))
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        assert "expiry_state" in calls, (
            f"{fn.__qualname__} decides plan state without billing.expiry_state — two answers to "
            "one question, and the stale one eventually wins")


@pytest.mark.parametrize("status,expires,grace,expected", [
    # the three production rows that paid for this file
    ("expired", NOW - timedelta(days=21), NOW - timedelta(days=13), "expired"),
    ("expired", NOW - timedelta(days=21), NOW - timedelta(days=14), "expired"),
    ("expired", NOW - timedelta(days=9),  NOW - timedelta(days=1),  "expired"),
    # still inside the window somebody may yet pay in
    ("expired", NOW - timedelta(days=2),  NOW + timedelta(days=5),  "grace"),
    ("active",  NOW + timedelta(days=30), None,                     "active"),
])
def test_expiry_state_is_what_the_gate_reads(status, expires, grace, expected):
    assert B.expiry_state(status, expires, grace, now=NOW) == expected


# ── the sweep ───────────────────────────────────────────────────────────────────────────────────

def _sweep_source() -> str:
    from genios_engine.api import routes
    return textwrap.dedent(inspect.getsource(routes.run_sync_sweep))


def test_the_sweep_skips_a_lapsed_tenants_connections():
    """L1 is the first spender: the relevance gate runs on every unknown sender."""
    assert "_plan_expired(" in _sweep_source(), (
        "run_sync_sweep no longer asks whether the tenant is paid up — the largest LLM spender "
        "in the system is ungated again")


def test_the_chain_is_skipped_too_not_only_the_pull():
    """⛔ THE HALF-FIX THIS REJECTS. Gating only the L1 pull leaves L2/L3/L5 running on data
    already in the graph — `l4_llm_decision` alone was 1,608 calls in 24h. The org set the chain
    iterates must exclude lapsed tenants, exactly as it already excludes paused ones."""
    src = _sweep_source()
    line = next((ln for ln in src.splitlines() if "orgs = {" in ln and "conns" in ln), None)
    assert line is not None, "the chain's org set moved — re-point this test at it"
    window = src[src.index(line):src.index(line) + 220]
    assert "lapsed" in window, (
        "the L2/L3/L5 pass still reasons for a lapsed tenant; only the pull was gated")


def test_the_skip_is_counted_not_silent():
    """A skip nobody can count is a skip nobody can audit — and 'why did this org stop syncing'
    is the question support is always asked. It is its OWN counter: over-budget clears at
    midnight and sync-quota clears on a bigger plan, but this one clears only when somebody pays."""
    src = _sweep_source()
    assert "l1_skipped_plan_expired" in src, "the lapsed-tenant skip reports no number"
    assert "l1_lapsed" in src


def test_the_plan_gate_outranks_the_budget_gate():
    """"You stopped paying" and "you spent today's allowance" send the customer to two different
    buttons. The first outranks, so it must be asked first."""
    src = _sweep_source()
    assert src.index("_plan_expired(") < src.index("_llm_over_daily_cap("), (
        "the daily-budget check now runs before the plan check; a lapsed tenant would be reported "
        "as merely over budget, and support would tell them to wait until midnight")


# ── the warm lane ───────────────────────────────────────────────────────────────────────────────

def test_the_warm_lane_refuses_at_the_door_not_at_the_claim():
    """⛔ Gating the CLAIM loop would leave the rows written, leased, retried and parked forever.
    Refusing to write them is the only version that actually stops."""
    from genios_engine.platform import warm_lane

    src = textwrap.dedent(inspect.getsource(warm_lane.enqueue))
    assert "plan_expired(" in src, (
        "warm_lane.enqueue queues work for a lapsed tenant again — every pushed mail, upload and "
        "screen delta reaches the chain through this one function")


def test_the_warm_lane_gate_runs_before_the_insert():
    """A check that runs after the insert is not a gate."""
    from genios_engine.platform import warm_lane

    src = textwrap.dedent(inspect.getsource(warm_lane.enqueue))
    assert src.index("plan_expired(") < src.index("insert into l2_work_queue"), (
        "the plan check moved below the insert — the row is written before anybody asks")


# ── the two refusals this gate must NOT make ────────────────────────────────────────────────────

def test_the_grace_window_still_runs():
    """⛔ THE MUTATION THIS REJECTS: treating `grace` as `expired`. The window exists so a late
    payment does not interrupt the product; gating it deletes its whole reason to exist."""
    assert B.expiry_state("expired", NOW - timedelta(days=2),
                          NOW + timedelta(days=5), now=NOW) == "grace"
    for fn_src in (textwrap.dedent(inspect.getsource(__import__(
            "genios_engine.api.routes", fromlist=["x"])._plan_expired)),
            textwrap.dedent(inspect.getsource(__import__(
                "genios_engine.platform.warm_lane", fromlist=["x"]).plan_expired))):
        assert '== "expired"' in fn_src, (
            "the gate no longer compares against 'expired' alone — a tenant inside its grace "
            "window would be cut off while it is still being asked to pay")


def test_an_unreadable_billing_row_never_stops_a_payer():
    """FAILS OPEN, like every other gate on this path. Being wrong this way costs money and is
    visible in `llm_costs`; being wrong the other way silently stops a paying customer's mail."""
    from genios_engine.api import routes
    from genios_engine.platform import warm_lane

    class Boom:
        def connect(self):
            raise RuntimeError("billing read failed")

    assert warm_lane.plan_expired(Boom(), "org_x") is False
    assert warm_lane.plan_expired(None, "org_x") is False

    src = textwrap.dedent(inspect.getsource(routes._plan_expired))
    tree = ast.parse(src)
    handlers = [h for h in ast.walk(tree) if isinstance(h, ast.ExceptHandler)]
    assert handlers, "_plan_expired lost its except branch — a DB blip now halts a payer's sync"
    assert any(isinstance(n, ast.Constant) and n.value is False
               for h in handlers for n in ast.walk(h)), (
        "_plan_expired no longer returns False on a failed billing read")


def test_an_unknown_org_is_not_treated_as_lapsed():
    """Auth owns the refusal for an org that does not exist; inventing a billing opinion here
    would turn a missing row into a silent product outage."""
    from genios_engine.api import routes

    for src in (textwrap.dedent(inspect.getsource(routes._plan_expired)),
                textwrap.dedent(inspect.getsource(__import__(
                    "genios_engine.platform.warm_lane", fromlist=["x"]).plan_expired))):
        assert "if row is None" in src, "a missing orgs row is no longer handled explicitly"
