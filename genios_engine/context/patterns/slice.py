"""The GRAPH SLICE — everything one anchor's evaluation is allowed to see, as injected data.

WHY A SLICE AND NOT A CONNECTION. `matcher.match` is pure by contract: same slice, same
`eval_time`, byte-identical result. A matcher that could open a cursor would be a matcher whose
answer depends on when it ran and on which replica answered, and doc 09's H8 gate diffs pattern
results across runs. So the whole read happens once, at the boundary (`store.slices_for`), and
everything below it is arithmetic over a frozen record.

WHY THE SLICE CARRIES `edge_coverage` AND `absences`, AND WHY THAT IS THE INTERESTING PART. Two of
the eight condition kinds make a NEGATIVE claim — `absence` and `edge ... missing` — and a
negative claim is only licensed when a source that could have carried the fact was actually
checked. `absences` carries L2.5.5's typed answer for the facts; `edge_coverage` carries the same
answer for edge types, because an org with no CRM connected has no `owns` edges at all and
"nobody owns this contract" is then a statement about our plumbing wearing the typography of a
statement about the customer.

Nothing here reads a clock, opens a connection, or imports a store.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from genios_engine.contracts.analytic import Anomaly, CohortPosition, Trend
from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.quality import AbsenceType, MissingFact
from genios_engine.contracts.visibility import Visibility


@dataclass(frozen=True, slots=True)
class SliceNode:
    node_id: str
    node_type: str
    display_name: str | None = None


@dataclass(frozen=True, slots=True)
class SliceFact:
    """One current fact, with the receipt that produced it.

    `spans` is optional and frequently empty: most graph facts are written by the structured lane
    from a CRM field, which has no quote to point at. The evidence a pattern match reports is the
    FACT ROW — `fact_version_id` — and a span when one exists; that distinction is why
    `ConditionEvidence.ref` is required and `spans` is not.
    """

    subject_node_id: str
    field_path: str
    value: Any
    fact_version_id: str
    occurred_at: datetime | None = None
    value_type: str = "text"
    spans: tuple[EvidenceSpan, ...] = ()
    #: Who could see the evidence this fact came from. Carried so `framing` can filter before it
    #: builds a prompt, never widened.
    visibility: Visibility | None = None


@dataclass(frozen=True, slots=True)
class SliceEdge:
    edge_version_id: str
    edge_type: str
    from_node_id: str
    to_node_id: str
    confidence_bp: int = 0


@dataclass(frozen=True, slots=True)
class SliceObservation:
    observation_id: str
    subject_node_id: str
    kind: str
    occurred_at: datetime | None = None
    spans: tuple[EvidenceSpan, ...] = ()
    visibility: Visibility | None = None


@dataclass(frozen=True, slots=True)
class GraphSlice:
    """One anchor and everything hanging off it, as at `read_at`.

    A slice is per-ANCHOR rather than per-org so the evaluator's cost is bounded by the anchor's
    neighbourhood, and so a pattern cannot accidentally match a fact about a different company
    that happens to be in the same tenant.
    """

    org_id: str
    anchor: SliceNode
    facts: tuple[SliceFact, ...] = ()
    edges: tuple[SliceEdge, ...] = ()
    observations: tuple[SliceObservation, ...] = ()
    #: L2.5.5's typed answers for this anchor. An expected fact with NO entry here is UNKNOWN, not
    #: absent — `absence_for` returns None and the condition fails, which is the safe direction.
    absences: tuple[MissingFact, ...] = ()
    trends: tuple[Trend, ...] = ()
    cohort_positions: tuple[CohortPosition, ...] = ()
    anomalies: tuple[Anomaly, ...] = ()
    #: Edge types whose ABSENCE is knowable for this org — i.e. a connected source could have
    #: carried them and was checked. An edge type outside this set can never satisfy a `missing`
    #: condition. Empty by default: nothing is knowably absent until somebody says it is.
    edge_coverage: frozenset[str] = frozenset()
    #: `@authority_threshold`, in minor units, resolved from the Authority view at `eval_time`.
    #: `None` means NO RULE — which is a refusal, not a zero: a threshold of zero would make
    #: "high value" mean "any value" and fire the pattern on every contract in the org.
    authority_threshold_minor_units: int | None = None
    #: Which authority rule that number came from, for the receipt.
    authority_rule_id: str | None = None
    #: Signals/events attached to this anchor, carried through to the candidate as `members`.
    member_signal_ids: tuple[str, ...] = ()
    member_event_ids: tuple[str, ...] = ()
    #: When the slice was read. Carried for the receipt; the evaluator compares against the
    #: `eval_time` it is given, never against this.
    read_at: datetime | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    # -- lookups, all deterministic in the slice's own order ------------------------------------

    def fact(self, field_path: str) -> SliceFact | None:
        """The anchor's own fact at this path, or a fact about any node in the slice.

        Anchor first, and only then the wider slice. Checking only the anchor is the mistake
        `situations.refresh_situations` documents: `thread.ball_in_court` and `commitment.due_at`
        are written to PEOPLE, so a company-anchored pattern asking whose turn it is would never
        fire. Anchor-first ordering keeps the anchor's own answer authoritative when both exist.
        """
        for fact in self.facts:
            if fact.subject_node_id == self.anchor.node_id and fact.field_path == field_path:
                return fact
        for fact in self.facts:
            if fact.field_path == field_path:
                return fact
        return None

    def edges_of_type(self, edge_type: str, *, from_node_id: str | None = None,
                      to_node_id: str | None = None) -> tuple[SliceEdge, ...]:
        return tuple(e for e in self.edges
                     if e.edge_type == edge_type
                     and (from_node_id is None or e.from_node_id == from_node_id)
                     and (to_node_id is None or e.to_node_id == to_node_id))

    def absence_for(self, expected_fact: str) -> MissingFact | None:
        """The typed absence recorded for this anchor and this expected fact, if any.

        Anchor-scoped on purpose: a `GENUINELY_ABSENT` recorded about a different node is not
        evidence about this one, and matching by field name alone is how one company's missing
        owner becomes every company's.
        """
        for absence in self.absences:
            if (absence.subject_node_id == self.anchor.node_id
                    and absence.expected_fact == expected_fact):
                return absence
        return None

    def licensed_absence(self, expected_fact: str) -> MissingFact | None:
        """The absence ONLY IF it licenses a negative inference. The whole rule, in one place.

        `licenses_negative_inference` is computed by the contract and cannot be supplied, so this
        cannot be talked past at a call site: `GENUINELY_ABSENT` satisfies, and `UNKNOWABLE`,
        `STALE`, `NOT_EXPECTED` and `PRESENT` do not.
        """
        absence = self.absence_for(expected_fact)
        if absence is None or not absence.licenses_negative_inference:
            return None
        return absence

    def trend_for(self, metric: str) -> Trend | None:
        for trend in self.trends:
            if trend.metric == metric:
                return trend
        return None

    def position_for(self, metric: str) -> CohortPosition | None:
        for position in self.cohort_positions:
            if position.metric == metric:
                return position
        return None

    def anomaly_for(self, metric: str) -> Anomaly | None:
        for anomaly in self.anomalies:
            if anomaly.metric == metric:
                return anomaly
        return None

    def observations_of(self, kind: str) -> tuple[SliceObservation, ...]:
        return tuple(o for o in self.observations if o.kind == kind)


__all__ = ["AbsenceType", "GraphSlice", "MissingFact", "SliceEdge", "SliceFact", "SliceNode",
           "SliceObservation"]
