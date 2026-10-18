"""STEP-15 · the brief says who someone is by name — never by an address, never a role mailbox.

    .venv/bin/python -m pytest -q tests/platform/test_a_party_is_named_never_addressed.py

`platform/self_identity.spoken_name` (tree `yc2_w27_s15` M44.C2.L-data.V0.U03, the desk's names). A calendar invite
and a first mail carry an address and no name: F54's attendees are `kavya@ferrypay.test` in memory, and the
organiser's mailbox `events@bluebayhub.test` is one of the case's forbidden names. A name is the display name when
it is one; else the word the address or domain spells; else none — said as "someone", never as the address.
"""
from __future__ import annotations

import pytest

from genios_engine.platform.self_identity import ROLE_MAILBOXES, spoken_name

pytestmark = pytest.mark.unit


@pytest.mark.parametrize("display, key, said", [
    ("Dev Malhotra", "dev@tanglewood.test", "Dev Malhotra"),       # a name is a name
    ("  Meera   Shah ", None, "Meera Shah"),
    ("kavya@ferrypay.test", "kavya@ferrypay.test", "Kavya"),       # an address spells its person
    (None, "gaurav@stackfield.test", "Gaurav"),
    (None, "kavitha.nair@inboxmail.test", "Kavitha Nair"),
    (None, "Rhea+events@tallowfin.test", "Rhea"),                  # a +tag is not part of the name
    ("events@bluebayhub.test", "events@bluebayhub.test", None),    # a role mailbox names nobody
    (None, "no-reply@statestartup.gov.test", None),
    (None, "hello@introly.test", None),
    (None, "jsmith2014@mail.test", None),                          # digits: no word to say
    (None, "anne.marie.de.vries@x.test", None),                    # more than three parts is no name
    (None, "team.lead@x.test", None),                              # a role word in any part
    (None, "j.smith@x.test", None),                                # an initial is no word to say
    ("bluepeak.test", "bluepeak.test", "Bluepeak"),                # a domain spells its company
    (None, "statestartup.gov.test", "Statestartup"),
    (None, "gmail.com", None),                                     # a public mail host is nobody's company
    (None, "x1y.test", None),
    (None, None, None), ("", "", None),
])
def test_a_party_is_said_by_name(display, key, said):
    assert spoken_name(display, key) == said


def test_no_role_mailbox_is_said_and_the_list_is_closed():
    assert {"events", "hello", "info", "team", "support", "noreply"} <= ROLE_MAILBOXES
    for role in ROLE_MAILBOXES:
        assert spoken_name(None, f"{role}@company.test") is None
