"""G3 · the content-type router — Wave W3 (doc 04, L1.4.1-U1 and the derived U2).

    pytest tests/capture/semantic/test_router.py -q

Doc 04's acceptance line is *"a table-driven test with one row per condition, plus the
fallback"*, and it is taken literally: `SPEC_TABLE` below is doc 04's own six-row decision
table transcribed, and `test_the_doc_table_routes_as_written` is parametrized over it. Two
further things are asserted about the table itself, because a table-driven test over a table
the implementation does not use would be a test of a copy:

* **every doc row is covered.** The parametrization is checked to hit all six rule numbers, so
  a seventh rule added to `RULES` without a spec row here fails collection rather than passing
  silently under the fallback;
* **order is the semantics.** Rule 3 above rule 4 is not decoration — an `email_attachment`
  whose mime is `audio/m4a` is a recording, and reading it under the document prompt asks for
  clauses against a diarized conversation. The overlap rows below fix the precedence so a
  reordering that reads as formatting fails as behaviour.

The fallback row is asserted twice over: that an unknown object type reaches it, and that it
reports `fell_back=True`. The flag is the monitorable half — a rising fallback rate is a
connector emitting an object type nobody mapped, which is a bug with a fix, and a fallback that
looked like a rule-1 email would be indistinguishable from a healthy inbox.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.capture.semantic.profiles import PROFILE_IDS, PROFILES
from genios_engine.capture.semantic.router import (CRM_SOURCES, FALLBACK_RULE_NUMBER, RULES,
                                                   ProfileChoice, RoutingInput, RoutingRule,
                                                   is_note_field, routing_input_for,
                                                   select_profile)
from genios_engine.capture.source_registry import PROVIDER_CAPABILITY
from genios_engine.contracts.source_event import Actor, SourceEvent, compute_dedup_key

WAVE = "W3"
GATE = "G3"

#: Doc 04, L1.4.1-U1's table — one row per condition, in the doc's order, plus the fallback.
#: Each row is (rule number, expected profile, kwargs for RoutingInput, id).
SPEC_TABLE = (
    (1, "email", {"source": "gmail", "object_type": "email_message"}, "r1-email_message"),
    (2, "chat", {"source": "slack", "object_type": "slack_message"}, "r2-slack_message"),
    (2, "chat", {"source": "teams", "object_type": "chat_message"}, "r2-chat_message"),
    (3, "transcript", {"source": "gong", "object_type": "call"}, "r3-transcript_source"),
    (3, "transcript", {"source": "gdrive", "object_type": "file", "mime": "audio/m4a"},
     "r3-audio_mime"),
    (4, "document", {"source": "gdrive", "object_type": "file"}, "r4-file"),
    (4, "document", {"source": "gmail", "object_type": "email_attachment"}, "r4-attachment"),
    (4, "document", {"source": "upload", "object_type": "upload/document_chunk"},
     "r4-document_chunk"),
    (4, "document", {"source": "notion", "object_type": "notion_page"}, "r4-notion_page"),
    (5, "crm_note", {"source": "hubspot", "object_type": "engagement",
                     "field_name": "hs_note_body"}, "r5-hubspot_note"),
    (5, "crm_note", {"source": "salesforce", "object_type": "task",
                     "field_name": "Description"}, "r5-salesforce_note"),
    (6, "email", {"source": "stripe", "object_type": "subscription"}, "r6-fallback"),
)

ROWS = [pytest.param(number, profile, kwargs, id=name)
        for number, profile, kwargs, name in SPEC_TABLE]


def _event(source: str, object_type: str) -> SourceEvent:
    return SourceEvent(
        event_id="evt_router", org_id="org_router", connection_id="conn_router",
        source=source, object_type=object_type, source_object_id="obj-1",
        dedup_key=compute_dedup_key(source, object_type, "obj-1"),
        actor=Actor(type="external_contact", email="rohit@example.com"),
        occurred_at=datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc))


# ── U1 · the decision table ─────────────────────────────────────────────────────────────────

@pytest.mark.gate
@pytest.mark.parametrize("rule_number,expected_profile,kwargs", ROWS)
def test_the_doc_table_routes_as_written(rule_number, expected_profile, kwargs):
    """One row per condition of doc 04's L1.4.1-U1 table, plus the fallback."""
    choice = select_profile(RoutingInput(**kwargs))
    assert (choice.profile_id, choice.rule_number) == (expected_profile, rule_number), (
        f"{kwargs} routed to {choice.profile_id!r} by rule {choice.rule_number} "
        f"({choice.rule_name}); doc 04 row {rule_number} says {expected_profile!r}")


@pytest.mark.gate
def test_every_rule_in_the_table_has_a_spec_row():
    """A rule the implementation walks and the spec table never exercises is untested by
    construction — and it would be reached only by events nobody wrote a row for."""
    covered = {number for number, _, _, _ in SPEC_TABLE}
    declared = {rule.number for rule in RULES}
    assert covered == declared, (f"rules {sorted(declared - covered)} have no row in SPEC_TABLE "
                                 f"and rows {sorted(covered - declared)} name no rule")


@pytest.mark.gate
def test_the_fallback_row_is_flagged_as_a_fallback():
    """`fell_back` is the monitorable half of rule 6.

    A fallback that reported itself as a rule-1 email would make "this connector emits an object
    type nobody mapped" invisible — the fallback rate is the only place that bug surfaces before
    somebody reads a thin card and wonders why.
    """
    unknown = select_profile(RoutingInput(source="stripe", object_type="subscription"))
    known = select_profile(RoutingInput(source="gmail", object_type="email_message"))
    assert unknown.fell_back is True and unknown.rule_number == FALLBACK_RULE_NUMBER
    assert known.fell_back is False
    assert unknown.profile_id == known.profile_id == "email", (
        "both land on the email profile — which is exactly why the flag has to distinguish them")


#: Objects that satisfy TWO rules. Order decides, so each row pins which one wins and why a
#: reordering of `RULES` is a behaviour change rather than a formatting change.
PRECEDENCE_TABLE = (
    ({"source": "gmail", "object_type": "email_attachment", "mime": "audio/m4a"},
     "transcript", "rule 3 above rule 4: an audio attachment is a recording, not a document"),
    ({"source": "gong", "object_type": "file", "filename": "call.mp4"},
     "transcript", "rule 3 above rule 4: a recorder's file is a recording"),
    ({"source": "hubspot", "object_type": "file", "field_name": "notes"},
     "document", "rule 4 above rule 5: a file attached to a deal is still a file"),
    ({"source": "gmail", "object_type": "email_message", "mime": "audio/mpeg"},
     "email", "rule 1 above rule 3: the message is prose; its attachment lands as its own event"),
)


@pytest.mark.gate
@pytest.mark.parametrize("kwargs,expected,why",
                         [pytest.param(*row, id=row[1] + "-" + row[0]["object_type"])
                          for row in PRECEDENCE_TABLE])
def test_rule_order_decides_when_two_rules_match(kwargs, expected, why):
    """First match wins, in doc 04's order."""
    assert select_profile(RoutingInput(**kwargs)).profile_id == expected, why


@pytest.mark.gate
@pytest.mark.parametrize("doc_name,registry_name,source", [
    pytest.param("upload/document_chunk", "document_chunk", "upload", id="document_chunk"),
    pytest.param("notion_page", "page", "notion", id="notion_page"),
    pytest.param("email_message", "message", "gmail", id="email_message"),
])
def test_the_docs_name_and_the_connectors_name_route_the_same(doc_name, registry_name, source):
    """Doc 04 and `capture/source_registry.py` spell three object types differently.

    The doc writes `upload/document_chunk`, `notion_page` and `email_message`; the registry's
    descriptors declare `document_chunk`, `page` and `message`. Renaming either side would break
    the spec trace or every connector, so both spellings route identically — and this is the
    test that stops the second spelling from quietly reaching the fallback.
    """
    by_doc = select_profile(RoutingInput(source=source, object_type=doc_name))
    by_registry = select_profile(RoutingInput(source=source, object_type=registry_name))
    assert by_doc.profile_id == by_registry.profile_id
    assert by_registry.fell_back is False, (
        f"{source}/{registry_name} — the name the connector actually emits — fell through to the "
        "fallback, so every real event of this type would be read under the email prompt")


@pytest.mark.gate
def test_the_crm_source_set_is_derived_from_the_registry_and_matches_the_doc():
    """Doc 04 names `{hubspot, salesforce}`; the router derives the set from the one place a
    source is described, so a third CRM is routed without an edit here."""
    assert CRM_SOURCES == {"hubspot", "salesforce"}
    assert all(PROVIDER_CAPABILITY[source] == "crm" for source in CRM_SOURCES)


#: Rule 5's second clause, which doc 04 states only as *"field is a note"*.
NOTE_FIELD_TABLE = (
    ("hs_note_body", True, "HubSpot's own name for the note body"),
    ("engagement_note", True, "contains 'note'"),
    ("notes", True, "the plain plural"),
    ("Description", True, "Salesforce Task.Description is the written note"),
    ("amount", False, "a typed currency column, not prose"),
    ("dealstage", False, "an enum, not prose"),
    ("", False, "no field named at all"),
    (None, False, "no field named at all"),
)


@pytest.mark.gate
@pytest.mark.parametrize("field_name,expected,why",
                         [pytest.param(*row, id=str(row[0]) or "empty")
                          for row in NOTE_FIELD_TABLE])
def test_only_written_note_fields_take_a_crm_object_to_the_note_profile(field_name, expected, why):
    """A HubSpot deal routed by its `amount` column is a typed value, not a note — and reading a
    number under a prose prompt is how a mapped column becomes an invented sentence."""
    assert is_note_field(field_name) is expected, why
    choice = select_profile(RoutingInput(source="hubspot", object_type="deal",
                                         field_name=field_name))
    assert (choice.profile_id == "crm_note") is expected, why


@pytest.mark.gate
def test_a_note_field_on_a_non_crm_source_does_not_reach_the_note_profile():
    """Rule 5 is a conjunction. A Notion page with a `notes` property is a page."""
    choice = select_profile(RoutingInput(source="notion", object_type="page", field_name="notes"))
    assert choice.profile_id == "document" and choice.rule_number == 4


@pytest.mark.gate
def test_an_audio_mime_is_recognised_by_extension_when_the_mime_lies():
    """Gmail hands us `application/octet-stream` for a voice memo. The filename is then the only
    surviving evidence, and `capture/documents/transcript.py::is_audio` is the tree's one answer
    — the router reuses it rather than keeping a second list that drifts."""
    lying = RoutingInput(source="gmail", object_type="email_attachment",
                         mime="application/octet-stream", filename="standup.m4a")
    honest = RoutingInput(source="gmail", object_type="email_attachment",
                          mime="application/octet-stream", filename="contract.pdf")
    assert select_profile(lying).profile_id == "transcript"
    assert select_profile(honest).profile_id == "document"


@pytest.mark.gate
def test_every_rule_selects_a_registered_profile():
    """A rule naming a profile the registry does not serve renders no prompt at all."""
    unregistered = sorted({rule.profile_id for rule in RULES} - set(PROFILE_IDS))
    assert not unregistered, f"rules select {unregistered}, which the registry does not serve"
    for rule in RULES:
        assert PROFILES[rule.profile_id].prompt_template.strip()


@pytest.mark.gate
def test_a_rule_naming_an_unregistered_profile_is_refused_at_construction():
    """Constructed through the real dataclass, because `__post_init__` IS the check under test."""
    with pytest.raises(ValueError, match="unregistered profile"):
        RoutingRule(99, "bad", "newsletter", lambda routing: True, "why")


@pytest.mark.gate
def test_the_choice_carries_the_profile_it_names():
    """The convenience that stops a caller pairing one profile's id with another's template."""
    choice = select_profile(RoutingInput(source="gdrive", object_type="file"))
    assert choice.profile.profile_id == "document"
    assert choice.profile is PROFILES["document"]


@pytest.mark.gate
def test_a_choice_always_explains_itself():
    """`reason` is what somebody reads six weeks later to check the routing of a thin card."""
    for rule in RULES:
        assert rule.why.strip(), f"rule {rule.number} ({rule.name}) has no explanation"
    choice = select_profile(RoutingInput(source="gmail", object_type="email_message"))
    assert isinstance(choice, ProfileChoice) and choice.reason.strip()


# ── U2 · the routing input ──────────────────────────────────────────────────────────────────

@pytest.mark.gate
def test_routing_input_is_derived_from_the_event_plus_the_document_metadata():
    """L1.4.1-U2. `SourceEvent` carries neither a mime nor the CRM field being read, so the two
    facts rules 3 and 5 are stated in terms of arrive from the caller, in one place."""
    event = _event("gmail", "email_attachment")
    routing = routing_input_for(event, mime="audio/m4a", filename="standup.m4a")
    assert routing.source == "gmail" and routing.object_type == "email_attachment"
    assert select_profile(routing).profile_id == "transcript"

    plain = routing_input_for(event)
    assert plain.mime == "" and plain.field_name is None
    assert select_profile(plain).profile_id == "document", (
        "without the mime the same attachment is a document — which is why the derivation is a "
        "unit rather than four call sites each remembering to pass it")


@pytest.mark.gate
def test_routing_input_reads_nothing_from_the_event_but_source_and_object_type():
    """Two events differing only in org, actor and time route identically.

    The profile is a property of the CONTENT. The moment it becomes a property of the tenant,
    two identical PDFs extract differently and the L1.4.9 cache key — which contains
    `profile_id` — forks under keys that both claim to be canonical.
    """
    a = _event("gdrive", "file")
    b = a.model_copy(update={"org_id": "org_other", "event_id": "evt_other",
                             "actor": Actor(type="internal_user", email="p@example.com"),
                             "occurred_at": datetime(2020, 5, 5, tzinfo=timezone.utc)})
    assert routing_input_for(a) == routing_input_for(b)


@pytest.mark.gate
def test_an_event_with_no_source_is_refused_rather_than_routed():
    """An empty source makes rules 3 and 5 unreachable, so every CRM note and every recording
    would land on the email profile — a total, silent misroute that raises nothing."""
    with pytest.raises(ValueError, match="source is required"):
        RoutingInput(source="", object_type="email_message")


@pytest.mark.gate
def test_an_event_with_no_object_type_reaches_the_fallback_and_says_so():
    """A connector that forgot the object type is a bug, but not one worth stopping a sync for.
    It must be VISIBLE, though — `fell_back` is where it becomes countable."""
    choice = select_profile(RoutingInput(source="gmail", object_type=""))
    assert choice.fell_back is True and choice.profile_id == "email"
