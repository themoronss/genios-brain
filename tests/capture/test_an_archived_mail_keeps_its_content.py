"""STEP-03 · an archived mail keeps its content, carries its tier and its rule, and no model reads it.

    pytest tests/capture/test_an_archived_mail_keeps_its_content.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/capture/test_an_archived_mail_keeps_its_content.py -q

`capture/pipeline.capture_event` (tree `yc2_w27_s03/M21.C3.L-logic.V3.U03`). The gate ARCHIVES what a
noise rule or the model's confident junk verdict would have deleted (`capture/gate/gate.ARCHIVE`).
The pipeline lands it as outcome `archived`: the ledger row says `archive` and names the rule, the
encrypted payload is stored for 180 days (06 D4), and it stops before the semantic lane — the
extraction model is never called for it.

⛔ AND NO PREPARED TEXT — corrected by measurement. The first version stored it, and STEP-03's
golden acceptance caught the resolution model reading an archived introduction on F37: every
reader of a message's words selects by correlation membership, a reading makes every thread event
a member whatever its outcome, and a dropped mail had been skipped only because it had no prepared
text. An archive keeps its payload; the text is re-derived at promotion (STEP-05).

Beside it: the emitted payload TTL goes from 30 days to 180, because `_pull` inner-joins
`raw_payloads` and a 30-day body stranded any event not drained within a month; a parked mail
keeps its 365; a gate verb the pipeline does not know is refused, never emitted.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, text

from genios_engine.capture import pipeline as P
from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.gate.context import GateResult
from genios_engine.capture.gate.relevance import RelevanceVerdict
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.prepared_store import InMemoryPreparedContentStore

ORG = "archived_content_org"
AT = datetime(2026, 10, 6, 9, tzinfo=timezone.utc)

BOARDY = {"subject": "Intro: Pankaj (angel, fintech) <> you",
          "body": "Hi! Pankaj backs early fintech founders and asked to meet you. Reply to connect.",
          "headers": {"List-Unsubscribe": "<mailto:unsub@boardy.test>"}}


def _mail(raw: dict, oid: str = "m1", email: str = "intros@boardy.test") -> RawObject:
    return RawObject(source="gmail", object_type="email_message", source_object_id=oid,
                     occurred_at=AT, actor_email=email, actor_type="external_contact",
                     raw=dict(raw))


class _Payloads:
    """Records what was stored and for how long."""

    def __init__(self) -> None:
        self.rows: dict[str, dict] = {}

    def put(self, *, payload_id, org_id, event_id, content, content_type="application/json",
            ttl_days=30):
        self.rows[payload_id] = {"event_id": event_id, "content": content, "ttl_days": ttl_days}


class _NoModel:
    """The extraction model. Any contact is the failure this file exists to catch."""

    def __getattr__(self, name):
        raise AssertionError(f"an archived mail reached the extraction model ({name})")


class _Junk:
    def classify(self, ctx, prepared):
        return RelevanceVerdict(False, 0.05, disposition="drop", reason="automated matchmaking")


def _capture(raw: RawObject, **kw):
    repo, payloads, prepared = (InMemorySourceEventRepository(), _Payloads(),
                                InMemoryPreparedContentStore())
    res = P.capture_event(raw, org_id=ORG, connection_id="conn_gmail", repo=repo,
                          payload_store=payloads, prepared_store=prepared, **kw)
    decision = repo._decision.get((ORG, res.event.dedup_key))
    return res, repo, payloads, prepared, decision


def _no_model_lane():
    return P.SemanticLane(llm=_NoModel(), eval_time=AT)


# ── archived ────────────────────────────────────────────────────────────────────────────────────

def test_a_rule_archived_mail_keeps_its_payload_and_no_text_a_reader_can_reach():
    res, repo, payloads, prepared, decision = _capture(_mail(BOARDY), semantic=_no_model_lane())
    assert res.outcome == "archived"
    assert repo._outcome[(ORG, res.event.dedup_key)] == "archived"
    assert (decision["attention"], decision["attention_reason"]) == ("archive", "N-02")
    stored = payloads.rows[res.event.payload_ref]
    assert "Pankaj" in stored["content"] and stored["ttl_days"] == P.ARCHIVED_PAYLOAD_TTL_DAYS == 180
    assert prepared.get_text(org_id=ORG, event_id=res.event.event_id) is None, (
        "an archived mail's prepared text is what the resolution model, the BSO and the card "
        "builder read by correlation membership — F37")


def test_an_archived_mail_is_read_by_no_model_and_is_not_published():
    res, _, _, _, decision = _capture(_mail(BOARDY), semantic=_no_model_lane())
    assert res.gated is None and res.extraction is None and res.esqe is None
    assert decision["triage_lane"] is None, "the triage lane is the drain order of emitted mail"
    assert [r.stage for r in res.trace.records if r.stage == "triage"] == []
    assert res.trace.records[-1].action.value == "archive"


def test_the_models_confident_junk_is_archived_with_its_code():
    res, _, payloads, prepared, decision = _capture(
        _mail({"subject": "Boardy here", "body": "Want me to find you more investors?"}, oid="m2"),
        relevance=_Junk(), semantic=_no_model_lane())
    assert res.outcome == "archived"
    assert (decision["attention"], decision["attention_reason"]) == ("archive", "llm_junk")
    assert payloads.rows[res.event.payload_ref]["ttl_days"] == P.ARCHIVED_PAYLOAD_TTL_DAYS
    assert prepared.get_text(org_id=ORG, event_id=res.event.event_id) is None


def test_an_empty_mail_is_archived_with_n10():
    res, _, payloads, _, decision = _capture(_mail({"subject": "", "body": ""}, oid="m3",
                                                   email="person@realco.test"))
    assert res.outcome == "archived" and decision["attention_reason"] == "N-10"
    assert res.event.payload_ref in payloads.rows


@pytest.mark.parametrize("raw, email, code", [
    ({**BOARDY, "headers": {}, "labelIds": ["CATEGORY_PROMOTIONS"]}, "updates@portal.test", "N-06"),
    ({**BOARDY, "headers": {}}, "no-reply@portal.test", "N-03"),
    ({**BOARDY, "headers": {}, "labelIds": ["SPAM"]}, "person@realco.test", "N-09"),
])
def test_every_noise_rule_lands_as_archived_with_its_rule(raw, email, code):
    res, _, payloads, _, decision = _capture(_mail(raw, oid=f"m_{code}", email=email))
    assert (res.outcome, decision["attention"], decision["attention_reason"]) == (
        "archived", "archive", code)
    assert res.event.payload_ref in payloads.rows


# ── what does not change, and what does ─────────────────────────────────────────────────────────

def test_an_emitted_mail_is_deep_and_keeps_its_body_for_180_days_not_30():
    res, _, payloads, prepared, decision = _capture(
        _mail({"subject": "Term sheet", "body": "Can we talk Friday about the round?"},
              oid="m4", email="priya@realvc.test"))
    assert res.outcome == "emitted"
    assert (decision["attention"], decision["attention_reason"]) == ("deep", "passed")
    assert payloads.rows[res.event.payload_ref]["ttl_days"] == P._EMITTED_PAYLOAD_TTL_DAYS == 180
    assert prepared.get_text(org_id=ORG, event_id=res.event.event_id), "a read mail keeps its text"


def test_a_parked_mail_is_deep_with_its_park_code_and_keeps_365_days():
    res, _, payloads, _, decision = _capture(
        _mail({"subject": "Deck", "body": "Attached.", "document": {"status": "fetch_failed"}},
              oid="m5", email="priya@realvc.test"))
    assert res.outcome == "parked"
    assert (decision["attention"], decision["attention_reason"]) == ("deep", "DOC-05")
    assert payloads.rows[res.event.payload_ref]["ttl_days"] == P._PARKED_PAYLOAD_TTL_DAYS == 365


def test_an_out_of_scope_object_is_still_dropped_with_nothing_kept():
    res, _, payloads, prepared, decision = _capture(_mail(BOARDY, oid="m6"), in_scope=False)
    assert res.outcome == "dropped"
    assert (decision["attention"], decision["attention_reason"]) == (None, None)
    assert payloads.rows == {} and prepared.rows == {}


def test_a_gate_verb_the_pipeline_does_not_know_is_refused_not_emitted(monkeypatch):
    """⛔ Found building this unit: the pipeline mapped every verb it did not know to `emitted`,
    so the gate's new `archive` published a Boardy nudge as founder mail until the pipeline learned
    the word. A verb with no outcome now raises — the sweep quarantines the object, loudly."""
    monkeypatch.setattr(P, "run_gate", lambda ctx, trace, relevance=None: GateResult(
        action="later", reason_code="X-01"))
    with pytest.raises(ValueError, match="later"):
        _capture(_mail(BOARDY, oid="m7"))


# ── Postgres ────────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def pg():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
    eng = create_engine(url)
    with eng.begin() as c:
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})
        c.execute(text("insert into orgs (id, name, email) values (:o, :o, 'ac@example.test')"),
                  {"o": ORG})
    yield url, eng
    with eng.begin() as c:
        c.execute(text("delete from event_trace where org_id = :o"), {"o": ORG})   # no org FK
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


@pytest.mark.pg
def test_on_postgres_an_archived_mail_is_a_row_and_a_payload_and_no_prepared_text(pg):
    from genios_engine.capture.landing.pg_repository import PostgresSourceEventRepository
    from genios_engine.capture.payload_store import PostgresRawPayloadStore
    from genios_engine.capture.prepared_store import PostgresPreparedContentStore
    from genios_engine.capture.trace_store import PostgresTraceRepository

    url, eng = pg
    res = P.capture_event(_mail(BOARDY, oid="pg1"), org_id=ORG, connection_id="conn_gmail",
                          repo=PostgresSourceEventRepository(url),
                          payload_store=PostgresRawPayloadStore(url, os.environ["GENIOS_CRYPTO_KEY"]),
                          prepared_store=PostgresPreparedContentStore(url),
                          trace_repo=PostgresTraceRepository(url),
                          semantic=_no_model_lane())
    assert res.outcome == "archived"
    with eng.connect() as c:
        row = c.execute(text(
            "select outcome, attention, attention_reason, payload_ref from source_events "
            "where org_id = :o and event_id = :e"), {"o": ORG, "e": res.event.event_id}).one()
        payload_expires = c.execute(text(
            "select expires_at from raw_payloads where org_id = :o and id = :p"),
            {"o": ORG, "p": row.payload_ref}).scalar()
        prepared_expires = c.execute(text(
            "select expires_at from prepared_content where org_id = :o and event_id = :e"),
            {"o": ORG, "e": res.event.event_id}).scalar()
        trace_s1 = c.execute(text(
            "select action, reason_code from event_trace where org_id = :o and event_id = :e "
            "and stage = 'S1'"), {"o": ORG, "e": res.event.event_id}).one()
    assert (row.outcome, row.attention, row.attention_reason) == ("archived", "archive", "N-02")
    now = datetime.now(timezone.utc)
    assert payload_expires is not None
    assert abs(payload_expires - (now + timedelta(days=180))) < timedelta(hours=1)
    assert prepared_expires is None, "no prepared_content row for an archived mail"
    assert tuple(trace_s1) == ("archive", "N-02")
