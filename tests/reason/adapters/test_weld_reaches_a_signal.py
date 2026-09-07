"""The weld on the LIVE path: `shadow_compile(live=True)` -> a `signals` row that names its losers.

`tests/reason/adapters/test_weld.py` proves the weld against a real decision in memory. This
proves the last hop — that what the decision knows about its rejected candidates is what the row
delivery reads actually holds. `signals.rejected_candidates` is rendered by the API as
`alternatives_rejected`; the compiled lane has never written it, so a compiled card's "why not X?"
came back empty however completely Layer 3 had answered it.

Real Postgres, real Layer 1 ingestion, real corpus, real reasoning. The seeding helpers are the
ones `tests/test_admin_support_packs.py` already uses for the same end-to-end lane, imported
rather than copied so the two cannot drift about what an admin org looks like.
"""

from __future__ import annotations

import json

import pytest
from sqlalchemy import text

from genios_engine.context import situations

from ...test_admin_support_packs import NOW, _run_admin, _seed_org

pytestmark = pytest.mark.pg


def test_a_compiled_signal_carries_its_rejected_candidates(pg_store):
    from genios_engine.packs.wiring import ensure_defaults, make_registry
    from genios_engine.reason.domain_shadow import shadow_compile

    org = "pk_weld_rejected"
    _seed_org(pg_store, org)
    # RE-RUNNABLE ON ONE DATABASE. `_emit_capability_signal` inserts `on conflict … do nothing`,
    # so a second run against a database that already holds this org's open signal emits nothing
    # and `counts["emitted"]` is 0 — the test would then fail for a reason that has nothing to do
    # with the weld. Seven files in this suite already carry that defect and the brief names them;
    # this one is not going to be the eighth.
    with pg_store.engine.begin() as conn:
        conn.execute(text("delete from signals where org_id = :o"), {"o": org})
    _run_admin(pg_store, org)
    situations.refresh_situations(pg_store, org, eval_time=NOW)
    registry = make_registry(pg_store.engine.url.render_as_string(hide_password=False))
    ensure_defaults(registry, org)

    counts = shadow_compile(store=pg_store, org_id=org, eval_time=NOW, live=True,
                            registry=registry)
    assert counts.get("emitted", 0) > 0, dict(counts)

    with pg_store.engine.connect() as conn:
        rows = conn.execute(text(
            "select rejected_candidates, capability_id from signals where org_id=:o"),
            {"o": org}).mappings().all()
        manifests = conn.execute(text(
            "select manifest from reasoning_capability_snapshots where org_id=:o"),
            {"o": org}).scalars().all()
    assert rows, "nothing was emitted to assert on"

    rejected = rows[0]["rejected_candidates"]
    if isinstance(rejected, str):
        rejected = json.loads(rejected)
    # A compiled decision ranks a field; the losers are the receipt that a choice happened, and
    # the column was null on every compiled signal this product has ever emitted.
    assert isinstance(rejected, list) and rejected, "the compiled lane still writes no losers"
    for row in rejected:
        assert set(row) == {"play_id", "disposition", "utility_bp", "eliminated_by"}
        for elimination in row["eliminated_by"]:
            # No admin rule FIRES on this fixture (both are `satisfied`), so this loop is empty
            # here — the elimination payload itself is proven end to end against a real decision
            # in `test_weld.py::test_the_rejection_reaches_alternatives_rejected_with_its_quote`.
            # Asserted anyway so the day an admin rule does fire, a malformed row fails here.
            assert set(elimination) == {"rule_id", "severity", "statement"}
            assert elimination["severity"] == "blocking"
            assert elimination["statement"]

    # And the weld itself reached the persisted capability snapshot, which is what
    # `scripts/weld_report.py --org` reads.
    welds = [json.loads(m)["metadata"]["weld"] if isinstance(m, str) else m["metadata"]["weld"]
             for m in manifests]
    assert welds and all(weld["bound"] for weld in welds), "the live pass welded unbound"
    receipts = [weld["weld_receipt"] for weld in welds]
    assert any(receipt["rules_compiled"] for receipt in receipts), "no rule compiled live"
    assert any(receipt["citations_attached"] for receipt in receipts), "no claim was quoted live"
    # The corpus's own authored tensions reach a real tenant's decision: the admin route carries
    # `slow_approvals_teach_workarounds` against `no_chase_while_we_hold_the_ball`, so the conflict
    # detector is data-reachable rather than fixture-only.
    assert any(receipt["conflicts_named"] for receipt in receipts), "no tension was surfaced"
