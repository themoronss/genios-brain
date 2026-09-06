"""THE WIRING PROBES — every one of these drives a REAL request path, not a unit.

    pytest tests/capture/test_wiring_close.py -q

This build has now shipped the same defect fourteen times: a unit written, unit-tested, proved
correct, and never called. A green sibling test file is not evidence against it — every test in
`tests/capture/<package>/` constructs its own collaborator, so it proves the UNIT and says
nothing about the WIRING. So every test here enters through `capture_event`, `run_sync`,
`ingest_pushed_objects` or an HTTP route, and asserts on what came back out.

Nine properties, one per thing that was claimed and never checked end to end:

1.  ALG-09's recurrence, calendar-duration and business-day cascades resolve on the SEMANTIC
    lane's real path — the model states `as_written`, the pipeline resolves it, and the window
    lands on the extraction the pipeline returns. Those three rows of the cascade are reached
    only from inside `resolve_date`, so a unit test of `resolve_recurrence` proves nothing about
    whether an event ever gets one.
2.  A detected conflict RENDERS — `render_conflict_card` is reached from the pipeline's own
    conflict lane, so a disagreement becomes something a human reads rather than a stored row.
3.  Layer 2 reads what Layer 1 published: the situation carries L1's `importance_bp` and its
    provenance, NOT the 5000 constant that made 193 of 223 signals identical.
4.  Every BLOCKING V-rule rejection leaves a ledger row naming the rule.
5.  A HubSpot deal produces a qualified signal with the semantic lane ABSENT and zero LLM calls.
6.  The same message ingested twice yields an identical subject key.
7.  The `signal_type` CHECK constraint rejects an out-of-taxonomy value at the DATABASE level.
8.  The structured lane names the column whose absence cost the extraction.
9.  Org deletion removes every one of the eleven new L1 tables' rows, on real Postgres.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture import pipeline as P
from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.landing.repository import InMemorySourceEventRepository

OWNER = "founder@genios.ai"
NOW = datetime(2026, 1, 14, 9, 0, tzinfo=timezone.utc)      # a Wednesday, per conftest


class RaisingLLM:
    """Any call is an immediate, unambiguous failure — stricter than a counter."""

    model = "must-not-be-called"

    def call(self, prompt: str, *, max_tokens: int = 4096):
        raise AssertionError("a model was called on a path the rules decide")


def _email(body: str, **over) -> RawObject:
    kwargs = dict(source="gmail", object_type="email_message", source_object_id="m_probe_1",
                  occurred_at=NOW, actor_email="buyer@acme.com", recipients=(OWNER,),
                  raw={"subject": "Renewal", "body": body})
    raw = dict(kwargs["raw"])
    raw.update(over.pop("raw", {}))
    kwargs.update(over)
    kwargs["raw"] = raw
    return RawObject(**kwargs)


def _capture(raw: RawObject, **over):
    kwargs = dict(org_id="org_probe", connection_id="con_probe",
                  repo=InMemorySourceEventRepository(), mailbox_owner=OWNER)
    kwargs.update(over)
    return P.capture_event(raw, **kwargs)


def _stage(**over):
    return [r for r in over["records"] if r.stage == over["stage"]]


# ────────────────────────────────────────────────────────────────────────────────────────────
# 1 · ALG-09's three deep cascades, on the semantic lane's real path
# ────────────────────────────────────────────────────────────────────────────────────────────

RECURRENCE = "every two weeks"
CALENDAR_SPAN = "for 3 months"
BUSINESS_DAYS = "in 3 working days"

BODY = (f"We will review the account {RECURRENCE}, the pilot runs {CALENDAR_SPAN}, "
        f"and legal will come back {BUSINESS_DAYS}.")


@pytest.mark.parametrize("as_written,earliest,latest", [
    # A recurrence names a WINDOW to the next occurrence, not an instant.
    (RECURRENCE, datetime(2026, 1, 14, tzinfo=timezone.utc),
     datetime(2026, 1, 28, tzinfo=timezone.utc)),
    # A calendar span is month arithmetic, never 90 days — the months a renewal falls in are
    # exactly where a 30-day "month" is wrong.
    (CALENDAR_SPAN, datetime(2026, 1, 14, tzinfo=timezone.utc),
     datetime(2026, 4, 14, tzinfo=timezone.utc)),
    # Wed 14th + 3 BUSINESS days = Monday 19th. A calendar-day answer would say Saturday 17th.
    (BUSINESS_DAYS, datetime(2026, 1, 19, tzinfo=timezone.utc),
     datetime(2026, 1, 19, tzinfo=timezone.utc)),
])
def test_the_deep_date_cascades_resolve_on_the_real_capture_path(
        fake_llm, as_written, earliest, latest):
    """Rows 12 and 13 of ALG-09's cascade (`resolve_recurrence`, `resolve_calendar_duration`,
    `add_business_days`) are reached ONLY from inside `resolve_date`. This drives the whole
    seam: a model states the phrase, `capture_event` resolves it, and the window is on the
    extraction the pipeline hands back."""
    quote = as_written
    llm = fake_llm({"intent": "inform", "stance": "neutral",
                    "dates_mentioned": [{"as_written": as_written,
                                         "evidence": [{"quote": quote}]}]})
    res = _capture(_email(BODY), semantic=P.SemanticLane(llm=llm, eval_time=NOW))

    assert res.outcome == "emitted"
    assert res.extraction is not None, "the semantic lane produced nothing to resolve"
    dates = [d for d in res.extraction.dates_mentioned if d.as_written == as_written]
    assert dates, f"{as_written!r} never reached the extraction the pipeline returned"
    resolved = dates[0]
    assert resolved.certainty.value != "unresolved", (
        f"{as_written!r} came back UNRESOLVED on the real path — the cascade row that answers "
        "it is reachable only through `resolve_date` and is not being reached")
    assert resolved.earliest.date() == earliest.date()
    assert resolved.latest.date() == latest.date()
    # No clock: the window is stated against the instant the caller froze, not against today.
    assert resolved.resolved_against == NOW


# ────────────────────────────────────────────────────────────────────────────────────────────
# 5 · a HubSpot deal: qualified signal, semantic lane ABSENT, zero model calls
# ────────────────────────────────────────────────────────────────────────────────────────────

def _deal(**over) -> RawObject:
    raw = {"dealname": "Acme Renewal", "dealstage": "contractsent", "amount": "84000",
           "deal_currency_code": "USD", "closedate": "2026-03-31",
           "contact_email": ["ops@acme.com"]}
    raw.update(over.pop("raw", {}))
    kwargs = dict(source="hubspot", object_type="deal", source_object_id="deal_probe",
                  occurred_at=NOW, actor_email=OWNER, content_version="v1", raw=raw)
    kwargs.update(over)
    return RawObject(**kwargs)


def test_a_hubspot_deal_qualifies_with_the_semantic_lane_absent_and_zero_model_calls():
    """The structured bypass exists precisely so a CRM row needs no model and no activation.
    `semantic=None` is the state EVERY unactivated tenant is in, and the deal must still reach
    a qualified signal — otherwise the bypass is a bypass around the product."""
    res = _capture(_deal(), esqe=P.EsqeStage(eval_time=NOW))     # no `semantic=` at all

    assert res.outcome == "emitted"
    assert res.gated is not None and res.gated.route == "structured"
    assert res.extraction is not None, "the structured lane produced no extraction"
    assert res.extraction_ref == f"struct:{res.event.event_id}"
    # ZERO tokens is the structural proof: the lane has no client parameter and imports none.
    assert res.extraction.input_tokens == 0 and res.extraction.output_tokens == 0
    # …and the semantic stage recorded a SKIP with its reason, rather than being silently absent.
    s2 = [r for r in res.trace.records if r.stage == "s2_semantic_extraction"]
    assert not s2 or s2[-1].reason_code in (None, "structured_bypass")

    esqe = res.esqe
    assert esqe is not None and esqe.detection.fired > 0, "no predicate fired on a typed deal"
    assert esqe.normalized, "nothing was normalised, so nothing can be published"
    kinds = {n.signal_type.value for n in esqe.normalized}
    assert "financial_obligation" in kinds
    # ALG-14: a system of record, from `weigh_authority`'s table — not a hardcoded 4.
    assert esqe.attribution.evidence.authority.value == "structured_source"
    # Every span points into the lane's own coordinate system, so the receipt is re-verifiable.
    for signal in esqe.normalized:
        for span in signal.evidence_refs:
            assert span.source_ref.startswith("structured:hubspot.deal.v1#")
            assert span.verified is True


def test_the_structured_lane_makes_zero_calls_against_a_client_that_raises():
    """A counter can be off by one; a client that RAISES cannot be satisfied by a swallowed
    exception. The whole `capture_event` passage of a typed object, with LLM-5 wired to a bomb."""
    res = _capture(_deal(), esqe=P.EsqeStage(eval_time=NOW, relevance_llm=RaisingLLM()),
                   semantic=P.SemanticLane(llm=RaisingLLM(), eval_time=NOW))
    assert res.outcome == "emitted"
    assert res.extraction is not None


# ────────────────────────────────────────────────────────────────────────────────────────────
# 8 · the structured lane names the column whose absence cost the extraction
# ────────────────────────────────────────────────────────────────────────────────────────────

def test_the_column_that_killed_the_extraction_is_named_on_the_trace():
    """`FieldMap` refuses to default a currency — correctly — so a deal whose
    `deal_currency_code` column went away loses its WHOLE extraction. `absent_fields` answered
    `()` for that object: it walked `mapping.fields` only, so the one column responsible for the
    failure was the one column it could not name."""
    res = _capture(_deal(raw={"deal_currency_code": None}), esqe=P.EsqeStage(eval_time=NOW))

    rec = [r for r in res.trace.records if r.stage == P.STRUCTURED_STAGE]
    assert rec, "the structured lane left no trace record at all"
    detail = rec[-1].detail
    assert "deal_currency_code" in detail["absent_names"], (
        "the mapping drifted from the provider's schema and the trace does not name the column")
    # …and the refusal is still explained, with ALG-14's rank beside it.
    assert rec[-1].reason_code and "deal_currency_code" in rec[-1].reason_code
    assert detail["authority"] == "structured_source"
    assert detail["authority_basis"] == "object_type"


def test_a_complete_deal_reports_no_absent_columns_and_full_confidence():
    """The other half: absence must MEAN something, so a complete object reports none. The two
    relation columns are alternate payload shapes for one edge — a deal carries one of them, and
    reporting the unused alternate would put a name here on every object of the source, which is
    the exact signature this list uses to mean 'drift'."""
    res = _capture(_deal(), esqe=P.EsqeStage(eval_time=NOW))

    detail = [r for r in res.trace.records if r.stage == P.STRUCTURED_STAGE][-1].detail
    assert detail["absent_names"] == []
    assert detail["refused_names"] == []
    # Every field that arrived has a receipt AND a confidence; the coordinate system additionally
    # covers the RELATION column (`contact_email`), which is a source_ref with no field target —
    # so the index is the wider of the two by exactly the relations that arrived.
    assert detail["confident_fields"] == 4          # the four declared FieldMaps
    assert detail["source_refs"] == 5               # + the one relation column that arrived


# ────────────────────────────────────────────────────────────────────────────────────────────
# 6 · the same message ingested twice yields an identical subject key
# ────────────────────────────────────────────────────────────────────────────────────────────

def test_the_same_object_ingested_twice_yields_an_identical_subject_key():
    """ALG-22's subject key is what makes a signal the SAME signal across sweeps — the floor
    dedups on it, the lifecycle supersedes on it, and L2 correlates on it. A key that moved
    between two ingests of one message would make every re-sync a new signal."""
    first = _capture(_deal(), esqe=P.EsqeStage(eval_time=NOW),
                     repo=InMemorySourceEventRepository())
    second = _capture(_deal(), esqe=P.EsqeStage(eval_time=NOW),
                      repo=InMemorySourceEventRepository())

    keys_a = [n.subject_key for n in first.esqe.normalized]
    keys_b = [n.subject_key for n in second.esqe.normalized]
    assert keys_a and keys_a == keys_b
    # It is derived from the OBJECT, not from the event id — which changes on every ingest.
    assert first.event.event_id != second.event.event_id
    assert all("deal_probe" in k for k in keys_a)


def test_a_re_ingest_at_a_later_instant_still_yields_the_same_subject_key():
    """The key must not carry the clock either: a nightly re-sync happens at a different instant
    and must land on the same subject, or the floor's dedup and the lifecycle's supersede both
    stop working the moment a tenant is swept twice."""
    early = _capture(_deal(), esqe=P.EsqeStage(eval_time=NOW))
    later = _capture(_deal(), esqe=P.EsqeStage(eval_time=NOW + timedelta(days=9)))

    assert [n.subject_key for n in early.esqe.normalized] == \
           [n.subject_key for n in later.esqe.normalized]


# ────────────────────────────────────────────────────────────────────────────────────────────
# 2 · a detected conflict RENDERS, from `_run_ledger` through to what a human reads
# ────────────────────────────────────────────────────────────────────────────────────────────

from genios_engine.contracts.conflict import (Authority, Conflict, ConflictClaim,     # noqa: E402
                                              ConflictResolution)
from genios_engine.contracts.evidence import EvidenceSpan                             # noqa: E402
from genios_engine.contracts.units import Money                                       # noqa: E402


def _claim(minor: int, written: str, authority: Authority, rank: int, quote: str, ref: str):
    return ConflictClaim(
        value=Money(minor_units=minor, currency="USD", as_written=written),
        authority=authority, authority_rank=rank,
        evidence=[EvidenceSpan(source_ref=ref, quote=quote, start_offset=0,
                               end_offset=len(quote), verified=True)])


def _headline_conflict() -> Conflict:
    """Doc 05's own fixture: a signed $74,000 against $84,000 in a covering email."""
    return Conflict(
        field="contract.value",
        claims=[_claim(7_400_000, "$74,000", Authority.SIGNED_DOCUMENT, 6,
                       "total annual commitment of $74,000", "prepared_content:pc_pdf"),
                _claim(8_400_000, "$84,000", Authority.EMAIL_PROSE, 2,
                       "the renewal comes to $84,000", "prepared_content:pc_mail")],
        resolution=ConflictResolution.RESOLVED_BY_AUTHORITY,
        resolved_value=Money(minor_units=7_400_000, currency="USD", as_written="$74,000"),
        detected_at=NOW)


def test_a_detected_conflict_becomes_a_card_a_human_reads():
    """L1.5.5-U3. A conflict nobody can see is the same product as no conflict detection at all
    — worse, because the founder is told nothing while the disagreement is on record. Driven
    through the ESCALATION path (`escalations_for`), which is what the sweep calls, rather than
    through `render_conflict_card` on its own."""
    from genios_engine.capture.validate.conflict import (ConflictDetection, DetectedConflict,
                                                         escalate_conflicts)
    detection = ConflictDetection(
        conflicts=(DetectedConflict(subject_key="contract:acme-msa",
                                    conflict=_headline_conflict(),
                                    event_ids=("evt_pdf", "evt_mail")),),
        total_detected=1)

    escalations = escalate_conflicts(detection)

    assert len(escalations) == 1, "a material money disagreement raised no escalation"
    esc = escalations[0]
    assert esc.signal_type.value == "information_conflict"
    assert esc.cards, "the escalation carries no card — nothing renders"
    card = esc.cards[0]
    # BOTH sides, always. A card showing only the winner cannot explain itself, and the loser is
    # the receipt that the winner was contested.
    assert len(card.lines) == 2
    text = card.render()
    assert "74,000" in text and "84,000" in text
    assert card.verdict and "higher authority" in card.verdict
    # …and both verbatim quotes survive to the surface.
    quotes = {line.quote for line in card.lines}
    assert "total annual commitment of $74,000" in quotes
    assert "the renewal comes to $84,000" in quotes


def test_a_conflict_stored_and_read_back_still_renders(pg_url):
    """The READ path, end to end on real Postgres: `persist_sweep_conflicts` files the row the
    sweep detected, and `render_stored_conflict` — the function `GET /conflicts` calls — turns
    that row back into the same card. A row that stores but cannot render is a disagreement on
    record that nobody can be shown."""
    from sqlalchemy import text

    from genios_engine.capture.validate import conflict_store as S
    from genios_engine.capture.validate.conflict import (ConflictDetection, DetectedConflict,
                                                         render_stored_conflict)
    from genios_engine.platform.db import get_engine

    org = "org_wiring_conflict"
    _seed_org(pg_url, org)
    store = S.PostgresConflictStore(pg_url)
    detection = ConflictDetection(
        conflicts=(DetectedConflict(subject_key="contract:acme-msa",
                                    conflict=_headline_conflict(),
                                    event_ids=("evt_pdf", "evt_mail")),),
        total_detected=1)

    written = S.persist_sweep_conflicts(_Summary(detection), org_id=org, store=store)
    assert written == 1, "the sweep's conflict was not filed"

    rows = store.list(org)
    assert len(rows) == 1
    card = render_stored_conflict(rows[0])
    assert card is not None, "a stored conflict came back unrenderable"
    assert len(card.lines) == 2
    assert "74,000" in card.render() and "84,000" in card.render()
    assert card.verdict and "higher authority" in card.verdict

    with get_engine(pg_url).begin() as c:
        c.execute(text("delete from signal_conflicts where org_id = :o"), {"o": org})


class _Summary:
    """The one attribute `persist_sweep_conflicts` reads off a sweep."""

    def __init__(self, detection):
        class _Outcome:
            pass
        self.conflicts = _Outcome()
        self.conflicts.detection = detection
        self.conflicts.escalations = ()


@pytest.fixture
def pg_url(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres wiring probes skipped")
    return live_db_url


def _seed_org(url: str, org: str) -> None:
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine
    with get_engine(url).begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, :o) "
                       "on conflict (id) do nothing"), {"o": org})


# ────────────────────────────────────────────────────────────────────────────────────────────
# 4 · V-6, the one blocking rule with no ledger coverage
# ────────────────────────────────────────────────────────────────────────────────────────────

def test_a_v6_refusal_leaves_a_ledger_row_naming_the_rule():
    """V-2, V-3, V-4 and V-7 are covered in `test_rejection_ledger.py`; V-6 is not, because it
    cannot be tripped through `publish_one` — `compose_for` clamps `confidence_bp` to the SAME
    Rule 11 ceiling V-6 checks, deliberately (`publish_one`: *"so V-6's ceiling and the
    composer's ceiling can never be two different lists"*), so no composed signal can exceed it.

    That makes the rule unreachable, not exempt: a future composer change, or a caller that
    supplies `source_confidences` from somewhere else, reaches it immediately. So this drives
    the three production functions `publish_one` chains — `validate_publication`,
    `rejecting_failures`, `rejection_rows` — over a signal whose confidence DOES exceed its
    weakest source, and asserts the row names V-6.
    """
    from genios_engine.capture.esqe import publisher as PUB
    from genios_engine.contracts.publication import PublicationRule, validate_publication

    signal = _qualified(confidence_bp=9000)
    decision = validate_publication(signal, source_confidences=[9000, 4000],
                                    independent_evidence=())

    rejecting = PUB.rejecting_failures(decision)
    assert PublicationRule.V6 in rejecting, (
        "a confidence above the weakest source it was composed from was not refused by V-6: "
        "several weak sources repeating one weak thing is not corroboration")

    refused = PUB.RefusedSignal(
        org_id="org_v6", signal_id=signal.signal_id, event_id=signal.event_id,
        outcome="reject", rules=tuple(r.value for r in rejecting),
        detail="; ".join(f.detail for f in decision.failures if f.rule in set(rejecting)),
        signal_type=signal.signal_type.value, payload_ref="prepared_content:pc_v6")

    rows = PUB.rejection_rows((refused,), eval_time=NOW)
    assert len(rows) == 1
    assert "V-6" in rows[0].rules, "the ledger row does not name the rule that refused it"
    assert "weakest source" in rows[0].reason
    assert rows[0].payload_ref == "prepared_content:pc_v6"


def test_no_composed_signal_can_break_v6_on_the_real_path():
    """The other half of the claim above, asserted rather than assumed.

    `publish_one` hands `validate_publication` BOTH halves of ONE `ComposedConfidence` —
    `source_confidences` and `independent_evidence` — and that pairing is what keeps V-6 quiet,
    in two different ways depending on which branch ALG-13 took:

    * ONE WITNESS REPEATED (a single independence key): nothing is independent, so V-6 is live,
      and `enforce_rule_11` has clamped the fold to the ceiling — the module docstring's own
      failure, "five sources all repeating one weak recollection composed upward into an 8900".
    * GENUINELY INDEPENDENT WITNESSES: the lift above the ceiling is legal corroboration, and
      the same object names them, so `validate_publication` WAIVES V-6 rather than failing it.

    Both branches are asserted, because a change that broke either one would put a confidence
    past its evidence into `qualified_signals` with V-6 reporting nothing.
    """
    from genios_engine.capture.validate.confidence import ConfidenceSource, compose_confidence
    from genios_engine.contracts.conflict import Authority
    from genios_engine.contracts.publication import PublicationRule, validate_publication

    def _sources(key_of):
        return [ConfidenceSource(name=f"s{i}", confidence_bp=1000, independence_key=key_of(i),
                                 authority=Authority.EMAIL_PROSE) for i in range(50)]

    repeated = compose_confidence(_sources(lambda i: "one-recollection"))
    assert not repeated.independent_evidence, "one witness was read as fifty"
    assert repeated.confidence_bp <= min(repeated.source_confidences), (
        "fifty repetitions of one 1000 bp recollection composed UPWARD past their own weakest "
        "with nothing named independent — the exact number V-6 exists to refuse")

    independent = compose_confidence(_sources(lambda i: f"witness-{i}"))
    assert independent.independent_evidence, "fifty distinct witnesses named none"
    decision = validate_publication(_qualified(confidence_bp=independent.confidence_bp),
                                    source_confidences=independent.source_confidences,
                                    independent_evidence=independent.independent_evidence)
    assert PublicationRule.V6 in decision.waived, (
        "a lift above the ceiling backed by named independent evidence was not WAIVED — the "
        "composer and the gate are reading two different lists")
    assert not any(f.rule is PublicationRule.V6 for f in decision.failures)


def _qualified(*, confidence_bp: int):
    """One C-12 signal that satisfies every rule except the one under test."""
    from genios_engine.contracts.extraction import ExtractionResult
    from genios_engine.contracts.signal import QualifiedEnterpriseSignal, SignalType
    from genios_engine.contracts.visibility import Visibility
    quote = "the renewal comes to $84,000"
    span = EvidenceSpan(source_ref="prepared_content:pc_v6", quote=quote, start_offset=0,
                        end_offset=len(quote), verified=True)
    return QualifiedEnterpriseSignal(
        signal_id="sig_v6", org_id="org_v6", event_id="evt_v6", trace_id="trace_v6",
        source="gmail", object_type="email_message", occurred_at=NOW,
        signal_type=SignalType.CONTRACT_RENEWAL, importance_bp=7800,
        triage_lane="P1",
        extraction=ExtractionResult(intent="inform", stance="neutral",
                                    model_snapshot="fake-1", prompt_version="p1",
                                    schema_version="1", extraction_profile="email",
                                    input_tokens=10, output_tokens=5),
        evidence_refs=[span], conflicts=[],
        confidence_bp=confidence_bp,
        confidence_vector={"evidence": confidence_bp, "expertise": 10000,
                           "freshness": 10000, "coverage": 10000},
        coverage_ready=True, state="active", supersedes=None, expires_at=None,
        internal_kind=None, recipients=("ops@genios.ai",),
        versions={"preprocessor": "pp-2"},
        visibility=Visibility(scope="org", derived_from="l1:probe"))


# ────────────────────────────────────────────────────────────────────────────────────────────
# 3 · Layer 2 reads what Layer 1 published — the situation carries L1's score, not the constant
# ────────────────────────────────────────────────────────────────────────────────────────────

L1_IMPORTANCE_BP = 8125          # deliberately NOT 5000, and not a round number
DEFAULT_CONSTANT_BP = 5000       # `situation_bso.DEFAULT_IMPORTANCE_BP`


def test_layer_2_carries_layer_1s_importance_and_not_the_5000_constant(pg_url):
    """THE SEAM THIS WHOLE ROUND IS ABOUT. Layer 1 scores, qualifies, ages and STORES a signal;
    Layer 2 then built its situation object and stamped a constant over the result — so 193 of
    223 signals shared one importance and Layer 4's utility formula had nothing to rank on.

    Driven through the two production functions the compile path calls in order —
    `gather_l1_signals` (the read) and `build_business_situation` (the object Layer 3 reasons
    over) — against a REAL `qualified_signals` row joined through a REAL correlation, because
    the join is the half that decides whether the read finds anything at all.
    """
    from sqlalchemy import text

    from genios_engine.context.situation_bso import (DEFAULT_IMPORTANCE_BP,
                                                     build_business_situation,
                                                     gather_l1_signals)
    from genios_engine.platform.db import get_engine

    assert DEFAULT_IMPORTANCE_BP == DEFAULT_CONSTANT_BP, "the constant under test moved"

    org, corr, event = "org_wiring_l2", "corr_wiring_l2", "evt_wiring_l2"
    _seed_org(pg_url, org)
    engine = get_engine(pg_url)
    quote = "the renewal comes to $84,000"
    with engine.begin() as c:
        _clear_l2_probe(c, org)
        c.execute(text(
            "insert into context_correlations (correlation_id, org_id, anchor_node_id) "
            "values (:c, :o, 'node_acme') on conflict do nothing"), {"c": corr, "o": org})
        c.execute(text(
            "insert into context_correlation_members (correlation_id, org_id, event_id) "
            "values (:c, :o, :e) on conflict do nothing"), {"c": corr, "o": org, "e": event})
        c.execute(text(
            "insert into qualified_signals (signal_id, org_id, event_id, trace_id, signal_type,"
            " importance_bp, importance_version, importance_components, confidence_bp,"
            " extraction_ref, evidence_refs, visibility, state, occurred_at) "
            "values ('sig_wiring_l2', :o, :e, 'trace_l2', :t, :imp, 'alg17-v1', "
            "cast(:comp as jsonb), 8000, 'x', cast(:ev as jsonb), '{}'::jsonb, 'active', now())"),
            {"o": org, "e": event, "t": "contract_renewal", "imp": L1_IMPORTANCE_BP,
             "comp": json.dumps({"monetary_exposure_bp": 9000, "deadline_proximity_bp": 7000}),
             "ev": json.dumps([{"source_ref": "prepared_content:pc_l2", "quote": quote,
                                "start_offset": 0, "end_offset": len(quote),
                                "verified": True}])})

    try:
        with engine.connect() as c:
            l1 = gather_l1_signals(c, org, corr)
        assert l1 is not None, (
            "Layer 2's read of `qualified_signals` found nothing for a correlation that has a "
            "live signal — the L1 -> L2 boundary is not joined")
        assert l1.importance_bp == L1_IMPORTANCE_BP
        assert l1.signal_ids == ("sig_wiring_l2",)

        bso = build_business_situation(
            org_id=org, trace_id="trace_l2", signal_ids=["evt_fallback"], evidence=[],
            situation={"situation_id": "sit_l2", "situation_type": "renewal",
                       "anchor_node_id": "node_acme", "status": "active"},
            l1=l1)

        # THE ASSERTION. Layer 1's number, on the object Layer 3 reasons over.
        assert bso.importance_bp == L1_IMPORTANCE_BP, (
            f"the situation carries {bso.importance_bp}, not Layer 1's {L1_IMPORTANCE_BP}")
        assert bso.importance_bp != DEFAULT_CONSTANT_BP
        # …with its PROVENANCE, so "scored" and "defaulted" can never look the same again — the
        # state the constant made indistinguishable for 193 of 223 signals.
        assert bso.metadata["importance_source"] == "l1_qualified_signals"
        assert bso.metadata["importance_version"] == "alg17-v1"
        assert bso.metadata["importance_components"]["monetary_exposure_bp"] == 9000
        assert bso.metadata["l1_scored_count"] == 1
        # …and the REAL signal ids, not the event ids the pre-`qualified_signals` path returned.
        assert bso.signal_ids == ("sig_wiring_l2",)
        # …and Layer 1's verified span leads the evidence.
        assert bso.evidence and bso.evidence[0]["quote"] == quote
        assert bso.evidence[0]["source"] == "l1_qualified_signal"
    finally:
        with engine.begin() as c:
            _clear_l2_probe(c, org)


def test_a_situation_with_no_layer_1_signal_still_reports_the_default_as_a_default(pg_url):
    """The fallback must stay reachable AND stay legible: a pre-activation tenant gets the
    neutral number, and `importance_source` says so, so nothing downstream can read a default
    as a score."""
    from genios_engine.context.situation_bso import (DEFAULT_IMPORTANCE_BP,
                                                     build_business_situation)

    # A BSO requires evidence by contract, so the pre-`qualified_signals` caller's own graph
    # refs stand in — which is exactly the shape this fallback exists to keep working.
    bso = build_business_situation(
        org_id="org_wiring_l2", trace_id="t", signal_ids=["evt_x"],
        evidence=[{"kind": "graph_fact", "ref": "fact:acme:renewal", "reconstructed": True}],
        situation={"situation_id": "sit_none", "situation_type": "renewal",
                   "anchor_node_id": "node_acme", "status": "active"},
        l1=None)

    assert bso.importance_bp == DEFAULT_IMPORTANCE_BP
    assert bso.metadata["importance_source"] == "default"
    assert bso.metadata["l1_signal_count"] == 0


def _clear_l2_probe(c, org: str) -> None:
    from sqlalchemy import text
    for table in ("qualified_signals", "context_correlation_members", "context_correlations"):
        c.execute(text(f"delete from {table} where org_id = :o"), {"o": org})


# ────────────────────────────────────────────────────────────────────────────────────────────
# 9 · org deletion removes every one of the new tables' rows, on real Postgres
# ────────────────────────────────────────────────────────────────────────────────────────────

#: Every table L1's last eleven migrations added. Each holds the TENANT'S OWN words — quoted
#: sentences, subject keys, amounts, the names of their vendors — so a deletion that skipped one
#: leaves a deleted customer's data behind in the table built to explain what we told them.
NEW_L1_TABLES = (
    "unclassified_observations",        # 0079 — message quotes with no vocabulary word
    "l1_extraction_results",            # 0080 — the extraction itself
    "source_waitlist",                  # 0083 — sources they asked for and could not connect
    "l1_semantic_activation",           # 0085 — the pilot switch, with free-text notes
    "signal_conflicts",                 # 0087 — BOTH sides of a disagreement, verbatim
    "org_qualification_floors",         # 0088 — the number a human set for this tenant
    "qualification_floor_changes",      # 0088 — who set it, and when
    "qualification_drops",              # 0088 — what we decided NOT to show them
    "qualified_signals",                # 0089 — everything Layer 1 concluded
    "signal_lifecycle",                 # 0093 — ALG-22 subjects: their counterparties
    "org_mission_critical_entities",    # 0091 — their vendors, and a human's free-text reason
    "publication_rejections",           # 0092 — their values quoted back in `reason`
)


def test_every_new_l1_table_is_named_in_the_erasure_list():
    """The list is executed with NO try/except by design, so a name missing from it leaks
    silently rather than failing loudly — which makes "is it in the list" a real test."""
    import re

    from genios_engine.api import account_routes
    listed = set(account_routes._ORG_SCOPED_TABLES)
    missing = [t for t in NEW_L1_TABLES if t not in listed]
    assert not missing, f"tables that would survive a tenant erasure: {missing}"
    # …and every name in the list is a real table, because a misspelling breaks EVERY deletion.
    assert all(re.fullmatch(r"[a-z0-9_]+", t) for t in listed)


def test_deleting_the_org_removes_every_new_tables_rows(pg_url):
    """Not the list — the DELETE. Rows in all twelve tables, then the erasure the route runs,
    then a count. A CASCADE that was declared and never exercised is a promise, not a fact."""
    from sqlalchemy import text

    from genios_engine.api import account_routes
    from genios_engine.platform.db import get_engine

    org = "org_wiring_erase"
    _seed_org(pg_url, org)
    engine = get_engine(pg_url)
    with engine.begin() as c:
        for table in NEW_L1_TABLES:
            _seed_one_row(c, table, org)
        for table in NEW_L1_TABLES:
            n = c.execute(text(f"select count(*) from {table} where org_id = :o"),
                          {"o": org}).scalar()
            assert n == 1, f"{table} was not seeded, so its deletion proves nothing"

        # The route's own erasure, run against the row it locks.
        account_routes._wipe(c, org)
        c.execute(text("delete from orgs where id = :o"), {"o": org})

    survivors = {}
    with engine.connect() as c:
        for table in NEW_L1_TABLES:
            n = c.execute(text(f"select count(*) from {table} where org_id = :o"),
                          {"o": org}).scalar()
            if n:
                survivors[table] = n
    assert not survivors, f"a deleted tenant's rows survived in: {survivors}"


#: The sentence a deletion must not leave behind, in the shape every evidence column holds.
_TENANT_SPAN = {"source_ref": "prepared_content:pc_erase",
                "quote": "their own confidential sentence",
                "start_offset": 0, "end_offset": 31, "verified": True}


def _seed_one_row(c, table: str, org: str) -> None:
    """One row in `table` for `org`, built from the LIVE schema rather than from a hand-written
    INSERT per table.

    Schema-driven on purpose: a hand-written fixture is a second copy of a DDL, and the day a
    migration adds a NOT NULL column the fixture breaks in a way that reads as "the erasure
    test is flaky" rather than "this table changed". Introspecting means this probe keeps
    covering the table through its next four migrations with no edit.
    """
    from sqlalchemy import text
    rows = c.execute(text(
        "select column_name, data_type from information_schema.columns "
        "where table_schema = 'public' and table_name = :t and is_nullable = 'NO' "
        "and column_default is null order by ordinal_position"), {"t": table}).all()
    assert rows, f"{table} does not exist — a name in the erasure list that is not a table "\
                 "breaks EVERY deletion"

    #: Columns a CHECK constrains — a closed vocabulary, a range, or a relation between two
    #: columns. Named here because these are the only places a generic value cannot be right:
    #: everything else is free text the tenant owns, which is the point of the probe.
    known = {"signal_type": "contract_renewal", "org_id": org,
             "resolution": "resolved_by_authority", "outcome": "reject",
             "state": "active", "span_verdict": "verified",
             "proposed_kind": "other", "proposed_kind_raw": "other",
             "start_offset": 0, "end_offset": 10,          # check (end_offset > start_offset)
             "importance_bp": 1000, "floor_bp": 3000,      # check (importance_bp < floor_bp)
             "confidence_bp": 8000, "authority_rank": 4,   # 0..10000 and ALG-14's 0..6
             "to_bp": 3000, "from_bp": 2000,
             # `check (jsonb_array_length(evidence_refs) > 0)` — a claim with no receipt is a
             # guess, at the database level too. The quote is the tenant's, which is exactly
             # what a deletion that skipped this table would leave behind.
             "evidence_refs": json.dumps([_TENANT_SPAN]),
             "claims": json.dumps([{"value": "their own number", "authority": "signed_document",
                                    "authority_rank": 6, "evidence": [_TENANT_SPAN]}])}
    values: dict[str, object] = {}
    for name, kind in rows:
        if name in known:
            values[name] = known[name]
        elif kind == "jsonb":
            # `[]` rather than `{}`: several of these columns carry a CHECK on
            # `jsonb_array_length`, which errors on an object rather than failing the check.
            values[name] = "[]"
        elif kind in ("integer", "bigint", "smallint"):
            values[name] = 1
        elif kind.startswith("timestamp"):
            values[name] = None            # rendered as now() below
        else:
            # Recognisably THE TENANT'S: what survives here is what a deletion would leak.
            values[name] = f"their-own-{name}"

    cols = ", ".join(values)
    binds = ", ".join(
        "now()" if v is None else
        (f"cast(:{n} as jsonb)" if isinstance(v, str) and v.startswith("{") else f":{n}")
        for n, v in values.items())
    params = {n: v for n, v in values.items() if v is not None}
    c.execute(text(f"insert into {table} ({cols}) values ({binds})"), params)


# ────────────────────────────────────────────────────────────────────────────────────────────
# ALG-03 is the AUTHORITY for `ball_in_court`, not a comment claiming to follow it
# ────────────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("actor,expected", [
    ("buyer@acme.com", "us"),      # they spoke last → we owe the reply
    (OWNER, "them"),               # we spoke last → their turn
])
def test_ball_in_court_on_the_capture_path_is_alg03s_own_answer(actor, expected):
    """`_thread_context` used to re-implement ALG-03's rule beside a comment promising it
    "follows `reconstruct_thread`'s rule exactly" — a promise no test could hold, because
    `reconstruct_thread` had no caller anywhere in the engine. The module that OWNS the rule
    could be re-tuned with every unit test green while the copy kept the old answer."""
    from genios_engine.capture.structural.threads import ThreadMessage, reconstruct_thread

    res = _capture(_email("Where are we on the renewal?", actor_email=actor),
                   esqe=P.EsqeStage(eval_time=NOW))

    thread = res.esqe.thread
    assert thread.ball_in_court == expected

    # …and it is the SAME answer ALG-03 gives for the same message, computed independently here.
    alg03 = reconstruct_thread(
        [ThreadMessage(message_id=res.event.event_id, occurred_at=res.event.occurred_at,
                       actor_email=actor)],
        org_identities=(OWNER,)).ball_in_court
    assert thread.ball_in_court == alg03.value


def test_an_internal_event_keeps_unknown_rather_than_being_put_to_alg03():
    """`internal` is a fact about the SOURCE, not about who sent a message to whom, and ALG-03
    has no word for it. Routing it through anyway would make every internal note read as one
    party owing the other."""
    res = _capture(_email("Note to self about the renewal.",
                          source="human", object_type="human_note", actor_email=OWNER),
                   esqe=P.EsqeStage(eval_time=NOW))

    assert res.esqe.thread.direction == "internal"
    assert res.esqe.thread.ball_in_court == "unknown"


# ────────────────────────────────────────────────────────────────────────────────────────────
# L1.4.6-U1 · the binder's own rate, on the trace beside the span rate
# ────────────────────────────────────────────────────────────────────────────────────────────

def test_the_no_evidence_rate_reaches_the_trace(fake_llm):
    """The two rates fail differently and both matter: the SPAN rate says the model cited text
    that is not in the message, this one says it made claims it cited nothing at all for. A
    prompt edit can hold one flat while wrecking the other, and `no_evidence_rate_bp` had no
    caller because `ExtractionDiagnostics` was never read on a request path."""
    quote = "We will move forward with the annual contract"
    body = f"{quote} once legal signs off."

    def _cite(text: str, q: str):
        start = text.index(q)
        return [{"quote": q, "start_offset": start, "end_offset": start + len(q)}]

    llm = fake_llm({
        "intent": "commit", "stance": "positive",
        # One claim WITH a recoverable receipt, one citing a sentence that is not in the message
        # — so the binder has both a `carried_own_evidence` and a `no_evidence` to count.
        "commitments": [
            {"actor": "us", "action": "move forward with the contract", "beneficiary": None,
             "is_conditional": False, "condition_text": None,
             "evidence": _cite(body, quote), "confidence_bp": 9000},
            {"actor": "us", "action": "a promise nobody made", "beneficiary": None,
             "is_conditional": False, "condition_text": None,
             "evidence": [{"quote": "this sentence does not appear anywhere",
                           "start_offset": 0, "end_offset": 37}],
             "confidence_bp": 9000},
        ]})
    res = _capture(_email(body), semantic=P.SemanticLane(llm=llm, eval_time=NOW))

    rec = [r for r in res.trace.records if r.stage == "s2_semantic_extraction"][-1]
    detail = rec.detail
    for key in ("claims_in", "no_evidence_drops", "no_evidence_rate_bp", "no_evidence_over_bar",
                "unverified_rate_bp"):
        assert key in detail, f"the trace does not carry {key} — the rate is uncomputable"
    assert isinstance(detail["no_evidence_rate_bp"], int), "a rate in a score path must be integer"
    assert 0 <= detail["no_evidence_rate_bp"] <= 10000
    # The release bar is EVALUATED where the number is produced, not left for a reader to
    # re-derive the threshold. One event is not a sustained rise, so this is a flag, not a gate.
    assert isinstance(detail["no_evidence_over_bar"], bool)
    assert res.outcome == "emitted", "a rate is a measurement; it must never drop mail"
