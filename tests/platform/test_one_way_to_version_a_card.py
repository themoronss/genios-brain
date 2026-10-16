"""STEP-14 · one way to version a card — the one writer of `cards.signal_id`, and every version says what changed.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/platform/test_one_way_to_version_a_card.py -q

Tree `yc2_w27_s14` M42.C1.L-data.V1.U03 (STEP-14 §8.4 item 1, s14-D2). A file's card lives (`migrations/0220`):
the file's next decision or question re-points it at the file's newest signal — `platform/card_lifecycle.
version_card`, as that module is the one writer of `expired` — and writes ONE `card.versioned` event carrying the
version (`contracts/card_version`): the words it shows, the words before, the signal it carried and the one it
came from, the change, whether it is material. In the caller's transaction. A card the clock, a replacement or a
clearing closed is reopened; one the founder decided (acted, resolved, dismissed, retired) stays decided, and one
an agent holds waits. A guard reads every SQL string in `genios_engine/` and `scripts/` by the AST and fails on any
other statement that sets `cards.signal_id`.
"""
from __future__ import annotations

import ast
import os
import re
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts.card_version import VersionWords, version_of
from tests.platform.test_one_way_to_expire_a_card import ROOT, SCANNED, _outermost_strings

ORG = "card_version_org"
OTHER = "card_version_other"
AT = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
THE_WRITER = "genios_engine/platform/card_lifecycle.py"
#: An UPDATE of `cards` and its SET list — up to the first `where`, `from` or `returning` — read whole.
_UPDATE_CARDS = re.compile(r"\bupdate\s+cards\b(?:\s+(?!set\b)\w+)?\s+set\b(?P<sets>.*?)(?:\bwhere\b|\bfrom\b|\breturning\b|$)",
                           re.IGNORECASE | re.DOTALL)
_SIGNAL_SET = re.compile(r"(?<![.\w])signal_id\s*=", re.IGNORECASE)


def _sets_signal(sql: str) -> int:
    """How many statements in `sql` set `cards.signal_id` in their SET list (a WHERE naming it sets nothing)."""
    return sum(1 for m in _UPDATE_CARDS.finditer(sql) if _SIGNAL_SET.search(m.group("sets")))

V1 = VersionWords(headline="Reply to Maria today", situation="Maria asked for the deck.", lane="decision",
                  mode="act", ask="loop:deck", by_when="2026-10-14")
V2 = VersionWords(headline="Send Maria the deck by Friday", situation="Maria asked for the deck.",
                  lane="decision", mode="act", ask="loop:deck", by_when="2026-10-16")


# ── the guard ──────────────────────────────────────────────────────────────────────────────────────────────
def violations() -> list[str]:
    found = []
    for top in SCANNED:
        for path in sorted((ROOT / top).rglob("*.py")):
            rel = path.relative_to(ROOT).as_posix()
            if rel == THE_WRITER or "/." in rel:
                continue
            for line, sql in _outermost_strings(ast.parse(path.read_text(encoding="utf-8"))):
                if _sets_signal(sql):
                    found.append(f"{rel}:{line}")
    return found


def test_a_planted_second_writer_is_caught():
    source = ('def f(c):\n'
              '    c.execute(text("update cards set headline = :h, "\n'
              '                   f"signal_id = :s where card_id = {1}"))\n')
    hits = [sql for _, sql in _outermost_strings(ast.parse(source)) if _sets_signal(sql)]
    assert len(hits) == 1, hits
    assert _sets_signal("update cards k set version = 2, signal_id = :s from held where k.card_id = held.card_id")
    assert not _sets_signal("update cards set state = 'acted' where signal_id = :signal")
    assert not _sets_signal("update cards set state='surfaced' from agent_claims ac where cards.signal_id=ac.signal_id")


def test_the_writer_is_where_it_says():
    tree = ast.parse((ROOT / THE_WRITER).read_text(encoding="utf-8"))
    assert sum(_sets_signal(sql) for _, sql in _outermost_strings(tree)) == 1


def test_no_other_code_sets_a_cards_signal():
    assert violations() == []


# ── the writer ─────────────────────────────────────────────────────────────────────────────────────────────
def _reset(eng):
    from sqlalchemy import text
    with eng.begin() as c:
        for org in (ORG, OTHER):
            for table in ("agent_claims", "card_events", "cards", "signals"):
                c.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
            c.execute(text("delete from orgs where id = :o"), {"o": org})


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs a scratch Postgres database")
    from sqlalchemy import create_engine, text
    eng = create_engine(url)
    _reset(eng)
    with eng.begin() as c:
        for org in (ORG, OTHER):
            c.execute(text("insert into orgs (id, name, email) values (:o, :o, :e)"),
                      {"o": org, "e": f"founder@{org}.test"})
        for org, sig in [(ORG, s) for s in ("sig_a", "sig_a2", "sig_b", "sig_b2", "sig_c", "sig_d", "sig_e",
                                            "sig_f", "sig_g", "sig_h", "sig_h2", "sig_lg", "sig_new", "sig_ru", "sig_st")] + \
                [(OTHER, "sig_x"), (OTHER, "sig_x2")]:
            c.execute(text("insert into signals (signal_id, org_id, rule_id, subject_node_id, score, reason_code, "
                           "eval_time) values (:s, :o, 'file_review', 'n1', 50, 'file_review', :t)"),
                      {"s": sig, "o": org, "t": AT})
        for org, card, sig, state, file_id in [
                (ORG, "c_open", "sig_a", "queued", "file_a"),
                (ORG, "c_lapsed", "sig_b", "expired", "file_b"),
                (ORG, "c_acted", "sig_c", "acted", "file_c"),
                (ORG, "c_resolved", "sig_d", "resolved", "file_d"),
                (ORG, "c_dismissed", "sig_e", "expired", "file_e"),
                (ORG, "c_claimed", "sig_f", "claimed", "file_f"),
                (ORG, "c_agent", "sig_g", "surfaced", "file_g"),
                (ORG, "c_snoozed", "sig_h", "snoozed", "file_h"),
                (ORG, "c_legacy", "sig_lg", "queued", None),
                # Decided by either half alone: its state, or the stamp a resolution leaves.
                (ORG, "c_resolved_unstamped", "sig_ru", "resolved", "file_ru"),
                (ORG, "c_stamped", "sig_st", "expired", "file_st"),
                (OTHER, "c_x", "sig_x", "queued", "file_x")]:
            c.execute(text(
                "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, score, "
                "why, actions, artifact, state, expires_at, file_id, snooze_until, resolved_at) values "
                "(:c, :s, :o, 'prescriptive', 'high', :h, :sit, 50, cast('[]' as jsonb), cast('[]' as jsonb), "
                "cast('{}' as jsonb), :st, :exp, :f, :snz, :res)"),
                {"c": card, "s": sig, "o": org, "st": state, "exp": AT + timedelta(days=3), "f": file_id,
                 "h": V1.headline, "sit": V1.situation,
                 "snz": AT + timedelta(hours=4) if state == "snoozed" else None,
                 "res": AT if card in ("c_resolved", "c_stamped") else None})
        c.execute(text("insert into card_events (id, card_id, org_id, kind, cause, actor_id) values "
                       "('cev_dismissed', 'c_dismissed', :o, 'card.dismissed', 'extension', 'seat_1')"), {"o": ORG})
        c.execute(text("insert into agent_claims (signal_id, card_id, org_id, agent_id, expires_at) values "
                       "('sig_g', 'c_agent', :o, 'agent_1', :exp)"), {"o": ORG, "exp": AT + timedelta(minutes=15)})
        # ⛔ RESTATED by `yc2_w27_s14` M42.C1.L-data.V1.U04 (the STEP-14 crosscheck, finding 6): `c_claimed` was held by
        # its STATE alone, the defect — a card is held by a live claim. Its claim, as a claimed card has one; a card
        # left `claimed` by nobody is `tests/platform/test_a_claimed_card_is_held_only_by_a_live_claim.py`'s.
        c.execute(text("insert into agent_claims (signal_id, card_id, org_id, agent_id, expires_at) values "
                       "('sig_f', 'c_claimed', :o, 'agent_1', :exp)"), {"o": ORG, "exp": AT + timedelta(minutes=15)})
    yield eng
    _reset(eng)


def _row(eng, card):
    from sqlalchemy import text
    with eng.connect() as c:
        return c.execute(text("select signal_id, version, state, expires_at, snooze_until, headline from cards "
                              "where card_id = :c"), {"c": card}).one()


def _events(eng, card):
    from sqlalchemy import text
    with eng.connect() as c:
        return [dict(r) for r in c.execute(text(
            "select kind, cause, actor_id, detail from card_events where card_id = :c and kind = 'card.versioned' "
            "order by occurred_at, id"), {"c": card}).mappings()]


def _version(card_version, signal, *, before=V1, after=V2, **flags):
    return version_of(before, after, version=card_version, signal_id=signal, **flags)


def test_a_files_card_moves_onto_its_newest_signal_and_says_what_changed(engine):
    from genios_engine.platform import card_lifecycle as cl
    later = AT + timedelta(days=5)
    with engine.begin() as c:
        assert cl.version_card(c, org_id=ORG, card_id="c_open", version=_version(2, "sig_a2"), expires_at=later)
    row = _row(engine, "c_open")
    assert (row.signal_id, row.version, row.state, row.expires_at) == ("sig_a2", 2, "queued", later)
    assert row.headline == V1.headline, "the words are the card store's to write, not this writer's"
    [event] = _events(engine, "c_open")
    assert (event["kind"], event["cause"], event["actor_id"]) == ("card.versioned", "updated", "system")
    detail = event["detail"]
    assert (detail["version"], detail["signal_id"], detail["from_signal"], detail["material"],
            detail["reopened"]) == (2, "sig_a2", "sig_a", True, False)
    assert detail["changed"] == ["headline", "by_when"]
    assert detail["words"] == V2.as_mapping() and detail["before"] == V1.as_mapping(), "the words before are kept"


def test_a_card_the_clock_closed_is_reopened(engine):
    from genios_engine.platform import card_lifecycle as cl
    with engine.begin() as c:
        assert cl.version_card(c, org_id=ORG, card_id="c_lapsed",
                               version=_version(2, "sig_b2", after=V1, reopened=True),
                               expires_at=AT + timedelta(days=7))
    row = _row(engine, "c_lapsed")
    assert (row.signal_id, row.version, row.state) == ("sig_b2", 2, "queued")
    [event] = _events(engine, "c_lapsed")
    assert (event["cause"], event["detail"]["reopened"], event["detail"]["material"]) == ("reopened", True, False)


def test_a_snoozed_card_keeps_its_snooze(engine):
    from genios_engine.platform import card_lifecycle as cl
    with engine.begin() as c:
        assert cl.version_card(c, org_id=ORG, card_id="c_snoozed", version=_version(2, "sig_h2"),
                               expires_at=AT + timedelta(days=7))
    row = _row(engine, "c_snoozed")
    assert (row.signal_id, row.state, row.snooze_until) == ("sig_h2", "snoozed", AT + timedelta(hours=4))


@pytest.mark.parametrize("card", ["c_acted", "c_resolved", "c_resolved_unstamped", "c_stamped", "c_dismissed",
                                  "c_claimed", "c_agent", "c_legacy"])
def test_a_decided_held_or_fileless_card_is_never_versioned(engine, card):
    from genios_engine.platform import card_lifecycle as cl
    before = _row(engine, card)
    with engine.begin() as c:
        assert not cl.version_card(c, org_id=ORG, card_id=card, version=_version(2, "sig_new"),
                                   expires_at=AT + timedelta(days=7))
    assert _row(engine, card) == before and _events(engine, card) == []


def test_another_tenants_card_and_a_stale_version_are_refused(engine):
    from genios_engine.platform import card_lifecycle as cl
    with engine.begin() as c:
        assert not cl.version_card(c, org_id=ORG, card_id="c_x", version=_version(2, "sig_x2"),
                                   expires_at=AT + timedelta(days=7))
        assert not cl.version_card(c, org_id=ORG, card_id="c_open", version=_version(3, "sig_a2"),
                                   expires_at=AT + timedelta(days=7)), "version 3 of a card at version 1"
    assert _row(engine, "c_x").signal_id == "sig_x" and _row(engine, "c_open").version == 1


def test_a_signal_that_has_its_own_card_is_never_taken(engine):
    from genios_engine.platform import card_lifecycle as cl
    with engine.begin() as c:
        assert not cl.version_card(c, org_id=ORG, card_id="c_open", version=_version(2, "sig_b"),
                                   expires_at=AT + timedelta(days=7))
    assert _row(engine, "c_open").signal_id == "sig_a"


def test_a_created_version_is_no_version(engine):
    from genios_engine.platform import card_lifecycle as cl
    with engine.begin() as c:
        with pytest.raises(ValueError):
            cl.version_card(c, org_id=ORG, card_id="c_open", version=version_of(None, V1, version=1,
                                                                               signal_id="sig_a2"),
                            expires_at=AT)
    assert _row(engine, "c_open").signal_id == "sig_a"


def test_a_version_is_dated_by_its_decision(engine):
    from sqlalchemy import text

    from genios_engine.platform import card_lifecycle as cl
    decided = AT - timedelta(days=30)
    with engine.begin() as c:
        assert cl.version_card(c, org_id=ORG, card_id="c_open", version=_version(2, "sig_a2"), expires_at=AT,
                               at=decided)
        when = c.execute(text("select occurred_at from card_events where card_id = 'c_open' "
                              "and kind = 'card.versioned'")).scalar()
    assert when == decided


def test_the_callers_transaction_owns_the_move_and_its_event(engine):
    from genios_engine.platform import card_lifecycle as cl
    with engine.connect() as c:
        tx = c.begin()
        cl.version_card(c, org_id=ORG, card_id="c_open", version=_version(2, "sig_a2"), expires_at=AT)
        tx.rollback()
    assert _row(engine, "c_open").signal_id == "sig_a" and _events(engine, "c_open") == []


def test_the_files_card_is_the_newest_nobody_decided(engine):
    from sqlalchemy import text

    from genios_engine.platform import card_lifecycle as cl
    with engine.begin() as c:
        assert cl.file_card(c, org_id=ORG, file_id="file_a").card_id == "c_open"
        assert cl.file_card(c, org_id=ORG, file_id="file_b").card_id == "c_lapsed"
        for decided in ("file_c", "file_d", "file_e", "file_ru", "file_st"):
            assert cl.file_card(c, org_id=ORG, file_id=decided) is None, decided
        held = [cl.file_card(c, org_id=ORG, file_id=f) for f in ("file_f", "file_g")]
        assert [(h.card_id, h.held) for h in held] == [("c_claimed", True), ("c_agent", True)]
        assert cl.file_card(c, org_id=ORG, file_id="file_a").held is False
        assert cl.file_card(c, org_id=ORG, file_id="file_x") is None, "another tenant's file"
        # A newer open card of the file is its card; an older closed one stays history.
        c.execute(text("update cards set created_at = :t where card_id = 'c_lapsed'"), {"t": AT - timedelta(days=9)})
        c.execute(text(
            "insert into cards (card_id, signal_id, org_id, level, urgency_band, headline, situation, score, state, "
            "expires_at, file_id) values ('c_b_new', 'sig_b2', :o, 'prescriptive', 'high', 'h', 's', 50, 'queued', "
            ":exp, 'file_b')"), {"o": ORG, "exp": AT + timedelta(days=3)})
        found = cl.file_card(c, org_id=ORG, file_id="file_b")
    assert (found.card_id, found.signal_id, found.version, found.state) == ("c_b_new", "sig_b2", 1, "queued")
