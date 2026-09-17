"""An email offering three meeting slots was recorded as a three-way disagreement.

    pytest tests/capture/validate/test_one_source_does_not_contradict_itself.py -q

A subject key is `{thread}:{field_family}` (ALG-22), so every date in a thread shares one key by
construction. One message proposing "Tue, Jul 7 · Wed, Jul 8 · Thu, Jul 9" therefore arrived at
ALG-12 as three claims about "the" date of that thread — and another had the message's own
sent-header timestamp competing with the time it proposed.

MEASURED ON THE PILOT 2026-09-16: 77 of 97 stored conflicts had every claim from ONE event. They
held 27 situations at `conflict_open` in Layer 3 — a gate that is right to refuse a situation
built on a contradicted claim, refusing on contradictions that were never there.

AND THEY COULD NEVER CLEAR. Claims from one event share an authority rank and an `asserted_at`,
so `_resolve` has nothing to choose between them: all 77 resolved `unresolved_surface_both`. Not a
slow path to a decision — no path at all. A situation held on one would be held for ever.

THIS IS THE RULE THE MODULE ALREADY DESCRIBED. `Claim.event_id` exists, in its own words, "so a
conflict can be shown to span two events, which is the property the headline fixture exists to
prove", and `detect_conflicts` opens by saying the batch "SPANS EVENTS by design". A group that
does not span them was never what ALG-12 was written to find.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_conflict import (  # noqa: E402
    EMAIL_84K, LATER, NOW, SIGNED_74K, claim, detect, usd)

pytestmark = pytest.mark.unit


def test_three_slots_in_one_email_are_not_a_disagreement() -> None:
    """The case that held 27 situations. One sender, one message, three dates offered."""
    slots = [claim(f"slot_{i}", usd(v, f"${v}"), __import__(
        "genios_engine.contracts.conflict", fromlist=["Authority"]).Authority.EMAIL_PROSE,
        field="date.value", event_id="evt_one_message", quote=q)
        for i, (v, q) in enumerate([(1, "Tue, Jul 7: 2:30 PM"), (2, "Wed, Jul 8: 2:30 PM"),
                                    (3, "Thu, Jul 9: 2:30 PM")])]
    out = detect(*slots)
    assert out.conflicts == ()
    assert out.total_detected == 0


def test_two_sources_disagreeing_is_still_a_conflict() -> None:
    """The headline case, untouched: the signed PDF and the email that misquotes it are two
    events. Narrowing D5 any further would delete the unit's whole purpose."""
    out = detect(SIGNED_74K, EMAIL_84K)
    assert len(out.conflicts) == 1
    assert len(out.conflicts[0].event_ids) == 2


def test_one_dissenting_source_among_many_from_one_event_still_conflicts() -> None:
    """The mixed case, and the reason the rule counts DISTINCT events rather than checking that
    every claim shares one. Three slots from one message plus a calendar record that says
    otherwise is a genuine disagreement, and the slots are the losing side's evidence."""
    from genios_engine.contracts.conflict import Authority

    same = [claim(f"s_{i}", usd(i + 1, f"${i+1}"), Authority.EMAIL_PROSE,
                  field="date.value", event_id="evt_message")
            for i in range(3)]
    other = claim("calendar", usd(99, "$99"), Authority.EMAIL_PROSE,
                  field="date.value", event_id="evt_calendar", at=LATER)
    out = detect(*same, other)
    assert len(out.conflicts) == 1
    assert set(out.conflicts[0].event_ids) == {"evt_message", "evt_calendar"}


def test_claims_that_name_no_source_are_not_two_sources() -> None:
    """A claim carrying no event id names no source, and two that both name none have not been
    shown to come from two — the same reading `is_admissible` takes of an unlocatable receipt."""
    from genios_engine.contracts.conflict import Authority

    a = claim("a", usd(1, "$1"), Authority.EMAIL_PROSE, field="date.value", event_id="")
    b = claim("b", usd(2, "$2"), Authority.EMAIL_PROSE, field="date.value", event_id="   ")
    assert detect(a, b).conflicts == ()


def test_a_single_event_group_is_not_counted_as_detected() -> None:
    """It is not a conflict that was found and dropped — it was never a conflict. Counting it in
    `total_detected` would report a storm the tenant does not have, and D4's per-subject cap is
    spent on real ones."""
    from genios_engine.contracts.conflict import Authority

    pair = [claim(f"p_{i}", usd(i + 1, f"${i+1}"), Authority.EMAIL_PROSE,
                  field="date.value", event_id="evt_same") for i in range(2)]
    out = detect(*pair)
    assert out.total_detected == 0
    assert out.subjects == ()
