"""Step 13 · `to` and `cc` are read, flattened one line later, and flattened AGAIN by Layer 2.

    pytest tests/capture/test_the_join_keys_survive.py -q

Benchmark P4 asks *"for every external meeting, was there a follow-up email within 7 days?"* — and
that join needs one thing: **`Manik` on a calendar invite and `Manik` in an email must be joinable.**

**THE BOUNDARY, because it is easy to get wrong and §9 forbids crossing it:**

> Layer 2 owns **identity resolution** — deciding two mentions are one person.
> Layer 1 owns **preserving the keys that make resolution possible**, and never destroying them.

This file is entirely about the second sentence.

**WHAT THE PREMISE CHECK FOUND, 2026-09-24 — three chances, all missed:**

    composio.py:522-525   to_emails and cc_emails are read SEPARATELY from the headers
    composio.py:318       recipients = tuple(to_emails) + tuple(cc_emails)   ← flattened
    composio.py:326       raw={... "to": to_emails, "cc": cc_emails}         ← still there!
    context/runner.py:161 recipients = (raw.get("to") or []) + (raw.get("cc") or [])  ← flattened AGAIN

The distinction is read from the headers, destroyed on the typed object, survives in the raw dict,
and is then destroyed a second time by **the only consumer that reads it**. Nobody ever needed to
re-derive it; it was already there, twice.

⛔ **AND THE COST CHECK CONSTRAINS THE FIX.** `cache.KEY_COMPONENTS` includes `envelope_hash`, and
`extract()` passes `envelope=call.envelope` — **the rendered prompt block string**. So rendering
`cc:` into `_envelope_block` would change that string on every event and **re-extract the entire
corpus**.

It must not, and not only for the cost: **the model does not need cc-from-to to read a message.**
`to: a, b, c` is what the prompt has always said and what the model was calibrated on. The split is
a **Layer 2 join key**, so it crosses on the CONTRACT and leaves the prompt untouched. Paying a
re-extraction to tell a model something irrelevant to it would be the worst of both.

**BCC IS NOT AVAILABLE AND THE STEP'S E5 ASSUMES IT IS.** `grep -rn "bcc" genios_engine/capture/
connectors/` returns nothing: Gmail's API does not hand it to us. E5 says *"bcc respects
`visibility_rules.py`"* — there is nothing to respect it with. The field exists on the contract so
a source that DOES supply it has somewhere to put it, and it is empty everywhere today. Recorded,
not faked.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 24, tzinfo=timezone.utc)


# =============================================================================================
# 13-U1 · the split survives — on the contract, and NOT in the prompt
# =============================================================================================
def test_the_raw_object_keeps_to_and_cc_apart():
    """`RawObject.recipients` is one tuple, and the connector had two lists a line earlier."""
    from genios_engine.capture.connectors.base import RawObject

    fields = RawObject.__dataclass_fields__
    assert "to_recipients" in fields and "cc_recipients" in fields


def test_bcc_has_a_home_even_though_no_source_supplies_it():
    """E5, corrected. The step assumes bcc is available and governs it with `visibility_rules`.
    **Gmail's API never hands it to us** — `grep -rn bcc connectors/` is empty.

    The field exists so a source that DOES supply it has somewhere to put it, and it is empty
    everywhere today. An empty field with a reason is honest; a missing one means the next
    connector author invents a key.
    """
    from genios_engine.capture.connectors.base import RawObject

    assert "bcc_recipients" in RawObject.__dataclass_fields__
    assert RawObject.__dataclass_fields__["bcc_recipients"].default == ()


def test_recipients_stays_the_union_so_nothing_downstream_breaks():
    """`recipients` is read by the gate, by `derive_visibility`, by the audience multiplier and by
    the thread reconstructor. It keeps meaning exactly what it meant — everyone on the message —
    and the two new fields are ADDITIVE.

    A step that redefined `recipients` to mean "to only" would silently change the audience size on
    every scored signal in the system, which is the shape of mistake steps 9 and 12 both made.
    """
    from genios_engine.capture.connectors.base import RawObject

    raw = RawObject(source="gmail", object_type="email_message", source_object_id="m1",
                    occurred_at=NOW, actor_email="a@x.com",
                    to_recipients=("b@x.com",), cc_recipients=("c@x.com",),
                    recipients=("b@x.com", "c@x.com"))

    assert raw.recipients == ("b@x.com", "c@x.com")
    assert raw.to_recipients == ("b@x.com",) and raw.cc_recipients == ("c@x.com",)


def test_the_connector_stops_flattening_what_it_just_read():
    """`composio.py:318` had `to_emails` and `cc_emails` in hand and wrote
    `recipients=tuple(to)+tuple(cc)`. Both lists survive now, beside the union."""
    import inspect

    from genios_engine.capture.connectors import composio

    source = inspect.getsource(composio)
    assert "to_recipients=tuple(to_emails)" in source, (
        "the connector still discards the to/cc split one line after reading it")
    assert "cc_recipients=tuple(cc_emails)" in source


def test_the_split_reaches_the_landed_event():
    """A field the connector keeps and `SourceEvent` drops is a field nothing downstream can use —
    the same loss step 3 spent its length closing one seam further on."""
    from genios_engine.contracts.source_event import SourceEvent

    fields = SourceEvent.model_fields
    assert "to_recipients" in fields and "cc_recipients" in fields


# =============================================================================================
# ⛔ THE COST GUARD — the prompt must not move
# =============================================================================================
def test_the_rendered_envelope_block_is_byte_identical():
    """**THE MOST IMPORTANT ROW IN THIS FILE.**

    `cache.KEY_COMPONENTS` includes `envelope_hash`, and `extract()` hashes the RENDERED block
    string. Rendering `cc:` would change it on every event and **re-extract the whole corpus** — a
    third full bill, to tell a model something it does not need.

    `to:` has always meant everyone on the message, and that is what the model was calibrated on.
    The split crosses on the CONTRACT; the prompt stays exactly as it is.
    """
    from genios_engine.capture.semantic.extractor import EventEnvelope, _envelope_block

    envelope = EventEnvelope(direction="inbound", sender="a@x.com",
                             recipients=("b@x.com", "c@x.com"), subject="Renewal",
                             thread_position=1, thread_depth=2)
    rendered = _envelope_block(envelope)

    assert "to: b@x.com, c@x.com" in rendered
    assert "cc:" not in rendered, (
        "the envelope block gained a line — every event's envelope_hash just changed and the "
        "entire corpus is about to re-extract")


def test_the_extraction_cache_fingerprint_is_untouched():
    """The other half of the same guard: no vocabulary changed either."""
    from genios_engine.capture.semantic.vocabulary import vocabulary_fingerprint

    assert vocabulary_fingerprint() == "a3d5496aa0d3"


# =============================================================================================
# 13-U2 · a calendar attendee is a person, not an email string
# =============================================================================================
def test_an_attendee_with_no_email_is_kept_as_a_partial_identity():
    """E6. `calendar.py:118` reads `[a.get("email") for a in attendees if a.get("email")]` — an
    attendee with a display name and no address is **dropped entirely**, so a room booking or an
    external guest invited by name vanishes from the participant set.

    Keeping them partial is what lets L2 decide; dropping them decides for it, invisibly.
    """
    from genios_engine.capture.connectors.attendees import read_attendees

    people = read_attendees([{"displayName": "Meeting Room 3"},
                             {"email": "manik@acme.com", "displayName": "Manik"}])

    assert len(people) == 2
    partial = [p for p in people if p.email is None]
    assert len(partial) == 1 and partial[0].display_name == "Meeting Room 3"
    assert partial[0].is_partial is True


def test_an_attendees_response_is_preserved():
    """`responseStatus` is the difference between *"we invited them"* and *"they came"*, and P4
    asks about meetings that happened. Flattening an attendee to an email string throws it away —
    the gap `STATUS.md` already flagged as a step-16 finding."""
    from genios_engine.capture.connectors.attendees import read_attendees

    people = read_attendees([{"email": "manik@acme.com", "responseStatus": "accepted"},
                             {"email": "priya@acme.com", "responseStatus": "declined"}])

    assert [p.response for p in people] == ["accepted", "declined"]


def test_an_attendee_carries_the_same_key_shape_as_an_email_participant():
    """13-U2's whole point. If a calendar person and an email person have different shapes, L2
    cannot join them and P4 stays blocked whatever else is built."""
    from genios_engine.capture.connectors.attendees import read_attendees

    person = read_attendees([{"email": "Manik@Acme.com", "displayName": "Manik"}])[0]

    assert person.email == "manik@acme.com", (
        "the address is not normalised, so the same person on two sources will not join")


def test_two_addresses_with_the_same_display_name_stay_two_people():
    """E1, and the benchmark names this exact trap: `keshav@rocketsdr.com` and `keshav@gmail.com`.

    **§9: do not merge two addresses because the display names match.** L1 preserves keys; L2
    resolves identity. Merging here would put the graph back inside the capture layer and would do
    it with less information than the layer that owns the question.
    """
    from genios_engine.capture.connectors.attendees import read_attendees

    people = read_attendees([{"email": "keshav@rocketsdr.com", "displayName": "Keshav"},
                             {"email": "keshav@gmail.com", "displayName": "Keshav"}])

    assert len({p.email for p in people}) == 2, "L1 merged two identities — that is L2's call"


# =============================================================================================
# 13-U3 · meeting kind — deterministic, and `unknown` when it cannot be told
# =============================================================================================
def test_a_cohort_session_is_not_an_external_meeting():
    """The finding that makes this cheap and worth doing. On the pilot's 7 calendar events,
    **5 were cohort sessions** where no follow-up is expected — so *"0 of 7 followed up"* is a true
    number and a misleading finding.

    `calendar.py` already records the cost in its own comment: *"a meeting cannot be told apart
    from a broadcast, and 'send a recap' shipped on twenty-person cohort workshops the founder
    attended as one participant."*
    """
    from genios_engine.capture.connectors.attendees import MeetingKind, read_meeting_kind

    kind = read_meeting_kind(attendee_count=24, organiser_domain="acc.vc",
                             owner_domain="genios.ai", is_recurring=True)

    assert kind is MeetingKind.COHORT


def test_a_two_person_meeting_with_an_outside_organiser_is_external():
    """SENSITIVITY. A classifier that said COHORT for everything would satisfy the row above and
    make P4 report zero external meetings."""
    from genios_engine.capture.connectors.attendees import MeetingKind, read_meeting_kind

    kind = read_meeting_kind(attendee_count=2, organiser_domain="acme.com",
                            owner_domain="genios.ai", is_recurring=False)

    assert kind is MeetingKind.EXTERNAL


def test_a_meeting_among_our_own_people_is_internal():
    from genios_engine.capture.connectors.attendees import MeetingKind, read_meeting_kind

    kind = read_meeting_kind(attendee_count=3, organiser_domain="genios.ai",
                            owner_domain="genios.ai", is_recurring=False)

    assert kind is MeetingKind.INTERNAL


def test_an_unknowable_meeting_is_unknown_and_never_guessed():
    """E7. No organiser domain means we cannot tell whose meeting it is, and `unknown` is a real
    answer here exactly as it is everywhere else in this layer.

    Guessing EXTERNAL would put a follow-up nudge on a meeting that may not warrant one; guessing
    INTERNAL would hide a real one. Neither error is recoverable by the reader.
    """
    from genios_engine.capture.connectors.attendees import MeetingKind, read_meeting_kind

    assert read_meeting_kind(attendee_count=4, organiser_domain=None,
                             owner_domain="genios.ai", is_recurring=False) is MeetingKind.UNKNOWN
    assert read_meeting_kind(attendee_count=4, organiser_domain="acme.com",
                             owner_domain=None, is_recurring=False) is MeetingKind.UNKNOWN


# =============================================================================================
# 13-U5 · the joinability figure — how much of P4's join is actually possible
# =============================================================================================
def test_the_joinability_report_says_how_much_of_the_join_can_happen():
    """13-U5. *"What share of calendar attendees have an email-side counterpart key."*

    Without it, P4's answer is unfalsifiable: *"no follow-up found"* could mean no follow-up
    happened or that the two sides were never joinable. Gemini's 18-of-18 with a different
    denominator.
    """
    from genios_engine.capture.connectors.attendees import joinability_bp

    assert joinability_bp(attendee_emails={"a@x.com", "b@x.com"},
                          email_side_emails={"a@x.com"}) == 5000


def test_joinability_over_nothing_is_absent_rather_than_perfect():
    """Zero attendees is not a perfect join — it is nothing to join. Reporting 10000 would make an
    empty calendar look like flawless coverage."""
    from genios_engine.capture.connectors.attendees import joinability_bp

    assert joinability_bp(attendee_emails=set(), email_side_emails={"a@x.com"}) == 0


# =============================================================================================
# §9 · the boundary guard
# =============================================================================================
def test_layer_one_never_resolves_an_identity():
    """T6 / E8. §9: *"Do not resolve identities in L1. That is L2's, and doing it here would put
    the graph back inside the capture layer."*

    The module may normalise an address (lowercase, trim) because that is a property of the STRING.
    It may not decide two different strings are one person — that needs the graph.
    """
    import inspect

    from genios_engine.capture.connectors import attendees

    source = inspect.getsource(attendees)
    for forbidden in ("difflib", "fuzz", "levenshtein", "embedding", "similar"):
        assert forbidden not in source.lower(), (
            f"`{forbidden}` suggests L1 is resolving identity — that is Layer 2's")


# =============================================================================================
# THE WIRING — five steps running, a field added and nothing filling it
# =============================================================================================
def test_the_split_survives_normalisation():
    """`landing/normalize.py` builds the `SourceEvent` the rest of the system sees. A field the
    connector keeps and normalisation drops is a field nothing downstream can use — which is
    **exactly how this split died three times already.**"""
    import inspect

    from genios_engine.capture.landing import normalize

    source = inspect.getsource(normalize)
    for name in ("to_recipients=", "cc_recipients=", "bcc_recipients="):
        assert name in source, f"normalisation drops {name!r} — the fourth death of the same field"


def test_the_calendar_connector_actually_reads_attendees_as_people():
    """`attendees.py` passing its own tests proves nothing if `calendar.py` still does
    `[a.get("email") for a in ...]`. Asserted against the shipping connector."""
    import inspect

    from genios_engine.capture.connectors import calendar

    source = inspect.getsource(calendar)
    assert "read_attendees(" in source, "the calendar still flattens attendees to addresses"
    assert "read_meeting_kind(" in source, "no meeting kind is computed on the real path"


def test_an_attendee_without_an_email_survives_the_real_connector():
    """END TO END through `_to_raw`, because the unit test above only proves the helper works.

    A room booking or a guest invited by name used to vanish at `if a.get("email")`. Losing them
    makes the attendee list silently wrong, and a wrong attendee count is what `read_meeting_kind`
    classifies on.
    """
    from genios_engine.capture.connectors.calendar import ComposioCalendarConnector

    connector = ComposioCalendarConnector.__new__(ComposioCalendarConnector)
    connector._internal_emails = {"rohit@genios.ai"}
    raw = connector._to_raw({
        "id": "e1", "organizer": {"email": "acc@acc.vc"},
        "attendees": [{"email": "a@x.com", "responseStatus": "accepted"},
                      {"displayName": "Meeting Room 3"}],
        "start": {"dateTime": "2026-09-01T10:00:00Z"}, "updated": "2026-09-01T09:00:00Z"})

    people = raw.raw["attendee_people"]
    assert len(people) == 2, "the address-less attendee was dropped by the real connector"
    assert any(p["display_name"] == "Meeting Room 3" and p["email"] is None for p in people)
    assert any(p["response"] == "accepted" for p in people)


def test_the_calendars_recipients_field_is_byte_identical_to_before():
    """REGRESSION GUARD. `recipients` feeds `derive_visibility`, the audience multiplier and the
    thread reconstructor. The richer list is ADDITIVE; the old one must not have moved by a
    character, or every scored calendar signal changes silently."""
    from genios_engine.capture.connectors.calendar import ComposioCalendarConnector

    connector = ComposioCalendarConnector.__new__(ComposioCalendarConnector)
    connector._internal_emails = set()
    raw = connector._to_raw({
        "id": "e1", "organizer": {"email": "o@x.com"},
        "attendees": [{"email": "a@x.com"}, {"displayName": "Room"}, {"email": "b@x.com"}],
        "start": {"dateTime": "2026-09-01T10:00:00Z"}, "updated": "2026-09-01T09:00:00Z"})

    assert list(raw.recipients) == ["a@x.com", "b@x.com"], (
        "the address list changed shape — the room leaked into it, or an address was lost")
    assert raw.raw["attendees"] == ["a@x.com", "b@x.com"]


def test_meeting_kind_reaches_the_raw_payload():
    """13-U3 on the real path. A classifier nothing calls is the defect this plan has found in
    five consecutive steps."""
    from genios_engine.capture.connectors.calendar import ComposioCalendarConnector

    connector = ComposioCalendarConnector.__new__(ComposioCalendarConnector)
    connector._internal_emails = set()
    raw = connector._to_raw({
        "id": "e1", "organizer": {"email": "acc@acc.vc"},
        "attendees": [{"email": f"p{i}@x.com"} for i in range(20)],
        "start": {"dateTime": "2026-09-01T10:00:00Z"}, "updated": "2026-09-01T09:00:00Z",
        "recurringEventId": "r1"})

    assert raw.raw["meeting_kind"] == "cohort", (
        "a twenty-person recurring session is being treated as a meeting somebody owes a recap")
