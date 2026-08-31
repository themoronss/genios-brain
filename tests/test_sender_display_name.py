"""A person the source named must be shown by name, not by address.

Measured on the design partner's org: 0 of 1,397 source events carried `actor.name`, 204 of 340
graph nodes fell back to naming themselves after an address, and 69 of 115 live cards headlined a
machine identifier — "ydvkhushi721@gmail.com — warming, needs opening", "antler.co — fit not
assessed". The name was never missing from the mail; `From: "Deepthi Chandrashekhar" <deepthi@...>`
was parsed for its address and the display part was dropped on the floor.

The refusals matter as much as the extraction. A missing name stays missing: inventing "Ydvkhushi721"
out of a local-part is a confident lie, where showing the address is merely ugly.
"""
from __future__ import annotations

from genios_engine.capture.connectors.composio import _extract_display_name


def test_the_display_part_of_a_from_header_is_the_name():
    assert _extract_display_name('"Deepthi Chandrashekhar" <deepthi@nsrcel.iimb.ac.in>') == \
        "Deepthi Chandrashekhar"
    assert _extract_display_name("Rohit Swerashi <rohit@example.com>") == "Rohit Swerashi"


def test_a_bare_address_has_no_name():
    assert _extract_display_name("deepthi@nsrcel.iimb.ac.in") is None
    assert _extract_display_name("<deepthi@nsrcel.iimb.ac.in>") is None


def test_a_client_that_repeats_the_address_as_the_display_part_supplies_no_name():
    """Common, and the reason a naive `split('<')` produces "khushi@gmail.com — warming"."""
    assert _extract_display_name('"a@b.com" <a@b.com>') is None


def test_a_local_part_echo_is_not_a_name():
    """The exact case behind "ydvkhushi721". A string before the @ is not a person."""
    assert _extract_display_name("ydvkhushi721 <ydvkhushi721@gmail.com>") is None


def test_nothing_in_nothing_out():
    assert _extract_display_name(None) is None
    assert _extract_display_name("") is None


def test_a_quoted_name_containing_a_comma_survives():
    """`parseaddr` over hand-rolled splitting — a comma inside quotes is not a separator."""
    assert _extract_display_name('"Chandrashekhar, Deepthi" <d@x.com>') == "Chandrashekhar, Deepthi"


# ── the chain that carries it ────────────────────────────────────────────────────────────────
def test_the_raw_object_and_the_actor_both_carry_a_name():
    from datetime import datetime, timezone

    from genios_engine.capture.connectors.base import RawObject
    from genios_engine.contracts.source_event import Actor

    raw = RawObject(source="gmail", object_type="email_message", source_object_id="m1",
                    occurred_at=datetime(2026, 8, 29, tzinfo=timezone.utc),
                    actor_email="d@x.com", actor_name="Deepthi Chandrashekhar")
    assert raw.actor_name == "Deepthi Chandrashekhar"
    assert Actor(type="external_contact", email="d@x.com", name=raw.actor_name).name == \
        "Deepthi Chandrashekhar"


def test_normalize_passes_the_name_through():
    """The hop that made every stored actor nameless."""
    import inspect

    from genios_engine.capture.landing import normalize

    assert "name=raw.actor_name" in inspect.getsource(normalize)


def test_the_l2_runner_selects_and_forwards_the_name():
    import inspect

    from genios_engine.context import runner

    src = inspect.getsource(runner)
    assert "se.actor->>'name' as sender_name" in src, "L2 never reads the stored name"
    assert "sender_name=getattr(row, \"sender_name\", None)" in src, "L2 reads it and drops it"


def test_only_the_sender_is_named_not_every_recipient():
    """Recipients arrive as bare addresses in To/Cc, so naming them would attach the sender's
    name to whoever else was on the mail — a wrong name is far worse than an address."""
    import inspect

    from genios_engine.context import pipeline

    src = inspect.getsource(pipeline.process_event)
    assert "key == (sender_email or \"\").strip().lower()" in src
