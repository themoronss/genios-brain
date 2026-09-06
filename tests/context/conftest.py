"""Deterministic builders for every Layer 2 v2 context test — one clock, one signal factory,
one graph, and a refusal to reach anything real.

Layer 2's claim is *comparison*: "this is getting worse", "this is unlike its peers", "these
five facts hold together". Every one of those is a statement about a POPULATION and a PERIOD,
and both are things a test can accidentally take from the machine it runs on. A trend suite
that reads `datetime.now()` measures a different window every day; a cohort suite that reads
whichever Postgres `.env` names measures a different population every developer. Neither
failure looks like a failure — it looks like a flaky comparison, which is the one thing a
comparison engine may never be.

So the three sources of nondeterminism get exactly one home here, and everything under
`tests/context/` takes them as parameters.

**The clock is a fixture, not a call.** `eval_time` is the instant a trend, a percentile and an
anomaly are all computed against. Period boundaries in L2.4 are derived from it, never from
`now()`, because doc 04 makes one shared boundary function the mitigation for "backfill and
live sampling disagree on period boundaries -> phantom changepoints". A test that needs "three
weeks earlier" computes it from `eval_time` with a `timedelta`.

**The signal factory imports the real contract.** `QualifiedEnterpriseSignal` is what Layer 1
publishes and the only shape Layer 2 knows. A local restatement of its 25 fields would drift
from `contracts/signal.py` the first time L1 adds a validator, and the L2 suite would then be
green against a signal L1 can no longer produce — which is precisely the seam H5 exists to
guard. `qes()` builds the real object and fails at construction if the contract moved.

**Importance is a PARAMETER of the factory, never a constant.** H5's whole subject is that
`situation_bso.py:39` satisfied `importance_bp` with 5000. A fixture that defaulted every
signal to one value would make the flat distribution H5 forbids the natural thing to write, so
`qes()` requires the caller to say what importance this signal carries, and `qes_spread()`
hands back a set with a real spread when a test needs a population.

**The graph is data, not a database.** `graph` is a frozen description — nodes, facts,
observations, edges — that a hermetic test reads directly and a `pg`-marked test materializes
through `pg_store`. One description, two lanes, so a unit test and its real-Postgres twin can
never disagree about what was in the graph.

**Nothing here reaches the network.** `_hermetic_by_default` refuses `socket.connect` for every
test in this tree that does not carry `pg` or `llm`, for the same reason `tests/capture/`
does: the fastest way for a test to touch production is to open a connection nobody in the
test file ever mentions (commits `ae63ef9`, `d860b8e`).
"""

from __future__ import annotations

import socket
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.extraction import ExtractionResult
from genios_engine.contracts.signal import QualifiedEnterpriseSignal, SignalType
from genios_engine.contracts.visibility import Visibility

# =================================================================================================
# THE CLOCK
# =================================================================================================

#: The one instant every Layer 2 test computes a period, a trend and a percentile against.
#:
#: **The first of a month, and a Sunday-free choice on purpose.** L2.4.2 rule 5 guarantees "at
#: least one point per month regardless", and L2.4.3 reads weekly periods; an `eval_time` that
#: sat mid-month would make "the last 6 periods" mean a different set of days depending on
#: whether the reader bucketed by ISO week or by calendar month, and the two would silently
#: disagree in the one place doc 04 says they must not. 2026-03-01 is a **Sunday**, so the ISO
#: week containing it is unambiguous, and the 24-month retention horizon (2024-03-01) lands on a
#: month boundary too — a retention test can therefore state its cutoff without arithmetic.
#:
#: 09:00 UTC rather than midnight so a same-day sample is inside the period rather than exactly
#: on its edge, which is the difference between an off-by-one that shows up and one that does not.
EVAL_TIME = datetime(2026, 3, 1, 9, 0, tzinfo=timezone.utc)

#: The 24-month retention horizon of `metric_history` (doc 04, L2.4.1-U1), derived rather than
#: written twice. A point older than this is prunable; the series must stay readable after.
RETENTION_HORIZON = EVAL_TIME - timedelta(days=730)

#: One week, as the sampler's default cadence (L2.4.2-U1 rule 1). Named so a test says
#: "three periods ago" instead of "21 days ago" and reads as the thing it is measuring.
PERIOD = timedelta(days=7)

#: The tenant every fixture in this tree belongs to. `tests/conftest.py` seeds this row into
#: `orgs` on the scratch database at import, so a `pg`-marked test can write foreign-keyed rows
#: without seeding an org of its own — and so two files cannot disagree about which org they
#: are testing, which is how a cohort test ends up with a population of zero.
ORG = "org_scratch_tests"


@pytest.fixture
def eval_time() -> datetime:
    """The frozen instant. Take it as a parameter; never call a clock."""
    return EVAL_TIME


@pytest.fixture
def period() -> timedelta:
    """The sampler's default cadence, for tests that step a series backwards."""
    return PERIOD


@pytest.fixture
def retention_horizon() -> datetime:
    """The 24-month cutoff, as a fixture rather than an import.

    A bare `from conftest import RETENTION_HORIZON` would resolve against whichever `conftest`
    module the session imported first — `tests/capture/conftest.py` is also called `conftest` —
    and a relative `from .conftest import` binds every test module to this tree's exact
    directory layout, which is a thing a wave that adds a subdirectory then has to fix.
    Everything a test needs from this module is therefore reachable as a FIXTURE, and the
    module-level names exist only for the builders below to share.

    (`tests/context/` IS a package: `test_authority.py` exists here and at
    `tests/capture/validate/`, and pytest's prepend import mode keys a test module on its
    basename up to the first directory without an `__init__.py`. Without the package markers
    the two collide and collection aborts the whole run — not this file, the whole run.)
    """
    return RETENTION_HORIZON


@pytest.fixture
def org_id() -> str:
    """The tenant every fixture in this tree belongs to, seeded into `orgs` by the root
    conftest so a `pg`-marked test can write foreign-keyed rows without seeding its own."""
    return ORG


@pytest.fixture
def metric_point():
    """The `MetricSeriesPoint` type itself, for tests that build one directly."""
    return MetricSeriesPoint


# =================================================================================================
# THE SIGNAL FACTORY — the real contract, never a restatement
# =================================================================================================

#: A minimal, VALID `ExtractionResult`. Layer 2 never reads inside it — it consumes
#: `signal_type`, `importance_bp`, `evidence_refs` and `state` — but the contract requires one,
#: so it is built once here rather than in every test that needs a signal for another reason.
_EXTRACTION = ExtractionResult(
    intent="inform", stance="neutral", model_snapshot="claude-3-5-haiku-20241022",
    prompt_version="l1.s2.email.v3", schema_version="l1.v2.0", extraction_profile="email",
    input_tokens=10, output_tokens=5)

#: The sentence every default evidence span points into, and the span's own source. A span is
#: only worth anything if it names a real offset in a real text, so the quote and the text are
#: the same object here and the offsets are FOUND, never counted.
_EVIDENCE_TEXT = "Finance confirmed the renewal lands on the 30th."


def _default_span() -> EvidenceSpan:
    """One verified span over `_EVIDENCE_TEXT`. `QualifiedEnterpriseSignal` requires at least
    one evidence ref, and a test that is about a trend should not have to invent one."""
    return EvidenceSpan(source_ref="prepared_content:evt_l2_fixture", quote=_EVIDENCE_TEXT,
                        start_offset=0, end_offset=len(_EVIDENCE_TEXT), verified=True)


@pytest.fixture
def qes():
    """Factory: `qes(importance_bp=8200, signal_type=SignalType.RISK_FLAGGED)`.

    `importance_bp` is REQUIRED and has no default, which is the fixture's one opinion.
    H5 fails an implementation whose situations sit at 5000, and the cheapest way to write a
    suite that cannot detect that is to give every fixture signal the same score and never
    notice. Making the caller state it means a flat population in a test is a thing somebody
    deliberately typed.

    Everything else defaults to something valid and boring. `**overrides` reaches the real
    constructor, so an unknown field is a `ValidationError` here (the contract sets
    `extra="forbid"`) rather than a silently ignored kwarg.
    """
    counter = _signal_counter()

    def _build(*, importance_bp: int, signal_type: SignalType = SignalType.COMMITMENT_MADE,
               occurred_at: datetime | None = None, state: str = "active",
               **overrides: Any) -> QualifiedEnterpriseSignal:
        n = next(counter)
        base: dict[str, Any] = dict(
            org_id=ORG, trace_id=f"trace_l2_{n}", visibility=Visibility(),
            signal_id=f"sig_l2_{n}", event_id=f"evt_l2_{n}", source="gmail",
            object_type="email_message",
            occurred_at=EVAL_TIME - timedelta(days=1) if occurred_at is None else occurred_at,
            signal_type=signal_type, importance_bp=importance_bp, triage_lane="P1",
            extraction=_EXTRACTION, evidence_refs=[_default_span()], conflicts=[],
            confidence_bp=6200,
            confidence_vector={"evidence": 6200, "expertise": 6200, "freshness": 6200,
                               "coverage": 6200},
            coverage_ready=True, state=state, supersedes=None, expires_at=None,
            internal_kind=None, recipients=("rohit@antler.co",),
            versions={"prompt": "l1.s2.email.v3", "schema": "l1.v2.0"})
        base.update(overrides)
        # ALG-19: an `expired` signal must name the clock it expired on, or the state cannot be
        # explained or replayed. Supplied here rather than left to each caller because the
        # factory's job is to produce a VALID signal in the state it was asked for — a caller
        # that has an opinion about the expiry passes `expires_at=` and this does nothing.
        if base["state"] == "expired" and base["expires_at"] is None:
            base["expires_at"] = base["occurred_at"] + timedelta(days=30)
        return QualifiedEnterpriseSignal(**base)

    return _build


def _signal_counter():
    """A local counter, so signal ids are unique WITHIN a test and identical ACROSS runs.

    `uuid4` would also make them unique and would destroy the property H5 measures: "identical
    input twice -> byte-identical". A monotonic per-fixture counter gives both.
    """
    n = 0
    while True:
        yield n
        n += 1


@pytest.fixture
def qes_spread(qes):
    """A population of signals with a REAL importance spread, for the composition gates.

    H5 asks two questions a single signal cannot answer — does the situation take the `max`
    rather than the `mean` (one critical + four routine must reach >= 9000), and is the
    resulting distribution wide enough to rank. Both need a population, and a population
    assembled ad hoc in each test is a population whose spread nobody checked.

    The default is deliberately the H5 shape: one critical signal and four routine ones.
    """
    def _build(*, importance_bps: tuple[int, ...] = (9600, 3100, 2800, 4400, 3500),
               **overrides: Any) -> tuple[QualifiedEnterpriseSignal, ...]:
        return tuple(qes(importance_bp=bp, **overrides) for bp in importance_bps)
    return _build


# =================================================================================================
# THE GRAPH — one description, two lanes
# =================================================================================================

@dataclass(frozen=True, slots=True)
class GraphNode:
    """A node as L2 reads it. `node_id` is stated, not generated, because a cohort test that
    asserts on membership has to be able to NAME the members."""

    node_id: str
    node_type: str
    display_name: str


@dataclass(frozen=True, slots=True)
class GraphFact:
    """A current fact — `graph_facts` semantics: one row per (subject, field), overwritten.

    `value` is whatever JSON the field holds. There is no `observed_at` here ON PURPOSE:
    `graph_facts` answers "what is true now?" and carries no history. A test that wants history
    builds `MetricSeriesPoint`s instead, and the fact that these are two different types in the
    fixture is the two-table rule made visible in the test suite.
    """

    subject_node_id: str
    field: str
    value: Any


@dataclass(frozen=True, slots=True)
class MetricSeriesPoint:
    """One point of intended `metric_history` — the "what was true then?" half.

    `known=False` carries `value_bp=None` and nothing else; a point that claims both is the
    interpolation V-3 rejects, so the fixture refuses to build one rather than leaving it to
    the unit under test to notice.
    """

    subject_node_id: str
    metric: str
    observed_at: datetime
    value_bp: int | None = None
    known: bool = True
    unit: str = "count"
    sample_reason: str = "scheduled"
    coverage_ready: bool | None = True

    def __post_init__(self) -> None:
        if self.known and self.value_bp is None:
            raise AssertionError(
                f"a known point must carry a value: {self.metric} @ {self.observed_at}")
        if not self.known and self.value_bp is not None:
            raise AssertionError(
                "a point with known=False must have value_bp=None — a gap with a value is an "
                f"interpolation, which is the one thing L2.4.1 forbids: {self.metric}")


@dataclass(frozen=True, slots=True)
class GraphFixture:
    """The whole deterministic world a Layer 2 test reasons over."""

    org_id: str
    nodes: tuple[GraphNode, ...] = ()
    facts: tuple[GraphFact, ...] = ()
    series: tuple[MetricSeriesPoint, ...] = ()

    def node(self, node_id: str) -> GraphNode:
        for n in self.nodes:
            if n.node_id == node_id:
                return n
        raise AssertionError(f"no node {node_id!r} in the fixture graph")


@pytest.fixture
def graph():
    """Factory: a `GraphFixture` with sensible accounts, extended per test.

    Three accounts rather than one, because every L2.4 unit above the history store is a
    COMPARISON and a population of one cannot be compared to anything. Three is also below
    `population_size >= 5` (validator V-2), so a test that wants a legal `CohortPosition` has
    to say so by adding members — which stops "the cohort was too small" from being an
    accident nobody wrote down.
    """
    def _build(*, nodes: tuple[GraphNode, ...] | None = None,
               facts: tuple[GraphFact, ...] = (),
               series: tuple[MetricSeriesPoint, ...] = ()) -> GraphFixture:
        default_nodes = (
            GraphNode("node_acct_north", "company", "Northwind"),
            GraphNode("node_acct_summit", "company", "Summit Labs"),
            GraphNode("node_acct_delta", "company", "Delta Retail"),
        )
        return GraphFixture(org_id=ORG, nodes=default_nodes if nodes is None else nodes,
                            facts=facts, series=series)
    return _build


@pytest.fixture
def declining_series():
    """A 6-point monotonic decline ending at `eval_time` — H2's decisive row.

    Built backwards from `eval_time` in whole periods so the values and the periods are both
    derived from one place. H2 asks for the same values "with 3 gaps" to read
    `INSUFFICIENT_COVERAGE` rather than `DECLINING`, so `gaps=` punches holes in this exact
    series rather than a test writing a second, subtly different one.
    """
    def _build(node_id: str = "node_acct_north", metric: str = "engagement.touch_count_28d",
               values: tuple[int, ...] = (60, 52, 44, 33, 21, 12),
               gaps: tuple[int, ...] = ()) -> tuple[MetricSeriesPoint, ...]:
        points = []
        oldest_first = len(values) - 1
        for i, value in enumerate(values):
            at = EVAL_TIME - PERIOD * (oldest_first - i)
            if i in gaps:
                points.append(MetricSeriesPoint(node_id, metric, at, None, known=False,
                                                coverage_ready=False))
            else:
                points.append(MetricSeriesPoint(node_id, metric, at, value))
        return tuple(points)
    return _build


# =================================================================================================
# PENDING GATES
# =================================================================================================

#: `l2_pending` is NOT defined here. It lives in `tests/conftest.py` beside `l1_pending`, for
#: the reason that fixture's own docstring gives: gate H0 is
#: `pytest tests/contracts/test_l2_contracts.py -q`, which is outside this tree, and `tests/`
#: is the only conftest both directories inherit from. A second copy here would be the one the
#: context tree picked up, and the two would drift.


# =================================================================================================
# HERMETIC BY DEFAULT
# =================================================================================================

#: Markers that legitimately need a real connection: `pg` opens the scratch Postgres, `llm`
#: calls a real model (L2's only model site is M-9, cohort predicate authoring).
_MAY_CONNECT = ("pg", "llm")


@pytest.fixture(autouse=True)
def _hermetic_by_default(request: pytest.FixtureRequest):
    """Refuse outbound sockets for every context test that is not marked `pg` or `llm`.

    Copied in behaviour from `tests/capture/conftest.py` and deliberately NOT imported from it:
    `tests/capture` is not a package, so an import would be a path hack, and a shared guard that
    one tree could weaken for the other is worse than two guards that each fail closed. The
    risk here is if anything larger than in capture — every L2.4 unit wants a database, and the
    difference between "took the graph fixture" and "opened whatever `database_url` names" is
    invisible in a passing test.

    `socket.socket.connect` is patched rather than the class replaced, so constructing a socket
    still works and only reaching a peer fails. Restoration deletes the override instead of
    writing the inherited C method onto the Python subclass, which would leave a shadowing
    attribute behind for the rest of the session.
    """
    if any(request.node.get_closest_marker(m) for m in _MAY_CONNECT):
        yield
        return

    def _refuse(self: socket.socket, *args: Any, **kwargs: Any):
        raise RuntimeError(
            "network access refused: context tests are hermetic. Use the `graph` fixture, or "
            "mark the test `@pytest.mark.pg` / `@pytest.mark.llm` if it genuinely needs a real "
            "one.")

    missing = object()
    saved = {name: socket.socket.__dict__.get(name, missing) for name in ("connect", "connect_ex")}
    for name in saved:
        setattr(socket.socket, name, _refuse)
    try:
        yield
    finally:
        for name, original in saved.items():
            if original is missing:
                delattr(socket.socket, name)
            else:
                setattr(socket.socket, name, original)


__all__ = ["EVAL_TIME", "ORG", "PERIOD", "RETENTION_HORIZON", "GraphFixture", "GraphFact",
           "GraphNode", "MetricSeriesPoint"]
