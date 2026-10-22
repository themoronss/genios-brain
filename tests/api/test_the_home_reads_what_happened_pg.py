"""GeniOS-010 B3–B9 · the dashboard home's numbers come from what happened, against real Postgres.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://localhost:5432/genios_scratch \\
        pytest tests/api/test_the_home_reads_what_happened_pg.py -q

`speedrun008/GeniOS-010/02-DASHBOARD-HOME/05-BRAIN-WORK.md` names what the redesigned home cannot show
truthfully until the brain serves it. Each test seeds the rows the number is counted from, with rows that
must NOT count beside them (last week, another seat's screen, a domain switched off), and reads the route:

  * B4 — `/v1/expertise/domains` marks a domain active for THIS workspace only (`l3_activation`);
  * B5 — `home-summary.changes`: facts learned and corrected, people and companies new and updated;
  * B6 — `home-summary.cards_7d`: this week's cards by band over every state, handled ones too;
  * B7 — nothing decided reads "—", never "0% Policy-safe actions";
  * B9 — the hard-coded `snapshot.notice` is gone;
  * B3 — `/v1/insights/stats` serves `card_action_rate`, not a second `intervention_rate`;
  * B8 — `/v1/seats/me/weekly-report`: the seat's screen sent to memory, and the cards it stands behind.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.pg


@pytest.fixture()
def org(pg_store):
    org_id = f"org_home_{uuid.uuid4().hex[:10]}"
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'Home reads')"), {"o": org_id})
    yield org_id
    with pg_store.engine.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": org_id})


def _event(c, org, source, event_id=None):
    event_id = event_id or f"ev_{uuid.uuid4().hex[:12]}"
    c.execute(text(
        "insert into source_events (event_id, org_id, connection_id, source, object_type, source_object_id, "
        "dedup_key, actor, occurred_at) values (:e, :o, 'conn_x', :s, 'message', :e, :e, '{}'::jsonb, now())"),
        {"e": event_id, "o": org, "s": source})
    return event_id


def _node(c, org, node_type, days_old):
    node_id = f"n_{uuid.uuid4().hex[:12]}"
    c.execute(text(
        "insert into graph_nodes (node_id, org_id, node_type, display_name, valid_from) "
        "values (:n, :o, :t, :n, now() - make_interval(days => :d))"),
        {"n": node_id, "o": org, "t": node_type, "d": days_old})
    return node_id


def _fact(c, org, node, *, days_old=0, status="active", superseded_days_ago=None, event_id=None):
    fid = f"f_{uuid.uuid4().hex[:12]}"
    c.execute(text(
        "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, value, value_type, "
        "status, occurred_at, created_at, valid_to, created_by_event_id) values (:fv, :f, :o, :n, 'person.title', "
        "'\"CFO\"'::jsonb, 'string', :st, now(), now() - make_interval(days => :d), "
        "case when cast(:sd as int) is null then null else now() - make_interval(days => cast(:sd as int)) end, :ev)"),
        {"fv": f"fv_{fid}", "f": fid, "o": org, "n": node, "st": status, "d": days_old,
         "sd": superseded_days_ago, "ev": event_id})


def _card(c, org, band, *, days_old=0, state="surfaced", subject=None, assignee=None):
    signal_id, card_id = f"sig_{uuid.uuid4().hex[:12]}", f"card_{uuid.uuid4().hex[:12]}"
    c.execute(text(
        "insert into signals (signal_id, org_id, rule_id, subject_node_id, score, reason_code, eval_time) "
        "values (:s, :o, 'r', :n, 50, 'rc', now())"), {"s": signal_id, "o": org, "n": subject or "n_none"})
    c.execute(text(
        "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, score, "
        "expires_at, state, assignee, created_at) values (:c, :s, :o, 'prescriptive', :b, 'h', 's', 50, "
        "now() + interval '3 days', :st, :a, now() - make_interval(days => :d))"),
        {"c": card_id, "s": signal_id, "o": org, "b": band, "st": state, "a": assignee, "d": days_old})
    return card_id


def _summary(pg_store, monkeypatch, org):
    from genios_engine.api import home_routes
    monkeypatch.setattr(home_routes, "_graph", pg_store)
    return home_routes.home_summary(org_id=org, org=org)


# ── B6 · cards raised this week ─────────────────────────────────────────────────────────────────

def test_cards_this_week_are_counted_by_band_over_every_state(pg_store, monkeypatch, org):
    with pg_store.engine.begin() as c:
        _card(c, org, "critical")
        _card(c, org, "high")
        _card(c, org, "high", state="resolved")          # handled this week — still raised this week
        _card(c, org, "standard", state="expired")
        _card(c, org, "high", days_old=10)               # last week's
    assert _summary(pg_store, monkeypatch, org)["cards_7d"] == {"critical": 1, "high": 2, "standard": 1}


# ── B5 · what changed this week ─────────────────────────────────────────────────────────────────

def test_what_memory_learned_and_corrected_this_week(pg_store, monkeypatch, org):
    with pg_store.engine.begin() as c:
        gmail, slack = _event(c, org, "gmail"), _event(c, org, "slack")
        known = _node(c, org, "person", days_old=30)     # known before the week, learned something in it
        _node(c, org, "company", days_old=30)            # known before, nothing new — not "updated"
        new = _node(c, org, "person", days_old=0)
        _node(c, org, "thread", days_old=0)              # not a person or a company
        _fact(c, org, known, event_id=gmail)
        _fact(c, org, new, event_id=gmail)
        _fact(c, org, new, event_id=slack)
        _fact(c, org, known, days_old=20, event_id=gmail)   # learned last month, from the same source
        _fact(c, org, known, days_old=20, status="superseded", superseded_days_ago=1)   # corrected this week
        _fact(c, org, known, days_old=30, status="superseded", superseded_days_ago=12)  # corrected before
    changes = _summary(pg_store, monkeypatch, org)["changes"]
    assert changes == {"facts_added": 3, "facts_updated": 1, "entities_added": 1, "entities_updated": 1,
                       "by_source": {"gmail": 2, "slack": 1}}


# ── B7 + B9 ─────────────────────────────────────────────────────────────────────────────────────

def test_nothing_decided_is_not_graded_and_the_notice_is_gone(pg_store, monkeypatch, org):
    snapshot = _summary(pg_store, monkeypatch, org)["snapshot"]
    policy = next(h for h in snapshot["health"] if h["label"] == "Policy-safe actions")
    assert policy["value"] == "—", "a workspace that decided nothing read '0% Policy-safe actions'"
    assert "notice" not in snapshot
    with pg_store.engine.begin() as c:
        c.execute(text("insert into decisions (decision_id, org_id, envelope) values (:d, :o, '{}'::jsonb)"),
                  {"d": f"dec_{uuid.uuid4().hex[:10]}", "o": org})
    snapshot = _summary(pg_store, monkeypatch, org)["snapshot"]
    assert next(h for h in snapshot["health"] if h["label"] == "Policy-safe actions")["value"] == "100%"


def test_one_unreadable_tile_does_not_zero_the_rest(pg_store, monkeypatch, org):
    """Each read is its own savepoint. Without one, the first failing read aborts the transaction and every
    read after it answers 0 — a home that looks empty because one tile's query broke."""
    from genios_engine.api import home_routes
    with pg_store.engine.begin() as c:
        gmail = _event(c, org, "gmail")
        _fact(c, org, _node(c, org, "person", days_old=0), event_id=gmail)
        _card(c, org, "critical")
    cards_sql = home_routes._CARDS_7D
    monkeypatch.setattr(home_routes, "_CARDS_7D", "select no_such_column from cards where org_id = :o")
    out = _summary(pg_store, monkeypatch, org)                      # a grouped read fails…
    assert out["cards_7d"] == {"critical": 0, "high": 0, "standard": 0}
    assert out["changes"]["facts_added"] == 1, "…and every count after it read 0"
    monkeypatch.setattr(home_routes, "_CARDS_7D", cards_sql)
    monkeypatch.setattr(home_routes, "_ENTITIES_UPDATED_7D", "select no_such_column from graph_nodes where org_id = :o")
    out = _summary(pg_store, monkeypatch, org)                      # a single count fails…
    assert out["changes"]["entities_updated"] == 0
    assert out["changes"]["by_source"] == {"gmail": 1}, "…and the grouped read after it came back empty"
    assert out["cards_7d"]["critical"] == 1


# ── B4 · a domain is active for THIS workspace ──────────────────────────────────────────────────

def test_a_domain_reads_active_only_where_it_is_switched_on(pg_store, monkeypatch, org):
    from genios_engine.api import expertise_routes
    from genios_engine.platform import l3_activation
    monkeypatch.setattr(expertise_routes, "_graph", pg_store)
    authored = {d["id"] for d in expertise_routes._corpus_domains()}
    assert {"sales", "admin"} <= authored
    out = expertise_routes.expertise_domains(org_id=org)
    assert out["active_count"] == 0 and not any(d["active"] for d in out["domains"])
    l3_activation.activate(pg_store.engine, org, domain="admin", by="test")
    out = expertise_routes.expertise_domains(org_id=org)
    assert {d["id"] for d in out["domains"] if d["active"]} == {"admin"}
    assert out["available_count"] == len(authored) - 1
    l3_activation.deactivate(pg_store.engine, org, domain="admin", by="test")
    assert expertise_routes.expertise_domains(org_id=org)["active_count"] == 0


# ── B3 · one name, one number ───────────────────────────────────────────────────────────────────

def test_the_card_action_rate_has_its_own_name(pg_store, monkeypatch, org):
    from genios_engine.api import intelligence_routes
    monkeypatch.setattr(intelligence_routes, "_graph", pg_store)
    with pg_store.engine.begin() as c:
        _card(c, org, "high")
        _card(c, org, "high")
    out = intelligence_routes.insight_stats(days=7, org_id=org)
    assert "intervention_rate" not in out
    assert out["card_action_rate"] == 0.0


def test_the_empty_intervention_summary_stub_is_gone():
    from genios_engine.api.routes import router
    assert "/v1/metrics/intervention_rate/summary" not in {getattr(r, "path", None) for r in router.routes}


# ── B8 · the screen's reasoning lane in the seat's week ─────────────────────────────────────────

def _promoted(c, org, seat, event_ids, *, days_ago=0):
    c.execute(text(
        "insert into screen_session_deltas (org_id, device_id, session_key, message_watermark, seat_id, app, "
        "payload_enc, status, promoted_at, event_ids) values (:o, 'dev', :k, 1, :s, 'gmail', '\\x00'::bytea, "
        "'promoted', :at, :ids)"),
        {"o": org, "k": uuid.uuid4().hex, "s": seat, "ids": list(event_ids),
         "at": WEEK_NOW - timedelta(days=days_ago)})


def _screen_observation(c, org, subject, event_id):
    c.execute(text(
        "insert into graph_observations (observation_id, org_id, subject_node_id, kind, occurred_at, "
        "created_by_event_id, created_at) values (:i, :o, :n, 'screen.ask', :at, :e, :at)"),
        {"i": f"obs_{uuid.uuid4().hex[:12]}", "o": org, "n": subject, "e": event_id,
         "at": WEEK_NOW - timedelta(days=1)})


#: A Wednesday, as the seat's week [Mon 00:00, next Mon 00:00) is read (`followups.week_bounds`).
WEEK_NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


def test_the_seat_week_counts_its_own_screen_and_the_cards_it_stands_behind(pg_store, org):
    from genios_engine.reason.moments import followups as F
    me, other = "seat_me", "seat_other"
    with pg_store.engine.begin() as c:
        mine = [_event(c, org, "screen_session") for _ in range(3)]
        theirs = _event(c, org, "screen_session")
        _promoted(c, org, me, mine[:2])
        _promoted(c, org, me, mine[2:], days_ago=9)                 # last week's promotion
        _promoted(c, org, other, [theirs])
        seen_on_my_screen, seen_on_theirs, plain = (_node(c, org, "person", 30) for _ in range(3))
        _screen_observation(c, org, seen_on_my_screen, mine[0])
        _screen_observation(c, org, seen_on_theirs, theirs)
        cards = [
            _card(c, org, "high", subject=seen_on_my_screen, assignee=me),       # counts
            _card(c, org, "high", subject=seen_on_theirs, assignee=me),          # another seat's screen
            _card(c, org, "high", subject=plain, assignee=me),                   # no screen evidence
            _card(c, org, "high", subject=seen_on_my_screen, assignee=other),    # not this seat's card
            _card(c, org, "high", subject=seen_on_my_screen),                    # reaches me as a recipient
        ]
        c.execute(text("update cards set created_at = :at where card_id = any(:ids)"),
                  {"at": WEEK_NOW, "ids": cards})
        c.execute(text(
            "insert into card_recipients (org_id, card_id, seat_id, accountability, scope_kind, scope_key, source) "
            "values (:o, :c, :s, 'covers', 'account', 'acme', 'admin_declared')"),
            {"o": org, "c": cards[4], "s": me})
    r = F.weekly_report(pg_store.engine, org_id=org, seat_id=me, capability_id="moment.screen_insight",
                        now=WEEK_NOW)
    assert r["threads_to_memory"] == 2
    assert r["screen_cards"] == 2
    r = F.weekly_report(pg_store.engine, org_id=org, seat_id=other, capability_id="moment.screen_insight",
                        now=WEEK_NOW)
    assert r["threads_to_memory"] == 1
    assert r["screen_cards"] == 0, "the other seat's card stands on MY screen's observation, not theirs"
