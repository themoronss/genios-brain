"""`03` F149 · a promise is due when its window CLOSES, not the moment it opens.

    pytest tests/context/test_a_promise_is_due_when_its_window_closes.py -q

`yc2_w27_align` M34.C2.L-logic.V0.U17. `context/qes_adapter` handed L2 a commitment's `due.earliest`
as its due date, so a window became a deadline at its first instant: golden case F48 as first written,
*"Will connect with Tarun this week"* on Thursday 16 Jul, was due at 16 Jul 07:10 — the moment it was
written — though its own window ran to Sunday 19 Jul; a *"next week"* promise was overdue from that
Monday. A bounded promise is now due at its window's last instant (`latest`); an exact date is the same
instant either way. What a RELATIVE *"soon"* is — the contract says never a deadline — is `06`'s to
decide, and it stays as it is until then.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.context.qes_adapter import adapt_qes_extraction
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import Commitment, ExtractionResult
from genios_engine.contracts.units import DateCertainty, ResolvedDate

QUOTE = "Will connect with Tarun this week"
SPAN = EvidenceSpan(source_ref="prepared_content:evt_1", quote=QUOTE, start_offset=0,
                    end_offset=len(QUOTE), verified=True)
WRITTEN = datetime(2026, 7, 16, 7, 10, tzinfo=timezone.utc)
WEEK_ENDS = datetime(2026, 7, 19, 18, 29, 59, tzinfo=timezone.utc)      # Sunday, 23:59:59 IST


def _due_text(certainty: DateCertainty, earliest, latest) -> str | None:
    due = ResolvedDate(as_written="this week", earliest=earliest, latest=latest, certainty=certainty,
                       resolved_against=WRITTEN, evidence=[SPAN])
    result = ExtractionResult(
        intent="commit", stance="positive",
        commitments=[Commitment(actor="Arjun Rao", action="connect with Tarun", due=due,
                                is_conditional=False, evidence=[SPAN], confidence_bp=9000)],
        all_evidence=[SPAN], model_snapshot="m", prompt_version="p", schema_version="3",
        extraction_profile="email", input_tokens=0, output_tokens=0)
    return adapt_qes_extraction(result, confidence_bp=8000).commitments[0]["due_text"]


def test_a_promise_for_this_week_is_due_when_the_week_ends():
    assert _due_text(DateCertainty.RANGE, WRITTEN, WEEK_ENDS) == WEEK_ENDS.isoformat()


def test_a_promise_for_a_day_is_due_on_that_day():
    assert _due_text(DateCertainty.EXACT, WEEK_ENDS, WEEK_ENDS) == WEEK_ENDS.isoformat()


def test_a_soon_stays_as_it_is_until_06_decides():
    """RELATIVE is a guessed window; whether it is a deadline at all is a decision, not this unit."""
    assert _due_text(DateCertainty.RELATIVE, WRITTEN, WEEK_ENDS) == WRITTEN.isoformat()


@pytest.mark.parametrize("certainty", [DateCertainty.UNRESOLVED])
def test_a_date_nobody_could_resolve_is_no_due_date(certainty):
    assert _due_text(certainty, None, None) is None
