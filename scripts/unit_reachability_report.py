"""K1a · which reasoning units actually reached a Finding on a real tenant — and why the rest did not.

    python scripts/unit_reachability_report.py --org <pilot> \\
        --database-url postgresql://…            [--at 2026-09-01T00:00:00Z] [--json]

WHY THIS EXISTS. Layer 4 holds twenty-five reasoner modules and twenty-two registered ids, and the
compiled lane scheduled six of them. Nothing in the system could say so. A unit that is never
declared, a unit that is declared and dropped, a unit that runs and finds nothing, and a unit that
runs and publishes a reading are four different states with four different fixes, and until this
report they were one undifferentiated silence. Doc 02's group gate asks for a number — *distinct
units producing Findings on the pilot* — and this is the command that prints it, next to the
receipt for every unit that produced none.

WHAT IT MEASURES, AND HOW. It runs the tenant's own compiled lane in SHADOW: the real situations,
the real corpus, the real manifests, the real orchestrator. It does not re-implement the lane —
that is the whole point. A report that assembled its own version of `shadow_compile` would answer
a question about the report. So it installs one recorder at the seam where `domain_shadow` hands a
capability to Layer 4, runs the pass that production runs, and reads the executions that come back.

FOUR STATES PER UNIT, NEVER FEWER:

    registered      the runtime holds an implementation for this id
    declared        a manifest for one of this tenant's situations named it
    scheduled       the Unit Selector kept it for that situation
    emitted         it published at least one Finding

and where a unit stops, the receipt that says why — a manifest decline
(`metadata["roster"]["declined"]`), a selector skip (`SkippedStep.reason_code` with the absent
fields), or a run status (`insufficient_context`, `failed`) with the unit's own reason codes.

READ-ONLY, AND NEVER IMPLICITLY PRODUCTION. The target resolves through `scripts/_db.py`, which
has no fallback to the application's configured `database_url`, and the engine is opened with
`postgresql_readonly=True`, so the SERVER refuses a write this script did not intend rather than a
reviewer catching it. The shadow pass writes nothing by construction (`publisher=None`,
`ExecutionMode.SHADOW`); the read-only transaction is the second lock, not the first.

THE INSTANT IS AN ARGUMENT. `--at` fixes the evaluation time for every situation in the pass, so
two runs of this report over the same graph are comparable. Omitting it reads the clock ONCE, here
at the process boundary, and prints what it read — the clock is never consulted inside the
reasoning it measures.

EXIT CODE. Non-zero on a breach of any K1a row this report owns:

    roster_v2 activated for this tenant                              (else the six-unit lane is
                                                                      what you just measured)
    distinct units emitting Findings                >= 12
    units that neither ran nor carry a receipt      == 0
    plan_hash recomputed from the same inputs       identical
    declared source units that are not registered   == 0
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._db import add_database_argument, resolve_database_url   # noqa: E402

#: Doc 02's group gate: distinct units producing Findings on the pilot.
MINIMUM_UNITS_EMITTING = 12

#: Registered units the compiled roster deliberately does not declare, and the decision that says
#: so (doc 02 U6). A stated dormancy is a receipt — it is the difference between "nobody thought
#: about this unit" and "this unit belongs to a lane that has not retired yet" — so these are
#: printed with their reason and are not counted as unreceipted silence. Anything else that is
#: registered, never declared and never skipped IS unreceipted, and fails the run.
STATED_DORMANT: dict[str, str] = {
    "core.signal_composition": "dormant by decision: legacy-lane only, no compiled consumer (U6)",
    "legacy.rule": "dormant by decision: the legacy strangler pair, until that lane retires (U6)",
    "legacy.score_gate": "dormant by decision: the legacy strangler pair, until that lane "
                         "retires (U6)",
}


class _ReadOnlyStore:
    """What `shadow_compile` needs of a `GraphStore` — its engine — and nothing more.

    A duck rather than a subclass because the read-only guarantee lives in the ENGINE's execution
    options: every connection this object hands out begins a read-only transaction, so a write
    fails at the server. Handing the pass a real `GraphStore` and trusting `live=False` would make
    the guarantee a property of an argument.
    """

    def __init__(self, engine) -> None:
        self.engine = engine


@dataclass
class UnitRow:
    """One unit's four states, aggregated over every situation in the pass."""

    unit_id: str
    registered: bool = False
    declared: int = 0
    scheduled: int = 0
    findings: int = 0
    situations_with_findings: int = 0
    declines: Counter = field(default_factory=Counter)
    skips: Counter = field(default_factory=Counter)
    statuses: Counter = field(default_factory=Counter)
    reason_codes: Counter = field(default_factory=Counter)
    missing_fields: Counter = field(default_factory=Counter)

    @property
    def receipted(self) -> bool:
        """Did every stop this unit made name itself?

        A unit that emitted is not silent. A unit that ran and published nothing is not silent
        either — it carries its own reason codes. Silence without a receipt is a unit that was
        neither declared, nor declined, nor skipped, nor run: nothing in the system accounts for
        it, and that is the state this report exists to make impossible.
        """
        if self.situations_with_findings or self.scheduled:
            return True
        if self.unit_id in STATED_DORMANT:
            return True
        return bool(self.declines or self.skips or self.statuses)

    def as_record(self) -> dict[str, Any]:
        return {"unit_id": self.unit_id, "registered": self.registered,
                "declared": self.declared, "scheduled": self.scheduled,
                "findings": self.findings,
                "situations_with_findings": self.situations_with_findings,
                "dormant_by_decision": STATED_DORMANT.get(self.unit_id),
                "declined": dict(sorted(self.declines.items())),
                "skipped": dict(sorted(self.skips.items())),
                "statuses": dict(sorted(self.statuses.items())),
                "reason_codes": dict(sorted(self.reason_codes.items())),
                "missing_fields": dict(sorted(self.missing_fields.items()))}


@dataclass
class Reachability:
    """Every row this report prints, and the verdicts computed from them."""

    org_id: str
    at: datetime
    activated_features: tuple[str, ...] = ()
    situations: int = 0
    executions: int = 0
    units: dict[str, UnitRow] = field(default_factory=dict)
    plan_hash_mismatches: tuple[str, ...] = ()
    unregistered_sources: tuple[str, ...] = ()
    counts: dict[str, int] = field(default_factory=dict)

    def row(self, unit_id: str) -> UnitRow:
        return self.units.setdefault(unit_id, UnitRow(unit_id))

    @property
    def units_emitting(self) -> tuple[str, ...]:
        return tuple(sorted(u.unit_id for u in self.units.values()
                            if u.situations_with_findings))

    @property
    def unreceipted(self) -> tuple[str, ...]:
        return tuple(sorted(u.unit_id for u in self.units.values()
                            if u.registered and not u.receipted))

    @property
    def checks(self) -> dict[str, bool]:
        return {
            "roster_v2_activated": "roster_v2" in self.activated_features,
            f"units_emitting_findings_at_least_{MINIMUM_UNITS_EMITTING}":
                len(self.units_emitting) >= MINIMUM_UNITS_EMITTING,
            "every_silent_unit_is_receipted": not self.unreceipted,
            "plan_hash_deterministic": not self.plan_hash_mismatches,
            "every_declared_source_is_registered": not self.unregistered_sources,
        }

    @property
    def ok(self) -> bool:
        return all(self.checks.values())

    def as_record(self) -> dict[str, Any]:
        return {"org_id": self.org_id, "at": self.at.isoformat(),
                "activated_features": list(self.activated_features),
                "situations": self.situations, "executions": self.executions,
                "units": [row.as_record() for row in
                          sorted(self.units.values(), key=lambda item: item.unit_id)],
                "units_emitting": list(self.units_emitting),
                "unreceipted": list(self.unreceipted),
                "plan_hash_mismatches": list(self.plan_hash_mismatches),
                "unregistered_sources": list(self.unregistered_sources),
                "compile_counts": dict(sorted(self.counts.items())),
                "checks": self.checks, "ok": self.ok}


def observe(report: Reachability, execution) -> None:
    """Fold one situation's execution into the per-unit rows.

    Pure bookkeeping over objects the lane already built: the manifest's roster receipt, the plan's
    kept and skipped steps, and each unit's result. Nothing here re-derives a reading.
    """
    from genios_engine.reason.plan import ReasoningPlanner

    report.executions += 1
    capability = execution.request.capability
    roster = capability.metadata.get("roster") or {}
    for unit_id, decline in (roster.get("declined") or {}).items():
        report.row(unit_id).declines[str(dict(decline).get("reason") or "declined")] += 1
    for spec in capability.reasoners:
        report.row(spec.reasoner_id).declared += 1
    for step in execution.plan.skipped:
        row = report.row(step.reasoner_id)
        row.skips[step.reason_code] += 1
        for name in step.missing_fields:
            row.missing_fields[name] += 1
    for result in execution.ordered_results:
        row = report.row(result.reasoner_id)
        row.scheduled += 1
        row.statuses[result.status.value] += 1
        row.findings += len(result.findings)
        row.situations_with_findings += int(bool(result.findings))
        for code in result.reason_codes:
            row.reason_codes[code] += 1
        for name in result.missing_fields:
            row.missing_fields[name] += 1

    # DETERMINISM, RE-ASKED RATHER THAN ASSERTED. The same manifest and the same frozen request
    # must produce the same plan, byte for byte — that is what makes a plan replayable, and it is
    # the one property of the selector a report can verify from outside.
    replanned = ReasoningPlanner().plan(capability, execution.request)
    if replanned.plan_hash != execution.plan.plan_hash:
        report.plan_hash_mismatches += (f"{capability.capability_id}@{capability.version}",)


def unregistered_sources(registry) -> tuple[str, ...]:
    """Source units the ROSTER declares by default that the registry cannot supply.

    `core.effort` was one of these for the life of `core.tradeoff` and nothing could see it. The
    registry refuses to be built with one now, so this reads zero — and reads it out loud, because
    a guarantee nobody prints is a guarantee nobody checks.
    """
    from genios_engine.reason.registry import declared_source_units

    known = registry.unit_ids
    missing: list[str] = []
    for (unit_id, _version), reasoner in sorted(registry._reasoners.items()):   # noqa: SLF001
        for source in declared_source_units(reasoner):
            if source not in known:
                missing.append(f"{unit_id} -> {source}")
    return tuple(sorted(set(missing)))


def read_only_engine(database_url: str):
    """An engine whose every transaction the SERVER will refuse writes on.

    Its own engine, not `platform/db.get_engine`: that one is the PROCESS's pooled engine, and
    disposing it here would tear down a pool the caller may still be holding. The driver
    normalisation matches the application's, because a report that reached the database through a
    different driver would be measuring a different connection than production uses.
    """
    from sqlalchemy import create_engine

    driver_url = database_url
    for prefix in ("postgresql://", "postgres://"):
        if driver_url.startswith(prefix):
            driver_url = "postgresql+psycopg://" + driver_url[len(prefix):]
            break
    return create_engine(driver_url, execution_options={"postgresql_readonly": True},
                         pool_pre_ping=True)


def collect(*, database_url: str, org_id: str, at: datetime, limit: int) -> Reachability:
    """Run the tenant's real compiled lane in shadow and record what every unit did."""
    from genios_engine.platform.l4_activation import activated_features
    from genios_engine.reason import domain_shadow
    from genios_engine.reason.reasoners import default_registry

    engine = read_only_engine(database_url)
    report = Reachability(org_id=org_id, at=at)
    try:
        report.activated_features = tuple(sorted(activated_features(engine, org_id)))
        registry = default_registry()
        for unit_id in sorted(registry.unit_ids):
            report.row(unit_id).registered = True
        report.unregistered_sources = unregistered_sources(registry)

        original = domain_shadow.reason_native_capability

        def recording(**kwargs):
            execution = original(**kwargs)
            observe(report, execution)
            return execution

        # ONE instrumentation point, at the seam the pass itself uses, restored unconditionally.
        # Everything before it — routing, compiling, the weld — is the production path untouched,
        # which is the only way this report can claim to describe production.
        domain_shadow.reason_native_capability = recording
        try:
            counts = domain_shadow.shadow_compile(
                store=_ReadOnlyStore(engine), org_id=org_id, eval_time=at,
                limit=limit, live=False)
        finally:
            domain_shadow.reason_native_capability = original
        report.counts = {str(key): int(value) for key, value in counts.items()}
        report.situations = report.counts.get("situations", 0)
    finally:
        engine.dispose()
    return report


def render(report: Reachability) -> str:
    lines = [f"unit reachability · org={report.org_id} · at={report.at.isoformat()}",
             f"activated: {', '.join(report.activated_features) or '(none)'}",
             f"situations={report.situations} reasoned={report.executions}",
             "",
             f"{'unit':<24}{'reg':>4}{'decl':>6}{'sched':>7}{'find':>6}  why not"]
    for row in sorted(report.units.values(), key=lambda item: item.unit_id):
        why: list[str] = []
        for reason, count in sorted(row.declines.items()):
            why.append(f"declined:{reason}×{count}")
        for reason, count in sorted(row.skips.items()):
            why.append(f"skipped:{reason}×{count}")
        for status, count in sorted(row.statuses.items()):
            if status != "completed":
                why.append(f"{status}×{count}")
        if row.unit_id in STATED_DORMANT and not row.declared:
            why.append(STATED_DORMANT[row.unit_id])
        if row.scheduled and not row.situations_with_findings:
            why.append("ran, published no finding: "
                       + ",".join(sorted(row.reason_codes)[:3] or ["(no reason codes)"]))
        lines.append(f"{row.unit_id:<24}{'y' if row.registered else 'n':>4}{row.declared:>6}"
                     f"{row.scheduled:>7}{row.findings:>6}  {'; '.join(why)}")
    lines += ["", f"units emitting findings: {len(report.units_emitting)} "
                  f"({', '.join(report.units_emitting) or 'none'})"]
    if report.unreceipted:
        lines.append(f"UNRECEIPTED SILENCE: {', '.join(report.unreceipted)}")
    if report.plan_hash_mismatches:
        lines.append(f"PLAN HASH DRIFT: {', '.join(report.plan_hash_mismatches)}")
    if report.unregistered_sources:
        lines.append(f"GHOST SOURCES: {', '.join(report.unregistered_sources)}")
    lines.append("")
    for name, ok in report.checks.items():
        lines.append(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    lines.append("")
    lines.append("K1a: " + ("PASS" if report.ok else "FAIL"))
    return "\n".join(lines)


def parse_instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("--at must carry a timezone, e.g. 2026-09-01T00:00:00Z")
    return parsed.astimezone(timezone.utc)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--org", required=True, help="the tenant to measure")
    parser.add_argument("--at", type=parse_instant, default=None,
                        help="evaluation instant (ISO-8601, timezone required). Omitted: the "
                             "clock is read once, here at the boundary, and printed.")
    parser.add_argument("--limit", type=int, default=200,
                        help="how many active situations to compile (default 200)")
    parser.add_argument("--json", action="store_true", help="emit the record instead of the table")
    add_database_argument(parser)
    args = parser.parse_args(argv)

    url = resolve_database_url(args, purpose="unit reachability report (read-only)")
    at = args.at or datetime.now(timezone.utc)
    report = collect(database_url=url, org_id=args.org, at=at, limit=args.limit)
    print(json.dumps(report.as_record(), indent=2, sort_keys=True) if args.json
          else render(report))
    return 0 if report.ok else 1


if __name__ == "__main__":       # pragma: no cover - the entry point itself
    raise SystemExit(main())
