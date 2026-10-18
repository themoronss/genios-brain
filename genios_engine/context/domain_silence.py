"""Which DOMAINS no authored corpus claims — declared, with a reason and a mover.

A DOMAIN LAYER 2 SERVES AND LAYER 3 CANNOT READ PRODUCES NOTHING, and produces it silently. The
chain is `domain_spec` registers a domain → correlation mints a situation of its type →
`l3_domain_for` looks for the corpus that claims it → `live_lane()` publishes a package and emits a
signal. When no corpus was authored, the chain ends at step three: `l3_domain_for` answers `None`,
`live_lane()` returns `False` **on every tenant configuration**, and nothing anywhere says a word.

This is the third place this layer needs the same fact, and the only one that had no file:

* `patterns/routing.UNROUTED_PATTERN_TYPES` — pattern types no domain binds
* `lane_health.SILENT_LANES` — readings producing nothing
* **here** — domains no corpus reads

`lane_health`'s opening is this file's whole argument, already written down once:

    A READING THAT RETURNS NOTHING IS INDISTINGUISHABLE FROM ONE THAT IS BROKEN, from the card side
    and from the log. Five lanes in this layer were dead for months while looking wired, and every
    one was found by accident rather than by a check.

⛔ **DORMANT IS NOT BROKEN, AND THE DIFFERENCE IS THE WHOLE POINT** — also `lane_health`'s, and the
reason an unclaimed domain must be DECLARED rather than merely counted. A domain nobody authored is
a decision somebody made. A domain nobody noticed is a defect wearing the same face.

**Checked in both directions**, exactly as both siblings are. A registered domain that no corpus
claims and is not listed here fails the suite; an entry here whose corpus has since been authored
fails just as loudly. A table that only ever grows becomes a list of things that used to be true.

THIS FILE REPORTS AND NEVER ROUTES. It does not map a dark domain onto a near one to "get some
coverage" — `domain_shadow`'s own comment refuses that in as many words, and it is right: putting
Admin doctrine on a fundraising situation is how six VCs and three accelerator programmes became
sales opportunities. Ending a silence is authoring a corpus, not re-pointing a table.
"""

from __future__ import annotations

#: `{domain: why no corpus claims it, and exactly what would end that}`.
#:
#: Every entry names its mover. A permanent exception list is a way to never fix anything.
#: ⛔ `fundraising` LEFT THIS TABLE ON 2026-10-09 (STEP-11, `06` D2): its doctrine moved into the
#: Founder Office corpus and `domain_shadow._L2_TO_L3_DOMAIN` maps it there — the mover its entry
#: named, to a corpus of its own rather than to Sales. Checked both ways, as this module promises: a
#: domain a corpus claims may not be listed here.
DARK_DOMAINS: dict[str, str] = {
    "general":
        "The deliberate catch-all. `domain_spec` gives it `relationship` and `deal` so a signal "
        "whose domain nothing recognised still mints a situation rather than vanishing — the "
        "same refusal-to-drop `capture`'s domain mapping makes one layer down, where an "
        "uncovered domain degrades rather than disappears. Authoring a `general` corpus would "
        "mean writing doctrine for 'business, unspecified', which is the shape of advice that "
        "reads as true and helps nobody. "
        "⛔ AND IT IS DARK FOR A DIFFERENT REASON FROM `fundraising`, WHICH ONE SENTENCE USED TO "
        "COVER FOR BOTH. `general:relationship` is claimed by ALL THREE authored corpora — admin, "
        "sales and customer_support — so a route here is AMBIGUOUS: a choice nobody has made, "
        "not a corpus nobody wrote. Picking one by hand is how Admin doctrine lands on a support "
        "thread. ENDS WHEN: a CENSUS says what actually lands in `general` and a real domain "
        "claims it — the mover is the census, not a corpus. Until then this row is a known "
        "unknown, and saying so is the point.",
}


def is_dark(domain: str | None) -> bool:
    """Does this domain mint situations that no authored corpus can read?

    A question the callers ask BEFORE concluding that a tenant has nothing happening — which is
    the reading `live_lane()` returning False produces today, and it is wrong.
    """
    return str(domain or "").strip().lower() in DARK_DOMAINS


def reason_for(domain: str | None) -> str | None:
    """Why, in the words that name what would end it. `None` when the domain is not dark."""
    return DARK_DOMAINS.get(str(domain or "").strip().lower())


__all__ = ["DARK_DOMAINS", "is_dark", "reason_for"]
