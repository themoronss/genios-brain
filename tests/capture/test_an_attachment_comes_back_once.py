"""STEP-08 · an attachment comes back once — with its deleted message, never beside a copy that survived.

    pytest tests/capture/test_an_attachment_comes_back_once.py -q                            # memory
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/capture/test_an_attachment_comes_back_once.py -q

`capture/landing/reread.drop_reread_attachments` (tree `yc2_w27_s08 · M26.C2.L-logic.V0.U01`, and
`V0.U02`, minted building it). Gmail hands out a fresh `attachmentId` on every read, so a re-read
message brings its attachments back under keys never seen, and the check dropped them by asking
whether the PARENT message's key exists. STEP-08 frees the key of every message the old gate deleted
(`capture/landing/resync`), and the old gate deleted a junk message while its readable attachment
landed as its own event (`connectors/composio.attachment_overrides_junk`, `03` F58). Listed again,
that attachment would land a second time. So a copy is dropped when an attachment of the same
message already landed KEPT, as well as when the message's key exists — and it lands when the earlier
copy was deleted with its message (STEP-08 §8.2, §8.3.4).

U02 · the re-read ladder's own copy. The ladder (`capture/landing/unread`, STEP-05 / B18) re-lands a
KEPT attachment nothing has read — a recovery's, a promotion's, a parked extraction's — by rebuilding
it under its OWN key, set aside for the purpose. The check knew nothing of it: the parent message had
landed, so the copy was dropped before capture, the row restored, and the ladder gave the attachment up
after three tries — read never. A copy that carries `rereading` is the ladder reading what it holds,
not a listing's second copy, so it always goes through.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.landing.normalize import to_source_event
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.landing.reread import drop_reread_attachments

NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


def _raw(object_type: str, source_object_id: str, parent: str | None = None, *,
         rereading: str | None = None) -> RawObject:
    return RawObject(source="gmail", object_type=object_type, source_object_id=source_object_id,
                     parent_object_id=parent, occurred_at=NOW - timedelta(days=5),
                     rereading=rereading)


def _memory(_url):
    return InMemorySourceEventRepository(), None


def _postgres(url):
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — needs real Postgres")
    from genios_engine.capture.landing.pg_repository import PostgresSourceEventRepository
    return PostgresSourceEventRepository(url), url


@pytest.fixture(params=[_memory, pytest.param(_postgres, marks=pytest.mark.pg)],
                ids=["memory", "postgres"])
def ledger(request, live_db_url):
    repo, url = request.param(live_db_url)
    org = f"org_att_once_{uuid.uuid4().hex[:8]}"
    if url:
        from sqlalchemy import create_engine, text
        engine = create_engine(url)
        with engine.begin() as c:
            c.execute(text("insert into orgs (id, name) values (:o, 'attachment once')"), {"o": org})
    yield repo, org
    if url:
        with engine.begin() as c:
            c.execute(text("delete from source_events where org_id = :o"), {"o": org})
            c.execute(text("delete from orgs where id = :o"), {"o": org})


def _landed(repo, org: str, raw: RawObject, outcome: str, *, freed: bool = False) -> None:
    """A row as the ledger holds it. `freed`: its key marked the way STEP-08's re-sync marks a
    message the old gate deleted — the row is there, its key no longer is."""
    event = to_source_event(raw, org_id=org, connection_id="con_x")
    if freed:
        event = event.model_copy(update={"dedup_key": f"{event.dedup_key}#resync:{event.event_id}"})
    repo.add(event, outcome=outcome)


def _listing(message: str) -> list[RawObject]:
    """Gmail listing the message again: the message, and its attachment under a FRESH id."""
    return [_raw("email_message", message, parent="thread-1"),
            _raw("email_attachment", f"{message}::ANGjdJ_{uuid.uuid4().hex[:8]}", parent=message)]


def _kept(objects) -> list[str]:
    return [o.object_type for o in objects]


# ── U01 · a listing's copy ───────────────────────────────────────────────────────────────────────

def test_an_attachment_that_survived_its_deleted_message_is_not_landed_twice(ledger):
    repo, org = ledger
    _landed(repo, org, _raw("email_message", "m1", parent="thread-1"), "dropped", freed=True)
    _landed(repo, org, _raw("email_attachment", "m1::ANGjdJ_first", parent="m1"), "emitted")
    kept, dropped = drop_reread_attachments(_listing("m1"), org_id=org, repo=repo)
    assert (_kept(kept), dropped) == (["email_message"], 1), (
        "the message comes back; its attachment already is")


def test_an_attachment_deleted_with_its_message_comes_back_with_it(ledger):
    repo, org = ledger
    _landed(repo, org, _raw("email_message", "m1", parent="thread-1"), "dropped", freed=True)
    _landed(repo, org, _raw("email_attachment", "m1::ANGjdJ_first", parent="m1"), "dropped")
    kept, dropped = drop_reread_attachments(_listing("m1"), org_id=org, repo=repo)
    assert (_kept(kept), dropped) == (["email_message", "email_attachment"], 0)


def test_a_freed_message_with_no_attachment_row_brings_its_attachment(ledger):
    """The old fast path fetched confident junk as a list snippet: no MIME, no attachment event."""
    repo, org = ledger
    _landed(repo, org, _raw("email_message", "m1", parent="thread-1"), "dropped", freed=True)
    kept, dropped = drop_reread_attachments(_listing("m1"), org_id=org, repo=repo)
    assert (_kept(kept), dropped) == (["email_message", "email_attachment"], 0)


def test_a_message_whose_key_exists_still_drops_its_reread_attachments(ledger):
    repo, org = ledger
    _landed(repo, org, _raw("email_message", "m1", parent="thread-1"), "emitted")
    kept, dropped = drop_reread_attachments(_listing("m1"), org_id=org, repo=repo)
    assert (_kept(kept), dropped) == (["email_message"], 1)


def test_a_first_read_keeps_every_attachment(ledger):
    repo, org = ledger
    page = _listing("m1") + [_raw("email_attachment", "m1::second", parent="m1")]
    kept, dropped = drop_reread_attachments(page, org_id=org, repo=repo)
    assert (len(kept), dropped) == (3, 0)


def test_a_ledger_that_cannot_say_keeps_the_attachment():
    """A repository with only `exists` (an older double) — or one that fails — keeps the file:
    a duplicate is recoverable, a lost file is not."""
    class Old:
        def exists(self, *_a):
            return False

    kept, dropped = drop_reread_attachments(_listing("m1"), org_id="o", repo=Old())
    assert (len(kept), dropped) == (2, 0)


# ── U02 · the re-read ladder's own copy ──────────────────────────────────────────────────────────

def test_the_ladders_reread_of_a_kept_attachment_goes_through(ledger):
    repo, org = ledger
    _landed(repo, org, _raw("email_message", "m1", parent="thread-1"), "emitted")
    _landed(repo, org, _raw("email_attachment", "m1::ANGjdJ_first", parent="m1"), "emitted")
    again = _raw("email_attachment", "m1::ANGjdJ_first", parent="m1",
                 rereading="extraction_never_ran")
    kept, dropped = drop_reread_attachments([again], org_id=org, repo=repo)
    assert (kept, dropped) == ([again], 0), "the ladder reads what it holds — never a listing's copy"


def test_a_listing_copy_beside_the_ladders_reread_is_still_dropped(ledger):
    repo, org = ledger
    _landed(repo, org, _raw("email_message", "m1", parent="thread-1"), "emitted")
    again = _raw("email_attachment", "m1::ANGjdJ_first", parent="m1", rereading="promoted:N-02")
    listing = _raw("email_attachment", "m1::ANGjdJ_fresh", parent="m1")
    kept, dropped = drop_reread_attachments([again, listing], org_id=org, repo=repo)
    assert (kept, dropped) == ([again], 1)


def test_the_ladder_rebuilds_a_row_with_its_reason_on_it():
    """U02 holds only while the ladder's rebuild carries `rereading` — `unread.to_raw_object`."""
    from genios_engine.capture.landing.unread import to_raw_object
    row = SimpleNamespace(event_id="evt_1", enc_content=None, actor={}, occurred_at=NOW,
                          source="gmail", object_type="email_attachment",
                          source_object_id="m1::ANGjdJ_first", parent_object_id="m1",
                          internal_kind=None, recipients=(), reason_code="extraction_never_ran")
    assert to_raw_object(row, "unused").rereading == "extraction_never_ran"
