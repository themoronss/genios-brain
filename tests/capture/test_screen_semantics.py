"""P2 group B · screen sessions meet the semantic lane (docs/plans/SCREEN_INTEL_P2_BUILD.md §3-§4).

    pytest tests/capture/test_screen_semantics.py -q

* routing: the three screen object types reach `screen_session` / `email` / `screen_generic`;
* authority: all three rank above 0 (else L2 may never publish them — plan §1.3);
* direction: a screen object with a mailbox owner is never `direction_unknown`;
* same message (§3.3): a Gmail/Outlook message the screen claimed first is skipped as
  `seen_on_screen` with exactly one `same_message:` ref — group C's `fingerprint` module is
  STUBBED here (C owns it; this branch codes against the frozen signatures only).
"""

from __future__ import annotations

import os
import sys
import types
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone

import pytest

from genios_engine.capture import pipeline as P
from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.semantic.router import routing_input_for, select_profile
from genios_engine.capture.validate.authority import (AuthorityBasis, Provenance,
                                                      weigh_authority)
from genios_engine.contracts.conflict import Authority
from genios_engine.contracts.source_event import Actor, SourceEvent, compute_dedup_key

SEAT = "seat1@genios.ai"
BUYER = "buyer@acme.com"
NOW = datetime(2026, 9, 13, 9, 30, tzinfo=timezone.utc)
MINIMAL_ANSWER = {"intent": "inform", "stance": "neutral"}
CANONICAL = "evt_screen_canonical"


def _event(object_type: str, *, source: str = "screen_session",
           email: str | None = None) -> SourceEvent:
    soid = f"thread-1#5#{object_type}"
    return SourceEvent(
        event_id=f"evt_{object_type}", org_id="org_p2b", connection_id="conn_p2b",
        source=source, object_type=object_type, source_object_id=soid,
        dedup_key=compute_dedup_key(source, object_type, soid),
        actor=Actor(type="external_contact", email=email), occurred_at=NOW)


# ── routing + authority ─────────────────────────────────────────────────────────────────────

SCREEN_TYPES = (
    ("screen_chat_thread", "screen_session", Authority.CHAT_ASIDE),
    ("screen_chat_sent", "screen_session", Authority.EMAIL_PROSE),      # own outgoing = rank 2
    ("screen_email_thread", "email", Authority.EMAIL_PROSE),
    ("screen_doc", "screen_generic", Authority.CHAT_ASIDE),
)


@pytest.mark.parametrize("object_type,profile_id,_authority", SCREEN_TYPES)
def test_each_screen_object_type_routes_to_its_profile(object_type, profile_id, _authority):
    choice = select_profile(routing_input_for(_event(object_type)))
    assert choice.profile_id == profile_id
    assert choice.fell_back is False


@pytest.mark.parametrize("object_type,_profile,authority", SCREEN_TYPES)
def test_each_screen_object_type_has_authority_above_zero(object_type, _profile, authority):
    weight = weigh_authority(Provenance(source="screen_session", object_type=object_type,
                                        source_ref="prepared_content:evt_1"))
    assert weight.authority is authority
    assert weight.basis is AuthorityBasis.SOURCE_OBJECT
    assert weight.rank > 0 and weight.recognised


def test_an_unknown_screen_object_type_is_still_ranked_not_floored():
    weight = weigh_authority(Provenance(source="screen_session", object_type="screen_future"))
    assert weight.authority is Authority.CHAT_ASIDE and weight.rank > 0


# ── direction ───────────────────────────────────────────────────────────────────────────────

DIRECTION_ROWS = (
    ("screen_session", SEAT, SEAT, "outbound", "the seat's own lines"),
    ("screen_session", SEAT.upper(), SEAT, "outbound", "case-insensitive"),
    ("screen_session", BUYER, SEAT, "inbound", "counterparty email"),
    ("screen_session", "li:https://www.linkedin.com/in/rohit", SEAT, "inbound", "li: handle"),
    ("screen_session", None, SEAT, "inbound", "a contact shown by name only"),
    ("screen_session", BUYER, None, None, "no owner: still no identity for 'us'"),
    ("gmail", None, SEAT, None, "mail without a sender is unchanged: refused"),
    ("gmail", BUYER, SEAT, "inbound", "mail unchanged"),
)


@pytest.mark.parametrize("source,sender,owner,expected,why", DIRECTION_ROWS,
                         ids=[row[4] for row in DIRECTION_ROWS])
def test_screen_direction_branch(source, sender, owner, expected, why):
    event = _event("screen_chat_thread" if source == "screen_session" else "message",
                   source=source, email=sender)
    assert P._envelope_direction(event, owner) == expected, why


# ── same message seen on screen (§3.3) ──────────────────────────────────────────────────────

class _FakeFingerprint(types.ModuleType):
    """C's `capture/screen/fingerprint.py`, by its frozen signatures only."""

    def __init__(self, canonical: str | None = None, *, fail: bool = False) -> None:
        super().__init__(P._FINGERPRINT_MODULE)
        self.canonical, self.fail, self.claims = canonical, fail, []

    def message_fp(self, sender_key, ts, body):
        return f"fp:{sender_key}:{ts:%H%M}:{body[:24]}"

    def claim(self, conn, org_id, fps, source, event_id):
        if self.fail:
            raise RuntimeError("database went away")
        self.claims.append({"org": org_id, "fps": list(fps), "source": source,
                            "event_id": event_id})
        return {fp: (self.canonical or event_id) for fp in fps}


class _Conn:
    def __init__(self) -> None:
        self.executed: list[tuple[str, dict]] = []

    def execute(self, statement, params=None):
        self.executed.append((str(statement), params or {}))


class _Engine:
    def __init__(self) -> None:
        self.conn = _Conn()

    @contextmanager
    def begin(self):
        yield self.conn


def _install(monkeypatch, module) -> None:
    monkeypatch.setitem(sys.modules, "genios_engine.capture.screen",
                        types.ModuleType("genios_engine.capture.screen"))
    monkeypatch.setitem(sys.modules, P._FINGERPRINT_MODULE, module)


def _gmail(**over) -> RawObject:
    kwargs = dict(source="gmail", object_type="message", source_object_id="gm_1",
                  occurred_at=NOW, actor_email=BUYER, recipients=(SEAT,),
                  raw={"subject": "Proposal", "body": "<p>We are going with another vendor.</p>"})
    kwargs.update(over)
    return RawObject(**kwargs)


def _capture(raw, lane, repo=None):
    return P.capture_event(raw, org_id="org_p2b", connection_id="conn_gmail",
                           repo=repo or InMemorySourceEventRepository(),
                           mailbox_owner=SEAT, semantic=lane)


def _skip_reason(res) -> str | None:
    rows = [r for r in res.trace.records if r.stage == "s2_semantic_extraction"]
    return rows[-1].reason_code if rows else None


def test_a_message_the_screen_claimed_first_is_not_extracted_and_gets_one_ref(fake_llm,
                                                                               monkeypatch):
    fp_mod, engine = _FakeFingerprint(CANONICAL), _Engine()
    _install(monkeypatch, fp_mod)
    llm = fake_llm()                      # no canned answer: any call fails the test
    res = _capture(_gmail(), P.SemanticLane(llm=llm, eval_time=NOW, fingerprint_engine=engine))

    assert llm.call_count == 0
    assert res.extraction is None
    assert _skip_reason(res) == P.SEEN_ON_SCREEN
    [claim] = fp_mod.claims
    assert claim["source"] == "gmail" and claim["org"] == "org_p2b"
    assert len(claim["fps"]) == 3, "minute -1/0/+1 are all claimed (screen clock skew)"
    assert all(fp.startswith(f"fp:{BUYER}:") for fp in claim["fps"])
    assert claim["fps"][0].endswith(":We are going with anothe"), \
        "the fingerprint is over the body as read, HTML stripped, subject excluded"
    [(sql, params)] = engine.conn.executed
    assert "insert into graph_source_refs" in sql and "on conflict" in sql
    assert params["canonical"] == CANONICAL
    assert params["grp"] == f"same_message:{claim['fps'][0]}"
    assert params["source"] == "gmail" and params["soid"] == "gm_1"
    assert f'"duplicate_event_id": "{claim["event_id"]}"' in params["evidence"]


def test_a_message_first_seen_by_the_connector_is_extracted_and_claimed(fake_llm, monkeypatch):
    fp_mod, engine = _FakeFingerprint(None), _Engine()
    _install(monkeypatch, fp_mod)
    llm = fake_llm(MINIMAL_ANSWER)
    res = _capture(_gmail(), P.SemanticLane(llm=llm, eval_time=NOW, fingerprint_engine=engine))

    assert llm.call_count == 1 and res.extraction is not None
    assert len(fp_mod.claims) == 1, "claimed, so a later screen sighting finds the canonical"
    assert engine.conn.executed == []


@pytest.mark.parametrize("case", ["no_engine", "module_missing", "claim_raises"])
def test_the_check_never_blocks_extraction(case, fake_llm, monkeypatch):
    fp_mod = _FakeFingerprint(CANONICAL, fail=(case == "claim_raises"))
    if case == "module_missing":
        monkeypatch.setitem(sys.modules, P._FINGERPRINT_MODULE, None)   # import -> ImportError
    else:
        _install(monkeypatch, fp_mod)
    engine = None if case == "no_engine" else _Engine()
    llm = fake_llm(MINIMAL_ANSWER)
    res = _capture(_gmail(), P.SemanticLane(llm=llm, eval_time=NOW, fingerprint_engine=engine))

    assert llm.call_count == 1 and res.extraction is not None
    assert fp_mod.claims == []


@pytest.mark.parametrize("source,object_type", [("screen_session", "screen_email_thread"),
                                                ("slack", "message"),
                                                ("gmail", "email_attachment")])
def test_only_connector_mail_messages_are_checked(source, object_type, monkeypatch):
    fp_mod, engine = _FakeFingerprint(CANONICAL), _Engine()
    _install(monkeypatch, fp_mod)
    lane = P.SemanticLane(llm=object(), eval_time=NOW, fingerprint_engine=engine)
    event = _event(object_type, source=source, email=BUYER)
    assert P._seen_on_screen(event, {"body": "hello"}, lane) is None
    assert fp_mod.claims == []


# ── real Postgres: the ref row, once, through the production lane factory ─────────────────

@pytest.mark.pg
def test_same_message_ref_lands_once_in_postgres(fake_llm, monkeypatch):
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set")
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine
    from genios_engine.platform.wiring import make_semantic_lane

    engine = get_engine(url)
    org = f"org_p2b_{uuid.uuid4().hex[:10]}"
    # `graph_source_refs` cascades from `orgs` (FK) — found by this lane; in production the
    # org always exists before its first event.
    with engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, :o)"), {"o": org})
    lane = make_semantic_lane(org, engine=engine, llm=fake_llm(), activated=frozenset({org}))
    assert lane is not None and lane.fingerprint_engine is engine, \
        "the production lane must carry the engine, or the check never runs"
    fp_mod = _FakeFingerprint(CANONICAL)
    _install(monkeypatch, fp_mod)
    def _refs():
        with engine.begin() as c:
            return c.execute(text(
                "select event_id, source, source_object_id, independence_group, "
                "fact_version_id, evidence from graph_source_refs where org_id=:o "
                "order by created_at"), {"o": org}).mappings().all()

    try:
        res = P.capture_event(_gmail(), org_id=org, connection_id="conn_gmail",
                              repo=InMemorySourceEventRepository(), mailbox_owner=SEAT,
                              semantic=lane)
        assert _skip_reason(res) == P.SEEN_ON_SCREEN
        assert len(_refs()) == 1, "one ref per duplicate message"
        # The same EVENT checked again (a re-extraction of it) adds nothing: the ref id is
        # derived from (org, fp, event). A second duplicate event is its own ref.
        event = SourceEvent(
            event_id="evt_gm_fixed", org_id=org, connection_id="conn_gmail", source="gmail",
            object_type="message", source_object_id="gm_2",
            dedup_key=compute_dedup_key("gmail", "message", "gm_2"),
            actor=Actor(type="external_contact", email=BUYER), occurred_at=NOW)
        body = {"body": "We are going with another vendor."}
        assert P._seen_on_screen(event, body, lane) == CANONICAL
        assert P._seen_on_screen(event, body, lane) == CANONICAL
        rows = _refs()
        assert len(rows) == 2
        assert [r["source_object_id"] for r in rows] == ["gm_1", "gm_2"]
        row = rows[0]
        assert row["event_id"] == CANONICAL and row["fact_version_id"] is None
        assert (row["source"], row["source_object_id"]) == ("gmail", "gm_1")
        assert row["independence_group"] == f"same_message:{fp_mod.claims[0]['fps'][0]}"
        assert row["evidence"]["reason"] == P.SEEN_ON_SCREEN
    finally:
        with engine.begin() as c:
            c.execute(text("delete from graph_source_refs where org_id=:o"), {"o": org})
            c.execute(text("delete from orgs where id=:o"), {"o": org})


# ── D7 eval harness: builds the production request and compares claims, read-only ─────────

def _eval_module():
    import importlib.util
    from pathlib import Path
    path = Path(__file__).resolve().parents[2] / "scripts" / "eval_screen_profile.py"
    spec = importlib.util.spec_from_file_location("eval_screen_profile", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_eval_harness_builds_the_screen_request_and_diffs_claims(fake_llm):
    ev = _eval_module()
    row = types.SimpleNamespace(event_id="evt_s1", object_type="screen_chat_thread",
                                actor={"email": SEAT}, occurred_at=NOW)
    body = ("Harsh: I'll send the proposal by Friday\n\ncontext — do not extract\n"
            "> Rohit: can you share pricing?")
    request = ev._request(row, {"body": body, "labelIds": ["SENT"]}, "org_p2b")
    assert request.profile_id == "screen_session" and request.tier == "T1"
    assert request.envelope.direction == "outbound"
    assert "context — do not extract" in request.prepared.clean_text

    answer = dict(MINIMAL_ANSWER, questions=["can we talk?"])
    _, keys_a = ev._run(request, fake_llm(answer))
    _, keys_b = ev._run(request, fake_llm(MINIMAL_ANSWER))
    assert keys_a.get("questions") and not keys_b.get("questions")
