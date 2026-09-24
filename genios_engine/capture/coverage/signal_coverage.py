"""L1.x-U1 · COVERAGE ON THE SIGNAL — so a negative claim carries its own proof.

> **"No follow-up email found" means nothing until you know whether the search covered 100% of the
> mail or 8% of it.**

Gemini's worst benchmark failure was exactly this: it reported the size of its context as the size
of the mailbox — *"18 threads read of 18 that exist"* against ~465. Claude's strongest behaviour was
publishing a coverage table **before** any finding.

`coverage/declaration.py` already makes the argument one level up, for CHANNELS:

> *"It is the difference between 'this customer has no support tickets' and 'we have no source that
> could carry a support ticket.' The first is a finding; the second is a blind spot wearing a
> finding's clothes."*

`coverage_ready` on the signal answers *"could a source have carried this?"* — a real question and a
narrower one than *"how much of what that source holds did we actually read?"* This module answers
the second.

⛔ **THE ALIGNMENT THAT MAKES IT WORTH BUILDING NOW:**

    step 5   built the denominator on the sweep — claimed_total, cursor_exhausted
    step 12  built the rule that BROKEN requires coverage >= 9000 bp ... with NOTHING wired in
    step 15  carries the figure onto the signal, frozen at capture

`CommitmentFacts.coverage_bp` has been an input a caller had to supply from somewhere. This is that
somewhere.

⛔ **E4 IS THE SUBTLE RULE AND §9 FORBIDS GETTING IT WRONG.** Coverage is a property of the
**observation moment**, not of the tenant. A signal that said *"no follow-up found, 8% of the window
indexed"* must keep saying 8% after a backfill takes the tenant to 100% — the claim was made with 8%
of the evidence and its strength has not changed; only our ability to make a NEW and better claim
has. So this is a frozen VALUE and never a pointer: no org id, no query, no run id, nothing that
would resolve against today's numbers when read tomorrow.

**PER SOURCE, NEVER BLENDED** (E5). A tenant with complete calendar coverage and 8% email coverage
has two different licences to make a negative claim, and one blended number would grant the stronger
one to both. *"No meeting was booked"* and *"no follow-up was sent"* rest on different evidence.

**AND NEVER 100% BY DEFAULT** (§9). An unknown denominator is `None`, which is neither zero nor
everything. Defaulting it full would write Gemini's failure into our own contract.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

#: Full scale. Integer basis points throughout (E6, V-7).
BP_FULL = 10_000


@dataclass(frozen=True, slots=True)
class SourceCoverage:
    """How much of ONE source we had read, as of the moment this signal was captured.

    Frozen, and that is E4's mechanism rather than a style choice: a mutable block could be
    rewritten by a later backfill, and yesterday's claim would silently restate itself tonight.
    """

    source: str
    #: How many objects we actually landed in the window.
    indexed: int
    #: How many the provider says exist. **`None` means the provider gave us no count** — not zero,
    #: and not everything.
    claimed_total: int | None
    #: E1 · Gmail's total is `resultSizeEstimate` and Google named it that. An estimate stored
    #: without its label becomes a fact at the first reader, and "465 of 465" then reads as a count
    #: somebody could be held to.
    is_estimate: bool
    #: Step 5's other half: did we reach the end, or stop? A sweep that exhausted its cursor read
    #: everything offered; one that did not has a tail it never saw.
    cursor_exhausted: bool

    @property
    def completeness_bp(self) -> int | None:
        """Share of the window we read, in integer basis points — or `None` when unknowable.

        **`None` RATHER THAN 10000 IS THE WHOLE POINT** (§9). No denominator means no ratio, and a
        confident 100% here is the exact failure this step exists to prevent.

        CAPPED AT FULL, because `indexed > claimed_total` is LEGAL: Gmail's estimate runs low, so a
        perfectly correct sweep can fetch more than the provider predicted. Reporting 11000 bp would
        be arithmetic nobody can defend; refusing it would raise on a healthy mailbox.

        Integer division, so the share is truncated and never overstated.
        """
        if self.claimed_total is None or self.claimed_total <= 0:
            return None
        return min(self.indexed * BP_FULL // self.claimed_total, BP_FULL)

    @property
    def is_unknown(self) -> bool:
        """True when we cannot say what share we read. A caller must be able to tell this from a
        low share: *"we read 8%"* and *"we do not know what we read"* license different claims."""
        return self.completeness_bp is None

    def as_dict(self) -> dict[str, object]:
        """The jsonb shape. Every number an int — E6, and a float here reaches storage as a value
        nobody can trace back to two counts."""
        return {"source": self.source, "indexed": int(self.indexed),
                "claimed_total": None if self.claimed_total is None else int(self.claimed_total),
                "is_estimate": bool(self.is_estimate),
                "cursor_exhausted": bool(self.cursor_exhausted),
                "completeness_bp": self.completeness_bp}


@dataclass(frozen=True, slots=True)
class SignalCoverage:
    """The window a signal's claim rests on, and what we had read of each source inside it.

    **NO BLENDED NUMBER, deliberately** (E5, §9). There is no `completeness_bp` on this class and
    there must not be: it would grant the best-covered source's licence to every claim the signal
    supports.

    THE WINDOW IS NOT DECORATION. *"465 of 465"* over what? A completeness with no period is a ratio
    over an unstated set, and a reader cannot tell whether the claim covers the month that matters.
    """

    window_from: datetime
    window_to: datetime
    sources: tuple[SourceCoverage, ...] = ()

    @property
    def is_unknown(self) -> bool:
        """True when no source can state a share. A block with nothing in it is not full coverage
        of nothing — it is a block that learned nothing."""
        return not self.sources or all(s.is_unknown for s in self.sources)

    def for_source(self, source: str) -> SourceCoverage | None:
        """This signal's coverage of one source, or `None` when it has none for it."""
        return next((s for s in self.sources if s.source == source), None)

    def coverage_bp_for(self, source: str) -> int | None:
        """The figure step 12's `BROKEN` gate consumes, for one named source.

        **`None` for a source we know nothing about, never 0.** Zero would feed that gate a number
        meaning *"we read none of it"* when the truth is *"we do not know"* — and the gate treats
        both conservatively, so the distinction has to survive for the REPORT to be honest even
        though the decision would match.
        """
        found = self.for_source(source)
        return found.completeness_bp if found is not None else None

    def as_dict(self) -> dict[str, object]:
        """The jsonb shape carried on C-12."""
        return {"window_from": self.window_from, "window_to": self.window_to,
                "sources": [s.as_dict() for s in self.sources]}


def coverage_from_sweep(*, window_from: datetime, window_to: datetime,
                        sweeps: Sequence[object]) -> SignalCoverage:
    """15-U2 · build the block from step 5's completeness values, **as of capture**.

    Each sweep is a `SyncSummary` (or anything carrying the same four names). It is read ONCE, here,
    and the resulting value is frozen — which is E4: a later backfill produces a NEW sweep and a new
    signal, and cannot reach back into one already published.

    A sweep with no source name is skipped rather than filed under a placeholder: coverage
    attributed to `"unknown"` would be read as a real source by anything grouping on it.
    """
    covered: list[SourceCoverage] = []
    for sweep in sweeps:
        source = str(getattr(sweep, "source", "") or "").strip()
        if not source:
            continue
        claimed = getattr(sweep, "claimed_total", None)
        covered.append(SourceCoverage(
            source=source,
            indexed=int(getattr(sweep, "scanned", 0) or 0),
            claimed_total=int(claimed) if isinstance(claimed, int) else None,
            is_estimate=bool(getattr(sweep, "claimed_is_estimate", False)),
            cursor_exhausted=bool(getattr(sweep, "cursor_exhausted", False))))
    return SignalCoverage(window_from=window_from, window_to=window_to,
                          sources=tuple(covered))


__all__ = ["BP_FULL", "SignalCoverage", "SourceCoverage", "coverage_from_sweep"]
