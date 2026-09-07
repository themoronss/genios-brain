"""J4 acceptance report — do the three runtime brains actually hold anything, and how did it get in?

    python scripts/brain_content_report.py --org <pilot>

This is a literal row of the J4 gate command block, so it answers the gate's questions and
nothing else:

    Organization entries (discovered + admin-confirmed)   >= 3
    Behavior entries published through the L6 floors      >= 1
    Adaptive lease from card feedback                     >= 1
    entries written outside the L6 pipeline                = 0
    any row with brain = 'expert'                          = 0   (a DB check; asserted anyway)

**"HOW DID IT GET THERE" IS THE POINT.** A count alone cannot tell a brain that learned something
from a brain somebody seeded by hand, and doc 02's whole argument is that the difference between
what a company SAYS and what it DOES is only intelligence if both halves are real. So every entry
is attributed — discovered, admin-confirmed, distilled or leased — by joining it back to the
`learning_objects` row that proposed it. An entry with no proposal behind it is a WRITE OUTSIDE
THE PIPELINE, which is a gate row in its own right; an entry whose proposal this report cannot
attribute is `unattributed`, and that is a breach too, because a provenance nobody can name is a
provenance nobody can audit.

**THE ADAPTIVE BRAIN GETS AN EXTRA COLUMN: EXPIRED BUT NOT CLEARED.** `temporary_memories.
expires_at` is `NOT NULL`, and readers already filter on it, so an uncleared row misleads nobody
directly. It is reported because it is the only visible symptom of the expiry sweep having stopped
running — and a lease store that never retires anything is how a "temporary" memory quietly
becomes permanent. Zero is the gate.

**READ-ONLY, AND IT NAMES ITS OWN TARGET.** The connection is opened through
`scripts/_gate.read_only_connection`, so PostgreSQL itself refuses a write this report did not
intend, and the database is resolved through `scripts/_db.resolve_database_url` — which has no
fallback to the application's configured URL, because on any developer machine that URL is the
production tenant database and this script would inherit it just by being run.

**THE INSTANT IS AN ARGUMENT.** `build_report` takes `at`; `main` reads the clock once, at the
process boundary. A report whose helpers each called `now()` would compare a lease's expiry
against one instant and count it against another.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

if __package__ in (None, ""):                       # pragma: no cover - CLI import shim
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._db import add_database_argument, resolve_database_url        # noqa: E402
from scripts._gate import read_only_connection, sql                        # noqa: E402

#: The three brains, in the order doc 02's table lists them. `expert` is deliberately absent: it
#: is not a row in this table and cannot become one — `learned_brain_no_expert` is a CHECK.
BRAINS: tuple[str, ...] = ("organization", "behavior", "adaptive")

#: How an entry got there, by the unit that proposed it. The two Layer 3 pipelines are named by
#: their own constants (imported below) so a rename cannot leave this table quietly wrong; the
#: rest are the Layer 6 units that already write these brains.
PROVENANCE_BY_UNIT: dict[str, str] = {
    "pattern_learning": "discovered",           # L6 unit 3 — repeated enterprise patterns
    "admin_console": "admin-confirmed",
    "recommendation_learning": "distilled",     # L6 unit 8 — play efficacy
}

#: Fallback attribution, off the entry's own value. A producer that names its source in the value
#: is attributable even if this report has never heard of its unit.
PROVENANCE_BY_SOURCE: dict[str, str] = {
    "admin": "admin-confirmed", "admin_confirmed": "admin-confirmed",
    "card_feedback": "leased", "discovered": "discovered", "distilled": "distilled",
}

#: What an entry with no attributable origin is called. Never a silent "other": an entry whose
#: provenance cannot be named is one nobody can audit, and the gate counts it.
UNATTRIBUTED = "unattributed"

#: The gate thresholds, from doc 02 §6 / doc 06's J4 table.
MIN_ORGANIZATION_ENTRIES = 3
MIN_BEHAVIOR_ENTRIES = 1
MIN_ADAPTIVE_LEASES = 1


def _pipeline_units() -> dict[str, str]:
    """The unit → provenance table, with the Layer 3 pipelines added FROM THEIR OWN CONSTANTS.

    Read off the modules rather than spelled here, because a unit name that drifts out of step
    with this table does not break anything — it silently reclassifies real entries as
    `unattributed`, which is a gate row. N-3's discovery unit is imported defensively: this
    report is one gate command for two pipelines, and a missing half should report a short
    Organization count, not crash the whole report.
    """
    from genios_engine.packs.brains.adaptive_lease import LEASE_UNIT
    from genios_engine.packs.brains.behavior_distill import BEHAVIOR_UNIT

    table = {**PROVENANCE_BY_UNIT, BEHAVIOR_UNIT: "distilled", LEASE_UNIT: "leased"}
    try:
        from genios_engine.packs.brains.org_discovery import DISCOVERY_UNIT
    except ImportError:                                  # pragma: no cover - N-3 not landed
        return table
    return {**table, DISCOVERY_UNIT: "discovered"}


@dataclass(frozen=True, slots=True)
class BrainContent:
    """One brain's active entries, attributed."""

    brain: str
    entries: int
    by_provenance: dict[str, int] = field(default_factory=dict)
    outside_pipeline: int = 0
    unattributed: int = 0
    subjects: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {"brain": self.brain, "entries": self.entries,
                "by_provenance": dict(sorted(self.by_provenance.items())),
                "outside_pipeline": self.outside_pipeline, "unattributed": self.unattributed,
                "subjects": list(self.subjects)}


@dataclass(frozen=True, slots=True)
class LeaseContent:
    """The Adaptive brain's other half: `temporary_memories`, and the clock on each row."""

    live: int
    from_card_feedback: int
    expired_not_cleared: int
    cleared: int
    outside_pipeline: int
    expired_subjects: tuple[str, ...] = ()
    #: Every lease this tenant has EVER been granted through card feedback, live or retired.
    #: REPORTED, NEVER GATED — the gate row stays on the live count, because a brain holds what
    #: is current and a retired lease is not held. It exists because the live count alone cannot
    #: tell "this tenant never earned a lease" from "the lease it earned expired on Tuesday,
    #: exactly as a lease is supposed to", and those two zeros mean opposite things to an
    #: operator: the first is a broken path, the second is the clock working.
    from_card_feedback_ever: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {"live": self.live, "from_card_feedback": self.from_card_feedback,
                "from_card_feedback_ever": self.from_card_feedback_ever,
                "expired_not_cleared": self.expired_not_cleared, "cleared": self.cleared,
                "outside_pipeline": self.outside_pipeline,
                "expired_subjects": list(self.expired_subjects)}


@dataclass(frozen=True, slots=True)
class BrainContentReport:
    """Everything J4 asks about this tenant's brains, plus the verdict."""

    org_id: str
    at: datetime
    brains: tuple[BrainContent, ...]
    leases: LeaseContent
    expert_rows: int

    def brain(self, name: str) -> BrainContent:
        for content in self.brains:
            if content.brain == name:
                return content
        return BrainContent(brain=name, entries=0)

    @property
    def outside_pipeline(self) -> int:
        return sum(c.outside_pipeline for c in self.brains) + self.leases.outside_pipeline

    @property
    def unattributed(self) -> int:
        return sum(c.unattributed for c in self.brains)

    @property
    def checks(self) -> tuple[tuple[str, bool, str], ...]:
        """Every gate row: (label, passed, measured). The report IS this table."""
        org = self.brain("organization").entries
        behavior = self.brain("behavior").entries
        return (
            (f"organization entries >= {MIN_ORGANIZATION_ENTRIES}",
             org >= MIN_ORGANIZATION_ENTRIES, str(org)),
            (f"behavior entries >= {MIN_BEHAVIOR_ENTRIES}",
             behavior >= MIN_BEHAVIOR_ENTRIES, str(behavior)),
            (f"adaptive leases from card feedback >= {MIN_ADAPTIVE_LEASES}",
             self.leases.from_card_feedback >= MIN_ADAPTIVE_LEASES,
             str(self.leases.from_card_feedback)),
            ("writes outside the L6 pipeline == 0", self.outside_pipeline == 0,
             str(self.outside_pipeline)),
            ("entries with unnameable provenance == 0", self.unattributed == 0,
             str(self.unattributed)),
            ("expired leases not cleared == 0", self.leases.expired_not_cleared == 0,
             str(self.leases.expired_not_cleared)),
            ("rows with brain='expert' == 0", self.expert_rows == 0, str(self.expert_rows)),
        )

    @property
    def passed(self) -> bool:
        return all(ok for _label, ok, _measured in self.checks)

    def as_dict(self) -> dict[str, Any]:
        return {"org_id": self.org_id, "at": self.at.isoformat(),
                "brains": [c.as_dict() for c in self.brains], "leases": self.leases.as_dict(),
                "expert_rows": self.expert_rows,
                "checks": [{"check": label, "passed": ok, "measured": measured}
                           for label, ok, measured in self.checks],
                "passed": self.passed}


def _value(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except ValueError:
            return {}
    return dict(raw or {}) if isinstance(raw, dict) else {}


def _attribute(unit: str | None, value: dict[str, Any], units: dict[str, str]) -> str:
    """unit first, then the entry's own `source`, then `unattributed`. Never a guess."""
    if unit and unit in units:
        return units[unit]
    source = str(value.get("source") or "")
    if source in PROVENANCE_BY_SOURCE:
        return PROVENANCE_BY_SOURCE[source]
    return UNATTRIBUTED


_ENTRIES_SQL = (
    "select e.brain, e.subject, e.value, e.learning_id, o.unit "
    "from learned_brain_entries e "
    "left join learning_objects o on o.org_id = e.org_id and o.learning_id = e.learning_id "
    "where e.org_id = :o and e.active order by e.brain, e.subject")

_LEASES_SQL = (
    "select m.subject, m.value, m.active, m.expires_at, m.learning_id, o.unit "
    "from temporary_memories m "
    "left join learning_objects o on o.org_id = m.org_id and o.learning_id = m.learning_id "
    "where m.org_id = :o order by m.created_at, m.memory_id")

#: The Expert-brain check. The CHECK constraint makes a row impossible, which is exactly why the
#: report counts them rather than assuming: a constraint that was quietly dropped would otherwise
#: be discovered by a card citing a machine-edited Expert Brain.
_EXPERT_SQL = "select count(*) from learned_brain_entries where org_id = :o and brain = 'expert'"


def build_report(conn, *, org_id: str, at: datetime) -> BrainContentReport:
    """Read the three brains and the lease store. Takes its instant; reads no clock of its own."""
    from genios_engine.packs.brains.adaptive_lease import LEASE_UNIT as lease_unit

    units = _pipeline_units()

    grouped: dict[str, dict[str, Any]] = {
        brain: {"entries": 0, "provenance": {}, "outside": 0, "unattributed": 0, "subjects": []}
        for brain in BRAINS}
    for row in conn.execute(sql(_ENTRIES_SQL), {"o": org_id}).mappings():
        bucket = grouped.setdefault(str(row["brain"]), {
            "entries": 0, "provenance": {}, "outside": 0, "unattributed": 0, "subjects": []})
        bucket["entries"] += 1
        bucket["subjects"].append(str(row["subject"]))
        if row["unit"] is None:
            # No proposal behind the entry: it was written by something that is not the pipeline.
            bucket["outside"] += 1
        kind = _attribute(row["unit"], _value(row["value"]), units)
        bucket["provenance"][kind] = bucket["provenance"].get(kind, 0) + 1
        if kind == UNATTRIBUTED:
            bucket["unattributed"] += 1

    brains = tuple(BrainContent(
        brain=name, entries=data["entries"], by_provenance=dict(data["provenance"]),
        outside_pipeline=data["outside"], unattributed=data["unattributed"],
        subjects=tuple(data["subjects"])) for name, data in sorted(grouped.items()))

    live = leased = leased_ever = expired = cleared = lease_outside = 0
    expired_subjects: list[str] = []
    for row in conn.execute(sql(_LEASES_SQL), {"o": org_id}).mappings():
        expires_at = row["expires_at"]
        is_expired = expires_at is not None and expires_at <= at
        if not row["active"]:
            cleared += 1
        elif is_expired:
            expired += 1
            expired_subjects.append(str(row["subject"]))
        else:
            live += 1
        if row["learning_id"] is None or row["unit"] is None:
            lease_outside += 1
        from_feedback = (row["unit"] == lease_unit
                         or str(_value(row["value"]).get("source") or "") == "card_feedback")
        if from_feedback:
            leased_ever += 1
            if row["active"] and not is_expired:
                leased += 1

    leases = LeaseContent(live=live, from_card_feedback=leased, expired_not_cleared=expired,
                          cleared=cleared, outside_pipeline=lease_outside,
                          expired_subjects=tuple(expired_subjects),
                          from_card_feedback_ever=leased_ever)
    expert_rows = int(conn.execute(sql(_EXPERT_SQL), {"o": org_id}).scalar() or 0)
    return BrainContentReport(org_id=org_id, at=at, brains=brains, leases=leases,
                              expert_rows=expert_rows)


def _mark(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def render(report: BrainContentReport) -> str:
    lines = [f"J4 brain content — org={report.org_id}",
             f"  as of            {report.at:%Y-%m-%d %H:%M} UTC", ""]
    for content in report.brains:
        provenance = ", ".join(f"{kind} {count}"
                               for kind, count in sorted(content.by_provenance.items())) or "—"
        lines.append(f"  {content.brain:<13} {content.entries:>4} active   {provenance}")
        if content.outside_pipeline:
            lines.append(f"    {content.outside_pipeline} entr(ies) with NO learning object — "
                         "written outside the L6 pipeline")
    lines += ["",
              f"  adaptive leases  {report.leases.live} live "
              f"({report.leases.from_card_feedback} from card feedback), "
              f"{report.leases.cleared} cleared, "
              f"{report.leases.expired_not_cleared} EXPIRED AND NOT CLEARED",
              f"                   {report.leases.from_card_feedback_ever} granted through card "
              "feedback in this tenant's history (reported, not gated)"]
    for subject in report.leases.expired_subjects:
        lines.append(f"    expired, still active: {subject}")
    if not any(c.entries for c in report.brains):
        lines += ["", "  NOTHING IS IN ANY BRAIN. An empty brain is not a pass — it is the state "
                      "a pipeline with no producer has always been in."]
    lines += [""]
    lines += [f"  [{_mark(ok)}] {label:<45} {measured}" for label, ok, measured in report.checks]
    lines += ["", f"  VERDICT: {_mark(report.passed)}"]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="brain_content_report",
        description="J4 acceptance report: what is in the three runtime brains, and how it got in")
    parser.add_argument("--org", required=True, help="the tenant to report on")
    parser.add_argument("--at", default=None,
                        help="ISO-8601 instant to evaluate expiry against (default: now, UTC)")
    parser.add_argument("--json", action="store_true", help="emit the report as JSON")
    add_database_argument(parser)
    args = parser.parse_args(argv)

    at = datetime.now(timezone.utc) if args.at is None else datetime.fromisoformat(args.at)
    if at.tzinfo is None:
        parser.error("--at must be timezone-aware; a naive instant means whatever the host's "
                     "locale happens to be, and a lease's expiry is a real moment")

    url = resolve_database_url(args, purpose="J4 brain content report (read-only)")

    from genios_engine.platform.db import get_engine
    conn = read_only_connection(get_engine(url))
    try:
        report = build_report(conn, org_id=args.org, at=at)
    finally:
        conn.close()

    print(json.dumps(report.as_dict(), indent=2) if args.json else render(report))
    return 0 if report.passed else 1


if __name__ == "__main__":                              # pragma: no cover - CLI entry
    raise SystemExit(main())
