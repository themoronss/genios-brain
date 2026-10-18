"""STEP-16 · the morning brief carries the same door — a line's "not useful because ___" corrects the line's file,
and a Watching line whose review cites your correction says so.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/executive/test_a_brief_line_is_a_correction_of_its_file.py

Tree `yc2_w27_s16` M46.C6.L-interface.V2.U01 (STEP-15 §3.5, STEP-16 §4). `executive/morning.mark` keeps your mark on
a line (`morning_store.mark_line`) and, when it is NOT USEFUL and the line is about a file — a decision, a question, a
watched file, or the change a review of that file made — keeps your words as a correction of that file
(`context/founder_corrections.correct`, scope `file`, the card the line showed): the road the card's *wrong* takes
(M46.C3.L-integration.V3.U04), so the next review reads it. A useful mark, a line about no file (a meeting, your
desk, a promise), or a mark older than the one kept corrects nothing; words that cannot be a correction are refused
whole, the mark with them. And `morning_day.you_said_on` reads, of the corrections a review cites, the newest that
still stands — the day it was said is the Watching line's *"(you said so on 21 Sep)"* (`morning_template.words_for`).
On F65's golden tenant — Leah asked for news only on real milestones; you said so; the next review waits — the
brief's Watching line says it.
"""
from __future__ import annotations

import os
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text

from genios_engine.api import executive_routes as R
from genios_engine.context import founder_corrections as fc
from genios_engine.contracts import morning_brief as B
from genios_engine.executive import morning, morning_store
from genios_engine.executive import morning_day as D
from genios_engine.executive.morning_template import words_for
from genios_engine.platform import auth
from genios_engine.platform.auth import AuthCtx, get_auth_ctx

pytestmark = pytest.mark.pg

ORG = "org_s16_brief_door"
OWNER = AuthCtx(org_id=ORG, seat_id="seat_owner", role="owner", source="jwt")
NOW = datetime(2026, 10, 13, 3, 0, tzinfo=timezone.utc)
LOCAL = date(2026, 10, 13)
WORDS = "Leah asked for news only on real milestones; don't push me."


class _Graph:
    def __init__(self, engine) -> None:
        self.engine = engine


@pytest.fixture
def engine():
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — a mark and a correction are kept in Postgres")
    from genios_engine.platform.db import get_engine
    from genios_engine.platform.seats import ensure_owner_seat
    eng = get_engine(os.environ["GENIOS_TEST_DATABASE_URL"])
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email, timezone) values (:o, 'Arjun Rao', :e, "
                       "'Asia/Kolkata')"), {"o": ORG, "e": f"{ORG}@example.test"})
        ensure_owner_seat(c, ORG)
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _item(kind, about, *, sources=None, card=None, words=(("name", "Lumen"), ("headline", "Wait for news"))):
    return B.Item(item_id=B.item_id_for(kind, about, "t"), kind=kind, about=about, subject="Lumen",
                  material=B.Material(words=words),
                  sources=sources or (B.Source(B.SOURCE_REVIEW, f"{about}@fp"),), card_id=card)


def _kept(engine, *items_sections):
    """A kept brief of LOCAL whose lines are the given (item, section) pairs; their line ids, in order."""
    lines, items = [], []
    for item, section in items_sections:
        lines.append(B.Line(line_id=B.line_id_for(ORG, "seat_owner", LOCAL, section, item.item_id),
                            item_id=item.item_id, section=section, words=f"{item.subject}: a line.",
                            kind=item.kind, subject=item.subject, sources=item.sources))
        items.append(item)
    brief = B.Brief(org_id=ORG, seat_id="seat_owner", local_date=LOCAL, timezone="Asia/Kolkata", as_of=NOW,
                    one_line="A thing to know.", lines=tuple(lines), items=tuple(items),
                    written_by=B.TEMPLATE_BRIEF, why="the template", model=None, tier=None, cost_micro_usd=0,
                    cut=(), material_digest=B.digest_of(tuple(items)))
    with engine.begin() as c:
        morning_store.keep(c, brief)
    return [l.line_id for l in lines]


def _corrections(engine):
    with engine.connect() as c:
        return c.execute(text("select file_id, card_id, words, scope, corrected_by, corrected_at, state "
                              "from founder_corrections where org_id = :o order by corrected_at, file_id"),
                         {"o": ORG}).all()


def _mark(engine, line_id, mark, words=None, *, at=NOW):
    with engine.begin() as c:
        return morning.mark(c, org_id=ORG, line_id=line_id, marked_by="seat_owner", mark=mark, words=words, at=at)


# ── the door: a line's "not useful because ___" is a correction of the line's file ─────────────────────────────
@pytest.mark.parametrize("kind, section", [(B.WATCHED, B.WATCHING), (B.DECISION, B.TODAY), (B.QUESTION, B.ASKED)])
def test_not_useful_on_a_files_line_is_a_correction_of_that_file(engine, kind, section):
    (line,) = _kept(engine, (_item(kind, "node_lumen", card="card_lumen"), section))
    marked = _mark(engine, line, morning_store.NOT_USEFUL, f"  {WORDS.replace(' ', '   ', 2)} ")  # as the mark keeps them
    assert marked.mark.mark == morning_store.NOT_USEFUL and marked.mark.words == WORDS
    (row,) = _corrections(engine)
    assert tuple(row) == ("node_lumen", "card_lumen", WORDS, fc.FILE, "seat_owner", NOW, fc.STANDING)
    assert marked.correction is not None and marked.correction.file_id == "node_lumen"


def test_the_change_a_review_of_the_file_made_is_that_files_line(engine):
    (line,) = _kept(engine, (_item(B.CHANGE, "node_lumen", words=(("name", "Lumen"), ("what", "Leah wrote."))),
                             B.CHANGED))
    _mark(engine, line, morning_store.NOT_USEFUL, WORDS)
    assert [r.file_id for r in _corrections(engine)] == ["node_lumen"]


@pytest.mark.parametrize("item", [
    _item(B.MEETING, "node_meeting", sources=(B.Source(B.SOURCE_MEETING, "node_meeting"),),
          words=(("when", "Today 10:00"), ("title", "Sync"))),
    _item(B.PROMISE, "node_promise", sources=(B.Source(B.SOURCE_PROMISE, "node_promise"),),
          words=(("promise", "send the deck"),)),
    # a gone line of the last brief about a meeting: a change, but no review of a file made it
    _item(B.CHANGE, "node_meeting", sources=(B.Source(B.SOURCE_MEETING, "node_meeting"),),
          words=(("name", "Sync"), ("what", "the meeting has passed"))),
    # a change whose review is ANOTHER file's: never this one's
    _item(B.CHANGE, "node_lumen", sources=(B.Source(B.SOURCE_REVIEW, "node_other@fp"),),
          words=(("name", "Lumen"), ("what", "Leah wrote."))),
    # a file's kind of line that names no file (the contract allows `about` None): nothing to correct
    _item(B.WATCHED, None, sources=(B.Source(B.SOURCE_CALCULATOR, "quiet"),)),
], ids=["meeting", "promise", "gone-meeting", "another-files-review", "no-file-named"])
def test_a_line_about_no_file_keeps_its_mark_and_corrects_nothing(engine, item):
    section = {B.MEETING: B.MEETINGS, B.CHANGE: B.CHANGED, B.PROMISE: B.PROMISES, B.WATCHED: B.WATCHING}[item.kind]
    (line,) = _kept(engine, (item, section))
    marked = _mark(engine, line, morning_store.NOT_USEFUL, WORDS)
    assert marked.mark.words == WORDS and marked.correction is None
    assert _corrections(engine) == []


def test_a_line_names_its_file_and_card_or_neither():
    """`file_of_line`, pure: a file's line gives its file and the card it showed; a line that names no file gives
    neither — never a card without its file."""
    items = (_item(B.WATCHED, "node_lumen", card="card_lumen"), _item(B.WATCHED, None, card="card_stray"))
    lines = tuple(B.Line(line_id=f"bl_{n}", item_id=i.item_id, section=B.WATCHING, words="Lumen: a line.",
                         kind=i.kind, subject=i.subject, sources=i.sources) for n, i in enumerate(items))
    brief = B.Brief(org_id=ORG, seat_id="seat_owner", local_date=LOCAL, timezone="Asia/Kolkata", as_of=NOW,
                    one_line="Two things.", lines=lines, items=items, written_by=B.TEMPLATE_BRIEF,
                    why="the template", model=None, tier=None, cost_micro_usd=0, cut=(),
                    material_digest=B.digest_of(items))
    assert morning.file_of_line(brief, "bl_0") == ("node_lumen", "card_lumen")
    assert morning.file_of_line(brief, "bl_1") == (None, None)
    assert morning.file_of_line(brief, "bl_no_such_line") == (None, None)


def test_a_useful_mark_corrects_nothing(engine):
    (line,) = _kept(engine, (_item(B.WATCHED, "node_lumen"), B.WATCHING))
    marked = _mark(engine, line, morning_store.USEFUL)
    assert marked.mark.mark == morning_store.USEFUL and marked.correction is None
    assert _corrections(engine) == []


def test_a_mark_older_than_the_one_kept_corrects_nothing(engine):
    (line,) = _kept(engine, (_item(B.WATCHED, "node_lumen"), B.WATCHING))
    _mark(engine, line, morning_store.NOT_USEFUL, WORDS)
    late = _mark(engine, line, morning_store.NOT_USEFUL, "Something else, said earlier.", at=NOW - timedelta(hours=1))
    assert late.mark.words == WORDS and late.correction is None, "the kept mark stands; the older one did nothing"
    assert [r.words for r in _corrections(engine)] == [WORDS]


def test_words_that_cannot_be_a_correction_are_refused_with_the_mark(engine):
    (line,) = _kept(engine, (_item(B.WATCHED, "node_lumen"), B.WATCHING))
    with pytest.raises(ValueError, match="at most"):
        _mark(engine, line, morning_store.NOT_USEFUL, "x" * (fc.MAX_WORDS + 1))
    with engine.connect() as c:
        assert morning_store.marks_for(c, ORG, "seat_owner", LOCAL) == {}, "refused whole: no mark either"
    assert _corrections(engine) == []


def _client(monkeypatch, engine):
    monkeypatch.setattr(R, "_graph", _Graph(engine))
    monkeypatch.setattr(R, "_now", lambda: NOW)
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    app = FastAPI()
    app.include_router(R.router)
    app.dependency_overrides[get_auth_ctx] = lambda: OWNER
    return TestClient(app)


def test_the_route_is_the_door_and_says_the_correction_it_kept(monkeypatch, engine):
    meeting, watched = _kept(engine,
                             (_item(B.MEETING, "node_meeting", sources=(B.Source(B.SOURCE_MEETING, "node_meeting"),),
                                    words=(("when", "Today 10:00"), ("title", "Sync"))), B.MEETINGS),
                             (_item(B.WATCHED, "node_lumen", card="card_lumen"), B.WATCHING))
    client = _client(monkeypatch, engine)
    said = client.post(f"/v1/executive/morning/lines/{watched}/mark", json={"mark": "not_useful", "words": WORDS})
    assert said.status_code == 200
    (row,) = _corrections(engine)
    assert said.json()["correction_id"] == fc.correction_id_for(ORG, "node_lumen", WORDS, fc.FILE)
    assert said.json()["file_id"] == "node_lumen" and row.card_id == "card_lumen"
    other = client.post(f"/v1/executive/morning/lines/{meeting}/mark", json={"mark": "not_useful", "words": WORDS})
    assert other.status_code == 200 and other.json()["correction_id"] is None and other.json()["file_id"] is None
    long = client.post(f"/v1/executive/morning/lines/{watched}/mark",
                       json={"mark": "not_useful", "words": "x" * (fc.MAX_WORDS + 1)})
    assert long.status_code == 422


# ── a Watching line whose review cites your correction says so ──────────────────────────────────────────────────
def _review(*cited):
    return SimpleNamespace(facts=(SimpleNamespace(evidence=("ev_1",)),),
                           inferences=(SimpleNamespace(based_on=tuple(cited[:1])),),
                           patterns=(SimpleNamespace(based_on=tuple(cited[1:])),))


def _correct(engine, words, at, *, file_id="node_lumen"):
    with engine.begin() as c:
        return fc.correct(c, org_id=ORG, file_id=file_id, words=words, scope=fc.FILE, by="seat_owner", at=at)


def test_you_said_on_is_the_newest_standing_correction_the_review_cites(engine):
    zone = ZoneInfo("Asia/Kolkata")
    old = _correct(engine, "Only on milestones.", datetime(2026, 10, 1, 20, 0, tzinfo=timezone.utc))
    new = _correct(engine, "Not before the pilot is signed.", datetime(2026, 10, 11, 20, 0, tzinfo=timezone.utc))
    with engine.connect() as c:
        both = D.you_said_on(c, ORG, _review(f"corr:{old.correction_id}", f"corr:{new.correction_id}"), zone)
        one = D.you_said_on(c, ORG, _review(f"corr:{old.correction_id}"), zone)
        none = D.you_said_on(c, ORG, _review("ev_1"), zone)
    assert both == "2026-10-12", "the newest cited, on the org's own day (20:00 UTC is 01:30 the next day)"
    assert one == "2026-10-02" and none is None
    with engine.begin() as c:
        fc.withdraw(c, org_id=ORG, correction_id=new.correction_id, by="seat_owner", at=NOW)
    with engine.connect() as c:
        assert D.you_said_on(c, ORG, _review(f"corr:{old.correction_id}", f"corr:{new.correction_id}"),
                             zone) == "2026-10-02", "a correction you took back is not what you said"
        assert D.you_said_on(c, ORG, _review(f"corr:{new.correction_id}"), zone) is None
        assert D.you_said_on(c, ORG, _review("corr:fc_no_such_correction"), zone) is None


def _watched(*, rule="Wait for a real milestone.", said=None):
    return B.Item(item_id=B.item_id_for(B.WATCHED, "node_lumen"), kind=B.WATCHED, about="node_lumen",
                  subject="Lumen", material=B.Material(
                      words=(("name", "Lumen"), ("headline", "Wait for Leah"), ("wait_rule", rule)),
                      dates=(("you_said", said),)),
                  sources=(B.Source(B.SOURCE_REVIEW, "node_lumen@fp"),))


def test_a_watching_line_whose_review_cites_your_correction_says_so():
    assert words_for(_watched(said="2026-10-12"), B.WATCHING) == (
        "Lumen: Wait for Leah. Wait for a real milestone (you said so on 12 Oct).")
    assert words_for(_watched(rule=None, said="2026-10-12"), B.WATCHING) == (
        "Lumen: Wait for Leah (you said so on 12 Oct).")
    assert words_for(_watched(), B.WATCHING) == "Lumen: Wait for Leah. Wait for a real milestone."


def test_f65_the_watching_line_says_you_said_so():
    """The golden tenant, as the real chain leaves it after F65's last sweep (replayed from its cassette): you
    called Leah's card wrong on 21 Sep with your words; the next review waits and cites your correction — and the
    brief's Watching line says so, on the day you said it."""
    if not os.environ.get("GENIOS_TEST_DATABASE_URL"):
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — F65 is replayed on Postgres")
    from genios_engine.api import routes
    from tests.replays import cassettes, engine_runner
    from tests.replays.founder_case import load_cases
    from tests.replays.harness import RecordedLLM
    engine_runner.pin_scratch_database()
    case = next(c for c in load_cases() if c.case_id == "F65")
    run = engine_runner.run_case(case, RecordedLLM(cassettes.load(case)), keep=True)
    try:
        assert run.misses == () and all(a.ok for a in run.acts)
        with routes._graph.engine.connect() as c:
            day = D.read_day(c, run.org_id, "seat_owner", now=case.sweeps[-1])
        (watched,) = [i for i in day.items if i.kind == B.WATCHED]
        local = case.sweeps[0].astimezone(ZoneInfo(day.tz)).date().isoformat()
        assert watched.material.date("you_said") == local
        said = f"{int(local[8:])} {date.fromisoformat(local).strftime('%b')}"
        assert f"(you said so on {said})" in words_for(watched, B.WATCHING)
    finally:
        engine_runner.remove_tenant(routes._graph.engine, run.org_id)
