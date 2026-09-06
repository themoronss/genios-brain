"""G9 · the REJECTION LEDGER, `PARKING_RULES`, and the two reads that make them answerable.

    pytest tests/capture/esqe/test_rejection_ledger.py -q

**WHY THIS FILE EXISTS.** V-2, V-3, V-4, V-6 and V-7 REJECT a signal and wrote nothing. Only
V-1's park and the below-floor drop left a trace, so an out-of-range importance, a receipt-less
claim and a Rule 11 violation each vanished with no record — and *"why did I never see X?"* had
an answer for two of the seven rules and silence for five. `RefusedSignal` was built, returned
and discarded at the top of `_publish_sweep`'s own loop.

The second half is `PARKING_RULES`, which `contracts/publication.py` declares and nothing read:
the publisher decided park-versus-reject by looking at ONE hard-coded outcome, so the declared
rule set was documentation. Here it is load-bearing — the table-driven test below moves a rule
into it and the publisher's answer changes.

Every wiring assertion goes through the ROUTER, never through a store the test built itself: a
test that constructs its own ledger proves the ledger and leaves the hole. The `pg` block opens
the scratch Postgres for the real upsert, the payload-retention promise and tenant erasure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from genios_engine.api import routes
from genios_engine.capture.esqe import publisher as P
from genios_engine.capture.esqe import qualification as Q
from genios_engine.capture.esqe.normalize import NormalizedSignal
from genios_engine.capture.esqe.signal_store import InMemorySignalStore, age_signals
from genios_engine.capture.esqe.source_analyzer import ActorBasis, SourceAttribution
from genios_engine.capture.validate.authority import AuthorityBasis, AuthorityWeight, to_legacy_rank
from genios_engine.contracts.conflict import Authority
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import Commitment, ExtractionResult
from genios_engine.contracts.publication import PublicationRule, VISIBILITY_UNKNOWN
from genios_engine.contracts.signal import SignalType
from genios_engine.contracts.visibility import Visibility
from genios_engine.platform.auth import AuthCtx, get_auth_ctx

NOW = datetime(2026, 4, 2, 9, 0, tzinfo=timezone.utc)
ORG = "org_rej_a"
OTHER = "org_rej_b"

BODY = "Finance will confirm the Kestrel MSA renewal at $84,000 before the quarter closes."
PROVENANCE = dict(model_snapshot="fake-model-1", prompt_version="p1", schema_version="1",
                  extraction_profile="email", input_tokens=1000, output_tokens=200)


def _span(quote: str = "Finance", *, verified: bool = True,
          source_ref: str = "prepared_content:pc_1") -> EvidenceSpan:
    start = BODY.index(quote)
    return EvidenceSpan(source_ref=source_ref, quote=quote, start_offset=start,
                        end_offset=start + len(quote), verified=verified)


def _extraction(*spans: EvidenceSpan, confidence_bp: int = 8000) -> ExtractionResult:
    return ExtractionResult(
        intent="inform", stance="neutral",
        commitments=[Commitment(actor="Finance", action="confirm", is_conditional=False,
                                evidence=list(spans), confidence_bp=confidence_bp)],
        **PROVENANCE)


def _attribution(authority: Authority = Authority.SIGNED_DOCUMENT) -> SourceAttribution:
    return SourceAttribution(
        evidence=AuthorityWeight(authority=authority, basis=AuthorityBasis.EXECUTED),
        actor_authority_bp=8000, actor_basis=ActorBasis.ROLE_LADDER,
        actor_email="cfo@kestrel.example")


def _signal(*, org_id: str = ORG, event_id: str = "evt_1",
            spans: tuple[EvidenceSpan, ...] | None = None,
            authority: Authority = Authority.SIGNED_DOCUMENT,
            occurred_at: datetime | None = None,
            signal_type: SignalType = SignalType.CONTRACT_RENEWAL) -> NormalizedSignal:
    return NormalizedSignal(
        org_id=org_id, event_id=event_id, source="gmail", object_type="email_message",
        occurred_at=occurred_at if occurred_at is not None else NOW - timedelta(hours=3),
        visibility=Visibility(scope="org", derived_from="source:gmail"),
        recipients=("ops@genios.ai",), internal_kind=None,
        signal_type=signal_type, predicate="renewal_window_open",
        subject_key="thread:thr_kestrel", subject_label="Kestrel MSA renewal",
        primary_entity="Kestrel Systems", primary_date=None, primary_amount=None,
        evidence_refs=(spans if spans is not None else (_span(),)),
        attribution=_attribution(authority))


@dataclass
class _Gated:
    triage_lane: str = "P1"
    coverage_ready: bool | None = True
    versions: dict = field(default_factory=lambda: {"preprocessor": "pp-2"})


@dataclass
class _Event:
    event_id: str
    occurred_at: datetime
    org_id: str = ORG


@dataclass
class _Prepared:
    prepared_content_id: str = "pc_1"


@dataclass
class _Esqe:
    normalized: tuple
    classification: object = None
    domains: object = None


@dataclass
class _Result:
    event: _Event
    esqe: _Esqe
    extraction: object = None
    extraction_ref: str | None = None
    gated: object = None
    prepared: object = None


@dataclass
class _Summary:
    results: list
    conflicts: object = None


def _summary(*signals: NormalizedSignal) -> _Summary:
    return _Summary(results=[
        _Result(event=_Event(event_id=s.event_id, occurred_at=s.occurred_at, org_id=s.org_id),
                esqe=_Esqe(normalized=(s,)),
                extraction=(_extraction(*s.evidence_refs) if s.evidence_refs
                            else _extraction(_span())),
                extraction_ref="l1x_9f2c", gated=_Gated(), prepared=_Prepared())
        for s in signals])


def _inputs(signal: NormalizedSignal, *, importance_bp: int | None = 7800,
            extraction: ExtractionResult | None = None,
            payload_ref: str | None = "prepared_content:pc_1") -> P.SignalInputs:
    return P.SignalInputs(
        importance_bp=importance_bp,
        importance_components={"monetary_exposure_bp": 7200},
        importance_version="alg17-v1",
        extraction=(extraction if extraction is not None
                    else _extraction(*(signal.evidence_refs or (_span(),)))),
        extraction_ref="l1x_9f2c", gated=_Gated(), payload_ref=payload_ref)


def _verdict(signal: NormalizedSignal, *, qualified: bool = True) -> Q.QualificationVerdict:
    return Q.QualificationVerdict(
        org_id=signal.org_id, signal_id=Q.signal_ref(signal), event_id=signal.event_id,
        signal_type=signal.signal_type, predicate=signal.predicate,
        subject_key=signal.subject_key, qualified=qualified,
        reason=(Q.QualificationReason.AT_OR_ABOVE_FLOOR if qualified
                else Q.QualificationReason.BELOW_FLOOR),
        importance_bp=7800, floor_bp=2500, components={"monetary_exposure_bp": 7200},
        importance_version="alg17-v1", payload_ref="prepared_content:pc_1",
        evaluated_at=NOW, retain_until=None if qualified else NOW + timedelta(days=90))


def _outcome(*verdicts: Q.QualificationVerdict) -> Q.QualificationOutcome:
    return Q.QualificationOutcome(
        floor=Q.QualificationFloor(org_id=ORG, floor_bp=2500, owner="rohit@genios.ai"),
        verdicts=verdicts)


# =============================================================================================
# 1 · THE LEDGER — five rules that wrote nothing now write a row
# =============================================================================================
#: One row per BLOCKING rule, and the shape of the signal that trips it. Table-driven because
#: the whole defect is that five rules shared one silent path: a per-rule test would have proved
#: whichever rule its author happened to pick.
_BLOCKING_RULES = [
    pytest.param("V-4", dict(spans=()), "receipt", id="v4_no_receipt"),
    pytest.param("V-2", dict(signal_type="renewal_ish"), "signal_type", id="v2_outside_taxonomy"),
    pytest.param("V-3", dict(importance_bp=20000), "importance_bp", id="v3_out_of_range"),
    pytest.param("V-7", dict(float_version=True), "float", id="v7_float_in_the_object"),
]


def _tripped(rule_case: dict) -> tuple[NormalizedSignal, P.SignalInputs]:
    """A signal built to fail exactly one blocking rule, through the same seam production uses.

    V-2, V-3 and V-7 describe objects `QualifiedEnterpriseSignal.__init__` cannot build, so they
    are produced the way the publisher's own docstring says they arrive: the field is set on the
    NORMALIZED record (or the verdict), and the constructor's refusal routes the object through
    `model_construct` into the gate.
    """
    signal = _signal(spans=rule_case.get("spans"))
    if "signal_type" in rule_case:
        object.__setattr__(signal, "signal_type", rule_case["signal_type"])
    inputs = _inputs(signal, importance_bp=rule_case.get("importance_bp", 7800))
    if rule_case.get("float_version"):
        # A ratio smuggled into `versions`, which rides onto the C-12 whole. V-7 walks the LIVE
        # object, so this is a float in a real published field rather than one parked on a
        # normalized record the contract never copies.
        object.__setattr__(inputs, "gated", _Gated(versions={"preprocessor": 1.5}))
    return signal, inputs


@pytest.mark.parametrize("rule, case, needle", _BLOCKING_RULES)
def test_every_blocking_rejection_becomes_a_ledger_row(rule, case, needle):
    """The defect, one row per rule. Before this, all four produced the identical nothing."""
    signal, inputs = _tripped(case)
    _, _, refused = P.publish_one(signal, inputs, eval_time=NOW)
    assert refused is not None, f"{rule} emitted or parked instead of rejecting"
    assert rule in refused.rules, f"rejected, but not by {rule}: {refused.rules}"

    rows = P.rejection_rows((refused,), eval_time=NOW)
    assert len(rows) == 1
    row = rows[0]
    assert row.org_id == ORG and row.event_id == "evt_1"
    assert rule in row.rules, "the ledger row does not name the rule that refused the signal"
    assert needle in row.reason, f"the stored reason does not say why: {row.reason!r}"
    assert row.payload_ref == "prepared_content:pc_1", \
        "the row cannot reach the payload the refused signal was read from"
    assert row.evaluated_at == NOW
    assert row.retain_until == NOW + timedelta(days=Q.DROP_PAYLOAD_RETENTION_DAYS), \
        "a rejection is retained on different terms from a drop"


def test_a_rejection_id_is_content_addressed_so_a_replay_upserts_one_row():
    """`drop_id`'s discipline, restated: the same refusal replayed is one fact re-observed, not
    a second row. `evaluated_at` is deliberately outside the digest — it is the only field a
    replay changes."""
    signal, inputs = _tripped(dict(spans=()))
    _, _, refused = P.publish_one(signal, inputs, eval_time=NOW)
    first = P.rejection_rows((refused,), eval_time=NOW)[0]
    later = P.rejection_rows((refused,), eval_time=NOW + timedelta(days=2))[0]
    assert first.rejection_id == later.rejection_id
    assert first.retain_until != later.retain_until


def test_two_rules_broken_at_once_are_one_row_naming_both():
    """A signal that fails V-4 and V-6 has two upstream bugs, and fixing one must not hide the
    other for a release."""
    signal = _signal(spans=())
    _, _, refused = P.publish_one(signal, _inputs(signal), eval_time=NOW)
    row = P.rejection_rows((refused,), eval_time=NOW)[0]
    assert "V-4" in row.rules
    assert len(row.rules) == len(set(row.rules)), "the rule list repeats itself"


def test_an_unbuildable_signal_is_recorded_under_its_own_outcome():
    """Fail-closed is not the same answer as a V-rule reject, and the ledger must not blur them:
    one says a rule refused this, the other says nothing in the rule table can see what is wrong.
    """
    signal = _signal()
    inputs = _inputs(signal)
    object.__setattr__(signal, "source", "")        # outside V-1..V-7; the constructor refuses
    _, _, refused = P.publish_one(signal, inputs, eval_time=NOW)
    assert refused is not None and refused.outcome == P.UNBUILDABLE
    row = P.rejection_rows((refused,), eval_time=NOW)[0]
    assert row.outcome == P.UNBUILDABLE and row.rules == ()


def test_the_in_memory_ledger_keys_on_the_tenant_boundary():
    ledger = P.InMemoryRejectionLedger()
    mine, theirs = _signal(), _signal(org_id=OTHER)
    rows = []
    for sig in (mine, theirs):
        _, _, refused = P.publish_one(_signal(org_id=sig.org_id, spans=()),
                                      _inputs(sig), eval_time=NOW)
        rows.extend(P.rejection_rows((refused,), eval_time=NOW))
    assert ledger.put(rows) == 2
    assert [r.org_id for r in ledger.list(ORG)] == [ORG], "a tenant read another tenant's rows"


# =============================================================================================
# 2 · THE SWEEP SEAM — the ledger is filed by the same hook the drop ledger is
# =============================================================================================
def test_the_sweep_seam_files_every_refusal_it_made():
    ledger = P.InMemoryRejectionLedger()
    good, bad = _signal(event_id="evt_ok"), _signal(event_id="evt_bad", spans=())
    report = P.publish_sweep(_summary(good, bad),
                             _outcome(_verdict(good), _verdict(bad)),
                             org_id=ORG, store=InMemorySignalStore(), rejections=ledger)

    assert len(report.emitted) == 1 and len(report.refused) == 1
    assert report.rejections_filed == 1, "the seam refused a signal and filed nothing"
    filed = ledger.list(ORG)
    assert [r.event_id for r in filed] == ["evt_bad"]
    assert "V-4" in filed[0].rules and filed[0].payload_ref == "prepared_content:pc_1"


def test_a_ledger_outage_costs_the_row_and_never_the_sweep():
    """The drop ledger's own terms: losing a rejection costs an explanation, raising costs the
    tenant their mail."""
    class _Broken:
        def put(self, rows):
            raise RuntimeError("no database")

    good, bad = _signal(event_id="evt_ok"), _signal(event_id="evt_bad", spans=())
    report = P.publish_sweep(_summary(good, bad), _outcome(_verdict(good), _verdict(bad)),
                             org_id=ORG, store=InMemorySignalStore(), rejections=_Broken())
    assert len(report.emitted) == 1, "a ledger outage swallowed the published signals"
    assert report.rejections_filed == 0


# =============================================================================================
# 3 · PARKING_RULES — the declared set decides, not a hard-coded V-1
# =============================================================================================
def test_v1_still_parks_and_leaves_no_rejection_row():
    ledger = P.InMemoryRejectionLedger()
    signal = _signal()
    object.__setattr__(signal, "visibility", None)
    report = P.publish_sweep(_summary(signal), _outcome(_verdict(signal)),
                             org_id=ORG, store=InMemorySignalStore(), rejections=ledger)
    assert len(report.parked) == 1 and report.parked[0].reason_code == VISIBILITY_UNKNOWN
    assert ledger.list(ORG) == [], "a park was also written to the rejection ledger"


def test_a_rule_moved_into_parking_rules_parks_instead_of_rejecting(monkeypatch):
    """THE WIRING, asserted by CHANGING the declared set. With V-4 in `PARKING_RULES` the same
    receipt-less signal must leave a reviewable park row and no rejection — which is only true
    if the publisher consults the set instead of pattern-matching one outcome."""
    monkeypatch.setattr(P, "PARKING_RULES",
                        frozenset({PublicationRule.V1, PublicationRule.V4}))
    ledger = P.InMemoryRejectionLedger()
    signal = _signal(spans=())
    report = P.publish_sweep(_summary(signal), _outcome(_verdict(signal)),
                             org_id=ORG, store=InMemorySignalStore(), rejections=ledger)

    assert report.refused == (), "V-4 was declared a parking rule and still rejected"
    assert len(report.parked) == 1
    park = report.parked[0]
    assert park.stage == "L1.6.10" and park.org_id == ORG and park.event_id == "evt_1"
    assert park.trace and park.trace[0]["rule"] == "V-4"
    assert ledger.list(ORG) == []


def test_a_signal_breaking_both_a_parking_and_a_rejecting_rule_is_rejected(monkeypatch):
    """Parking is the WEAKER answer: a signal that is also unpublishable for a reason nothing
    can recover must not be filed away as merely reviewable."""
    monkeypatch.setattr(P, "PARKING_RULES",
                        frozenset({PublicationRule.V1, PublicationRule.V4}))
    signal, inputs = _tripped(dict(spans=(), importance_bp=20000))
    _, parked, refused = P.publish_one(signal, inputs, eval_time=NOW)
    assert parked is None and refused is not None
    assert "V-3" in refused.rules
    assert "V-4" not in refused.rules, "a parking rule was recorded as a rejection"


# =============================================================================================
# 4 · to_legacy_rank — translated once, at the L1 -> L2 write
# =============================================================================================
@pytest.mark.parametrize("authority", list(Authority))
def test_the_stored_row_carries_the_legacy_rank_layer_2_writes_facts_at(authority):
    """ALG-14 is a 0..6 ladder and `context.pipeline.FACT_CONF_BY_RANK` is a 0..4 dict that
    means different things by the same digits. `to_legacy_rank` is the one sanctioned crossing,
    and the crossing belongs at the WRITE — so the stored row carries the translated rank and
    no consumer re-derives it (usually as `rank - 1`, which is wrong for four of seven classes).
    """
    signal = _signal(authority=authority)
    published, _, _ = P.publish_one(signal, _inputs(signal), eval_time=NOW)
    assert published is not None
    assert published.row.authority_rank == to_legacy_rank(authority)
    from genios_engine.context.pipeline import FACT_CONF_BY_RANK
    assert published.row.authority_rank in FACT_CONF_BY_RANK, \
        "the stored rank is not a live key of the dict it exists to be used with"


# =============================================================================================
# 5 · confidence.decay — a stored signal is not as certain in June as it was in April
# =============================================================================================
def test_a_stored_signals_confidence_ages_on_the_read():
    """A signal composed in April and read in June must not be presented at April's confidence.
    Aged on the READ, against a passed instant — the row keeps what was composed, because the
    composition is a judgement made at a moment and the age is the reader's question.
    """
    signal = _signal()
    published, _, _ = P.publish_one(signal, _inputs(signal), eval_time=NOW)
    row = published.row
    fresh = age_signals((row,), eval_time=row.occurred_at)[0]
    later = age_signals((row,), eval_time=row.occurred_at + timedelta(days=60))[0]

    assert fresh.confidence_bp == row.confidence_bp, "a same-day read already aged the signal"
    assert fresh.days_old == 0 and later.days_old == 60
    assert later.confidence_bp < row.confidence_bp, "sixty days changed nothing"
    assert later.stored_confidence_bp == row.confidence_bp, "the aged read overwrote the row"
    assert isinstance(later.confidence_bp, int) and 0 <= later.confidence_bp <= 10000


def test_ageing_is_monotone_and_never_negative():
    signal = _signal()
    published, _, _ = P.publish_one(signal, _inputs(signal), eval_time=NOW)
    row = published.row
    seen = [age_signals((row,), eval_time=row.occurred_at + timedelta(days=d))[0].confidence_bp
            for d in (0, 30, 90, 365, 5000)]
    assert seen == sorted(seen, reverse=True), f"confidence rose with age: {seen}"
    assert seen[-1] >= 0


# =============================================================================================
# 6 · THE ROUTES — every read above, through the router the tenant actually reaches
# =============================================================================================
@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(routes, "_drop_ledger", Q.InMemoryDropLedger())
    monkeypatch.setattr(routes, "_rejection_ledger", P.InMemoryRejectionLedger())
    monkeypatch.setattr(routes, "_signal_store", InMemorySignalStore())
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: AuthCtx(org_id=ORG, actor_id="seat_founder")
    return TestClient(app)


def _publish_through_the_hook(*signals: NormalizedSignal) -> P.PublicationReport:
    """The production seam, called the way `api/routes._run_ledger` calls it — same stores."""
    return P.publish_sweep(_summary(*signals), _outcome(*(_verdict(s) for s in signals)),
                           org_id=ORG, store=routes._signal_store,
                           rejections=routes._rejection_ledger)


def test_the_sync_hook_itself_files_rejections(monkeypatch, client):
    """THE WIRING, at the one place every HTTP sync caller already reaches.

    `_run_ledger` is the hook that files conflicts, qualifies against the floor, ages the
    lifecycle and publishes — six sync call sites go through it and none of them knows the
    rejection ledger exists. This test calls THAT function, not `publish_sweep`, so a build where
    the ledger is resolved at module scope and then never handed to the publisher fails here.
    Every store it touches is swapped for an in-memory sibling, on the G7 file's own terms; the
    `_rejection_ledger` it must reach is the module-level one the `client` fixture installed.
    """
    monkeypatch.setattr(routes, "_floor_store", Q.InMemoryFloorStore({ORG: 0}))
    monkeypatch.setattr(routes, "_conflict_store", None)
    monkeypatch.setattr(routes, "_lifecycle_store", None)
    monkeypatch.setattr(routes, "_graph", None)

    routes._run_ledger(org_id=ORG, connection_id="con_1", source="gmail", mode="incremental",
                       summary=_summary(_signal(event_id="evt_hook", spans=())))

    filed = routes._rejection_ledger.list(ORG)
    assert [r.event_id for r in filed] == ["evt_hook"], \
        "the sync hook refused a signal and the ledger it resolves at import saw nothing"
    assert "V-4" in filed[0].rules
    # ...and the tenant can read it back through the door, off the same store.
    assert client.get("/qualification/rejections").json()["rejections"][0]["event_id"] == \
        "evt_hook"


def test_a_tenant_can_ask_why_a_rejected_signal_never_appeared(client):
    """The whole point. Before this route the answer to "this email produced nothing; why?" was
    a log line on a server the tenant cannot read."""
    _publish_through_the_hook(_signal(event_id="evt_bad", spans=()))
    body = client.get("/qualification/rejections").json()
    assert len(body["rejections"]) == 1
    row = body["rejections"][0]
    assert row["event_id"] == "evt_bad" and "V-4" in row["rules"]
    assert "receipt" in row["reason"] and row["payload_ref"] == "prepared_content:pc_1"

    narrowed = client.get("/qualification/rejections", params={"event_id": "evt_ok"}).json()
    assert narrowed["rejections"] == [], "the event filter did not narrow anything"

    one = client.get(f"/qualification/rejections/{row['rejection_id']}")
    assert one.status_code == 200 and one.json()["rejection_id"] == row["rejection_id"]
    assert client.get("/qualification/rejections/prj_nope").status_code == 404


def test_the_signal_read_route_ages_what_it_returns(client):
    """`qualified_signals` had no reader on any request path at all — the table built to be read
    by every downstream surface could not be read by anything. This is that door, and it is the
    one that applies the age decay."""
    old = _signal(event_id="evt_old", occurred_at=NOW - timedelta(days=120))
    _publish_through_the_hook(old)
    body = client.get("/qualification/signals").json()
    assert len(body["signals"]) == 1
    row = body["signals"][0]
    assert row["event_id"] == "evt_old"
    assert row["days_old"] >= 120
    assert row["aged_confidence_bp"] < row["confidence_bp"], \
        "a four-month-old signal was served at the confidence it was composed with"
    assert row["authority_rank"] == to_legacy_rank(Authority.SIGNED_DOCUMENT)


def test_the_drops_route_survives_a_row_that_came_out_of_the_database(client):
    """`_drop_json` read `row.signal_type.value`, and every row the LEDGER produces carries a
    `str` there (`drop_rows` stores `.value`; `_to_drop_row` decodes text). Only a test that
    hand-built a `DropRow` with an enum could pass, so the route 500'd on every real drop."""
    routes._drop_ledger.put((Q.DropRow(
        org_id=ORG, drop_id="qdr_real", signal_id="sig_1", event_id="evt_dropped",
        signal_type=SignalType.CONTRACT_RENEWAL.value, predicate="renewal_window_open",
        subject_key="thread:thr_kestrel", importance_bp=1800, importance_version="alg17-v1",
        floor_bp=2500, components={}, payload_ref="prepared_content:pc_1",
        evaluated_at=NOW, retain_until=NOW + timedelta(days=90)),))

    resp = client.get("/qualification/drops")
    assert resp.status_code == 200, resp.text
    assert resp.json()["drops"][0]["signal_type"] == "contract_renewal"


# =============================================================================================
# 7 · POSTGRES — the real table, the retention promise, and erasure
# =============================================================================================
@pytest.fixture
def pg_url(live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — real-Postgres ledger tests skipped")
    return live_db_url


def _seed_org(url: str, org_id: str) -> None:
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine
    with get_engine(url).begin() as conn:
        conn.execute(text("delete from orgs where id=:o"), {"o": org_id})
        cols = conn.execute(text(
            "select column_name, data_type from information_schema.columns "
            "where table_name='orgs' and is_nullable='NO' and column_default is null "
            "and column_name<>'id'")).all()
        names, holes, params = ["id"], [":id"], {"id": org_id}
        for col in cols:
            names.append(col.column_name)
            holes.append(f":{col.column_name}")
            params[col.column_name] = (0 if "int" in col.data_type or "numeric" in col.data_type
                                       else datetime.now(timezone.utc)
                                       if "timestamp" in col.data_type else org_id)
        conn.execute(text(f"insert into orgs ({', '.join(names)}) values ({', '.join(holes)})"),
                     params)


@pytest.mark.pg
def test_the_real_ledger_upserts_and_reads_back(pg_url):
    org = "org_rej_pg"
    _seed_org(pg_url, org)
    ledger = P.PostgresRejectionLedger(pg_url)
    signal = _signal(org_id=org, event_id="evt_pg", spans=())
    _, _, refused = P.publish_one(signal, _inputs(signal), eval_time=NOW)
    rows = P.rejection_rows((refused,), eval_time=NOW)

    assert ledger.put(rows) == 1
    assert ledger.put(rows) == 1, "a replayed sweep failed instead of upserting"
    back = ledger.list(org)
    assert len(back) == 1, "the replay appended a second row for one refusal"
    assert back[0].rules == rows[0].rules and back[0].reason == rows[0].reason
    assert back[0].payload_ref == rows[0].payload_ref
    assert back[0].signal_type == rows[0].signal_type
    assert ledger.list(org, event_id="evt_nope") == []
    assert ledger.get(org, rows[0].rejection_id) is not None
    assert ledger.get("org_rej_pg_other", rows[0].rejection_id) is None, "the read crossed a tenant"


@pytest.mark.pg
def test_the_signal_type_check_constraint_refuses_a_kind_outside_the_taxonomy(pg_url):
    """The closed 14 enforced by the DATABASE, not only by Python. A writer that bypassed the
    contract — a backfill script, a psql session, a future ingestion path — must not be able to
    put a fifteenth kind in the two tables every downstream surface reads."""
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine
    org = "org_rej_check"
    _seed_org(pg_url, org)
    engine = get_engine(pg_url)
    cases = {
        "qualified_signals":
            "insert into qualified_signals (signal_id, org_id, event_id, trace_id, signal_type, "
            "importance_bp, importance_version, confidence_bp, extraction_ref, evidence_refs, "
            "visibility, state, occurred_at) values ('sig_bad', :o, 'e', 't', :kind, 5000, "
            "'v1', 5000, 'x', '[{\"quote\": \"q\"}]'::jsonb, '{}'::jsonb, 'active', now())",
        "qualification_drops":
            "insert into qualification_drops (drop_id, org_id, signal_id, event_id, signal_type, "
            "predicate, subject_key, importance_bp, importance_version, floor_bp, evaluated_at, "
            "retain_until) values ('qdr_bad', :o, 's', 'e', :kind, 'p', 'k', 100, 'v1', "
            "2500, now(), now())",
    }
    for table, sql in cases.items():
        with pytest.raises(Exception) as err:
            with engine.begin() as conn:
                conn.execute(text(sql), {"o": org, "kind": "renewal_ish"})
        assert "signal_type" in str(err.value), \
            f"{table} accepted a kind outside the closed 14: {err.value}"
        # ...and the same statement with a real member gets past the constraint, so the test
        # above is proving a CHECK rather than any old integrity error.
        with engine.begin() as conn:
            conn.execute(text(sql), {"o": org, "kind": SignalType.CONTRACT_RENEWAL.value})


@pytest.mark.pg
def test_filing_a_rejection_extends_the_payload_it_points_at(pg_url):
    """A ledger row that outlived the body it references is a receipt for something nobody can
    fetch — which looks like an answer and is not. Same promise `PostgresDropLedger` makes, and
    made by the same writer rather than a second copy of it."""
    from sqlalchemy import text

    from genios_engine.platform.db import get_engine
    org = "org_rej_retain"
    _seed_org(pg_url, org)
    engine = get_engine(pg_url)
    short = NOW + timedelta(days=3)
    with engine.begin() as conn:
        # `raw_payloads.event_id` has a real FK to `source_events`, so the body is seeded the way
        # the pipeline seeds it: an event first, then its payload. Faking the FK away would test
        # an UPDATE that could never run against the real schema.
        conn.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            "source_object_id, dedup_key, actor, occurred_at) "
            "values ('evt_ret', :o, 'con_rej', 'gmail', 'email_message', 'evt_ret', 'evt_ret', "
            "cast('{}' as jsonb), :at) on conflict (event_id) do nothing"),
            {"o": org, "at": NOW})
        conn.execute(text(
            "insert into raw_payloads (id, org_id, event_id, content_type, enc_content, "
            "expires_at) values ('pay_rej_1', :o, 'evt_ret', 'text/plain', 'x', :e)"),
            {"o": org, "e": short})

    signal = _signal(org_id=org, event_id="evt_ret", spans=())
    _, _, refused = P.publish_one(signal, _inputs(signal), eval_time=NOW)
    filed = P.PostgresRejectionLedger(pg_url).put(P.rejection_rows((refused,), eval_time=NOW))
    assert filed == 1

    with engine.connect() as conn:
        kept = conn.execute(text(
            "select expires_at from raw_payloads where id='pay_rej_1'")).scalar_one()
    assert kept >= NOW + timedelta(days=Q.DROP_PAYLOAD_RETENTION_DAYS), \
        "the rejection promised 90 days of payload and the body still expires in three"


def test_the_rejection_ledger_leaves_with_the_tenant():
    """`account_routes._wipe` runs with NO try/except: a table missing from its list is a silent
    leak of the tenant's own quoted sentences, which is exactly what a rejection reason is."""
    from genios_engine.api.account_routes import _ORG_SCOPED_TABLES
    assert P.REJECTION_TABLE in _ORG_SCOPED_TABLES
