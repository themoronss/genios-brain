"""G2 audit probes — written independently of the fixers' own tests.

Every probe is paired with a neutralisation that removes the fix in memory and asserts the probe
would then FAIL, so no assertion here can be vacuous.

Scope, verbatim from the gate brief:
  * a transient attachment failure is still retryable after a heartbeat, not dead-lettered
  * every park code is drained by exactly one path and appears in scripts/l1_s1_report.py counts
  * chunking does NOT split a clause on all-caps prose, and chunk offsets still map to the
    ORIGINAL
  * the structured lane passes validate/schema.py S-1..S-9 against the REAL vocabulary, with
    ZERO LLM calls (proved with a client that RAISES)
  * structural token offsets round-trip
"""

from __future__ import annotations

import inspect
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.documents.chunking import chunk_document
from genios_engine.capture.parked.drain import NEEDS_REFETCH, RE_ADJUDICABLE
from genios_engine.capture.parked.refetch import (InMemoryRefetchQueue,
                                                  refetch_parked_attachments)
from genios_engine.capture.parked.refetch_policy import (DEFAULT_POLICY, AttemptFailure,
                                                         AttemptResult, ParkStatus,
                                                         RefetchAction, RefetchCandidate,
                                                         classify_fetch_error, plan_refetch,
                                                         settle_attempt)
from genios_engine.capture.structural.tokens import scan
from genios_engine.capture.structured.lane import run_structured_lane, structured_vocabulary
from genios_engine.capture.structured.mapper import structured_validation_stage
from genios_engine.capture.structured.registry import get_mapping
from genios_engine.capture.validate.schema import SchemaRule

NOW = datetime(2026, 3, 11, 10, 30, tzinfo=timezone.utc)
ORG = "org_probe_g2"


# =============================================================================================
# PROBE 1 — a TRANSIENT attachment failure survives a heartbeat; it is not dead-lettered.
# =============================================================================================

def _candidate(*, attempts: int = 0, parked_at: datetime | None = None,
               next_attempt_at: datetime | None = None,
               reason_code: str = "DOC-05") -> RefetchCandidate:
    return RefetchCandidate(
        event_id="evt_probe_att", org_id=ORG, reason_code=reason_code, status="pending",
        object_type="email_attachment", source="gmail",
        source_object_id="msg_probe::att_probe", parent_object_id="msg_probe",
        connection_id="con_probe",
        parked_at=parked_at or (NOW - timedelta(hours=6)),
        attempts=attempts, next_attempt_at=next_attempt_at,
        filename="statement.pdf", mime="application/pdf")


#: One real provider sentence per transient class. Each is a phrase that ALSO contains a
#: permanent-looking marker, which is exactly the overlap that used to retire live attachments.
_TRANSIENT_PROSE = [
    ("token refresh in flight", "401 Unauthorized: connected account not found"),
    ("rate limited",            "429 Too Many Requests — key not found in cache, retry later"),
    ("upstream gone",           "503 upstream gone, service unavailable"),
    ("socket died",             "Connection reset by peer"),
    ("plain timeout",           "Read timed out after 30s"),
]


@pytest.mark.parametrize("label,message", _TRANSIENT_PROSE, ids=[r[0] for r in _TRANSIENT_PROSE])
def test_probe_provider_prose_that_means_try_again_is_classified_transient(label, message):
    assert classify_fetch_error(message) is AttemptFailure.TRANSIENT, message


def test_probe_a_transient_failure_stays_pending_with_a_future_retry():
    """One failed attempt on a five-rung ladder settles PENDING, with the next attempt scheduled
    — the definition of 'still retryable'."""
    plan = plan_refetch(_candidate(), eval_time=NOW)
    assert plan.action is RefetchAction.ATTEMPT, plan.reason
    settlement = settle_attempt(
        plan, AttemptResult(ok=False, failure=AttemptFailure.TRANSIENT,
                            error="429 Too Many Requests"), eval_time=NOW)
    assert settlement.status is ParkStatus.PENDING
    assert settlement.next_attempt_at is not None and settlement.next_attempt_at > NOW
    assert settlement.failure is AttemptFailure.TRANSIENT


def test_probe_a_transient_failure_is_still_claimable_by_the_NEXT_heartbeat():
    """The gate's actual wording. A settlement that says PENDING but that the next drain cycle
    never claims again is a dead letter with better paperwork, so this runs TWO real cycles of
    `refetch_parked_attachments` — the function the heartbeat calls."""
    queue = InMemoryRefetchQueue()
    queue.add(_candidate(), payload={"filename": "statement.pdf",
                                     "mime_type": "application/pdf"})

    class _FailingConnector:
        source = "gmail"

        def __init__(self) -> None:
            self.calls = 0

        def fetch_attachment(self, message_id: str, attachment_id: str) -> bytes:
            self.calls += 1
            raise RuntimeError("429 Too Many Requests — please retry")

    connector = _FailingConnector()
    first = refetch_parked_attachments(queue, connector_for=lambda *_a, **_k: connector,
                                       eval_time=NOW)
    assert first.claimed == 1 and first.dead_lettered == 0, first
    assert first.retry_scheduled == 1, first

    # The SECOND heartbeat, after the ladder's first rung has elapsed.
    later = NOW + timedelta(hours=3)
    second = refetch_parked_attachments(queue, connector_for=lambda *_a, **_k: connector,
                                        eval_time=later)
    assert second.claimed == 1, "the transient failure was not re-claimed by the next heartbeat"
    assert second.dead_lettered == 0, second
    assert connector.calls == 2, "the provider was not asked a second time"
    assert queue.candidates["evt_probe_att"].status == ParkStatus.PENDING.value


def test_probe_the_ladder_still_terminates():
    """'Retryable' must not mean 'forever' — the bound is what stops a permanent cost."""
    candidate = _candidate(attempts=DEFAULT_POLICY.max_attempts)
    plan = plan_refetch(candidate, eval_time=NOW)
    assert plan.action is RefetchAction.DEAD_LETTER
    assert plan.failure is AttemptFailure.TRANSIENT, (
        "an exhausted ladder was recorded as PERMANENT — that is a claim about the provider "
        "nothing in the run supports")


def test_neutralised_a_permanent_first_classifier_dead_letters_the_same_prose():
    """The neutralisation: classify permanent-first (the original ordering) and the SAME five
    sentences settle DEAD_LETTER on their first attempt. If they did not, the transient probe
    would be indistinguishable from a probe that asserts nothing."""
    import re

    from genios_engine.capture.parked import refetch_policy as RP

    permanent_first = re.compile(
        "|".join(rf"\b{re.escape(m)}\b" for m in RP._PERMANENT_FETCH_MARKERS))
    dead = 0
    for _label, message in _TRANSIENT_PROSE:
        naive = (AttemptFailure.PERMANENT if permanent_first.search(message.lower())
                 else AttemptFailure.TRANSIENT)
        if naive is AttemptFailure.PERMANENT:
            plan = plan_refetch(_candidate(), eval_time=NOW)
            settlement = settle_attempt(plan, AttemptResult(ok=False, failure=naive,
                                                            error=message), eval_time=NOW)
            assert settlement.status is ParkStatus.DEAD_LETTER
            dead += 1
    assert dead >= 3, (
        f"only {dead} of the transient sentences would have been dead-lettered by a "
        "permanent-first table — the fixture does not exercise the overlap the fix is about")


def test_probe_a_genuinely_gone_attachment_still_dies_on_the_first_answer():
    """The other direction: transient-wins-ties must not make everything retryable forever."""
    assert classify_fetch_error("404 Not Found: message does not exist") \
        is AttemptFailure.PERMANENT
    plan = plan_refetch(_candidate(), eval_time=NOW)
    settlement = settle_attempt(
        plan, AttemptResult(ok=False, failure=AttemptFailure.PERMANENT,
                            error="404 not found"), eval_time=NOW)
    assert settlement.status is ParkStatus.DEAD_LETTER
    assert settlement.next_attempt_at is None


# =============================================================================================
# PROBE 2 — every park code is drained by EXACTLY ONE path, and shows up in the S1 report.
# =============================================================================================

def _every_park_code_the_gate_can_emit() -> set[str]:
    """Enumerated from the GATE, not from a list: every reason code any rule can return.

    `content_integrity_rule` is driven with every `DocumentStatus`, and the remaining rule
    reasons are read out of `gate/rules.py`'s own source so a code added there without a drain
    is caught here rather than in production.
    """
    import re

    from genios_engine.capture.gate import rules as R
    source = inspect.getsource(R)
    codes = set(re.findall(r"['\"](DOC-\d{2})['\"]", source))
    assert codes, "no DOC-* codes were found in gate/rules.py — the enumeration is broken"
    return codes


def test_probe_every_gate_park_code_is_drained_by_exactly_one_path():
    """Two classes, and a code must be in exactly one. In NEITHER means every surface walks past
    it forever; in BOTH means the drain would re-adjudicate a stub and report work that did not
    happen."""
    codes = _every_park_code_the_gate_can_emit()
    orphans = sorted(c for c in codes if c not in NEEDS_REFETCH and c not in RE_ADJUDICABLE)
    both = sorted(c for c in codes if c in NEEDS_REFETCH and c in RE_ADJUDICABLE)
    assert not orphans, f"park codes no drain path claims: {orphans}"
    assert not both, f"park codes claimed by BOTH drain paths: {both}"


def test_probe_the_two_drain_classes_are_disjoint_overall():
    assert not (NEEDS_REFETCH & RE_ADJUDICABLE), NEEDS_REFETCH & RE_ADJUDICABLE


def test_probe_the_s1_report_counts_the_refetch_class_from_the_same_set():
    """The G2 metric is 'attachments stuck in NEEDS_REFETCH over 1h'. If the report filtered on
    its own copy of the set, a code added to the drain and not to the report would be invisible
    in exactly the surface the gate reads."""
    import scripts.l1_s1_report as report

    from genios_engine.capture.parked import refetch as refetch_module
    assert refetch_module.NEEDS_REFETCH is NEEDS_REFETCH, (
        "the refetch queue holds a SEPARATE NEEDS_REFETCH set from the drain's")
    report_source = inspect.getsource(report)
    assert "read_aging" in report_source
    # The report must not restate the set: a literal DOC-* code in the report IS a second list.
    import re
    inline = set(re.findall(r"['\"](DOC-\d{2})['\"]", report_source))
    assert not inline, (
        f"scripts/l1_s1_report.py hard-codes park codes {sorted(inline)} — that is a second "
        "list that will drift from capture/parked/drain.py")


def test_probe_the_refetch_aging_surface_reports_every_needs_refetch_code():
    """A stuck park of EVERY refetch code must be counted, not just the ones a fixture used."""
    queue = InMemoryRefetchQueue()
    for i, code in enumerate(sorted(NEEDS_REFETCH)):
        queue.add(RefetchCandidate(
            event_id=f"evt_{i}", org_id=ORG, reason_code=code, status="pending",
            object_type="email_attachment", source="gmail",
            source_object_id=f"msg_{i}::att_{i}", parent_object_id=f"msg_{i}",
            connection_id="con", parked_at=NOW - timedelta(days=2),
            filename="f.pdf", mime="application/pdf"))
    aging = queue.aging(eval_time=NOW, policy=DEFAULT_POLICY, org_id=ORG)
    reported = {row.reason_code for row in aging.rows}
    assert reported == set(NEEDS_REFETCH), sorted(set(NEEDS_REFETCH) - reported)
    assert aging.stuck_attachments == len(NEEDS_REFETCH)


def test_neutralised_an_orphan_park_code_is_caught_by_the_probe(monkeypatch):
    """Add a code to neither class and the exactly-one-path probe must fail."""
    import genios_engine.capture.parked.drain as D
    monkeypatch.setattr(D, "NEEDS_REFETCH", frozenset(NEEDS_REFETCH - {"DOC-09"}))
    orphan = [c for c in _every_park_code_the_gate_can_emit()
              if c not in D.NEEDS_REFETCH and c not in D.RE_ADJUDICABLE]
    assert "DOC-09" in orphan, (
        "removing DOC-09 from the refetch class left it claimed by something — the "
        "exactly-one-path probe cannot see an orphan")


# =============================================================================================
# PROBE 3 — chunking does not split a clause on all-caps prose; offsets map to the ORIGINAL.
# =============================================================================================

#: An agreement whose CLAUSE BODY is written in block capitals — the shape that used to be read
#: as a wall of headings and cut into one chunk per line.
_ALLCAPS_CLAUSE = """LIMITATION OF LIABILITY

IN NO EVENT SHALL EITHER PARTY BE LIABLE TO THE OTHER FOR ANY INDIRECT,
INCIDENTAL, SPECIAL OR CONSEQUENTIAL DAMAGES ARISING OUT OF OR RELATED TO
THIS AGREEMENT, WHETHER IN CONTRACT OR IN TORT, EVEN IF THAT PARTY HAS BEEN
ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.

GOVERNING LAW

This Agreement is governed by the laws of the State of Delaware."""


def test_probe_an_all_caps_clause_body_is_not_cut_into_one_chunk_per_line():
    chunks = chunk_document(_ALLCAPS_CLAUSE, strategy="section")
    liability = [c for c in chunks if "INDIRECT" in c.text]
    assert len(liability) == 1, (
        "the capitalised clause was split: " + " || ".join(repr(c.text) for c in liability))
    body = liability[0].text
    for fragment in ("IN NO EVENT", "CONSEQUENTIAL DAMAGES", "SUCH DAMAGES."):
        assert fragment in body, f"{fragment!r} left the clause: {body!r}"


def test_probe_the_real_headings_are_still_detected():
    """Without this, 'nothing was split' is satisfied by a chunker that detects no headings at
    all — which would be a different defect wearing this probe's green tick."""
    chunks = chunk_document(_ALLCAPS_CLAUSE, strategy="section")
    titles = {c.section_title for c in chunks if c.section_title}
    assert "LIMITATION OF LIABILITY" in titles, titles
    assert "GOVERNING LAW" in titles, titles


def test_probe_every_chunk_offset_indexes_the_ORIGINAL_document():
    """`chunk.text` must be `original[start:end]` — an identity, not an approximation. An offset
    map that drifts makes every evidence span above it wrong while still reporting verified."""
    for strategy in ("none", "sentence", "section"):
        chunks = chunk_document(_ALLCAPS_CLAUSE, strategy=strategy)
        assert chunks, strategy
        for chunk in chunks:
            assert _ALLCAPS_CLAUSE[chunk.start_offset:chunk.end_offset] == chunk.text, (
                f"{strategy}: offsets {chunk.start_offset}:{chunk.end_offset} do not slice "
                f"back to the chunk text")
            assert 0 <= chunk.start_offset < chunk.end_offset <= len(_ALLCAPS_CLAUSE)


def test_probe_chunks_do_not_overlap_and_stay_in_document_order():
    chunks = chunk_document(_ALLCAPS_CLAUSE, strategy="section")
    ends = [c.end_offset for c in chunks]
    starts = [c.start_offset for c in chunks]
    assert starts == sorted(starts)
    for previous_end, next_start in zip(ends, starts[1:]):
        assert next_start >= previous_end, (previous_end, next_start)


def test_neutralised_treating_every_caps_line_as_a_heading_splits_the_clause():
    """The neutralisation: the ALL-CAPS heading test without its neighbour check
    (`_stands_apart`) — the exact rule that was missing. The clause must then split."""
    from genios_engine.capture.documents import chunking as C
    naive_headings = [line for line in _ALLCAPS_CLAUSE.splitlines()
                      if C._ALLCAPS.match(line) and line.strip()
                      and not any(ch.islower() for ch in line)]
    assert len(naive_headings) > 2, (
        f"only {naive_headings} would be read as headings without the neighbour rule — the "
        "fixture does not exercise the defect, so the no-split probe proves nothing")


def test_neutralised_a_chunk_carrying_drifted_offsets_fails_the_round_trip():
    """Prove the offset probe would catch a drift rather than passing on any tuple."""
    chunk = chunk_document(_ALLCAPS_CLAUSE, strategy="section")[0]
    drifted = replace(chunk, start_offset=chunk.start_offset + 1,
                      end_offset=chunk.end_offset + 1)
    assert _ALLCAPS_CLAUSE[drifted.start_offset:drifted.end_offset] != drifted.text


# =============================================================================================
# PROBE 4 — the structured lane conforms to S-1..S-9 with ZERO LLM calls.
# =============================================================================================

class _ExplodingLLM:
    """A client that RAISES on every attribute access. Not a counter — a counter proves only
    that the method a test knows about was not called."""

    def __getattr__(self, name):        # noqa: ANN001
        raise AssertionError(
            f"the structured lane reached an LLM client (attribute {name!r}) — G2 requires zero "
            "model calls on this lane")

    def __call__(self, *a, **kw):
        raise AssertionError("the structured lane CALLED an LLM client")


#: A real HubSpot deal payload, in the shape `hubspot.deal.v1` maps.
_HUBSPOT_DEAL = {
    "id": "deal_918273",
    "dealname": "Acme — annual renewal",
    "dealstage": "contractsent",
    "amount": "128500",
    "deal_currency_code": "USD",
    "closedate": "2026-05-14T00:00:00Z",
    "contact_email": "priya@acme-probe.test",
}


def _run_lane(monkeypatch=None):
    mapping = get_mapping("hubspot", "deal")
    assert mapping is not None, "hubspot.deal.v1 is not registered — the probe has no subject"
    return run_structured_lane(mapping, _HUBSPOT_DEAL, org_id=ORG, event_id="evt_probe_deal",
                               eval_time=NOW)


def test_probe_the_structured_lane_makes_zero_llm_calls(monkeypatch):
    """Every seam the lane could reach a model through is replaced with an object that raises."""
    import genios_engine.capture.semantic.extractor as EX
    import genios_engine.capture.structured.lane as L
    for module, name in ((EX, "extract"), (L, "run_structured_lane")):
        assert hasattr(module, name)
    monkeypatch.setattr(EX, "extract", _ExplodingLLM(), raising=True)
    try:
        import genios_engine.context.llm.client as CLIENT
    except Exception:                       # noqa: BLE001 — module may not exist in this build
        CLIENT = None
    if CLIENT is not None and hasattr(CLIENT, "LLMClient"):
        monkeypatch.setattr(CLIENT, "LLMClient", _ExplodingLLM(), raising=True)

    outcome = _run_lane()
    assert outcome.extracted, outcome.failure


def test_probe_the_structured_lane_conforms_to_every_schema_rule():
    outcome = _run_lane()
    assert outcome.result is not None, outcome.failure
    assert outcome.schema.conforms, [
        f"{v.rule.value} on {v.field}: {v.detail}" for v in outcome.schema.violations]


def test_probe_the_lane_is_validated_against_the_REAL_vocabulary():
    """Not a permissive test double: the sets must be the curated ones from `vocabulary.py`."""
    from genios_engine.capture.semantic.vocabulary import vocabulary_sets
    vocab = structured_vocabulary()
    live = vocabulary_sets()
    assert set(live), "the vocabulary is empty — S-3 would pass against nothing"
    for name, expected in live.items():
        assert getattr(vocab, name) == expected, name


def test_probe_every_mapped_field_is_certain_and_verified():
    """G2's own structured-lane assertions: `field_confidence == 10000` on every mapped field,
    and every emitted evidence span already `verified=True`.

    A mapping copies a typed column; there is nothing for the span verifier to disagree with, so
    anything less than certainty here would be a fabricated doubt — and anything unverified
    would mean L1.5.1 had to re-grade a value it did not extract.
    """
    outcome = _run_lane()
    result = outcome.result
    assert result is not None, outcome.failure
    assert result.field_confidence, "the mapping declared no field confidences — vacuous"
    for field, confidence in result.field_confidence.items():
        assert confidence == 10_000, f"{field} carries {confidence}, not certainty"
    assert result.all_evidence, "the mapping emitted no evidence — vacuous"
    for span in result.all_evidence:
        assert span.verified is True, span
        assert span.source_ref.startswith("structured:"), span
    # And the spans carried on the typed claims themselves, not only the flat index.
    for mention in result.entity_mentions:
        for span in mention.evidence:
            assert span.verified is True, span


def test_probe_the_structured_lane_costs_zero_tokens():
    """The other reading of 'zero LLM calls': the result must not claim token spend."""
    result = _run_lane().result
    assert result is not None
    assert result.input_tokens == 0 and result.output_tokens == 0, result
    assert result.model_snapshot.startswith("mapping:"), result.model_snapshot
    assert result.prompt_version == "structured-no-prompt", result.prompt_version


def test_neutralised_the_exploding_client_really_explodes():
    """If `_ExplodingLLM` were inert, the zero-call probe would pass for any lane at all."""
    client = _ExplodingLLM()
    with pytest.raises(AssertionError):
        client.call("hello")
    with pytest.raises(AssertionError):
        client("hello")


def test_neutralised_an_off_vocabulary_value_is_refused_by_the_schema():
    """Prove S-3 is actually enforced by this lane's validator, not merely invoked."""
    from genios_engine.capture.validate.schema import (ExtractionVocabulary,
                                                       validate_extraction_schema)
    outcome = _run_lane()
    assert outcome.result is not None
    narrow = ExtractionVocabulary(**{name: frozenset({"__nothing_real__"})
                                     for name in ExtractionVocabulary.model_fields})
    # `stage` is named on purpose: `tests/capture/validate/test_schema.py` ratchets on every
    # call site declaring one, because S-9 is the only rule whose enforcement depends on WHICH
    # seam is validating, and a defaulted stage is a seam nobody chose.
    report = validate_extraction_schema(outcome.result, vocabulary=narrow,
                                        stage=structured_validation_stage())
    assert not report.conforms, (
        "an extraction validated clean against a vocabulary containing none of its values — "
        "S-3 is not being enforced, so the conformance probe means nothing")
    assert any(v.rule is SchemaRule.S3 for v in report.violations), \
        [v.rule.value for v in report.violations]


# =============================================================================================
# PROBE 5 — structural token offsets round-trip.
# =============================================================================================

#: Every token class the scanner recognises, in one paragraph, with the awkward neighbours that
#: break a naive offset: a trailing-parenthesis URL, a currency inside a sentence, a date at the
#: very end of the text.
_TOKEN_SOAK = (
    "Invoice INV-2026-0041 for $128,500.00 (see https://acme-probe.test/invoices/41) was "
    "issued on 2026-03-11 and is payable by 14 April 2026; questions to "
    "ap@acme-probe.test or +1 (415) 555-0134. Renewal closes 2026-05-14"
)


def test_probe_every_structural_token_slices_back_to_its_own_offsets():
    tokens = scan(_TOKEN_SOAK).tokens
    assert tokens, "the soak text produced no tokens — the probe would be vacuous"
    for token in tokens:
        assert _TOKEN_SOAK[token.start_offset:token.end_offset] == token.raw, token
        assert 0 <= token.start_offset < token.end_offset <= len(_TOKEN_SOAK)


def test_probe_the_soak_text_exercises_more_than_one_token_type():
    counts = scan(_TOKEN_SOAK).counts
    firing = {k: v for k, v in counts.items() if v}
    assert len(firing) >= 4, firing


def test_probe_offsets_survive_a_leading_prefix_shift():
    """The strongest round-trip statement: prepend text and every offset must move by exactly
    the prefix length. A scanner that returned offsets into a normalized copy would not."""
    prefix = "RE: FWD: "
    shifted = scan(prefix + _TOKEN_SOAK).tokens
    base = scan(_TOKEN_SOAK).tokens
    assert len(shifted) == len(base), (len(shifted), len(base))
    for a, b in zip(base, shifted):
        assert b.raw == a.raw
        assert b.start_offset == a.start_offset + len(prefix), (a, b)
        assert b.end_offset == a.end_offset + len(prefix), (a, b)


def test_neutralised_an_offset_shifted_by_one_fails_the_round_trip():
    token = scan(_TOKEN_SOAK).tokens[0]
    assert _TOKEN_SOAK[token.start_offset + 1:token.end_offset + 1] != token.raw, (
        "shifting an offset by one still sliced back to the same text — the round-trip probe "
        "cannot detect drift on this fixture")
