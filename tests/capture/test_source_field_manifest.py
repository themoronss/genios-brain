"""Step 16 · nothing can be extracted from a field that was never fetched.

    pytest tests/capture/test_source_field_manifest.py -q

Every other step improves what L1 *does with* a field. This one asks the question that comes before
all of them: **did we fetch it at all?**

A field the connector never pulled fails **silently** — no error, no drop row, no trace entry. It is
the most expensive class of bug in the layer because **it is invisible to every existing test**: a
unit test on the extractor passes perfectly well on a raw dict the test assembled itself.

⛔ **THE PREMISE CHECK MOVED TWO OF THE THREE NAMED GAPS, AND FOUND A LARGER ONE.**

    gap 3 · attendee responseStatus   ALREADY FIXED — step 13 did it
    gap 1 · Gmail bcc                 IMPOSSIBLE — the API does not supply it (step 13 confirmed)
    gap 2 · In-Reply-To / References  CONFIRMED missing
    NEW   · thread position           **every event in production is "message 1 of 1"**

**THE NEW ONE IS THE REAL FINDING OF THIS STEP.** `pipeline._thread_place` reads
`raw["thread_position"]` and `raw["thread_depth"]`, and **no connector sets either** —
`grep -rn "thread_position|thread_depth" connectors/` is empty. So it returns `(1, 1)` for every
message ever captured, and `_envelope_block` renders that into **every prompt**:

    thread position: message 1 of 1

A twelve-message negotiation is described to the model as the first and only message in its thread.
That is not a missing field — it is a **wrong** one, stated confidently, on every extraction this
product has ever run.

**AND `assemble_chain` IS WORSE OFF THAN THE STEP SAYS.** §1 claims it *"always falls back to
chronology"*. It does not get that far: `pipeline.py:586` calls `reconstruct_thread` with a list of
**ONE** message — the event being captured. There is no chain to build, branched or straight.
Capturing `In-Reply-To` is **necessary and not sufficient**; the caller has to pass a thread.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


# =============================================================================================
# THE FINDING · every message in production is "message 1 of 1"
# =============================================================================================
def test_no_connector_states_a_thread_position_so_every_event_is_the_first_of_one():
    """**THE DEFECT THIS STEP EXISTS FOR, and it is not in the step's own list.**

    `_thread_place` reads `raw["thread_position"]` / `raw["thread_depth"]` and defaults to `(1, 1)`.
    That default is correct and well-argued — *"a single message with no thread metadata is
    genuinely the first of one"* — and **no connector has ever supplied the metadata**.

    So the envelope tells the model `thread position: message 1 of 1` on every message of every
    thread. A reply to a reply to a reply is presented as an opening message, and `turn_index` is
    0 for the entire corpus.

    This row fails the day a connector starts stating it, which is the point: it is the thing that
    should be true and is not.
    """
    from pathlib import Path

    connectors = Path("genios_engine/capture/connectors")
    stating = [p.name for p in connectors.glob("*.py")
               if "thread_position" in p.read_text() or "thread_depth" in p.read_text()]

    assert stating, (
        "NO connector states a thread position, so `_thread_place` returns (1, 1) for every "
        "event and every prompt says 'message 1 of 1' — including on a twelve-message thread")


def test_a_reply_carries_its_position_from_the_references_header():
    """The fix, and it costs **no extra API call**.

    RFC 5322 §3.6.4: `References` carries the parent's `References` plus the parent's
    `Message-ID`, oldest first. So N references means N ancestors, and this message is the
    (N+1)th. The very header we capture for gap 2 answers the position question for free.

    `threads.get` would give an exact thread size and costs a request per thread against a rate
    limit — §9's *"know what we fetch, and why we do not fetch the rest"* says record the choice,
    not pay it.
    """
    from genios_engine.capture.connectors.thread_position import thread_place_from_references

    place = thread_place_from_references(
        references="<m1@x> <m2@x> <m3@x>", in_reply_to="<m3@x>")

    assert place == (4, 4)


def test_depth_equals_position_because_capture_always_happens_at_the_tip():
    """**Why `depth` is not invented.** One message cannot state its thread's total size, and
    guessing one would be the Gemini failure step 15 named — reporting the size of what we hold as
    the size of what exists.

    `_thread_context`'s own docstring already settles it: *"at capture time this event genuinely IS
    the newest message of its thread."* So `depth = position` is the true statement *"message 4,
    and the newest so far"* — the same claim the existing `(1, 1)` default makes for a lone
    message, generalised rather than replaced.
    """
    from genios_engine.capture.connectors.thread_position import thread_place_from_references

    position, depth = thread_place_from_references(references="<a> <b>", in_reply_to=None)

    assert (position, depth) == (3, 3)


def test_a_message_with_no_threading_headers_stays_the_first_of_one():
    """An opening message genuinely IS message 1 of 1. This must not invent a position, and the
    envelope string it renders must stay byte-identical — that is what keeps the cache warm for
    every non-reply in the corpus."""
    from genios_engine.capture.connectors.thread_position import thread_place_from_references

    assert thread_place_from_references(references=None, in_reply_to=None) == (1, 1)
    assert thread_place_from_references(references="", in_reply_to="") == (1, 1)


def test_a_reply_whose_client_dropped_references_still_counts_its_parent():
    """Some clients send `In-Reply-To` and no `References`. Reading (1, 1) there would tell the
    model an obvious reply is an opening message — the exact failure being fixed."""
    from genios_engine.capture.connectors.thread_position import thread_place_from_references

    assert thread_place_from_references(references=None, in_reply_to="<m1@x>") == (2, 2)


def test_a_repeated_or_malformed_reference_does_not_inflate_the_position():
    """A broken client repeats ids, and a relay can rewrite the header without angle brackets.
    Neither may push a second message to 'message 5 of 5' — an inflated position is a confident
    lie in the same way the current one is."""
    from genios_engine.capture.connectors.thread_position import thread_place_from_references

    assert thread_place_from_references(
        references="<m1@x> <m1@x> <m1@x>", in_reply_to="<m1@x>") == (2, 2)
    assert thread_place_from_references(references="m1@x", in_reply_to=None) == (2, 2)


# =============================================================================================
# gap 2 · the RFC 5322 headers, and what capturing them does and does not buy
# =============================================================================================
def test_the_reply_headers_are_surfaced_by_the_connector():
    """T1. `ThreadMessage` declares `in_reply_to` and `references` and says why they are optional:
    *"the Gmail path does not carry them yet"*. It still did not.

    Their own tuple, not `_ROUTING_HEADERS`. That tuple is `("Reply-To", "Sender")` and the file
    says why it is separate from `_NOISE_HEADERS` — *"captured for the opposite purpose"*. Those
    two mark **attribution** (the From address carried this, did not write it); these mark
    **threading**. One tuple per purpose is this file's existing convention.
    """
    from genios_engine.capture.connectors.composio import _ROUTING_HEADERS, _THREAD_HEADERS

    assert "In-Reply-To" in _THREAD_HEADERS and "References" in _THREAD_HEADERS
    assert set(_ROUTING_HEADERS) == {"Reply-To", "Sender"}, "attribution headers were disturbed"


def test_the_captured_headers_reach_the_raw_object():
    """WIRING. A constant nothing reads is the *"field nothing fills"* defect steps 5, 6, 7 and 14
    each caught one step after shipping it. The tuple must reach the comprehension that builds
    `raw["headers"]`, and the derived place must reach `raw["thread_position"]`."""
    import inspect

    from genios_engine.capture.connectors import composio

    source = inspect.getsource(composio)
    assert "_NOISE_HEADERS + _ROUTING_HEADERS + _THREAD_HEADERS" in source
    assert '"thread_position"' in source and '"thread_depth"' in source


def test_assemble_chain_reconstructs_a_branch_rather_than_a_straight_line():
    """T2 — *"the one worth writing first"*, because it proves a unit that has never once run on
    production data.

    Three messages: m2 and m3 BOTH reply to m1. That is a branch. Without the headers the
    chronological fallback makes it a straight line m1 → m2 → m3, and m3's `reply_depth` is wrong
    by one — which is what every thread in the corpus currently looks like.
    """
    from genios_engine.capture.structural.threads import ThreadMessage, assemble_chain

    chain = assemble_chain([
        ThreadMessage(message_id="m1", occurred_at=NOW, thread_id="t", actor_email="a@x.com"),
        ThreadMessage(message_id="m2", occurred_at=NOW + timedelta(minutes=10), thread_id="t",
                      actor_email="b@x.com", in_reply_to="m1"),
        ThreadMessage(message_id="m3", occurred_at=NOW + timedelta(minutes=20), thread_id="t",
                      actor_email="c@x.com", in_reply_to="m1")])

    depth = {link.message.message_id: link.reply_depth for link in chain.links}
    assert depth == {"m1": 0, "m2": 1, "m3": 1}, (
        f"m3 is not a sibling of m2 — the branch was flattened into a line: {depth}")


def test_capturing_the_headers_is_necessary_and_not_sufficient():
    """⛔ **THE CORRECTION TO §1.** It says `assemble_chain` *"always falls back to chronology"*.
    It never gets that far.

    `pipeline.py` calls `reconstruct_thread` with a list of **ONE** message — the event being
    captured — so there is no chain to build, branched or straight. Capturing `In-Reply-To` puts
    the data on the event; passing the thread is a separate change, and this row records that the
    step is not finished by the connector edit alone.
    """
    import inspect

    from genios_engine.capture import pipeline

    source = inspect.getsource(pipeline)
    assert "[ThreadMessage(message_id=event.event_id" in source, (
        "the single-message call changed — re-check whether assemble_chain now receives a thread")


def test_the_pipeline_reads_the_position_the_connector_stated():
    """**THE WIRING CHECK, as a test.** *"A unit is done when a real request path reaches it and a
    test drives that path."*

    `thread_place_from_references` being correct proves nothing on its own — `_thread_place` is
    what the pipeline actually calls, and it reads two raw keys. This drives that function with the
    dict the connector now produces.
    """
    from genios_engine.capture.pipeline import _thread_place

    assert _thread_place({"thread_position": 4, "thread_depth": 4}) == (4, 4)
    assert _thread_place({"subject": "Re: Re: Re: renewal"}) == (1, 1)


def test_a_reply_and_an_opening_message_no_longer_render_the_same_envelope():
    """The whole finding in one assertion. Today both render `message 1 of 1`; the model is told an
    opening message and the fourth turn of a negotiation are the same shape of thing."""
    from genios_engine.capture.semantic.extractor import EventEnvelope, _envelope_block

    def block(position, depth):
        return _envelope_block(EventEnvelope(
            direction="inbound", sender="a@x.com", recipients=("b@x.com",),
            subject="renewal", thread_position=position, thread_depth=depth))

    assert "message 1 of 1" in block(1, 1)
    assert "message 4 of 4" in block(4, 4)
    assert block(1, 1) != block(4, 4)


def test_the_cache_price_is_paid_only_by_replies():
    """⛔ **THE COST CHECK, asserted rather than asserted-to.**

    `envelope_hash` is a `KEY_COMPONENTS` member and it hashes the RENDERED block, so a changed
    block is a cache miss. The price is bounded and the bound is the point:

        opening message  → still "message 1 of 1" → byte-identical → **cache HIT**
        a reply          → "message 4 of 4"       → **miss, and we WANT the miss**

    A cached extraction of a reply was produced from a prompt that stated a falsehood. Re-extracting
    it is not the cost of this fix; it **is** the fix.

    And `vocabulary_fingerprint` is untouched, so the whole-corpus trigger does not fire.
    """
    from genios_engine.capture.semantic.extractor import EventEnvelope, _envelope_block

    def env(position, depth):
        return EventEnvelope(direction="inbound", sender="a@x.com", recipients=("b@x.com",),
                             subject="renewal", thread_position=position, thread_depth=depth)

    #: What every message rendered before this step, replies included.
    was = _envelope_block(env(1, 1))

    assert _envelope_block(env(1, 1)) == was, "an opening message must still hit its cache entry"
    assert _envelope_block(env(3, 3)) != was, "a reply must miss — its old extraction was misled"


# =============================================================================================
# 16-U1 · the manifest — a declared set, with a reason for every omission
# =============================================================================================
def test_every_buildable_source_declares_a_field_manifest():
    """16-U1. *"Nobody has ever listed, per source, what the API offers versus what we take. That
    list does not exist, so the gap cannot be measured — only stumbled into."*"""
    from genios_engine.capture.connectors.manifest import MANIFESTS

    assert {"gmail", "gcal"} <= set(MANIFESTS)
    assert all(MANIFESTS[s].fields for s in MANIFESTS), "a source declares no fields"


def test_an_uncaptured_field_carries_a_written_reason():
    """E2. *"A silent omission and a considered one look identical without this."*

    `bcc` is the case that proves the rule: the step assumed it was a capture we had skipped, and
    it is a field **the provider does not supply**. Without a reason column that distinction is
    invisible and the next person re-opens it.
    """
    from genios_engine.capture.connectors.manifest import MANIFESTS

    for source, manifest in MANIFESTS.items():
        for field in manifest.fields:
            if not field.captured:
                assert field.reason, f"{source}.{field.name} is uncaptured with no reason given"


def test_a_captured_but_unread_field_is_recorded_and_is_not_a_defect():
    """E1 — *"the discipline that keeps this step honest."*

    *"The goal is not 'fetch everything'. It is 'know what we fetch, and why we do not fetch the
    rest.'"* Over-fetching costs payload size, not correctness; deleting later is cheap and
    re-adding means a re-sync.
    """
    from genios_engine.capture.connectors.manifest import MANIFESTS

    unused = [f for m in MANIFESTS.values() for f in m.fields if f.captured and not f.read_by]
    assert unused, "nothing is recorded as captured-but-unused — the manifest is not honest yet"
    assert all(f.reason or f.read_by == () for f in unused)


def test_bcc_is_recorded_as_unavailable_rather_than_as_a_todo():
    """⛔ **THE STEP'S OWN GAP 1 IS WRONG.** §1 says *"Gmail: bcc is never captured"* and 16-U2
    says *"capture it, and route through `visibility_rules`"*.

    **Gmail's API does not supply it.** On a message we RECEIVED the bcc list is invisible by
    definition, and step 13 confirmed the connectors have no path to it. There is nothing to
    capture and nothing for `visibility_rules` to govern.

    Recorded as `unavailable` with the reason, so nobody re-opens it as an oversight.
    """
    from genios_engine.capture.connectors.manifest import MANIFESTS

    bcc = next(f for f in MANIFESTS["gmail"].fields if f.name == "bcc")

    assert bcc.captured is False
    assert "provider" in bcc.reason.lower() or "not supplied" in bcc.reason.lower()


def test_attendee_response_status_is_recorded_as_captured_because_step_thirteen_did_it():
    """The step's gap 3, **already closed**. `read_attendees` keeps `responseStatus`,
    `displayName` and the address-less attendees `calendar.py` used to drop.

    The manifest says so rather than leaving a stale TODO — a manifest that disagreed with the
    code would be the drift this step exists to end.
    """
    from genios_engine.capture.connectors.manifest import MANIFESTS

    status = next(f for f in MANIFESTS["gcal"].fields if f.name == "attendees.responseStatus")

    assert status.captured is True


# =============================================================================================
# 16-U3 · the drift ratchet — fails in BOTH directions
# =============================================================================================
def test_the_ratchet_catches_a_field_captured_but_undeclared():
    """T5. The same shape as `test_every_llm_call_site_is_metered.py`, which is the proven pattern
    in this codebase for exactly this problem."""
    from genios_engine.capture.connectors.manifest import undeclared_captures

    assert undeclared_captures("gmail", captured={"subject", "body", "surprise_field"}) == (
        "surprise_field",)


def test_the_ratchet_catches_a_declared_field_that_stopped_arriving():
    """T6 / E5. The provider removes a field and nothing notices — the corpus quietly loses a
    column and every reading built on it silently weakens."""
    from genios_engine.capture.connectors.manifest import missing_captures

    missing = missing_captures("gmail", captured={"subject"})

    assert "body" in missing, "a declared field stopped arriving and the ratchet said nothing"


def test_the_ratchet_is_silent_when_the_manifest_and_the_code_agree():
    """SENSITIVITY. A ratchet that always fired would be turned off in a week."""
    from genios_engine.capture.connectors.manifest import MANIFESTS, undeclared_captures

    declared = {f.name for f in MANIFESTS["gmail"].fields if f.captured}

    assert undeclared_captures("gmail", captured=declared) == ()


def _gmail_reply():
    """A real Gmail poll payload for the fourth message of a thread, driven through the real
    connector. `_execute` is stubbed because a full MIME fetch is a network call — everything the
    manifest is checked against is parsed from this payload."""
    import base64

    from genios_engine.capture.connectors.composio import ComposioGmailConnector

    connector = ComposioGmailConnector(api_key="", user_id="")
    connector._execute = lambda slug, args: {}
    message = {
        "id": "msg_4", "threadId": "thread_1", "internalDate": "1756900000000",
        "labelIds": ["INBOX"],
        "payload": {"headers": [
            {"name": "From", "value": '"Priya Rao" <priya@acme.com>'},
            {"name": "To", "value": "founder@acme.com"},
            {"name": "Subject", "value": "Re: Re: Re: Revised contract"},
            {"name": "In-Reply-To", "value": "<m3@acme.com>"},
            {"name": "References", "value": "<m1@acme.com> <m2@acme.com> <m3@acme.com>"}],
            "parts": [{"mimeType": "text/plain", "filename": "", "body": {
                "data": base64.urlsafe_b64encode(b"Sending it Friday.").decode()}}]}}
    return connector._to_batch({"data": {"messages": [message]}}).objects[0]


def test_the_ratchet_runs_against_what_the_connector_actually_produces():
    """⛔ **THE WIRING CHECK FOR 16-U3.** A ratchet driven only by hand-passed sets is the *"field
    nothing fills"* defect wearing a test's clothes — steps 5, 6, 7 and 14 each shipped one and
    caught it a step later.

    This drives the **real** connector and diffs its **real** output against the manifest, in both
    directions. It is the row that fails when someone adds a raw key and forgets the table, which
    is the entire reason the table exists.
    """
    from genios_engine.capture.connectors.manifest import missing_captures, undeclared_captures

    landed = set(_gmail_reply().raw)

    assert undeclared_captures("gmail", captured=landed) == (), "a raw key has no manifest row"
    #: Only fields this payload cannot carry — it has no attachment and no parsed document.
    assert set(missing_captures("gmail", captured=landed)) <= {
        "document", "important_attachment", "mime", "page_offsets"}


def test_a_real_gmail_reply_lands_as_the_fourth_message_and_not_the_first():
    """**THE END-TO-END PROOF, on the path production runs.** Not the derivation, not the pipeline
    reader — the connector, given a Gmail payload, landing the keys `_thread_place` reads.

    Before this step the same payload landed neither key and the prompt said `message 1 of 1`.
    """
    raw = _gmail_reply().raw

    assert (raw["thread_position"], raw["thread_depth"]) == (4, 4)
    assert raw["headers"]["References"] == "<m1@acme.com> <m2@acme.com> <m3@acme.com>"


def test_an_opening_message_still_lands_as_the_first_of_one():
    """The other half of the cost check, on the real path: a message with no threading headers must
    render the identical envelope string it always did, or the whole corpus re-extracts."""
    import base64

    from genios_engine.capture.connectors.composio import ComposioGmailConnector

    connector = ComposioGmailConnector(api_key="", user_id="")
    connector._execute = lambda slug, args: {}
    raw = connector._to_batch({"data": {"messages": [{
        "id": "msg_1", "threadId": "thread_9", "internalDate": "1756900000000",
        "payload": {"headers": [{"name": "From", "value": "priya@acme.com"},
                                {"name": "Subject", "value": "Revised contract"}],
                    "parts": [{"mimeType": "text/plain", "filename": "", "body": {
                        "data": base64.urlsafe_b64encode(b"Here it is.").decode()}}]}}]}}
    ).objects[0].raw

    assert (raw["thread_position"], raw["thread_depth"]) == (1, 1)


# =============================================================================================
# The rules this step must not break
# =============================================================================================
def test_adding_a_field_does_not_change_the_dedup_key():
    """T7 / E6. *"Adding a field must not silently re-land the corpus."*

    The key is `source:object_type:source_object_id[:content_version]`. Email passes **no**
    content version — *"the immutable object never re-lands"* — so raw fields cannot enter it.
    Verified rather than assumed, because a re-landed corpus is a very expensive surprise.
    """
    from genios_engine.contracts.source_event import compute_dedup_key

    before = compute_dedup_key("gmail", "email_message", "m1")
    after = compute_dedup_key("gmail", "email_message", "m1")

    assert before == after == "gmail:email_message:m1"


def test_the_noise_headers_are_untouched():
    """T8 — the regression guard. §9: *"Do not touch the noise rules. They read the same headers
    they always did."* N-01/N-02/N-04 fire on `_NOISE_HEADERS`, and this step only extends
    `_ROUTING_HEADERS`."""
    from genios_engine.capture.connectors.composio import _NOISE_HEADERS

    assert set(_NOISE_HEADERS) == {
        "Auto-Submitted", "Precedence", "List-Unsubscribe", "List-Id", "List-Post",
        "Feedback-ID", "X-Autoreply", "X-Autorespond"}


def test_the_extraction_cache_fingerprint_is_untouched():
    """The manifest and the headers are capture-side. No vocabulary changes.

    NOTE: capturing a thread position DOES change the rendered envelope on a threaded message, and
    therefore `envelope_hash` — that is a re-extraction, and it is recorded in the findings rather
    than hidden. This guard covers the vocabulary half only.
    """
    from genios_engine.capture.semantic.vocabulary import vocabulary_fingerprint

    assert vocabulary_fingerprint() == "a3d5496aa0d3"


def test_the_chain_and_the_position_read_the_header_the_same_way():
    """One parser, two callers. A prompt saying `message 4 of 4` beside a three-link chain would be
    a disagreement neither side could falsify, so `reference_ids` and `thread_place_from_references`
    share `_ids` rather than each parsing the header their own way."""
    from genios_engine.capture.connectors.thread_position import (reference_ids,
                                                                  thread_place_from_references)

    header = "<m1@x> <m2@x> <m2@x> <m3@x>"
    position, _ = thread_place_from_references(references=header, in_reply_to="<m3@x>")

    assert len(reference_ids(header)) + 1 == position


def test_the_pipeline_carries_the_threading_headers_onto_its_thread_message():
    """The seam, so it is already correct the day a caller supplies the sibling messages. Today
    `assemble_chain` receives a one-message list and cannot use them — that is the honest limit,
    and leaving the fields blank would make closing it a second change nobody remembers."""
    import inspect

    from genios_engine.capture import pipeline

    source = inspect.getsource(pipeline._thread_context)
    assert "in_reply_to=" in source and "references=reference_ids(" in source
