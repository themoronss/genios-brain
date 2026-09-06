"""L1.5.1 (ALG-08) ON THE REQUEST PATH — the step that stamps `verified`, and the retry that hid
a total loss behind the word "duplicate".

TWO DEFECTS, ONE SYMPTOM EACH, BOTH INVISIBLE.

**1. `validate/spans.apply_verdicts` had no production caller.** `semantic/evidence_binder.py`
builds every receipt with `verified=False` and says why in its own docstring — *"that stamp
belongs to L1.5.1 alone: the binder runs at the extractor seam, so a span leaving here wearing a
checkmark would be the extractor grading its own homework."* L1.5.1's whole-extraction entry
point was then reachable from nothing but its own test file, so no span in the system was ever
graded. Nothing raised. Three things were simply wrong:

* doc 06's group gate requires *">= 1 verified evidence span"* on 95% of published signals; the
  measured number on the production path was **0 of 321**;
* V-5 downgrades a signal's confidence for unverified evidence, so the rule that exists to mark
  the rare unsubstantiated claim was marking every claim;
* G10's *"unverified span rate < 5%"* was 100%, and `spans.unverified_rate_bp` — the function
  that measures it — had no production caller either.

**2. `_capture_bounded` reported a failed capture as a duplicate.** `capture_event` writes its
`source_events` row after the gate and BEFORE extraction, so an exception downstream of that
write leaves the ledger row behind; the retry's dedup check then finds it, returns `duplicate`,
and the sweep counted a clean re-sync. A 132-message page scanned 132, wrote 132 rows, produced
zero extractions and raised nothing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture import pipeline as P
from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.contracts.evidence import EvidenceSpan

NOW = datetime(2026, 3, 4, 9, 0, tzinfo=timezone.utc)
ORG = "org_span_grading"
BODY = ("Hello, the Northwind Ltd annual contract renews at $84,000, and the date on it is "
        "16 March 2026. Please read the thread before replying.")


class _Result:
    def __init__(self, parsed):
        self.parsed, self.raw = parsed, "{}"
        self.input_tokens, self.output_tokens = 900, 180
        self.model, self.cached, self.ok, self.error = "fake-model-1", False, True, None


class _LLM:
    model = "fake-model-1"

    def __init__(self, payload):
        self._payload, self.calls = payload, 0

    def call(self, prompt: str, *, max_tokens: int = 4096):
        self.calls += 1
        return _Result(self._payload)


def _cite(quote: str) -> list[dict]:
    start = BODY.index(quote)
    return [{"quote": quote, "start_offset": start, "end_offset": start + len(quote)}]


def _payload(*, grounded: bool = True) -> dict:
    return {
        "intent": "inform", "stance": "neutral", "topics": ["contract_renewal"],
        "entity_mentions": [{
            "surface_form": "Northwind Ltd", "entity_type": "organization",
            "evidence": _cite("the Northwind Ltd annual contract renews at $84,000"),
            "confidence_bp": 9000}],
        "amounts": [{"minor_units": 8_400_000, "currency": "USD",
                     "as_written": "$84,000" if grounded else "$8,400,000"}],
        "dates_mentioned": [{"as_written": "16 March 2026",
                             "evidence": _cite("16 March 2026")}],
    }


def _raw(object_id: str = "m_span_grading") -> RawObject:
    return RawObject(source="gmail", object_type="email_message", source_object_id=object_id,
                     occurred_at=NOW, actor_email="cfo@northwind.test",
                     recipients=("founder@genios.test",),
                     raw={"subject": "Northwind renewal", "body": BODY})


def _capture(llm, *, object_id: str = "m_span_grading", repo=None):
    return P.capture_event(
        _raw(object_id), org_id=ORG, connection_id="con_span", mailbox_owner="founder@genios.test",
        repo=repo or InMemorySourceEventRepository(),
        semantic=P.SemanticLane(llm=llm, eval_time=NOW))


# ── 1 · the grading step ─────────────────────────────────────────────────────────────────────

def test_the_lane_hands_back_spans_that_carry_the_checkmark():
    """**THE WIRING ASSERTION.** `capture/pipeline.py::run_semantic_lane` -> `_grade_spans` ->
    `validate/spans.apply_verdicts`, driven from `capture_event`. Nothing here calls
    `apply_verdicts`; if the call is removed from the lane this goes red."""
    result = _capture(_LLM(_payload()))
    assert result.extraction is not None, "the lane produced no extraction to grade"
    spans = list(result.extraction.evidence_from_claims())
    assert spans, "the extraction carries no receipts at all"
    assert all(span.verified for span in spans), (
        "every receipt this event published is unverified. L1.5.1 did not run: the binder ships "
        "verified=False by design and `apply_verdicts` is what stamps it.")


def test_the_offsets_the_grader_returns_resolve_against_the_prepared_text():
    """A checkmark is worth nothing unless `clean_text[start:end] == quote` holds. The extractor's
    own offsets are measured against the BODY and the prepared text is subject + body, so every
    span here is relocated — and the grader's corrected offsets are what gets stored."""
    result = _capture(_LLM(_payload()))
    prepared = result.prepared
    assert prepared is not None
    for span in result.extraction.evidence_from_claims():
        assert prepared.clean_text[span.start_offset:span.end_offset] == span.quote, (
            f"a span survived grading with offsets that point somewhere else: {span!r}")


def test_the_grader_removes_an_amount_the_source_does_not_contain():
    """ALG-08's policy, on the production path: a fabricated `Money` is DROPPED, not downgraded.
    A wrong amount is acted on and the human reading the card has no way to know it was invented.
    """
    grounded = _capture(_LLM(_payload()))
    assert grounded.extraction.amounts, "the grounded amount was dropped"

    invented = _capture(_LLM(_payload(grounded=False)), object_id="m_span_grading_2")
    assert not invented.extraction.amounts, (
        "an amount whose literal appears nowhere in the message survived grading")


def test_the_unverified_rate_is_recorded_on_the_trace_of_the_event_it_measured():
    """L1.5.1-U2's rate had no production caller either. It is the number that makes a silently
    degrading extractor visible — a prompt edit that quietly stops citing raises nothing, fails
    no test, and shows up only as this rate moving on a date."""
    result = _capture(_LLM(_payload()))
    semantic = [r for r in result.trace.records if r.stage == P.SEMANTIC_STAGE]
    assert semantic, "the semantic stage left no trace record"
    detail = semantic[-1].detail
    assert detail.get("spans_total"), f"no span tally on the trace: {detail}"
    assert detail.get("unverified_rate_bp") == 0, (
        f"every receipt resolved, so the rate must be 0: {detail}")


def test_a_grading_failure_costs_the_checkmark_and_never_the_sweep(monkeypatch):
    """Downstream of capture on the same terms as every other late stage: losing a checkmark
    costs one signal some confidence, raising costs the tenant their mail."""
    def _boom(*a, **k):
        raise RuntimeError("grader exploded")

    monkeypatch.setattr(P, "apply_verdicts", _boom)
    result = _capture(_LLM(_payload()))
    assert result.outcome == "emitted", "a grading failure took the whole capture down"
    assert result.extraction is not None, "the ungraded extraction did not travel"


def test_the_cache_keeps_the_ungraded_original():
    """`apply_verdicts` asks for it in as many words: *"the input is left alone, because the
    unverified original is what a replay and an audit need to see."* The lane grades on the way
    OUT, so a cache HIT is graded too — a replayed event's evidence must not differ from a
    freshly extracted one's."""
    from genios_engine.capture.semantic.cache import InMemoryExtractionCache

    cache = InMemoryExtractionCache()
    llm = _LLM(_payload())
    first = P.capture_event(
        _raw("m_cache_1"), org_id=ORG, connection_id="con_span",
        mailbox_owner="founder@genios.test", repo=InMemorySourceEventRepository(),
        semantic=P.SemanticLane(llm=llm, eval_time=NOW, cache=cache))
    second = P.capture_event(
        _raw("m_cache_2"), org_id=ORG, connection_id="con_span",
        mailbox_owner="founder@genios.test", repo=InMemorySourceEventRepository(),
        semantic=P.SemanticLane(llm=llm, eval_time=NOW, cache=cache))

    assert llm.calls == 1, "the second event did not hit the cache, so nothing was proven"
    assert all(s.verified for s in second.extraction.evidence_from_claims()), (
        "a cache HIT came back ungraded — a replayed event's evidence differs from a freshly "
        "extracted one's, and only one of them is verified")
    assert [(s.quote, s.start_offset) for s in first.extraction.evidence_from_claims()] \
        == [(s.quote, s.start_offset) for s in second.extraction.evidence_from_claims()]


# ── 2 · the retry that reported a failure as a duplicate ─────────────────────────────────────

def test_a_capture_that_fails_and_then_dedups_is_reported_as_the_failure():
    """The first attempt raises AFTER the ledger row is written; the second finds its own row and
    says `duplicate`. Only the FIRST attempt can legitimately report one, so the caller has to
    receive the error and quarantine the object rather than count a clean re-sync."""
    from genios_engine.capture.acquire import sync_runner as SR

    attempts: list[int] = []

    class _Res:
        outcome = "duplicate"

    def _capture_event(raw, **kw):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("the extractor exploded after the ledger row was written")
        return _Res()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(SR, "capture_event", _capture_event)
        result, err = SR._capture_bounded(_raw(), retries=2, org_id=ORG,
                                          connection_id="con_span",
                                          repo=InMemorySourceEventRepository())
    assert result is None, "a failed capture was reported as a successful duplicate"
    assert err is not None and "exploded" in str(err), (
        "the caller was handed no error, so nothing is quarantined and nothing is logged")


def test_a_genuine_duplicate_on_the_first_attempt_is_still_a_duplicate():
    """The other half. A re-sync over mail we already have must stay cheap and quiet — this fix
    must not turn every second sweep into a page of quarantines."""
    from genios_engine.capture.acquire import sync_runner as SR

    repo = InMemorySourceEventRepository()
    llm = _LLM(_payload())
    first = _capture(llm, repo=repo)
    assert first.outcome == "emitted"

    result, err = SR._capture_bounded(
        _raw(), retries=2, org_id=ORG, connection_id="con_span", repo=repo,
        semantic=P.SemanticLane(llm=llm, eval_time=NOW), mailbox_owner="founder@genios.test")
    assert err is None
    assert result is not None and result.outcome == "duplicate"


def test_a_capture_that_keeps_failing_still_returns_the_error():
    from genios_engine.capture.acquire import sync_runner as SR

    def _always_raises(raw, **kw):
        raise RuntimeError("poison")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(SR, "capture_event", _always_raises)
        result, err = SR._capture_bounded(_raw(), retries=2, org_id=ORG,
                                          connection_id="con_span",
                                          repo=InMemorySourceEventRepository())
    assert result is None and "poison" in str(err)


def test_a_capture_that_succeeds_on_the_second_attempt_still_succeeds():
    """A transient failure that the retry genuinely recovers from must not be turned into an
    error by the guard above: the discriminator is the `duplicate` outcome, not the retry."""
    from genios_engine.capture.acquire import sync_runner as SR

    attempts: list[int] = []

    class _Res:
        outcome = "emitted"

    def _flaky(raw, **kw):
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("transient")
        return _Res()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(SR, "capture_event", _flaky)
        result, err = SR._capture_bounded(_raw(), retries=2, org_id=ORG,
                                          connection_id="con_span",
                                          repo=InMemorySourceEventRepository())
    assert err is None and result is not None and result.outcome == "emitted"
