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
from datetime import datetime, timezone

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
        if "select org_id from org_channels where active" in sql:
            orgs = set(self.world["channels"]) | set(self.world["cards"])
            return _Result((o,) for o in sorted(orgs))
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
    calls: dict[str, list] = {"pending": [], "digest": [], "reminders": [], "linked": []}
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


def world(channels=None, cards=None):
    return {"channels": channels or {}, "cards": cards or {}}


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

    This is production's whole delivery history in one assertion — status `failed_terminal`,
    attempts 1, `last_error='channel unregistered or inactive'` — and it lands identically on
    'in_app', so "queue it to the channel they DO have" would have changed nothing but the
    channel name in the error.
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
    assert row.status == "failed_terminal" and row.attempts == 1
    assert row.last_error == "channel unregistered or inactive"
