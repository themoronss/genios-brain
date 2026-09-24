"""L2-0 · every way this layer declines, counted and named — with nothing silent.

    pytest tests/context/test_every_refusal_is_reported.py -q

⛔ **THE DEFECT, IN THE CODE'S OWN WORDS.** `situation_bso.l1_refusal`:

    THE REFUSAL IS CORRECT. The 71 events behind those cards scored 528-1920 basis points against
    a floor of 2500... THE SILENCE IS NOT. Such a card today simply exists, ranks, and quietly
    never becomes anything, while no surface says "its best evidence scored 1360 against a floor
    of 2500". That is the fifth time this codebase has carried a refusal that was right and
    invisible, and the other four were each found by accident.

Layer 1 wrote the rule for signals — **`DROP ≠ DELETE`** — and logs why, which rule, which
threshold, so that *"why didn't GeniOS tell me about this?"* has an answer. **Layer 2 has the
refusals and no ledger anybody reads.**

EVERY NUMBER THIS NEEDS ALREADY EXISTS. `l1_refusal()` returns `highest_bp` and `floor_bp`.
`situation_admission_decisions` stores `outcome`, `reasons` and the candidate's own bytes.
`domain_silence.DARK_DOMAINS` names the domains no corpus reads. **Nothing assembled them.**

PURE — no database, no clock, no contract import. The caller reads rows; this shapes them. That
separation is what makes `capture/validate/` the strongest package in Layer 1, and it is why this
module can be tested at all without a Postgres nobody has.

THE REASON TABLE IS BUILT FROM THE ENUM, NEVER FROM A SECOND LIST. An eighth `HoldReason` appears
here the day it is added, at zero, without anybody remembering to add it — because two hand-kept
lists of one fact drift, and this repository has caught that exact drift five times.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ScoredRefusal:
    """One situation Layer 1 assessed and declined, with the number it missed by."""

    situation_id: str
    highest_bp: int | None
    floor_bp: int | None

    @property
    def sentence(self) -> str:
        """⛔ The sentence `l1_refusal` says no surface speaks.

        `None` is NOT rendered as zero. *"Never assessed and assessed-then-refused are different
        facts, and only the second is a judgement Layer 1 made"* — so an unscored refusal says it
        was never scored rather than implying it scored nothing.
        """
        if self.highest_bp is None or self.floor_bp is None:
            return (f"{self.situation_id}: its evidence was never scored — "
                    f"no judgement was made, and none should be read into this")
        return (f"{self.situation_id}: its best evidence scored {self.highest_bp} "
                f"against a floor of {self.floor_bp}")


@dataclass(frozen=True, slots=True)
class DarkDomain:
    """A domain Layer 2 serves and no authored corpus can read."""

    domain: str
    situations: int
    reason: str


@dataclass(frozen=True, slots=True)
class CorpusDomain:
    """One authored domain's capabilities, and how many of them a compile may actually read.

    ⛔ **THE NUMBER THIS CARRIES WAS WRONG IN THE PLAN AND NOTHING COULD CONTRADICT IT.** Layer 2's
    plan budgeted *"334 of 534 capabilities go dark at `require_admission=True`"*. Measured
    2026-09-24: **155 capabilities, 155 admissible, 0 hollow** — the 534 counted FILES, three per
    capability, so the cutover is free rather than expensive.

    `hollow` is a subset of `admitted`, never a third bucket: **an inadmissible capability needs a
    reviewer and a hollow one needs an author**, and one number would send whoever reads it to the
    wrong person.
    """

    domain: str
    total: int
    admitted: int
    inadmissible: int
    hollow: int
    #: ⛔ THE SECOND CORPUS REFUSAL, AND IT COSTS SOMETHING DIFFERENT. An inadmissible capability
    #: is DROPPED — the answer loses its material. An unreviewed situation is FLAGGED:
    #: `review_state='draft'` -> `_apply_abstention` -> the card becomes an OBSERVATION.
    #: *"The intelligence still ships; it stops instructing."*
    situations: int = 0
    situations_unreviewed: int = 0


@dataclass(frozen=True, slots=True)
class RefusalReport:
    """What this layer declined, in one object.

    `held` counts SITUATIONS. `by_reason` counts REASONS. They are different numbers — a situation
    held for two reasons appears once in the first and twice in the second — and conflating them
    is how 63 held situations get reported as the 71 events behind them.
    """

    held: int = 0
    admitted: int = 0
    rejected: int = 0
    by_reason: dict[str, int] = field(default_factory=dict)
    scored_refusals: tuple[ScoredRefusal, ...] = ()
    dark_domains: tuple[DarkDomain, ...] = ()
    corpus: tuple[CorpusDomain, ...] = ()

    @property
    def silent_total(self) -> int:
        """SITUATIONS that produced nothing and said nothing about it.

        ⛔ Deliberately excludes the corpus. A capability is not a situation, and summing the two
        gives a number that means nothing — the same conflation this class already warns about
        between `held` and `by_reason`.
        """
        return self.held + self.rejected + sum(d.situations for d in self.dark_domains)

    @property
    def corpus_total(self) -> int:
        return sum(c.total for c in self.corpus)

    @property
    def corpus_unreadable(self) -> int:
        """Authored, in the corpus, and no compile may read it."""
        return sum(c.inadmissible for c in self.corpus)

    @property
    def situations_cannot_instruct(self) -> int:
        """Authored, detected, and downgraded to an observation because nobody approved the words."""
        return sum(c.situations_unreviewed for c in self.corpus)

    @property
    def corpus_hollow(self) -> int:
        """Admitted, hash-pinned, and saying nothing. A different repair from `unreadable`."""
        return sum(c.hollow for c in self.corpus)


def _reason_table() -> dict[str, int]:
    """Every `HoldReason` at zero. Built from the enum so an eighth cannot escape."""
    from genios_engine.context.situation_publisher import HoldReason

    return {reason.value: 0 for reason in HoldReason}


def refusal_report(*,
                   decisions: Iterable[Mapping[str, Any]],
                   refusals: Iterable[Mapping[str, Any]],
                   dark: Iterable[Mapping[str, Any]],
                   corpus: Iterable[Mapping[str, Any]] = ()) -> RefusalReport:
    """Shape three row sets into one report. No I/O, no clock.

    `decisions`  rows of `situation_admission_decisions` — `outcome` and `reasons`
    `refusals`   `l1_refusal()` answers — `highest_bp` and `floor_bp`
    `dark`       per-domain situation counts for domains `domain_silence` declares
    `corpus`     per-domain capability health — `packs.compiler.capability_resolver.corpus_health`

    Each arrives as plain mappings, never as the producing module's own type: that is what keeps
    this module importable, and testable, with no database and no corpus on disk.
    """
    from genios_engine.context.domain_silence import reason_for

    by_reason = _reason_table()
    held = admitted = rejected = 0

    for row in decisions:
        outcome = str(row.get("outcome") or "").strip().lower()
        if outcome == "hold":
            held += 1
        elif outcome == "admit":
            admitted += 1
        elif outcome == "reject":
            rejected += 1
        for reason in (row.get("reasons") or ()):
            # A reason arrives as `law:subject` from the admission laws, or bare from a hold.
            key = str(reason).split(":", 1)[0].strip()
            if key in by_reason:
                by_reason[key] += 1

    scored = tuple(
        ScoredRefusal(situation_id=str(r.get("situation_id") or ""),
                      highest_bp=r.get("highest_bp"), floor_bp=r.get("floor_bp"))
        for r in refusals)

    darks = tuple(
        DarkDomain(domain=str(d.get("domain") or ""),
                   situations=int(d.get("situations") or 0),
                   # THE REASON IS READ, NEVER PASSED IN. A caller that supplied its own could
                   # disagree with the declaration, and then two places would say why a domain is
                   # dark — which is the drift `domain_silence` exists to prevent.
                   reason=reason_for(d.get("domain")) or "")
        for d in dark)

    corpora = tuple(
        CorpusDomain(domain=str(c.get("domain") or ""), total=int(c.get("total") or 0),
                     admitted=int(c.get("admitted") or 0),
                     inadmissible=int(c.get("inadmissible") or 0),
                     hollow=int(c.get("hollow") or 0),
                     situations=int(c.get("situations") or 0),
                     situations_unreviewed=int(c.get("situations_unreviewed") or 0))
        for c in corpus)

    return RefusalReport(held=held, admitted=admitted, rejected=rejected,
                         by_reason=by_reason, scored_refusals=scored, dark_domains=darks,
                         corpus=corpora)


def render(report: RefusalReport) -> Sequence[str]:
    """The report as lines. Terminal-readable, because a dashboard nobody opens is the defect."""
    out = [
        "LAYER 2 · WHAT WAS REFUSED, AND WHY",
        "=" * 52,
        f"admitted  {report.admitted:>6}",
        f"held      {report.held:>6}",
        f"rejected  {report.rejected:>6}",
        "",
        "BY REASON" + (" " * 12) + "(zeros shown on purpose — a reason that",
        " " * 21 + " appears only when it fires is one nobody knows exists)",
        "-" * 52,
    ]
    out += [f"  {name:<34}{count:>6}" for name, count in sorted(report.by_reason.items())]

    if report.scored_refusals:
        out += ["", "REFUSED BY LAYER 1, WITH THE NUMBER IT MISSED BY", "-" * 52]
        out += [f"  {r.sentence}" for r in report.scored_refusals]

    if report.dark_domains:
        out += ["", "DOMAINS NO AUTHORED CORPUS CAN READ", "-" * 52]
        for d in report.dark_domains:
            out += [f"  {d.domain}: {d.situations} situations minted, none readable",
                    f"      {d.reason[:100]}…"]

    if report.corpus:
        # PRINTED EVEN WHEN CLEAN. A section that appears only on a problem is one nobody trusts
        # is running, and a blank report then looks exactly like a healthy one.
        out += ["", "THE AUTHORED CORPUS, AND WHAT A COMPILE MAY READ", "-" * 52,
                f"  {'domain':<20}{'caps':>6}{'unreadable':>12}{'hollow':>8}"
                f"{'situations':>12}{'draft':>7}"]
        out += [f"  {c.domain:<20}{c.total:>6}{c.inadmissible:>12}{c.hollow:>8}"
                f"{c.situations:>12}{c.situations_unreviewed:>7}" for c in report.corpus]
        out += [f"  {'ALL':<20}{report.corpus_total:>6}{report.corpus_unreadable:>12}"
                f"{report.corpus_hollow:>8}"
                f"{sum(c.situations for c in report.corpus):>12}"
                f"{report.situations_cannot_instruct:>7}"]
        if report.situations_cannot_instruct:
            # THE NUMBER IS USELESS WITHOUT ITS COST. "24 draft" tells nobody anything; "24 cards
            # that describe and cannot instruct" is a sentence somebody acts on.
            out += ["",
                    f"  ⛔ {report.situations_cannot_instruct} authored situations are still "
                    f"`draft`. Any card built from one is",
                    "     downgraded to an OBSERVATION — it describes, and it does not instruct.",
                    "     The repair is one word per file, by an author."]

    out += ["", f"TOTAL SITUATIONS PRODUCING NOTHING: {report.silent_total}"]
    return out


__all__ = ["CorpusDomain", "DarkDomain", "RefusalReport", "ScoredRefusal",
           "refusal_report", "render"]
