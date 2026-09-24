"""L1.6.6-U5 · DOMAIN COVERAGE AND DISTRIBUTION — and why coverage alone is the wrong number.

Metric 4 is *"events carrying a non-fallback domain"*. Reported on its own it is gameable by the
most natural mistake a domain tagger can make:

> **A tagger that returns all five domains for every message has 100% coverage and zero
> information.**

Coverage cannot see that. A distribution can. And it is not hypothetical — it is the same shape as
the failure `hints.py` already records, where the generic sales vocabulary claimed investor threads
and *"six VCs and three accelerator programmes became sales opportunities. Not one of its sixteen
sales situations was a customer."* Every one of those events had a domain. Coverage looked
excellent right up until somebody read a card.

So this module reports three things together and a reader is expected to look at all three:

    tagged                  events with at least one NON-FALLBACK domain        — the metric
    fallback_only           events where the only tag was the placeholder       — the honest gap
    mean_domains_per_event  how discriminating the tagger is                    — the guard

THE FALLBACK IS NOT COVERAGE. `FALLBACK_DOMAIN` exists so unmatched business mail is not invisible.
Counting it as a tagged event restates the problem as a solution, which is the single easiest way
to make this metric lie.

EVERYTHING IS INTEGER BASIS POINTS. V-7 — a float reaches storage as jsonb and comes back as a
number nobody can trace to a count. `mean_domains_per_event_bp` is a MEAN carried at 10000 = one
domain per event, so 2.5 domains per event is 25000 bp. It is a ratio of counts, not a probability,
and it is deliberately allowed above 10000.

PURE: no clock, no I/O, no model.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field

#: Above this mean, a tagger is tagging rather than distinguishing. 2.5 domains on EVERY event, in
#: a world with four shipped domains, means more than half the taxonomy fires every time — at which
#: point the tag carries almost no information and L3 has no basis to select a corpus.
#:
#: A THRESHOLD, NOT A LIMIT. Nothing is refused for crossing it; it sets `is_indiscriminate` so the
#: condition is visible in a report. Refusing tags here would be filtering, which §9 of this step
#: forbids in as many words.
INDISCRIMINATE_MEAN_BP = 25_000

#: One domain per event, as basis points. The unit `mean_domains_per_event_bp` is carried in.
ONE_DOMAIN_BP = 10_000


@dataclass(frozen=True, slots=True)
class DomainDistribution:
    """What a sweep's domain tagging looks like. Read all three numbers or none of them."""

    events: int = 0
    #: Events carrying at least one NON-FALLBACK domain. This is metric 4's numerator.
    tagged: int = 0
    #: Events whose ONLY tag was the fallback placeholder. Not a gap we are hiding — a gap we are
    #: counting.
    fallback_only: int = 0
    #: Events with no domain at all.
    untagged: int = 0
    #: domain -> how many events carried it. The shape that shows a taxonomy collapsing onto one
    #: name, which is what the six-VCs failure looked like from here.
    per_domain: dict[str, int] = field(default_factory=dict)
    #: Mean domains per event, at 10000 = one. See the module docstring for why it may exceed it.
    mean_domains_per_event_bp: int = 0

    @property
    def coverage_bp(self) -> int:
        """Metric 4, in basis points. Integer division, so it is truncated and never overstated.

        Zero events reports 0 — which is why a caller must read it beside `events`. A sweep that
        tagged nothing because it saw nothing is not a coverage failure, and only the two numbers
        together say which happened.
        """
        if self.events <= 0:
            return 0
        return self.tagged * ONE_DOMAIN_BP // self.events

    @property
    def is_indiscriminate(self) -> bool:
        """True when the tagger is labelling rather than distinguishing.

        THE GUARD THAT MAKES COVERAGE HONEST. A proposer returning every domain every time drives
        `coverage_bp` to 10000 and this flag to True at the same moment, and the pair is readable
        where either alone is not.
        """
        return self.mean_domains_per_event_bp > INDISCRIMINATE_MEAN_BP

    @property
    def dominant_share_bp(self) -> int:
        """The share of tagged events carried by the single most common domain.

        The six-VCs failure seen directly: sixteen sales situations, none of them a customer, in
        an org whose real activity was fundraising. One domain swallowing the corpus is a
        different fault from every domain firing at once, and `is_indiscriminate` cannot see it.
        """
        if not self.per_domain or self.tagged <= 0:
            return 0
        return max(self.per_domain.values()) * ONE_DOMAIN_BP // self.tagged


def domain_distribution(per_event: Sequence[Sequence[str]],
                        *, fallback_only: Sequence[bool] | None = None) -> DomainDistribution:
    """Tally one sweep's domain tags.

    `per_event` is one tuple of domain names per event. `fallback_only` is the parallel list
    saying, for each event, whether its only tag was the placeholder — passed in rather than
    inferred from the name, because `FALLBACK_DOMAIN` is `admin`, which is ALSO a real domain a
    keyword can match. Guessing from the name would count every genuine admin event as a gap.

    A shorter or absent `fallback_only` reads as False, so a caller that has not wired the flag
    gets the optimistic reading of its own data rather than a crash — and the flag's absence is
    visible in `fallback_only == 0`, which is checkable.
    """
    flags = list(fallback_only or ())
    counts: Counter[str] = Counter()
    tagged = fallback = untagged = 0
    total_domains = 0

    for index, domains in enumerate(per_event):
        names = [str(d) for d in domains if str(d).strip()]
        total_domains += len(names)
        counts.update(names)
        if not names:
            untagged += 1
        elif index < len(flags) and flags[index]:
            fallback += 1
        else:
            tagged += 1

    events = len(per_event)
    mean_bp = (total_domains * ONE_DOMAIN_BP // events) if events else 0
    return DomainDistribution(events=events, tagged=tagged, fallback_only=fallback,
                              untagged=untagged, per_domain=dict(counts),
                              mean_domains_per_event_bp=mean_bp)


__all__ = ["INDISCRIMINATE_MEAN_BP", "ONE_DOMAIN_BP", "DomainDistribution", "domain_distribution"]
