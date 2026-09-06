"""The COVERAGE LENS — one org's tri-state coverage, read once, injected everywhere.

The absence classifier is pure: it is handed what could have been seen and decides what an
absence means. This is the thing that reads it. One query for the whole tenant, because there are
as many coverage rows as there are registered domains (four) and a per-situation lookup would be
223 queries against a table with four rows in it — the same argument `importance.read_domain_
coverage` makes one file over.

**Three fields, and each one is load-bearing:**

    ready    tri-state. `None` is NOT `False`. A domain with no row has never been declared for
             this tenant, which is "we did not assess" — and assessing nothing is not evidence
             that a source is missing, nor that it is present.
    basis    WHAT WE LOOKED AT: the capabilities that were connected when the declaration was
             filed. `MissingFact` requires it for `GENUINELY_ABSENT`, because the receipt for
             "we looked and it was not there" is the list of what we looked at, and a claim with
             no receipt is a guess.
    epoch    which coverage regime the absence is being drawn under, so it can be revoked later.

**Why not reuse `importance.read_domain_coverage`.** That reader collapses the tri-state on
purpose — it returns `dict[str, bool]` and drops rows whose `coverage_ready` is null, because
step 4's penalty is for coverage we know we lack. Dropping the row is right there and wrong here:
this lens's entire subject is the difference between "not covered" and "not assessed", and a
reader that cannot represent the second cannot type an absence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from sqlalchemy import text

from genios_engine.context.domain_spec import canonical_domain
from genios_engine.context.quality.epoch import CoverageEpoch, current_epochs

COVERAGE_TABLE = "source_coverage"

#: What `freshness` calls a capability that is connected and flowing. Only a fresh capability is
#: part of the basis: a paused mailbox produces the same empty result set as a connected one with
#: nothing in it, so counting it as "what we looked at" would put a receipt under a claim nobody
#: could have checked. Same constant, same reasoning, as `capture.coverage.declaration.FRESH`.
FRESH = "fresh"


@dataclass(frozen=True, slots=True)
class CoverageLens:
    """What this org could see, per domain, at the instant the declaration was filed.

    PURE once built. Every consumer takes the lens as a parameter, so a classification is
    reproducible from the lens alone and a test never needs a database to prove the cascade.
    """

    org_id: str
    #: domain -> coverage_ready. A domain ABSENT from this mapping was never declared, and that
    #: is a different fact from a domain declared not-ready. Never collapse the two by using
    #: `.get(domain, False)`; use `ready_for`.
    ready: Mapping[str, bool] = field(default_factory=dict)
    #: domain -> the capabilities that were connected and FRESH. The receipt.
    basis: Mapping[str, tuple[str, ...]] = field(default_factory=dict)
    #: domain -> the current coverage epoch. Stamped onto every absence drawn through this lens.
    epochs: Mapping[str, int] = field(default_factory=dict)

    def ready_for(self, domain: str | None) -> bool | None:
        """TRI-STATE. `None` for a domain nobody declared — never `False`.

        Aliases resolve first (`investor` is `fundraising`), because a situation carries the
        domain its correlation was filed under and the coverage row carries the registered name.
        Without this an aliased domain would read as undeclared and every one of its absences
        would be `UNKNOWABLE` — safe, and silently useless.
        """
        return self.ready.get(canonical_domain(domain))

    def basis_for(self, domain: str | None) -> tuple[str, ...]:
        """What was consulted. Empty when nothing was, which is what stops a `GENUINELY_ABSENT`
        with no receipt from being constructible at all."""
        return tuple(self.basis.get(canonical_domain(domain), ()))

    def epoch_for(self, domain: str | None) -> int | None:
        """The regime an absence drawn now is being drawn under, or `None` if unrecorded."""
        return self.epochs.get(canonical_domain(domain))


def read_coverage_lens(conn, org_id: str) -> CoverageLens:
    """One org's whole coverage picture, in two queries.

    The `freshness` map is filtered to FRESH before it becomes the basis, for the reason `FRESH`
    gives above. `required` is deliberately NOT part of the basis: a capability the domain
    requires and does not have is the reason coverage is not ready, not something we looked at.
    """
    rows = conn.execute(text(
        f"select domain, coverage_ready, freshness from {COVERAGE_TABLE} where org_id = :o"),
        {"o": org_id}).mappings().all()
    ready: dict[str, bool] = {}
    basis: dict[str, tuple[str, ...]] = {}
    for row in rows:
        domain = str(row["domain"])
        if row["coverage_ready"] is not None:
            ready[domain] = bool(row["coverage_ready"])
        freshness = row["freshness"] or {}
        if not isinstance(freshness, Mapping):
            freshness = {}
        basis[domain] = tuple(sorted(cap for cap, status in freshness.items()
                                     if str(status) == FRESH))
    epochs = {domain: epoch.epoch for domain, epoch in current_epochs(conn, org_id).items()}
    return CoverageLens(org_id=org_id, ready=ready, basis=basis, epochs=epochs)


def lens_from_epochs(org_id: str, epochs: Mapping[str, CoverageEpoch]) -> CoverageLens:
    """A lens built from epoch rows alone — what coverage was, at a PAST instant.

    `read_coverage_lens` answers "now" because `source_coverage` is an upsert. Replaying a past
    decision needs the regime that held THEN, and that only exists in `coverage_epochs`. Pair it
    with `epoch_at` per domain and an absence can be re-typed exactly as it was typed in March.

    The basis comes off the epoch's stored `capability=status` receipt rather than from today's
    connection set, for the same reason: today's connections are not evidence about March.
    """
    ready: dict[str, bool] = {}
    basis: dict[str, tuple[str, ...]] = {}
    numbers: dict[str, int] = {}
    for domain, epoch in epochs.items():
        ready[domain] = epoch.coverage_ready
        numbers[domain] = epoch.epoch
        fresh: list[str] = []
        for entry in epoch.capabilities:
            capability, _, status = str(entry).partition("=")
            if status == FRESH:
                fresh.append(capability)
        basis[domain] = tuple(sorted(fresh))
    return CoverageLens(org_id=org_id, ready=ready, basis=basis, epochs=numbers)


__all__ = ["COVERAGE_TABLE", "FRESH", "CoverageLens", "lens_from_epochs", "read_coverage_lens"]
