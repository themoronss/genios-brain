"""Seven stored campaign recipients must not render as 'several'."""
from genios_engine.deliver.slots import compute_slots, SENTINELS
from tests.context.test_support_derived_provenance import NOW


def test_campaign_and_cohort_cards_take_counts_only_from_their_own_subject():
    facts = {"campaign.contacted": {"value": 7}, "campaign.awaiting": {"value": 7},
             "cohort.contacted": {"value": 13}, "cohort.awaiting": {"value": 6}}
    campaign = compute_slots("campaign_awaiting_reply", "send", facts, NOW)
    assert (campaign["contacted"], campaign["awaiting"]) == (7, 7)
    cohort = compute_slots("cohort_outreach_gap", "cohort", facts, NOW)
    assert (cohort["contacted"], cohort["awaiting"]) == (13, 6)


def test_an_unknown_campaign_count_does_not_borrow_a_cohorts_count():
    slots = compute_slots("campaign_awaiting_reply", "send", {"cohort.contacted": {"value": 13}}, NOW)
    assert slots["contacted"] == SENTINELS["contacted"]
    assert slots["awaiting"] == SENTINELS["awaiting"]
