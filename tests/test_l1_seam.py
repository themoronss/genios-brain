"""The L1→L2 seam, persisted. L1's computed decisions (route, lane, hints) and the
PII-masked prepared text must SURVIVE capture — before this, they were computed and
thrown away, and L2 re-derived text itself (inverting heavy-at-ingestion)."""
from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.payload_store import InMemoryRawPayloadStore
from genios_engine.capture.pipeline import capture_event
from genios_engine.capture.prepared_store import InMemoryPreparedContentStore
from genios_engine.capture.source_families import family_of


def _raw(oid="m1", body="Hi, can we meet Friday about the proposal? Call me at urgent.",
         source="gmail", object_type="email", **raw_extra):
    raw = {"body": body, "subject": "proposal", "headers": {}, **raw_extra}
    return RawObject(source=source, object_type=object_type, source_object_id=oid,
                     occurred_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
                     actor_type="external_contact", actor_email="priya@chat360.io",
                     raw=raw)


def _capture(raw, **kw):
    repo = InMemorySourceEventRepository()
    prepared = InMemoryPreparedContentStore()
    payloads = InMemoryRawPayloadStore()
    res = capture_event(raw, org_id="org_a", connection_id="c1", repo=repo,
                        payload_store=payloads, prepared_store=prepared, **kw)
    return res, repo, prepared


def test_emitted_event_persists_route_lane_and_hints():
    res, repo, _ = _capture(_raw())
    assert res.outcome == "emitted"
    dec = repo._decision[("org_a", res.event.dedup_key)]
    assert dec["route"] == "needs_extraction"
    assert dec["triage_lane"] in ("P0", "P1", "P2", "P3")
    assert any(h["type"] == "company_domain" and h["value"] == "chat360.io"
               for h in (dec["linkage_hints"] or []))


def test_prepared_text_is_persisted_for_kept_events():
    res, _, prepared = _capture(_raw())
    text = prepared.get_text(org_id="org_a", event_id=res.event.event_id)
    assert text and "proposal" in text
    # and it is org-scoped
    assert prepared.get_text(org_id="org_b", event_id=res.event.event_id) is None


def test_dropped_noise_persists_no_content():
    res, repo, prepared = _capture(_raw(oid="m2", raw_extra=None,
                                        body="x", labelIds=["SPAM"]))
    assert res.outcome == "dropped"
    assert prepared.rows == {}                       # ledger row only, no content
    dec = repo._decision[("org_a", res.event.dedup_key)]
    assert dec["triage_lane"] is None                # lane is for emitted events only


def test_html_is_stripped_at_ingestion():
    res, _, prepared = _capture(_raw(oid="m3",
        body="<html><body><p>Hello <b>Priya</b>, see the <a href='x'>doc</a></p></body></html>"))
    text = prepared.get_text(org_id="org_a", event_id=res.event.event_id)
    assert "<" not in text and "Hello" in text and "Priya" in text


def test_subject_line_pii_is_masked_in_prepared_text():
    """The subject is part of the prose and is masked WITH the body. (Regression: the
    seam once persisted body-only prepared text and L2 prepended the RAW subject —
    unmasked subject-line PII reached the LLM.)"""
    res, _, prepared = _capture(_raw(
        oid="m-pii", body="details attached",
        subject="Re: KYC — Aadhaar 1234 5678 9012"))
    text = prepared.get_text(org_id="org_a", event_id=res.event.event_id)
    assert "1234 5678 9012" not in text          # masked
    assert "KYC" in text                          # subject prose survives
    assert "details attached" in text             # body present too


def test_source_family_stamped_on_envelope():
    res, _, _ = _capture(_raw(oid="m4"))
    assert res.event.source_family == "communication"
    # v2 added source_family, v3 added internal_kind. Both additive: an ordinary observed
    # event carries no kind and is otherwise byte-identical to what v2 produced.
    # v4 adds `recipients` — additive, so every earlier consumer still reads the envelope. The
    # assertion tracks the contract rather than pinning a number, or it fails on every additive
    # change and teaches people to bump it without reading why.
    from genios_engine.contracts.source_event import SourceEvent
    assert res.event.schema_version == SourceEvent.model_fields["schema_version"].default
    assert res.event.schema_version >= 3, "the envelope must never lose a field"
    assert res.event.internal_kind is None
    assert family_of("notion") == "knowledge"
    assert family_of("human") == "human_input"
    assert family_of("agent") == "ai_generated"
    assert family_of("weird_new_thing") == "unclassified"


def test_deliberate_sources_bypass_noise_gate():
    """A human note / upload / agent event must never be N-code dropped — the noise
    gate exists for inbox firehoses, not for material someone deliberately handed us."""
    for source, otype in (("human", "note"), ("upload", "document_chunk"), ("agent", "action")):
        raw = _raw(oid=f"d-{source}", source=source, object_type=otype,
                   body="fyi")                        # short body: would N-10 without W-05
        raw.raw["headers"] = {"Precedence": "bulk"}   # would N-04 without W-05
        res, repo, _ = _capture(raw)
        assert res.outcome == "emitted", f"{source} was {res.outcome}"


def test_recipients_survive_the_payload_ttl():
    """Participants are first-class on the envelope, not only inside the expiring blob.

    To/Cc lived exclusively in the encrypted `raw_payloads` row, which carries a 30-day TTL — so
    the design partner's backfilled correspondence would have lost its recipient data on
    2026-09-16, after which even best-effort reconstruction is impossible. This is the rare
    defect with a date attached.

    It is not only retention. One sender per event cannot say who a conversation is WITH: a
    mediated introduction, a message copied to nine people and a direct reply are the same shape
    to every layer above, which is how a card comes to target an introducer as the counterparty.
    """
    from genios_engine.capture.connectors.base import RawObject
    from genios_engine.capture.landing.normalize import to_source_event
    from datetime import datetime, timezone

    raw = RawObject(
        source="gmail", object_type="email_message", source_object_id="m1",
        occurred_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        actor_email="partner@vc.com",
        recipients=("founder@startup.com", "analyst@vc.com"))
    event = to_source_event(raw, org_id="o", connection_id="c")

    assert event.recipients == ("founder@startup.com", "analyst@vc.com")
    assert event.schema_version >= 4, "recipients arrived in envelope v4"


def test_an_event_with_no_recipients_is_empty_not_missing():
    """Empty and unknown are different facts, and the column keeps them different.

    An empty tuple means "we looked and there were none"; NULL in the table means "captured
    before the column existed". Collapsing them would make the backfill unmeasurable.
    """
    from genios_engine.capture.connectors.base import RawObject
    from genios_engine.capture.landing.normalize import to_source_event
    from datetime import datetime, timezone

    event = to_source_event(
        RawObject(source="gcal", object_type="calendar_event", source_object_id="e1",
                  occurred_at=datetime(2026, 8, 1, tzinfo=timezone.utc)),
        org_id="o", connection_id="c")
    assert event.recipients == ()


def test_an_unregistered_domain_is_not_reported_as_covered():
    """"No requirements" satisfied the readiness test trivially.

    Ask for coverage on `fundraising` — this org's actual domain — and the answer was "ready"
    with nothing connected. Every negative inference downstream ("they did not reply", "no
    meeting was booked") then looks licensed, when in truth we had never established what a
    complete picture for that domain even is.
    """
    from genios_engine.capture.coverage.model import compute_coverage

    unknown = compute_coverage(domain="astrology", connected={}, company_knowledge_count=0)
    assert unknown["coverage_ready"] is False
    assert unknown["coverage_state"] == "unknown_domain"
    assert unknown["reason"], "failing closed silently is the same bug in a different direction"
    assert not any(v for k, v in unknown["readiness"].items() if k != "has_company_canon"), (
        "an unassessed domain grants no readiness permissions")


def test_a_fundraising_tenant_can_actually_be_complete():
    """Failing closed must not mean permanently incomplete.

    A founder raising money has no CRM and does not need one — the pipeline lives in the inbox
    and the calendar. Requiring `crm` (as sales does) would report a correctly connected
    fundraising tenant as never ready, which is the same failure pointed the other way.
    """
    from genios_engine.capture.coverage.model import compute_coverage

    assert compute_coverage(domain="fundraising", connected={"communication": "fresh"},
                            company_knowledge_count=0)["coverage_ready"] is True


def test_coverage_ready_is_written_onto_the_gated_event():
    """The field was declared on the contract and never assigned by its only constructor.

    So the one seam that could tell L2 "a negative inference about this domain is licensed"
    carried nothing, permanently. A dead field is worse than a missing one: it invites a
    consumer to trust a seam that says nothing, and None reads as "unknown" exactly where a
    caller most wants a yes.
    """
    import inspect

    from genios_engine.capture import pipeline

    src = inspect.getsource(pipeline._build_gated_event)
    assert "coverage_ready=coverage_ready" in src
