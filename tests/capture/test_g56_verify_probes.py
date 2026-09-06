"""G5/G6 verification probes — written independently of every wave that built the units.

    pytest tests/capture/test_g56_verify_probes.py -q

These are NOT a second opinion about `capture/validate/` or `capture/esqe/`; those suites are
green and were written by the agents that wrote the code. Each probe here enters L1 through a
function the PRODUCT enters it through — `run_sync`, `capture_event`, `push_ingest`,
`api/routes._run_ledger` — and asserts on what falls out. Anything a probe has to construct
itself (a lane, a grouper, a page batcher) is a unit test wearing a gate's name, and the one
failure mode this build has shipped repeatedly is a unit with no production caller.

Sections:

* SEAM   — the cross-event conflict, through a real sweep, with NO test-supplied grouper.
* D3     — a claim whose receipt ALG-08 could not verify is not a side, and is not on the card.
* D4     — a storming subject spends only its OWN budget.
* D6     — the model call rate over a mixed page, measured; the rules-only path proved with a
           client that RAISES; the cost governor actually consulted; and the PAGE SEAM reached
           from the poll door and not only the webhook door.
* D9     — `degraded_compile` survives all the way onto `GatedEvent`.
* D10    — the thread reaches S4, lands on the normalized signal, and gates ALG-15's
           `new_party_on_known_thread` in BOTH directions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture import pipeline as P
from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.esqe.normalize import ThreadContext
from genios_engine.capture.esqe.relevance import (RULE_COST_REFUSED, RelevanceCandidate,
                                                  RelevancePage)
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.validate.conflict import (Authority, NormalizedClaim,
                                                     detect_conflicts, escalate_conflicts,
                                                     render_conflict_card)
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.units import Money

VERIFY_NOW = datetime(2026, 3, 3, 8, 30, tzinfo=timezone.utc)
US = "ops@genios.ai"

V_THREAD = "thr_kestrel"
V_MSG = "msg_kestrel_01"
V_PDF = "msg_kestrel_01::kestrel_msa_countersigned.pdf"

# Deliberately different numbers and wording from every other fixture in the repo, so a probe
# cannot pass by colliding with a value some other test already made work.
V_MAIL = ("Re: Kestrel MSA — finance has the renewal down as EUR 61,500 for the year, "
          "same as last cycle.")
V_PDF_TEXT = ("MASTER SERVICES AGREEMENT — Kestrel Systems and GeniOS. Annual fee of "
              "EUR 58,200, invoiced on the anniversary date.")


def _span_dicts(text: str, quote: str) -> list[dict]:
    at = text.index(quote)
    return [{"quote": quote, "start_offset": at, "end_offset": at + len(quote)}]


@dataclass
class _LLMResult:
    parsed: dict
    raw: str
    input_tokens: int = 80
    output_tokens: int = 40
    model: str = "probe-model"
    cached: bool = False
    ok: bool = True
    error: str | None = None


class _MoneyLLM:
    """Answers from the CONTENT it is shown — `run_sync` captures a page on a thread pool, so
    an order-keyed stub is flaky by construction.

    `fabricate` makes the MAIL cite a sentence that is nowhere in the mail. That is the D3
    input: an amount whose only receipt cannot be located in the source it claims to come from.
    """

    model = "probe-model"

    def __init__(self, *, fabricate: bool = False) -> None:
        self.calls: list[str] = []
        self.fabricate = fabricate

    def call(self, prompt: str, *, max_tokens: int = 4096):
        self.calls.append(prompt)
        if "58,200" in prompt:
            text, minor, written = V_PDF_TEXT, 5_820_000, "EUR 58,200"
            evidence = _span_dicts(text, written)
        elif self.fabricate:
            # An amount NOTHING in the mail says, cited to a sentence the mail does not
            # contain. There is no offset in this text that quotes it, so ALG-08 has nothing
            # to stamp — which is exactly the input D3 is a rule about.
            text, minor, written = V_MAIL, 9_990_000, "EUR 99,900"
            evidence = [{"quote": "the parties agreed EUR 99,900 in the amendment",
                         "start_offset": 0, "end_offset": 44}]
        else:
            text, minor, written = V_MAIL, 6_150_000, "EUR 61,500"
            evidence = _span_dicts(text, written)
        payload = {
            "intent": "inform", "stance": "neutral",
            "entity_mentions": [{"surface_form": "Kestrel Systems",
                                 "entity_type": "organization",
                                 "evidence": _span_dicts(text, "Kestrel"),
                                 "confidence_bp": 9100}],
            "amounts": [{"minor_units": minor, "currency": "EUR", "as_written": written}],
            "all_evidence": evidence,
        }
        return _LLMResult(parsed=payload, raw=json.dumps(payload, sort_keys=True))


class _RaisesIfCalled:
    """A model client whose only behaviour is to fail the test with a stack trace. Proving
    "zero calls" with a counter tells you a number at the end; proving it with this tells you
    WHERE."""

    model = "must-never-be-called"

    def call(self, prompt: str, *, max_tokens: int = 4096):
        raise AssertionError("the rules-only path reached a model")


class _KestrelMailbox:
    """One Gmail message and its countersigned attachment — the two RawObjects
    `connectors/composio.py` emits for one message, linked by `parent_object_id`."""

    source = "gmail"

    def validate_connection(self) -> bool:
        return True

    def _objects(self) -> list[RawObject]:
        return [
            RawObject(source="gmail", object_type="email_message", source_object_id=V_MSG,
                      parent_object_id=V_THREAD, occurred_at=VERIFY_NOW,
                      actor_email="cfo@kestrel.example", recipients=(US,),
                      raw={"subject": "Re: Kestrel MSA", "body": V_MAIL}),
            RawObject(source="gmail", object_type="email_attachment", source_object_id=V_PDF,
                      parent_object_id=V_MSG, occurred_at=VERIFY_NOW - timedelta(hours=2),
                      actor_email="cfo@kestrel.example", recipients=(US,),
                      raw={"subject": "kestrel_msa_countersigned.pdf", "body": V_PDF_TEXT,
                           "has_attachment": True}),
        ]

    def initial_snapshot(self, cursor=None, limit=50) -> SourceBatch:
        return SourceBatch(objects=self._objects(), next_cursor=None)

    def incremental_changes(self, cursor=None, limit=50, since=None) -> SourceBatch:
        return SourceBatch(objects=self._objects(), next_cursor=None)


def _kestrel_sweep(llm=None, **lane_kw):
    lane = P.SemanticLane(llm=llm or _MoneyLLM(), eval_time=VERIFY_NOW, **lane_kw)
    summary = run_sync(_KestrelMailbox(), org_id="org_probe", connection_id="con_probe",
                       repo=InMemorySourceEventRepository(), mailbox_owner=US, semantic=lane)
    return summary, lane


# =============================================================================================
# SEAM — one conflict out of a real sweep, with nothing test-supplied in the middle
# =============================================================================================
def test_seam_a_sweep_of_two_events_yields_exactly_one_cross_event_conflict():
    """No `ConflictLane`, no `ExtractionClaimGrouper`, no `detect_conflicts` in this test. A
    connector, a repo and a lane go in; a conflict comes out of the summary."""
    summary, _ = _kestrel_sweep()

    assert summary.emitted == 2
    assert summary.conflicts is not None, "ALG-12 did not run on the sweep"
    assert len(summary.conflicts.conflicts) == 1, (
        f"expected exactly one conflict, got {len(summary.conflicts.conflicts)}")

    detected = summary.conflicts.conflicts[0]
    assert sorted(c.value.minor_units for c in detected.conflict.claims) == [5_820_000, 6_150_000]
    assert len(set(detected.event_ids)) == 2, (
        "a conflict inside ONE event is the defect this gate exists to catch")
    # The grouping half: the two claims only meet because ALG-23 unioned the attachment's
    # subject with its covering mail's across `parent_object_id`.
    assert summary.claim_groups, "no claim groups were assembled by the sweep"
    keys = {g.group_key for g in summary.claim_groups
            if len({c.event_id for c in g.claims}) > 1}
    assert keys, "no claim group spans the message and its attachment"


def test_seam_the_grouping_answer_is_what_reaches_detection_not_a_re_derived_one():
    """The subject the conflict is filed under is ALG-23's group key, not a per-claim subject.
    If detection re-derived its own subject the two amounts would never be compared, and this
    is the assertion that tells those two worlds apart."""
    summary, _ = _kestrel_sweep()
    detected = summary.conflicts.conflicts[0]
    cross = {g.group_key for g in summary.claim_groups
             if len({c.event_id for c in g.claims}) > 1}
    assert detected.subject_key in cross, (
        f"conflict filed under {detected.subject_key!r}, which is not one of the cross-event "
        f"group keys {cross!r} — detection is not reading ALG-23's answer")


# =============================================================================================
# D3 — an unverifiable receipt is not a side of a disagreement
# =============================================================================================
def test_d3_a_claim_whose_span_failed_verification_is_not_a_side_of_the_conflict():
    """Same sweep, one change: the mail's amount cites a sentence the mail does not contain.
    ALG-08 cannot locate it, so the claim must not stand opposite a signed document."""
    honest, _ = _kestrel_sweep(llm=_MoneyLLM(fabricate=False))
    assert len(honest.conflicts.conflicts) == 1, "control: the honest sweep must conflict"

    fabricated, _ = _kestrel_sweep(llm=_MoneyLLM(fabricate=True))
    assert fabricated.emitted == 2, "the event still lands; D3 is scoped to ALG-12"
    assert not fabricated.conflicts.conflicts, (
        "a claim ALG-08 could not verify was admitted as a side of a disagreement")


def test_d3_the_unverifiable_quote_never_reaches_a_rendered_card():
    """The card renders `evidence[0].quote` verbatim to a human being asked to adjudicate. A
    sentence the source does not contain must not appear there in the same typeface as one it
    does."""
    fabricated, _ = _kestrel_sweep(llm=_MoneyLLM(fabricate=True))
    rendered = "\n".join(render_conflict_card(d.conflict).render()
                         for d in fabricated.conflicts.conflicts)
    assert "in the amendment" not in rendered
    for detected in fabricated.conflicts.conflicts:
        for claim in detected.conflict.claims:
            for span in claim.evidence:
                assert span.verified, "an unverified span rode onto a card"


def test_d3_refusal_is_scoped_to_the_bad_claim_and_not_to_its_neighbours():
    """Three claims about one subject, one of them unverifiable. The other two must still
    disagree with each other — D3 is a refusal, not a batch abort."""
    text = "The fee is EUR 58,200 per year, not EUR 61,500 as the summary says."

    def good(quote: str) -> EvidenceSpan:
        at = text.index(quote)
        return EvidenceSpan(source_ref="prepared_content:p1", quote=quote, start_offset=at,
                            end_offset=at + len(quote), verified=True)

    def rotten() -> EvidenceSpan:
        return EvidenceSpan(source_ref="prepared_content:p1",
                            quote="a sentence nobody wrote here", start_offset=0,
                            end_offset=28, verified=False)

    def claim(cid: str, minor: int, written: str, span: EvidenceSpan) -> NormalizedClaim:
        return NormalizedClaim(claim_id=cid, subject_key="contract:kestrel-msa",
                               field="contract.value",
                               value=Money(minor_units=minor, currency="EUR",
                                           as_written=written),
                               authority=Authority.EMAIL_PROSE, evidence=(span,),
                               asserted_at=VERIFY_NOW, event_id=f"evt_{cid}")

    detection = detect_conflicts(
        [claim("a", 5_820_000, "EUR 58,200", good("EUR 58,200")),
         claim("b", 6_150_000, "EUR 61,500", good("EUR 61,500")),
         claim("c", 9_990_000, "EUR 99,900", rotten())],
        detected_at=VERIFY_NOW)

    assert len(detection.conflicts) == 1
    values = sorted(c.value.minor_units for c in detection.conflicts[0].conflict.claims)
    assert values == [5_820_000, 6_150_000], (
        "the two verified claims must still conflict; the unverifiable third must be absent")


# =============================================================================================
# D4 — a storm stays inside the subject that is storming
# =============================================================================================
def _storm_claims(subject: str, pairs: int, *, base: int,
                  field: str | None = None) -> list[NormalizedClaim]:
    """`pairs` disagreements about one subject, each on its OWN field so each is a conflict."""
    out: list[NormalizedClaim] = []
    for i in range(pairs):
        for n, minor in enumerate((base + i * 1000, base + i * 1000 + 500)):
            written = f"EUR {minor // 100:,}"
            text = f"line {i} says {written} for the term"
            at = text.index(written)
            out.append(NormalizedClaim(
                claim_id=f"{subject}:{i}:{n}", subject_key=subject,
                field=field or f"contract.line_{i}",
                value=Money(minor_units=minor, currency="EUR", as_written=written),
                authority=Authority.EMAIL_PROSE,
                evidence=(EvidenceSpan(source_ref="prepared_content:p", quote=written,
                                       start_offset=at, end_offset=at + len(written),
                                       verified=True),),
                asserted_at=VERIFY_NOW, event_id=f"evt_{subject}_{i}_{n}"))
    return out


def test_d4_a_capped_noisy_subject_does_not_silence_a_quiet_one_in_the_same_batch():
    """The failure this rules out: one vendor's broken export spends the whole cap and every
    other subject in the sweep goes silent, while the founder is told the vendor is what all of
    them were about."""
    cap = 3
    noisy = _storm_claims("vendor:broken-export", pairs=cap + 4, base=1_000_000)
    quiet = _storm_claims("contract:kestrel-msa", pairs=1, base=5_820_000)

    detection = detect_conflicts(noisy + quiet, detected_at=VERIFY_NOW, max_conflicts=cap)

    subjects = {d.subject_key for d in detection.conflicts}
    assert "contract:kestrel-msa" in subjects, (
        "the quiet subject's conflict was deleted by a neighbour's storm")
    per_subject = {}
    for d in detection.conflicts:
        per_subject[d.subject_key] = per_subject.get(d.subject_key, 0) + 1
    assert per_subject["vendor:broken-export"] == cap, "the cap must still bind the storm"
    assert per_subject["contract:kestrel-msa"] == 1, "the quiet subject keeps its own budget"
    assert detection.total_detected == (cap + 4) + 1, (
        "the tally must report what was DETECTED, not what survived")


def test_d4_the_quiet_subject_keeps_its_escalation_while_the_storm_collapses_to_one():
    """The half that costs the most when the guard is global: INFORMATION_CONFLICT for the deal
    that quietly disagreed must survive the noisy neighbour."""
    cap = 3
    noisy = _storm_claims("vendor:broken-export", pairs=cap + 4, base=1_000_000)
    # `contract.value` is one of doc 05's MATERIAL fields — the quiet subject has to be
    # asking for a signal at all before "did the storm delete it" means anything.
    quiet = _storm_claims("contract:kestrel-msa", pairs=1, base=5_820_000,
                          field="contract.value")
    detection = detect_conflicts(noisy + quiet, detected_at=VERIFY_NOW, max_conflicts=cap)

    storming = {t.subject_key for t in detection.storming}
    assert "vendor:broken-export" in storming
    assert "contract:kestrel-msa" not in storming

    escalations = escalate_conflicts(detection)
    by_subject: dict[str, int] = {}
    for e in escalations:
        by_subject[e.subject_key] = by_subject.get(e.subject_key, 0) + 1
    assert by_subject.get("vendor:broken-export") == 1, "a storm raises exactly one signal"
    assert by_subject.get("contract:kestrel-msa", 0) >= 1, (
        "the quiet subject lost its INFORMATION_CONFLICT to a neighbour's storm")


# =============================================================================================
# D6 — what the model actually costs, measured at the door
# =============================================================================================
class _CountingRelevanceLLM:
    """LLM-5's client, counting PROMPTS and the items inside them.

    The number that matters is `prompts`: one prompt for a page is the seam working, one prompt
    per ambiguous event is the seam being bypassed, and both produce identical decisions — which
    is exactly why the defect survived every functional test written about it.
    """

    model = "probe-relevance"

    def __init__(self) -> None:
        self.prompts: list[str] = []
        self.items = 0

    def call(self, prompt: str, *, max_tokens: int = 4096):
        self.prompts.append(prompt)
        count = prompt.count("ITEM ") or prompt.count("item ") or 1
        self.items += count
        verdicts = [{"item": i, "business": True, "description": "probe"}
                    for i in range(1, count + 1)]
        payload = {"verdicts": verdicts}
        return _LLMResult(parsed=payload, raw=json.dumps(payload))


class _NotBusinessLLM:
    """LLM-5 answering "not business" for every item it is shown."""

    model = "probe-relevance-no"

    def call(self, prompt: str, *, max_tokens: int = 4096):
        count = prompt.count("ITEM ") or 1
        payload = {"verdicts": [{"item": i, "business": False, "description": "personal"}
                                for i in range(1, count + 1)]}
        return _LLMResult(parsed=payload, raw=json.dumps(payload))


class _MixedPage:
    """A page of ordinary mail: `ambiguous` strangers plus `known` counterparties.

    A stranger with no bulk headers and no service-account pattern is precisely what
    `_rule_verdict` returns `None` for — the only input LLM-5 is ever given.
    """

    source = "gmail"

    def __init__(self, ambiguous: int = 12, known: int = 6) -> None:
        self.ambiguous = ambiguous
        self.known = known

    def validate_connection(self) -> bool:
        return True

    def _objects(self) -> list[RawObject]:
        out = []
        for i in range(self.ambiguous):
            out.append(RawObject(
                source="gmail", object_type="email_message",
                source_object_id=f"amb_{i}", occurred_at=VERIFY_NOW,
                actor_email=f"stranger{i}@elsewhere.example", recipients=(US,),
                raw={"subject": f"Quick question {i}",
                     "body": f"Hello, following up on item {i} from last week. Regards."}))
        for i in range(self.known):
            out.append(RawObject(
                source="gmail", object_type="email_message",
                source_object_id=f"known_{i}", occurred_at=VERIFY_NOW,
                actor_email=f"partner{i}@kestrel.example", recipients=(US,),
                raw={"subject": f"Kestrel update {i}",
                     "body": f"Update {i} on the Kestrel rollout."}))
        return out

    def initial_snapshot(self, cursor=None, limit=50) -> SourceBatch:
        return SourceBatch(objects=self._objects(), next_cursor=None)

    def incremental_changes(self, cursor=None, limit=50, since=None) -> SourceBatch:
        return SourceBatch(objects=self._objects(), next_cursor=None)


def _known_sender(raw: RawObject) -> bool:
    return str(raw.actor_email or "").endswith("@kestrel.example")


class _QuietExtractor:
    """S2's client, answering nothing. It exists so the relevance client can be counted alone:
    one object serving both stages makes an extraction prompt indistinguishable from a
    relevance prompt, which is the measurement this whole section is about."""

    model = "probe-extractor"

    def call(self, prompt: str, *, max_tokens: int = 4096):
        payload = {"intent": "inform", "stance": "neutral", "all_evidence": []}
        return _LLMResult(parsed=payload, raw=json.dumps(payload))


_SWEEP = 0


def _mixed_sweep(*, page: RelevancePage, connector=None):
    """One page through the POLL door, with a fresh org per call.

    Fresh because the dedup ledger is keyed on `(org, source_object_id)` and a second sweep of
    the same fixture is a redelivery — which is correct behaviour and would silently empty
    every assertion below it."""
    global _SWEEP
    _SWEEP += 1
    lane = P.SemanticLane(llm=_QuietExtractor(), eval_time=VERIFY_NOW, relevance_page=page)
    return run_sync(connector or _MixedPage(), org_id=f"org_probe_d6_{_SWEEP}",
                    connection_id=f"con_probe_d6_{_SWEEP}",
                    repo=InMemorySourceEventRepository(), mailbox_owner=US,
                    sender_resolver=_known_sender, semantic=lane)


def test_d6_the_poll_door_buys_one_prompt_for_a_page_not_one_per_ambiguous_event():
    """THE WIRING CLAIM. `pipeline.prime_relevance_page` names both capture doors in its own
    docstring — `push_ingest.ingest_pushed_objects` AND `sync_runner.run_sync`. The webhook
    door calls it. The poll door is the one every tenant is actually served by.

    Decisions are identical either way, so nothing functional goes red when the seam is
    bypassed; the only observable is the prompt count.
    """
    llm = _CountingRelevanceLLM()
    page = RelevancePage(llm=llm)
    _mixed_sweep(page=page)

    stats = page.stats
    assert stats.ambiguous == 12, f"fixture drifted: {stats.ambiguous} ambiguous events"
    assert len(llm.prompts) == 1, (
        f"the page's ambiguous remainder cost {len(llm.prompts)} prompts, not 1 — "
        "run_sync is not priming the D6 page seam")


def test_d6_the_measured_share_reaches_the_model_for_under_the_planned_fraction():
    """The plan bounds the model to a SHARE of events. That bound is meaningless unless the
    page reports a population, which is what priming is for."""
    llm = _CountingRelevanceLLM()
    page = RelevancePage(llm=llm)
    _mixed_sweep(page=page)

    stats = page.stats
    assert stats.total == 18, f"every event must be DECIDED once, got {stats.total}"
    assert stats.cache_hits == stats.ambiguous, (
        f"{stats.cache_hits} of {stats.ambiguous} ambiguous events read the page verdict — "
        "the rest bought their own call")
    assert stats.llm_calls == 1


def test_d6_a_page_of_known_counterparties_never_touches_a_model_at_all():
    """Zero calls proved with a client that RAISES. A counter tells you a number at the end;
    this tells you the file and line."""
    boom = _RaisesIfCalled()
    page = RelevancePage(llm=boom)
    summary = _mixed_sweep(page=page, connector=_MixedPage(ambiguous=0, known=6))
    assert summary.emitted == 6
    assert page.stats.llm_calls == 0
    assert page.stats.ambiguous == 0


def test_d6_no_client_at_all_still_qualifies_the_whole_page_and_fails_open():
    """The rules-only path is not a degraded mode: with no client the events are KEPT at
    unknown authority, never filtered."""
    page = RelevancePage(llm=None)
    summary = _mixed_sweep(page=page)
    assert summary.emitted == 18
    assert page.stats.llm_calls == 0
    kept = [g for g in summary.gated]
    assert len(kept) == 18, "failing open means keeping the events, not dropping them"


class _RefusingGovernor:
    """L1.4.8's governor, saying no. The only answer this seam can act on."""

    def __init__(self) -> None:
        self.asked = 0

    def decide(self, request):
        self.asked += 1

        class _V:
            admitted = False
            reason = "daily_cap_exhausted"
        return _V()


def test_d6_the_cost_governor_is_consulted_before_any_relevance_prompt_and_can_refuse():
    """The defect this build shipped once already: a governor built, tested, and never asked.
    The probe asserts BOTH halves — that it was asked, and that its refusal was obeyed."""
    llm = _RaisesIfCalled()          # a refusal that still called would raise here
    governor = _RefusingGovernor()
    page = RelevancePage(llm=llm, governor=governor)
    summary = _mixed_sweep(page=page)

    assert governor.asked >= 1, "the cost governor was never consulted"
    assert page.stats.llm_calls == 0, "a refused prompt was sent anyway"
    assert summary.emitted == 18, "a refused budget must not delete a message"
    assert page.stats.budget_alert and "cost governor" in page.stats.budget_alert

    refused = page.decide(RelevanceCandidate(
        event_id="probe_after_refusal", page_key="probe_after_refusal",
        sender="nobody@elsewhere.example", subject="hello",
        snippet="an ordinary note with no rule to decide it"))
    assert refused.relevant is True, "fail OPEN — the event is kept at unknown authority"
    assert refused.rule == RULE_COST_REFUSED


# =============================================================================================
# D9 — degraded_compile survives to the published envelope
# =============================================================================================
def _one_event(raw: RawObject, *, coverage_fn=None, llm=None, relevance_page=None, **kw):
    lane = None
    if llm is not None or relevance_page is not None:
        lane = P.SemanticLane(llm=llm or _QuietExtractor(), eval_time=VERIFY_NOW,
                              relevance_page=relevance_page)
    return P.capture_event(raw, org_id="org_probe_d9", connection_id="con_probe_d9",
                           repo=InMemorySourceEventRepository(), mailbox_owner=US,
                           coverage_fn=coverage_fn, semantic=lane, **kw)


def _plain_raw(**over) -> RawObject:
    base = dict(source="gmail", object_type="email_message", source_object_id="msg_d9",
                occurred_at=VERIFY_NOW, actor_email="cfo@kestrel.example", recipients=(US,),
                raw={"subject": "Kestrel MSA renewal",
                     "body": "The Kestrel MSA renews on 1 June and finance wants a decision."})
    base.update(over)
    return RawObject(**base)


def _ready(domain: str) -> dict:
    return {"coverage_ready": True, "coverage_state": "ready", "missing_required": []}


def _not_ready(domain: str) -> dict:
    return {"coverage_ready": False, "coverage_state": "insufficient",
            "missing_required": ["crm"]}


def test_d9_an_uncovered_domain_sets_degraded_compile_on_the_gated_event():
    """L3 must be able to tell a degraded compile from a full one, and the only carrier is the
    published envelope. This is the field, on the object that leaves L1."""
    # `coverage_fn` maps a domain to `coverage/model.compute_coverage`'s DICT. A bool is not
    # "covered", it is unreadable — and `_coverage_for` correctly reports unassessable for it.
    covered = _one_event(_plain_raw(), coverage_fn=_ready)
    uncovered = _one_event(_plain_raw(source_object_id="msg_d9b"), coverage_fn=_not_ready)

    assert covered.gated is not None and uncovered.gated is not None
    assert uncovered.gated.degraded_compile is True, (
        "the domain tagger's degraded flag never reached GatedEvent")
    assert covered.gated.degraded_compile is False, (
        "control: a fully covered event must NOT be flagged degraded")


def test_d9_the_degraded_flag_is_also_on_the_trace_row_that_explains_it():
    """A flag with no reason is an unanswerable support ticket."""
    result = _one_event(_plain_raw(source_object_id="msg_d9c"), coverage_fn=_not_ready)
    esqe_rows = [r for r in result.trace.records if r.stage == P.ESQE_STAGE]
    assert esqe_rows, "S4 wrote no trace row"
    assert esqe_rows[-1].detail.get("degraded_compile") is True
    assert esqe_rows[-1].detail.get("domains"), "the flag must name the domains it is about"


# =============================================================================================
# D10 — the conversation reaches S4 and is acted on
# =============================================================================================
def test_d10_the_thread_reaches_s4_and_lands_on_every_normalized_signal():
    """`run_esqe_stage` derives the thread and passes it to L1.6.2. Before that seam existed
    ALG-22 fell to `event:{id}` and two messages of one conversation produced two subjects."""
    raw = _plain_raw(source_object_id="msg_d10", parent_object_id=V_THREAD,
                     raw={"subject": "Re: Kestrel MSA",
                          "body": "Confirming we will send the countersigned MSA by 12 June."})
    result = _one_event(raw, llm=_MoneyLLM())

    assert result.esqe is not None and result.esqe.thread is not None
    thread = result.esqe.thread
    assert thread.thread_key == f"thread:{V_THREAD}", (
        "an event whose parent IS a thread must key on it, or ALG-22 falls to the event")
    assert thread.direction == "inbound" and thread.ball_in_court == "us", (
        "they spoke last, so we owe the reply")
    for signal in result.esqe.normalized:
        assert signal.thread.thread_key == thread.thread_key, (
            "a normalized signal was qualified without its conversation")


def test_d10_the_thread_is_derived_even_for_an_event_ruled_out_of_the_business():
    """Provenance stays true about a message we decided not to act on — an operator asking
    "why was this not relevant?" is asking about a conversation, not an orphan."""
    # An ambiguous stranger whose verdict comes back NOT business. Chosen over the obvious
    # fixtures on purpose: a bulk-header digest and a service-account robot are both refused by
    # S1's noise rules several stages before S4, so neither would prove anything about whether
    # the ESQE stage derived a thread for an event it ruled out.
    raw = _plain_raw(source_object_id="msg_d10_ruled_out", parent_object_id=V_THREAD,
                     actor_email="stranger@elsewhere.example",
                     raw={"subject": "Re: conference photos",
                          "body": "Great to see everyone at the meetup last night."})
    result = _one_event(raw, relevance_page=RelevancePage(llm=_NotBusinessLLM()))
    assert result.esqe is not None
    assert result.esqe.relevance.relevant is False, "fixture drifted: this must be ruled out"
    assert result.esqe.thread is not None
    assert result.esqe.thread.thread_key == f"thread:{V_THREAD}"


def test_d10_thread_parties_gate_relationship_change_in_both_directions():
    """ALG-15's rule, and the refusal underneath it. `parties=None` is *"we do not know the
    history"*, which is NOT *"the thread had no participants"* — firing RELATIONSHIP_CHANGE on
    it would fire it on everybody, forever."""
    from genios_engine.capture.esqe.detector import DetectionInput, detect_signals
    from genios_engine.contracts.evidence import EvidenceSpan as _Span
    from genios_engine.contracts.extraction import EntityMention, ExtractionResult
    from genios_engine.contracts.signal import SignalType

    body = "Looping in Dana Reyes from Kestrel Systems on the renewal."
    at = body.index("Dana Reyes")
    mention = EntityMention(surface_form="Dana Reyes", entity_type="person", confidence_bp=9000,
                            evidence=[_Span(source_ref="prepared_content:p", quote="Dana Reyes",
                                            start_offset=at, end_offset=at + 10, verified=True)])
    extraction = ExtractionResult(
        intent="inform", stance="neutral", entity_mentions=[mention],
        model_snapshot="probe-model", prompt_version="p1", schema_version="1",
        extraction_profile="email", input_tokens=10, output_tokens=5)

    unknown_history = detect_signals(DetectionInput(
        extraction=extraction, eval_time=VERIFY_NOW, thread_parties=None))
    assert SignalType.RELATIONSHIP_CHANGE not in unknown_history.types, (
        "an unknown thread history must not be read as an empty one")

    known_history = detect_signals(DetectionInput(
        extraction=extraction, eval_time=VERIFY_NOW,
        thread_parties=frozenset({"kestrel systems", "ops@genios.ai"})))
    assert SignalType.RELATIONSHIP_CHANGE in known_history.types, (
        "a new party on a KNOWN thread is exactly ALG-15's predicate")
    fired = [sig for sig in known_history.signals
             if sig.signal_type is SignalType.RELATIONSHIP_CHANGE]
    assert fired and fired[0].predicate == "new_party_on_known_thread", (
        "the predicate must name WHY, or nobody can check the claim")


# =============================================================================================
# D8 — a detected conflict is FILED, and leaves with the tenant
# =============================================================================================
def _disposable_org(url: str) -> str:
    """A real `orgs` row of our own so the FK is satisfied and no shared tenant is touched."""
    import uuid

    from sqlalchemy import text

    from genios_engine.platform.db import get_engine

    org = f"org_g56probe_{uuid.uuid4().hex[:10]}"
    with get_engine(url).begin() as conn:
        template = conn.execute(text("select id from orgs limit 1")).scalar()
        if not template:
            pytest.skip("no org in the scratch database to clone")
        columns = [r.column_name for r in conn.execute(text(
            "select column_name from information_schema.columns "
            "where table_schema='public' and table_name='orgs'")).all()]
        unique = {r.column_name for r in conn.execute(text(
            "select a.attname as column_name from pg_index i "
            "join pg_attribute a on a.attrelid=i.indrelid and a.attnum = any(i.indkey) "
            "where i.indrelid='public.orgs'::regclass and i.indisunique")).all()}
        projection = ", ".join(f":clone_{c} as {c}" if c in unique else c for c in columns)
        params = {"t": template}
        params.update({f"clone_{c}": (org if c == "id" else f"{org}@probe.invalid")
                       for c in unique})
        conn.execute(text(f"insert into orgs ({', '.join(columns)}) select {projection} "
                          "from orgs where id=:t"), params)
    return org


@pytest.fixture()
def pg(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set")
    return live_db_url


def test_d8_a_sweeps_conflicts_reach_real_postgres_and_die_with_the_org(pg):
    """End to end on a real database: a SWEEP's conflict — not a hand-built row — is filed
    through the seam `api/routes._run_ledger` calls, and `delete from orgs` takes it with it.

    The store is pointed at the scratch database rather than taken from `routes` because which
    URL `make_conflict_store` chose is a settings decision; what this probe is about is whether
    a real `ConflictOutcome` survives serialisation, the FK, and the cascade.
    """
    from sqlalchemy import text

    from genios_engine.capture.validate.conflict_store import (PostgresConflictStore,
                                                               persist_sweep_conflicts)
    from genios_engine.platform.db import get_engine

    summary, _ = _kestrel_sweep()
    assert summary.conflicts and summary.conflicts.conflicts, "fixture drifted: nothing to file"

    org = _disposable_org(pg)
    store = PostgresConflictStore(pg)
    written = persist_sweep_conflicts(summary, org_id=org, store=store)
    assert written == 1, f"the sweep's conflict was not filed ({written} rows)"

    engine = get_engine(pg)
    with engine.begin() as conn:
        row = conn.execute(text("select claims, event_ids, resolution from signal_conflicts "
                                "where org_id=:o"), {"o": org}).one()
    values = sorted(c["value"]["minor_units"] for c in row.claims)
    assert values == [5_820_000, 6_150_000], "the losing claim did not survive storage"
    assert len(row.event_ids) == 2, "the stored row cannot be traced to two messages"

    with engine.begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": org})
        left = conn.execute(text("select count(*) from signal_conflicts where org_id=:o"),
                            {"o": org}).scalar()
    assert left == 0, ("a deleted tenant's disputed contract amounts and quoted sentences "
                       "outlived the account")


class _SpyStore:
    def __init__(self) -> None:
        self.rows: list = []

    def put(self, rows) -> int:
        self.rows.extend(rows)
        return len(rows)


def test_d8_the_request_path_hook_files_conflicts_and_not_only_the_ledger(monkeypatch):
    """WIRED — driven from `api/routes._run_ledger`, the hook every `run_sync` caller in the
    HTTP layer passes as `run_ledger=`. Six call sites read the summary's conflict counts and
    dropped the object; filing it from the hook is what makes the record independent of which
    caller remembered.
    """
    from genios_engine.api import routes

    summary, _ = _kestrel_sweep()
    spy = _SpyStore()
    monkeypatch.setattr(routes, "_conflict_store", spy)

    routes._run_ledger(org_id="org_probe_d8", connection_id="con_probe_d8", source="gmail",
                       mode="incremental", summary=summary)

    assert len(spy.rows) == 1, "the request-path hook did not file the sweep's conflict"
    assert spy.rows[0].org_id == "org_probe_d8"
    assert len(spy.rows[0].claims) == 2, "both sides must be filed, never pruned"


def test_d8_conflict_filing_does_not_depend_on_the_l2_graph_store_being_built(monkeypatch):
    """`_run_ledger` returns early when the L2 graph store is absent. Conflict persistence sits
    AFTER that return, so an engine that has a conflict store but no graph store files nothing
    — silently, with no log line, because the early return is about the sync LEDGER and knows
    nothing about ALG-12. Two unrelated subsystems must not share one off-switch."""
    from genios_engine.api import routes

    summary, _ = _kestrel_sweep()
    spy = _SpyStore()
    monkeypatch.setattr(routes, "_conflict_store", spy)
    monkeypatch.setattr(routes, "_graph", None)

    routes._run_ledger(org_id="org_probe_d8b", connection_id="con_probe_d8b", source="gmail",
                       mode="incremental", summary=summary)

    assert len(spy.rows) == 1, (
        "no l1_sync_runs ledger meant no conflict record either — the disagreement between a "
        "signed PDF and the mail quoting it survived exactly as long as the request")


# =============================================================================================
# WIRING AUDIT · L1.5.4-U2 — the alias table, on the request path
# =============================================================================================
AWS_SHORT = "Renewal quote from AWS came in at EUR 44,000 for the year."
AWS_LONG = "Amazon Web Services have the annual figure at EUR 47,500 on the order form."


class _VendorLLM:
    """Two messages naming ONE vendor two ways, with two different amounts."""

    model = "probe-model"

    def call(self, prompt: str, *, max_tokens: int = 4096):
        if "Amazon Web Services" in prompt:
            text, surface, minor, written = AWS_LONG, "Amazon Web Services", 4_750_000, "EUR 47,500"
        else:
            text, surface, minor, written = AWS_SHORT, "AWS", 4_400_000, "EUR 44,000"
        payload = {
            "intent": "inform", "stance": "neutral",
            "entity_mentions": [{"surface_form": surface, "entity_type": "vendor",
                                 "evidence": _span_dicts(text, surface),
                                 "confidence_bp": 9000}],
            "amounts": [{"minor_units": minor, "currency": "EUR", "as_written": written}],
            "all_evidence": _span_dicts(text, written),
        }
        return _LLMResult(parsed=payload, raw=json.dumps(payload))


class _TwoVendorMessages:
    """Two UNRELATED messages — no `parent_object_id` between them. The thread rung of ALG-22
    therefore cannot join them, so the only thing that can is the canonical hint."""

    source = "gmail"

    def validate_connection(self) -> bool:
        return True

    def _objects(self) -> list[RawObject]:
        return [
            RawObject(source="gmail", object_type="email_message",
                      source_object_id="msg_vendor_short", occurred_at=VERIFY_NOW,
                      actor_email="sales@reseller.example", recipients=(US,),
                      raw={"subject": "Renewal quote", "body": AWS_SHORT}),
            RawObject(source="gmail", object_type="email_message",
                      source_object_id="msg_vendor_long",
                      occurred_at=VERIFY_NOW - timedelta(hours=3),
                      actor_email="billing@reseller.example", recipients=(US,),
                      raw={"subject": "Order form", "body": AWS_LONG}),
        ]

    def initial_snapshot(self, cursor=None, limit=50) -> SourceBatch:
        return SourceBatch(objects=self._objects(), next_cursor=None)

    def incremental_changes(self, cursor=None, limit=50, since=None) -> SourceBatch:
        return SourceBatch(objects=self._objects(), next_cursor=None)


def test_the_alias_table_reaches_production_and_joins_one_vendor_named_two_ways():
    """`canonical.fill_canonical_hints` is L1.5.4-U2's seam and NOTHING on a request path called
    it, so `EntityMention.canonical_hint` was None on every event the product has ever captured
    and the shipped alias table was dead code. `claim_group._org_anchor` then fell to
    `derive_key` on the raw surface form — which is correct for a name the table has never heard
    of, and wrong for "AWS" against "Amazon Web Services": two keys, two subjects, and the two
    amounts never compared.

    Both halves are asserted, because a hint that is set but not USED would pass the first.
    """
    summary = run_sync(_TwoVendorMessages(), org_id="org_probe_alias",
                       connection_id="con_probe_alias",
                       repo=InMemorySourceEventRepository(), mailbox_owner=US,
                       semantic=P.SemanticLane(llm=_VendorLLM(), eval_time=VERIFY_NOW))

    assert summary.emitted == 2
    hints = {m.canonical_hint for r in summary.results if r.extraction is not None
             for m in r.extraction.entity_mentions}
    assert hints == {"amazon web services"}, (
        f"the alias table never reached the extraction: canonical_hint = {hints}")

    assert summary.conflicts is not None
    assert len(summary.conflicts.conflicts) == 1, (
        "one vendor written two ways produced two subjects, so its two renewal figures were "
        "never compared")
    values = sorted(c.value.minor_units for c in summary.conflicts.conflicts[0].conflict.claims)
    assert values == [4_400_000, 4_750_000]


def test_a_vendor_the_alias_table_has_never_heard_of_still_anchors_its_own_claims():
    """The control that keeps the fix honest: filling hints must not DELETE the derived-key
    fallback for a name with no table row."""
    summary, _ = _kestrel_sweep()
    hints = {m.canonical_hint for r in summary.results if r.extraction is not None
             for m in r.extraction.entity_mentions}
    assert hints and None not in hints, f"an unlisted vendor lost its anchor entirely: {hints}"
    assert summary.conflicts.conflicts, "the unlisted vendor's claims stopped grouping"
