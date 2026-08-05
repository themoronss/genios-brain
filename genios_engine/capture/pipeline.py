from __future__ import annotations

import json
from dataclasses import dataclass

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.documents.native import extract_native_text
from genios_engine.capture.domain.hints import domain_hints
from genios_engine.capture.gate.context import GateContext, GateResult
from genios_engine.capture.gate.gate import run_gate
from genios_engine.capture.gate.relevance import RelevanceClassifier
from genios_engine.capture.documents.store import DocumentJobStore
from genios_engine.capture.landing.normalize import to_source_event
from genios_engine.capture.landing.repository import SourceEventRepository
from genios_engine.capture.payload_store import RawPayloadStore
from genios_engine.capture.preprocess.preprocess import preprocess
from genios_engine.capture.structured.apply import apply_mapping
from genios_engine.capture.structured.registry import get_mapping, has_mapping
from genios_engine.capture.trace_store import TraceRepository
from genios_engine.capture.triage.triage import triage_lane
from genios_engine.contracts.gated_event import GatedEvent
from genios_engine.contracts.prepared_content import PreparedContent
from genios_engine.contracts.source_event import SourceEvent, SyncMode
from genios_engine.contracts.trace import EventTrace
from genios_engine.platform.ids import new_id


# ----------------------------------------------------------------------------------
# Step 1 — landing (dedup). Kept standalone so it is independently testable.
# ----------------------------------------------------------------------------------
@dataclass
class LandingResult:
    event: SourceEvent
    trace: EventTrace
    landed: bool


def land_raw_object(raw: RawObject, *, org_id: str, connection_id: str,
                    repo: SourceEventRepository,
                    sync_mode: SyncMode = SyncMode.incremental,
                    trace: EventTrace | None = None) -> LandingResult:
    """Normalize + dedup check ONLY. Writing is deferred to after the gate so the
    ledger records the decision (and content is stored kept-only). `landed` here
    means "new" (not already seen), not "written"."""
    event = to_source_event(raw, org_id=org_id, connection_id=connection_id,
                            sync_mode=sync_mode)
    trace = trace or EventTrace(org_id=org_id, event_id=event.event_id,
                                dedup_key=event.dedup_key, source=event.source)
    if repo.exists(org_id, event.dedup_key):
        trace.record("landing", "drop", reason_code="duplicate", dedup_key=event.dedup_key)
        return LandingResult(event=event, trace=trace, landed=False)
    trace.record("landing", "pass", object_type=event.object_type)
    return LandingResult(event=event, trace=trace, landed=True)


# ----------------------------------------------------------------------------------
# Full L1 capture: raw → land → preprocess → gate → triage → gated_event, one trace.
# ----------------------------------------------------------------------------------
@dataclass
class CaptureResult:
    event: SourceEvent
    trace: EventTrace
    outcome: str                    # emitted | duplicate | dropped | park
    gated: GatedEvent | None


_FREE_MAIL = ("gmail.com", "googlemail.com", "outlook.com", "hotmail.com",
              "yahoo.com", "yahoo.co.in", "icloud.com", "proton.me")


def _linkage_hints(event: SourceEvent) -> list[dict]:
    """S3 — cheap deterministic entity hints for L2 (hints only; L2 decides identity).
    Company domain from the sender, and thread linkage from the parent object."""
    hints: list[dict] = []
    email = (event.actor.email or "").lower()
    if "@" in email:
        domain = email.split("@")[-1]
        if domain and domain not in _FREE_MAIL:
            hints.append({"type": "company_domain", "value": domain, "from": "sender"})
    if event.parent_object_id:
        hints.append({"type": "thread", "value": event.parent_object_id})
    return hints


def _build_gated_event(event: SourceEvent, prepared: PreparedContent | None,
                       gate: GateResult, lane: str, structured_fields: dict,
                       hints: list[dict], links: list[dict]) -> GatedEvent:
    return GatedEvent(
        event_id=event.event_id,
        org_id=event.org_id,
        source=event.source,
        object_type=event.object_type,
        occurred_at=event.occurred_at,
        payload_ref=event.payload_ref,
        prepared_content_ref=prepared.prepared_content_id if prepared else None,
        route=gate.route or "needs_extraction",
        structured_fields=structured_fields,
        domain_hints=hints,
        linkage_hints=links,
        triage_lane=lane,
        versions={
            "preprocessor": prepared.preprocessor_version if prepared else None,
            "gate_rules": "gate-1",
        },
    )


def _finish(event: SourceEvent, trace: EventTrace, outcome: str,
            gated: GatedEvent | None, trace_repo: TraceRepository | None) -> CaptureResult:
    """Single exit: persist the decision trace (all outcomes) and return the result."""
    if trace_repo is not None:
        trace_repo.save(trace)
    return CaptureResult(event=event, trace=trace, outcome=outcome, gated=gated)


def capture_event(raw: RawObject, *, org_id: str, connection_id: str,
                  repo: SourceEventRepository,
                  sender_known: bool = False, is_structured: bool = False,
                  structured_fields: dict | None = None, in_scope: bool = True,
                  mask_phone: bool = False,
                  relevance: RelevanceClassifier | None = None,
                  trace_repo: TraceRepository | None = None,
                  payload_store: RawPayloadStore | None = None,
                  prepared_store=None,
                  document_job_store: DocumentJobStore | None = None,
                  sync_mode: SyncMode = SyncMode.incremental) -> CaptureResult:
    """The L1 pipeline for one raw object, fully traced. Terminal outcomes:
    duplicate (landing), dropped/park (gate), or emitted (gated_event → L2).

    Everything L1 computes is PERSISTED at the seam: the decision (route/lane/hints)
    lands on the source_events row and the PII-masked prepared text (+offset map) in
    prepared_content — so L2 reads the seam instead of re-deriving it, and evidence
    can trace back to exact source characters."""
    structured_fields = structured_fields or {}

    landing = land_raw_object(raw, org_id=org_id, connection_id=connection_id,
                              repo=repo, sync_mode=sync_mode)
    trace, event = landing.trace, landing.event
    if not landing.landed:
        return _finish(event, trace, "duplicate", None, trace_repo)

    # auto-detect structured sources (CRM/calendar/DB): a registry mapping means the
    # object is typed → structured route (gate short-circuit), no LLM extraction.
    if not is_structured and has_mapping(event.source, event.object_type):
        is_structured = True

    # preprocess (unstructured text only; structured events carry typed fields).
    # HTML is stripped HERE (heavy at ingestion): the gate's OOO/empty checks and the
    # persisted seam text both want prose, and L2 used to re-strip it per event.
    # Offset map note: src coordinates refer to the stripped text, not raw HTML bytes.
    prepared: PreparedContent | None = None
    if not is_structured:
        source_text = raw.raw.get("body") or raw.raw.get("snippet") or ""
        stripped = extract_native_text(mime="text/html", data=source_text) or source_text
        prepared = preprocess(stripped, event_id=event.event_id, mask_phone=mask_phone)
        trace.record("preprocess", "pass", language=prepared.language,
                     masked=len(prepared.masked_spans),
                     protected=len(prepared.protected_spans))

    ctx = GateContext(event=event, prepared=prepared, raw=raw.raw,
                      is_structured=is_structured, structured_fields=structured_fields,
                      sender_known=sender_known, in_scope=in_scope)
    gate = run_gate(ctx, trace, relevance=relevance)

    # Decision-first ledger: write the lightweight source_events row (metadata + the
    # decision) AFTER the gate, for every new object — this is the dedup + audit ledger
    # ("already fetched?" check reads it).
    outcome = {"drop": "dropped", "park": "parked"}.get(gate.action, "emitted")
    kept = outcome in ("emitted", "parked")

    # The seam, computed ONCE for kept events (dropped noise gets only the ledger row):
    # deterministic hints persisted WITH the decision so L2 and any replay read them
    # instead of recomputing. The triage lane is the L2 DRAIN order, so it exists only
    # for emitted events — a parked event's terminal trace record stays the gate's
    # park decision (recovery re-emits and the drain treats lane-less as P3).
    hints: list[dict] = []
    links: list[dict] = []
    lane: str | None = None
    if kept:
        text = prepared.clean_text if prepared else None
        hints = domain_hints(event.source, text)
        links = _linkage_hints(event)
    if gate.action not in ("drop", "park"):
        lane = triage_lane(ctx, prepared)
        trace.record("triage", "pass", lane=lane)

    # KEPT content: stash the raw body (encrypted, short TTL) for EMITTED and PARKED events.
    # Parked = a human-review queue (grey-zone), so it MUST keep content to be recoverable — was
    # a bug: parked stored no payload, dedup blocked re-fetch, /recover was a no-op → black hole.
    # Dropped noise still gets NO content — only the ledger row (L1 stays a filter, not a warehouse).
    if kept and payload_store is not None:
        event.payload_ref = new_id("pay")
    repo.add(event, outcome=outcome, route=gate.route, triage_lane=lane,
             domain_hints=hints or None, linkage_hints=links or None)
    if kept and payload_store is not None:
        # full raw object → L2 reads body (unstructured) or maps fields (structured); a recovered
        # parked event flips to 'emitted' and L2 reads this same payload.
        payload_store.put(payload_id=event.payload_ref, org_id=org_id,
                          event_id=event.event_id, content=json.dumps(raw.raw, default=str))
    if kept and prepared is not None and prepared_store is not None:
        # the PII-masked, replayable form + offset map — retained longer than the raw payload
        prepared_store.put(org_id=org_id, prepared=prepared)

    # document provenance (native vs OCR + status) for any file-type event
    doc = raw.raw.get("document")
    if doc and document_job_store is not None:
        document_job_store.put(org_id=org_id, event_id=event.event_id, doc=doc,
                               fmt=raw.raw.get("mime"))

    if gate.action in ("drop", "park"):
        return _finish(event, trace, outcome, None, trace_repo)

    # structured route: derive fields from the mapping registry (data-driven, no LLM)
    if is_structured and not structured_fields:
        mapping = get_mapping(event.source, event.object_type)
        if mapping:
            structured_fields = apply_mapping(mapping, raw.raw)

    gated = _build_gated_event(event, prepared, gate, lane or "P3", structured_fields,
                               hints, links)
    trace.record("emit", "emit", route=gated.route, lane=lane)
    return _finish(event, trace, "emitted", gated, trace_repo)
