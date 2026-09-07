"""J1 · the WELD report — Layer 3's typed consumers, measured rather than asserted.

    python scripts/weld_report.py --fixtures --at 2026-08-08T12:00:00Z
    python scripts/weld_report.py --org <pilot> --at 2026-08-08T12:00:00Z \\
        --database-url postgresql://…

WHY A REPORT AND NOT ONLY A TEST. Doc 03's own warning is that activation "would LOOK successful
while producing generic output": every unit test can pass while 63% of the corpus reaches nobody,
because a unit test asks "does this function work" and the gate asks "did the knowledge arrive".
Those are different questions and only the second one is J1. So this script measures the eight J1
rows over real compiled output and exits non-zero when one of them breaks.

TWO LANES, ONE VERDICT.

  --fixtures  compiles the SHIPPED corpus against a small set of situations built in memory and
              welds each one. No database, no network. This is the lane doc 06 names
              (`python scripts/weld_report.py --fixtures`) and the one that can run in CI, because
              the thing under test is the corpus plus the adapter and neither lives in a database.
  --org       reads what production actually welded: `reasoning_capability_snapshots.manifest ->
              metadata -> weld`, written by `reason/adapters/expertise.py` on the live pass. It
              proves the same eight rows against real tenant traffic rather than against a fixture,
              which is the difference between "the code can do this" and "the code did this".

READ-ONLY, AT THE SERVER, AND NEVER IMPLICITLY PRODUCTION. `set transaction read only` is the
first statement of the transaction (`scripts/_gate.py`), and the target is resolved through
`scripts/_db.py`, which has no fallback to the application's configured `database_url` — the
variable that, on a developer machine with a `.env`, is the live tenant database.

NO CLOCK. `--at` is required in both lanes and is the evaluation time every predicate is bound
against. A report that read `now()` would produce a different answer every run for reasons that
have nothing to do with the weld, and "same situation, same snapshot, byte-identical result" is
Law 2 — which this script's `--fixtures` lane checks by welding each fixture twice.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from genios_engine.platform.canonical import semantic_hash            # noqa: E402
from scripts._db import add_database_argument, resolve_database_url   # noqa: E402
from scripts._gate import read_only_connection, sql                   # noqa: E402

#: The five authored classes. A consumer for each is J1's first row, and the row is checked
#: against the receipt rather than against a reading of the code: a class whose receipt records
#: nothing was not consumed, whatever the module docstrings claim.
ARTIFACT_CLASSES = ("decision_framework", "heuristic", "mental_model", "playbook", "rule")

#: The receipt keys that PROVE a class was consumed. `no_tag_overlap` and the cap refusals are
#: consumption too — the consumer looked, and said no by name — which is why a refusal counts.
#: What does not count is silence.
CONSUMER_EVIDENCE = {
    "decision_framework": ("framing", "over_framing_cap", "capability_not_routed",
                           "statement_missing", "no_tag_overlap"),
    "heuristic": ("cited", "over_citation_cap", "capability_not_routed", "statement_missing",
                  "no_tag_overlap", "contradicts_fired_rule"),
    "mental_model": ("framing", "over_framing_cap", "capability_not_routed", "statement_missing",
                     "no_tag_overlap"),
    "playbook": ("consumed_as_play",),
    "rule": ("consumed_as_compiled_constraint", "fired"),
}

#: The receipt string the play converter used for every non-playbook class before the typed
#: consumers existed. J1 requires it to reach zero on the four classes that now have readers;
#: the string itself stays in the code for a sixth class nobody has written a consumer for yet.
LEGACY_UNSUPPORTED = "no_steps_artifact_unsupported"

#: Situations the `--fixtures` lane welds. Each is a real L2 situation type against the shipped
#: corpus, chosen because it exercises a different J1 row: `deal` with a licensed absence fires the
#: `urgency_must_belong_to_the_buyer` blocking rule; the same deal WITHOUT that absence leaves it
#: UNKNOWN, which is the row that proves an unevaluable rule neither passes nor blocks.
FIXTURES: tuple[dict[str, Any], ...] = (
    {"name": "deal_with_a_licensed_absence", "type": "deal", "domain": "sales",
     "facts": {"deal.status": "open", "thread.ball_in_court": "them"},
     "observations": ("proposal_sent", "verbal_yes"), "edges": 4,
     "absent": ("commitment.due_at",)},
    {"name": "deal_with_an_unknown_absence", "type": "deal", "domain": "sales",
     "facts": {"deal.status": "open", "thread.ball_in_court": "them"},
     "observations": ("proposal_sent", "verbal_yes"), "edges": 4, "absent": ()},
    {"name": "relationship", "type": "relationship", "domain": "sales",
     "facts": {"thread.ball_in_court": "us"}, "observations": ("question",), "edges": 2,
     "absent": ()},
)


@dataclass(frozen=True)
class WeldSample:
    """One welded capability: where it came from, and everything J1 asks about it."""

    source: str
    capability_id: str
    receipt: dict[str, Any]
    citations: tuple[dict[str, Any], ...] = ()
    constraints: tuple[dict[str, Any], ...] = ()
    framing_blocks: tuple[dict[str, Any], ...] = ()
    rule_verdicts: tuple[dict[str, Any], ...] = ()
    #: play id -> the rule ids a fired blocking rule removed it for.
    eliminations: dict[str, tuple[str, ...]] = field(default_factory=dict)
    #: Only the fixtures lane can answer this; a stored manifest is one observation, not two.
    reproducible: bool | None = None

    @property
    def by_class(self) -> dict[str, dict[str, int]]:
        value = self.receipt.get("by_class") or {}
        # `Mapping`, not `dict`: an in-memory weld hands back the contract's frozen
        # `MappingProxyType` and a stored one hands back a plain dict from `jsonb`. Testing for
        # `dict` scored the frozen half as "no consumer" — a gate that reads red for the lane it
        # was written to check.
        if not isinstance(value, Mapping):
            return {}
        return {str(klass): {str(k): int(v) for k, v in dict(counters).items()}
                for klass, counters in value.items()}


@dataclass(frozen=True)
class WeldVerdict:
    """The J1 table over a set of welded capabilities."""

    at: datetime
    lane: str
    samples: int
    classes_with_consumer: tuple[str, ...]
    legacy_unsupported_receipts: int
    blocking_eliminations: int
    decisions_with_a_heuristic_citation: int
    unknown_rules: int
    unknown_rules_that_fired_or_blocked: int
    citations_checked: int
    citations_verbatim: int
    play_cap_situation_fit_wins: int
    play_cap_alphabetical_wins: int
    llm_call_sites: int
    reproducible: bool | None
    refusals: dict[str, int]

    @property
    def classes_passed(self) -> bool:
        return len(self.classes_with_consumer) == len(ARTIFACT_CLASSES)

    @property
    def verbatim_passed(self) -> bool:
        return self.citations_checked == self.citations_verbatim

    @property
    def unknown_passed(self) -> bool:
        return self.unknown_rules_that_fired_or_blocked == 0

    @property
    def play_cap_passed(self) -> bool:
        """A cut is only legitimate when what it cut was NOT situation-fit while something that
        survived was. `play_cap_alphabetical_wins` counts the opposite: a non-fit play surviving
        while a fit play was cut — the exact defect CLG-07 exists to end."""
        return self.play_cap_alphabetical_wins == 0

    @property
    def passed(self) -> bool:
        """A run with no samples is NOT a pass. Nothing was measured, and a gate that returns
        green on an empty table is how "the weld never ran" reads as success."""
        return bool(self.samples) and self.classes_passed and self.verbatim_passed \
            and self.unknown_passed and self.play_cap_passed \
            and self.legacy_unsupported_receipts == 0 and self.llm_call_sites == 0 \
            and self.blocking_eliminations >= 1 \
            and self.decisions_with_a_heuristic_citation >= 1 \
            and self.reproducible is not False

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate": "J1", "lane": self.lane, "at": self.at.isoformat(),
            "samples": self.samples,
            "artifact_classes_with_a_consumer":
                f"{len(self.classes_with_consumer)} of {len(ARTIFACT_CLASSES)}",
            "classes": list(self.classes_with_consumer),
            "legacy_unsupported_receipts": self.legacy_unsupported_receipts,
            "blocking_rule_eliminations": self.blocking_eliminations,
            "welds_carrying_a_heuristic_citation": self.decisions_with_a_heuristic_citation,
            "unknown_rules": self.unknown_rules,
            "unknown_rules_that_fired_or_blocked": self.unknown_rules_that_fired_or_blocked,
            "citations_verbatim": f"{self.citations_verbatim}/{self.citations_checked}",
            "play_cap_situation_fit_wins": self.play_cap_situation_fit_wins,
            "play_cap_alphabetical_wins": self.play_cap_alphabetical_wins,
            "llm_call_sites_in_the_adapters": self.llm_call_sites,
            "byte_identical_reweld": self.reproducible,
            "refusals": self.refusals,
            "checks": {
                "five_of_five_classes": self.classes_passed,
                "no_legacy_unsupported_receipts": self.legacy_unsupported_receipts == 0,
                "a_blocking_rule_eliminated_a_candidate": self.blocking_eliminations >= 1,
                "a_weld_carried_a_heuristic_citation":
                    self.decisions_with_a_heuristic_citation >= 1,
                "unknown_never_coerced": self.unknown_passed,
                "citations_byte_identical": self.verbatim_passed,
                "situation_fit_beats_alphabetical": self.play_cap_passed,
                "zero_llm": self.llm_call_sites == 0,
                "reproducible": self.reproducible is not False,
            },
            "passed": self.passed,
        }


# =================================================================================================
# THE MEASUREMENTS — pure functions over samples, so both lanes are scored identically
# =================================================================================================

def llm_call_sites() -> int:
    """How many model call sites exist in the three weld modules. J1 requires zero.

    Read from the SOURCE rather than from a mock, because the claim is structural: an adapter that
    grew a model call would still pass every behavioural test that does not happen to exercise it.
    The same check runs as a unit test; it is repeated here so the gate's own report answers the
    question rather than pointing at a test suite.
    """
    root = Path(__file__).resolve().parents[1] / "genios_engine" / "reason" / "adapters"
    needles = ("anthropic", "openai", "llm_client", "complete(", "chat.completions")
    hits = 0
    for name in ("expertise.py", "rule_compiler.py", "citations.py"):
        source = (root / name).read_text()
        # Docstrings are prose ABOUT the absence of a model; only code lines can be a call site.
        code = "\n".join(line.split("#", 1)[0] for line in source.splitlines())
        hits += sum(code.lower().count(needle) for needle in needles)
    return hits


def score(samples: Sequence[WeldSample], *, at: datetime, lane: str) -> WeldVerdict:
    """The J1 table. PURE — no database, no clock, no float."""
    consumed: set[str] = set()
    legacy = 0
    blocking = 0
    heuristic_citations = 0
    unknown = 0
    coerced = 0
    checked = 0
    verbatim = 0
    fit_wins = 0
    alphabetical_wins = 0
    refusals: dict[str, int] = {}
    reproducible: bool | None = None

    for sample in samples:
        by_class = sample.by_class
        for klass in ARTIFACT_CLASSES:
            counters = by_class.get(klass) or {}
            if any(counters.get(key) for key in CONSUMER_EVIDENCE[klass]):
                consumed.add(klass)
            legacy += int(counters.get(LEGACY_UNSUPPORTED) or 0)
        for entry in sample.receipt.get("refusals") or ():
            reason = str(entry.get("reason"))
            refusals[reason] = refusals.get(reason, 0) + int(entry.get("count") or 0)
            if reason == LEGACY_UNSUPPORTED:
                legacy += int(entry.get("count") or 0)
        blocking += sum(len(rules) for rules in sample.eliminations.values())
        if any(item.get("artifact_class") == "heuristic" for item in sample.citations):
            heuristic_citations += 1
        for verdict in sample.rule_verdicts:
            if verdict.get("outcome") != "unevaluable":
                continue
            unknown += 1
            # An unevaluable rule that named a blocked play, or that carries no missing predicate,
            # is a rule that was coerced — the first blocked on an unknown, the second cannot say
            # what it did not know, and both are the failure step 4 exists to prevent.
            if verdict.get("blocked_play_ids") or not verdict.get("missing"):
                coerced += 1
        for citation in tuple(sample.citations) + tuple(sample.framing_blocks):
            statement = citation.get("statement")
            if statement is None:
                continue
            checked += 1
            verbatim += int(_statement_hash(statement) == citation.get("statement_hash"))
        fit, alpha = _play_cap_scores(sample)
        fit_wins += fit
        alphabetical_wins += alpha
        if sample.reproducible is not None:
            reproducible = (sample.reproducible if reproducible is None
                            else reproducible and sample.reproducible)

    return WeldVerdict(
        at=at, lane=lane, samples=len(samples),
        classes_with_consumer=tuple(sorted(consumed)),
        legacy_unsupported_receipts=legacy,
        blocking_eliminations=blocking,
        decisions_with_a_heuristic_citation=heuristic_citations,
        unknown_rules=unknown, unknown_rules_that_fired_or_blocked=coerced,
        citations_checked=checked, citations_verbatim=verbatim,
        play_cap_situation_fit_wins=fit_wins,
        play_cap_alphabetical_wins=alphabetical_wins,
        llm_call_sites=llm_call_sites(),
        reproducible=reproducible,
        refusals=dict(sorted(refusals.items())),
    )


def _statement_hash(statement: str) -> str:
    from genios_engine.contracts.domain_expertise import citation_statement_hash
    return citation_statement_hash(statement)


def _play_cap_scores(sample: WeldSample) -> tuple[int, int]:
    """(fit plays that survived a cut, non-fit plays that survived while a fit play was cut).

    The second number is the CLG-07 defect made countable. It reads the play receipt the adapter
    already writes, so the gate and the ranking cannot disagree about which plays were cut.
    """
    receipt = sample.receipt.get("play_receipt") or {}
    truncated = tuple(receipt.get("plays_truncated") or ())
    if not truncated:
        return 0, 0
    fit = int(receipt.get("plays_situation_fit") or 0)
    selected = int(receipt.get("plays_selected") or receipt.get("plays_emitted") or 0)
    # Every fit play survived when the fit count is at or below the number selected AND no fit
    # play appears in the cut list. The receipt does not label the cut plays, so the check is the
    # arithmetic one: a fit play was cut exactly when more plays are fit than survived.
    return (min(fit, selected), max(0, fit - selected))


# =================================================================================================
# LANE 1 — the shipped corpus, in memory
# =================================================================================================

def fixture_samples(at: datetime) -> list[WeldSample]:
    """Compile and weld each fixture TWICE, and report whether the two agree byte for byte."""
    from dataclasses import replace as _replace

    from genios_engine.context.quality.inference import ABSENT_FIELDS_KEY
    from genios_engine.context.situation_bso import (build_business_situation,
                                                     build_context_slice,
                                                     gather_evidence_and_signals,
                                                     stored_importance)
    from genios_engine.packs.compiler import DomainCompiler, InMemoryRuntimeBrains
    from genios_engine.packs.compiler.authoring import (ExpertBrainCatalog,
                                                        default_authoring_root)
    from genios_engine.packs.compiler.errors import NoExpertiseRoute
    from genios_engine.reason.adapters.expertise import expertise_capability_manifest

    catalog = ExpertBrainCatalog(default_authoring_root())
    samples: list[WeldSample] = []
    for fixture in FIXTURES:
        row = {
            "situation_id": f"sit_{fixture['name']}", "situation_type": fixture["type"],
            "domain": fixture["domain"], "status": "active", "correlation_id": None,
            "confidence_overall": 82, "coverage": 70, "first_seen_at": at, "last_seen_at": at,
            "anchor_node_id": "node_1", "anchor_name": "Fixture", "anchor_type": "company",
        }
        signal_ids, evidence = gather_evidence_and_signals(None, "org_fixture", None,
                                                           row["situation_id"])
        situation = build_business_situation(
            org_id="org_fixture", situation=row, signal_ids=signal_ids, evidence=evidence,
            trace_id="trace_fixture",
            # BLG-18 steps 2..6, read back off the row rather than recomputed — the discipline
            # `test_situation_importance` ratchets on every builder call site in the tree. A
            # fixture row carries no stored composition, so this is `None` and the situation
            # publishes on Layer 1's base, which is the documented pre-composition path.
            composed=stored_importance(row))
        context = build_context_slice(
            org_id="org_fixture", situation=row,
            facts={path: {"value": value} for path, value in fixture["facts"].items()},
            observations=[{"kind": kind} for kind in fixture["observations"]],
            neighbor=(fixture["edges"], set(), {}), graph_version=1, eval_time=at,
            trace_id="trace_fixture")
        if fixture["absent"]:
            context = _replace(context, metadata={**context.metadata,
                                                  ABSENT_FIELDS_KEY: list(fixture["absent"])})
        compiler = DomainCompiler(catalog=catalog, runtime_brains=InMemoryRuntimeBrains(),
                                  publisher=None, require_admission=False)
        try:
            package = compiler.compile(situation, context)
        except NoExpertiseRoute:
            continue
        manifests = [expertise_capability_manifest(
            package, root_entity_type="company", situation=situation, context=context)
            for _ in range(2)]
        weld = dict(manifests[0].metadata["weld"])
        receipt = dict(weld["weld_receipt"])
        receipt["play_receipt"] = dict(manifests[0].metadata["play_receipt"])
        samples.append(WeldSample(
            source=f"fixture:{fixture['name']}",
            capability_id=manifests[0].capability_id,
            receipt=receipt,
            citations=tuple(dict(item) for item in weld["citations"]),
            constraints=tuple(dict(item) for item in weld["compiled_constraints"]),
            framing_blocks=tuple(dict(item) for item in weld["framing_blocks"]),
            rule_verdicts=tuple(dict(item) for item in weld["rule_verdicts"]),
            eliminations=_eliminations(weld),
            reproducible=semantic_hash(manifests[0].to_semantic_dict())
            == semantic_hash(manifests[1].to_semantic_dict()),
        ))
    return samples


def _eliminations(weld: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    out: dict[str, list[str]] = {}
    for verdict in weld.get("rule_verdicts") or ():
        if verdict.get("outcome") != "fired" or verdict.get("severity") != "blocking":
            continue
        for play_id in verdict.get("blocked_play_ids") or ():
            out.setdefault(str(play_id), []).append(str(verdict["rule_id"]))
    return {play_id: tuple(sorted(rules)) for play_id, rules in sorted(out.items())}


# =================================================================================================
# LANE 2 — what production welded
# =================================================================================================

_MANIFESTS = (
    "select capability_id, capability_version, manifest "
    "from reasoning_capability_snapshots "
    "where org_id = :org and capability_id like 'expertise.%' "
    "order by created_at desc limit :lim"
)


def stored_samples(engine, org_id: str, limit: int) -> list[WeldSample]:
    """Every compiled capability this tenant has welded, newest first. READS ONLY."""
    samples: list[WeldSample] = []
    with read_only_connection(engine) as conn:
        rows = conn.execute(sql(_MANIFESTS), {"org": org_id, "lim": limit}).mappings().all()
    for row in rows:
        manifest = row["manifest"]
        if isinstance(manifest, str):
            manifest = json.loads(manifest)
        metadata = (manifest or {}).get("metadata") or {}
        weld = metadata.get("weld")
        if not isinstance(weld, dict):
            # A manifest written before the typed consumers existed. Counted by its absence from
            # the sample set rather than scored as a pass — this is exactly the "compiled fine,
            # consumed nothing" state the gate is looking for.
            continue
        receipt = dict(weld.get("weld_receipt") or {})
        receipt["play_receipt"] = dict(metadata.get("play_receipt") or {})
        samples.append(WeldSample(
            source=f"{row['capability_id']}@{row['capability_version']}",
            capability_id=str(row["capability_id"]),
            receipt=receipt,
            citations=tuple(weld.get("citations") or ()),
            constraints=tuple(weld.get("compiled_constraints") or ()),
            framing_blocks=tuple(weld.get("framing_blocks") or ()),
            rule_verdicts=tuple(weld.get("rule_verdicts") or ()),
            eliminations=_eliminations(weld),
        ))
    return samples


def parse_instant(value: str) -> datetime:
    """`--at`, as an aware UTC instant. There is no default: see this module's NO CLOCK note."""
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"--at must be an ISO-8601 instant with an offset (e.g. 2026-08-08T12:00:00Z); "
            f"got {value!r}") from None
    if parsed.tzinfo is None:
        raise argparse.ArgumentTypeError("--at must carry a timezone offset")
    return parsed.astimezone(timezone.utc)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="J1 · Layer 3 weld report")
    parser.add_argument("--fixtures", action="store_true",
                        help="weld the shipped corpus in memory; no database is opened")
    parser.add_argument("--org", default=None, help="tenant whose stored manifests to score")
    parser.add_argument("--at", required=True, type=parse_instant,
                        help="the evaluation instant every predicate binds against")
    parser.add_argument("--limit", type=int, default=500,
                        help="how many stored manifests to read (--org lane)")
    add_database_argument(parser)
    args = parser.parse_args(argv)

    if bool(args.fixtures) == bool(args.org):
        parser.error("pass exactly one of --fixtures or --org")

    if args.fixtures:
        samples = fixture_samples(args.at)
        lane = "fixtures"
    else:
        from genios_engine.platform.db import get_engine
        url = resolve_database_url(args, purpose="J1 weld report (read-only)")
        engine = get_engine(url)
        try:
            samples = stored_samples(engine, args.org, args.limit)
        finally:
            engine.dispose()
        lane = f"org:{args.org}"

    verdict = score(samples, at=args.at, lane=lane)
    print(json.dumps(verdict.as_dict(), indent=2, sort_keys=True))
    for sample in samples:
        print(f"  {sample.source}: constraints={len(sample.constraints)} "
              f"citations={len(sample.citations)} framing={len(sample.framing_blocks)} "
              f"eliminations={sum(len(v) for v in sample.eliminations.values())}")
    return 0 if verdict.passed else 1


if __name__ == "__main__":                                        # pragma: no cover
    raise SystemExit(main())
