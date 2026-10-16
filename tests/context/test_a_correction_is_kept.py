"""STEP-16 · your correction is kept as you wrote it — once, withdrawable, and read back for its file.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/context/test_a_correction_is_kept.py

`context/founder_corrections` (tree `yc2_w27_s16` M46.C3.L-data.V1.U02; STEP-16 §8.4 item 2, S16-D1). `correct`
keeps your words on a file with their scope — its id the content's (tenant, file, words, scope), so the same
words again are the same correction and no id is minted twice (`03` F170). `withdraw` takes one back, kept.
`standing_for` reads the file's own (on its anchor or one of its people) and its kind's, newest first,
bounded, the cut counted. A `company` correction is your own preferences line of the brief, accepted as
written through the brief's one writer, its line id kept; withdrawn, it leaves the brief.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.context import founder_corrections as C
from genios_engine.contracts.learning_attribution import ALL_REASONS

ORG = "fc_store_org"
AT = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)
FILE = "node_antler"
WORDS = "Theresa asked for updates only with real news — don't push me."
KIND_WORDS = "Investors who asked for news only on milestones get nothing before one lands."


def test_the_vocabulary_is_closed_and_the_bound_is_the_tables():
    from pathlib import Path
    sql = (Path(__file__).resolve().parents[2] / "migrations" / "0241_founder_corrections.sql").read_text()
    assert C.SCOPES == (C.FILE, C.KIND, C.COMPANY) == ("file", "kind", "company")
    assert f"between 1 and {C.MAX_WORDS}" in sql
    assert C.COMPANY_SECTION == "preferences"


class _Unreachable:
    def execute(self, *_a, **_k):                                    # pragma: no cover - the point
        raise AssertionError("a refused correction reached the database")


@pytest.mark.parametrize("over", [
    {"words": ""}, {"words": "   "}, {"words": "two\nlines"}, {"words": "x" * (C.MAX_WORDS + 1)},
    {"scope": "team"}, {"reason": "meh"},
    {"scope": "kind"}, {"scope": "kind", "kind": "astrology"},
    {"scope": "file", "kind": "investor"}, {"scope": "company", "kind": "investor"},
])
def test_what_is_not_a_correction_is_refused_before_anything_is_written(over):
    kw = {"org_id": ORG, "file_id": FILE, "words": WORDS, "scope": C.FILE, "by": "user_rohit", "at": AT}
    kw.update(over)
    with pytest.raises(ValueError):
        C.correct(_Unreachable(), **kw)


def test_the_id_is_the_contents():
    a = C.correction_id_for(ORG, FILE, WORDS, C.FILE)
    assert a == C.correction_id_for(ORG, FILE, WORDS, C.FILE) and a.startswith("fc_")
    assert len({a, C.correction_id_for(ORG, FILE, WORDS, C.KIND), C.correction_id_for(ORG, "node_x", WORDS, C.FILE),
                C.correction_id_for(ORG, FILE, WORDS + "!", C.FILE),
                C.correction_id_for("org_other", FILE, WORDS, C.FILE)}) == 5


@pytest.fixture
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs a scratch Postgres database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'fc@store.test')"), {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _correct(c, words=WORDS, *, file=FILE, scope=C.FILE, at=AT, **kw):
    return C.correct(c, org_id=ORG, file_id=file, words=words, scope=scope, by="user_rohit", at=at, **kw)


def _count(c):
    return c.execute(text("select count(*) from founder_corrections where org_id = :o"), {"o": ORG}).scalar()


@pytest.mark.pg
def test_a_correction_is_kept_in_your_words(engine):
    with engine.begin() as c:
        kept = _correct(c, f"  {WORDS}  ", card_id="card_7", feedback_id="fb_7", reason="not_relevant")
    assert kept == C.Correction(
        correction_id=C.correction_id_for(ORG, FILE, WORDS, C.FILE), file_id=FILE, card_id="card_7",
        feedback_id="fb_7", reason="not_relevant", words=WORDS, scope=C.FILE, kind=None, brief_line_id=None,
        corrected_by="user_rohit", corrected_at=AT, state=C.STANDING)


@pytest.mark.pg
def test_the_same_words_again_are_the_same_correction(engine):
    with engine.begin() as c:
        first = _correct(c, card_id="card_7")
        again = _correct(c, card_id="card_8", at=AT + timedelta(days=1))
        assert _count(c) == 1
    assert again == first, "unchanged while it stands — the first card it was about, when you first said it"


@pytest.mark.pg
def test_a_withdrawn_correction_is_kept_withdrawn_and_said_again_it_stands(engine):
    with engine.begin() as c:
        kept = _correct(c)
        gone = C.withdraw(c, org_id=ORG, correction_id=kept.correction_id, by="user_rohit",
                          at=AT + timedelta(hours=1))
        assert C.standing_for(c, ORG, FILE).corrections == ()
        with pytest.raises(ValueError):
            C.withdraw(c, org_id=ORG, correction_id=kept.correction_id, by="user_rohit", at=AT)
        again = _correct(c, at=AT + timedelta(days=2))
        assert _count(c) == 1
    assert (gone.state, gone.withdrawn_by, gone.withdrawn_at) == (C.WITHDRAWN, "user_rohit", AT + timedelta(hours=1))
    assert (again.correction_id, again.state, again.corrected_at, again.withdrawn_at) == (
        kept.correction_id, C.STANDING, AT + timedelta(days=2), None)


@pytest.mark.pg
def test_what_stands_for_a_file_is_its_own_its_peoples_and_its_kinds_newest_first(engine):
    with engine.begin() as c:
        own = _correct(c, at=AT)
        person = _correct(c, "Sanjay is the partner who decides.", file="node_sanjay", at=AT + timedelta(hours=1))
        kind = _correct(c, KIND_WORDS, file="node_other_fund", scope=C.KIND, kind="investor",
                        at=AT + timedelta(hours=2))
        _correct(c, "Programmes reply in their own time.", file="node_prog", scope=C.KIND, kind="program",
                 at=AT + timedelta(hours=3))
        _correct(c, "Not this file's.", file="node_elsewhere", at=AT + timedelta(hours=4))
        gone = _correct(c, "Withdrawn since.", at=AT + timedelta(hours=5))
        C.withdraw(c, org_id=ORG, correction_id=gone.correction_id, by="user_rohit", at=AT + timedelta(hours=6))
        stands = C.standing_for(c, ORG, FILE, people=("node_sanjay",), kind="investor")
        alone = C.standing_for(c, ORG, FILE)
    assert stands == C.Standing(corrections=(kind, person, own), cut=0)
    assert alone == C.Standing(corrections=(own,), cut=0), "no people, no kind: the file's own only"


@pytest.mark.pg
def test_what_stands_is_bounded_and_the_cut_is_counted(engine):
    with engine.begin() as c:
        made = [_correct(c, f"Correction number {i}.", at=AT + timedelta(minutes=i)) for i in range(5)]
        stands = C.standing_for(c, ORG, FILE, limit=3)
    assert [k.correction_id for k in stands.corrections] == [m.correction_id for m in made[::-1][:3]]
    assert stands.cut == 2


@pytest.mark.pg
def test_a_company_correction_is_your_own_preferences_line_of_the_brief(engine):
    from genios_engine.platform import company_brief_store as brief
    words = "Never push a follow-up on a Friday."
    with engine.begin() as c:
        kept = _correct(c, words, scope=C.COMPANY)
        lines = [ln for ln in brief.accepted(c, ORG) if ln.line_id == kept.brief_line_id]
        row = c.execute(text("select proposed_by, decided_by from company_brief_lines where org_id = :o "
                             "and line_id = :l"), {"o": ORG, "l": kept.brief_line_id}).one()
        assert C.standing_for(c, ORG, FILE).corrections == (), "the brief carries it, not the file"
        C.withdraw(c, org_id=ORG, correction_id=kept.correction_id, by="user_rohit", at=AT + timedelta(hours=1))
        still = [ln.line_id for ln in brief.accepted(c, ORG)]
    assert [(ln.section, ln.text) for ln in lines] == [("preferences", words)]
    assert (row.proposed_by, row.decided_by) == (brief.BY_FOUNDER, "user_rohit"), "accepted as written — yours"
    assert kept.brief_line_id not in still, "withdrawn, it leaves the brief"


@pytest.mark.pg
def test_a_company_correction_the_brief_cannot_hold_writes_nothing(engine):
    with pytest.raises(ValueError):
        with engine.begin() as c:
            _correct(c, "y" * 300, scope=C.COMPANY)
    with engine.begin() as c:
        assert _count(c) == 0


@pytest.mark.pg
def test_every_reason_of_the_eleven_rides_on_a_correction(engine):
    with engine.begin() as c:
        for reason in sorted(ALL_REASONS):
            _correct(c, f"Because: {reason}.", reason=reason)
        assert _count(c) == 11
