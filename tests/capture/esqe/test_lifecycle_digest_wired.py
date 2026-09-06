"""ALG-19's replay check, reached from `_run_ledger` — the hook every HTTP sync caller shares.

    pytest tests/capture/esqe/test_lifecycle_digest_wired.py -q

`outcome_digest` is the thing an operator compares instead of eyeballing a list of records:
"the same sweep at the same `eval_time` produces byte-identical lifecycles" is the property the
whole no-clock discipline in `lifecycle.py` exists to buy. It had no caller outside its own unit
test, so the discipline was unmeasured on every production sweep.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.api import routes
from genios_engine.capture.esqe import lifecycle as L

NOW = datetime(2026, 4, 2, 9, 0, tzinfo=timezone.utc)
ORG = "org_digest_wired"


def test_the_ledger_hook_computes_the_replay_digest(monkeypatch, caplog):
    """Through `_run_ledger`, not through `sweep_lifecycle`: a build where the digest is
    computed in a helper nothing calls fails here."""
    seen: list[str] = []
    real = L.outcome_digest
    monkeypatch.setattr(routes, "outcome_digest",
                        lambda outcome: seen.append(real(outcome)) or real(outcome))
    for name in ("_graph", "_conflict_store", "_floor_store", "_drop_ledger",
                 "_signal_store", "_rejection_ledger", "_parked"):
        monkeypatch.setattr(routes, name, None)

    # A real ALG-19 move, produced by ALG-19: an active signal whose clock has run out, aged
    # through `apply_expiries` — the same function the sweep calls.
    before = _record(state=L.ACTIVE, expires_at=NOW.replace(year=2025))
    transitions, records = L.apply_expiries((before,), eval_time=NOW)
    assert transitions, "the fixture did not actually expire — the digest would be of nothing"
    monkeypatch.setattr(
        routes, "sweep_lifecycle",
        lambda *a, **kw: L.LifecycleOutcome(org_id=ORG, eval_time=NOW,
                                            transitions=transitions, records=records))

    routes._run_ledger(org_id=ORG, connection_id="con_d", source="gmail", mode="incremental",
                       summary=_Summary())

    assert seen, "the ledger hook swept the lifecycle and never computed its replay digest"
    assert len(seen[0]) == 64, "a digest that is not a sha256 hex is not comparable"


def test_two_identical_sweeps_produce_the_same_digest():
    """The property the digest exists to check, asserted rather than assumed."""
    def _outcome():
        return L.LifecycleOutcome(org_id=ORG, eval_time=NOW, transitions=(),
                                  records=(_record(state=L.ACTIVE),))

    assert L.outcome_digest(_outcome()) == L.outcome_digest(_outcome())


def test_a_changed_state_changes_the_digest():
    """…and it must actually discriminate, or comparing it proves nothing."""
    # `LifecycleRecord` refuses an expired state with no clock ("a state that names no clock
    # cannot be explained or replayed"), so both records carry the same `expires_at` and ONLY
    # the state differs — which is exactly the discrimination being asserted.
    past = NOW.replace(year=2025)

    def _outcome(state: str):
        return L.LifecycleOutcome(org_id=ORG, eval_time=NOW, transitions=(),
                                  records=(_record(state=state, expires_at=past),))

    assert L.outcome_digest(_outcome(L.ACTIVE)) != L.outcome_digest(_outcome(L.EXPIRED))


def _record(*, state: str, expires_at=None, signal_id: str = "sig_d") -> L.LifecycleRecord:
    return L.LifecycleRecord(
        org_id=ORG, signal_id=signal_id, subject_key="contract:acme",
        signal_type="contract_renewal", authority_rank=4, occurred_at=NOW,
        state=state, supersedes=None, expires_at=expires_at, evaluated_at=NOW)


class _Summary:
    scanned = emitted = dropped = parked = duplicate = quarantined = 0
    gated: list = []
    results: list = []
    conflicts = None
    claim_groups: tuple = ()
