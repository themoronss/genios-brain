"""STEP-09 · a rebuild files a connector's and a portal's mail exactly where the drain filed it.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/context/test_a_rebuild_files_as_the_drain_did.py -q

`context/backfill.backfill_correlations` (tree `yc2_w27_s09 · M27.C1.L-logic.V1.U05`, minted building
C1). A rebuild (`rebuild=True` — the history replay after new deal nodes, or an operator's repair)
re-derives every file from what each event left in the graph, and it passed correlation no roles: the
intro network the brief names anchored again, so every introduction the drain filed under the person
introduced was filed under Introly as well — the one `boardy.ai` file of 254 threads that STEP-09
exists to end, rebuilt by the repair. Now the rebuild reads who is a connector from the one answer
the drain reads (`introductions.connector_roles`), and every file it rebuilds is the file the drain
wrote: the introduction, a contact's reply in a thread of two files, a nudge, the next nudge in its
thread, the connector's own ask, a contact's mail that names the connector, a portal's notices.
"""
from __future__ import annotations

from datetime import timedelta

import pytest

from genios_engine.capture.gate.rules import AUTO_REPLY
from genios_engine.context.backfill import backfill_correlations
from genios_engine.platform import company_brief, company_brief_store

from .workstream_world import (CONNECTOR, FOUNDER, T0, UNSUBSCRIBE, WATCHED, anchors, later,
                               mention, process, reset, tenant)

pytestmark = pytest.mark.pg

ORG = "org_s09_rebuild"
RAHUL, FARAH = "rahul@kestrelcap.test", "farah@kitepath.test"

#: (event, sender, recipients, thread, headers, mentions, days after T0) — in the order they arrive.
WORLD = (
    ("evt_intro", CONNECTOR, (FOUNDER, RAHUL, FARAH), "t_intro", UNSUBSCRIBE,
     (mention("Rahul Menon"), mention("Farah Qureshi"), mention("Kestrel Capital", "organization"),
      mention("Kitepath", "organization")), 0),
    ("evt_farah", FARAH, (FOUNDER, CONNECTOR), "t_intro", None, (), 1),
    ("evt_nudge", CONNECTOR, (FOUNDER,), "t_nudges", UNSUBSCRIBE, (mention("Rahul"),), 2),
    ("evt_nudge2", CONNECTOR, (FOUNDER,), "t_nudges", UNSUBSCRIBE, (), 3),
    ("evt_ask", CONNECTOR, (FOUNDER,), "t_ask", UNSUBSCRIBE,
     (mention("Introly", "organization"),), 4),
    ("evt_thanks", RAHUL, (FOUNDER,), "t_thanks", None, (mention("Introly", "organization"),), 5),
    ("evt_notice", f"updates@{WATCHED}", (FOUNDER,), None, None, (), 6),
    ("evt_notice2", f"no-reply@notify.{WATCHED}", (FOUNDER,), None, None, (), 7),
)

#: Where the drain files each of them — asserted first, so the comparison is never two empties.
FILED = {
    "evt_intro": {"kestrelcap.test", "kitepath.test"},
    "evt_farah": {"kitepath.test"},
    "evt_nudge": {"kestrelcap.test"},
    "evt_nudge2": {"kestrelcap.test"},
    "evt_ask": {"introly.test"},
    "evt_thanks": {"kestrelcap.test"},
    "evt_notice": {WATCHED},
    "evt_notice2": {WATCHED},
}


@pytest.fixture
def store(pg_store):
    tenant(pg_store, ORG)
    with pg_store.engine.begin() as c:
        company_brief_store.add(c, org_id=ORG, section="connectors", address=CONNECTOR,
                                words="Introly — an AI agent that introduces the founder to people",
                                decided_by="founder", at=T0 - timedelta(days=30))
        company_brief_store.add(c, org_id=ORG, section="watchlist", domain=WATCHED,
                                words="StartupSetu — the startup recognition portal",
                                decided_by="founder", at=T0 - timedelta(days=30))
    yield pg_store
    reset(pg_store, ORG)
    company_brief.invalidate(ORG)


def _drain(store) -> dict[str, set[str]]:
    """Each mail as the drain hands it — the brief read as `context/runner` reads it."""
    brief = company_brief.current(store, ORG)
    assert brief.named_sender(CONNECTOR) == f"connector:{CONNECTOR}", "the brief did not land"
    for event_id, sender, recipients, thread, headers, mentions, days in WORLD:
        process(store, ORG, event_id=event_id, sender=sender, recipients=recipients, thread=thread,
                headers=headers, mentions=mentions, company_brief=brief, at=later(days))
    return {event_id: anchors(store, ORG, event_id) for event_id, *_ in WORLD}


def test_the_drain_files_the_world_as_step_09_says(store):
    assert _drain(store) == FILED


def test_a_rebuild_files_every_mail_where_the_drain_did(store):
    live = _drain(store)
    out = backfill_correlations(store, ORG, rebuild=True)
    assert out["events_correlated"] == len(WORLD)
    assert {event_id: anchors(store, ORG, event_id) for event_id in live} == live


@pytest.mark.parametrize("rebuild", [False, True], ids=["the replay after a drain", "a rebuild"])
def test_the_replay_files_nothing_the_drain_kept_out(store, rebuild):
    """A newsletter, the connector's own mailing that names Rahul, an out-of-office: the drain reads
    all three and files none. The history replay `api/routes._replay_l2_history` runs after every backfill
    drain (STEP-08's re-sync among them), and the rebuild after new deal nodes — neither may file
    them (`03` F101)."""
    _drain(store)
    brief = company_brief.current(store, ORG)
    process(store, ORG, event_id="evt_news", sender="editor@letters.test", thread="t_news",
            company_brief=brief, at=later(8), noise_type="newsletter")
    process(store, ORG, event_id="evt_digest", sender=CONNECTOR, thread="t_digest",
            headers=UNSUBSCRIBE, mentions=(mention("Rahul"),), company_brief=brief, at=later(9),
            noise_type="newsletter")
    process(store, ORG, event_id="evt_away", sender="priya@northwind.test", thread="t_away",
            company_brief=brief, at=later(10), availability_marker=AUTO_REPLY)
    kept_out = ("evt_news", "evt_digest", "evt_away")
    assert [anchors(store, ORG, e) for e in kept_out] == [set(), set(), set()]
    backfill_correlations(store, ORG, rebuild=rebuild)
    assert [anchors(store, ORG, e) for e in kept_out] == [set(), set(), set()]


def test_a_rebuild_never_anchors_the_connector_on_an_introduction(store):
    _drain(store)
    backfill_correlations(store, ORG, rebuild=True)
    for event_id in ("evt_intro", "evt_farah", "evt_nudge", "evt_thanks"):
        assert "introly.test" not in anchors(store, ORG, event_id), event_id
