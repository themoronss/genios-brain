"""The narration pass — where a published decision actually gets its voice.

**This is the real path.** It runs at the END of `reason/runner.run_all`, after every pack has
reasoned and every signal has been written, which is doc 05 §7's "bundles generate AFTER
publication, never in the decision's critical path" and doc 11 guard 5 expressed as a position in
the code rather than as an intention. If this pass fails entirely, every decision the sweep made is
already committed and every card already renders; only the prose is missing.

**Where the DecisionObject comes from: a replay, and the replay is verified.** The decision this
narrates has already been made, persisted and published; re-reasoning it here from the live graph
would be a SECOND decision that might differ from the one the card is about. So the pass loads the
run's immutable input snapshot and replays it — pure arithmetic, no live reads, no model — and
narrates only when the replayed decision hashes to what was stored. A run that does not replay is
counted and skipped: doc 05's whole argument is that the narrative is about a decision the record
can prove, and a decision the record cannot reproduce is not one.

**Nothing here decides.** The replay is a read of a decision that already exists. `ReplayComparison`
is checked and never repaired.

**Every skip is counted and named.** The tally this returns is what K4's rows are computed from, and
"forty decisions, twelve narrated" with no reason column is a number nobody can act on.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from genios_engine.platform.l4_activation import FEATURE_BUNDLE, activated_features
from genios_engine.platform.logging import get_logger

from .gate import RSiteGate
from .narrator import SKIP_NO_ACTION, SKIP_NO_GROUNDING, narrate
from .sites import SITE_NARRATE, tier_for
from .store import BundleStore

_log = get_logger("genios.reason.bundle.sweep")

#: How many decisions one sweep may narrate. A tenant switched on after a month of history must not
#: spend its first day narrating a month of cards nobody is going to open; the budget would stop the
#: spend but not the choice of what to spend it on. Newest first, so what a founder opens tomorrow
#: is what got narrated tonight.
DEFAULT_LIMIT = 25


def narrate_published(*, store, org_id: str, eval_time: datetime | None = None,
                      limit: int = DEFAULT_LIMIT, llm=None, orchestrator=None,
                      reasoning_store=None, gate: RSiteGate | None = None) -> dict[str, Any]:
    """Give every un-narrated published decision on this tenant a voice. Never raises.

    `store` is the L2 `GraphStore` the sweep already holds — the same object `runner.run_all` has —
    so this adds no connection and no second source of truth about which decisions were published.
    """
    eval_time = eval_time or datetime.now(timezone.utc)
    engine = getattr(store, "engine", None)
    tally: dict[str, Any] = {"considered": 0, "narrated": 0, "fallback": 0, "cached": 0,
                             "skipped": {}, "cost_micro_usd": 0}

    if engine is None:
        return _skip(tally, "no_engine")

    # Step 1 of the gate, asked ONCE for the whole pass. A tenant that is not on the pilot must
    # cost one query, not one query per decision.
    #
    # Skipped when a gate was HANDED IN, and that is not a hole: the gate re-checks activation on
    # every consult from the set it read at construction, so a caller supplying one has already
    # answered this question and answering it twice would mean two reads that can disagree. This
    # branch exists so the ordinary path can refuse the whole sweep — including the replays — before
    # building anything.
    if gate is None and FEATURE_BUNDLE not in activated_features(engine, org_id):
        return _skip(tally, "bundle_not_activated")

    bundle_store = BundleStore(engine)
    try:
        pending = bundle_store.undecorated_decisions(org_id=org_id, limit=limit)
    except Exception:      # noqa: BLE001 — a worklist that cannot be read is an empty sweep
        _log.exception("could not read the narration worklist for org=%s", org_id)
        return _skip(tally, "worklist_unreadable")
    if not pending:
        return tally

    if gate is None:
        gate = RSiteGate(org_id=org_id, engine=engine, client=llm or _client(),
                         store=bundle_store, eval_time=eval_time,
                         cost_recorder=getattr(store, "record_cost", None))
    orchestrator = orchestrator or _orchestrator()
    reasoning_store = reasoning_store or _reasoning_store(engine)

    for row in pending:
        tally["considered"] += 1
        execution = _replay(reasoning_store, orchestrator, org_id=org_id, run_id=row["run_id"],
                            tally=tally)
        if execution is None:
            continue
        decision = execution.decision
        try:
            narration = narrate(
                decision, execution.ordered_results, gate=gate, eval_time=eval_time,
                request=execution.request, store=bundle_store, run_id=row["run_id"],
                store_decision_hash=row["decision_hash"],
                subject_ref=f"signal:{row['signal_id']}")
        except Exception:      # noqa: BLE001 — one unnarratable decision is not a failed sweep
            _log.exception("narration failed for org=%s decision=%s", org_id, row["decision_hash"])
            _count(tally, "narration_failed")
            continue
        if narration is None:
            _count(tally, SKIP_NO_ACTION if decision.action_id is None else SKIP_NO_GROUNDING)
            continue
        tally["narrated"] += 1
        tally["cost_micro_usd"] += narration.consult.cost_micro_usd
        if narration.cached:
            tally["cached"] += 1
        if narration.is_fallback:
            tally["fallback"] += 1
    return tally


def _replay(reasoning_store, orchestrator, *, org_id: str, run_id: str, tally: dict):
    """The stored decision, rebuilt from its immutable snapshot. None when it cannot be."""
    from genios_engine.reason.replay import replay_persisted
    try:
        execution, comparison = replay_persisted(
            store=reasoning_store, org_id=org_id, run_id=run_id, orchestrator=orchestrator)
    except Exception as exc:      # noqa: BLE001 — an expired payload is the expected case here
        _count(tally, f"replay_unavailable:{type(exc).__name__}")
        return None
    if not comparison.matches:
        _count(tally, "replay_mismatch")
        return None
    return execution


def _count(tally: dict, reason: str) -> None:
    tally["skipped"][reason] = tally["skipped"].get(reason, 0) + 1


def _skip(tally: dict, reason: str) -> dict:
    _count(tally, reason)
    return tally


def _orchestrator():
    from genios_engine.reason.orchestrator import ReasoningOrchestrator
    from genios_engine.reason.reasoners import default_registry
    return ReasoningOrchestrator(default_registry())


def _reasoning_store(engine):
    from genios_engine.reason.store import ReasoningStore
    return ReasoningStore(engine=engine)


def _client():
    """The narrator's model AT ITS BUDGETED TIER, or None.

    R-2 is a T2 site (doc 11 §1) and this pass charges it at T2 prices, so it must not silently run
    the Haiku-class model `platform.wiring.make_llm_client` returns — a call priced at one tier and
    served at another makes both the bill and the quality story wrong. The tier -> model mapping
    lives in `reason/llm_sites.tier_model`, which the R-1/R-3/R-4 sites already use; it is imported
    rather than repeated so there is ONE answer in the tree to "what is the stronger model".

    `None` is a first-class answer either way: the gate records `skipped_no_client` and the
    labelled template ships.
    """
    try:
        from genios_engine.reason.llm_sites import make_site_client
        return make_site_client(tier_for(SITE_NARRATE))
    except Exception:      # noqa: BLE001 — that module is a sibling site's; never a hard dependency
        pass
    try:
        from genios_engine.platform.wiring import make_llm_client
        return make_llm_client()
    except Exception:      # noqa: BLE001 — a deployment with no model narrates from the template
        return None


def sweep_orgs(*, store, orgs: Sequence[str] | None = None, **kwargs) -> dict[str, Any]:
    """Every activated tenant, for an operator running the pass by hand. Not on the sweep path."""
    from genios_engine.platform.l4_activation import l4_activated_orgs
    engine = getattr(store, "engine", None)
    targets = (list(orgs) if orgs is not None
               else sorted(l4_activated_orgs(engine, FEATURE_BUNDLE)))
    return {org: narrate_published(store=store, org_id=org, **kwargs) for org in targets}


__all__ = ["DEFAULT_LIMIT", "narrate_published", "sweep_orgs"]
