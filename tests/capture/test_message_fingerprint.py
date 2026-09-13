"""SCREEN_INTEL_P2 §3.3 / acceptance (5) at fingerprint level — one message, two copies, one claim.

    pytest tests/capture/test_message_fingerprint.py -q

Hermetic half on SQLite (keys + claim semantics); the `pg` half runs the same scenarios on the real
`message_fingerprints` table from migration 0144, including the advisory-lock path.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.capture.screen.fingerprint import (
    BODY_KEY_CHARS, SAME_MESSAGE_PREFIX, MessageKey, body_key, candidate_fps, claim,
    claim_messages, lookup, message_fp, sender_key_for, utc_minute, write_same_message_ref)

ORG = "org_fp"
T = datetime(2026, 9, 13, 10, 15, 42, tzinfo=timezone.utc)
BODY = "Hi Priya — we'll send the proposal by Friday.\n\nOn Mon, Sep 8, 2026 at 9:00 AM Priya wrote:\n> can you share pricing?"
SENDER = "rohit@genios.ai"


# ── pure keys ────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.unit
def test_quoted_history_and_whitespace_do_not_change_the_body_key():
    live_only = "Hi   Priya — we'll send the proposal\nby Friday."
    assert body_key(BODY) == body_key(live_only)
    assert "pricing" not in body_key(BODY)


@pytest.mark.unit
def test_body_key_is_nfkc_lowered_and_capped():
    assert body_key("ＡＣＭＥ  Deal") == "acme deal"          # full-width → ASCII via NFKC
    assert len(body_key("x" * 1000)) == BODY_KEY_CHARS


@pytest.mark.unit
def test_sender_key_prefers_email_then_linkedin_then_name():
    assert sender_key_for(email="  Rohit@Genios.AI ", name="Rohit") == "rohit@genios.ai"
    assert sender_key_for(linkedin_url="https://in.linkedin.com/in/Priya-S/?trk=x", name="Priya") \
        == "li:https://www.linkedin.com/in/priya-s"
    assert sender_key_for(name="Priya  S.") == "priya s"
    assert sender_key_for() == ""


@pytest.mark.unit
def test_the_fingerprint_is_per_utc_minute_and_version_bound():
    ist = T.astimezone(timezone(timedelta(hours=5, minutes=30)))
    assert utc_minute(ist) == "2026-09-13T10:15"
    assert message_fp(SENDER, T, BODY) == message_fp(SENDER, ist.replace(second=3), BODY)
    assert message_fp(SENDER, T, BODY) != message_fp(SENDER, T + timedelta(minutes=1), BODY)
    assert len(message_fp(SENDER, None, BODY)) == 64


@pytest.mark.unit
def test_candidates_cover_minus_one_zero_plus_one():
    cands = candidate_fps(SENDER, T, BODY)
    assert cands == [message_fp(SENDER, T, BODY),
                     message_fp(SENDER, T - timedelta(minutes=1), BODY),
                     message_fp(SENDER, T + timedelta(minutes=1), BODY)]
    assert candidate_fps(SENDER, None, BODY) == [message_fp(SENDER, None, BODY)]


# ── claims (both orders, ±1 min) ─────────────────────────────────────────────────────────────────
def _sqlite():
    engine = create_engine("sqlite://")
    with engine.begin() as c:
        c.execute(text(
            "create table message_fingerprints (org_id text, fp text, source text, event_id text, "
            "delta_key text, seen_at text, primary key (org_id, fp, source))"))
        c.execute(text(
            "create table graph_source_refs (source_ref_id text primary key, org_id text, "
            "fact_version_id text, edge_version_id text, observation_id text, event_id text, "
            "source text, source_object_id text, source_field_path text, evidence text, "
            "independence_group text, extractor_version text, mapping_version text)"))
        c.execute(text("create table source_events (org_id text, event_id text, "
                       "source_object_id text)"))
    return engine


def _scenario(engine, org: str, first: tuple[str, str, datetime], second: tuple[str, str, datetime]):
    """Two copies of one message: returns (canonical seen by 1st, canonical seen by 2nd, fp2)."""
    (src1, ev1, ts1), (src2, ev2, ts2) = first, second
    with engine.begin() as c:
        got1 = claim_messages(c, org, [MessageKey(SENDER, ts1, BODY)], src1, ev1)
    with engine.begin() as c:
        got2 = claim_messages(c, org, [MessageKey(SENDER, ts2, BODY)], src2, ev2,
                              delta_key="dev1|sess|9")
    fp2 = message_fp(SENDER, ts2, BODY)
    return got1[message_fp(SENDER, ts1, BODY)], got2[fp2], fp2


@pytest.mark.unit
@pytest.mark.parametrize("skew", [0, 1, -1])
def test_connector_then_screen_keeps_the_connector_copy(skew):
    engine = _sqlite()
    c1, c2, _ = _scenario(engine, ORG, ("gmail", "ev_gmail", T),
                          ("screen_session", "ev_screen", T + timedelta(minutes=skew)))
    assert (c1, c2) == ("ev_gmail", "ev_gmail")


@pytest.mark.unit
@pytest.mark.parametrize("skew", [0, 1, -1])
def test_screen_then_connector_keeps_the_screen_copy(skew):
    engine = _sqlite()
    c1, c2, _ = _scenario(engine, ORG, ("screen_session", "ev_screen", T),
                          ("gmail", "ev_gmail", T + timedelta(minutes=skew)))
    assert (c1, c2) == ("ev_screen", "ev_screen")


@pytest.mark.unit
def test_two_minutes_apart_is_two_messages():
    engine = _sqlite()
    c1, c2, _ = _scenario(engine, ORG, ("gmail", "ev_gmail", T),
                          ("screen_session", "ev_screen", T + timedelta(minutes=2)))
    assert (c1, c2) == ("ev_gmail", "ev_screen")


@pytest.mark.unit
def test_a_retry_of_the_same_source_is_a_noop_and_other_orgs_are_unseen():
    engine = _sqlite()
    fp = message_fp(SENDER, T, BODY)
    with engine.begin() as c:
        assert claim(c, ORG, [fp], "gmail", "ev1") == {fp: "ev1"}
        assert claim(c, ORG, [fp], "gmail", "ev1") == {fp: "ev1"}
        assert claim(c, "other_org", [fp], "screen_session", "ev9") == {fp: "ev9"}
        assert c.execute(text("select count(*) from message_fingerprints")).scalar() == 2
        assert lookup(c, ORG, [fp]) == {fp: "ev1"}


@pytest.mark.unit
def test_the_duplicate_leaves_exactly_one_same_message_ref():
    engine = _sqlite()
    _, canonical, fp = _scenario(engine, ORG, ("gmail", "ev_gmail", T),
                                 ("screen_session", "ev_screen", T))
    with engine.begin() as c:
        c.execute(text("insert into source_events values (:o, 'ev_screen', 'thread#9#in')"),
                  {"o": ORG})
        first = write_same_message_ref(c, org_id=ORG, fp=fp, canonical_event_id=canonical,
                                       duplicate_source="screen_session",
                                       duplicate_event_id="ev_screen")
        again = write_same_message_ref(c, org_id=ORG, fp=fp, canonical_event_id=canonical,
                                       duplicate_source="screen_session",
                                       duplicate_event_id="ev_screen")
        rows = c.execute(text("select event_id, source, source_object_id, independence_group, "
                              "fact_version_id from graph_source_refs")).fetchall()
    assert first and again is None
    assert [tuple(r) for r in rows] == [
        ("ev_gmail", "screen_session", "thread#9#in", SAME_MESSAGE_PREFIX + fp, None)]


# ── group B's call shape: all three minute fps of ONE message, no alternates ─────────────────────
def _b_style(conn, org, ts, source, event_id):
    return claim(conn, org, candidate_fps(SENDER, ts, BODY), source, event_id)


def _check_b_style(engine, org):
    fps_at = lambda ts: candidate_fps(SENDER, ts, BODY)       # noqa: E731
    # screen saw it at T+1; the Gmail lane claims all three of its own minute fps at T
    with engine.begin() as c:
        claim_messages(c, org, [MessageKey(SENDER, T + timedelta(minutes=1), BODY)],
                       "screen_session", "ev_scr_b")
    with engine.begin() as c:
        got = _b_style(c, org, T, "gmail", "ev_gm_b")
        rows = c.execute(text("select fp, source from message_fingerprints where org_id=:o"),
                         {"o": org}).fetchall()
    fp0, fp_minus, fp_plus = fps_at(T)
    assert got == {fp0: "ev_gm_b", fp_minus: "ev_gm_b", fp_plus: "ev_scr_b"}
    assert any(v != "ev_gm_b" for v in got.values())          # → a duplicate: do not extract
    # the claimed-by-other fp is NOT re-inserted; the rest are
    assert sorted((r.fp, r.source) for r in rows) == sorted(
        [(fp_plus, "screen_session"), (fp0, "gmail"), (fp_minus, "gmail")])
    # a retry of the same Gmail event never makes it its own duplicate
    with engine.begin() as c:
        assert _b_style(c, org, T, "gmail", "ev_gm_b") == got


def _check_b_style_fresh(engine, org):
    with engine.begin() as c:
        got = _b_style(c, org, T, "gmail", "ev_alone")
        again = _b_style(c, org, T, "gmail", "ev_alone")
    assert set(got.values()) == {"ev_alone"} and again == got


def _check_lookup_is_read_only(engine, org):
    """Group A's screen-second path: the promoter LOOKS before landing a screen message."""
    with engine.begin() as c:
        claim(c, org, [message_fp(SENDER, T, BODY)], "gmail", "ev_gm_l")
    with engine.begin() as c:
        before = c.execute(text("select count(*) from message_fingerprints where org_id=:o"),
                           {"o": org}).scalar()
        screen_fps = candidate_fps(SENDER, T + timedelta(minutes=1), BODY)
        found = lookup(c, org, screen_fps)
        assert found == {screen_fps[1]: "ev_gm_l"}          # the −1 minute fp is Gmail's
        assert lookup(c, org, ["0" * 64]) == {}
        after = c.execute(text("select count(*) from message_fingerprints where org_id=:o"),
                          {"o": org}).scalar()
    assert before == after == 1


@pytest.mark.unit
def test_lookup_finds_the_gmail_claim_and_writes_nothing():
    _check_lookup_is_read_only(_sqlite(), ORG)


@pytest.mark.pg
def test_pg_lookup_finds_the_gmail_claim_and_writes_nothing(pg_engine):
    engine, org = pg_engine
    _check_lookup_is_read_only(engine, org)


@pytest.mark.unit
def test_b_style_three_minute_fps_find_the_screen_copy_and_insert_the_rest():
    _check_b_style(_sqlite(), ORG)


@pytest.mark.unit
def test_b_style_a_fresh_message_is_never_its_own_duplicate():
    _check_b_style_fresh(_sqlite(), ORG)


@pytest.mark.unit
def test_the_ref_helper_logs_and_returns_none_instead_of_raising(caplog):
    engine = create_engine("sqlite://")            # no graph_source_refs table at all
    with engine.begin() as c:
        c.execute(text("create table source_events (org_id text, event_id text, "
                       "source_object_id text)"))
        assert write_same_message_ref(c, org_id=ORG, fp="f" * 64, canonical_event_id="ev1",
                                      duplicate_source="gmail", duplicate_event_id="ev2") is None
        assert c.execute(text("select 1")).scalar() == 1      # caller's transaction still usable
    assert "same_message ref not written" in caplog.text


# ── real Postgres ────────────────────────────────────────────────────────────────────────────────
@pytest.fixture
def pg_engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set")
    from genios_engine.platform.db import get_engine
    engine = get_engine(url)
    with engine.begin() as c:
        org = c.execute(text("select id from orgs order by id limit 1")).scalar()
        c.execute(text("delete from message_fingerprints where org_id = :o"), {"o": org})
        c.execute(text("delete from graph_source_refs where org_id = :o "
                       "and independence_group like 'same_message:%'"), {"o": org})
    yield engine, org
    with engine.begin() as c:
        c.execute(text("delete from message_fingerprints where org_id = :o"), {"o": org})
        c.execute(text("delete from graph_source_refs where org_id = :o "
                       "and independence_group like 'same_message:%'"), {"o": org})


@pytest.mark.pg
@pytest.mark.parametrize("order", ["connector_first", "screen_first"])
@pytest.mark.parametrize("skew", [0, 1, -1])
def test_pg_either_order_one_canonical_one_ref(pg_engine, order, skew):
    engine, org = pg_engine
    gmail = ("gmail", "ev_gmail_pg", T)
    screen = ("screen_session", "ev_screen_pg", T + timedelta(minutes=skew))
    first, second = (gmail, screen) if order == "connector_first" else (screen, gmail)
    c1, c2, fp2 = _scenario(engine, org, first, second)
    assert c1 == c2 == first[1]
    with engine.begin() as c:
        write_same_message_ref(c, org_id=org, fp=fp2, canonical_event_id=c2,
                               duplicate_source=second[0], duplicate_event_id=second[1],
                               duplicate_source_object_id="copy-1")
        write_same_message_ref(c, org_id=org, fp=fp2, canonical_event_id=c2,
                               duplicate_source=second[0], duplicate_event_id=second[1],
                               duplicate_source_object_id="copy-1")
        refs = c.execute(text(
            "select event_id, independence_group, evidence from graph_source_refs "
            "where org_id = :o and independence_group like 'same_message:%'"),
            {"o": org}).fetchall()
        fps = c.execute(text("select count(*) from message_fingerprints where org_id = :o"),
                        {"o": org}).scalar()
    # one canonical claim row; the copy leaves a ref, not a second claim
    assert len(refs) == 1 and fps == 1
    assert refs[0].event_id == first[1]
    assert refs[0].independence_group == SAME_MESSAGE_PREFIX + fp2
    assert refs[0].evidence["duplicate_event_id"] == second[1]


@pytest.mark.pg
def test_pg_b_style_three_minute_fps(pg_engine):
    engine, org = pg_engine
    _check_b_style(engine, org)


@pytest.mark.pg
def test_pg_b_style_fresh_message(pg_engine):
    engine, org = pg_engine
    _check_b_style_fresh(engine, org)


@pytest.mark.pg
def test_pg_ref_helper_survives_the_orgs_fk(pg_engine, caplog):
    """`graph_source_refs.org_id` references `orgs`; an unknown org must not raise into capture."""
    engine, org = pg_engine
    with engine.begin() as c:
        assert write_same_message_ref(c, org_id="org_that_does_not_exist", fp="a" * 64,
                                      canonical_event_id="ev1", duplicate_source="gmail",
                                      duplicate_event_id="ev2") is None
        # the SAVEPOINT rolled back alone — the caller's transaction is still usable
        assert claim(c, org, ["b" * 64], "gmail", "ev_after") == {"b" * 64: "ev_after"}
    assert "same_message ref not written" in caplog.text


@pytest.mark.pg
def test_pg_two_open_transactions_cannot_both_be_canonical(pg_engine):
    """The advisory lock: the second claimer waits for the first to commit, then sees it."""
    import threading

    engine, org = pg_engine
    results: dict[str, str] = {}
    fp = message_fp(SENDER, T, BODY)
    first_holds = threading.Event()

    def screen():
        with engine.begin() as c:
            results["screen"] = claim(c, org, [fp], "screen_session", "ev_s")[fp]
            first_holds.set()
            import time
            time.sleep(0.5)            # hold the lock with the row uncommitted

    t = threading.Thread(target=screen)
    t.start()
    first_holds.wait(5)
    with engine.begin() as c:
        results["gmail"] = claim(c, org, [fp], "gmail", "ev_g")[fp]
    t.join()
    assert results == {"screen": "ev_s", "gmail": "ev_s"}
