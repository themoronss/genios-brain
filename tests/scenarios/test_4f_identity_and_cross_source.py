"""§4f · S35–S39 — identity and cross-source.

    pytest tests/scenarios/test_4f_identity_and_cross_source.py -q

⛔ **THE THEME OF THIS SECTION IS A REFUSAL.** L1's job is to **preserve the keys** and let L2
decide who is one person. Every row here is either *"do not destroy this"* or *"do not merge this"*.

S35 is the sharpest: `keshav@rocketsdr.com` and `keshav@gmail.com` are probably the same human, and
**L1 must keep them as two identities anyway.** Merging on a local part is how one person's work
address absorbs a stranger with the same first name — F06 in the direction that cannot be undone,
because once two people are one row nothing downstream can tell they were ever two.

Step 13's finding sits under all of it: `to` and `cc` were read separately from the headers,
**flattened one line later**, preserved in the raw dict, and **flattened again** by the only
consumer that read them. Three chances, all missed, and the suite green throughout.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)


# =================================================================================================
# S35 · F06 — two addresses, one human, and L1 must NOT merge them
# =================================================================================================
def test_s35_two_addresses_for_one_human_stay_two_identities_in_l1():
    """⛔ **The merge L1 is forbidden to make.**

    They are probably the same Keshav. L1 has no evidence of that — only a matching local part —
    and a merge on that basis lets one person's work address absorb a stranger.

    **A wrong split is recoverable downstream. A wrong merge is not.**
    """
    from genios_engine.platform.identity import person_key

    assert person_key("keshav@rocketsdr.com") != person_key("keshav@gmail.com")


def test_s36_one_address_with_two_display_names_is_one_identity():
    """The other direction, and it IS safe. The address is the identity; the display name is what
    a mail client happened to render. *"Keshav"* and *"Keshav R."* are one person by the only
    evidence L1 has."""
    from genios_engine.capture.landing.normalize import to_source_event
    from genios_engine.capture.connectors.base import RawObject
    from genios_engine.platform.identity import person_key

    def _event(name: str):
        return to_source_event(RawObject(
            source="gmail", object_type="email_message", source_object_id="m1",
            occurred_at=NOW, actor_email="keshav@rocketsdr.com", actor_name=name,
            actor_type="external_contact", raw={"subject": "s", "body": "b"}),
            org_id="o", connection_id="c")

    short, long = _event("Keshav"), _event("Keshav R.")

    assert person_key(short.actor.email) == person_key(long.actor.email)
    assert (short.actor.name, long.actor.name) == ("Keshav", "Keshav R."), (
        "the display name must SURVIVE — 204 of 340 graph nodes once fell back to an address")


def test_s36_case_and_whitespace_do_not_mint_a_second_identity():
    """`Keshav@RocketSDR.com ` and `keshav@rocketsdr.com` are one address. Splitting on casing
    would be F06 in the *other* direction — an identity per mail client."""
    from genios_engine.platform.identity import person_key

    assert person_key(" Keshav@RocketSDR.com ") == person_key("keshav@rocketsdr.com")


# =================================================================================================
# S37 · F16 — L1 preserves both keys, L2 decides
# =================================================================================================
def test_s37_the_calendar_side_and_the_email_side_both_survive_capture():
    """L1's contribution to the join is **not destroying the keys**.

    Step 13's finding: attendees were reduced to address strings, so a room booking or a guest
    invited by name **vanished from the participant set**, and `responseStatus` went with it.
    """
    from genios_engine.capture.connectors.attendees import attendee_emails, read_attendees

    people = read_attendees([{"email": "a@acme.com", "responseStatus": "accepted"},
                             {"displayName": "Boardroom 3"}])

    assert attendee_emails(people) == ("a@acme.com",), "the flat shape still means what it meant"
    assert len(people) == 2, "and the richer list travels beside it, room included"


def test_s37_joinability_is_measurable_so_p4_is_falsifiable():
    """⛔ **Without this figure, P4's answer is unfalsifiable.**

    *"No follow-up found"* could mean no follow-up happened, or that the two sides were never
    joinable at all — and those have **opposite fixes**. It is Gemini's 18-of-18 with a different
    denominator.
    """
    from genios_engine.capture.connectors.attendees import joinability_bp

    assert joinability_bp(attendee_emails=["a@x.com", "b@x.com", "c@x.com", "d@x.com"],
                          email_side_emails=["a@x.com", "b@x.com"]) == 5000


def test_s37_an_empty_calendar_reports_zero_and_not_a_perfect_join():
    """*"An empty calendar is nothing to join, and reporting 10000 would make it look like flawless
    coverage."* The same failure as defaulting an unknown denominator to full."""
    from genios_engine.capture.connectors.attendees import joinability_bp

    assert joinability_bp(attendee_emails=[], email_side_emails=["a@x.com"]) == 0


def test_s37_layer_one_may_not_be_imported_by_the_contracts_it_feeds():
    """**The structural half of "L2 decides".** If `contracts` could import `capture`, the decision
    about who is one person could quietly migrate down here where no L2 test would see it.

    A code review cannot enforce this. A test can — technique 4.
    """
    import pathlib

    offenders = [p.name for p in pathlib.Path("genios_engine/contracts").glob("*.py")
                 if "from genios_engine.capture" in p.read_text()
                 or "import genios_engine.capture" in p.read_text()]

    assert offenders == [], f"contracts import capture: {offenders}"


# =================================================================================================
# S38 · F16 — a cohort session is not an external meeting
# =================================================================================================
def test_s38_a_large_recurring_session_is_a_cohort_even_with_no_identifiable_owner():
    """⛔ **THE RUNG ORDER STEP 13 CORRECTED.** `COHORT` used to sit **below** the domain check, so
    a twenty-person recurring session with no identifiable owner came back `UNKNOWN` — and would
    have been chased for a recap email to twenty strangers.

    It goes first because *"it needs no domains at all"* and because **it is the only rung that can
    only ever SUPPRESS an expectation.**
    """
    from genios_engine.capture.connectors.attendees import MeetingKind, read_meeting_kind

    kind = read_meeting_kind(attendee_count=20, organiser_domain=None,
                             owner_domain=None, is_recurring=True)

    assert kind == MeetingKind.COHORT


def test_s38_an_external_meeting_is_still_external():
    """The case P4 is actually about, and the one the cohort rung must not swallow."""
    from genios_engine.capture.connectors.attendees import MeetingKind, read_meeting_kind

    assert read_meeting_kind(attendee_count=3, organiser_domain="acme.com",
                             owner_domain="ours.com", is_recurring=False) == MeetingKind.EXTERNAL


def test_s38_an_unknowable_meeting_says_unknown_rather_than_guessing():
    """Rung 2. *"Guessing EXTERNAL would put a follow-up on a meeting that may not warrant one
    while guessing INTERNAL would hide a real one. Neither is recoverable by a reader."*

    §5 puts a model on "the remainder". The remainder is this rung, and `UNKNOWN` is a real answer
    rather than a gap a model should be paid to fill.
    """
    from genios_engine.capture.connectors.attendees import MeetingKind, read_meeting_kind

    assert read_meeting_kind(attendee_count=3, organiser_domain=None,
                             owner_domain="ours.com", is_recurring=False) == MeetingKind.UNKNOWN


# =================================================================================================
# S39 · F16 — a warm intro where the introduced person was never emailed
# =================================================================================================
def test_s39_the_recipient_graph_can_answer_who_was_introduced_but_never_written_to():
    """⛔ **THE QUESTION STEP 13 MADE ANSWERABLE, and the flattening that made it impossible.**

    A warm intro puts the new person on `cc`. If `to` and `cc` are flattened into one
    `recipients` tuple, *"was this person ever written TO, or only ever copied?"* cannot be asked —
    and that is exactly the difference between an intro that was followed up and one that was not.
    """
    from genios_engine.capture.connectors.base import RawObject

    intro = RawObject(source="gmail", object_type="email_message", source_object_id="m1",
                      occurred_at=NOW, actor_email="connector@network.test",
                      recipients=("founder@ours.com", "target@acme.com"),
                      to_recipients=("founder@ours.com",),
                      cc_recipients=("target@acme.com",))

    assert intro.recipients == ("founder@ours.com", "target@acme.com"), (
        "the flat set must keep meaning everyone on the message — nothing downstream shifts")
    assert "target@acme.com" in intro.cc_recipients
    assert "target@acme.com" not in intro.to_recipients, (
        "copied is not addressed, and collapsing them loses the whole question")


def test_s39_the_gmail_connector_stops_flattening_to_and_cc_on_the_real_path():
    """The wiring, not the contract. Step 13's finding was that the split existed in the raw dict
    and was thrown away — so proving the FIELD exists proves nothing. This drives the connector."""
    import base64

    from genios_engine.capture.connectors.composio import ComposioGmailConnector

    connector = ComposioGmailConnector(api_key="", user_id="")
    connector._execute = lambda slug, args: {}
    obj = connector._to_batch({"data": {"messages": [{
        "id": "m1", "threadId": "t1", "internalDate": "1756900000000",
        "payload": {"headers": [{"name": "From", "value": "connector@network.test"},
                                {"name": "To", "value": "founder@ours.com"},
                                {"name": "Cc", "value": "target@acme.com"},
                                {"name": "Subject", "value": "intro"}],
                    "parts": [{"mimeType": "text/plain", "filename": "", "body": {
                        "data": base64.urlsafe_b64encode(b"meet target").decode()}}]}}]}}
    ).objects[0]

    assert obj.to_recipients == ("founder@ours.com",)
    assert obj.cc_recipients == ("target@acme.com",)
