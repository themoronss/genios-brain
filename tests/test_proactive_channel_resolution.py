"""Proactive delivery addresses the channel the TENANT has, or it says it cannot reach them.

Why this file exists, in production numbers measured on 2026-08-29:

  * ``delivery_outbox`` held THREE rows across the database's entire history. All three were
    ``channel='slack'``, all three ``failed_terminal``, all three ``last_error='channel
    unregistered or inactive'``, all three ``attempts=1`` — killed by the drain on first look.
  * ``org_channels`` held exactly TWO rows, both ``in_app``, both created by a backfill at the
    byte-identical timestamp ``2026-08-23 17:05:46.993357``. No ``slack`` row has ever existed
    in either org.
  * ``last_digest_date`` was NULL for both orgs across all of history and no ``digest:`` row was
    ever written — the digest never failed, it never ran.

One defect explains all three: the enqueue paths took ``channel: str = "slack"`` as a Python
default and ``run_distribution`` called every one of them without an argument. Every proactive
message this product has ever produced was therefore addressed by a default rather than by the
tenant, to a channel that did not exist.

The fix is a resolution step, and these tests are about the two halves it must get right:
a channel counts only if the tenant REGISTERED it *and* we have a transport for it. Checking
either half alone reproduces the bug — the one channel these tenants do have (``in_app``) is the
pull surface, ``get_channel('in_app')`` is None, and an ``in_app`` row would have died in the
drain exactly like the slack rows did.
"""
from __future__ import annotations

import inspect
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.deliver import executive_bridge, outbox

NOW = datetime(2026, 8, 29, 9, 0, tzinfo=timezone.utc)


# ── a database small enough to reason about ───────────────────────────────────────────────────
class _Result:
    def __init__(self, rows):
        self._rows = list(rows)

    def __iter__(self):
        return iter(self._rows)

    def fetchall(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        return self._rows[0][0] if self._rows else None


class _Conn:
    """Answers only the statements ``run_distribution`` issues in its own body.

    Anything else raises rather than returning empty: a silent empty result would let a test
    pass by skipping the very read it was written to check — the same contract
    ``tests/executive_fakes.py`` states for the Layer 5 double.
    """

    def __init__(self, world):
        self.world = world

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        p = params or {}
        if "from org_channels where org_id=:o and active" in sql:
            # `order by channel` is in the real statement, so the double sorts too — otherwise a
            # test could depend on an ordering Postgres does not promise.
            return _Result((ch,) for ch in sorted(self.world["channels"].get(p["o"], [])))
        if "from agent_registry" in sql:
            # The OTHER recipient table. A tenant's executors are NOT in `org_channels` and
            # cannot be — `deliverable_channels` subtracts the agent transports by law — so the
            # double keeps them in their own dict for the same reason the code keeps them in
            # their own table. Membership here already means "would pass `connected_executors`":
            # the scope and webhook-url clauses are real SQL and are proved against real
            # Postgres below, not simulated here.
            return _Result((a,) for a in sorted(self.world["agents"].get(p["o"], [])))
        if "select org_id from org_channels where active" in sql:
            # The real statement UNIONs `org_channels` with orgs holding LIVE cards, and
            # `agent_registry` is deliberately not in it: an executor with nothing to deliver is
            # not delivery work. A pushable card is a live card, so it enumerates its org here
            # exactly as the union would.
            orgs = (set(self.world["channels"]) | set(self.world["cards"])
                    | set(self.world["pushable"]))
            return _Result((o,) for o in sorted(orgs))
        if "urgency_band in ('high','critical')" in sql:
            return _Result((c,) for c in self.world["pushable"].get(p["o"], []))
        if "from delivery_outbox where org_id=:o and channel='agent_push'" in sql:
            return _Result(self.world["agent_rows"].get(p["o"], []))
        if "urgency_band not in ('high','critical')" in sql:
            return _Result([(self.world["cards"].get(p["o"], {}).get("standard", 0),)])
        if "k.assignee is null" in sql:
            return _Result([(self.world["cards"].get(p["o"], {}).get("unrouted", 0),)])
        raise AssertionError(f"the fake database does not model: {sql[:120]}")


class _Engine:
    def __init__(self, world):
        self.world = world

    def connect(self):
        return _Conn(self.world)


@pytest.fixture
def sweep(monkeypatch):
    """``run_distribution`` with its collaborators replaced by recorders.

    The collaborators are real and separately tested; what was broken — and what this fixture
    isolates — is the ORCHESTRATION decision above them: which channel each enqueue path is
    handed, and whether one is invoked at all.
    """
    calls: dict[str, list] = {"pending": [], "digest": [], "reminders": [], "linked": [],
                              "agent": []}
    # The agent lane's WRITER is the recorder; `enqueue_agent_lane` itself runs for real against
    # the double, because its gating — does this org have an executor, which cards qualify, which
    # (card, agent) pairs already have a row — IS the orchestration these tests are about.
    monkeypatch.setattr(outbox, "enqueue_agent_push",
                        lambda engine, org, card_id: (
                            calls["agent"].append((org, card_id)), 1)[1])
    monkeypatch.setattr(outbox, "enqueue_pending",
                        lambda engine, org, channel, base_url="": (
                            calls["pending"].append((org, channel, base_url)),
                            {"queued": 1, "band_starved": 0, "unrouted": 0})[1])
    monkeypatch.setattr(outbox, "enqueue_digest",
                        lambda engine, org, channel, eval_time=None: (
                            calls["digest"].append((org, channel)), 1)[1])
    monkeypatch.setattr(outbox, "enqueue_executive_messages",
                        lambda engine, org, channel, base_url="": (
                            calls["reminders"].append((org, channel, base_url)), 1)[1])
    monkeypatch.setattr(outbox, "link_commitment_cards",
                        lambda engine, org: (calls["linked"].append(org), 0)[1])
    monkeypatch.setattr(outbox, "shadow_resolve_v2",
                        lambda engine, org, now: {"resolved": 0, "unroutable": {}, "errors": 0})
    monkeypatch.setattr(outbox, "drain", lambda engine, eval_time=None: {})
    return calls


def world(channels=None, cards=None, agents=None, pushable=None, agent_rows=None):
    """``agents``/``pushable``/``agent_rows`` are the agent lane's three inputs.

    ``agents``    : org → executor ids that pass ``connected_executors``.
    ``pushable``  : org → card ids that pass the HUMAN lane's eligibility filter, which the agent
                    lane shares verbatim (``outbox.PUSHABLE_CARDS_SQL``). A card absent from this
                    list is one the human lane suppresses.
    ``agent_rows``: org → (card_id, agent_id) pairs already in ``delivery_outbox``.
    """
    return {"channels": channels or {}, "cards": cards or {}, "agents": agents or {},
            "pushable": pushable or {}, "agent_rows": agent_rows or {}}


# ── the resolution itself ─────────────────────────────────────────────────────────────────────
def test_a_channel_counts_only_if_registered_and_implemented():
    """Both halves, because the live tenant fails a different one than the outbox rows did."""
    conn = _Conn(world(channels={"org_1": ["in_app", "slack", "teams"]}))
    assert outbox.deliverable_channels(conn, "org_1") == ["slack"]


def test_the_pull_surface_is_not_a_transport():
    """The exact production state: the only registered channel is the one with no adapter.

    ``in_app`` is ``routing.PULL_SURFACE`` — the card is already sitting on it, so there is
    nothing to send and ``get_channel('in_app')`` is None. Resolving to it would have moved the
    identical ``failed_terminal`` from 'slack' onto 'in_app' rather than fixing anything.
    """
    conn = _Conn(world(channels={"org_1": ["in_app"]}))
    assert outbox.deliverable_channels(conn, "org_1") == []

    from genios_engine.deliver.channels.base import get_channel
    from genios_engine.deliver.routing import PULL_SURFACE
    assert get_channel(PULL_SURFACE) is None, "if a pull surface ever gains an adapter, revisit"


def test_an_unregistered_org_resolves_to_nothing_rather_than_to_slack():
    assert outbox.deliverable_channels(_Conn(world()), "org_never_seen") == []


# ── what the sweep does with that answer ──────────────────────────────────────────────────────
def test_a_tenant_with_no_push_channel_is_sent_nothing_and_is_counted(sweep):
    """The live tenant's actual state. Nothing is queued, and the silence has a NAME.

    Queueing here would not be "trying": the drain has already decided the outcome, so the row
    is a failure we manufactured and then reported as work. Production's three ``failed_terminal``
    rows were counted by the sweep as ``queued``.
    """
    engine = _Engine(world(channels={"org_1": ["in_app"]},
                           cards={"org_1": {"standard": 113, "unrouted": 0}}))

    totals = outbox.run_distribution(engine, base_url="", eval_time=NOW)

    assert sweep["pending"] == [] and sweep["digest"] == [] and sweep["reminders"] == []
    assert totals["queued"] == 0 and totals["digests"] == 0 and totals["reminders"] == 0
    assert totals["no_deliverable_channel"] == 1
    assert totals["org_failures"] == 0, "an unconfigured tenant is a state, not an error"


def test_every_enqueue_path_is_handed_the_channel_the_tenant_registered(sweep):
    """All three paths, because all three carried the same hardcoded default."""
    engine = _Engine(world(channels={"org_1": ["in_app", "slack"]}))

    totals = outbox.run_distribution(engine, base_url="https://app.test", eval_time=NOW)

    assert sweep["pending"] == [("org_1", "slack", "https://app.test")]
    assert sweep["digest"] == [("org_1", "slack")]
    assert sweep["reminders"] == [("org_1", "slack", "https://app.test")]
    assert totals["no_deliverable_channel"] == 0
    assert totals["queued"] == 1 and totals["digests"] == 1 and totals["reminders"] == 1


def test_backlog_diagnostics_survive_having_nowhere_to_send(sweep):
    """``band_starved``/``unrouted`` used to be computed only as a side effect of enqueueing.

    So the one tenant whose delivery is entirely unconfigured — the tenant these numbers are
    actually about — produced neither. They are per-ORG facts about the card pipeline and hold
    whether or not a channel exists.
    """
    engine = _Engine(world(channels={"org_1": ["in_app"]},
                           cards={"org_1": {"standard": 113, "unrouted": 6}}))

    totals = outbox.run_distribution(engine, base_url="", eval_time=NOW)

    assert totals["band_starved"] == 113 and totals["unrouted"] == 6


def test_backlog_is_counted_once_per_org_not_once_per_channel(sweep, monkeypatch):
    """A per-channel loop that also counted the backlog would multiply one card by two channels.

    Only one human push adapter ships today, so the second channel is introduced here rather
    than found — which is the point: this arithmetic breaks on the day a second one lands, and
    that is the day nobody will be looking at it.
    """
    from genios_engine.deliver import units
    monkeypatch.setattr(units, "_implemented_channels", lambda: frozenset({"slack", "teams"}))
    engine = _Engine(world(channels={"org_1": ["slack", "teams"]},
                           cards={"org_1": {"standard": 10, "unrouted": 4}}))

    totals = outbox.run_distribution(engine, base_url="", eval_time=NOW)

    assert [c[1] for c in sweep["pending"]] == ["slack", "teams"], "both channels are used"
    assert totals["queued"] == 2, "one enqueue pass per channel"
    assert totals["band_starved"] == 10 and totals["unrouted"] == 4


def test_an_agent_transport_is_never_a_human_card_channel():
    """Routing law 1, with a mechanical consequence.

    ``agent_push`` HAS an adapter, so an intersection of registered-and-implemented alone would
    hand it to ``enqueue_pending``. That row's recipient is a seat; the drain resolves agent rows
    against ``agent_registry`` by recipient, would find no such agent, and would write
    ``failed_terminal`` — the same defect by a different road. Agent deliveries have their own
    enqueue path and their own registry.
    """
    conn = _Conn(world(channels={"org_1": ["agent_push", "in_app"]}))
    assert outbox.deliverable_channels(conn, "org_1") == []


def test_bookkeeping_still_runs_for_a_tenant_that_cannot_be_reached(sweep):
    """Linking a commitment to its card is our own bookkeeping, not a send.

    Skipping it when no channel exists would mean the day a tenant finally registers one, their
    reminders cannot name the card they belong to.
    """
    engine = _Engine(world(channels={"org_1": ["in_app"]}))

    outbox.run_distribution(engine, base_url="", eval_time=NOW)

    assert sweep["linked"] == ["org_1"]


# ── the agent lane ────────────────────────────────────────────────────────────────────────────
#
# `enqueue_agent_push` was fully built, documented and wired to NOTHING in the sweep. Its three
# siblings are called inside `for channel in channels:`, and the agent lane cannot live there:
# `deliverable_channels` subtracts `routing.AGENT_TRANSPORTS` on purpose (law 1), so an executor
# is invisible to channel resolution by construction. It needs its own pass, resolved from
# `agent_registry`. These tests are about that pass staying a pass and not becoming a back door.
def test_an_org_with_a_registered_executor_gets_its_pushable_cards_queued(sweep):
    """The wiring itself: the lane runs, and it runs on the cards the human lane would push."""
    engine = _Engine(world(agents={"org_1": ["agent_ops"]},
                           pushable={"org_1": ["card_a", "card_b"]}))

    totals = outbox.run_distribution(engine, base_url="", eval_time=NOW)

    assert sweep["agent"] == [("org_1", "card_a"), ("org_1", "card_b")]
    assert totals["agent_pushed"] == 2


def test_an_org_with_no_executor_is_completely_untouched_by_the_lane(sweep):
    """The safety property of turning a dormant path on: nobody new starts receiving anything.

    ``agents`` empty means the lane returns before it opens a connection — not "queries and finds
    nothing". The double would raise on the eligibility SELECT if it were reached, so this asserts
    the early return rather than merely its result.
    """
    engine = _Engine(world(channels={"org_1": ["slack"]},
                           pushable={"org_1": ["card_a"]}))

    totals = outbox.run_distribution(engine, base_url="", eval_time=NOW)

    assert sweep["agent"] == [] and totals["agent_pushed"] == 0
    assert sweep["pending"] == [("org_1", "slack", "")], "the human lane is unaffected"


def test_a_card_the_human_lane_suppresses_is_never_pushed_to_an_agent(sweep):
    """The gate this lane must not loosen.

    ``card_standard`` is live and this org has an executor; it is simply not pushable — below the
    band, or its pack authority has lapsed, or its decision was superseded. The human lane would
    queue nothing for it, and the machine lane must not become the looser of the two on the same
    card. It cannot, structurally: both select on the one ``PUSHABLE_CARDS_SQL`` string, which is
    what the next test locks.
    """
    engine = _Engine(world(agents={"org_1": ["agent_ops"]},
                           pushable={"org_1": ["card_pushable"]},
                           cards={"org_1": {"standard": 1, "unrouted": 0}}))

    totals = outbox.run_distribution(engine, base_url="", eval_time=NOW)

    assert sweep["agent"] == [("org_1", "card_pushable")], "the suppressed card is not in the set"
    assert totals["agent_pushed"] == 1
    assert totals["band_starved"] == 1, "and it is still REPORTED, not silently dropped"


def test_both_push_lanes_select_on_one_eligibility_string():
    """A regression lock on the mechanism, because the failure mode is silent.

    The human lane's filter is nine joins and a ~40-clause authority predicate. A second copy of
    it that drops one clause still returns plausible cards, and the only symptom would be an
    external machine holding a card no person was allowed to see. So the two lanes must not have
    two copies — they must have one string.
    """
    lane = inspect.getsource(outbox.enqueue_agent_lane)
    human = inspect.getsource(outbox.enqueue_pending)
    assert "PUSHABLE_CARDS_SQL" in lane and "PUSHABLE_CARDS_SQL" in human
    for clause in ("urgency_band in ('high','critical')", "k.state in ('queued','surfaced')",
                   "s.status='open'"):
        assert clause in outbox.PUSHABLE_CARDS_SQL
        assert clause not in lane, "the lane re-states an eligibility clause instead of sharing it"


def test_a_card_already_queued_to_every_executor_is_not_re_enqueued(sweep):
    """Idempotence at the lane, not only at the unique index.

    The index already makes a second ``enqueue_agent_push`` a no-op, so this is about cost, and
    the cost is one write TRANSACTION per card per tick forever on an org whose queue is settled.
    The check is per (card, agent), so ``card_a`` still moves when a SECOND agent registers.
    """
    engine = _Engine(world(agents={"org_1": ["agent_ops"]},
                           pushable={"org_1": ["card_a", "card_b"]},
                           agent_rows={"org_1": [("card_a", "agent_ops")]}))

    totals = outbox.run_distribution(engine, base_url="", eval_time=NOW)

    assert sweep["agent"] == [("org_1", "card_b")] and totals["agent_pushed"] == 1

    engine.world["agents"]["org_1"] = ["agent_ops", "agent_new"]
    sweep["agent"].clear()
    outbox.run_distribution(engine, base_url="", eval_time=NOW)
    assert ("org_1", "card_a") in sweep["agent"], (
        "a card already sent to one agent must still reach an agent registered later")


# ── what "nowhere to send" means once a second lane exists ─────────────────────────────────────
def test_an_org_with_an_agent_and_no_human_channel_is_not_counted_as_unreachable(sweep):
    """``no_deliverable_channel`` is the number that means "nothing we produce can get out".

    Before the agent lane was wired, no human channel DID mean exactly that. It no longer does:
    this org is reached on every tick. Leaving it counted would send an operator to fix a tenant
    whose delivery works, and would quietly turn the one unambiguous alarm in this sweep into a
    weaker statement about channel configuration.
    """
    engine = _Engine(world(agents={"org_1": ["agent_ops"]},
                           pushable={"org_1": ["card_a"]},
                           cards={"org_1": {"standard": 4, "unrouted": 2}}))

    totals = outbox.run_distribution(engine, base_url="", eval_time=NOW)

    assert totals["no_deliverable_channel"] == 0
    assert totals["agent_pushed"] == 1, "because it is genuinely reachable — that is the reason"
    assert sweep["pending"] == [] and sweep["digest"] == [] and sweep["reminders"] == []
    assert totals["band_starved"] == 4 and totals["unrouted"] == 2


def test_an_org_with_neither_lane_is_still_counted_as_unreachable(sweep):
    """And the alarm still fires for the tenant it was written about."""
    engine = _Engine(world(channels={"org_1": ["in_app"]},
                           cards={"org_1": {"standard": 113, "unrouted": 0}}))

    totals = outbox.run_distribution(engine, base_url="", eval_time=NOW)

    assert totals["no_deliverable_channel"] == 1
    assert totals["agent_pushed"] == 0 and sweep["agent"] == []


def test_the_unreachable_log_line_names_which_lane_is_missing(sweep, caplog):
    """Two different states, two different fixes — so one message for both would be a lie in one
    of them. An org with an executor is not "nothing proactive can be sent"; it is "no PERSON
    sees what the machines are acting on"."""
    import logging

    with caplog.at_level(logging.WARNING, logger="genios.deliver.outbox"):
        outbox.run_distribution(
            _Engine(world(agents={"org_1": ["agent_ops"]}, pushable={"org_1": ["card_a"]})),
            base_url="", eval_time=NOW)
        agent_only = caplog.messages[-1] if caplog.messages else ""
        caplog.clear()
        outbox.run_distribution(
            _Engine(world(channels={"org_2": ["in_app"]}, cards={"org_2": {"standard": 1}})),
            base_url="", eval_time=NOW)
        neither = caplog.messages[-1] if caplog.messages else ""

    assert "no human channel" in agent_only and "executor" in agent_only
    assert "nothing" not in agent_only, "it is reachable; saying otherwise is false"
    assert "no deliverable channel and no registered executor" in neither
    assert "nothing proactive can be sent" in neither


# ── the regression lock ───────────────────────────────────────────────────────────────────────
def test_no_enqueue_path_may_default_its_channel():
    """The defect was a DEFAULT, so the lock is on the signature, not on one call site.

    There is no channel that is right when the caller has not looked, so not-looking has to be
    impossible to express. Every one of these took ``channel: str = "slack"`` and every one was
    called without an argument.
    """
    for fn in (outbox.enqueue_pending, outbox.enqueue_digest,
               executive_bridge.enqueue_executive_messages):
        param = inspect.signature(fn).parameters["channel"]
        assert param.default is inspect.Parameter.empty, (
            f"{fn.__name__} defaults its channel again — that default is how every proactive "
            "message in production got addressed to a Slack channel nobody had registered")


def test_the_sweep_never_names_a_channel_of_its_own():
    """A resolved channel is the only kind ``run_distribution`` may pass on.

    Asserted over the parsed body rather than the raw text, so the prose in this module and in
    the function's own comments — which must be free to name the channel that broke — cannot
    make the lock pass or fail for the wrong reason.
    """
    import ast
    import textwrap

    tree = ast.parse(textwrap.dedent(inspect.getsource(outbox.run_distribution)))
    literals = {node.value for node in ast.walk(tree)
                if isinstance(node, ast.Constant) and isinstance(node.value, str)}
    assert "deliverable_channels" in inspect.getsource(outbox.run_distribution)
    for name in ("slack", "teams", "in_app", "agent_push", "email", "webhook"):
        assert name not in literals, (
            f"run_distribution names the channel {name!r} itself; the sweep must only ever "
            "pass on a channel resolved from org_channels")


# ── the link back into the product ────────────────────────────────────────────────────────────
def test_the_card_link_comes_from_configuration_not_from_an_empty_default(sweep, monkeypatch):
    """``run_distribution(base_url="")`` was the shipped behaviour and its one caller never
    overrode it, so ``channels/slack.py`` dropped the "Open the card →" line from every message
    it has ever built (measured: all 3 production payloads, 238/260/248 bytes, no link)."""
    from genios_engine.platform import config

    monkeypatch.setattr(config, "get_settings",
                        lambda: type("S", (), {"dashboard_url": "https://brain.example.com"})())
    engine = _Engine(world(channels={"org_1": ["slack"]}))

    outbox.run_distribution(engine, eval_time=NOW)

    assert sweep["pending"] == [("org_1", "slack", "https://brain.example.com")]
    assert sweep["reminders"] == [("org_1", "slack", "https://brain.example.com")]


def test_an_unset_dashboard_url_omits_the_link_rather_than_inventing_one(sweep, monkeypatch):
    from genios_engine.platform import config

    monkeypatch.setattr(config, "get_settings", lambda: type("S", (), {"dashboard_url": ""})())
    engine = _Engine(world(channels={"org_1": ["slack"]}))

    outbox.run_distribution(engine, eval_time=NOW)

    assert sweep["pending"] == [("org_1", "slack", "")]
    from genios_engine.deliver.channels.slack import format_card_message
    rendered = format_card_message({"headline": "h", "situation": "s", "card_id": "card_1"},
                                   base_url="")
    assert "Open the card" not in rendered["blocks"][0]["text"]["text"]


# ── against real Postgres ─────────────────────────────────────────────────────────────────────
#
# The double above proves the sweep's CONTROL FLOW. It cannot prove that the SQL means in
# Postgres what it looks like it means — and two of the four defects here were SQL semantics:
# `enqueue_digest` returning 0 from its first statement, and the drain terminating a row whose
# channel has no adapter. These run against the scratch database when GENIOS_TEST_DATABASE_URL
# is set and skip otherwise, the same contract every other real-PG file in this suite has.
@pytest.fixture()
def conn(live_db_url):
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine
    if not live_db_url:
        pytest.skip("no scratch database configured")
    c = get_engine(live_db_url).connect()
    tx = c.begin()
    if not c.execute(text("select to_regclass('public.delivery_outbox')")).scalar():
        tx.rollback(); c.close(); pytest.skip("0043 not applied")
    org = c.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        tx.rollback(); c.close(); pytest.skip("no org")
    c.execute(text("delete from org_channels where org_id=:o"), {"o": org})
    c.execute(text("delete from agent_registry where org_id=:o"), {"o": org})
    try:
        yield c, org
    finally:
        tx.rollback(); c.close()


def _register(c, org, channel, config="{}"):
    from sqlalchemy import text
    c.execute(text("insert into org_channels (org_id, channel, config, active) "
                   "values (:o, :ch, cast(:cfg as jsonb), true)"),
              {"o": org, "ch": channel, "cfg": config})


def test_pg_the_production_channel_row_yields_no_deliverable_channel(conn):
    """Reconstruct production exactly: one active `in_app` row, config '{}', nothing else."""
    c, org = conn
    _register(c, org, "in_app")
    assert outbox.deliverable_channels(c, org) == []


def test_pg_registering_slack_is_what_makes_the_tenant_reachable(conn):
    """The whole fix, from the tenant's side: one PUT and delivery becomes possible."""
    c, org = conn
    _register(c, org, "in_app")
    _register(c, org, "slack", '{"webhook_url": "https://hooks.slack.com/services/T/B/x"}')
    assert outbox.deliverable_channels(c, org) == ["slack"]


def test_pg_an_inactive_channel_is_not_deliverable(conn):
    from sqlalchemy import text
    c, org = conn
    _register(c, org, "slack", '{"webhook_url": "https://hooks.slack.com/services/T/B/x"}')
    c.execute(text("update org_channels set active=false where org_id=:o and channel='slack'"),
              {"o": org})
    assert outbox.deliverable_channels(c, org) == []


class _TxEngine:
    """Hands the enqueue paths the test's own open transaction, so their writes roll back.

    `enqueue_digest` opens `engine.begin()`; nesting a real transaction inside the fixture's
    would commit independently and leak rows into the scratch database.
    """

    def __init__(self, c):
        self._c = c

    class _NoCommit:
        def __init__(self, c):
            self._c = c

        def __enter__(self):
            return self._c

        def __exit__(self, *exc):
            return False

        def close(self):
            """No-op: the fixture's transaction owns this connection's lifetime, not the drain."""

        def execute(self, *a, **kw):
            return self._c.execute(*a, **kw)

    def begin(self):
        return self._NoCommit(self._c)

    def connect(self):
        return self._NoCommit(self._c)


def test_pg_the_digest_returns_zero_when_the_channel_row_does_not_exist(conn):
    """The measured production state, reproduced: `last_digest_date` NULL forever, no digest row.

    The old default made `channel` 'slack' while `org_channels` held only 'in_app', so the
    function's FIRST statement found no row and returned 0 on every tick for every org. It never
    reached the point of failing — which is why there is no failed digest row to find.
    """
    from sqlalchemy import text
    c, org = conn
    _register(c, org, "in_app")

    assert outbox.enqueue_digest(_TxEngine(c), org, "slack", eval_time=NOW) == 0
    assert c.execute(text("select count(*) from delivery_outbox where org_id=:o and card_id like "
                          "'digest:%'"), {"o": org}).scalar() == 0


def test_pg_the_digest_is_claimed_once_a_day_on_a_channel_that_exists(conn):
    from sqlalchemy import text
    c, org = conn
    _register(c, org, "slack", '{"webhook_url": "https://hooks.slack.com/services/T/B/x"}')
    engine = _TxEngine(c)

    assert outbox.enqueue_digest(engine, org, "slack", eval_time=NOW) == 1
    assert outbox.enqueue_digest(engine, org, "slack", eval_time=NOW) == 0, "once per UTC day"

    row = c.execute(text("select card_id, channel from delivery_outbox where org_id=:o "
                         "and card_id like 'digest:%'"), {"o": org}).one()
    assert row.card_id == f"digest:{NOW.date().isoformat()}" and row.channel == "slack"
    assert c.execute(text("select last_digest_date from org_channels where org_id=:o "
                          "and channel='slack'"), {"o": org}).scalar() == NOW.date()


def test_pg_the_daily_marker_is_per_channel_so_a_second_channel_is_not_suppressed(conn):
    """`org_channels.last_digest_date` doubles as the once-per-day marker.

    It lives on the channel ROW, so resolving to two channels gives one digest on each rather
    than the second silently swallowing the first — the coupling to check before anyone adds a
    second transport.
    """
    from sqlalchemy import text
    c, org = conn
    _register(c, org, "slack", '{"webhook_url": "https://hooks.slack.com/services/T/B/x"}')
    _register(c, org, "teams", "{}")
    engine = _TxEngine(c)

    assert outbox.enqueue_digest(engine, org, "slack", eval_time=NOW) == 1
    assert outbox.enqueue_digest(engine, org, "teams", eval_time=NOW) == 1
    assert sorted(r.channel for r in c.execute(text(
        "select channel from delivery_outbox where org_id=:o and card_id like 'digest:%'"),
        {"o": org})) == ["slack", "teams"]


def test_pg_a_channel_without_an_adapter_is_terminated_by_the_drain_on_sight(conn):
    """Why resolution must exclude a pull surface rather than merely prefer a real one.

    A row addressed to a channel with no adapter dies on sight without a transport call, and it
    lands identically on 'in_app' — so "queue it to the channel they DO have" would have changed
    nothing but the channel name in the error.

    What it must NOT do any more is what production's entire delivery history did: three rows,
    `failed_terminal`, attempts 1, burned permanently because both the enqueue dedupe and
    `delivery_outbox_once` ignore status. `_park` writes `UNDELIVERABLE` instead — not terminal,
    attempts untouched, and selected by `revive_undeliverable` the moment a channel appears.
    Attempts is the assertion that matters: incrementing it would march a tenant toward
    `failed_terminal` for the time they spent unconfigured.
    """
    from sqlalchemy import text
    c, org = conn
    _register(c, org, "in_app")
    c.execute(text(
        "insert into delivery_outbox (id, org_id, card_id, channel, payload, next_attempt_at) "
        "values ('ob_pull_surface', :o, 'card_x', 'in_app', cast('{}' as jsonb), :t)"),
        {"o": org, "t": NOW})

    outbox.drain(_TxEngine(c), eval_time=NOW, limit=10)

    row = c.execute(text("select status, attempts, last_error from delivery_outbox "
                         "where id='ob_pull_surface'")).one()
    assert row.status == outbox.UNDELIVERABLE, "a config gap was recorded as a transport failure"
    assert row.attempts == 0, "parking burned a retry slot for a message never attempted"
    assert row.last_error == "no adapter for this channel"

    # ...and it is revivable, which is the whole point of not calling it terminal.
    revived = outbox.revive_undeliverable(c, org, "in_app", now=NOW)
    assert revived == 1
    assert c.execute(text("select status from delivery_outbox where id='ob_pull_surface'")
                     ).scalar() == "queued"


# ── the agent lane against real Postgres ──────────────────────────────────────────────────────
#
# The double above proves the sweep calls the lane and with which agents. It cannot prove the
# lane's SQL, and the lane's SQL is where this goes wrong quietly: `PUSHABLE_CARDS_SQL` is nine
# joins and a ~40-clause authority predicate, and a filter that silently matches nothing looks
# exactly like a filter that correctly matched nothing.
def _register_agent(c, org, agent_id, *, actions=("signals.read",),
                    url="https://agent.example.com/hook", status="active"):
    from sqlalchemy import text
    c.execute(text(
        "insert into agent_registry (id, org_id, agent_id, key_hash, allowed_actions, status, "
        "webhook_url) values (:i, :o, :a, 'x', :acts, :st, :url)"),
        {"i": f"ar_{agent_id}", "o": org, "a": agent_id, "acts": list(actions),
         "st": status, "url": url})


def _insert_card(c, org, card_id, *, band="critical"):
    """A live card with NO authority chain behind it — deliberately.

    Building the nine-join chain by hand would test the seed, not the lane. What matters here is
    that a card the human lane cannot prove is a card the agent lane does not send, and an
    unprovable card is the cheapest possible instance of that.
    """
    from sqlalchemy import text
    c.execute(text(
        "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, "
        "situation, score, expires_at, state) values (:c, :s, :o, 'prescriptive', :b, 'h', "
        "'s', 90, :exp, 'queued')"),
        {"c": card_id, "s": f"sig_{card_id}", "o": org, "b": band,
         "exp": NOW + timedelta(days=1)})


def _agent_rows(c, org):
    from sqlalchemy import text
    return sorted((r.card_id, r.recipient, r.channel_class) for r in c.execute(text(
        "select card_id, recipient, channel_class from delivery_outbox "
        "where org_id=:o and channel='agent_push'"), {"o": org}))


def test_pg_only_a_scoped_executor_with_a_real_url_counts_as_connected(conn):
    """Three clauses, and each one has a failure it prevents.

    ``signals.read`` because the payload the drain builds IS the /v1/signals projection, so
    pushing without it hands a machine, unasked, the data its scope says it may not poll — the
    push being looser than the poll on the same bytes. ``webhook_url <> ''`` because
    ``channels/agent.py`` returns False on an empty url, so such an agent burns all four retry
    slots and lands in ``failed_terminal`` for a message that never had anywhere to go.
    ``status`` because a deactivated agent is not a recipient.
    """
    c, org = conn
    _register_agent(c, org, "agent_ok")
    _register_agent(c, org, "agent_unscoped", actions=("cards.read",))
    _register_agent(c, org, "agent_no_url", url="")
    _register_agent(c, org, "agent_paused", status="revoked")

    assert outbox.connected_executors(c, org) == ["agent_ok"]


def test_pg_the_lane_writes_one_row_per_connected_executor(conn):
    """Fan-out is per agent — which is why 0068 put `recipient` into the outbox dedupe key."""
    c, org = conn
    _register_agent(c, org, "agent_a")
    _register_agent(c, org, "agent_b")
    _insert_card(c, org, "card_1")

    queued = outbox.enqueue_agent_push(_TxEngine(c), org, "card_1")

    assert queued == 2
    assert _agent_rows(c, org) == [("card_1", "agent_a", "agent"),
                                   ("card_1", "agent_b", "agent")]


def test_pg_an_unscoped_executor_is_never_written_a_row(conn):
    """The scope check has to live in the WRITER, not only in the caller's gate.

    An org can hold both kinds of agent at once, and it is the common shape: one integration with
    `signals.read`, one narrower one without. Gating the lane on "this org has SOME connected
    executor" and then fanning out to every active row would push to the narrower one too — the
    leak arriving through the org that legitimately qualified.
    """
    c, org = conn
    _register_agent(c, org, "agent_scoped")
    _register_agent(c, org, "agent_unscoped", actions=("cards.read",))
    _insert_card(c, org, "card_1")

    outbox.enqueue_agent_push(_TxEngine(c), org, "card_1")

    assert [row[1] for row in _agent_rows(c, org)] == ["agent_scoped"]


def test_pg_a_card_the_human_lane_will_not_queue_is_not_queued_to_an_agent(conn):
    """The property the whole lane turns on, with a discriminator so the zero means something.

    ``card_1`` is live, unexpired, critical and this org has a connected executor — everything
    except a provable authority chain, which is exactly what ``PUSHABLE_CARDS_SQL`` demands. The
    human lane queues nothing for it, and the lane must not be the looser of the two.

    The second half is what makes this a test rather than a tautology: ``enqueue_agent_push`` on
    the SAME card writes a row immediately. So the lane's zero comes from the eligibility gate,
    not from a mis-seeded agent or a query that never matches anything.
    """
    c, org = conn
    _register_agent(c, org, "agent_a")
    _insert_card(c, org, "card_1")
    engine = _TxEngine(c)

    assert outbox.enqueue_pending(engine, org, "slack")["queued"] == 0
    assert outbox.enqueue_agent_lane(
        engine, org, agents=["agent_a"], eval_time=NOW) == {"queued": 0, "cards": 0}
    assert _agent_rows(c, org) == []

    assert outbox.enqueue_agent_push(engine, org, "card_1") == 1, (
        "the agent and the writer are live — the zero above was the gate, not the seed")


def test_pg_an_org_with_no_executor_writes_nothing_at_all(conn):
    """Turning a dormant path on must not start sending to anybody who did not register.

    ``agents`` empty is an early return, so this holds even for an org whose cards WOULD qualify.
    """
    c, org = conn
    _insert_card(c, org, "card_1")
    engine = _TxEngine(c)

    assert outbox.connected_executors(c, org) == []
    assert outbox.enqueue_agent_lane(engine, org, agents=[], eval_time=NOW)["queued"] == 0
    assert _agent_rows(c, org) == []


def test_pg_the_eligibility_query_executes_and_selects_by_authority(conn):
    """`PUSHABLE_CARDS_SQL` has to run in Postgres, not merely look like SQL.

    The lane returning 0 for the right reason and 0 because its nine joins do not resolve are
    indistinguishable from the caller, and the second one is what a copy-paste of a select list
    produces. This runs the lane's own statement and asserts the shape of the answer.
    """
    from sqlalchemy import text
    c, org = conn
    _insert_card(c, org, "card_1")

    rows = c.execute(text("select k.card_id " + outbox.PUSHABLE_CARDS_SQL + "order by k.card_id"),
                     {"o": org, "authority_time": NOW}).fetchall()

    assert rows == [], "an unprovable card is not pushable"
    assert c.execute(text("select count(*) from cards where org_id=:o and card_id='card_1'"),
                     {"o": org}).scalar() == 1, "and it is the AUTHORITY that excluded it"


def test_pg_a_second_pass_re_enqueues_nothing_and_a_new_agent_still_catches_up(conn):
    """Idempotence, and the case it must not buy at the cost of: an agent registered LATER.

    The skip is per (card, agent), not per card, so a card already delivered to `agent_a` still
    reaches `agent_b` on the tick after `agent_b` registers. Skipping per card would mean an
    integration added on Tuesday never sees anything decided on Monday.
    """
    c, org = conn
    _register_agent(c, org, "agent_a")
    _insert_card(c, org, "card_1")
    engine = _TxEngine(c)
    outbox.enqueue_agent_push(engine, org, "card_1")
    assert len(_agent_rows(c, org)) == 1

    assert outbox.enqueue_agent_push(engine, org, "card_1") == 0, "the unique index holds"

    _register_agent(c, org, "agent_b")
    assert outbox.enqueue_agent_push(engine, org, "card_1") == 1
    assert [row[1] for row in _agent_rows(c, org)] == ["agent_a", "agent_b"]
