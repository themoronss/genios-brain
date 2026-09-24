"""§4a · S01–S06 — ingestion and fields.

    pytest tests/scenarios/test_4a_ingestion_and_fields.py -q

*"Nothing can be extracted from a field that was never fetched."* These six sit at the very front of
the layer, which is why four of the eight defects in §1's table are here.
"""
from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


def _gmail():
    from genios_engine.capture.connectors.composio import ComposioGmailConnector

    connector = ComposioGmailConnector(api_key="", user_id="")
    connector._execute = lambda slug, args: {}       # a full MIME fetch would be a network call
    return connector


def _message(mid: str, headers: dict[str, str], body: str = "ok") -> dict:
    return {"id": mid, "threadId": "t1", "internalDate": "1756900000000", "labelIds": ["INBOX"],
            "payload": {"headers": [{"name": k, "value": v} for k, v in headers.items()],
                        "parts": [{"mimeType": "text/plain", "filename": "",
                                   "body": {"data": base64.urlsafe_b64encode(
                                       body.encode()).decode()}}]}}



def _obj(oid: str):
    """The shape `backfill_drain`'s own test uses — a real `RawObject` that survives the gate."""
    from genios_engine.capture.connectors.base import RawObject

    return RawObject(source="gmail", object_type="email", source_object_id=oid,
                     occurred_at=NOW, actor_type="external_contact", actor_email="a@acme.io",
                     raw={"subject": "proposal",
                          "body": "hello there, this is a real business message about the proposal."})


class _PagedConnector:
    """A connector whose history is a fixed list of pages, so exhaustion is observable."""

    source = "gmail"

    def __init__(self, pages) -> None:
        self.pages = pages

    def initial_snapshot(self, cursor, limit):
        from genios_engine.capture.connectors.base import SourceBatch

        idx = int(cursor) if cursor else 0
        return SourceBatch(objects=self.pages[idx] if idx < len(self.pages) else [],
                           next_cursor=str(idx + 1) if idx + 1 < len(self.pages) else None)

    def incremental_changes(self, cursor, limit, since=None):
        return self.initial_snapshot(cursor, limit)


def _gate_ctx(raw: dict):
    """A `GateContext` over a real `SourceEvent`, so `whitelist` is driven rather than imitated."""
    from genios_engine.capture.gate.context import GateContext
    from genios_engine.contracts.source_event import SourceEvent

    event = SourceEvent(event_id="e1", org_id="o", connection_id="c", source="gmail",
                        object_type="email_message", source_object_id="m1",
                        dedup_key="gmail:email_message:m1", occurred_at=NOW,
                        actor={"email": "stranger@unknown.test", "type": "external_contact"})
    return GateContext(event=event, raw=raw, sender_known=False)


# =================================================================================================
# S01 · F04/F05 — a branched thread
# =================================================================================================
def test_s01_a_branched_thread_reconstructs_the_branch_not_a_line():
    """Two people reply to the SAME message. That is a branch.

    Without the headers the chronological fallback makes it a line m1 → m2 → m3, and m3's
    `reply_depth` is wrong by one — which is what every thread in the corpus looked like until
    step 16.
    """
    from genios_engine.capture.structural.threads import ThreadMessage, assemble_chain

    chain = assemble_chain([
        ThreadMessage(message_id="m1", occurred_at=NOW, thread_id="t", actor_email="a@x.com"),
        ThreadMessage(message_id="m2", occurred_at=NOW + timedelta(minutes=10), thread_id="t",
                      actor_email="b@x.com", in_reply_to="m1"),
        ThreadMessage(message_id="m3", occurred_at=NOW + timedelta(minutes=20), thread_id="t",
                      actor_email="c@x.com", in_reply_to="m1")])

    assert {l.message.message_id: l.reply_depth for l in chain.links} == {"m1": 0, "m2": 1, "m3": 1}


def test_s01_the_headers_the_branch_needs_now_reach_the_raw_object():
    """The other half, and the half that was missing: `assemble_chain` was always correct and was
    never fed. Step 16's connector edit, driven on the real path."""
    raw = _gmail()._to_batch({"data": {"messages": [_message("m4", {
        "From": "p@acme.com", "Subject": "Re: Re: Re: renewal",
        "In-Reply-To": "<m3@acme.com>",
        "References": "<m1@acme.com> <m2@acme.com> <m3@acme.com>"})]}}).objects[0].raw

    assert raw["headers"]["In-Reply-To"] == "<m3@acme.com>"
    assert (raw["thread_position"], raw["thread_depth"]) == (4, 4)


def test_s01b_the_pipeline_still_hands_assemble_chain_a_single_message():
    """⛔ **OPEN, and recorded rather than hidden.** §1 says `assemble_chain` *"falls back to
    chronology"*. It never gets that far: the pipeline builds a list of **ONE** message, so full
    RFC 5322 parent resolution has still never run on real data.

    Step 16 carried the headers onto that `ThreadMessage` so closing this is one caller change
    rather than two. This test fails the day someone passes a thread — which is the point of an
    OPEN row: it is a defect with an address, not a TODO.
    """
    import inspect

    from genios_engine.capture import pipeline

    source = inspect.getsource(pipeline._thread_context)

    assert "[ThreadMessage(message_id=event.event_id" in source, (
        "the single-message call changed — S01b may now be closeable; re-check the registry")
    assert "in_reply_to=" in source and "references=reference_ids(" in source, (
        "the seam lost the headers it was given, so closing S01b became two changes again")


# =================================================================================================
# S02 · F04/F17 — bcc. IMPOSSIBLE, and the reason matters more than the row
# =================================================================================================
def test_s02_bcc_is_recorded_as_unavailable_with_its_reason():
    """⛔ **THE SCENARIO CANNOT BE SATISFIED AND THAT IS NOT A FAILURE.**

    §4a expects *"captured, and `visibility_rules` restricts who sees it"*. **Gmail's API does not
    supply bcc**, and on a message we RECEIVED it is invisible by definition — that is what bcc
    means. Step 13 found it, step 16 found it a second time, and the manifest row now ends the
    rediscovery.
    """
    from genios_engine.capture.connectors.manifest import MANIFESTS

    bcc = next(f for f in MANIFESTS["gmail"].fields if f.name == "bcc")

    assert bcc.captured is False and bcc.reason


def test_s02_the_contract_can_still_carry_a_bcc_if_a_source_ever_offers_one():
    """The half of S02 that IS real. The field exists and is empty everywhere — so the day a source
    supplies one, nothing downstream needs changing."""
    from genios_engine.capture.connectors.base import RawObject

    obj = RawObject(source="gmail", object_type="email_message", source_object_id="m1",
                    occurred_at=NOW, actor_email="a@x.com",
                    to_recipients=("b@x.com",), bcc_recipients=("hidden@x.com",))

    assert obj.bcc_recipients == ("hidden@x.com",)


def test_s02_visibility_governs_the_recipient_set_it_is_given():
    """F17's actual claim, separated from the impossible one: whatever recipients we DO have, the
    ACL is derived from them rather than left open."""
    from genios_engine.capture.visibility_rules import derive_visibility

    acl = derive_visibility(source="gmail", actor_email="a@x.com",
                            recipients=("b@x.com", "c@x.com"))

    assert acl is not None, "no ACL means the gate parks — the audience is never guessed"
    assert acl.scope == "participants"
    assert set(acl.principals) == {"a@x.com", "b@x.com", "c@x.com"}, (
        "the ACL IS the participant list — sender plus To/Cc, never a guess")


# =================================================================================================
# S03 · F04 — a tentative invite
# =================================================================================================
def test_s03_a_tentative_invite_keeps_its_response_status():
    """Step 13's fix. Attendees used to be flattened to address strings, so `responseStatus` — the
    difference between *"we invited them"* and *"they came"* — was destroyed at the connector.

    P4 asks about meetings that **happened**.
    """
    from genios_engine.capture.connectors.attendees import read_attendees

    people = read_attendees([
        {"email": "a@x.com", "responseStatus": "tentative", "displayName": "Ana"},
        {"email": "b@x.com", "responseStatus": "accepted"},
        {"displayName": "Boardroom 3"}])

    assert [(p.email, p.response) for p in people[:2]] == [
        ("a@x.com", "tentative"), ("b@x.com", "accepted")]
    assert len(people) == 3, "the address-less room was dropped again"


# =================================================================================================
# S04 · F02 — the cursor
# =================================================================================================
def test_s04_a_drain_that_exhausts_its_cursor_says_so():
    """Step 5's denominator. `cursor_exhausted` is **three-valued** — `True`, `False`, and `None`
    for *"nobody looked"* — because a two-valued flag makes an unmeasured sweep indistinguishable
    from a truncated one, and those license opposite claims."""
    from genios_engine.capture.acquire.sync_runner import backfill_drain
    from genios_engine.capture.landing.repository import InMemorySourceEventRepository

    total = backfill_drain(_PagedConnector([[_obj("m1"), _obj("m2")], [_obj("m3")]]),
                           org_id="o", connection_id="c",
                           repo=InMemorySourceEventRepository(), source="gmail", limit=10)

    assert total.cursor_exhausted is True
    assert total.page_budget_spent is False
    assert total.scanned == 3


def test_s04_a_drain_that_hits_its_budget_reports_truncated():
    """The other side, and the off-by-one step 5 caught: a drain of exactly N pages with budget N
    is **complete**, not truncated."""
    from genios_engine.capture.acquire.sync_runner import backfill_drain
    from genios_engine.capture.connectors.base import SourceBatch
    from genios_engine.capture.landing.repository import InMemorySourceEventRepository

    class _Endless:
        source = "gmail"

        def initial_snapshot(self, cursor, limit):
            n = int(cursor or 0)
            return SourceBatch(objects=[_obj(f"m{n}")], next_cursor=str(n + 1))

        def incremental_changes(self, cursor, limit, since=None):
            return self.initial_snapshot(cursor, limit)

    total = backfill_drain(_Endless(), org_id="o", connection_id="c",
                           repo=InMemorySourceEventRepository(), source="gmail", max_rounds=3)

    assert total.cursor_exhausted is False, "a drain that stopped early must not read complete"
    assert total.page_budget_spent is True, "and must say WHO stopped it"


# =================================================================================================
# S05 · GUARD — the attachment exemption must not narrow
# =================================================================================================
def test_s05_an_attachment_only_email_from_an_unknown_sender_survives():
    """W-04. N-06/N-07 drop on Gmail's own PROMOTIONS guess **regardless of attachments**, so a
    renewal notice with the countersigned PDF attached lost its covering email.

    A GUARD, not progress: it works, and this asserts the change did not cost it.
    """
    from genios_engine.capture.gate.rules import whitelist

    assert whitelist(_gate_ctx({"important_attachment": True,
                                "labelIds": ["PROMOTIONS"]})) == "W-04"
    assert whitelist(_gate_ctx({"labelIds": ["PROMOTIONS"]})) is None


# =================================================================================================
# S06 · F18 — the dedup key must not shift
# =================================================================================================
def test_s06_adding_a_field_does_not_re_land_the_message_as_new():
    """**F18 — dedup semantic collapse, in reverse.** Step 16 added fields to the raw dict. If the
    dedup key had included them, the whole corpus would have re-landed as new objects — an update
    destroyed as a duplicate's mirror image, and just as expensive.

    The key is `source:object_type:source_object_id[:content_version]`, and email passes **no**
    content version: *"the immutable object never re-lands."*
    """
    from genios_engine.contracts.source_event import compute_dedup_key

    assert compute_dedup_key("gmail", "email_message", "m1") == "gmail:email_message:m1"


def test_s06_a_changed_deal_DOES_re_land_because_it_states_a_content_version():
    """The deliberate other half. HubSpot and Linear pass `updatedAt` as `content_version`, so a
    stage move re-lands and updates instead of freezing at first-seen. **The same key does both
    jobs, and the difference is the connector's choice** — which is why this pair is one scenario."""
    from genios_engine.contracts.source_event import compute_dedup_key

    before = compute_dedup_key("hubspot", "deal", "d1", content_version="2026-09-01")
    after = compute_dedup_key("hubspot", "deal", "d1", content_version="2026-09-24")

    assert before != after
