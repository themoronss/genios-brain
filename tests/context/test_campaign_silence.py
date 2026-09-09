"""The Cross Conversation READING — and the approved card that could never fire.

    pytest tests/context/test_campaign_silence.py -q

`admin.sit.campaign_going_quiet` is authored, approved, reviewed by a named human and carries an
`accepted_content_hash`. It has never rendered and could not. It gates on `cohort_outreach_gap`,
which `read_outreach_cohorts` mints by grouping on `thread.objective` — and that field has ZERO
facts in the pilot's graph. Measured read-only on 2026-09-09: not superseded, not inactive, never
written. 0 of 141 waiting rows carry it. `relationship.nature`, written by the same extractor, has
exactly one fact across every node in the tenant.

So the reading returns zero findings, and the card bound to it is structurally unfireable — a
capability that reports as healthy in every count and reaches nobody. The same shape as `textguard`
unimported by capture, the `owns` edge never read, and `derived.timeline.condition_review` surfaced
by nothing.

`read_campaign_silence` groups on the SENTENCE instead, from `correlation_conversation`, which was
itself dead code: nothing in `genios_engine/` imported it. Live, it finds the two sends of 11
August — 7 of 7 and 6 of 6 still silent at 29 days, each with a verbatim line and real event ids.

IT YIELDS RATHER THAN COMPETES, and the tests below pin that in both directions.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.context.correlation_conversation import Campaign
from genios_engine.context.outreach_situations import (
    ANCHOR_CAMPAIGN,
    READINGS,
    read_campaign_silence,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 9, tzinfo=timezone.utc)
SENT = datetime(2026, 8, 11, 7, 56, tzinfo=timezone.utc)
PITCH = "As we can see the need of the product, we can expect the numbers to hit nearly ~$2-3k MRR."
DECK = "I am sharing a few details here as well for your reference with the deck attached."


def campaign(recipients, *, sentence: str = PITCH, at: datetime = SENT,
             cid: str = "campaign_a") -> Campaign:
    return Campaign(campaign_id=cid, sentence=sentence, first_sent=at, last_sent=at,
                    recipients=tuple(recipients),
                    event_ids=tuple(f"evt_{r}" for r in recipients))


_DEFAULT = object()


def rows(*, waiting: dict[str, float], campaigns=_DEFAULT, extra: dict | None = None) -> dict:
    held: dict = {node: {"thread.days_waiting": days, "_name": node}
                  for node, days in waiting.items()}
    for node, patch in (extra or {}).items():
        held.setdefault(node, {}).update(patch)
    held["_campaigns"] = ((campaign(sorted(waiting)),) if campaigns is _DEFAULT else campaigns)
    held["_organizations"] = ()
    return held


def read(**kw):
    return read_campaign_silence(rows(**kw), NOW, {})


def facts_of(finding) -> dict:
    return {name: value for name, value, _kind in finding.facts}


THREE = {"p_a": 29, "p_b": 29, "p_c": 30}


# =============================================================================================
# The card the approved one could not be.
# =============================================================================================
def test_one_send_with_several_silent_recipients_is_one_finding():
    [finding] = read(waiting=THREE)

    assert finding.anchor == ANCHOR_CAMPAIGN
    assert facts_of(finding)["campaign.awaiting"] == 3
    assert facts_of(finding)["campaign.contacted"] == 3


def test_the_reading_is_dispatched_like_every_other_one():
    """`correlation_conversation` shipped on this branch and nothing in `genios_engine/` imported
    it. A reading that is not in `READINGS` is the same defect one layer down."""
    assert (ANCHOR_CAMPAIGN, read_campaign_silence) in READINGS


def test_the_line_they_all_received_is_on_the_card():
    """The one thing nothing else in the system can show the reader: they wrote it, and they will
    not remember which version went to whom."""
    [finding] = read(waiting=THREE)

    assert facts_of(finding)["campaign.quote"] == PITCH


def test_a_wrapped_mail_body_does_not_break_the_sentence():
    """A quote arrives with the line breaks the mail client put in it, and a newline inside a
    headline slot breaks the sentence a reader sees. Folded for display; the words are untouched.
    Caught on the live run, where both quotes came back with a break mid-clause."""
    wrapped = "As we can see the need\nof the product, we can expect\tthe numbers to hit ~$2-3k."

    [finding] = read(waiting=THREE, campaigns=(campaign(sorted(THREE), sentence=wrapped),))

    quote = facts_of(finding)["campaign.quote"]
    assert "\n" not in quote and "\t" not in quote
    assert quote.startswith("As we can see the need of the product")


def test_the_send_date_is_reported():
    [finding] = read(waiting=THREE)

    assert facts_of(finding)["campaign.sent_on"] == "2026-08-11"


def test_the_messages_are_kept_so_the_card_can_cite_them():
    [finding] = read(waiting=THREE)

    assert len(finding.inputs["events"]) == 3


def test_the_longest_waiter_is_the_subject():
    [finding] = read(waiting={"p_a": 29, "p_b": 29, "p_c": 44})

    assert finding.concerns_node == "p_c"
    assert facts_of(finding)["campaign.longest_wait_days"] == 44


# =============================================================================================
# What it refuses to claim.
# =============================================================================================
def test_what_the_outreach_was_for_is_never_guessed():
    """A sentence is evidence of what was written, not of what it was meant to achieve — an
    investor we are RAISING FROM and one we merely OWE A REPORT need opposite follow-ups and can
    receive identical words. `cohort.objective` is a closed enum a quote is not a member of, and
    writing one there would put free text into a field rules gate on."""
    [finding] = read(waiting=THREE)

    assert "campaign.objective" not in facts_of(finding)
    assert "campaign.objective" in finding.missing


def test_one_silent_recipient_is_not_a_campaign_going_quiet():
    """The per-counterparty card already covers it exactly."""
    assert read(waiting={"p_a": 29}) == []


def test_a_send_this_morning_is_not_a_silence():
    """Same two-day floor every other state reading uses, so the numbers on this card and the
    cards underneath it cannot disagree."""
    assert read(waiting={"p_a": 1, "p_b": 1, "p_c": 1}) == []


def test_a_thread_covered_by_its_party_is_not_a_second_silent_recipient():
    found = read(waiting={"p_a": 29, "t_a": 29}, extra={"t_a": {"_covered_by_party": "A"}})

    assert found == []


def test_no_campaigns_is_not_an_error():
    assert read(waiting=THREE, campaigns=()) == []


# =============================================================================================
# It yields — in both directions.
# =============================================================================================
def test_it_stands_down_for_an_objective_keyed_cohort():
    """The cohort reading groups by STATED PURPOSE, which is the better key when it exists: two
    different messages about one raise are one campaign to a founder, and only a purpose can see
    that. One group of people gets one group card, and that one wins."""
    held = rows(waiting=THREE)
    for node in THREE:
        held[node]["thread.objective"] = "fundraising"

    assert read_campaign_silence(held, NOW, {}) == []


def test_it_fires_when_the_cohort_reading_cannot():
    """The live case. Same three people, no objective on any of them — which is every waiting row
    on the pilot — so the cohort mints nothing and this must."""
    held = rows(waiting=THREE)

    assert len(read_campaign_silence(held, NOW, {})) == 1


def test_a_send_whose_silent_people_are_all_on_a_bigger_card_says_nothing_new():
    """Subset, so it yields. The larger send is emitted first and already names everyone."""
    big = campaign(["p_a", "p_b", "p_c"], cid="big")
    small = campaign(["p_a", "p_b"], sentence=DECK, cid="small")

    found = read(waiting=THREE, campaigns=(small, big))

    assert len(found) == 1
    assert facts_of(found[0])["campaign.awaiting"] == 3


def test_two_overlapping_sends_are_still_two_sends():
    """SUBSET, NOT OVERLAP. On 11 August the founder sent two different lines whose recipient sets
    intersect without either containing the other — seven people got the deck, six got the MRR
    number, and four got both. That is two real sends. An overlap threshold here would be a policy
    invented in Layer 2, which is the choice this module refuses everywhere else."""
    deck = campaign(["p_a", "p_b", "p_c"], cid="deck")
    mrr = campaign(["p_b", "p_c", "p_d"], sentence=PITCH, cid="mrr")

    found = read(waiting={"p_a": 29, "p_b": 29, "p_c": 29, "p_d": 29}, campaigns=(deck, mrr))

    assert len(found) == 2


def test_the_bigger_send_is_the_one_that_survives_a_subset():
    """Order-independent: the rule resolves on size, not on the order a caller stamped them in."""
    big = campaign(["p_a", "p_b", "p_c"], cid="big")
    small = campaign(["p_a", "p_b"], sentence=DECK, cid="small")

    for order in ((big, small), (small, big)):
        [finding] = read(waiting=THREE, campaigns=order)
        assert finding.correlation_id == "campaign:big"


# =============================================================================================
# Identity.
# =============================================================================================
def test_the_correlation_id_is_the_campaign():
    """Stable across sweeps, so six drains a day produce one row rather than six."""
    [finding] = read(waiting=THREE)

    assert finding.correlation_id == "campaign:campaign_a"


def test_the_same_line_a_quarter_later_is_a_different_card():
    later = campaign(["p_a", "p_b", "p_c"], at=SENT + timedelta(days=95), cid="campaign_b")

    [first] = read(waiting=THREE)
    [second] = read(waiting=THREE, campaigns=(later,))

    assert first.correlation_id != second.correlation_id
    assert facts_of(second)["campaign.sent_on"] != facts_of(first)["campaign.sent_on"]
