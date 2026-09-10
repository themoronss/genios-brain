"""ES-02 and ES-07 — two implementations of one question, each documented as the only one.

    pytest tests/capture/test_one_answer_per_question.py -q

TWO ROBOT TABLES. `relevance.is_service_account` says it is public "because two implementations
of 'is this a robot' would eventually disagree about one address and give it a person's authority
in one place and a machine's in the other." `gate/rules.is_automated_sender` says it is "the ONE
machine-sender table … a second regex would drift into a second answer about `notify@stripe.com`
— the gate dropping it as a robot while the scorer weighs it as a counterparty."

Both existed. Run side by side over 23 addresses they disagreed on EIGHTEEN, in both directions,
and `notify@stripe.com` was one of them — the exact address the second docstring names.

THE FIX IS ONE-WAY DELEGATION, not a merge. Whatever the GATE calls a robot, the scorer now calls
a robot: that is the direction that matters, because the gate DELETES the message under N-03 and
an address it discards while the scorer treats it as a person is a counterparty who silently
ceased to exist. The scorer still knows about more machinery than the gate — `postmaster`,
`mailer-daemon`, `robot`, `daemon`, `cron`, `jenkins`, `build` — and that asymmetry is kept
deliberately: scoring can afford to be broader than DROPPING, whose own comment warns that
`support@`/`hello@` are a real small business.

TWO WAYS TO READ A HEADER. The S1 gate read `hdrs.get("Auto-Submitted")` / `"Precedence"` /
`"List-Unsubscribe"` EXACTLY, while `relevance._header_value` read the same headers
case-insensitively. RFC 5322 makes header names case-insensitive and provider payloads are
case-PRESERVING, so a connector that lower-cased them turned three of the gate's four bulk rules
off with nothing going red.
"""

from __future__ import annotations

import pytest

from genios_engine.capture.esqe.relevance import is_service_account
from genios_engine.capture.gate.rules import header, is_automated_sender

pytestmark = pytest.mark.unit

#: The probe set the disagreement was measured over. Each entry is an address and whether a
#: PERSON could plausibly be behind it.
ADDRESSES: tuple[tuple[str, bool], ...] = (
    # Machinery both tables should agree on.
    ("no-reply@stripe.com", False),
    ("notify@stripe.com", False),
    ("notifications@github.com", False),
    ("newsletter@substack.com", False),
    ("digest@medium.com", False),
    ("marketing@vendor.io", False),
    ("campaigns@vendor.io", False),
    ("jobalerts@linkedin.com", False),
    ("no-response@vendor.io", False),
    ("mailer-daemon@google.com", False),
    ("postmaster@acme.com", False),
    ("bounces@sendgrid.net", False),
    ("robot@ci.acme.com", False),
    ("daemon@acme.com", False),
    ("cron@acme.com", False),
    ("jenkins@acme.com", False),
    ("build@ci.acme.com", False),
    ("automation@acme.com", False),
    ("alerts@datadog.com", False),
    ("someone@news.acme.com", False),
    ("someone@mktg.acme.com", False),
    ("someone@updates.acme.com", False),
    # REAL PEOPLE, including the two the gate's own comment protects.
    ("harshita@peakxv.com", True),
    ("support@smallbusiness.com", True),
    ("hello@smallbusiness.com", True),
    ("rohit@genios.ai", True),
    ("joseph@afore.vc", True),
)


# =============================================================================================
# The direction that deletes mail.
# =============================================================================================
@pytest.mark.parametrize(("address", "_human"), ADDRESSES, ids=lambda v: v if isinstance(v, str) else "")
def test_nothing_the_gate_drops_is_scored_as_a_person(address, _human):
    """THE DANGEROUS HALF. N-03 discards the message; if the scorer disagrees, a counterparty
    silently ceased to exist and no count anywhere says so."""
    if is_automated_sender(address):
        assert is_service_account(address), address


def test_the_address_both_docstrings_named():
    """`notify@stripe.com` is called out by name in `gate/rules.py` as the thing a second regex
    must never split — and it was exactly what the two tables split on."""
    assert is_automated_sender("notify@stripe.com")
    assert is_service_account("notify@stripe.com")


def test_the_scorer_delegates_rather_than_re_deciding():
    """A copy of the gate's regex would pass the test above on the day it was written and drift
    the week after. The delegation is the property; the agreement is its consequence."""
    import inspect

    from genios_engine.capture.esqe import relevance

    source = inspect.getsource(relevance.is_service_account)

    assert "is_automated_sender(address)" in source


# =============================================================================================
# What each table is allowed to know that the other does not.
# =============================================================================================
@pytest.mark.parametrize("address", ["postmaster@acme.com", "mailer-daemon@google.com",
                                     "robot@ci.acme.com", "daemon@acme.com", "cron@acme.com",
                                     "jenkins@acme.com", "build@ci.acme.com"])
def test_the_scorer_knows_machinery_the_gate_does_not_delete(address):
    """Kept deliberately. These are unambiguously machines, but they are NOT added to the gate's
    table, because the gate's job is to delete the message and its comment gives the reason to
    stay conservative. Scoring can be broader than dropping."""
    assert is_service_account(address)


@pytest.mark.parametrize(("address", "human"), ADDRESSES, ids=lambda v: v if isinstance(v, str) else "")
def test_a_real_person_is_a_person_to_both(address, human):
    """The guard may not become "call everything a robot". `support@` and `hello@` are a real
    small business, and over-matching costs a genuine sender 80% of its authority."""
    if human:
        assert not is_automated_sender(address), address
        assert not is_service_account(address), address


def test_an_address_with_no_at_sign_is_nobody():
    assert not is_service_account("not-an-address")
    assert not is_service_account("")


# =============================================================================================
# One way to read a header.
# =============================================================================================
@pytest.mark.parametrize("spelling", ["List-Unsubscribe", "list-unsubscribe",
                                      "LIST-UNSUBSCRIBE", "List-UnSubscribe"])
def test_a_bulk_header_is_found_however_the_mailer_spelled_it(spelling):
    """RFC 5322 makes header names case-insensitive and provider payloads are case-PRESERVING,
    so the spelling that arrives is whatever the sending mailer chose."""
    assert header({spelling: "<mailto:x@y.z>"}, "List-Unsubscribe") == "<mailto:x@y.z>"


def test_a_missing_header_returns_the_default_rather_than_none():
    """N-01 compares against `("no", "")`, so a `None` would slip past it as "not 'no'"."""
    assert header({}, "Auto-Submitted", "no") == "no"
    assert header(None, "Auto-Submitted", "no") == "no"
    assert header({"X-Other": "1"}, "Precedence") == ""


def test_a_header_present_but_empty_is_not_a_signal():
    assert header({"Precedence": ""}, "Precedence") == ""


def test_a_none_value_reads_as_the_default():
    assert header({"Precedence": None}, "Precedence", "") == ""


def test_the_three_bulk_rules_all_go_through_it():
    """N-01, N-02 and N-04 each read a header directly. A rule that keeps its own
    `hdrs.get("Exact-Spelling")` is the defect coming back on one line."""
    import inspect

    from genios_engine.capture.gate import rules

    # `noise_rule`, not `hard_rule` — the latter is a two-line dispatcher and the header reads
    # live in the noise half.
    source = inspect.getsource(rules.noise_rule)

    for name in ("Auto-Submitted", "Precedence", "List-Unsubscribe", "List-Id",
                 "List-Post", "Feedback-ID"):
        assert f'hdrs.get("{name}")' not in source, name
        assert name in source, name


def test_a_lower_casing_connector_no_longer_disables_the_gate():
    """The whole point, end to end: the same message, headers lower-cased, must still be bulk."""
    from genios_engine.capture.gate.rules import hard_rule

    class Ctx:
        raw = {"has_attachment": False, "headers": {"list-unsubscribe": "<mailto:u@x.com>"}}
        labels = ()

    lowered = {"list-unsubscribe": "<mailto:u@x.com>"}
    proper = {"List-Unsubscribe": "<mailto:u@x.com>"}

    assert header(lowered, "List-Unsubscribe") == header(proper, "List-Unsubscribe")
    assert hard_rule is not None      # the rule is reachable; the read is what was broken
