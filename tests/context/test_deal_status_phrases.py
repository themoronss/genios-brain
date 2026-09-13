"""A stated deal outcome written as a phrase must not collapse to `open`.

Found by the P2 gate: a LinkedIn decline landed as deal.stage "vendor selection decision made;
proceeding with another vendor" and the exact-word table read it as `open`.
"""
import pytest

from genios_engine.context.pipeline import _normalise_deal_status


@pytest.mark.parametrize("stage", [
    "vendor selection decision made; proceeding with another vendor",
    "decided to go with another vendor",
    "We will not proceed this quarter",
    "not moving forward with the proposal",
    "Declined",
    "Closed Lost",
    "no longer interested",
])
def test_stated_declines_are_lost(stage):
    assert _normalise_deal_status(stage) == ("lost", stage)


@pytest.mark.parametrize("stage", ["contract signed", "PO issued", "closed won", "Signed"])
def test_stated_wins_are_won(stage):
    assert _normalise_deal_status(stage)[0] == "won"


@pytest.mark.parametrize("stage", ["negotiation", "final review", "on hold", "delayed",
                                   "proceeding to legal review", "proposal sent"])
def test_ordinary_stages_stay_open_and_keep_their_words(stage):
    assert _normalise_deal_status(stage) == ("open", stage)


def test_empty_is_nothing():
    assert _normalise_deal_status("") == (None, None)
    assert _normalise_deal_status(None) == (None, None)
