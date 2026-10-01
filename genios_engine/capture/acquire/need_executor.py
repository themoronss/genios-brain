"""U10 · the pass that works the queue — Layer 2 asked, and this is Layer 1 answering.

`context/evidence_need_store.py` files needs. `evidence_need.execute()` works ONE need. Nothing ran
the loop between them, so the queue was write-only: questions accumulated and none was ever answered.

⛔ THE REASON THIS PASS IS DANGEROUS, AND WHAT IT REFUSES.

`need_id` is deterministic and the insert is `on conflict do nothing`, so **a closed need is never
re-asked.** That is correct — it is what stops the queue growing forever. But it means a closure is
PERMANENT, and therefore:

> A need closed `unavailable` because we had not wired a connector yet is a question **destroyed**.
> When the connector arrives, the question does not come back. Nothing re-asks it, because the row
> says it was answered.

So a naive first run of this pass — against today's production, where no connector is wired — would
close **the entire queue** as "not connected" and permanently erase every question Layer 2 had asked.
That is strictly worse than never running it.

Two refusals prevent it, and they are the whole reason this module exists rather than being four lines
inside a sweep:

  1. ⛔ **No fetchers at all → the pass refuses to start.** It closes nothing and says why. An
     executor with nothing to execute with is not an executor, and letting it "work" the queue would
     mean recording our own missing plumbing as a fact about the tenant's evidence.
  2. ⛔ **A need whose fetch kind has no fetcher is LEFT OPEN.** Not closed, not counted as
     unavailable — deferred, and reported as deferred. `fetch_thread` being wired while `reextract` is
     not is the normal state during a rollout, and the reextract questions must survive it.

`plan_fetch` returning `None` IS closed, and the difference matters: that means no Layer 1 fetch of any
kind could ever answer this need. It is a fact about the question, not about our deployment.

⛔ AND THE QUEUE IS INJECTED, NOT IMPORTED. `capture/` is layer 1 and the `evidence_needs` table
belongs to `context/` at layer 2, so importing the store here is an UPWARD import —
`tests/test_layer_topology.py` fails the build on it, and it caught this module's first draft.

That gate is right, and the fix is not a workaround. **`capture/` must not know where a need is
stored.** It answers questions; the row is `context/`'s. So `read_open` and `close` arrive as
callables, exactly as `fetchers` does, and the composition root joins the two halves. It is the same
data-not-import rule `docs/LAYER_MAP.md` records for the downward direction, applied upward.

ONE OTHER THING THE PASS OWNS. `close_need` returns False when someone else closed the need first.
⛔ That is not an error and is not retried — their answer stands. It is counted separately so a
double-running cron is visible as a number rather than as a mystery.

NEVER RAISES, on the same terms as everything else in `capture/`: losing a fetch costs an answer,
raising costs the tenant their mail.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from genios_engine.capture.acquire.evidence_need import FetchOutcome, execute, plan_fetch
from genios_engine.contracts.evidence import EvidenceNeed
from genios_engine.platform.logging import get_logger

_log = get_logger("genios.capture.need_executor")

#: How many needs one pass will work. The queue is read oldest-first, so a cap delays the newest
#: questions rather than starving the oldest — which is the right way round when the oldest is the one
#: a situation has been held on for a week.
DEFAULT_LIMIT = 50

#: What one pass may spend in total, across all needs, regardless of each need's own `max_cost_usd`.
#: A per-need limit cannot stop fifty cheap fetches from costing more than anyone intended, and the
#: tenant experiences the sweep's total, not one need's share of it.
DEFAULT_SWEEP_BUDGET_USD = 1.00


@dataclass(frozen=True, slots=True)
class NeedSweepReport:
    """What one pass did. Every number here is a thing that happened, not a thing attempted."""

    examined: int = 0
    met: int = 0
    unavailable: int = 0
    #: ⛔ Left OPEN because no fetcher is wired for that kind. Not a failure, and not a closure.
    deferred: int = 0
    #: Closed by another pass first. Their answer stands.
    already_closed: int = 0
    #: ⛔ Rows that no longer satisfy the contract. SKIPPED, not fatal — see `_run_needs`.
    malformed: int = 0
    #: Set when the pass refused to run at all. `examined` is then 0 by construction.
    refused: str | None = None
    outcomes: tuple[FetchOutcome, ...] = ()

    @property
    def ran(self) -> bool:
        return self.refused is None

    @property
    def closed(self) -> int:
        return self.met + self.unavailable


def _now(eval_time: datetime | None) -> datetime:
    return eval_time or datetime.now(timezone.utc)


def _need_from_row(row: Mapping[str, Any]) -> EvidenceNeed:
    """Rebuild the contract from its row, so the pass works on the validated type.

    Going through the constructor is deliberate: a row that no longer satisfies the contract — an
    `unavailable` state with no reason, say — should fail loudly here rather than be worked as if it
    were sound.
    """
    return EvidenceNeed(
        need_id=str(row["need_id"]), org_id=str(row["org_id"]), trace_id=str(row["trace_id"]),
        question=str(row["question"]), why_it_matters=str(row["why_it_matters"]),
        subject_ref=row.get("subject_ref"),
        acceptable_sources=tuple(row.get("acceptable_sources") or ()),
        unacceptable_sources=tuple(row.get("unacceptable_sources") or ()),
        window_from=row.get("window_from"), window_to=row.get("window_to"),
        max_cost_usd=row.get("max_cost_usd"), expires_at=row.get("expires_at"),
        state=str(row.get("state") or "open"),
        unavailable_reason=row.get("unavailable_reason"),
    )


#: `read_open(org_id, limit) -> sequence of need rows`. Supplied by the composition root from
#: `context/evidence_need_store.read_open_needs`, which this layer may not import.
ReadOpen = Callable[..., Sequence[Mapping[str, Any]]]

#: `close(need_id, state, reason) -> bool`, False meaning someone else closed it first.
CloseNeed = Callable[..., bool]


def run_needs(org_id: str, *,
              read_open: ReadOpen,
              close: CloseNeed,
              fetchers: Mapping[str, Callable[[EvidenceNeed], Any]],
              eval_time: datetime | None = None,
              limit: int = DEFAULT_LIMIT,
              sweep_budget_usd: float = DEFAULT_SWEEP_BUDGET_USD) -> NeedSweepReport:
    """Work this tenant's open needs to closed states — or refuse, and say so.

    `fetchers` maps a member of `FETCH_KINDS` to something that performs it. `read_open` and `close`
    reach the queue. All three are injected: the fetchers because a connector is not testable, the
    queue because `context/` sits above this layer and may not be imported from it.
    """
    try:
        return _run_needs(org_id, read_open=read_open, close=close, fetchers=fetchers,
                          eval_time=eval_time, limit=limit, sweep_budget_usd=sweep_budget_usd)
    except Exception as exc:      # noqa: BLE001 — a fetch pass must never break ingestion
        _log.exception("the evidence-need pass failed for org=%s", org_id)
        return NeedSweepReport(refused=f"the pass failed: {type(exc).__name__}")


def _run_needs(org_id: str, *, read_open, close, fetchers, eval_time, limit,
               sweep_budget_usd) -> NeedSweepReport:
    if not fetchers:
        # ⛔ REFUSAL 1. Closing the queue as "not connected" would record our own missing plumbing as
        # a permanent fact about the tenant's evidence, and `on conflict do nothing` means those
        # questions never come back.
        return NeedSweepReport(refused="no fetcher is wired, so no need can be worked; closing them "
                                       "would permanently erase questions this deployment simply "
                                       "cannot answer yet")

    now = _now(eval_time)
    rows = read_open(org_id, limit=limit)

    met = unavailable = deferred = already = malformed = 0
    spent = 0.0
    outcomes: list[FetchOutcome] = []

    for row in rows:
        try:
            need = _need_from_row(row)
        except Exception:      # noqa: BLE001
            # ⛔ SKIPPED, never fatal. The queue is read oldest-first, so a row that failed the whole
            # pass would sit at the head of it forever and block every need behind it — a permanent
            # stall, and an invisible one. Counting it makes the corruption a number somebody can see
            # while the other forty-nine questions still get answered.
            malformed += 1
            _log.warning("evidence need row is malformed and was skipped: %s",
                         row.get("need_id"), exc_info=True)
            continue

        kind = plan_fetch(need)
        if kind is not None and kind not in fetchers:
            # ⛔ REFUSAL 2. Left OPEN. `fetch_thread` wired while `reextract` is not is the normal
            # state during a rollout, and those questions must survive it.
            deferred += 1
            continue

        if spent >= sweep_budget_usd:
            # Also left open, for the same reason: a budget we ran out of is a fact about this pass,
            # not about the evidence. The next pass reads the same queue, oldest first.
            deferred += 1
            continue

        outcome = execute(need, fetchers=fetchers, eval_time=now)
        outcomes.append(outcome)
        spent += float(need.max_cost_usd or 0.0)

        wrote = close(need.need_id, state=outcome.state, reason=outcome.reason)

        if not wrote:
            # Not an error, and never retried — another pass settled it first and its answer stands.
            already += 1
        elif outcome.state == "met":
            met += 1
        else:
            unavailable += 1

    return NeedSweepReport(examined=len(rows), met=met, unavailable=unavailable, deferred=deferred,
                           already_closed=already, malformed=malformed, outcomes=tuple(outcomes))


def build_fetchers(org_id: str) -> dict[str, Callable[[EvidenceNeed], Any]]:
    """The connectors this deployment can actually reach. **Empty today, and honestly empty.**

    ⛔ This returning `{}` is what makes `run_needs` refuse, and that is the correct behaviour rather
    than a placeholder: no connector is wired, so there is nothing this pass could truthfully learn.
    A stub that returned `None` for every fetch would close every need as "found nothing in the
    window" — indistinguishable from a real negative result, permanent, and wrong.

    Wiring these to live connectors is Harsh's integration (L1 STEP-07, L3 STEP-05). The seam is
    here so that work is a mapping, not a redesign.
    """
    return {}


__all__ = ["DEFAULT_LIMIT", "DEFAULT_SWEEP_BUDGET_USD", "CloseNeed", "NeedSweepReport", "ReadOpen",
           "build_fetchers", "run_needs"]
