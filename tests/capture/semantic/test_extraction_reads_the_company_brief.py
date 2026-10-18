"""STEP-07 · extraction reads the mail through the company brief — and a tenant without one is read as before.

    pytest tests/capture/semantic/test_extraction_reads_the_company_brief.py -q

Tree `yc2_w27_s07 · M25.C5.L-logic.V2.U01`. The reader extracted every mail with no idea whose company it
was reading for (`speedrun008/YC-II W27/` STEP-07 §8.1). The brief's block now rides in the envelope —
the one slot above the fence and AFTER the cached prefix — so: the model reads it before the mail; the
fixed instructions stay one cacheable prefix; the extraction cache key moves with the brief's version
(it hashes the envelope) and with nothing else; and a tenant with no brief is asked byte for byte what
it was asked before. The lane carries the block, read once when the lane is built.
"""
from __future__ import annotations

from datetime import datetime, timezone

from genios_engine.capture import pipeline as P
from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.semantic import extractor as ex
from genios_engine.capture.semantic.profiles import ENVELOPE_MARKER
from genios_engine.contracts.company_brief import CompanyBriefLine, compose
from genios_engine.contracts.prepared_content import PreparedContent
from genios_engine.contracts.source_event import Actor, SourceEvent

T = datetime(2026, 9, 24, 5, 20, tzinfo=timezone.utc)
NONCE = "deadbeefcafe0001"
TEXT = "Your application SSR-2026-48213 has moved to the stage: Under Examination."
BRIEF = compose(org_id="o", company="Nimbus Labs", founder="Arjun Rao", us=("arjun@nimbuslabs.test",),
                lines=[CompanyBriefLine(line_id="l1", section="in_motion",
                                        text="Compliance — StartupSetu recognition, application live")])


def _request(**over):
    kwargs = dict(org_id="o", event_id="evt_1", source="gmail", profile_id="email", tier="T2",
                  prepared=PreparedContent(prepared_content_id="pc_1", event_id="evt_1",
                                           clean_text=TEXT, language="en"),
                  envelope=ex.EventEnvelope(direction="inbound",
                                            sender="StartupSetu <updates@startupsetu.gov.test>",
                                            recipients=("arjun@nimbuslabs.test",),
                                            subject="Application status"),
                  eval_time=T, timezone="UTC", locale="en_US")
    kwargs.update(over)
    return ex.ExtractionRequest(**kwargs)


def test_the_block_sits_after_the_cached_prefix_and_before_the_mail():
    call = ex.assemble_call(_request(company_brief=BRIEF.prompt_block()), nonce=NONCE)
    prompt = call.prompt
    marker = prompt.index(ENVELOPE_MARKER)
    block = prompt.index("COMPANY BRIEF " + BRIEF.version)
    assert marker < block < prompt.index(TEXT)
    assert "StartupSetu recognition" in call.envelope


def test_no_brief_asks_exactly_what_was_asked_before():
    plain = ex.assemble_call(_request(), nonce=NONCE)
    empty = ex.assemble_call(_request(company_brief=""), nonce=NONCE)
    assert plain.prompt == empty.prompt and "COMPANY BRIEF" not in plain.prompt
    assert plain.envelope == empty.envelope


def test_the_cache_moves_with_the_brief_and_only_with_it():
    plain = ex.assemble_call(_request(), nonce=NONCE)
    one = ex.assemble_call(_request(company_brief=BRIEF.prompt_block()), nonce=NONCE)
    other = compose(org_id="o", company="Nimbus Labs", founder="Arjun Rao", us=(),
                    lines=[CompanyBriefLine(line_id="l2", section="goals", text="raise the pre-seed")])
    two = ex.assemble_call(_request(company_brief=other.prompt_block()), nonce=NONCE)
    assert len({plain.envelope, one.envelope, two.envelope}) == 3
    assert one.prompt_version == plain.prompt_version, "the template did not change"


def test_the_lane_hands_its_brief_to_every_extraction(monkeypatch):
    seen = []

    def _extract(request, *, llm, store, open_lane):
        seen.append(request)
        raise RuntimeError("stop after the request is built")

    monkeypatch.setattr(P, "extract", _extract)
    lane = P.SemanticLane(llm=object(), eval_time=T, company_brief=BRIEF.prompt_block())
    event = SourceEvent(event_id="evt_1", org_id="o", connection_id="c", source="gmail",
                        object_type="email_message", source_object_id="m1",
                        dedup_key="gmail:email_message:m1",
                        actor=Actor(type="external_contact", email="updates@startupsetu.gov.test"),
                        occurred_at=T)
    raw = RawObject("gmail", "email_message", "m1", T, actor_email="updates@startupsetu.gov.test",
                    raw={"subject": "Application status", "snippet": TEXT})
    prepared = PreparedContent(prepared_content_id="pc_1", event_id="evt_1", clean_text=TEXT,
                               language="en")
    try:
        P.run_semantic_lane(event, prepared, raw, lane=lane, is_structured=False,
                            mailbox_owner="arjun@nimbuslabs.test")
    except RuntimeError:
        pass
    assert seen and seen[0].company_brief == BRIEF.prompt_block()
