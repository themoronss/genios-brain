"""Identity parity — the substrate of cross-intelligence. The same human via gmail,
calendar, CRM and a typed note must mint ONE canonical person key, byte-identical,
from every writer. If two writers normalize differently, the graph reasons about
strangers and every cross-tool rule dies quietly."""
from __future__ import annotations

from genios_engine.capture.structured.apply import _emails_from, apply_relations
from genios_engine.capture.structured.registry import get_mapping
from genios_engine.context.pipeline import _norm_email
from genios_engine.platform.identity import norm_email


def test_one_definition_everywhere():
    assert _norm_email is norm_email             # pipeline aliases platform.identity


def test_plus_tag_strips_identically_in_both_lanes():
    # the fracture this file exists to prevent: calendar attendee priya+cal@ used to
    # become a DIFFERENT person than email sender priya@
    assert norm_email("Priya+cal@Chat360.io") == "priya@chat360.io"
    assert _emails_from("Priya+cal@Chat360.io") == [("priya@chat360.io", None)]
    assert _emails_from([{"email": "PRIYA+x@chat360.io", "displayName": "Priya"}]) \
        == [("priya@chat360.io", "Priya")]


def test_malformed_input_never_mints_a_key():
    for bad in (None, "", "no-at-sign", "@dom.com", "x@"):
        assert norm_email(bad) is None
    assert _emails_from(["not-an-email"]) == []


def test_hubspot_deal_bridges_to_people():
    """The island fix: a CRM deal payload carrying contact emails yields person edges
    whose canonical keys merge with email/calendar-derived persons."""
    m = get_mapping("hubspot", "deal")
    rels = apply_relations(m, {"dealname": "Pilot", "dealstage": "proposal",
                               "contact_email": "Rakesh+crm@meridian.io"})
    assert rels == [{"node_type": "person", "canonical_key": "rakesh@meridian.io",
                     "display_name": "rakesh@meridian.io", "edge_type": "involves",
                     "direction": "in"}]
    # list shape too (associations-style)
    rels2 = apply_relations(m, {"contacts": [{"email": "a@x.com"}, {"email": "b@x.com"}]})
    assert {r["canonical_key"] for r in rels2} == {"a@x.com", "b@x.com"}
    # absent fields → no edges, no crash
    assert apply_relations(m, {"dealname": "Pilot"}) == []


def test_calendar_attendees_still_merge():
    m = get_mapping("gcal", "calendar_event")
    rels = apply_relations(m, {"attendees": [{"email": "Priya+cal@chat360.io",
                                              "displayName": "Priya"}]})
    assert rels[0]["canonical_key"] == "priya@chat360.io"   # same key as the email lane
