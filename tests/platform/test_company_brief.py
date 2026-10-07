"""STEP-07 · the company brief, composed: from what the founder accepted, and nothing else.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/platform/test_company_brief.py -q

Tree `yc2_w27_s07 · M25.C1.L-data.V1.U04`. `brief_for` composes deterministically from `orgs`, the
people who are us (STEP-04) and the accepted lines — the same inputs, the same version id; a brief over
its budget is reported, not cut (`speedrun008/YC-II W27/` STEP-07 §6). `current` is what a model site
calls: cached, dropped on every write, and EMPTY when it cannot be read, so a failure costs the brief,
never the judgment.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.platform import company_brief as cb
from genios_engine.platform import company_brief_store as store

pytestmark = pytest.mark.pg

ORG = "org_s07_brief"
AT = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.platform.db import get_engine
    eng = get_engine(live_db_url)
    _reset(eng)
    with eng.begin() as c:
        c.execute(text("insert into orgs (id, name, company, email) values "
                       "(:o, 'Arjun Rao', 'Nimbus Labs', 'arjun@nimbuslabs.test')"), {"o": ORG})
        c.execute(text("insert into org_self_identities (org_id, kind, value, declared_by) values "
                       "(:o, 'domain', 'nimbuslabs.test', 'test')"), {"o": ORG})
    cb.invalidate(ORG)
    yield eng
    _reset(eng)
    cb.invalidate(ORG)


def _reset(eng):
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _seed(eng):
    with eng.begin() as c:
        store.add(c, org_id=ORG, section="goals", words="raise the pre-seed round",
                  decided_by="founder", at=AT)
        store.add(c, org_id=ORG, section="connectors", words="Introly — introduces people",
                  address="hello@introly.test", decided_by="founder", at=AT)
        store.add(c, org_id=ORG, section="watchlist", words="StartupSetu — the recognition portal",
                  domain="startupsetu.gov.test", decided_by="founder", at=AT)
        pending = store.propose(c, org_id=ORG, section="goals", words="a line nobody accepted",
                                proposed_by="drafter", at=AT)
    return pending


def test_no_accepted_line_is_no_brief(engine):
    with engine.begin() as c:
        store.propose(c, org_id=ORG, section="goals", words="a proposal only",
                      proposed_by="drafter", at=AT)
    with engine.connect() as c:
        assert not cb.brief_for(c, ORG)
    assert cb.current(engine, ORG).prompt_block() == ""


def test_the_brief_is_the_company_us_and_the_accepted_lines(engine):
    _seed(engine)
    with engine.connect() as c:
        brief = cb.brief_for(c, ORG)
    block = brief.prompt_block()
    assert "Nimbus Labs" in block and "Arjun Rao" in block
    assert "arjun@nimbuslabs.test" in block and "nimbuslabs.test" in block   # STEP-04's us
    assert "raise the pre-seed round" in block and "hello@introly.test" in block
    assert "a line nobody accepted" not in block


def test_the_same_inputs_give_the_same_version(engine):
    _seed(engine)
    with engine.connect() as c:
        one, two = cb.brief_for(c, ORG), cb.brief_for(c, ORG)
    assert one.version == two.version and one.prompt_block() == two.prompt_block()


def test_the_brief_of_a_past_instant_is_rebuilt(engine):
    _seed(engine)
    with engine.begin() as c:
        late = store.add(c, org_id=ORG, section="in_motion", words="hiring a founding engineer",
                         decided_by="founder", at=AT + timedelta(days=2))
        then = cb.brief_for(c, ORG, at=AT + timedelta(days=1))
        now = cb.brief_for(c, ORG)
    assert "hiring a founding engineer" not in then.prompt_block()
    assert "hiring a founding engineer" in now.prompt_block() and late
    assert then.version != now.version


def test_current_is_cached_and_a_write_drops_it(engine):
    _seed(engine)
    first = cb.current(engine, ORG)
    with engine.begin() as c:                         # a write OUTSIDE the store: the cache holds
        c.execute(text("update company_brief_lines set text = 'changed behind its back' "
                       "where org_id = :o and section = 'goals'"), {"o": ORG})
    assert cb.current(engine, ORG).version == first.version
    with engine.begin() as c:                         # a write THROUGH the store drops it
        store.add(c, org_id=ORG, section="preferences", words="never on a Sunday",
                  decided_by="founder", at=AT)
    after = cb.current(engine, ORG)
    assert after.version != first.version and "never on a Sunday" in after.prompt_block()


def test_a_brief_that_cannot_be_read_is_no_brief(engine):
    class Broken:
        def connect(self):
            raise RuntimeError("the database is gone")

    assert cb.current(Broken(), "org_unreadable").prompt_block() == ""


def test_named_sender_reads_the_current_brief(engine):
    _seed(engine)
    assert cb.named_sender(engine, ORG, "hello@introly.test") == "connector:hello@introly.test"
    assert cb.named_sender(engine, ORG, "updates@startupsetu.gov.test") == \
        "watchlist:startupsetu.gov.test"
    assert cb.named_sender(engine, ORG, "someone@else.test") is None
