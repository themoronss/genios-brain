"""DE-03 — three shipped situations named slots the engine did not write, and the card crashed.

    pytest tests/deliver/test_an_authored_slot_is_one_the_engine_can_fill.py -q

`render._interpolate` ended in `tpl.format(**slots)`, which raises KeyError on any `{name}` the
slot vocabulary does not carry. `campaign-awaiting-reply.yaml`, `organization-gone-quiet.yaml`
and `condition-awaiting-review.yaml` named six such slots between them — `{organization}`,
`{quote}`, `{sent_on}`, `{longest_wait_days}`, `{age_days}` — so their whole card died at render
even though the decision behind it was correct.

Three locks, in the order they should catch it:

  1. THE WRITER. Every one of those facts was already on the row; only the slot was missing.
  2. THE VALIDATOR. `_tools/validate.py` refuses an authored fallback naming a slot the engine
     cannot fill, at the moment an author can still see it.
  3. THE ENGINE. An unwritten slot degrades to a dropped clause, because an authoring mistake
     must not take down the delivery of an otherwise correct decision.
"""

from __future__ import annotations

import pathlib
import re
from datetime import datetime, timezone

import pytest
import yaml

from genios_engine.deliver.render import _interpolate
from genios_engine.deliver.slots import SENTINELS, compute_slots

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 10, tzinfo=timezone.utc)
CORPUS = pathlib.Path(__file__).resolve().parents[2] / "Domain Expertise"


def slots(facts=None):
    """A graph fact is `{path: {"value": v}}` — `_fval` reads the inner `value`, so a raw value
    here would silently read as absent and every assertion below would pass against a sentinel."""
    wrapped = {path: {"value": value} for path, value in (facts or {}).items()}
    return compute_slots("any", "Peak XV", wrapped, NOW)


# =============================================================================================
# 1 · The writer.
# =============================================================================================
@pytest.mark.parametrize("slot", ["organization", "quote", "sent_on",
                                  "longest_wait_days", "age_days"])
def test_every_group_slot_is_written(slot):
    assert slot in slots()


def test_a_firm_card_can_name_the_firm():
    got = slots({"organization.name": "Peak XV Partners",
                 "organization.longest_wait_days": 34})

    assert got["organization"] == "Peak XV Partners"
    assert got["longest_wait_days"] == 34


def test_a_campaign_card_can_quote_the_line_it_sent():
    """The quote is the one thing this card can show that nothing else in the system can."""
    got = slots({"campaign.quote": "Quick one — are you free Thursday?",
                 "campaign.sent_on": "11 August", "campaign.longest_wait_days": 30})

    assert got["quote"] == "Quick one — are you free Thursday?"
    assert got["sent_on"] == "11 August"
    assert got["longest_wait_days"] == 30


def test_a_campaign_wait_does_not_answer_a_firms_card():
    """Read from the anchor the reading actually writes it on and nowhere else. Falling back
    across them would let a send's wait render on a firm's card — the cross-subject bleed the
    group cards exist to avoid."""
    got = slots({"campaign.longest_wait_days": 30})

    assert got["longest_wait_days"] == 30
    assert got["organization"] == SENTINELS["organization"]


def test_an_unwritten_group_slot_falls_to_a_sentinel_no_value_can_equal():
    """A firm genuinely called "this firm" does not exist, so a sentinel that could be mistaken
    for content would let an unnamed group card ship looking complete."""
    got = slots()

    assert got["organization"] == "an unnamed counterparty"
    assert got["quote"] == "the message we sent"


# =============================================================================================
# 2 · The validator.
# =============================================================================================
def test_every_authored_fallback_slot_is_one_the_engine_writes():
    """The check that would have caught all three files before they shipped."""
    declared = set(yaml.safe_load(
        (CORPUS / "_schema/vocabulary.yaml").read_text())["substrate"]["fallback_slots"])

    unfillable: dict[str, set[str]] = {}
    for path in sorted(CORPUS.rglob("situations/*.yaml")):
        fallback = ((yaml.safe_load(path.read_text()) or {}).get("render") or {}
                    ).get("fallback") or {}
        for part in ("headline", "situation"):
            for slot in re.findall(r"\{(\w+)\}", str(fallback.get(part) or "")):
                if slot not in declared:
                    unfillable.setdefault(path.name, set()).add(slot)

    assert unfillable == {}, unfillable


def test_the_declared_list_matches_the_engine():
    """A transcription that drifts is worse than no transcription: the validator would start
    admitting slots that crash, or refusing slots that work."""
    declared = set(yaml.safe_load(
        (CORPUS / "_schema/vocabulary.yaml").read_text())["substrate"]["fallback_slots"])

    assert declared == set(SENTINELS)


# =============================================================================================
# 3 · The engine, as the last lock.
# =============================================================================================
def test_an_unknown_slot_no_longer_crashes_the_card():
    """THE ORIGINAL FAILURE, in one assertion."""
    rendered = _interpolate("{organization} — {entity} has gone quiet",
                            {"entity": "Peak XV"})

    assert "Peak XV" in rendered


def test_an_unknown_slots_clause_is_dropped_rather_than_stubbed():
    """The same move the sentinel path makes: saying nothing is honest, printing a placeholder
    word where a fact belongs is not."""
    rendered = _interpolate("{entity} — sent {nonexistent_slot}", {"entity": "Peak XV"})

    assert rendered == "Peak XV"


def test_an_unknown_slot_with_no_clause_of_its_own_reads_as_missing():
    """It cannot be cut without mangling the sentence, so it degrades to a phrase that reads as
    an absence to a person and to the model — an empty string would read as a rendering bug."""
    rendered = _interpolate("Sent {nonexistent_slot} to {entity}", {"entity": "Peak XV"})

    assert "not recorded" in rendered
    assert "Peak XV" in rendered


def test_a_grounded_slot_still_renders_normally():
    """The guard may not become "drop everything"."""
    rendered = _interpolate("{organization} — {awaiting} of {contacted} have gone quiet",
                            {"organization": "Peak XV", "awaiting": 2, "contacted": 2})

    assert rendered == "Peak XV — 2 of 2 have gone quiet"
