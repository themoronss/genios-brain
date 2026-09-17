""""Sehan via Boardy" wrote nothing. Boardy carried what Sehan wrote.

`context/pipeline.py` attaches extracted content to `canon_node or document_node or meeting_node
or sender_node`, and the seam's own comment says why the middle two terms were added: a Drive
file's sender is whoever last edited it, and "filing a policy's contents on that colleague is the
exact facts-about-the-wrong-subject bug this seam already exists to fix". A relay is the same bug
one case further along, and the case the seam does not yet cover.

It is NOT covered by `is_automated_sender`. That table is a conservative list of machine
local-parts, and everything it matches is already routed through `is_noise` — kept out of the
network graph and out of correlation, so it can never anchor a relationship or a situation. An
intro network's `hello@` matches no machine pattern, so it arrived as a genuine correspondent.
"""
import pytest

from genios_engine.capture.gate.rules import (is_automated_sender, relayed_party_name,
                                              reply_to_party, sender_is_a_relay)


def _mail(**headers):
    return {"headers": dict(headers)}


# ── the display name, which works on mail already captured ───────────────────────────────────

@pytest.mark.parametrize("display, party", [
    ("Sehan Sanjula via Boardy", "Sehan Sanjula"),
    ("Harshita via Peak XV Intros", "Harshita"),
    ("Theresa via Antler", "Theresa"),
    ("jane.doe via groups.example.com", "jane.doe"),
    ("Priya  VIA  Boardy", "Priya"),
])
def test_a_relay_display_name_names_its_passenger(display: str, party: str) -> None:
    assert relayed_party_name(display) == party
    assert sender_is_a_relay(None, sender_name=display) is True


@pytest.mark.parametrize("display", [
    None, "", "   ",
    "Harshita Kaul",                 # an ordinary human name
    "Peak XV Partners",              # an ordinary org name
    "via",                           # the word alone names nobody
    "via Boardy",                    # no passenger on the left
    "Sehan via",                     # no relay on the right
    "Olivia via-Kent",               # hyphenated: not a free-standing separator
    "Viavi Solutions",               # contains the letters, not the word
])
def test_an_ordinary_display_name_is_not_a_relay(display) -> None:
    assert relayed_party_name(display) is None
    assert sender_is_a_relay(None, sender_name=display) is False


# ── Reply-To, which both proves the relay AND names the address ──────────────────────────────

def test_reply_to_names_the_party_behind_the_relay() -> None:
    """The one signal that does both. RFC 5322 §3.6.2: Reply-To names where answers go when that
    is not the author's own address — which is exactly what a relay sets it to."""
    raw = _mail(**{"Reply-To": '"Sehan Sanjula" <sehan@sanjula.io>'})
    assert reply_to_party(raw, "hello@boardy.ai") == "sehan@sanjula.io"
    assert sender_is_a_relay(raw, sender_email="hello@boardy.ai") is True


def test_a_reply_to_pointing_at_the_sender_asserts_nothing() -> None:
    """Plenty of ordinary mailers set Reply-To to the From address. That is not a relay."""
    raw = _mail(**{"Reply-To": "harshita@peakxv.com"})
    assert reply_to_party(raw, "harshita@peakxv.com") is None
    assert sender_is_a_relay(raw, sender_email="harshita@peakxv.com") is False


def test_the_address_is_normalised_the_way_the_graph_normalises_it() -> None:
    """`norm_email` is THE person-identity function, so the address returned here is the key
    `_person()` would mint a node under — the comparison cannot disagree with the graph."""
    raw = _mail(**{"Reply-To": "  Sehan <SEHAN+intro@Sanjula.IO>  "})
    assert reply_to_party(raw, "hello@boardy.ai") == "sehan@sanjula.io"
    # …and the same normalisation on the other side of the comparison.
    assert reply_to_party(_mail(**{"Reply-To": "HARSHITA@peakxv.com"}),
                          "harshita+deals@peakxv.com") is None


@pytest.mark.parametrize("value", ["", "   ", "not an address", "<>"])
def test_an_unreadable_reply_to_is_not_evidence(value: str) -> None:
    assert reply_to_party(_mail(**{"Reply-To": value}), "hello@boardy.ai") is None


def test_a_payload_with_no_headers_is_not_a_relay() -> None:
    """Absence is never evidence — a calendar event or CRM record carries no mail headers."""
    for raw in (None, {}, {"headers": None}, {"headers": {}}):
        assert reply_to_party(raw, "someone@example.com") is None
        assert sender_is_a_relay(raw, sender_email="someone@example.com") is False


# ── the boundary against the machine-sender table ────────────────────────────────────────────

def test_an_intro_network_is_a_relay_and_not_a_machine_sender() -> None:
    """The whole reason this predicate exists: `is_noise` already handles everything the machine
    table matches, and it matches none of these."""
    for address in ("hello@boardy.ai", "intros@boardy.ai", "connect@network.example"):
        assert is_automated_sender(address) is False
        assert sender_is_a_relay(_mail(**{"Reply-To": "real@person.com"}),
                                 sender_email=address) is True


def test_either_signal_alone_is_enough() -> None:
    """They are independent: old mail has only the display name, new mail may have only Reply-To."""
    assert sender_is_a_relay(None, sender_name="Sehan via Boardy") is True
    assert sender_is_a_relay(_mail(**{"Reply-To": "sehan@x.io"}),
                             sender_email="hello@boardy.ai") is True
    assert sender_is_a_relay(_mail(), sender_name="Harshita Kaul",
                             sender_email="harshita@peakxv.com") is False
