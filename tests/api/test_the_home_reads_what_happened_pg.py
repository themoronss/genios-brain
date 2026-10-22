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


# ── B8 · the Screen page: how each item was read, what it led to, and the seat's week ───────────

#: A Wednesday, as the seat's week [Mon 00:00, next Mon 00:00) is read (`followups.week_bounds`).
WEEK_NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)
ME, OTHER = "seat_me", "seat_other"


def _promoted(c, org, seat, event_ids, *, days_ago=0):
    c.execute(text(
        "insert into screen_session_deltas (org_id, device_id, session_key, message_watermark, seat_id, app, "
        "payload_enc, status, promoted_at, event_ids) values (:o, 'dev', :k, 1, :s, 'gmail', '\\x00'::bytea, "
        "'promoted', :at, :ids)"),
        {"o": org, "k": uuid.uuid4().hex, "s": seat, "ids": list(event_ids),
         "at": WEEK_NOW - timedelta(days=days_ago)})


def _screen_item(c, org, seat, subject, *, thread="wa:priya", app="whatsapp"):
    """A follow-up the screen caught, written on `subject` the way `screen_memory` writes it."""
    fid, obs = f"fu_{uuid.uuid4().hex[:12]}", f"obs_{uuid.uuid4().hex[:12]}"
    at = WEEK_NOW - timedelta(days=1)
    c.execute(text(
        "insert into graph_observations (observation_id, org_id, subject_node_id, kind, occurred_at, "
        "created_by_event_id, created_at) values (:i, :o, :n, 'screen.ask', :at, :e, :at)"),
        {"i": obs, "o": org, "n": subject, "e": _event(c, org, "screen_session"), "at": at})
    c.execute(text(
        "insert into screen_followups (id, org_id, seat_id, thread_key, app, kind, text, topic_key, created_at, "
        "updated_at, subject_node_id, observation_id, graph_written_at) values (:i, :o, :s, :t, :app, 'ask', "
        "'send the quote', :i, :at, :at, :n, :obs, :at)"),
        {"i": fid, "o": org, "s": seat, "t": thread, "app": app, "n": subject, "obs": obs, "at": at})
    return fid


def _week_cards(c, org):
    """Two people seen on screens (one on mine, one on theirs), one never seen, and their cards."""
    on_mine, on_theirs, plain = (_node(c, org, "person", 30) for _ in range(3))
    mine, theirs = _screen_item(c, org, ME, on_mine), _screen_item(c, org, OTHER, on_theirs)
    cards = {
        "mine": _card(c, org, "high", subject=on_mine, assignee=ME),             # fed by my item
        "theirs_to_me": _card(c, org, "high", subject=on_theirs, assignee=ME),   # another seat's screen
        "plain": _card(c, org, "high", subject=plain, assignee=ME),              # no screen behind it
        "mine_to_other": _card(c, org, "high", subject=on_mine, assignee=OTHER),  # not my card
        "mine_as_recipient": _card(c, org, "high", subject=on_mine),             # reaches me as a recipient
        "theirs": _card(c, org, "high", subject=on_theirs, assignee=OTHER),      # theirs, fed by theirs
    }
    c.execute(text("update cards set created_at = :at where card_id = any(:ids)"),
              {"at": WEEK_NOW, "ids": list(cards.values())})
    c.execute(text(
        "insert into card_recipients (org_id, card_id, seat_id, accountability, scope_kind, scope_key, source) "
        "values (:o, :c, :s, 'covers', 'account', 'acme', 'admin_declared')"),
        {"o": org, "c": cards["mine_as_recipient"], "s": ME})
    return mine, theirs, cards


def test_the_seat_week_counts_its_own_screen_and_the_cards_it_fed(pg_store, org):
    from genios_engine.reason.moments import followups as F
    from genios_engine.reason.moments import screen_insight as SI
    with pg_store.engine.begin() as c:
        events = [_event(c, org, "screen_session") for _ in range(4)]
        _promoted(c, org, ME, events[:2])
        _promoted(c, org, ME, events[2:3], days_ago=9)              # last week's promotion
        _promoted(c, org, OTHER, events[3:])
        _week_cards(c, org)
        for kind, n, days_ago in ((SI.COUNTER_KIND, 3, 0), (SI.RULED_KIND, 2, 1), (SI.SKIPPED_KIND, 4, 2),
                                  (SI.SKIPPED_KIND, 5, 9), (SI.UNVERIFIED_KIND, 7, 0)):
            c.execute(text("insert into rate_counters (scope_key, kind, window_start, count) values (:k, :kind, :d, :n)"),
                      {"k": f"{org}:{ME}", "kind": kind, "d": (WEEK_NOW - timedelta(days=days_ago)).date(), "n": n})
    r = F.weekly_report(pg_store.engine, org_id=org, seat_id=ME, capability_id=SI.CAPABILITY_ID, now=WEEK_NOW)
    assert (r["threads_to_memory"], r["cards_from_screen"]) == (2, 2)
    assert (r["screens_read"], r["screens_skipped"]) == (9, 4), "read = model + rule + skipped, this week only"
    r = F.weekly_report(pg_store.engine, org_id=org, seat_id=OTHER, capability_id=SI.CAPABILITY_ID, now=WEEK_NOW)
    assert (r["threads_to_memory"], r["cards_from_screen"], r["screens_read"]) == (1, 1, 0)


def test_each_item_names_the_cards_it_fed_and_its_popup_and_why_it_is_kept(pg_store, org):
    from genios_engine.reason.moments import followups as F
    with pg_store.engine.begin() as c:
        mine, _theirs, cards = _week_cards(c, org)
        personal = _screen_item(c, org, ME, None, thread="wa:mom")
        c.execute(text("update screen_followups set subject_node_id = null, graph_written_at = null where id = :i"),
                  {"i": personal})
        c.execute(text("insert into screen_thread_verdicts (org_id, seat_id, thread_key, work, memory, judged_at) "
                       "values (:o, :s, 'wa:mom', false, false, :at)"), {"o": org, "s": ME, "at": WEEK_NOW})
        c.execute(text(
            "insert into moments (moment_id, org_id, seat_id, origin, kind, priority, capability_id, "
            "capability_version, headline, actions, evidence, display, created_at, expires_at) values ('mom_1', :o, "
            ":s, 'server', 'advice', 'normal', 'moment.screen_insight', '4', 'h', cast(:a as jsonb), '[]'::jsonb, "
            "true, :at, :at + interval '10 minutes')"),
            {"o": org, "s": ME, "at": WEEK_NOW,
             "a": '[{"action": "useful", "payload": {"followup_id": "%s"}}]' % mine})
    items = {f["id"]: f for f in F.listing(pg_store.engine, org_id=org, seat_id=ME, status="all",
                                           now=WEEK_NOW)["followups"]}
    assert set(items) == {mine, personal}, "only my own screen's items"
    assert sorted(items[mine]["card_ids"]) == sorted([cards["mine"], cards["mine_as_recipient"]])
    assert items[mine]["moment_id"] == "mom_1" and items[personal]["moment_id"] is None
    assert items[mine]["remember"] is True and items[mine]["graph_written_at"] is not None
    assert items[personal]["remember"] is False and items[personal]["keep_reason"].startswith("Temporary")
    assert items[personal]["card_ids"] == []
    with pg_store.engine.connect() as c:
        assert F.screen_items(c, org_id=org, card_id=cards["mine"], seat_id=ME) == [
            {"followup_id": mine, "app": "whatsapp"}]
        assert F.screen_items(c, org_id=org, card_id=cards["mine"], seat_id=OTHER) == [], "never another seat's screen"
        assert F.screen_items(c, org_id=org, card_id=cards["mine"], seat_id=None) == []
        assert F.screen_items(c, org_id=org, card_id=cards["plain"], seat_id=ME) == []


def test_the_first_read_path_is_kept_and_the_due_words_move_with_the_due(pg_store, org):
    from genios_engine.reason.moments import followups as F
    due = WEEK_NOW + timedelta(days=1)
    one = dict(engine=pg_store.engine, org_id=org, seat_id=ME, kind="ask", note="send the quote", who="Priya",
               thread_key="wa:priya", app="whatsapp", topic="t1", tz_name="Asia/Kolkata", now=WEEK_NOW)
    first = F.upsert(**one, due_at=due, read_by="rule", due_phrase="kal tak")
    assert first is not None
    F.upsert(**one, due_at=None, read_by="hourly_batch", due_phrase=None)          # a later, dateless sighting
    (row,) = F.listing(pg_store.engine, org_id=org, seat_id=ME, status="all", now=WEEK_NOW)["followups"]
    assert (row["read_by"], row["due_phrase"]) == ("rule", "kal tak")
    F.upsert(**one, due_at=due + timedelta(days=2), read_by="quick_read", due_phrase="by Friday")
    (row,) = F.listing(pg_store.engine, org_id=org, seat_id=ME, status="all", now=WEEK_NOW)["followups"]
    assert (row["read_by"], row["due_phrase"]) == ("rule", "by Friday")
    F.upsert(**{**one, "topic": "t2"}, due_at=None, read_by="quick_read", due_phrase="someday")
    rows = {f["id"]: f for f in F.listing(pg_store.engine, org_id=org, seat_id=ME, status="all",
                                          now=WEEK_NOW)["followups"]}
    assert rows[F.followup_id(org, ME, "t2")]["due_phrase"] is None, "no due parsed, so no due words"
    with pytest.raises(ValueError):
        F.upsert(**{**one, "topic": "t3"}, due_at=None, read_by="guess")


def test_the_card_route_lists_the_viewers_screen_items(pg_store, monkeypatch, org):
    """The call site: `GET /cards/{id}` attaches `screen_items` for the seat reading it."""
    from types import SimpleNamespace
    from genios_engine.api import routes
    with pg_store.engine.begin() as c:
        mine, _theirs, cards = _week_cards(c, org)
    monkeypatch.setattr(routes, "_graph", pg_store)
    monkeypatch.setattr(routes, "_require_l5", lambda: None)
    monkeypatch.setattr(routes, "_owns_authoritative_card", lambda card_id, org_id: {"card_id": card_id})
    monkeypatch.setattr(routes, "_card_intelligence", lambda org_id, card: (None, None, None))
    for seat, expected in ((ME, [{"followup_id": mine, "app": "whatsapp"}]), (OTHER, [])):
        ctx = SimpleNamespace(org_id=org, seat_id=seat, sees_org_queue=True)
        assert routes.get_card(cards["mine"], ctx=ctx)["screen_items"] == expected
