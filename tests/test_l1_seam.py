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
    # v2 added source_family, v3 internal_kind, v4 visibility + the signal lifecycle. All
    # additive: an ordinary observed event carries no kind, defaults to the org-wide
    # audience, and is otherwise what v2 produced.
    assert res.event.schema_version == 4
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
