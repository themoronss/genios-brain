"""The woken roster on the LIVE path: twenty units into one tenant's persisted reasoning audit.

`test_roster_v2.py` proves the roster against a real compiled package in memory, and
`test_unit_reachability_report.py` measures it through the gate command in shadow. This proves the
last hop — that what the roster produced is what the audit store actually holds, because a run
whose extra eighteen units never reach `reasoning_reasoner_results` has not woken anything a human
or a replay can ever see.

Real Postgres, real Layer 1 ingestion, real corpus, real reasoning, `live=True`. The seeding
helpers are the ones `test_weld_reaches_a_signal.py` already uses for this same lane, imported
rather than copied so the two cannot drift about what an admin tenant looks like.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from genios_engine.context import situations

from ...l1_supply import attach_l1_signals
from ...test_admin_support_packs import NOW, _run_admin, _seed_org

pytestmark = pytest.mark.pg

_UNITS_WITH_FINDINGS = (
    "select r.reasoner_id, r.status, r.output from reasoning_reasoner_results r "
    "join reasoning_runs u on u.org_id = r.org_id and u.run_id = r.run_id "
    "where r.org_id = :o and u.capability_id like 'expertise.%'")


def _run(pg_store, org: str, *, roster_v2: bool) -> None:
    from genios_engine.packs.wiring import ensure_defaults, make_registry
    from genios_engine.platform.l4_activation import activate
    from genios_engine.reason.domain_shadow import shadow_compile

    _seed_org(pg_store, org)
    with pg_store.engine.begin() as conn:
        conn.execute(text("delete from signals where org_id = :o"), {"o": org})
    # ORG-SCOPED EVENT ID. `source_events_pkey` is `(event_id)`, not `(org_id, event_id)`, and
    # `_seed_event` inserts `on conflict do nothing` — so with `_run_admin`'s constant default
    # only the FIRST org seeded on a database ever gets a `source_events` row, and every later
    # tenant silently scores `source_count = 0` in `situations.evidence_score`.
    _run_admin(pg_store, org, event_id=f"adm_evt_{org}")
    situations.refresh_situations(pg_store, org, eval_time=NOW)
    # LAYER 1's OWN SUPPLY, which this tenant never had. L2's admission gate refuses a situation
    # carrying no verified evidence span, and a verified span is only ever published on a
    # `qualified_signals` row — so before this line every situation here was HELD and the roster
    # under test reasoned about nothing. Scored, because this file's subject is the ACTIVATED
    # tenant; the unscored supply is exercised in `tests/reason/test_ranking_activation.py`.
    assert attach_l1_signals(pg_store, org, eval_time=NOW) > 0
    if roster_v2:
        activate(pg_store.engine, org, feature="roster_v2", by="test")
    registry = make_registry(pg_store.engine.url.render_as_string(hide_password=False))
    ensure_defaults(registry, org)
    counts = shadow_compile(store=pg_store, org_id=org, eval_time=NOW, live=True,
                            registry=registry)
    assert counts.get("reasoned", 0) > 0, dict(counts)
    assert counts.get("roster_v2", 0) == int(roster_v2), dict(counts)


def _results(pg_store, org: str) -> dict[str, tuple[str, int]]:
    with pg_store.engine.connect() as conn:
        rows = conn.execute(text(_UNITS_WITH_FINDINGS), {"o": org}).mappings().all()
    out: dict[str, tuple[str, int]] = {}
    for row in rows:
        output = row["output"]
        if isinstance(output, str):
            output = json.loads(output)
        findings = len((output or {}).get("findings") or [])
        status, held = row["status"], out.get(row["reasoner_id"])
        out[row["reasoner_id"]] = (status, max(findings, held[1] if held else 0))
    return out


def test_the_activated_tenants_audit_holds_the_whole_roster_not_six_units(pg_store):
    org = "pk_roster_live"
    _run(pg_store, org, roster_v2=True)

    results = _results(pg_store, org)

    assert len(results) >= 15, sorted(results)
    emitting = {unit for unit, (_status, findings) in results.items() if findings}
    assert len(emitting) >= 12, sorted(emitting)
    # The units doc 02 records as never having run anywhere, now in a tenant's own audit rows.
    for unit_id in ("core.cost", "core.tradeoff", "core.validation", "core.recommendation",
                    "core.alternative", "core.timeline", "core.dependency"):
        assert unit_id in results, sorted(results)


def test_an_unactivated_tenant_persists_exactly_the_six_it_persists_today(pg_store):
    """The gate is per tenant and it fails closed: nothing about a tenant nobody switched on
    changes, including the rows its decisions leave behind."""
    org = "pk_roster_live_dark"
    _run(pg_store, org, roster_v2=False)

    assert set(_results(pg_store, org)) == {
        "core.context", "core.risk", "core.constraint", "core.priority", "core.confidence",
        "core.planning"}


def test_the_skips_the_selector_made_are_in_the_tenants_audit_rows(pg_store):
    """The receipts survive the persistence boundary.

    A woken roster drops what a situation cannot feed, and the answer to "why did `core.temporal`
    not run here?" has to be readable from the audit rather than only from the process that is
    long gone. Each dropped unit lands as a `skipped` row carrying the planner's reason code and
    the fields that were absent.
    """
    org = "pk_roster_receipts"
    _run(pg_store, org, roster_v2=True)

    with pg_store.engine.connect() as conn:
        rows = conn.execute(text(
            "select reasoner_id, status, skip_reason_code, output from "
            "reasoning_reasoner_results where org_id=:o and status='skipped'"),
            {"o": org}).mappings().all()

    assert rows, "this tenant carries no dates or money; the selector must have dropped something"
    for row in rows:
        assert row["skip_reason_code"] in {"no_declared_input_available",
                                           "dependency_not_scheduled"}
        output = row["output"]
        if isinstance(output, str):
            output = json.loads(output)
        assert output["missing_fields"], row["reasoner_id"]


def test_a_compiled_bundle_verifies_end_to_end(pg_store):
    """CLOSED IN WAVE Z3, and worth recording how long it was open.

    This was an xfail: `ReasoningDecision.to_semantic_dict` gained `citations` and
    `constraints_applied` in wave Y1's weld, and both enter the decision hash when carried — but
    `audit._output` never wrote them into `decision_core` and
    `store._verify_replay_bundle`'s `contract_decision` reconstruction never read them back. Every
    COMPILED decision carries both, so from the day the weld landed no compiled bundle verified,
    with the roster awake or asleep. Z3 was about to add two more conditional fields
    (`ranking_weights_version`, `do_nothing`) through the same gap, so the round trip is now
    written and read for all five — see the comments at both sites.
    """
    from genios_engine.reason.store import ReasoningStore

    org = "pk_roster_replay"
    _run(pg_store, org, roster_v2=True)
    store = ReasoningStore(engine=pg_store.engine)
    with pg_store.engine.connect() as conn:
        run_ids = conn.execute(text(
            "select run_id from reasoning_runs where org_id=:o and capability_id like "
            "'expertise.%'"), {"o": org}).scalars().all()
    assert run_ids

    for run_id in run_ids:
        store.verify_replay_bundle(store.load_replay_bundle(org_id=org, run_id=run_id),
                                   org_id=org)


def test_the_writer_refuses_a_bundle_whose_unscheduled_unit_carries_no_receipt(pg_store,
                                                                              monkeypatch):
    """The same rule the replay verifier enforces, enforced again by the writer.

    Two independent proofs of one law, which is how this module already treats its guards: a row
    that could be written without a receipt would be a silence nobody could catch afterwards,
    because afterwards is when the only copy of the reason is gone.
    """
    from genios_engine.contracts.reasoning import ReasonerResult, ResultStatus
    from genios_engine.reason import audit
    from genios_engine.reason.store import ReasoningStore, ReasoningStoreError

    from ..test_selected_runs_are_auditable import _selected_execution

    execution = _selected_execution()
    _seed_org(pg_store, execution.request.org_id)
    original = audit._audited_results

    def receiptless(subject):
        return [(ReasonerResult(reasoner_id=result.reasoner_id,
                                reasoner_version=result.reasoner_version,
                                status=ResultStatus.SKIPPED), input_hash)
                if result.status is ResultStatus.SKIPPED else (result, input_hash)
                for result, input_hash in original(subject)]

    monkeypatch.setattr(audit, "_audited_results", receiptless)

    with pytest.raises(ReasoningStoreError, match="carries no skip receipt"):
        audit.persist_execution(store=ReasoningStore(engine=pg_store.engine),
                                execution=execution)
