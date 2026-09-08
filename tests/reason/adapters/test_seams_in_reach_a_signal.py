"""WAVE Z5 · THE INBOUND SEAMS ON THE LIVE PATH — the K5 rows, in the database.

`test_seams_in.py` proves both seams against the real kernel in memory. This proves the last hop:
that what the projection built and what the corpus doctrine decided are what the AUDIT STORE
actually holds and what `signals.rejected_candidates` — rendered by the API as
`alternatives_rejected` — actually carries.

Real Postgres, real Layer 1 ingestion through `process_event`, the production derived block in
production order, the real situation refresh, `shadow_compile(live=True)`. The tenant is seeded by
`l3_pilot_seed`, which exists because the shortcut fixtures leave out exactly the passes that make
a corpus rule able to fire — imported rather than copied so the two lanes cannot drift about what
an admin tenant looks like.

WHY THIS FILE AND NOT AN ASSERTION ADDED TO THE L3 TEST. `test_l3_pilot_report` proves the
elimination reaches a signal; what wave Z5 changed is WHO MAY CLAIM one (`rule_compiler.
_policy_eliminated`) and what else now rides in the snapshot (the projection). Both are properties
of a run that already had a green test, so they need their own failing-without-them assertions
rather than a stronger sentence in someone else's.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from genios_engine.reason.adapters import situation_projection as sp
from genios_engine.reason.adapters.rule_compiler import POLICY_BLOCK_REASON

from .l3_pilot_seed import BLOCKING_RULE, ELIMINATED_PLAY, seed_admin_pilot

pytestmark = pytest.mark.pg


def _seed(pg_store, org: str, *, roster_v2: bool) -> dict:
    from genios_engine.platform.l4_activation import activate

    if roster_v2:
        # Activated BEFORE the compile, because `shadow_compile` reads the switch once per pass.
        # `seed_admin_pilot` seeds the org row itself, so the FK parent exists by the time this
        # writes — and `activate` is idempotent on a live row, which is what makes this file
        # re-runnable on one database.
        from ...test_admin_support_packs import _seed_org
        _seed_org(pg_store, org)
        activate(pg_store.engine, org, feature="roster_v2", by="test_seams_in")
    with pg_store.engine.begin() as conn:
        # `_emit_capability_signal` inserts `on conflict do nothing`, so a second run against a
        # database that already holds this org's open signal emits nothing and every assertion
        # below would fail for a reason that has nothing to do with the seams.
        conn.execute(text("delete from signals where org_id = :o"), {"o": org})
    return seed_admin_pilot(pg_store, org, build_cards=False)


def _eliminations(pg_store, org: str) -> list[tuple[dict, dict]]:
    with pg_store.engine.connect() as conn:
        rows = conn.execute(text(
            "select play, rejected_candidates from signals where org_id = :o"),
            {"o": org}).mappings().all()
    out: list[tuple[dict, dict]] = []
    for row in rows:
        rejected = row["rejected_candidates"]
        rejected = json.loads(rejected) if isinstance(rejected, str) else (rejected or ())
        for candidate in rejected:
            for elimination in (candidate or {}).get("eliminated_by") or ():
                out.append((candidate, elimination))
    return out


# =================================================================================================
# IN-2 · the rule id travels, and only the rule that removed the option may claim it
# =================================================================================================

def test_the_corpus_rule_id_still_travels_into_alternatives_rejected(pg_store):
    """The K5 row, re-proved through the attribution gate wave Z5 added.

    `constraint_applications` used to join a fired blocking rule to any eliminated candidate its
    scope covered. It now requires the candidate to carry the `tenant_policy_block` check the
    constraint unit stamps on the eliminations it actually performs — so this assertion is no
    longer "a rule fired and a candidate is gone", it is "this rule removed this candidate".
    """
    org = "pk_seams_in_live"
    _seed(pg_store, org, roster_v2=False)

    eliminations = _eliminations(pg_store, org)
    assert eliminations, "no candidate on this tenant was eliminated by authored doctrine"
    candidate, elimination = next(
        (c, e) for c, e in eliminations if e["rule_id"] == BLOCKING_RULE)
    assert candidate["play_id"] == ELIMINATED_PLAY
    assert candidate["disposition"] == "eliminated"
    assert elimination["severity"] == "blocking"
    assert elimination["statement"]


def test_every_elimination_the_database_holds_names_the_check_that_performed_it(pg_store):
    """The attribution property, read off the persisted decision rather than the in-memory one.

    A rule may only claim a candidate whose own stored checks carry the constraint unit's
    elimination. A receipt that reads correctly and is false is worse than no receipt at all, and
    before this the loop below would have found claims with no check behind them.
    """
    org = "pk_seams_in_attribution"
    _seed(pg_store, org, roster_v2=False)

    with pg_store.engine.connect() as conn:
        outputs = conn.execute(text(
            "select o.run_id, o.decision_core from reasoning_run_outputs o "
            "join reasoning_runs u on u.org_id = o.org_id and u.run_id = o.run_id "
            "where o.org_id = :o and u.capability_id like 'expertise.%'"),
            {"o": org}).mappings().all()
        blocked = conn.execute(text(
            "select k.run_id, k.candidate_id from reasoning_candidate_checks k "
            "join reasoning_runs u on u.org_id = k.org_id and u.run_id = k.run_id "
            "where k.org_id = :o and u.capability_id like 'expertise.%' "
            "and k.outcome = 'eliminate' and k.reason_code = :reason"),
            {"o": org, "reason": POLICY_BLOCK_REASON}).mappings().all()
    assert outputs, "the compiled lane persisted no decision"

    claimed_runs: set[str] = set()
    claims = 0
    for row in outputs:
        decision = row["decision_core"]
        decision = json.loads(decision) if isinstance(decision, str) else (decision or {})
        for applied in decision.get("constraints_applied") or ():
            named = applied.get("eliminated_candidate_ids") or ()
            if named:
                claims += len(named)
                claimed_runs.add(str(row["run_id"]))
    assert claims, "no elimination was attributed to a rule on this tenant"

    # The decision names CONTRACT candidate ids and the store keys rows by its own id (see
    # `_emit_capability_signal`'s note on the alias), so the two are compared per RUN rather than
    # by id: every run whose decision claims an elimination must be a run where the constraint
    # policy seam actually eliminated something, and no run may claim more than it performed.
    performed: dict[str, int] = {}
    for row in blocked:
        performed[str(row["run_id"])] = performed.get(str(row["run_id"]), 0) + 1
    assert performed, "nothing was eliminated through the constraint policy seam"
    assert claimed_runs <= set(performed), sorted(claimed_runs - set(performed))
    for run_id in claimed_runs:
        run_claims = 0
        for row in outputs:
            if str(row["run_id"]) != run_id:
                continue
            decision = row["decision_core"]
            decision = json.loads(decision) if isinstance(decision, str) else (decision or {})
            for applied in decision.get("constraints_applied") or ():
                run_claims = max(run_claims, len(applied.get("eliminated_candidate_ids") or ()))
        assert run_claims <= performed[run_id]


# =================================================================================================
# IN-1 · the projection reaches the persisted snapshot, three-state intact
# =================================================================================================

def test_an_activated_tenants_context_payload_carries_layer_2s_own_readings(pg_store):
    """DLG-06 on the live path. The stored context payload is what a replay re-proves and what an
    auditor reads a year later, so a projection that existed only in memory would be a reading no
    decision could ever be re-justified from."""
    org = "pk_seams_in_projection"
    counts = _seed(pg_store, org, roster_v2=True)
    assert counts["compile"].get("roster_v2") == 1, counts["compile"]
    assert counts["compile"].get("projected_situation_facts", 0) > 0, counts["compile"]

    with pg_store.engine.connect() as conn:
        payloads = conn.execute(text(
            "select p.payload from reasoning_context_payloads p "
            "join reasoning_runs u on u.org_id = p.org_id "
            "and u.context_snapshot_id = p.context_snapshot_id "
            "where p.org_id = :o and u.capability_id like 'expertise.%'"),
            {"o": org}).scalars().all()
    assert payloads, "the compiled lane persisted no context payload"

    projected: set[str] = set()
    unknown: set[str] = set()
    for payload in payloads:
        body = json.loads(payload) if isinstance(payload, str) else payload
        projected.update(name for name in (body.get("facts") or {})
                         if name.startswith(sp.SITUATION_NAMESPACE))
        unknown.update(name for name in (body.get("missing_fields") or ())
                       if name.startswith(sp.SITUATION_NAMESPACE))
        for name in projected:
            record = (body.get("facts") or {}).get(name)
            if record is not None:
                assert record["source"] == sp.PROJECTION_SOURCE
    assert projected, "no situation projection reached the stored payload"
    # THREE STATES, on real data: something was read, something was typed unknown, and no name is
    # in both. The last is the one that matters — a field read as a value and as a gap on the same
    # snapshot is the flattening this wave exists to prevent.
    assert unknown, "nothing was typed unknown; the three-state claim is untested here"
    assert not projected & unknown

    # Every projected fact resolves to evidence minted by the one builder, under ONE witness.
    for payload in payloads:
        body = json.loads(payload) if isinstance(payload, str) else payload
        groups = {ref.get("independence_group") for ref in (body.get("evidence") or ())
                  if str(ref.get("field", "")).startswith(sp.SITUATION_NAMESPACE)}
        assert len(groups) <= 1, groups


def test_the_activated_tenants_capability_snapshot_records_what_the_projection_did(pg_store):
    """The receipt, persisted. `prerequisites_withheld_unknowable` is the one that has to survive
    the round trip: a shorter `prerequisite_fields` with no record of what left it is
    indistinguishable from an expertise that reads fewer facts."""
    org = "pk_seams_in_receipt"
    _seed(pg_store, org, roster_v2=True)

    with pg_store.engine.connect() as conn:
        manifests = conn.execute(text(
            "select manifest from reasoning_capability_snapshots where org_id = :o"),
            {"o": org}).scalars().all()
    assert manifests

    receipts = []
    for manifest in manifests:
        body = json.loads(manifest) if isinstance(manifest, str) else manifest
        roster = (body.get("metadata") or {}).get("roster") or {}
        if "situation_projection" in roster:
            receipts.append(roster["situation_projection"])
    assert receipts, "no persisted capability snapshot records the projection"
    for receipt in receipts:
        assert set(receipt) == {"declared_on_core_context", "unknown_typed",
                                "prerequisites_withheld_unknowable"}
        assert all(name.startswith(sp.SITUATION_NAMESPACE)
                   for name in receipt["declared_on_core_context"])
        assert not set(receipt["declared_on_core_context"]) & set(receipt["unknown_typed"])


def test_an_unactivated_tenants_payload_is_untouched_by_this_wave(pg_store):
    """The additive claim, measured rather than asserted. A tenant that is not on the roster pilot
    carries no projected fact and no projected missing field — the six-unit lane declares none, so
    injecting them would move its context snapshot id and every decision hash under it."""
    org = "pk_seams_in_unactivated"
    _seed(pg_store, org, roster_v2=False)

    with pg_store.engine.connect() as conn:
        payloads = conn.execute(text(
            "select p.payload from reasoning_context_payloads p "
            "join reasoning_runs u on u.org_id = p.org_id "
            "and u.context_snapshot_id = p.context_snapshot_id "
            "where p.org_id = :o and u.capability_id like 'expertise.%'"),
            {"o": org}).scalars().all()
    assert payloads
    for payload in payloads:
        body = json.loads(payload) if isinstance(payload, str) else payload
        assert not [name for name in (body.get("facts") or {})
                    if name.startswith(sp.SITUATION_NAMESPACE)]
        assert not [name for name in (body.get("missing_fields") or ())
                    if name.startswith(sp.SITUATION_NAMESPACE)]
        assert "situation_projection" not in (body.get("metadata") or {})
