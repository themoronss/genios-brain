"""Group L4.3 gate, half two — S3, the digest that outlives the 720h payload TTL.

Doc 03's acceptance rows tested here:

    post-TTL replay ....... digest-verified and LABELLED, never a false failure
    tampered payload ...... still fails closed
    permanent row size .... bounded
    historic id migration . complete, replay-tested

Every one of these runs against a real PostgreSQL. `reason/store.py` is preserve-hard and its
guarantee is a fail-closed hash check against bytes in a table; a fake connection can be made to
agree with anything, so it can prove nothing about this.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.contracts.reasoning import (
    ContextSnapshot,
    EvidenceRef,
    ExecutionMode,
    ReasoningRequest,
)
from genios_engine.packs.capabilities import DEAL_COOLING_V1
from genios_engine.reason.audit import persist_execution
from genios_engine.reason.orchestrator import ReasoningOrchestrator
from genios_engine.reason.reasoners import default_registry
from genios_engine.reason.replay import replay_persisted
from genios_engine.reason.store import (
    ContextPayloadExpired,
    EvidenceDigestMismatch,
    ReasoningStore,
    ReplayIntegrityError,
)

NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)

#: NOT the production default of 720h, and the difference is load-bearing. `NOW` is a FIXED past
#: instant so every hash in this file is reproducible, and 720h from a fixed past instant lapses
#: against the wall clock the moment the calendar moves past it — at which point "the payload is
#: still present, so the strong proof must be used" becomes untestable, because every run in the
#: file is already TTL-expired. A long TTL keeps the live-payload state reachable; the post-TTL
#: state is then reached deliberately, by purging at `AFTER_TTL`, which is what production's
#: heartbeat does too.
TTL_HOURS = 43_800
AFTER_TTL = NOW + timedelta(hours=TTL_HOURS + 1)


def deal_cooling_context(org_id: str = "org_z2") -> ContextSnapshot:
    """The bounded context DEAL_COOLING_V1 reasons over. Shared with test_evidence_shape.py so
    the 100%-unit_ref claim and the digest claims are made about the SAME run."""
    return ContextSnapshot(
        org_id=org_id, graph_version=21, root_entity_id="deal_1", root_entity_type="deal",
        evaluation_time=NOW, selector_version="deal_cooling.selector.v1",
        facts={
            "deal.status": {"value": "open", "confidence_bp": 9_500, "src_count": 2},
            "deal.value": {"value": 500_000, "confidence_bp": 9_500, "src_count": 2},
            "derived.engagement": {"value_bp": 4_000, "confidence_bp": 8_500, "src_count": 2},
            "thread.last_inbound": {"value": (NOW - timedelta(days=10)).isoformat(),
                                    "confidence_bp": 9_000, "src_count": 2},
            "relationship.verified_stakeholder_count": {"value": 2},
        },
        observations=({"kind": "customer_reply", "occurred_at": NOW - timedelta(days=10)},),
        neighbor_facts={"deal.status": "open", "contact.verified_recipient": True,
                        "account.alternate_stakeholder_verified": True},
        neighbor_observations=("pricing_discussed", "buying_intent"),
        edge_count=2,
        evidence=(
            EvidenceRef("ev_status", "deal.status", "open", source_ref_id="email_1",
                        fact_version_id="factv_status_1", occurred_at=NOW - timedelta(hours=1),
                        confidence_bp=9_500, authority_rank=3, independence_group="crm"),
            EvidenceRef("ev_engagement", "derived.engagement", 4_000,
                        confidence_bp=8_500, authority_rank=2),
            EvidenceRef("ev_inbound", "thread.last_inbound",
                        (NOW - timedelta(days=10)).isoformat(),
                        confidence_bp=9_000, authority_rank=2),
        ),
        metadata={"tenant_timezone": "Asia/Kolkata"},
    )


@pytest.fixture(scope="module")
def engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres L4.3 tests skipped")
    from genios_engine.platform.db import get_engine

    return get_engine(url)


@pytest.fixture
def org(engine, request):
    """One tenant per test, dropped afterwards. These tests purge, tamper with and delete rows
    in shared reasoning tables, so sharing a tenant would make them order-dependent — and an
    order-dependent proof about a fail-closed store is not a proof."""
    org_id = f"org_l43_{abs(hash(request.node.name)) % 10 ** 9}"
    with engine.begin() as conn:
        conn.execute(text("insert into orgs (id, name) values (:o, :o) "
                          "on conflict (id) do nothing"), {"o": org_id})
    yield org_id
    with engine.begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": org_id})


def _persist(engine, org_id: str, *, context: ContextSnapshot | None = None) -> dict:
    execution = ReasoningOrchestrator(default_registry()).execute(ReasoningRequest(
        org_id=org_id, capability=DEAL_COOLING_V1,
        context=context or deal_cooling_context(org_id),
        evaluation_time=NOW, trigger_kind="email.received", trigger_ref="event_1",
        mode=ExecutionMode.LIVE, config_snapshot_id=None))
    return persist_execution(store=ReasoningStore(engine=engine), execution=execution,
                             context_payload_ttl_hours=TTL_HOURS)


# ── the digest exists at all, and it exists with the payload ─────────────────────────────

def test_the_permanent_digest_is_written_with_the_payload_it_describes(engine, org):
    bundle = _persist(engine, org)
    digests = bundle["evidence_digests"]

    assert {row["evidence_id"] for row in digests} == {
        "ev_status", "ev_engagement", "ev_inbound"}
    assert bundle["context_snapshot"]["evidence_digest_hash"]
    assert all(len(row["rendered_text"]) <= 120 for row in digests)
    assert all(len(row["value_digest"]) == 64 for row in digests)
    # doc 03's "who observed it", stamped from the run's own hash-verified reasoner results.
    assert any(row["unit_refs"] for row in digests)


def test_the_permanent_table_refuses_a_row_longer_than_the_bound(engine, org):
    """Bounded in code AND in the schema. doc 03's 120 characters is a PII argument as much as a
    size one, so one of the two enforcements failing must not silently widen the other."""
    _persist(engine, org)
    with pytest.raises(Exception) as exc:
        with engine.begin() as conn:
            conn.execute(text(
                "update reasoning_evidence_digests set rendered_text=:t where org_id=:o"),
                {"o": org, "t": "x" * 121})

    assert "rendered_text" in str(exc.value) or "check" in str(exc.value).lower()


def test_a_second_run_on_one_snapshot_adds_its_units_without_erasing_the_first(engine, org):
    first = _persist(engine, org)
    before = {row["evidence_id"]: set(row["unit_refs"]) for row in first["evidence_digests"]}

    again = _persist(engine, org)
    after = {row["evidence_id"]: set(row["unit_refs"]) for row in again["evidence_digests"]}

    assert all(before[key] <= after[key] for key in before)
    assert after == before, "the same capability re-run observes the same facts"


# ── the tampering rows: doc 03's "still fails closed" ────────────────────────────────────

def test_a_tampered_payload_still_fails_closed_now_that_a_digest_exists(engine, org):
    """The row that had to be re-proved after this wave, not merely kept.

    A digest bolted on carelessly is a NEW way to accept a bad payload: verify the digest, shrug
    at the payload, serve it. The verifier's ordering forbids that — while the payload exists it
    is the payload that is checked — and this drives the actual bytes to prove it.
    """
    bundle = _persist(engine, org)
    store = ReasoningStore(engine=engine)
    with engine.begin() as conn:
        conn.execute(text(
            "update reasoning_context_payloads "
            "set payload = jsonb_set(payload, '{graph_version}', '99'::jsonb) "
            "where org_id=:o and context_snapshot_id=:s"),
            {"o": org, "s": bundle["run"]["context_snapshot_id"]})

    with pytest.raises(ReplayIntegrityError):
        store.load_replay_bundle(org_id=org, run_id=bundle["run"]["run_id"])
    # and the digest lane is not a back door out of it either
    with pytest.raises(ReplayIntegrityError):
        store.load_replay_bundle(org_id=org, run_id=bundle["run"]["run_id"],
                                 allow_digest_replay=True)


def test_a_tampered_digest_row_fails_closed(engine, org):
    bundle = _persist(engine, org)
    store = ReasoningStore(engine=engine)
    with engine.begin() as conn:
        conn.execute(text(
            "update reasoning_evidence_digests set rendered_text='deal.status=won' "
            "where org_id=:o and evidence_id='ev_status'"), {"o": org})

    with pytest.raises(EvidenceDigestMismatch):
        store.load_evidence_digests(
            org_id=org, context_snapshot_id=bundle["run"]["context_snapshot_id"])
    with pytest.raises(ReplayIntegrityError):
        store.load_bundle(org_id=org, run_id=bundle["run"]["run_id"])


def test_a_digest_row_deleted_outright_fails_closed(engine, org):
    """Removing evidence is a tamper too, and a set hash over the remaining rows is what catches
    it — a per-row hash alone would happily verify the two survivors."""
    bundle = _persist(engine, org)
    store = ReasoningStore(engine=engine)
    with engine.begin() as conn:
        conn.execute(text("delete from reasoning_evidence_digests "
                          "where org_id=:o and evidence_id='ev_inbound'"), {"o": org})

    with pytest.raises(EvidenceDigestMismatch):
        store.load_evidence_digests(
            org_id=org, context_snapshot_id=bundle["run"]["context_snapshot_id"])


def test_a_digest_set_transplanted_from_another_snapshot_fails_closed(engine, org):
    """The set hash is bound to `payload_hash`, which is inside `context_hash`, which is the
    snapshot id — so a real, internally consistent digest set from a DIFFERENT decision cannot be
    presented as this one's."""
    first = _persist(engine, org)
    other_context = ContextSnapshot(**{
        **{field: getattr(deal_cooling_context(org), field)
           for field in ("org_id", "root_entity_id", "root_entity_type", "evaluation_time",
                         "selector_version", "facts", "observations", "neighbor_facts",
                         "neighbor_observations", "edge_count", "evidence", "metadata")},
        "graph_version": 22})
    second = _persist(engine, org, context=other_context)
    assert (first["run"]["context_snapshot_id"] != second["run"]["context_snapshot_id"])

    with engine.begin() as conn:
        conn.execute(text(
            "update reasoning_context_snapshots set evidence_digest_hash="
            "(select evidence_digest_hash from reasoning_context_snapshots "
            " where org_id=:o and context_snapshot_id=:b) "
            "where org_id=:o and context_snapshot_id=:a"),
            {"o": org, "a": first["run"]["context_snapshot_id"],
             "b": second["run"]["context_snapshot_id"]})

    with pytest.raises(EvidenceDigestMismatch):
        ReasoningStore(engine=engine).load_evidence_digests(
            org_id=org, context_snapshot_id=first["run"]["context_snapshot_id"])


# ── the post-TTL rows: doc 03's whole reason for existing ────────────────────────────────

def test_the_purge_mints_the_digest_before_it_deletes_the_payload(engine, org):
    """There is no separate backfill to forget to run. A payload written before migration 0117
    has no digest, and this is the LAST moment one can be derived from it."""
    bundle = _persist(engine, org)
    snapshot_id = bundle["run"]["context_snapshot_id"]
    store = ReasoningStore(engine=engine)
    with engine.begin() as conn:  # simulate a pre-0117 snapshot: payload kept, digest never minted
        conn.execute(text("delete from reasoning_evidence_digests where org_id=:o"), {"o": org})
        conn.execute(text("update reasoning_context_snapshots set evidence_digest_hash=null "
                          "where org_id=:o"), {"o": org})
    assert store.load_evidence_digests(org_id=org, context_snapshot_id=snapshot_id) == []

    # The sweep is tenant-WIDE by design (it is a retention clock, not a tenant operation), so
    # this counts what happened to THIS tenant's snapshot rather than to the whole table — a
    # global count would make the assertion depend on whatever else the suite left expired.
    purged = store.purge_expired_context_payloads(eval_time=AFTER_TTL)

    assert purged >= 1
    with engine.connect() as conn:
        assert conn.execute(text("select count(*) from reasoning_context_payloads "
                                 "where org_id=:o"), {"o": org}).scalar() == 0
    recovered = store.load_evidence_digests(org_id=org, context_snapshot_id=snapshot_id)
    assert {row["evidence_id"] for row in recovered} == {
        "ev_status", "ev_engagement", "ev_inbound"}
    assert any(row["rendered_text"] == "deal.status=open" for row in recovered)


def test_a_post_ttl_replay_digest_verifies_and_says_that_is_what_it_did(engine, org):
    """The doc 03 headline. The card can be re-justified; the answer is LABELLED as the weaker
    proof, so no reader has to assume which one they got."""
    bundle = _persist(engine, org)
    store = ReasoningStore(engine=engine)
    assert store.load_replay_bundle(
        org_id=org, run_id=bundle["run"]["run_id"])["replay_mode"] == "payload_verified"

    store.purge_expired_context_payloads(eval_time=AFTER_TTL)
    replayed = store.load_replay_bundle(org_id=org, run_id=bundle["run"]["run_id"],
                                        allow_digest_replay=True)

    assert replayed["replay_mode"] == "digest_verified"
    assert replayed["replayable"] is False
    assert (replayed["context_snapshot"] or {}).get("payload") is None
    assert {row["evidence_id"] for row in replayed["evidence_digests"]} == {
        "ev_status", "ev_engagement", "ev_inbound"}


def test_a_post_ttl_replay_still_refuses_by_default(engine, org):
    """Nothing that replays today changes. Re-EXECUTING a run without its bounded context is
    impossible, and returning a bundle shaped like a replayable one would be a lie of shape."""
    bundle = _persist(engine, org)
    store = ReasoningStore(engine=engine)
    store.purge_expired_context_payloads(eval_time=AFTER_TTL)

    with pytest.raises(ContextPayloadExpired):
        store.load_replay_bundle(org_id=org, run_id=bundle["run"]["run_id"])


def test_the_weaker_proof_may_not_stand_in_while_the_stronger_one_exists(engine, org):
    """Asking for digest verification is not the same as being granted it. While the payload is
    present the payload is what gets verified, and a caller that asked for the shortcut is told
    no — otherwise `allow_digest_replay=True` would become a way to skip the hash check."""
    bundle = _persist(engine, org)
    store = ReasoningStore(engine=engine)

    replayed = store.load_replay_bundle(org_id=org, run_id=bundle["run"]["run_id"],
                                        allow_digest_replay=True)

    assert replayed["replay_mode"] == "payload_verified"
    assert replayed["replayable"] is True


def test_a_decision_older_than_the_digest_whose_payload_is_gone_says_so(engine, org):
    """The honest answer to an unanswerable question. Returning an empty evidence list would read
    as "this decision cited nothing", which is a false statement about a sound decision."""
    bundle = _persist(engine, org)
    store = ReasoningStore(engine=engine)
    with engine.begin() as conn:
        conn.execute(text("delete from reasoning_context_payloads where org_id=:o"), {"o": org})
        conn.execute(text("delete from reasoning_evidence_digests where org_id=:o"), {"o": org})
        conn.execute(text("update reasoning_context_snapshots set evidence_digest_hash=null "
                          "where org_id=:o"), {"o": org})

    with pytest.raises(EvidenceDigestMismatch, match="can no longer be re-justified"):
        store.load_replay_bundle(org_id=org, run_id=bundle["run"]["run_id"],
                                 allow_digest_replay=True)


def test_a_post_ttl_replay_refuses_when_a_cited_fact_has_no_digest(engine, org):
    """Coverage, not merely consistency. A replay that verified two digests and said nothing
    about the third fact the decision rested on is exactly the false reassurance this group
    exists to prevent."""
    bundle = _persist(engine, org)
    store = ReasoningStore(engine=engine)
    store.purge_expired_context_payloads(eval_time=AFTER_TTL)
    snapshot_id = bundle["run"]["context_snapshot_id"]
    with engine.begin() as conn:
        rows = conn.execute(text(
            "select evidence_id, digest_hash from reasoning_evidence_digests "
            "where org_id=:o and context_snapshot_id=:s order by evidence_id"),
            {"o": org, "s": snapshot_id}).mappings().all()
        conn.execute(text("delete from reasoning_evidence_digests "
                          "where org_id=:o and evidence_id='ev_status'"), {"o": org})
        # Re-anchor the set hash so the ONLY remaining failure is the missing coverage.
        from genios_engine.reason.evidence import digest_set_hash
        kept = [dict(row) for row in rows if row["evidence_id"] != "ev_status"]
        payload_hash = conn.execute(text(
            "select payload_hash from reasoning_context_snapshots "
            "where org_id=:o and context_snapshot_id=:s"),
            {"o": org, "s": snapshot_id}).scalar()
        conn.execute(text("update reasoning_context_snapshots set evidence_digest_hash=:h "
                          "where org_id=:o and context_snapshot_id=:s"),
                     {"o": org, "s": snapshot_id,
                      "h": digest_set_hash(payload_hash=payload_hash, rows=kept)})

    with pytest.raises(EvidenceDigestMismatch, match="no permanent digest"):
        store.load_replay_bundle(org_id=org, run_id=bundle["run"]["run_id"],
                                 allow_digest_replay=True)


# ── S2's migration half, replay-tested ───────────────────────────────────────────────────

def test_the_purge_maps_every_historic_evidence_id_forward(engine, org):
    """Historic decisions replay against a MAPPING, never against a silently different id.

    The stored ids here (`ev_status`, …) are literals, exactly as a pre-0117 lane's would be
    unrecognisable to the new seed. They are not rewritten — they live inside a hash-verified
    payload — so the map is what makes them reachable from the canonical identity.
    """
    from genios_engine.reason.evidence import canonical_evidence_id_for

    bundle = _persist(engine, org)
    store = ReasoningStore(engine=engine)
    store.purge_expired_context_payloads(eval_time=AFTER_TTL)

    with engine.connect() as conn:
        mapped = {row.legacy_evidence_id: row.evidence_id for row in conn.execute(text(
            "select legacy_evidence_id, evidence_id from reasoning_evidence_id_map "
            "where org_id=:o"), {"o": org})}

    assert set(mapped) == {"ev_status", "ev_engagement", "ev_inbound"}
    assert mapped["ev_status"] == canonical_evidence_id_for(
        org_id=org, root_entity_id="deal_1",
        ref={"field": "deal.status", "context_scope": "root", "source_ref_id": "email_1",
             "occurred_at": NOW - timedelta(hours=1)})
    assert store.canonical_evidence_id(org_id=org, legacy_evidence_id="ev_status") == (
        mapped["ev_status"])
    assert store.canonical_evidence_id(org_id=org, legacy_evidence_id="ev_nothing") is None
    # And the decision itself still replays, digest-verified, after the mapping was written.
    assert store.load_replay_bundle(org_id=org, run_id=bundle["run"]["run_id"],
                                    allow_digest_replay=True)["replay_mode"] == "digest_verified"


def test_a_canonical_id_is_not_mapped_to_itself(engine, org):
    """The map answers "what did this old id become". A row for an id that never changed would
    make an empty answer ambiguous between "already canonical" and "never seen"."""
    from genios_engine.reason.evidence import build_evidence_ref

    context = deal_cooling_context(org)
    canonical = tuple(build_evidence_ref(
        org_id=org, entity_ref="deal_1", field=ref.field, value=ref.value,
        source_ref=ref.source_ref_id, observed_at=ref.occurred_at,
        confidence_bp=ref.confidence_bp, authority_rank=ref.authority_rank,
        independence_group=ref.independence_group) for ref in context.evidence)
    _persist(engine, org, context=ContextSnapshot(**{
        **{field: getattr(context, field)
           for field in ("org_id", "graph_version", "root_entity_id", "root_entity_type",
                         "evaluation_time", "selector_version", "facts", "observations",
                         "neighbor_facts", "neighbor_observations", "edge_count", "metadata")},
        "evidence": canonical}))
    ReasoningStore(engine=engine).purge_expired_context_payloads(eval_time=AFTER_TTL)

    with engine.connect() as conn:
        assert conn.execute(text("select count(*) from reasoning_evidence_id_map "
                                 "where org_id=:o"), {"o": org}).scalar() == 0


def test_the_sweep_is_bounded_so_a_neglected_table_cannot_stall_the_heartbeat(engine, org):
    first = _persist(engine, org)
    second_context = ContextSnapshot(**{
        **{field: getattr(deal_cooling_context(org), field)
           for field in ("org_id", "root_entity_id", "root_entity_type", "evaluation_time",
                         "selector_version", "facts", "observations", "neighbor_facts",
                         "neighbor_observations", "edge_count", "evidence", "metadata")},
        "graph_version": 23})
    second = _persist(engine, org, context=second_context)
    assert first["run"]["context_snapshot_id"] != second["run"]["context_snapshot_id"]
    store = ReasoningStore(engine=engine)

    def _mine() -> int:
        with engine.connect() as conn:
            return conn.execute(text("select count(*) from reasoning_context_payloads "
                                     "where org_id=:o"), {"o": org}).scalar()

    assert _mine() == 2
    # ONE row, whoever it belongs to — the sweep is tenant-wide, so the claim under test is the
    # bound, not which tenant it landed on. Two of this tenant's payloads cannot go in one pass.
    assert store.purge_expired_context_payloads(eval_time=AFTER_TTL, batch_limit=1) == 1
    assert _mine() >= 1
    while store.purge_expired_context_payloads(eval_time=AFTER_TTL, batch_limit=1):
        if _mine() == 0:
            break
    assert _mine() == 0


# ── the live read path ───────────────────────────────────────────────────────────────────

def test_the_explain_route_reads_the_digest_and_names_which_proof_it_carried(monkeypatch):
    """The year-old card, on the route a customer actually reaches. `/v1/intelligence/decisions/
    {id}/explain` is where "why did GeniOS say this" is answered, and before this wave it could
    name a decision's evidence and never re-read it once the payload expired."""
    from genios_engine.api import intelligence_routes as routes

    envelope = {"confidence": 0.74, "as_of": {"graph_version": 9},
                "derivation": [{"rule_id": "cooling", "conclusion": "cooling_deal",
                                "reasoning_run_id": "run_a", "matched_facts": {}}]}

    class _Conn:
        def execute(self, _statement, _params=None):
            return SimpleNamespace(first=lambda: SimpleNamespace(envelope=envelope))

    class _Engine:
        @contextmanager
        def connect(self):
            yield _Conn()

    class _Store:
        def __init__(self, *, engine):
            self.engine = engine

        def load_bundle(self, *, org_id, run_id):
            return {
                "reasoner_results": [{"reasoner_id": "core.timeline"}],
                "candidate_checks": [],
                "context_snapshot": {"source_manifest": [], "payload": None},
                "evidence_digests": [{
                    "evidence_id": "ev_renewal", "field": "deal.renewal_date",
                    "rendered_text": "deal.renewal_date=2027-03-03",
                    "value_digest": "a" * 64, "observed_at_key": "2026-08-06T11:00:00+00:00",
                    "unit_refs": ("core.timeline",)}],
                "output": {"confidence_bp": 8_100},
            }

    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=_Engine()))
    monkeypatch.setattr(routes, "ReasoningStore", _Store)

    result = routes.explain_decision("dec_1", org_id="org_1")
    view = result["reasoning_runs"][0]

    assert view["evidence_provenance"] == "digest_verified"
    assert view["evidence"] == [{
        "evidence_id": "ev_renewal", "field": "deal.renewal_date",
        "claim": "deal.renewal_date=2027-03-03", "value_digest": "a" * 64,
        "observed_at": "2026-08-06T11:00:00+00:00",
        "observed_by_units": ["core.timeline"]}]


def test_the_explain_route_distinguishes_a_live_payload_from_a_pre_digest_decision(monkeypatch):
    from genios_engine.api import intelligence_routes as routes

    envelope = {"confidence": 0.5, "as_of": {},
                "derivation": [{"rule_id": "r", "conclusion": "c", "reasoning_run_id": "run_a",
                                "matched_facts": {}}]}

    class _Conn:
        def execute(self, _statement, _params=None):
            return SimpleNamespace(first=lambda: SimpleNamespace(envelope=envelope))

    class _Engine:
        @contextmanager
        def connect(self):
            yield _Conn()

    def _store_returning(context_snapshot, digests):
        class _Store:
            def __init__(self, *, engine):
                self.engine = engine

            def load_bundle(self, *, org_id, run_id):
                return {"reasoner_results": [], "candidate_checks": [],
                        "context_snapshot": context_snapshot, "evidence_digests": digests,
                        "output": {"confidence_bp": 1}}
        return _Store

    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=_Engine()))

    monkeypatch.setattr(routes, "ReasoningStore",
                        _store_returning({"source_manifest": [], "payload": {"facts": {}}}, []))
    live = routes.explain_decision("dec_1", org_id="org_1")

    monkeypatch.setattr(routes, "ReasoningStore",
                        _store_returning({"source_manifest": [], "payload": None}, []))
    lost = routes.explain_decision("dec_1", org_id="org_1")

    assert live["reasoning_runs"][0]["evidence_provenance"] == "payload_verified"
    assert lost["reasoning_runs"][0]["evidence_provenance"] == "unavailable_pre_digest"


# ── the three properties a forger who knows the hashing law would still hit ──────────────

def test_a_forged_digest_that_is_internally_consistent_is_caught_by_the_live_payload(engine, org):
    """The reason the payload-vs-digest cross-check runs on EVERY load while the payload lives.

    Here the attacker recomputes everything: the row's own `digest_hash`, and the snapshot's
    `evidence_digest_hash` over the edited set. Every self-referential check now agrees. Only one
    thing still disagrees — the payload the digests claim to describe — and that is precisely why
    the digest table must be audited by the full-strength path continuously rather than first
    consulted in five years, when the payload is gone and nothing can contradict it.
    """
    from genios_engine.reason.evidence import digest_row, digest_set_hash

    bundle = _persist(engine, org)
    snapshot_id = bundle["run"]["context_snapshot_id"]
    forged = digest_row(EvidenceRef("ev_status", "deal.status", "won",
                                    source_ref_id="email_1",
                                    occurred_at=NOW - timedelta(hours=1),
                                    independence_group="crm"))
    with engine.begin() as conn:
        conn.execute(text(
            "update reasoning_evidence_digests set rendered_text=:t, value_digest=:v, "
            "digest_hash=:h where org_id=:o and context_snapshot_id=:s and evidence_id='ev_status'"),
            {"o": org, "s": snapshot_id, "t": forged["rendered_text"],
             "v": forged["value_digest"], "h": forged["digest_hash"]})
        rows = [dict(row) for row in conn.execute(text(
            "select evidence_id, digest_hash from reasoning_evidence_digests "
            "where org_id=:o and context_snapshot_id=:s"), {"o": org, "s": snapshot_id}).mappings()]
        payload_hash = conn.execute(text(
            "select payload_hash from reasoning_context_snapshots "
            "where org_id=:o and context_snapshot_id=:s"),
            {"o": org, "s": snapshot_id}).scalar()
        conn.execute(text("update reasoning_context_snapshots set evidence_digest_hash=:h "
                          "where org_id=:o and context_snapshot_id=:s"),
                     {"o": org, "s": snapshot_id,
                      "h": digest_set_hash(payload_hash=payload_hash, rows=rows)})

    store = ReasoningStore(engine=engine)
    # Every hash the digests keep about themselves now verifies …
    assert store.load_evidence_digests(org_id=org, context_snapshot_id=snapshot_id)
    # … and the payload still refuses the claim.
    with pytest.raises(EvidenceDigestMismatch, match="differ from the payload they describe"):
        store.load_replay_bundle(org_id=org, run_id=bundle["run"]["run_id"])


def test_rewriting_a_snapshot_re_reads_the_digests_it_did_not_have_to_insert(engine, org):
    """`on conflict do nothing` means a second write of a content-identical snapshot inserts
    nothing — so if the store trusted the insert it would never notice that what is ALREADY there
    is not what it would have written. It re-reads and compares instead.

    The edit here leaves `digest_hash` and the set hash untouched, so neither content-address
    check can see it; only the row-for-row comparison against the payload can.
    """
    bundle = _persist(engine, org)
    snapshot_id = bundle["run"]["context_snapshot_id"]
    with engine.begin() as conn:
        conn.execute(text(
            "update reasoning_evidence_digests set rendered_text='deal.status=won' "
            "where org_id=:o and context_snapshot_id=:s and evidence_id='ev_status'"),
            {"o": org, "s": snapshot_id})

    with pytest.raises(EvidenceDigestMismatch, match="differ from the payload they bind"):
        _persist(engine, org)


def test_digest_verification_may_never_be_asked_for_while_the_payload_is_readable(engine, org):
    """`digest_only=True` is a statement about the world, not a preference.

    `load_replay_bundle` never passes it while a payload is readable — but the verifier is public
    and a future caller could, and the weaker proof standing in for a stronger one that is sitting
    right there is the exact failure doc 03 warns a careless digest introduces.
    """
    bundle = _persist(engine, org)
    store = ReasoningStore(engine=engine)
    loaded = store.load_replay_bundle(org_id=org, run_id=bundle["run"]["run_id"])
    assert loaded["context_snapshot"]["payload"] is not None

    store.verify_replay_bundle(loaded, org_id=org)          # the strong proof still passes
    with pytest.raises(ReplayIntegrityError, match="may never stand in"):
        store.verify_replay_bundle(loaded, org_id=org, digest_only=True)


def test_the_reset_that_customers_press_erases_the_permanent_evidence_too(engine, org):
    """The permanent table is the one place a fact's rendered text OUTLIVES its payload.

    `_ORG_SCOPED_TABLES` runs a bare `delete from {tbl}` per name with no try/except, so a table
    missing from that list is not erased and nothing says so. A digest row that survived /reset
    would leave a short, readable claim about a real counterparty behind after the customer asked
    for their graph to be wiped — which is exactly the sentence a privacy answer cannot contain.
    """
    from genios_engine.api import account_routes

    bundle = _persist(engine, org)
    ReasoningStore(engine=engine).purge_expired_context_payloads(eval_time=AFTER_TTL)
    with engine.connect() as conn:
        assert conn.execute(text("select count(*) from reasoning_evidence_digests "
                                 "where org_id=:o"), {"o": org}).scalar() == 3
        assert conn.execute(text("select count(*) from reasoning_evidence_id_map "
                                 "where org_id=:o"), {"o": org}).scalar() == 3

    with engine.begin() as conn:
        wiped = account_routes._wipe(conn, org)

    assert wiped["reasoning_evidence_digests"] == 3
    assert wiped["reasoning_evidence_id_map"] == 3
    with engine.connect() as conn:
        for table in ("reasoning_evidence_digests", "reasoning_evidence_id_map"):
            assert conn.execute(text(f"select count(*) from {table} where org_id=:o"),
                                {"o": org}).scalar() == 0
    assert bundle["run"]["run_id"]


# ── the verifier and the writer must describe the SAME run ───────────────────────────────

def test_a_selected_run_replays_clean_instead_of_crying_wolf(engine, org):
    """Preserve-hard 5. The audit's verifier is only worth reading if it is quiet on honest rows.

    `audit._audited_results` writes `decision_core.reasoner_result_hashes` as every DECLARED unit
    — the ones that ran, then the ones the Unit Selector dropped, each with its receipt.
    `replay_persisted` rebuilt its half from `execution.ordered_results`, which excludes the
    dropped ones. That cost nothing while selection was enabled by no manifest; the moment the
    roster woke it made the verifier disagree with the writer on every selected run — 605 false
    mismatches in a 660-run compiled population, `decision_hash` and `candidate_hashes` matching on
    all 605. A verifier that reports a mismatch on 92% of honest rows cannot find the dishonest one.

    Driven through a capability whose plan actually drops units, because a capability that drops
    none cannot tell the two constructions apart — which is exactly why this went unnoticed.
    """
    from dataclasses import replace as _replace

    from genios_engine.reason.audit import audited_results
    from genios_engine.reason.plan import CONTEXT_AWARE_SELECTION_KEY

    # THE SELECTOR ON, and a snapshot that cannot feed one of the declared units — otherwise the
    # skipped tail is empty and the two constructions are indistinguishable, which is precisely
    # why this defect survived a green suite.
    from genios_engine.contracts.reasoning import FailurePolicy, ReasonerSpec

    # A DISTINCT capability id and version. `reasoning_capability_snapshots` is keyed on
    # (capability_id, version) and refuses a second, different manifest under the same key, so
    # persisting a modified DEAL_COOLING_V1 under its own name would poison the row every other
    # test in the suite reads — which is the "commits its own rows" hazard, not a proof.
    #
    # THE INTELLIGENCE OBJECTS ARE RE-HOMED WITH THE RENAME, and that is not bookkeeping:
    # `CapabilityManifest.__post_init__` refuses a manifest holding an object that names another
    # capability, so a bare `replace(capability_id=...)` raises before the run is even built.
    # The rule is right — an intelligence object is owned by the capability it was authored for —
    # and the probe has to obey it rather than be exempted from it.
    probe_id = "sales.deal_cooling_selector_probe"
    selecting = _replace(
        DEAL_COOLING_V1,
        capability_id=probe_id, version="1.0.0-gk",
        intelligence_objects=tuple(_replace(obj, capability_id=probe_id)
                                   for obj in DEAL_COOLING_V1.intelligence_objects),
        reasoners=DEAL_COOLING_V1.reasoners + (
            ReasonerSpec(reasoner_id="core.opportunity", version="1.0.0",
                         dependencies=("core.temporal",),
                         required_fields=("deal.never_captured",),
                         failure_policy=FailurePolicy.OPTIONAL),),
        metadata={**dict(DEAL_COOLING_V1.metadata), CONTEXT_AWARE_SELECTION_KEY: True})
    execution = ReasoningOrchestrator(default_registry()).execute(ReasoningRequest(
        org_id=org, capability=selecting, context=deal_cooling_context(org),
        evaluation_time=NOW, trigger_kind="email.received", trigger_ref="event_1",
        mode=ExecutionMode.LIVE, config_snapshot_id=None))
    assert execution.plan.skipped, "this capability dropped no unit; the case proves nothing"
    bundle = persist_execution(store=ReasoningStore(engine=engine), execution=execution,
                               context_payload_ttl_hours=TTL_HOURS)
    run_id = bundle["run"]["run_id"]
    replayed, comparison = replay_persisted(
        store=ReasoningStore(engine=engine), org_id=org, run_id=run_id,
        orchestrator=ReasoningOrchestrator(default_registry()))
    assert comparison.differences == (), comparison.differences
    assert comparison.matches
    # and the two sides are the same construction, not two that happen to agree here
    stored = [tuple(item) for item in
              bundle["output"]["decision_core"]["reasoner_result_hashes"]]
    assert stored == [(item.reasoner_id, item.semantic_hash)
                      for item, _hash in audited_results(replayed)]


def test_a_replayed_capability_addresses_to_the_row_it_was_read_from(engine, org):
    """`capability_snapshot_id` is the content address of `to_semantic_dict`, which carries
    `selection_fields` — and `replay.capability_from_manifest` did not read that key back. Every
    manifest declaring one round-tripped into a capability with a DIFFERENT id, so the replay was
    conducted under a capability that was not the stored one. Measured on a compiled manifest:
    9 selection fields in, 0 out, ids unequal."""
    from genios_engine.contracts.reasoning import CapabilityManifest
    from genios_engine.platform.canonical import canonicalize
    from genios_engine.reason.replay import capability_from_manifest

    with_selection = CapabilityManifest(
        capability_id=DEAL_COOLING_V1.capability_id, version=DEAL_COOLING_V1.version,
        domain=DEAL_COOLING_V1.domain, root_entity_type=DEAL_COOLING_V1.root_entity_type,
        goal=DEAL_COOLING_V1.goal, reasoners=DEAL_COOLING_V1.reasoners,
        plays=DEAL_COOLING_V1.plays, required_fields=DEAL_COOLING_V1.required_fields,
        selection_fields=("deal.value", "thread.last_inbound"),
        ranking_weights=DEAL_COOLING_V1.ranking_weights, policies=DEAL_COOLING_V1.policies,
        do_nothing_consequence=DEAL_COOLING_V1.do_nothing_consequence,
        expiry_hours=DEAL_COOLING_V1.expiry_hours, metadata=DEAL_COOLING_V1.metadata)
    restored = capability_from_manifest(canonicalize(with_selection.to_semantic_dict()))
    assert restored.selection_fields == with_selection.selection_fields
    assert restored.capability_snapshot_id == with_selection.capability_snapshot_id
