"""U05 · the loop closes — a met need frees a hold, an unavailable one ends the waiting.

    pytest tests/context/test_a_met_need_clears_its_hold.py -q

⛔ THE DISTINCTION UNDER TEST IS THREE-WAY, NOT TWO-WAY. `open`, `met` and `unavailable` are three
different things to do, and the two easy mistakes both collapse a pair of them:

  - treating `unavailable` as `met` → the card claims evidence it never got
  - treating `unavailable` as `open` → the situation waits forever for a document that does not exist
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.context.hold_resolution import (DISPOSITIONS, GIVE_UP, KEEP_WAITING,
                                                   NO_EVIDENCE_QUESTION, RETRY, resolve_hold)
from pydantic import ValidationError

from genios_engine.contracts.evidence import EvidenceNeed

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def _need(**over):
    kwargs = dict(need_id="EN-1", org_id="o", trace_id="t",
                  question="Is there source material we have not fetched?",
                  why_it_matters="The situation cannot publish without it.",
                  subject_ref="signal:SIG-1")
    kwargs.update(over)
    return EvidenceNeed(**kwargs)


_MET = _need(need_id="EN-met", state="met")
_GONE = _need(need_id="EN-gone", state="unavailable",
              unavailable_reason="the document does not exist")
_OPEN = _need(need_id="EN-open")


# =================================================================================================
# 1 · the four dispositions
# =================================================================================================
def test_a_still_open_need_changes_nothing():
    d = resolve_hold([_OPEN], eval_time=_NOW)
    assert d.disposition == KEEP_WAITING
    assert d.still_open == 1
    assert d.should_retry_admission is False
    assert d.should_stop_waiting is False


def test_a_met_need_earns_another_go_at_admission():
    d = resolve_hold([_MET], eval_time=_NOW)
    assert d.disposition == RETRY
    assert d.should_retry_admission is True


def test_every_need_unavailable_stops_the_waiting_and_says_why():
    """⛔ The reason must reach the card. A situation that gave up and a situation still waiting are
    different states, and a card that cannot tell them apart nags forever or goes quiet."""
    d = resolve_hold([_GONE], eval_time=_NOW)
    assert d.disposition == GIVE_UP
    assert d.should_stop_waiting is True
    assert "the document does not exist" in d.explain()


def test_a_hold_that_asked_nothing_is_not_called_waiting():
    """Four of seven hold reasons raise no need. That hold is waiting on a RULING, and calling it
    KEEP_WAITING would imply a pending fetch that does not exist."""
    d = resolve_hold([], eval_time=_NOW)
    assert d.disposition == NO_EVIDENCE_QUESTION
    assert d.should_retry_admission is False
    assert d.should_stop_waiting is False


def test_the_disposition_is_always_one_of_the_four():
    for needs in ([], [_OPEN], [_MET], [_GONE], [_MET, _GONE], [_MET, _OPEN]):
        assert resolve_hold(needs, eval_time=_NOW).disposition in DISPOSITIONS


# =================================================================================================
# 2 · ⛔ unavailable is never met, and never open
# =================================================================================================
def test_unavailable_never_produces_a_retry_on_its_own():
    """⛔ THE MISTAKE THAT WOULD MATTER MOST. A retry here would send an unchanged situation back
    through admission forever, and if it ever admitted it would do so on evidence that never came."""
    d = resolve_hold([_GONE, _GONE], eval_time=_NOW)
    assert d.disposition == GIVE_UP
    assert d.met_sources == ()


def test_unavailable_is_not_counted_as_still_open():
    """⛔ The other way of collapsing the pair: the situation would wait forever on a question that
    has already been answered with "no"."""
    d = resolve_hold([_GONE], eval_time=_NOW)
    assert d.still_open == 0
    assert d.disposition != KEEP_WAITING


def test_the_three_states_give_three_different_explanations():
    lines = {resolve_hold(n, eval_time=_NOW).explain()
             for n in ([_OPEN], [_MET], [_GONE], [])}
    assert len(lines) == 4
    assert all(line.strip() for line in lines)


def test_the_contract_will_not_let_an_unavailable_need_exist_without_a_reason():
    """Guarded one layer down, in `EvidenceNeed` itself, which is the right place: a reasonless
    closure should not be constructible at all rather than caught by every reader."""
    with pytest.raises(ValidationError, match="carries its reason"):
        _need(state="unavailable", unavailable_reason=None)


def test_a_reasonless_row_still_says_something_rather_than_nothing():
    """Reachable only through a raw row, not through the contract \u2014 but a blank line on a card is
    indistinguishable from a reason nobody wrote, so the fallback is not left to chance."""
    class _Row:
        state = "unavailable"
        unavailable_reason = None
        expires_at = None

    d = resolve_hold([_Row()], eval_time=_NOW)
    assert d.disposition == GIVE_UP
    assert d.explain().strip() not in {"", "stopped waiting:"}
    assert "no reason recorded" in d.explain()


# =================================================================================================
# 3 · ⛔ a partial arrival is not a complete one
# =================================================================================================
def test_one_met_and_one_still_open_keeps_waiting():
    """⛔ Checked BEFORE the met branch on purpose. The situation has not got everything it asked for,
    and retrying would re-derive the same hold while the outstanding question is in flight."""
    d = resolve_hold([_MET, _OPEN], eval_time=_NOW)
    assert d.disposition == KEEP_WAITING
    assert d.still_open == 1
    assert d.met_sources != (), "what DID arrive must not be forgotten while waiting"


def test_one_met_and_one_unavailable_retries_but_carries_what_is_still_missing():
    """⛔ THE `not_carried` DEFECT. Dropping the unavailable reason would let the retry read as "we
    have everything now" — a value computed at one boundary and silently lost at the next."""
    d = resolve_hold([_MET, _GONE], eval_time=_NOW)
    assert d.disposition == RETRY
    assert d.unavailable_reasons != ()
    explain = d.explain()
    assert "still missing" in explain
    assert "the document does not exist" in explain


def test_a_clean_retry_does_not_invent_a_missing_half():
    d = resolve_hold([_MET], eval_time=_NOW)
    assert d.unavailable_reasons == ()
    assert "still missing" not in d.explain()


# =================================================================================================
# 4 · ⛔ an expired open need is not still waiting
# =================================================================================================
def test_an_expired_open_need_stops_the_waiting_rather_than_extending_it_forever():
    """⛔ THE PERMANENT HOLD. The row still says `open` because the executor has not run. Counting it
    as waiting means the situation waits on a question nobody will answer, forever, and no surface
    says so."""
    stale = _need(expires_at=_NOW - timedelta(hours=1))
    d = resolve_hold([stale], eval_time=_NOW)
    assert d.disposition == GIVE_UP
    assert d.still_open == 0
    assert "expired" in d.explain()


def test_a_need_expiring_later_is_still_a_live_question():
    fresh = _need(expires_at=_NOW + timedelta(hours=1))
    assert resolve_hold([fresh], eval_time=_NOW).disposition == KEEP_WAITING


def test_a_need_expiring_exactly_now_is_expired():
    """The boundary matches the executor's own refusal, which uses `expires_at <= now`. Two different
    answers at the same instant would let a need be fetched by one path and refused by the other."""
    d = resolve_hold([_need(expires_at=_NOW)], eval_time=_NOW)
    assert d.disposition == GIVE_UP


def test_a_met_need_that_has_since_expired_is_still_met():
    """Expiry governs the QUESTION, not the answer. An answer that arrived in time does not stop
    being an answer."""
    d = resolve_hold([_need(state="met", expires_at=_NOW - timedelta(days=1))], eval_time=_NOW)
    assert d.disposition == RETRY


# =================================================================================================
# 5 · eval_time is a parameter, never now()
# =================================================================================================
def test_the_same_needs_replay_to_the_same_disposition():
    """A decision that cannot be replayed cannot be audited."""
    needs = [_need(expires_at=_NOW + timedelta(hours=1)), _MET]
    a = resolve_hold(needs, eval_time=_NOW)
    b = resolve_hold(needs, eval_time=_NOW)
    assert a == b


def test_moving_the_clock_forward_is_what_changes_the_answer():
    needs = [_need(expires_at=_NOW + timedelta(hours=1))]
    assert resolve_hold(needs, eval_time=_NOW).disposition == KEEP_WAITING
    assert resolve_hold(needs, eval_time=_NOW + timedelta(hours=2)).disposition == GIVE_UP


def test_resolve_hold_requires_an_eval_time():
    """⛔ No default. A default would be `now()` at the one seam where replayability matters."""
    with pytest.raises(TypeError):
        resolve_hold([_MET])


def test_the_disposition_is_frozen():
    d = resolve_hold([_MET], eval_time=_NOW)
    with pytest.raises(Exception):
        d.disposition = GIVE_UP


# =================================================================================================
# 6 · ⛔ it decides; it does not write
# =================================================================================================
def test_this_module_touches_no_database_and_no_clock():
    """The compare-and-set belongs to the caller that applies the disposition — `reason/` already has
    a working one. A second copy here would be the duplicate Step 2 was withdrawn for."""
    import inspect

    from genios_engine.context import hold_resolution

    source = inspect.getsource(hold_resolution)
    for forbidden in ("sqlalchemy", "engine", "datetime.now", "utcnow", "text("):
        assert forbidden not in source, f"{forbidden!r} does not belong in a pure decision"
