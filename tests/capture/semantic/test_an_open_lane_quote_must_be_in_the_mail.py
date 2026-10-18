"""Layer 1 · a relationship or scheduling quote the mail does not contain is cleared, never stored.

    pytest tests/capture/semantic/test_an_open_lane_quote_must_be_in_the_mail.py -q

THE DEFECT (GeniOS-008 L1 W11 / C3). `relationships` and `scheduling_proposals` carry no evidence
span — their `evidence_text` is the only receipt they have, and L3 files it as the fact's evidence
(`context/pipeline.py`, `relationship.nature`). Nothing checked that the quote was in the mail, so a
sentence the model wrote rather than read could be stored as something the counterparty said.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit

_MAIL = "Hi Rohit,\nWe are a pre-seed fund and would love to\n  meet next Tuesday at 3pm.\nBest, Khushi"


def _lane(entries, content=_MAIL):
    from genios_engine.capture.semantic.extractor import _open_lane_entries, _Tally

    return _open_lane_entries(entries, _Tally(), content)


def test_a_quote_that_is_in_the_mail_is_kept_whatever_its_spacing_or_case():
    kept = _lane([{"party": "Khushi", "nature": "investor",
                   "evidence_text": "We are a PRE-SEED fund and would love to meet"}])
    assert kept[0]["evidence_text"] == "We are a PRE-SEED fund and would love to meet"


def test_a_quote_the_mail_does_not_contain_is_cleared_and_the_entry_stays():
    kept = _lane([{"proposer": "Khushi", "text": "Tuesday 3pm",
                   "evidence_text": "Let's lock Tuesday 3pm, I've sent the term sheet"}])
    assert len(kept) == 1, "the judgement stays; only the invented receipt goes"
    assert kept[0]["evidence_text"] is None
    assert kept[0]["text"] == "Tuesday 3pm"


def test_surrounding_quote_marks_do_not_make_a_real_quote_fail():
    kept = _lane([{"party": "Khushi", "nature": "investor",
                   "evidence_text": "“meet next Tuesday at 3pm.”"}])
    assert kept[0]["evidence_text"] is not None


def test_without_content_nothing_is_judged():
    """A caller that has no content (none today) keeps the old behaviour rather than clearing all."""
    kept = _lane([{"party": "x", "nature": "investor", "evidence_text": "anything"}], content=None)
    assert kept[0]["evidence_text"] == "anything"
