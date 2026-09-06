"""L2.4 · the ON-DEMAND analytic surface — declared metric pairs (L2.4.7) and cached peer
baselines (L2.4.6).

THIS IS THE REQUEST PATH THE CORRELATOR IS REACHED ON, and it is a READ rather than a sweep pass
deliberately. Its two neighbours in the analytic stratum earn a place on the drain because they
accumulate: the sampler must record what was true THIS period or the period is gone, and the trend
must be refreshed or the fact it wrote goes stale. A correlation accumulates nothing — it is
recomputed from `metric_history` and `cohort_membership` on demand, at an `eval_time` the caller
names, and computing it on every drain of every org would spend six pair-reads per cohort per
sweep to produce an object no table holds.

`comparator.compare_in_cohort` (L2.4.4) is wired the same way and for the same reason — a
comparison is answered when somebody asks for it — on `cohort_routes`' own position route.
(It says `compare_in_cohort` and not `cohort.position_in_cohort` deliberately: that one applies no
staleness horizon and serves the raw ladder, and the route it used to answer is the one where both
of those were measured. See the handler's docstring.)

WHY L2.4.6's LADDER READ IS ALSO HERE. `peer_baselines` was written on every drain and read by
nothing on a request path — the exact Layer 1 failure, and the reason X5 could not start on it.
The fix is a reader, and a reader needs a router `main.py` already includes; this file is the one
in L2.4's read surface. The alternative was a new `baseline_routes.py`, which would have needed a
line in `main.py` — a file this wave does not own — and would have shipped as another module
nothing reaches. The two live together honestly enough: both are ON-DEMAND reads over
`metric_history` and `cohort_membership` at a caller-named instant, and neither writes anything.

WHAT THE BASELINE ROUTE MAY AND MAY NOT SAY. It publishes five smoothed rungs and a population —
never a member id, never an order statistic. `peer_baseline` enforces that at the point of
PUBLICATION (`MIN_BASELINE_POPULATION`, `require_publishable_window`), so this route cannot widen
it by asking differently: it reads rows that already passed both floors and adds no parameter
that could lower either.

Everything here is single-tenant. `_org` refuses a mismatch between the path and the credential,
and every call below passes exactly one `org_id` into the correlator, which is where the
statements that carry it live.

**NO ROUTE HERE CAN EMIT A CAUSAL CLAIM.** The payload is `MetricCorrelation.model_dump()`, whose
`is_causal` is False by construction (V-7), plus the registered QUESTION the pair was declared
with — a question, never a because.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from genios_engine.context.analytic.correlator import (MAX_COHORTS_PER_READ, REGISTERED_PAIRS,
                                                       correlate_pair_for_node,
                                                       correlate_pair_in_cohort,
                                                       correlations_for_org,
                                                       correlations_in_cohort, is_registered,
                                                       outcome_payload)
from genios_engine.context.analytic.peer_baseline import (BASELINE_RUNGS_BP,
                                                          MIN_BASELINE_POPULATION, load_baseline,
                                                          load_baselines)
from genios_engine.platform.auth import get_current_org
from genios_engine.platform.wiring import make_graph_store

router = APIRouter()
_graph = make_graph_store()


def _org(org_id: str, org: str = Depends(get_current_org)) -> str:
    if org_id != org:
        raise HTTPException(403, "org mismatch")
    return org


def _store():
    if _graph is None:
        raise HTTPException(400, "graph store not configured")
    return _graph


def _now() -> datetime:
    """The clock is read HERE, at the process boundary, and nowhere below it — every function in
    the correlator takes `eval_time` as a parameter so a request is replayable."""
    return datetime.now(timezone.utc)


def _at(as_of: datetime | None) -> datetime:
    """The instant this request is answered AS. `as_of` is what makes a published rung checkable
    six months later — "the ladder this percentile was judged against, as it stood in March".

    A NAIVE datetime is refused rather than assumed UTC. The whole layer keys on period
    boundaries, and a silent offset moves an answer to the wrong week rather than raising
    anything a caller could see.
    """
    if as_of is None:
        return _now()
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise HTTPException(422, "as_of must carry a timezone offset")
    return as_of.astimezone(timezone.utc)


@router.get("/api/org/{org_id}/correlations/pairs")
def list_registered_pairs(org_id: str, org: str = Depends(_org)) -> dict:
    """The declared hypotheses, with the customer question each one serves.

    Exposed because "why is this the list?" is a fair question and the answer — these six were
    written down in advance — is the only thing separating a finding here from the three spurious
    ones an open-ended scan over sixty-six pairs would produce on any tenant.
    """
    return {"pairs": [{"metric_a": pair.metric_a, "metric_b": pair.metric_b,
                       "question": pair.question} for pair in REGISTERED_PAIRS]}


@router.get("/api/org/{org_id}/cohorts/{cohort_id}/correlations")
def cohort_correlations(org_id: str, cohort_id: str, org: str = Depends(_org),
                        metric_a: str | None = None, metric_b: str | None = None) -> dict:
    """Every declared pair in this cohort — or one named pair — with refusals spelled out.

    A refusal is a 200 with a named reason, not an error: *"eighteen members have both readings
    and this needs twenty"* is an ANSWER, and rendering it as a failure is how a UI ends up
    filling the space with a number nobody computed.

    An UNDECLARED pair is the exception, and it is a 422. The other refusals describe this
    tenant's data; this one describes the request, and returning it as a result would make
    `?metric_a=..&metric_b=..` a general-purpose scanner that answers "not registered" politely
    until somebody stops reading the reason.
    """
    if (metric_a is None) != (metric_b is None):
        raise HTTPException(422, "name both metrics of a pair, or neither")
    if metric_a is not None and metric_b is not None:
        if not is_registered(metric_a, metric_b):
            raise HTTPException(422, "that metric pair is not registered: pairs are declared in "
                                     "advance, never discovered by scanning")
        outcomes = (correlate_pair_in_cohort(_store(), org_id=org, cohort_id=cohort_id,
                                             metric_a=metric_a, metric_b=metric_b,
                                             eval_time=_now()),)
    else:
        outcomes = correlations_in_cohort(_store(), org_id=org, cohort_id=cohort_id,
                                          eval_time=_now())
    return {"cohort_id": cohort_id,
            "results": [outcome_payload(outcome) for outcome in outcomes]}


@router.get("/api/org/{org_id}/correlations")
def org_correlations(org_id: str, org: str = Depends(_org),
                     limit: int = MAX_COHORTS_PER_READ) -> dict:
    """Every declared pair in every cohort this tenant has active membership in.

    The read behind "show me what moves with what here", and the reason it exists as a route
    rather than as a sweep pass: a correlation accumulates nothing, so computing it on every
    drain of every org would spend six pair-reads per cohort per sweep to produce an object no
    table holds. `correlations_for_org` was built with that bound already in it
    (`MAX_COHORTS_PER_READ`) and had no caller until now.

    The truncation is REPORTED rather than silent. Cohorts are read in id order, so a tenant over
    the ceiling truncates at the same place on every run — which is deterministic and, unstated,
    indistinguishable from "this tenant has twenty-five cohorts".
    """
    if limit < 1 or limit > MAX_COHORTS_PER_READ:
        raise HTTPException(422, f"limit must be between 1 and {MAX_COHORTS_PER_READ}")
    by_cohort = correlations_for_org(_store(), org_id=org, eval_time=_now(), limit=limit)
    return {"cohorts": [{"cohort_id": cohort_id,
                         "results": [outcome_payload(outcome) for outcome in outcomes]}
                        for cohort_id, outcomes in sorted(by_cohort.items())],
            "cohort_limit": limit, "truncated": len(by_cohort) >= limit}


@router.get("/api/org/{org_id}/nodes/{node_id}/correlations")
def node_correlations(node_id: str, org_id: str, metric_a: str, metric_b: str,
                      org: str = Depends(_org)) -> dict:
    """L2.4.7's TIME-SERIES form: do these two metrics move together ON THIS ONE ACCOUNT?

    Both metrics are REQUIRED here, where the cohort route lets them be omitted. The cohort form
    answers six declared pairs from two reads per pair over one membership list; this form reads
    two dense series per pair for one node, and answering all six unasked would be twelve series
    reads for a question nobody posed. An undeclared pair is a 422 for the same reason it is on
    the cohort route: the other refusals describe the tenant's data, this one describes the
    request.

    A MIXED-GRAIN pair is a 200 with a named refusal, not a 422 — it is declared, it is simply
    unanswerable in this form, and the reason belongs in front of the reader rather than in a
    status code.
    """
    if not is_registered(metric_a, metric_b):
        raise HTTPException(422, "that metric pair is not registered: pairs are declared in "
                                 "advance, never discovered by scanning")
    outcome = correlate_pair_for_node(_store(), org_id=org, subject_node_id=node_id,
                                      metric_a=metric_a, metric_b=metric_b, eval_time=_now())
    return {"node_id": node_id, "results": [outcome_payload(outcome)]}


def _ladder_payload(baseline) -> dict:
    """One ladder, as it leaves the process. Five aggregates, a population, a unit and a period —
    the same set `PeerBaseline.as_row` writes, minus the tenant, and with the rung definitions
    attached so a reader knows what p10 MEANS here rather than guessing at a convention."""
    return {"metric": baseline.metric, "unit": baseline.unit.value,
            "currency": baseline.currency, "population": baseline.population,
            "computed_at": baseline.computed_at.isoformat(),
            "rungs_bp": list(BASELINE_RUNGS_BP), "ladder": list(baseline.ladder),
            "p10_bp": baseline.p10_bp, "p25_bp": baseline.p25_bp, "p50_bp": baseline.p50_bp,
            "p75_bp": baseline.p75_bp, "p90_bp": baseline.p90_bp}


@router.get("/api/org/{org_id}/cohorts/{cohort_id}/baselines")
def cohort_baselines(org_id: str, cohort_id: str, org: str = Depends(_org),
                     metric: str | None = None, as_of: datetime | None = None) -> dict:
    """L2.4.6-U1 · the cached ladder for this peer group, as it stood at `as_of`.

    THE READER THE TABLE DID NOT HAVE. `refresh_baselines_for_drain` writes `peer_baselines` on
    every drain; until this route the only thing that ever read a row back was a test, which is
    storage cost with a docstring rather than a cache. ALG-17 — the consumer doc 04 names — has
    not landed; `peer_baseline`'s docstring says so plainly and states what has to be true before
    `load_baseline` is on that path.

    AN EMPTY LIST IS AN HONEST ANSWER AND NOT AN ERROR. Refusals are not stored, so this route
    cannot tell "under the k-anonymity floor" from "the drain has not run for this cohort yet",
    and it does not guess: it returns the ladders that exist and names the floor a cohort has to
    clear to have one. Fabricating either sentence would be a claim the table does not hold.
    """
    at = _at(as_of)
    if metric is not None:
        found = load_baseline(_store().engine, org, cohort_id, metric, as_of=at)
        ladders = () if found is None else (found,)
    else:
        ladders = load_baselines(_store().engine, org, cohort_id, as_of=at)
    return {"cohort_id": cohort_id, "as_of": at.isoformat(),
            "baselines": [_ladder_payload(b) for b in ladders],
            "population_floor": MIN_BASELINE_POPULATION,
            "detail": ("no ladder is stored for this cohort at that instant — a peer group needs "
                       f"{MIN_BASELINE_POPULATION} members with a reading before one is "
                       "published, and none is computed before the tenant's first drain")
                      if not ladders else ""}
