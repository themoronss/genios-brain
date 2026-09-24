"""L1.6.6-U1 · Domain tagging — the existing hint resolver, with the never-filter rule enforced.

**This unit does not re-derive domains.** `capture/domain/hints.py` already does that and it
works; the plan marks L1.6.6 "exists, one rule to preserve", so `domain_hints()` is IMPORTED and
called, never copied. What did not exist is the half around it: the answer to "what happens when
this signal's domain is not covered yet", which was previously nothing at all.

**THE RULE THAT MUST NOT BE LOST — never filter here.** An uncovered domain gets a
degraded-compile flag and an observation card; it is never a discard. The reason is stated in the
plan and it is permanent damage rather than a missed card: L2's cross-domain correlator can only
correlate what reached it, so a signal dropped for being in an uncovered domain removes one side
of every future correlation involving that domain — including correlations that would have been
possible later, once the domain WAS covered. There is no backfill for a signal that was never
stored. Consequently `DomainTagging.hints` is the unfiltered output of `domain_hints()`, always,
and coverage only ever ADDS a flag beside it.

**The second rule, which lives inside `hints.py` and is preserved by not touching it.** The
`_KEYWORDS` mapping is ORDERED and its order is load-bearing: `fundraising` is tested before
`sales` because an investor thread says "deck", "round" and "diligence" and *also* says "budget"
and "contract", and letting the generic sales vocabulary claim it is how six VCs and three
accelerator programmes became sales opportunities in one org's graph. This unit preserves that by
keeping the returned tag order exactly as `domain_hints()` produced it — no sorting, no set, no
dedup pass that reorders. `context/correlation.resolve_domain` reads this list positionally
(ties inside an origin rank keep arrival order), so re-sorting here would silently hand an
investor thread to the sales pack.

**Several domains is correct, not a bug to collapse.** An AWS renewal is Admin *and* Finance
*and* Engineering, and L2's correlator depends on all three surviving. Nothing in this unit
picks a winner; picking one is `resolve_domain`'s job, one layer up, and only for the single
field that needs a scalar.

**Public callable:** `tag_domains(source, text, *, coverage_fn=None) -> DomainTagging`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from genios_engine.capture.domain.hints import domain_hints
from genios_engine.contracts.gated_event import DomainHint

#: This unit's trace stage.
STAGE = "s4_domain_mapping"

#: `coverage_state` values `capture/coverage/model.compute_coverage` can return, plus the one
#: this unit adds. `unassessed` is NOT the same as `unknown_domain`: the first means nobody asked
#: (no `coverage_fn` was wired), the second means the coverage model was asked and answered that
#: it has no requirements registered for this domain at all. Collapsing them would make an
#: un-wired caller look like a tenant with an unregistered domain.
STATE_UNASSESSED = "unassessed"

#: Why an observation card exists. One string per cause, because "degraded" with no cause is a
#: card an operator cannot act on.
REASON_UNCOVERED = "domain_not_covered"
REASON_UNASSESSABLE = "coverage_not_assessable"


@dataclass(frozen=True)
class DomainObservation:
    """The observation card an uncovered domain produces INSTEAD of a discard.

    It carries the domain, the cause, and the coverage model's own state string, so the card can
    say "fundraising has no capability requirements registered" rather than the useless
    "coverage not ready". `missing_required` is the capabilities that would fix it — the card is
    a piece of onboarding work, and a card that does not name the work is a notification.
    """

    domain: str
    reason: str
    coverage_state: str
    missing_required: tuple[str, ...] = ()

    @property
    def message(self) -> str:
        missing = ", ".join(self.missing_required) if self.missing_required else "none named"
        return (f"domain {self.domain!r} is not covered ({self.coverage_state}); signals in it "
                f"are published with a degraded-compile flag, never dropped. "
                f"Missing capabilities: {missing}.")


@dataclass(frozen=True)
class DomainTagging:
    """Every domain this signal carries, plus what coverage says about them.

    `hints` is the complete, unfiltered, order-preserving tag list — the never-filter rule made
    into a data shape, since a caller reading this field cannot accidentally receive a pruned
    one. `covered` and `uncovered` PARTITION the domains in `hints`; they are reporting, and
    neither of them is the list a consumer should publish from.
    """

    hints: tuple[DomainHint, ...]
    covered: tuple[str, ...]
    uncovered: tuple[str, ...]
    #: True when at least one domain is uncovered. The flag that travels with the published
    #: signal so L3 compiles it in degraded mode instead of pretending full expertise.
    degraded_compile: bool
    observations: tuple[DomainObservation, ...]
    #: 6-U3 · domain names the proposer put forward that this deployment does not run.
    #:
    #: CARRIED, NEVER DROPPED. A proposer saying `procurement` for a tenant with no procurement
    #: corpus has told us two true things — something about this message, and something about a
    #: gap in our own coverage. `context/extract/vocab.py` records what dropping these costs:
    #: *268 distinct field names in one org, 192 of them used exactly once*, a vocabulary that
    #: grew unwatched because every unrecognised name went somewhere nobody counted.
    #:
    #: It is NOT in `hints` and must never be: these are names the ontology refused, and putting
    #: them in the tag list would make an unknown proposal indistinguishable from a real domain.
    proposed_unknown: tuple[str, ...] = ()

    @property
    def domains(self) -> tuple[str, ...]:
        """Domain names in tag order, deduplicated, first occurrence wins — the order
        `resolve_domain` reads positionally."""
        seen: list[str] = []
        for hint in self.hints:
            if hint.domain not in seen:
                seen.append(hint.domain)
        return tuple(seen)

    @property
    def as_dicts(self) -> list[dict[str, Any]]:
        """The `GatedEvent.domain_hints` wire shape, order preserved.

        `confidence_bp` joined it on 2026-09-24. A field on the contract that this property drops
        is a field Layer 2 never sees — which is the exact loss step 3 spent its whole length
        closing at the other end of this same seam, so it is asserted rather than assumed
        (`test_the_wire_shape_carries_the_confidence_to_layer_two`).
        """
        return [{"domain": h.domain, "source": h.source, "confidence_bp": h.confidence_bp}
                for h in self.hints]


def _coverage_for(domain: str, coverage_fn: Callable[[str], Any] | None) -> tuple[bool, str,
                                                                                 tuple[str, ...]]:
    """(covered, state, missing_required) for one domain.

    A coverage lookup that raises must not fail a capture — the same rule
    `pipeline.coverage_verdict` follows — but it also must not report `covered`. It reports
    unassessable, which produces an observation card rather than silent confidence.
    """
    if coverage_fn is None:
        return False, STATE_UNASSESSED, ()
    try:
        verdict = coverage_fn(domain)
    except Exception:                             # noqa: BLE001 — coverage never fails a capture
        return False, REASON_UNASSESSABLE, ()
    if not isinstance(verdict, Mapping):
        return False, REASON_UNASSESSABLE, ()
    state = str(verdict.get("coverage_state") or STATE_UNASSESSED)
    missing = tuple(str(c) for c in (verdict.get("missing_required") or ()))
    return bool(verdict.get("coverage_ready")), state, missing


def tag_domains(source: str, text: str | None, *,
                coverage_fn: Callable[[str], Any] | None = None,
                fallback: str | None = None,
                proposer: Any | None = None) -> DomainTagging:
    """L1.6.6-U1 · tag a signal with every business domain it belongs to.

    `coverage_fn` maps a domain name to `capture/coverage/model.compute_coverage`'s dict, or is
    `None` for a caller that cannot assess coverage. Either way the tag list that comes back is
    complete: coverage decides whether a card is raised and whether the degraded flag is set, and
    it decides nothing else. There is no argument to this function that removes a tag.

    `proposer` is L1.6.6-U6's model client, added 2026-09-24 (step 6), and it is OPTIONAL in the
    strong sense: `None` is the shipping default and every caller that does not pass one gets
    exactly the deterministic behaviour it had before. A proposer that fails, times out or
    returns nonsense also lands here as "no proposals" — `propose_domains` never raises — so
    domain enrichment can never fail a capture (E7).

    THE PROPOSALS ARE MERGED, NEVER SUBSTITUTED. `merge_proposals` keeps every deterministic hint
    and its source; a keyword and a proposal that disagree BOTH survive, because resolving that
    disagreement silently is how *"six VCs and three accelerator programmes became sales
    opportunities"* (E8).
    """
    hints = list(domain_hints(source, text, fallback=fallback))
    proposal_outcome = None
    if proposer is not None:
        from genios_engine.capture.domain.hints import merge_proposals
        from genios_engine.capture.domain.proposer import propose_domains

        proposal_outcome = propose_domains(text, llm=proposer)
        if proposal_outcome.accepted:
            hints = merge_proposals(hints, proposal_outcome.accepted)
    hints = tuple(hints)

    covered: list[str] = []
    uncovered: list[str] = []
    observations: list[DomainObservation] = []
    for domain in dict.fromkeys(h.domain for h in hints):
        is_covered, state, missing = _coverage_for(domain, coverage_fn)
        if is_covered:
            covered.append(domain)
            continue
        uncovered.append(domain)
        reason = REASON_UNASSESSABLE if state in (STATE_UNASSESSED,
                                                  REASON_UNASSESSABLE) else REASON_UNCOVERED
        observations.append(DomainObservation(domain=domain, reason=reason, coverage_state=state,
                                              missing_required=missing))

    return DomainTagging(hints=hints, covered=tuple(covered), uncovered=tuple(uncovered),
                         degraded_compile=bool(uncovered), observations=tuple(observations),
                         proposed_unknown=tuple(proposal_outcome.unknown) if proposal_outcome
                         else ())


__all__ = ["REASON_UNASSESSABLE", "REASON_UNCOVERED", "STAGE", "STATE_UNASSESSED",
           "DomainObservation", "DomainTagging", "tag_domains"]
