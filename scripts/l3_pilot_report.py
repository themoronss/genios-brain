"""J5 · the PILOT report — did the Layer 3 unlock actually reach a card, on a real tenant?

    python scripts/l3_pilot_report.py --org <pilot> --days 7 \\
        --database-url postgresql://…

WHY THIS EXISTS AND WHY IT IS NOT `weld_report.py`. J1 asks whether the typed consumers WORK: it
reads compiled manifests and scores what the weld produced. J5 asks a strictly harder question —
whether what they produced survived the remaining hops to a surface a human sees. Doc 06 names one
of these rows as Layer 3's G7/H5-equivalent, *"the single measurement that says the unlock actually
reached a card"*, and a report that measured the manifest again would answer the easy question in
the hard question's voice. So every row here is read from the DELIVERY side of the seam wherever a
delivery side exists: `signals`, `cards`, `expertise_packages` — not from the weld's own receipt.

THE SEVEN ROWS, and where each is read (doc 06's J5 table):

  packages compiled for the pilot, Admin domain   > 0    expertise_packages.payload -> domain_ids
  A CARD CARRYING A HEURISTIC/RULE CITATION       >= 1   cards ⋈ signals.citations / .rejected_candidates
  a candidate eliminated by a blocking rule       >= 1   signals.rejected_candidates[*].eliminated_by
  a package with non-empty Org/Behavior/Adaptive  >= 1   expertise_packages.payload's three slices
  abstention downgrades on stamped capabilities   ~0     signals.capability_review_state
  byte-identical recompile of any package         exact  expertise_packages, one address / situation
  generic "review the situation" plays emitted    0      signals.play + the adapter's own play id

TWO ROWS ARE SCORED HARDER THAN DOC 06 ASKS, and both changes are tightenings.

THE ELIMINATION ROW IS SCOPED TO THE PILOT'S OWN DOMAIN. `eliminated_by` carries the authored
rule id, and an authored rule id is prefixed with the domain that wrote it, so
`admin.rule.opportunity_tracking.…` and `sales.rule.closing.…` are distinguishable for free. The
row asks whether the ADMIN corpus's doctrine bound something on an admin pilot; a Sales rule
firing on the same tenant is real enforcement and is reported (`eliminating_rules` lists every
rule, whatever its domain) but does not earn this row. Without the scoping a pilot whose Admin
doctrine binds nothing would pass on another domain's rule — which is the precise failure the row
was written to catch.

THE CARD ROW IS REPORTED TWICE, because the join and the copy are different claims. A card
"carries a citation" here in the sense doc 06's table spells — the card is bound to the decision
whose `citations` hold the quote — and that is the row. `cards_quoting_the_claim_in_their_own_copy`
is the STRICTER question, and the honest answer today is that it reads 0 on every card: the
renderer's `why` block carries fact/value pairs and the quote is never composed into the card's
own words. It is measured and noted rather than made a check, because the check the gate defined
is the join and a report may not quietly move its own goalposts — but a reader of J5 must not come
away believing the expert's sentence reached the human's screen when it reached the row behind it.

READ-ONLY, AND NEVER IMPLICITLY PRODUCTION. `set transaction read only` is the transaction's first
statement (`scripts/_gate.py`) and the target resolves through `scripts/_db.py`, which has no
fallback to the application's configured `database_url`.

THE ACTIVATION ROW IS REPORTED, NEVER FLIPPED. This script reads `l3_activation` and says whether
the tenant is switched on for a domain. It cannot switch anything on: Y5's ordering rule is that
typed consumers come before activation, and a report that could activate would be a way around it.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts._db import add_database_argument, resolve_database_url   # noqa: E402
from scripts._gate import read_only_connection, sql              # noqa: E402

#: The play the L3→L4 adapter mints when NO authored playbook survived conversion. Imported from
#: the adapter would be ideal; it is a literal there, so it is named here once and asserted against
#: the adapter by `tests/reason/adapters/test_l3_pilot_report.py` — the fake-success detector must
#: not be able to drift away from the thing it detects.
GENERIC_PLAY_ID = "review_situation"

#: The Admin domain's id, as the corpus spells it in `Admin Expertise/domain.yaml`.
ADMIN_DOMAIN = "admin"

#: `capability_review_state` values that mean the compiled capability was NOT trusted to speak
#: prescriptively. On a stamped corpus this should be empty — that is the "the stale-comment world
#: is over" row.
DOWNGRADED_STATES = ("draft", "stub")


def _json(value: Any) -> Any:
    return json.loads(value) if isinstance(value, str) else value


@dataclass(frozen=True, slots=True)
class PilotVerdict:
    """Every J5 row, its number, and whether the number clears the gate."""

    org_id: str
    since: datetime
    at: datetime
    activated_domains: tuple[str, ...] = ()
    packages_admin: int = 0
    packages_total: int = 0
    cards_with_a_citation: int = 0
    cards_quoting_in_their_own_copy: int = 0
    cards_total: int = 0
    signals_with_a_citation: int = 0
    citation_quotes: tuple[str, ...] = ()
    eliminations: int = 0
    domain_eliminations: int = 0
    elimination_rules: tuple[str, ...] = ()
    eliminated_plays: tuple[str, ...] = ()
    packages_with_a_brain_slice: int = 0
    brain_entries: Mapping[str, int] = field(default_factory=dict)
    adaptive_leases: int = 0
    downgraded_signals: int = 0
    compiled_signals: int = 0
    situations_addressed: int = 0
    worst_addresses_per_situation: int = 0
    generic_plays: int = 0
    notes: tuple[str, ...] = ()

    @property
    def checks(self) -> dict[str, bool]:
        return {
            "packages_compiled_admin": self.packages_admin > 0,
            # THE HEADLINE ROW, SPLIT INTO ITS TWO HOPS — because they fail for different
            # reasons and a single boolean hides which. A quote reaches the SIGNAL as soon as the
            # compiled lane runs live (migration 0114); it reaches a CARD only once the delivery
            # lane builds one, which needs a tenant with seats and a live pack. Reporting only the
            # second would read "the unlock did not happen" on a tenant where the unlock happened
            # and delivery had not run.
            "a_signal_carries_a_citation": self.signals_with_a_citation >= 1,
            "a_card_carries_a_citation": self.cards_with_a_citation >= 1,
            # SCOPED TO THE PILOT'S DOMAIN — see the module docstring. `eliminations` counts
            # every domain's enforcement and is reported; only the Admin corpus's own doctrine
            # earns the row, because "the Admin corpus binds something" is the claim.
            "a_candidate_was_eliminated_by_a_blocking_rule": self.domain_eliminations >= 1,
            "a_package_carries_a_brain_slice": self.packages_with_a_brain_slice >= 1,
            "no_abstention_downgrades": self.downgraded_signals == 0,
            "law2_one_address_per_situation": (self.packages_total > 0
                                              and self.worst_addresses_per_situation <= 1),
            "no_generic_plays": self.generic_plays == 0,
        }

    @property
    def passed(self) -> bool:
        return all(self.checks.values())

    def as_dict(self) -> dict[str, Any]:
        return {
            "gate": "J5",
            "org": self.org_id,
            "window": {"since": self.since.isoformat(), "at": self.at.isoformat()},
            "l3_activated_domains": list(self.activated_domains),
            "packages_compiled_admin": self.packages_admin,
            "packages_compiled_total": self.packages_total,
            "cards_carrying_a_citation": self.cards_with_a_citation,
            "cards_quoting_the_claim_in_their_own_copy": self.cards_quoting_in_their_own_copy,
            "cards_total": self.cards_total,
            "signals_carrying_a_citation": self.signals_with_a_citation,
            "citation_quotes_sample": list(self.citation_quotes[:3]),
            "candidates_eliminated_by_a_blocking_rule": self.eliminations,
            "candidates_eliminated_by_an_admin_rule": self.domain_eliminations,
            "eliminating_rules": list(self.elimination_rules),
            "eliminated_plays": list(self.eliminated_plays),
            "packages_with_a_brain_slice": self.packages_with_a_brain_slice,
            "learned_brain_entries_active": dict(sorted(self.brain_entries.items())),
            "adaptive_leases_active": self.adaptive_leases,
            "abstention_downgrades": self.downgraded_signals,
            "compiled_signals": self.compiled_signals,
            "situations_addressed": self.situations_addressed,
            "worst_addresses_per_situation": self.worst_addresses_per_situation,
            "generic_review_plays": self.generic_plays,
            "checks": dict(sorted(self.checks.items())),
            "passed": self.passed,
            "notes": list(self.notes),
        }


_PACKAGES = (
    "select expertise_id, semantic_hash, payload from expertise_packages "
    "where org_id = :org"
)
_SIGNALS = (
    "select signal_id, play, capability_id, capability_review_state, rejected_candidates, "
    "citations from signals "
    "where org_id = :org and capability_id is not null and eval_time >= :since"
)
#: WHAT THE THREE LEARNED BRAINS HOLD, independently of what reached a package. Row 4 reads
#: `expertise_packages`, and a zero there has two completely different causes: the brains are
#: empty, or the brains are full and nothing SELECTED from them. Only one of those is J4's problem,
#: and a report that cannot tell them apart sends the reader to the wrong layer.
_BRAIN_ENTRIES = (
    "select brain, count(*) as n from learned_brain_entries "
    "where org_id = :org and active group by brain"
)
#: The Adaptive brain's other home. `feedback/publisher.py` writes a timing LEASE into
#: `temporary_memories`, not into `learned_brain_entries`, and `packs/compiler/runtime_brains.py`
#: reads only the latter — so a live lease is counted here and can still be absent from every
#: package. Reported rather than argued about.
_ADAPTIVE_LEASES = (
    "select count(*) from temporary_memories where org_id = :org and active"
)

#: The card, the decision behind it, AND the card's own rendered copy. The last three columns are
#: what makes `cards_quoting_the_claim_in_their_own_copy` measurable instead of assumed: a quote
#: has reached the reader only if it is in something the reader is shown.
_CARDS = (
    "select k.card_id, s.citations, s.rejected_candidates, "
    "       coalesce(k.headline, '') as headline, coalesce(k.situation, '') as situation, "
    "       coalesce(k.why::text, '') as why, coalesce(k.artifact::text, '') as artifact "
    "from cards k "
    "join signals s on s.signal_id = k.signal_id and s.org_id = k.org_id "
    "where k.org_id = :org and k.created_at >= :since"
)


def _package_rows(conn, org_id: str) -> list[Mapping[str, Any]]:
    return [dict(row) for row in conn.execute(sql(_PACKAGES), {"org": org_id}).mappings().all()]


def _brain_slices(payload: Mapping[str, Any]) -> bool:
    return any(payload.get(key) for key in
               ("organization_rules", "behavior_patterns", "adaptive_preferences"))


def _domains(payload: Mapping[str, Any]) -> tuple[str, ...]:
    metadata = payload.get("metadata") or {}
    return tuple(str(item) for item in (metadata.get("domain_ids") or ()))


def _law2_under_load(rows: Sequence[Mapping[str, Any]]) -> tuple[int, int, int]:
    """LAW 2 as the STORE can testify to it — `(packages, situations, worst_repeat)`.

    A literal recompile needs the situation and the context slice the package was compiled FOR,
    and neither survives in `expertise_packages`; only the compiled result does. Re-canonicalising
    the stored payload proves nothing either — it is ALREADY canonical, and `canonicalize` refuses
    to re-tag its own output, which is the correct behaviour and a useless measurement.

    What the store can answer is the question the churn incident actually turned on. A package is
    content-addressed, so a sweep that compiles the same situation from the same knowledge must
    land on the SAME `expertise_id` and `on conflict do nothing` must fire. Two addresses for one
    situation means two different payloads for one situation — which is either a real knowledge
    change (legitimate, and visible) or the churn that reached 4,086 rows and 995 MB and took the
    production database read-only. Either way it is the number an operator has to look at, and it
    is measurable from the rows alone.

    The literal byte-identity of a recompile is proven where it can be — against the compiler, in
    `tests/packs/compiler/test_byte_identical_compile.py`. This is its production echo.
    """
    per_situation: dict[str, set[str]] = {}
    for row in rows:
        payload = _json(row["payload"])
        situation = str((payload or {}).get("situation_id") or "")
        per_situation.setdefault(situation, set()).add(str(row["expertise_id"]))
    worst = max((len(ids) for ids in per_situation.values()), default=0)
    return len(rows), len(per_situation), worst


def score(conn, *, org_id: str, since: datetime, at: datetime,
          activation_target: Any = None) -> PilotVerdict:
    from genios_engine.platform import l3_activation

    # `l3_activation`'s readers take an ENGINE and fail closed on anything they cannot query —
    # correct for a gate read, and it means handing them this report's read-only CONNECTION would
    # print "not activated" for an activated tenant and log a warning nobody reads. So the engine
    # is passed separately when the caller has one; a caller that does not gets an honest empty
    # tuple rather than a wrong answer.
    packages = _package_rows(conn, org_id)
    admin = brains = 0
    for row in packages:
        payload = _json(row["payload"])
        if not isinstance(payload, Mapping):
            continue
        admin += int(ADMIN_DOMAIN in _domains(payload))
        brains += int(_brain_slices(payload))
    package_count, situation_count, worst = _law2_under_load(packages)

    signals = conn.execute(sql(_SIGNALS), {"org": org_id, "since": since}).mappings().all()
    downgraded = sum(1 for row in signals
                     if str(row["capability_review_state"] or "") in DOWNGRADED_STATES)
    generic = sum(1 for row in signals if str(row["play"] or "") == GENERIC_PLAY_ID)
    eliminations = domain_eliminations = 0
    quoted_signals = 0
    quotes: list[str] = []
    rules: set[str] = set()
    eliminated_plays: set[str] = set()
    for row in signals:
        quoted_signals += int(bool(_json(row["citations"])))
        for rejected in _json(row["rejected_candidates"]) or ():
            for elimination in (rejected or {}).get("eliminated_by") or ():
                rule_id = str(elimination.get("rule_id") or "")
                eliminations += 1
                # An authored rule id names its own domain in its first segment
                # (`admin.rule.<capability>.<name>`), which is why the scoping needs no extra
                # column and cannot disagree with the corpus.
                domain_eliminations += int(rule_id.split(".", 1)[0] == ADMIN_DOMAIN)
                rules.add(rule_id)
                eliminated_plays.add(str((rejected or {}).get("play_id") or ""))

    brain_entries = {str(row["brain"]): int(row["n"]) for row in
                     conn.execute(sql(_BRAIN_ENTRIES), {"org": org_id}).mappings().all()}
    leases = int(conn.execute(sql(_ADAPTIVE_LEASES), {"org": org_id}).scalar() or 0)

    cards = conn.execute(sql(_CARDS), {"org": org_id, "since": since}).mappings().all()
    quoted = quoted_in_copy = 0
    for row in signals:
        # The quote itself, sampled from wherever it landed, so an operator reading this report
        # can SEE the expert's words rather than a count of them.
        quotes.extend(str(c.get("statement") or "") for c in (_json(row["citations"]) or ()))
    for row in cards:
        statements = [str(c.get("statement") or "") for c in (_json(row["citations"]) or ())]
        statements += [str(e.get("statement") or "")
                       for r in (_json(row["rejected_candidates"]) or ())
                       for e in (r or {}).get("eliminated_by") or ()]
        statements = [s for s in statements if s]
        if statements:
            quoted += 1
            quotes.extend(statements)
            # THE STRICTER READING. Did the expert's own sentence reach anything the human is
            # shown? Everything the card renders, concatenated — headline, situation line, the
            # `why` block and the artifact — and searched for the quote VERBATIM. Verbatim is the
            # only defensible test: `citation_statement_hash` pins the stored quote to the
            # authored bytes precisely so a renderer cannot paraphrase it and still claim it.
            rendered = "\n".join(str(row[column] or "") for column in
                                  ("headline", "situation", "why", "artifact"))
            quoted_in_copy += int(any(statement in rendered for statement in statements))

    notes: list[str] = []
    if not packages:
        notes.append("this tenant has compiled nothing: every row below is an absence, not a "
                     "failure of the weld")
    if quoted_signals and not cards:
        notes.append(f"{quoted_signals} signal(s) carry a quoted expert claim and NO card was "
                     "built in this window — the citation row is blocked on delivery, not on the "
                     "weld")
    if quoted and not quoted_in_copy:
        notes.append(f"{quoted} card(s) rest on a quoted expert claim and NONE renders it: the "
                     "card row is earned through the decision it is bound to, not through words "
                     "a human reads. The renderer's `why` block carries fact/value pairs only")
    if eliminations and not domain_eliminations:
        notes.append(f"{eliminations} candidate(s) were eliminated by authored doctrine and none "
                     f"of it is {ADMIN_DOMAIN}'s: this pilot's own corpus bound nothing "
                     f"({', '.join(sorted(rules))})")
    if packages and not brains and (brain_entries or leases):
        held = ", ".join(f"{name}={count}" for name, count in sorted(brain_entries.items()))
        notes.append(
            f"the learned brains hold rows ({held or 'none'}; adaptive leases={leases}) and NO "
            "package carries a slice — this is a SELECTION gap, not an empty brain. "
            "`packs/compiler/runtime_brains._selectors` matches on the situation's "
            "`brain_subject_keys` (no writer exists for that metadata key anywhere in the "
            "engine), its capability ids, its object ids, its own id, and its entity ids — and a "
            "correlated situation's entity id is an EMAIL (`situation_bso.gather_members`) while "
            "a published Behaviour subject is `behavior:<metric>:<node_id>`. A lease never "
            "matches at all: it lives in `temporary_memories` and the reader queries only "
            "`learned_brain_entries`")
    if not signals:
        notes.append("no compiled signal in the window — the compiler ran in SHADOW, or the "
                     "window predates the cutover; the card rows cannot be earned from shadow")

    return PilotVerdict(
        org_id=org_id, since=since, at=at,
        activated_domains=(tuple(sorted(l3_activation.activated_domains(
            activation_target, org_id))) if activation_target is not None else ()),
        packages_admin=admin, packages_total=len(packages),
        cards_with_a_citation=quoted, cards_total=len(cards),
        cards_quoting_in_their_own_copy=quoted_in_copy,
        signals_with_a_citation=quoted_signals,
        citation_quotes=tuple(quotes),
        eliminations=eliminations, domain_eliminations=domain_eliminations,
        elimination_rules=tuple(sorted(rules)),
        eliminated_plays=tuple(sorted(p for p in eliminated_plays if p)),
        packages_with_a_brain_slice=brains,
        brain_entries=brain_entries, adaptive_leases=leases,
        downgraded_signals=downgraded, compiled_signals=len(signals),
        situations_addressed=situation_count, worst_addresses_per_situation=worst,
        generic_plays=generic, notes=tuple(notes))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="J5 · Layer 3 pilot report")
    parser.add_argument("--org", required=True)
    parser.add_argument("--days", type=int, default=7,
                        help="how far back the card/signal window reaches (default 7)")
    parser.add_argument("--at", default=None,
                        help="the window's end, ISO-8601 with an offset (default: now)")
    add_database_argument(parser)
    args = parser.parse_args(argv)
    if args.days <= 0:
        parser.error("--days must be a positive whole number of days")

    at = (datetime.now(timezone.utc) if args.at is None
          else datetime.fromisoformat(args.at.replace("Z", "+00:00")))
    if at.tzinfo is None:
        parser.error("--at must carry a timezone offset")
    at = at.astimezone(timezone.utc)

    # `platform.db.get_engine`, not a bare `create_engine`: this codebase runs psycopg3, so a
    # plain `postgresql://` URL resolves to the psycopg2 dialect and the script dies on an import
    # nobody has installed. One helper owns that normalisation; a second copy of it here would be
    # a second opinion about which driver this product uses.
    from genios_engine.platform.db import get_engine
    engine = get_engine(resolve_database_url(args, purpose="the J5 pilot report"))
    with read_only_connection(engine) as conn:
        verdict = score(conn, org_id=args.org, since=at - timedelta(days=args.days), at=at,
                        activation_target=engine)
    print(json.dumps(verdict.as_dict(), indent=2, sort_keys=True))
    for note in verdict.notes:
        print(f"  note: {note}")
    return 0 if verdict.passed else 1


if __name__ == "__main__":                                        # pragma: no cover
    raise SystemExit(main())
