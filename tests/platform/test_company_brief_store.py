"""STEP-07 · the company brief's one writer: nothing counts until accepted, nothing is deleted.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/platform/test_company_brief_store.py -q

Tree `yc2_w27_s07 · M25.C1.L-data.V1.U03`. A line is proposed, then accepted (as written or in the
founder's own words), rejected, or — once accepted — removed. The drafter cannot propose what the brief
already says, nor nag with a line the founder rejected; the brief in force at any instant can be
rebuilt from the rows.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.platform import company_brief_store as store

pytestmark = pytest.mark.pg

ORG = "org_s07_brief_store"
AT = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, company) values (:o, 'Arjun Rao', 'Nimbus Labs')"),
                  {"o": ORG})
    yield eng
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _status(eng, line_id):
    with eng.connect() as c:
        return c.execute(text("select status, text, proposed_text, decided_by, accepted_at, "
                              "removed_at from company_brief_lines where org_id = :o and line_id = :l"),
                         {"o": ORG, "l": line_id}).mappings().one()


def test_a_proposal_counts_only_once_accepted(engine):
    with engine.begin() as c:
        line = store.propose(c, org_id=ORG, section="goals", words="raise the pre-seed round",
                             proposed_by="drafter", at=AT, evidence=[{"pattern": "wave:2026-08-11"}])
        assert store.accepted(c, ORG) == []
        assert [p["line_id"] for p in store.pending(c, ORG)] == [line]
        assert store.pending(c, ORG)[0]["evidence"] == [{"pattern": "wave:2026-08-11"}]
    with engine.begin() as c:
        store.accept(c, org_id=ORG, line_id=line, decided_by="founder", at=AT + timedelta(minutes=1))
        assert [ln.text for ln in store.accepted(c, ORG)] == ["raise the pre-seed round"]
        assert store.pending(c, ORG) == []
    assert _status(engine, line)["status"] == "accepted"


def test_accepting_in_the_founders_words_keeps_the_proposals(engine):
    with engine.begin() as c:
        line = store.propose(c, org_id=ORG, section="goals", words="raise a seed round",
                             proposed_by="drafter", at=AT)
        store.accept(c, org_id=ORG, line_id=line, decided_by="founder", at=AT,
                     words="raise the pre-seed round by December")
    row = _status(engine, line)
    assert (row["text"], row["proposed_text"]) == ("raise the pre-seed round by December",
                                                   "raise a seed round")


def test_a_rejected_line_stays_and_is_not_proposed_again_soon(engine):
    with engine.begin() as c:
        line = store.propose(c, org_id=ORG, section="goals", words="hire a sales lead",
                             proposed_by="drafter", at=AT)
        store.reject(c, org_id=ORG, line_id=line, decided_by="founder", at=AT)
        again = store.propose(c, org_id=ORG, section="goals", words="Hire a  sales lead",
                              proposed_by="weekly", at=AT + timedelta(days=7))
        later = store.propose(c, org_id=ORG, section="goals", words="hire a sales lead",
                              proposed_by="weekly",
                              at=AT + timedelta(days=store.REJECTED_QUIET_DAYS + 1))
    assert _status(engine, line)["status"] == "rejected"
    assert again is None, "a line the founder rejected a week ago is not proposed again"
    assert later is not None, "after the quiet window it may be proposed once more"


def test_what_the_brief_already_says_is_not_proposed_twice(engine):
    with engine.begin() as c:
        first = store.propose(c, org_id=ORG, section="connectors",
                              words="Introly — introduces people", address="hello@introly.test",
                              proposed_by="drafter", at=AT)
        same_address = store.propose(c, org_id=ORG, section="connectors",
                                     words="Introly, an intro agent", address="HELLO@introly.test",
                                     proposed_by="drafter", at=AT)
        store.accept(c, org_id=ORG, line_id=first, decided_by="founder", at=AT)
        after_accept = store.propose(c, org_id=ORG, section="connectors",
                                     words="Introly — introduces people",
                                     address="hello@introly.test", proposed_by="weekly", at=AT)
    assert same_address is None and after_accept is None


def test_removing_a_line_keeps_it_and_the_past_brief_can_be_rebuilt(engine):
    with engine.begin() as c:
        kept = store.add(c, org_id=ORG, section="goals", words="raise the pre-seed round",
                         decided_by="founder", at=AT)
        gone = store.add(c, org_id=ORG, section="in_motion", words="hiring a founding engineer",
                         decided_by="founder", at=AT)
        store.remove(c, org_id=ORG, line_id=gone, decided_by="founder", at=AT + timedelta(days=3))
        now = [ln.line_id for ln in store.accepted(c, ORG)]
        then = [ln.line_id for ln in store.accepted(c, ORG, at=AT + timedelta(days=1))]
        before = store.accepted(c, ORG, at=AT - timedelta(seconds=1))
    assert now == [kept]
    assert sorted(then) == sorted([kept, gone])
    assert before == []
    row = _status(engine, gone)
    assert row["status"] == "removed" and row["removed_at"] is not None


def test_a_declined_proposal_mints_no_id_and_a_named_one_is_used_as_given(engine, monkeypatch):
    """`03` F170 (STEP-12 M32.C3.L-data.V1.U12): an id is minted only for a line that is written —
    in a golden run ids come from a per-case sequence, and a wasted one shifts every id after it."""
    from genios_engine.platform import ids
    minted = []
    real = ids.new_id
    monkeypatch.setattr(store, "new_id", lambda prefix: minted.append(prefix) or real(prefix))
    with engine.begin() as c:
        first = store.propose(c, org_id=ORG, section="goals", words="raise the pre-seed round",
                              proposed_by="drafter", at=AT)
        again = store.propose(c, org_id=ORG, section="goals", words="Raise the pre-seed round",
                              proposed_by="drafter", at=AT)
        named = store.propose(c, org_id=ORG, section="goals", words="hire a founding engineer",
                              proposed_by="expert_review", at=AT, line_id="cbl_given")
    assert first and again is None and named == "cbl_given"
    assert minted == ["cbl"], "the declined proposal and the named one minted nothing"


def test_add_does_not_double_a_line(engine):
    with engine.begin() as c:
        one = store.add(c, org_id=ORG, section="watchlist", words="StartupSetu",
                        domain="startupsetu.gov.test", decided_by="founder", at=AT)
        two = store.add(c, org_id=ORG, section="watchlist", words="the recognition portal",
                        domain="StartupSetu.gov.test", decided_by="founder", at=AT)
    assert one == two


def test_a_decision_the_state_does_not_allow_is_refused(engine):
    with engine.begin() as c:
        line = store.propose(c, org_id=ORG, section="goals", words="raise the pre-seed round",
                             proposed_by="drafter", at=AT)
        store.reject(c, org_id=ORG, line_id=line, decided_by="founder", at=AT)
    for act in (lambda c: store.accept(c, org_id=ORG, line_id=line, decided_by="f", at=AT),
                lambda c: store.reject(c, org_id=ORG, line_id=line, decided_by="f", at=AT),
                lambda c: store.remove(c, org_id=ORG, line_id=line, decided_by="f", at=AT)):
        with pytest.raises(store.CompanyBriefError):
            with engine.begin() as c:
                act(c)
    with pytest.raises(store.CompanyBriefError) as missing:
        with engine.begin() as c:
            store.accept(c, org_id=ORG, line_id="cbl_nope", decided_by="f", at=AT)
    assert missing.value.code == "not_found"


def test_a_malformed_line_is_refused_before_it_is_written(engine):
    with pytest.raises(ValueError):
        with engine.begin() as c:
            store.propose(c, org_id=ORG, section="watchlist", words="a portal", proposed_by="d",
                          at=AT)                                  # no domain
    with engine.connect() as c:
        assert c.execute(text("select count(*) from company_brief_lines where org_id = :o"),
                         {"o": ORG}).scalar() == 0


def test_a_public_mail_host_is_never_a_watchlist_domain(engine):
    for act in (lambda c: store.propose(c, org_id=ORG, section="watchlist", words="gmail",
                                        domain="gmail.com", proposed_by="drafter", at=AT),
                lambda c: store.add(c, org_id=ORG, section="watchlist", words="gmail",
                                    domain="GMAIL.com", decided_by="founder", at=AT)):
        with pytest.raises(ValueError):
            with engine.begin() as c:
                act(c)


def test_every_write_drops_the_cached_brief(engine, monkeypatch):
    dropped: list[str] = []
    monkeypatch.setattr("genios_engine.platform.company_brief.invalidate",
                        lambda org_id=None: dropped.append(org_id))
    with engine.begin() as c:
        line = store.propose(c, org_id=ORG, section="goals", words="raise the pre-seed round",
                             proposed_by="drafter", at=AT)
        store.accept(c, org_id=ORG, line_id=line, decided_by="founder", at=AT)
        store.remove(c, org_id=ORG, line_id=line, decided_by="founder", at=AT)
        store.add(c, org_id=ORG, section="goals", words="land three design partners",
                  decided_by="founder", at=AT)
    assert dropped == [ORG, ORG, ORG, ORG]


# =================================================================================================
# STEP-16 · 0242 — the brief keeps what you corrected (`yc2_w27_s16` M46.C5.L-contract.V0.U01; `03` F126, F157)
# =================================================================================================
from pathlib import Path  # noqa: E402

MIGRATION_0242 = Path(__file__).resolve().parents[2] / "migrations" / "0242_company_brief_corrections.sql"


def test_0242_adds_two_nullable_columns_and_nothing_else():
    sql = " ".join(line.split("--", 1)[0] for line in MIGRATION_0242.read_text(encoding="utf-8").splitlines())
    sql = " ".join(sql.lower().split())
    statements = [s.strip() for s in sql.split(";") if s.strip() and not s.strip().startswith("comment on")]
    assert statements == [
        "alter table company_brief_lines add column if not exists proposed_kind text",
        "alter table company_brief_lines add column if not exists replaces text"], statements


def test_the_columns_are_nullable_text_with_no_default(engine):
    with engine.connect() as c:
        cols = {r.column_name: r for r in c.execute(text(
            "select column_name, data_type, is_nullable, column_default from information_schema.columns "
            "where table_name = 'company_brief_lines' and column_name in ('proposed_kind', 'replaces')"))}
    assert set(cols) == {"proposed_kind", "replaces"}
    assert all((r.data_type, r.is_nullable, r.column_default) == ("text", "YES", None) for r in cols.values())


def test_a_line_written_as_the_previous_image_writes_it_keeps_neither(engine):
    """The previous image never names either column: its insert still runs, and leaves both null."""
    with engine.begin() as c:
        c.execute(text(
            "insert into company_brief_lines (org_id, line_id, section, text, address, domain, kind, status, "
            "proposed_by, evidence, proposed_at) values (:o, 'cbl_prev', 'goals', 'raise the round', null, null, "
            "null, 'proposed', 'drafter', '[]'::jsonb, :at)"), {"o": ORG, "at": AT})
        row = c.execute(text("select proposed_kind, replaces from company_brief_lines where org_id = :o "
                             "and line_id = 'cbl_prev'"), {"o": ORG}).one()
    assert tuple(row) == (None, None)
