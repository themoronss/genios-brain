"""A message says whether it went to a list. A headcount never does.

`context/pipeline.py` discarded every recipient of any email with more than ten addresses on it —
not ten of them, all of them — so a fundraise update to twelve investors produced no recipient
nodes, no presence receipts, no `corresponded_with` edges and nothing for the outbound-evidence
mirror to write against. This predicate replaces that count, and it may only answer True on
something the message ASSERTS about itself.
"""
import pytest

from genios_engine.capture.gate.rules import LIST_HEADERS, addressed_to_a_list


def _mail(**headers):
    return {"headers": dict(headers)}


# ── the count is not evidence ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("recipients", [1, 11, 40, 400])
def test_the_number_of_recipients_is_never_evidence(recipients: int) -> None:
    """The whole defect this replaces. A fundraise update to twelve investors and a newsletter to
    twelve thousand differ in kind, not in size, and this predicate is not shown the size."""
    assert addressed_to_a_list(_mail(Subject="Q3 update")) is False


def test_a_payload_with_no_headers_keeps_its_recipients() -> None:
    """A calendar event or CRM record carries no mail headers. Absence is not evidence — the
    anti-over-gating law: refuse on positive contrary evidence, never on a gap."""
    assert addressed_to_a_list(None) is False
    assert addressed_to_a_list({}) is False
    assert addressed_to_a_list({"headers": None}) is False
    assert addressed_to_a_list({"headers": {}}) is False


# ── what the message says about itself ───────────────────────────────────────────────────────

@pytest.mark.parametrize("name", LIST_HEADERS)
def test_every_list_header_is_recognised(name: str) -> None:
    """Parametrised over the exported tuple, not a list retyped here: a reader answering this
    question with three of the four names is the failure `composio.py:71` records."""
    assert addressed_to_a_list(_mail(**{name: "<https://example.com/u>"})) is True


@pytest.mark.parametrize("value", ["bulk", "list", "junk", "Bulk", "  LIST  "])
def test_a_bulk_precedence_is_a_list(value: str) -> None:
    assert addressed_to_a_list(_mail(Precedence=value)) is True


def test_an_ordinary_precedence_is_not(value: str = "normal") -> None:
    assert addressed_to_a_list(_mail(Precedence=value)) is False


def test_a_machine_submission_is_a_list() -> None:
    """`Auto-Submitted: no` is the RFC's way of saying a human sent it."""
    assert addressed_to_a_list(_mail(**{"Auto-Submitted": "auto-generated"})) is True
    assert addressed_to_a_list(_mail(**{"Auto-Submitted": "no"})) is False


def test_a_machine_sender_is_a_list_even_with_clean_headers() -> None:
    """A mailshot platform need not announce itself in a header."""
    assert addressed_to_a_list(_mail(), sender_email="noreply@vendor.com") is True
    assert addressed_to_a_list(_mail(), sender_email="harshita@peakxv.com") is False
    assert addressed_to_a_list(_mail(), sender_email=None) is False


# ── the property that keeps L1 and L2 from disagreeing ───────────────────────────────────────

def test_header_names_are_matched_case_insensitively() -> None:
    """RFC 5322 makes header names case-insensitive and provider payloads are case-PRESERVING.
    A connector that lower-cased them once turned three of four bulk rules off silently."""
    assert addressed_to_a_list(_mail(**{"list-unsubscribe": "<mailto:u@x.com>"})) is True
    assert addressed_to_a_list(_mail(**{"PRECEDENCE": "bulk"})) is True


def test_an_empty_header_value_is_not_a_list() -> None:
    """A header present but blank asserts nothing."""
    assert addressed_to_a_list(_mail(**{"List-Id": "   "})) is False
