"""One door: human notes, agent actions and upload chunks become SourceEvents through
the SAME capture pipeline as a connector sync — deduped, traced, never noise-dropped."""
from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture.intake import (ingest_agent_event, ingest_human_event,
                                          ingest_manual)
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.payload_store import InMemoryRawPayloadStore
from genios_engine.capture.prepared_store import InMemoryPreparedContentStore
from genios_engine.contracts.events import AgentEvent, HumanEvent

T = datetime(2026, 8, 1, 12, 0, tzinfo=timezone.utc)


def _stores():
    return (InMemorySourceEventRepository(), InMemoryRawPayloadStore(),
            InMemoryPreparedContentStore())


def test_human_event_lands_as_source_event():
    repo, pay, prep = _stores()
    ev = HumanEvent(type="human.manual_context", org_id="o1", actor_id="rohit",
                    detail={"text": "Chat360 ka procurement slow hai, Priya CFO hai."},
                    occurred_at=T)
    res = ingest_human_event(ev, repo=repo, payload_store=pay, prepared_store=prep)
    assert res.outcome == "emitted"
    assert res.event.source == "human"
    assert res.event.source_family == "human_input"
    # the note's text is in the prepared seam for L2
    assert "procurement" in prep.get_text(org_id="o1", event_id=res.event.event_id)


def test_agent_event_lands_and_dedups_on_idempotency_key():
    repo, pay, prep = _stores()
    ev = AgentEvent(org_id="o1", agent_id="sdr-1", client_event_id="c-42",
                    action_taken="email_sent", target_hint={"email": "priya@chat360.io"},
                    result="sent", occurred_at=T)
    first = ingest_agent_event(ev, repo=repo, payload_store=pay, prepared_store=prep)
    second = ingest_agent_event(ev, repo=repo, payload_store=pay, prepared_store=prep)
    assert first.outcome == "emitted"
    assert first.event.source_family == "ai_generated"
    assert second.outcome == "duplicate"             # same idempotency key → one event


def test_upload_chunk_shape_and_dedup():
    repo, pay, prep = _stores()
    kw = dict(org_id="o1", source="upload", object_type="document_chunk",
              source_object_id="up_9:chunk_0", body="Pricing SOP: never discount early.",
              subject="sop.pdf", repo=repo, payload_store=pay, prepared_store=prep,
              connection_id="upload")
    first = ingest_manual(**kw)
    second = ingest_manual(**kw)
    assert first.outcome == "emitted"
    assert first.event.dedup_key == "upload:document_chunk:up_9:chunk_0"
    assert second.outcome == "duplicate"
    assert "discount" in prep.get_text(org_id="o1", event_id=first.event.event_id)


def test_short_human_note_is_not_noise_dropped():
    """'fyi' from a connector inbox would N-10 drop; from a human it must land (W-05)."""
    repo, pay, prep = _stores()
    ev = HumanEvent(type="human.manual_context", org_id="o1", actor_id="r",
                    detail={"text": "fyi"}, occurred_at=T)
    res = ingest_human_event(ev, repo=repo, payload_store=pay, prepared_store=prep)
    assert res.outcome == "emitted"
