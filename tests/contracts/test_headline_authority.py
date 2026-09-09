"""The headline must not outrank the card.

    pytest tests/contracts/test_headline_authority.py -q

`card_builder` withdraws a card's authority to instruct when it cannot say what to do, and its own
comment says so: *"it just stops claiming the authority to give an order it cannot phrase."* That
happens in E0. The headline is written in E1, and until this transform existed `deliver/render.py`
contained no reference to `level` anywhere — the two stages never met.

MEASURED on the pilot's fifteen live cards, by resolving each through `contracts/outcomes`:

    level = review        11    "there is no instruction to give, a human must look"
    level = observation    3
    level = prescriptive   1    ← the only card the system is actually recommending

Their headlines: *"Deliver fundraising opportunities to sanchiconnect.tech NOW"*,
*"Renew Growth plan at $599/month now"*, *"Reply to Sehan Sanjula now"*. Fourteen of the fifteen
had two layers implying different outcomes.

The push gate already honours the level — `deliver/pipeline.py` checks `is_actionable` before it
interrupts, so an abstaining card does not push. **The sentence did not**, and the sentence is what
the reader sees first.

A SAFETY TRANSFORM, NOT COPYWRITING. It does not rewrite the sentence: deterministic verb surgery
on "Send Lalitha A R the product context materials" produces fragments. It reframes — the trailing
urgency word goes and a prefix states what the card is. Stiff and honest beats fluent and false.
"""

from __future__ import annotations

import pytest

from genios_engine.contracts.abstention import Level
from genios_engine.deliver.render import HEADLINE_CAP, state_not_command

pytestmark = pytest.mark.unit

#: Verbatim from the tenant, with the level the card actually carries.
PILOT = [
    ("Deliver fundraising opportunities to sanchiconnect.tech NOW", "review"),
    ("Deliver mentorship guidance from expert mentors now", "review"),
    ("Renew Growth plan at $599/month now", "review"),
    ("Deliver $2,000 monthly savings to myzyner.com", "review"),
    ("Reply to Sehan Sanjula now", "observation"),
    ("Send Lalitha A R the product context materials", "observation"),
    ("Book time with Sal Stabler on her calendar link", "observation"),
]


# =============================================================================================
# The defect.
# =============================================================================================
@pytest.mark.parametrize("headline,level", PILOT, ids=[h[:28] for h, _ in PILOT])
def test_a_card_that_declined_to_advise_stops_shouting(headline, level):
    """None of these may keep reading as an order — the card's own level says it has none."""
    out = state_not_command(headline, level)

    assert out != headline
    assert not out.lower().rstrip(".!").endswith(" now")


def test_a_review_card_says_a_decision_is_needed():
    out = state_not_command("Renew Growth plan at $599/month now", "review")

    assert out == "Needs a decision — Renew Growth plan at $599/month"


def test_an_observation_says_it_is_unresolved():
    out = state_not_command("Reply to Sehan Sanjula now", "observation")

    assert out == "Unresolved — Reply to Sehan Sanjula"


# =============================================================================================
# And the half that must not change.
# =============================================================================================
def test_the_one_prescriptive_card_is_untouched():
    """The single card on the tenant the system is genuinely recommending. A transform that
    restyled it would be a regression, not a fix."""
    headline = "Confirm your attendance for Evokoa's call"

    assert state_not_command(headline, "prescriptive") == headline


def test_a_predictive_warning_still_instructs():
    """`PREDICTIVE` is actionable: a warning about a trajectory still tells the reader to act."""
    headline = "Renewal lapses in 6 days without a decision"

    assert state_not_command(headline, Level.PREDICTIVE) == headline


def test_an_unknown_level_is_left_alone():
    """Fail-open on purpose. A level nobody has reasoned about must not silently restyle a
    headline; the alternative is a transform firing on values it was never designed for."""
    headline = "Reply to Sehan Sanjula now"

    assert state_not_command(headline, "some_future_level") == headline
    assert state_not_command(headline, None) == headline


def test_an_empty_headline_stays_empty():
    assert state_not_command("", "review") == ""
    assert state_not_command("   ", "review") == ""


# =============================================================================================
# The budget bug this transform shipped with for one run.
# =============================================================================================
def test_the_frame_never_eats_the_headline():
    """THE FIRST CUT DID EXACTLY THIS. Capping the joined string let the cap treat the em dash as
    a clause boundary and cut everything after it, returning the bare words "Needs a decision" for
    the pilot's top card — strictly worse than the imperative it replaced."""
    out = state_not_command("Deliver fundraising opportunities to sanchiconnect.tech NOW", "review")

    assert out.startswith("Needs a decision — ")
    assert len(out) > len("Needs a decision — ")
    assert "fundraising" in out


@pytest.mark.parametrize("headline,level", PILOT, ids=[h[:28] for h, _ in PILOT])
def test_every_reframed_headline_keeps_some_of_its_subject(headline, level):
    body = headline.rsplit(" now", 1)[0].rsplit(" NOW", 1)[0]
    first_word = body.split()[1] if len(body.split()) > 1 else body

    assert first_word.lower() in state_not_command(headline, level).lower()


@pytest.mark.parametrize("headline,level", PILOT, ids=[h[:28] for h, _ in PILOT])
def test_the_cap_is_respected(headline, level):
    assert len(state_not_command(headline, level)) <= HEADLINE_CAP


# =============================================================================================
# Idempotence — a rebuild must not stack frames.
# =============================================================================================
def test_reframing_twice_changes_nothing():
    once = state_not_command("Reply to Sehan Sanjula now", "observation")
    twice = state_not_command(once, "observation")

    assert twice == once


def test_a_frame_from_a_different_level_is_not_stacked_on_top():
    """A card that was `observation` on one build and `review` on the next keeps one frame. The
    level moved; the headline does not accumulate history."""
    once = state_not_command("Reply to Sehan Sanjula now", "observation")
    again = state_not_command(once, "review")

    assert again.count("—") == 1


def test_the_urgency_tail_goes_in_every_spelling():
    for tail in (" now", " NOW", " today", " immediately", ", now.", " ASAP"):
        out = state_not_command(f"Reply to Sehan Sanjula{tail}", "observation")

        assert out == "Unresolved — Reply to Sehan Sanjula", tail
