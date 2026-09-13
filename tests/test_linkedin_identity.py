"""SCREEN_INTEL_P2 §3.2 / acceptance (6) — a LinkedIn-only person is ONE node with ONE strong alias.

    pytest tests/test_linkedin_identity.py -q
"""
from __future__ import annotations

import os

import pytest

from genios_engine.context.identity import ALIAS_EMAIL, ALIAS_LINKEDIN, _STRONG, alias_keys_for_node
from genios_engine.platform.identity import linkedin_handle, norm_linkedin_url, person_key

CANON = "https://www.linkedin.com/in/priya-s"


@pytest.mark.unit
@pytest.mark.parametrize("raw", [
    "https://www.linkedin.com/in/Priya-S",
    "https://www.linkedin.com/in/priya-s/",
    "http://in.linkedin.com/in/priya-s?trk=public_profile#about",
    "linkedin.com/in/PRIYA-S",
    "https://m.linkedin.com/in/priya-s/details/experience/",
    "li:https://www.linkedin.com/in/priya-s/",
    "  https://www.linkedin.com/in/priya-s  ",
])
def test_every_spelling_of_one_profile_normalises_to_one_url(raw):
    assert norm_linkedin_url(raw) == CANON
    assert linkedin_handle(raw) == "li:" + CANON


@pytest.mark.unit
@pytest.mark.parametrize("raw", [
    None, "", "https://www.linkedin.com/company/acme", "https://www.linkedin.com/feed/",
    "https://evil.com/in/priya-s", "priya@acme.io", "https://www.linkedin.com/in/",
])
def test_non_profiles_are_not_people(raw):
    assert norm_linkedin_url(raw) is None


@pytest.mark.unit
def test_person_key_normalises_handles_and_leaves_emails_as_before():
    assert person_key("li:http://uk.linkedin.com/in/Priya-S/") == "li:" + CANON
    assert person_key("Priya+cal@Acme.io") == "priya@acme.io"
    assert person_key("  Some-Id ") == "some-id"
    assert person_key(None) is None


@pytest.mark.unit
def test_a_li_person_is_findable_by_a_strong_linkedin_alias():
    keys = alias_keys_for_node(node_type="person", canonical_key="li:" + CANON,
                               display_name="Priya S")
    assert keys == [(ALIAS_LINKEDIN, CANON, "anchor")]
    assert ALIAS_LINKEDIN in _STRONG
    # email persons are unchanged
    assert alias_keys_for_node(node_type="person", canonical_key="p@acme.io",
                               display_name=None) == [(ALIAS_EMAIL, "p@acme.io", "anchor")]


@pytest.mark.pg
def test_the_same_li_url_twice_is_one_person_and_one_alias(pg_store):
    """Acceptance (6): two screen sessions name one counterparty by two spellings of one url."""
    from sqlalchemy import text

    from genios_engine.platform.ids import new_id

    org = None
    with pg_store.engine.begin() as c:
        org = c.execute(text("select id from orgs order by id limit 1")).scalar()
        slug = new_id("slug").lower().replace("_", "-")
        ids = [pg_store.find_or_create_node(
                   c, org_id=org, node_type="person",
                   canonical_key=person_key(f"li:{url}"), display_name="Priya",
                   event_id=None)
               for url in (f"https://www.linkedin.com/in/{slug}/",
                           f"http://in.linkedin.com/in/{slug.upper()}?trk=x")]
        nodes = c.execute(text(
            "select count(*) from graph_nodes where org_id=:o and canonical_key=:k "
            "and valid_to is null"),
            {"o": org, "k": f"li:https://www.linkedin.com/in/{slug}"}).scalar()
        aliases = c.execute(text(
            "select node_id from graph_aliases where org_id=:o and alias_type=:t and alias_key=:k"),
            {"o": org, "t": ALIAS_LINKEDIN,
             "k": f"https://www.linkedin.com/in/{slug}"}).fetchall()
        proposals = c.execute(text(
            "select count(*) from merge_proposals where org_id=:o and (left_node_id=:n "
            "or right_node_id=:n)"), {"o": org, "n": ids[0]}).scalar()
        c.execute(text("delete from graph_aliases where org_id=:o and node_id=:n"),
                  {"o": org, "n": ids[0]})
        c.execute(text("delete from graph_nodes where org_id=:o and node_id=:n"),
                  {"o": org, "n": ids[0]})
    assert ids[0] == ids[1]
    assert nodes == 1
    assert [r.node_id for r in aliases] == [ids[0]]
    assert proposals == 0


@pytest.mark.unit
def test_screen_sessions_have_no_visibility_rule_and_park_without_the_door_stamp():
    """G-11: only the promoter door may name a screen event's audience."""
    from genios_engine.capture.visibility_rules import derive_visibility

    assert derive_visibility(source="screen_session", actor_email="p@acme.io",
                             recipients=("rohit@genios.ai",), mailbox_owner="rohit@genios.ai") \
        is None
    assert derive_visibility(source="gmail", actor_email="p@acme.io",
                             recipients=("rohit@genios.ai",)).scope == "participants"
