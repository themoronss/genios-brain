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
DARK_DOMAINS: dict[str, str] = {
    "fundraising":
        "⛔ THE PILOT TENANT'S OWN DOMAIN. Layer 2 registers it and mints "
        "`investor_relationship` and `investor_contact` today, declaring `funding.round`, "
        "`application_status`, `thread.ball_in_court` and `party.role` as the facts they are "
        "expected to know. `Domain Expertise/` authors Admin, Sales and Customer Support and "
        "nothing else, so `l3_domain_for('fundraising')` answers None and every investor "
        "situation on the tenant publishes no package and emits no signal. The benchmark mailbox "
        "is investors end to end — 3one4, Titan, Neon, Antler, PeakXV, Surge, IIMA, Suvan — and "
        "not one of them can reach a card. ENDS WHEN: a fundraising corpus is authored and "
        "admitted, and `_L2_TO_L3_DOMAIN` gains its row. Authoring, not code.",
    "general":
        "The deliberate catch-all. `domain_spec` gives it `relationship` and `deal` so a signal "
        "whose domain nothing recognised still mints a situation rather than vanishing — the "
        "same refusal-to-drop `capture`'s domain mapping makes one layer down, where an "
        "uncovered domain degrades rather than disappears. Authoring a `general` corpus would "
        "mean writing doctrine for 'business, unspecified', which is the shape of advice that "
        "reads as true and helps nobody. ENDS WHEN: a real domain is authored that claims what "
        "is currently landing in `general` — so the mover is a CENSUS of what actually lands "
        "here, not a corpus. Until that census exists this row is a known unknown, and saying so "
        "is the point.",
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
