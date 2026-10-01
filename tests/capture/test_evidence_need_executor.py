"""U08 · the executor — and the three refusals that keep it from becoming a backfill.

    pytest tests/capture/test_evidence_need_executor.py -q

⛔ EVERY PATH ENDS IN A CLOSED NEED. `met` or `unavailable`, and `unavailable` always carries a
reason. A need left `open` because nothing matched is a hold that can never clear — the exact state
this whole step exists to end, re-created one layer down. Several tests below exist only to prove
that, including the one where the fetcher explodes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.acquire.evidence_need import (BACKFILL_WINDOW, FETCH_THREAD,
                                                         MIN_FETCH_USD, REEXTRACT, execute,
                                                         plan_fetch)
from genios_engine.contracts.evidence import EvidenceNeed

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)


def _need(**over):
    kwargs = dict(need_id="EN-1", org_id="o", trace_id="t",
                  question="Does the signed contract auto-renew?",
                  why_it_matters="It moves the decision deadline.",
                  subject_ref="thread:abc",
                  acceptable_sources=("signed_contract",),
                  unacceptable_sources=("vendor_quote_email",))
    kwargs.update(over)
    return EvidenceNeed(**kwargs)


def _found(source):
    return lambda need: {"source": source}


_NOTHING = lambda need: None                                        # noqa: E731


# =================================================================================================
# 1 · which fetch a need calls for
# =================================================================================================
@pytest.mark.parametrize(("subject", "kind"), [
    ("thread:abc", FETCH_THREAD),
    ("document:d1", REEXTRACT),
    ("attachment:a1", REEXTRACT),
    ("signal:SIG-101", BACKFILL_WINDOW),
])
def test_the_plan_is_read_off_the_subject(subject, kind):
    """Read off a typed reference, never guessed from the question text — matching on prose would
    make the plan depend on wording that changes whenever somebody improves a sentence."""
    assert plan_fetch(_need(subject_ref=subject)) == kind


def test_a_need_layer_one_cannot_answer_says_so():
    outcome = execute(_need(subject_ref="capability:expertise.accounts"),
                      fetchers={}, eval_time=_NOW)
    assert outcome.state == "unavailable"
    assert "no Layer 1 fetch answers" in outcome.reason


# =================================================================================================
# 2 · ⛔ the three refusals
# =================================================================================================
def test_an_expired_need_is_never_fetched():
    """The answer would arrive after the decision it was for. Buying it anyway spends the tenant's
    money on history."""
    called = []
    outcome = execute(_need(expires_at=_NOW - timedelta(hours=1)),
                      fetchers={FETCH_THREAD: lambda n: called.append(1) or {"source": "x"}},
                      eval_time=_NOW)
    assert outcome.state == "unavailable"
    assert "expired" in outcome.reason
    assert called == [], "an expired need must not reach the fetcher at all"


def test_a_budget_below_the_cheapest_fetch_closes_rather_than_half_fetching():
    """⛔ A partial answer LOOKS like an answer, and the hold clears on it."""
    outcome = execute(_need(max_cost_usd=MIN_FETCH_USD / 2),
                      fetchers={FETCH_THREAD: _found("signed_contract")}, eval_time=_NOW)
    assert outcome.state == "unavailable"
    assert "partial fetch would answer partly and close fully" in outcome.reason


def test_a_substitute_source_never_closes_the_need():
    """⛔ THE REFUSAL THAT MATTERS. Something was found and it is not what was asked for. Closing on
    it would let Layer 2 proceed on evidence that cannot carry the claim."""
    outcome = execute(_need(), fetchers={FETCH_THREAD: _found("vendor_quote_email")},
                      eval_time=_NOW)
    assert outcome.state == "unavailable"
    assert outcome.source == "vendor_quote_email"
    assert "does not accept it" in outcome.reason


# =================================================================================================
# 3 · the happy path
# =================================================================================================
def test_the_right_source_meets_the_need():
    outcome = execute(_need(), fetchers={FETCH_THREAD: _found("signed_contract")}, eval_time=_NOW)
    assert outcome.state == "met"
    assert outcome.source == "signed_contract"
    assert outcome.kind == FETCH_THREAD


def test_an_open_acceptable_list_takes_anything_not_forbidden():
    outcome = execute(_need(acceptable_sources=()),
                      fetchers={FETCH_THREAD: _found("drive")}, eval_time=_NOW)
    assert outcome.state == "met"


# =================================================================================================
# 4 · ⛔ every path closes
# =================================================================================================
def test_finding_nothing_closes_the_need():
    outcome = execute(_need(), fetchers={FETCH_THREAD: _NOTHING}, eval_time=_NOW)
    assert outcome.state == "unavailable"
    assert "found nothing" in outcome.reason


def test_a_missing_connector_closes_the_need():
    outcome = execute(_need(), fetchers={}, eval_time=_NOW)
    assert outcome.state == "unavailable"
    assert "not connected" in outcome.reason


def test_an_exploding_fetcher_still_closes_the_need():
    """⛔ Leaving it open on an exception re-creates the permanently-open need this contract exists
    to prevent, and hides a broken connector behind a hold that simply never clears."""
    def boom(need):
        raise RuntimeError("connector is down")

    outcome = execute(_need(), fetchers={FETCH_THREAD: boom}, eval_time=_NOW)
    assert outcome.state == "unavailable"
    assert "RuntimeError" in outcome.reason


def test_an_already_closed_need_is_not_reworked():
    outcome = execute(_need(state="met"), fetchers={FETCH_THREAD: _found("x")}, eval_time=_NOW)
    assert outcome.state == "met"


@pytest.mark.parametrize("fetchers", [{}, {FETCH_THREAD: _NOTHING},
                                      {FETCH_THREAD: _found("vendor_quote_email")}])
def test_no_outcome_is_ever_left_open(fetchers):
    outcome = execute(_need(), fetchers=fetchers, eval_time=_NOW)
    assert outcome.state in {"met", "unavailable"}
    if outcome.state == "unavailable":
        assert outcome.reason and outcome.reason.strip()
