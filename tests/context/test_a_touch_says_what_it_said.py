"""STEP-12 · a touch says what it said — its words, bounded and counted — and an archive's words are never read.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_touch_says_what_it_said.py -q

`context/workstream_timeline.timeline_for` (tree `yc2_w27_s12` M32.C2.L-data.V0.U06, added by
`yc2_w27_align` M34.C4). A file's timeline said who touched it and when, never what was said — so the
expert's dossier could not show a portal's notice (`03` F99: F02's decider saw *"this is a company"* and
not *"upload it within 7 days, or the application will be closed"*), nor the reply a promise answered
beside our own promise (F147: F49's card chased Kunal for a link he had sent the same day). Each touch
now carries its words — the prepared text memory holds for it, cut at `WORDS_CHARS` and the cut counted
— and its ledger outcome, asked FIRST: a correlation's membership ignores outcome (F57), so an archived
mail can be a member, and its words are never read through one.
"""
from __future__ import annotations

import re
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context import workstream_timeline as W

from .workstream_world import FOUNDER, T0, WATCHED, brief, process, reset, tenant

pytestmark = pytest.mark.pg

ORG = "org_s12_touch_words"
KUNAL = "kunal@meridianvc.test"
NOW = T0 + timedelta(days=20)


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    yield pg_store
    reset(pg_store, ORG)


def _words(store, event_id: str, words: str) -> None:
    """The prepared text Layer 1 stores for a kept mail (`prepared_content`)."""
    with store.engine.begin() as c:
        c.execute(text("insert into prepared_content (event_id, org_id, prepared_content_id, "
                       "clean_text) values (:e, :o, :p, :t)"),
                  {"e": event_id, "o": ORG, "p": f"pc_{event_id}", "t": words})


def _file_of(store, sender: str) -> str:
    with store.engine.connect() as c:
        return c.execute(text(
            "select distinct k.anchor_node_id from context_correlations k "
            "  join context_correlation_members m on m.org_id = k.org_id "
            "       and m.correlation_id = k.correlation_id "
            "  join source_events se on se.org_id = m.org_id and se.event_id = m.event_id "
            " where k.org_id = :o and lower(se.actor->>'email') = :s"),
            {"o": ORG, "s": sender}).scalar_one()


def _kunal(store) -> str:
    """F147's shape: we asked for the link, Kunal sent it the same day, and we promised to book."""
    process(store, ORG, event_id="evt_ask", sender=FOUNDER, recipients=(KUNAL,), thread="t_k", at=T0)
    process(store, ORG, event_id="evt_link", sender=KUNAL, thread="t_k", at=T0 + timedelta(hours=3))
    process(store, ORG, event_id="evt_promise", sender=FOUNDER, recipients=(KUNAL,), thread="t_k",
            at=T0 + timedelta(hours=5))
    _words(store, "evt_ask", "Please resend the calendar link.")
    _words(store, "evt_link", "Here it is again: https://cal.test/kunal — any slot this week works.")
    _words(store, "evt_promise", "Thanks Kunal, I will book it again tonight.")
    return _file_of(store, KUNAL)


def test_each_touch_carries_what_it_said_and_its_outcome(store):
    file_id = _kunal(store)
    with store.engine.connect() as c:
        tl = W.timeline_for(c, ORG, file_id, now=NOW)
    assert [(t.event_id, t.direction, t.outcome, t.words) for t in tl.touches] == [
        ("evt_ask", "out", "emitted", "Please resend the calendar link."),
        ("evt_link", "in", "emitted",
         "Here it is again: https://cal.test/kunal — any slot this week works."),
        ("evt_promise", "out", "emitted", "Thanks Kunal, I will book it again tonight.")]
    assert all(t.words_cut == 0 for t in tl.touches) and tl.words_cut == 0


def test_an_archived_members_words_are_never_read(store):
    """`03` F57: membership ignores outcome. Even with prepared text present for it — which STEP-03
    never stores for an archive — the archive's words stay unread; it is still a touch, said so."""
    file_id = _kunal(store)
    with store.engine.begin() as c:
        c.execute(text("update source_events set outcome = 'archived' where org_id = :o "
                       "and event_id = 'evt_link'"), {"o": ORG})
    with store.engine.connect() as c:
        tl = W.timeline_for(c, ORG, file_id, now=NOW)
    link = next(t for t in tl.touches if t.event_id == "evt_link")
    assert (link.outcome, link.words, link.words_cut) == ("archived", None, 0)
    assert [t.event_id for t in tl.touches] == ["evt_ask", "evt_link", "evt_promise"]


def test_a_long_mail_is_cut_and_the_cut_is_counted(store):
    process(store, ORG, event_id="evt_long", sender=KUNAL, thread="t_long", at=T0)
    long_words = " ".join(f"word{n:04d}" for n in range(400))          # 3,599 characters
    _words(store, "evt_long", long_words)
    with store.engine.connect() as c:
        tl = W.timeline_for(c, ORG, _file_of(store, KUNAL), now=NOW)
    [touch] = tl.touches
    assert len(touch.words) <= W.WORDS_CHARS and touch.words.startswith("word0000 word0001")
    assert touch.words_cut == len(long_words) - len(touch.words) and touch.words_cut > 0
    assert long_words.startswith(touch.words)
    assert re.fullmatch(r"(word\d{4} )*word\d{4}", touch.words), touch.words[-20:]   # never inside a word
    assert tl.words_cut == touch.words_cut


def test_a_mail_memory_holds_no_text_for_says_nothing(store):
    process(store, ORG, event_id="evt_bare", sender=KUNAL, thread="t_bare", at=T0)
    with store.engine.connect() as c:
        tl = W.timeline_for(c, ORG, _file_of(store, KUNAL), now=NOW)
    [touch] = tl.touches
    assert (touch.outcome, touch.words, touch.words_cut) == ("emitted", None, 0)


def test_a_watched_portals_notice_reads_what_it_asks(store):
    """`03` F99: the notice's words are on its touch, so the dossier can show the 7-day ask."""
    process(store, ORG, event_id="evt_notice", sender=f"updates@{WATCHED}", thread="t_n", at=T0,
            company_brief=brief(ORG))
    _words(store, "evt_notice", "The examiner requires a board resolution. Upload it on the portal "
                                "within 7 days, or the application will be closed.")
    with store.engine.connect() as c:
        tl = W.timeline_for(c, ORG, _file_of(store, f"updates@{WATCHED}"), now=NOW)
    [notice] = tl.touches
    assert "within 7 days, or the application will be closed" in notice.words


def test_the_timeline_reads_as_json_with_its_words(store):
    file_id = _kunal(store)
    with store.engine.connect() as c:
        body = W.as_dict(W.timeline_for(c, ORG, file_id, now=NOW))
    assert body["touches"][1]["words"].startswith("Here it is again")
    assert (body["touches"][1]["outcome"], body["touches"][1]["words_cut"]) == ("emitted", 0)
    assert body["words_cut"] == 0
