"""The end of M-3's chain: the queue was built, the question asked, the answer stored, nobody told.

`campaign_candidates` publishes what the exact-sentence rule declined to group.
`same_situation_two_threads` adjudicates each near-miss. This is where a `one_campaign` verdict
becomes a card — the step that was missing, and the reason the whole lane existed.

THREE RULES CARRY THIS FILE.

`test_same_topic_mints_nothing` is the one that protects the tenant. Five introductions answered
personally in one morning share the raise vocabulary and reach this queue every time. They are
five relationships with five cards; grouping them is the wrongful merge the whole lane avoids, and
the enum has a separate word for exactly that case.

`test_it_yields_to_a_group_card_that_already_covers_these_people` keeps the rule
`read_campaign_silence` set next door: one group of people gets one group card.

`test_it_never_claims_an_exact_sentence` is what keeps the card honest. `find_campaigns` mints a
`Campaign` and quotes the sentence every member carried; no two members here carry one, and that
absence is precisely why the deterministic grouping did not fire.
"""
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.context.reworded_outreach import (ANCHOR_REWORDED, MAX_PER_SWEEP, ONE_CAMPAIGN,
                                                     read_reworded_outreach)

NOW = datetime(2026, 8, 11, 8, 0, tzinfo=timezone.utc)
NAMES = {"n_peak": "Vidushi", "n_afore": "Harshita", "n_neon": "Manik", "n_surge": "Shivam"}


def _candidate(verdict=ONE_CAMPAIGN, recipients=("n_peak", "n_afore", "n_neon"),
               cid="cand_1", hours=5, sentences=3):
    return {"candidate_id": cid,
            "verdict": verdict,
            "shared_tokens": ["mrr", "preseed", "traction"],
            "sentences": [f"wording {i}" for i in range(sentences)],
            "recipients": list(recipients),
            "event_ids": [f"e{i}" for i in range(len(recipients))],
            "sends": len(recipients),
            "first_sent": NOW.isoformat(),
            "last_sent": (NOW + timedelta(hours=hours)).isoformat()}


def _facts(finding) -> dict:
    return {name: value for name, value, _kind in finding.facts}


# ── the card ─────────────────────────────────────────────────────────────────────────────────

def test_a_reworded_raise_becomes_one_card() -> None:
    [card] = read_reworded_outreach([_candidate()], NOW, NAMES)
    facts = _facts(card)

    assert card.anchor == ANCHOR_REWORDED
    assert facts["outreach.recipients"] == 3
    assert facts["outreach.distinct_wordings"] == 3
    assert facts["outreach.window_hours"] == 5
    assert facts["outreach.reading"] == ONE_CAMPAIGN
    assert "3 ways to 3 people" in card.display_name


def test_the_shared_words_travel_with_the_card() -> None:
    """A stored similarity score is undebuggable — `correlation_conversation` refuses one by name.
    These are the actual words every member has in common, which is what the model was shown and
    what a reader checks against their own sent folder."""
    facts = _facts(read_reworded_outreach([_candidate()], NOW, NAMES)[0])
    assert facts["outreach.shared_words"] == "mrr, preseed, traction"


def test_the_group_names_who_is_in_it_and_counts_the_rest() -> None:
    """`outreach.recipients` is the true number; the names are a sample. The same split
    `read_outreach_cohorts` keeps between `cohort.contacted` and the names it prints."""
    card = read_reworded_outreach(
        [_candidate(recipients=tuple(NAMES))], NOW, NAMES)[0]
    facts = _facts(card)
    assert facts["outreach.recipients"] == 4
    assert "Vidushi" in facts["outreach.named"]
    assert card.evidence_nodes == tuple(sorted(NAMES))
    assert card.concerns_node in NAMES


# ── what must not become a card ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("verdict", ["same_topic_not_one_message", "unrelated", "unknowable", ""])
def test_same_topic_mints_nothing(verdict: str) -> None:
    """THE RULE THAT PROTECTS THE TENANT, and the commonest verdict this mailbox will produce. An
    introducer makes five introductions; the founder answers each personally the same morning;
    every reply mentions the raise. Those reach this queue every time and they are five
    relationships, not one outreach. Grouping them would tell a founder to work as a campaign
    something they never sent."""
    assert read_reworded_outreach([_candidate(verdict=verdict)], NOW, NAMES) == []


def test_no_verdict_no_card() -> None:
    """With no angle layer the queue is unannotated and the sweep is exactly what it was."""
    candidate = _candidate()
    candidate.pop("verdict")
    assert read_reworded_outreach([candidate], NOW, NAMES) == []


def test_two_people_are_a_coincidence_not_a_group() -> None:
    assert read_reworded_outreach([_candidate(recipients=("n_peak", "n_afore"))], NOW, NAMES) == []


def test_it_yields_to_a_group_card_that_already_covers_these_people() -> None:
    """`read_campaign_silence` sets the rule: "one group of people gets one group card". A founder
    shown "your raise outreach" and "one outreach, reworded" about the same three people has been
    told one thing twice."""
    covered = {"n_peak", "n_afore", "n_neon"}
    assert read_reworded_outreach([_candidate()], NOW, NAMES, covered) == []


def test_it_does_not_yield_on_a_partial_overlap() -> None:
    """Not partially, because a group card about the LEFTOVERS of another group card is a third
    description of the same morning. It yields whole or not at all."""
    covered = {"n_peak"}
    assert len(read_reworded_outreach([_candidate()], NOW, NAMES, covered)) == 1


def test_one_sweep_cannot_become_a_feed() -> None:
    many = [_candidate(cid=f"c{i}") for i in range(MAX_PER_SWEEP + 5)]
    assert len(read_reworded_outreach(many, NOW, NAMES)) == MAX_PER_SWEEP


# ── what the card refuses to claim ───────────────────────────────────────────────────────────

def test_it_never_claims_an_exact_sentence() -> None:
    """`find_campaigns` mints a `Campaign` and quotes the sentence every member carried. No two
    members here carry one — that absence is exactly why the deterministic grouping did not fire —
    so claiming it would be taking the receipt this card does not have."""
    [card] = read_reworded_outreach([_candidate()], NOW, NAMES)
    assert "outreach.exact_sentence" in card.missing
    assert not any(name == "outreach.sentence" for name, _v, _k in card.facts)
    for word in ("campaign", "blast", "send-out"):
        assert word not in card.display_name.lower()


def test_it_says_nothing_about_who_replied() -> None:
    """The candidate is built from what was SENT. A reply rate would be a number from nowhere."""
    [card] = read_reworded_outreach([_candidate()], NOW, NAMES)
    assert "outreach.replied" in card.missing
    assert not any("repl" in name for name, _v, _k in card.facts)


# ── it is routable and dispatched ────────────────────────────────────────────────────────────

def test_the_anchor_routes_and_is_dispatched() -> None:
    from genios_engine.context.domain_spec import domains_declaring, spec_for
    from genios_engine.context.outreach_situations import READINGS

    assert domains_declaring(ANCHOR_REWORDED) == ("admin",)
    assert spec_for("admin").type_for(ANCHOR_REWORDED) == "outreach_reworded"
    assert ANCHOR_REWORDED in {anchor for anchor, _ in READINGS}


def test_it_is_dispatched_before_the_last_resort_reading() -> None:
    """The dispatch order is the precedence: each group reading computes coverage from the ones it
    names, so a reading must run after everything it yields to."""
    from genios_engine.context.outreach_situations import READINGS

    order = [anchor for anchor, _ in READINGS]
    assert order.index("cohort") < order.index(ANCHOR_REWORDED)
    assert order.index("campaign") < order.index(ANCHOR_REWORDED)
