"""L1.6.6-U2/U3 · THE DOMAIN ONTOLOGY — which domains exist, and what happens to a name that does not.

Two jobs, and the second is the one with teeth:

1. **Which domains this deployment recognises** — the four shipped in `hints.py` plus every one an
   L3 corpus has authored in its `domain.yaml`.
2. **What happens to a proposal outside that set** — it is RECORDED as `proposed_unknown`, never
   discarded. A proposer that says *"procurement"* for a tenant with no procurement corpus has
   told us two true things: something about this message, and something about our own gap.

WHY THE SET IS DERIVED AND NEVER LISTED. A hand-written tuple is correct the day it is typed and
wrong the day a tenant authors a corpus, and the failure mode is the worst available: the matcher
in `hints.py` produces a domain, this module refuses it, and a perfectly well-known name lands in
the review queue as unknown. So `registered_domains()` reads the same tables `domain_hints`
matches against, and `test_every_domain_the_matcher_can_produce_is_registered` is what holds the
two together.

WHY AN UNKNOWN IS KEPT. `context/extract/vocab.py` records what happens otherwise — *268 distinct
field names in one org, 192 of them used exactly once* — a vocabulary that grew from nothing
because every unrecognised name was dropped where no one could count it. The discovery lane exists
so a name we do not have a word for becomes evidence rather than a silence. A domain is the same
shape of problem one level up.

MALFORMED IS NOT UNKNOWN, and the distinction is what keeps the review queue readable. `""` and
`None` are not domains somebody proposed; they are a broken answer. Filing them beside
*"procurement"* would put rows in front of a human that name nothing and teach them to skim.

PURE: no clock, no I/O, no model. It is handed a name and returns a verdict.
"""
from __future__ import annotations

from dataclasses import dataclass

#: A proposal naming a domain this deployment does not run. **Recorded, never dropped** — it is a
#: statement about a gap in our coverage, which is exactly what the weekly review is for.
PROPOSED_UNKNOWN = "proposed_unknown"

#: A proposal that is not a domain name at all — blank, whitespace, or not a string. Distinct from
#: the above because it names nothing and there is nothing for a reviewer to decide about it.
PROPOSED_MALFORMED = "proposed_malformed"

#: Accepted: the name is in the registered set.
ACCEPTED = "accepted"

#: Longest a domain name may be. A model that returns a sentence has not proposed a domain, and
#: storing it would put a paragraph in a column every card renders inline.
MAX_DOMAIN_CHARS = 64


@dataclass(frozen=True, slots=True)
class ProposalVerdict:
    """What the ontology says about one proposed domain name.

    `domain` is the NORMALISED name and it survives every outcome, including refusal — a verdict
    that dropped the name would make `proposed_unknown` unreviewable, which is the one thing this
    module exists to prevent.
    """

    domain: str
    outcome: str

    @property
    def accepted(self) -> bool:
        return self.outcome == ACCEPTED

    @property
    def is_unknown(self) -> bool:
        """True for a real name we do not run — the row a reviewer should actually see."""
        return self.outcome == PROPOSED_UNKNOWN


def normalize_domain(value: object) -> str | None:
    """A proposed name into its canonical form, or None when it is not a name at all.

    `Sales`, ` sales ` and `SALES` are ONE domain. Judging them as three would file two perfectly
    good proposals as unknown and fill the review queue with noise that hides the real finding.
    Lowercased and stripped, matching how `hints.py` already keys its source priors.
    """
    if not isinstance(value, str):
        return None
    name = " ".join(value.split()).strip().lower()
    if not name or len(name) > MAX_DOMAIN_CHARS:
        return None
    return name


def registered_domains() -> frozenset[str]:
    """Every domain this deployment recognises: shipped ∪ authored ∪ the fallback.

    Read off `hints.py`'s own tables rather than listed here, so a corpus authored tomorrow is
    registered tomorrow and not on the day somebody remembers to edit this file.

    THE FALLBACK IS INCLUDED EXPLICITLY. `FALLBACK_DOMAIN` is stamped on every business message
    nothing matched, and an ontology that refused it would turn the most common tag in the system
    into an unknown proposal. It happens to be `admin`, which is also shipped — the union is
    written anyway, because the day somebody points the fallback at a name that is not in
    `_SHIPPED_RANK` this keeps working instead of breaking quietly.
    """
    from genios_engine.capture.domain.hints import (FALLBACK_DOMAIN, _SHIPPED_RANK, _SOURCE_PRIOR,
                                                    _authored_hints)

    authored_keywords, authored_priors = _authored_hints()
    names = {*_SHIPPED_RANK, *_SOURCE_PRIOR.values(), *authored_keywords, *authored_priors.values()}
    names.add(FALLBACK_DOMAIN)
    return frozenset(name for name in (normalize_domain(n) for n in names) if name)


def validate_proposal(value: object) -> ProposalVerdict:
    """Judge one proposed domain name. Never raises, never drops, never guesses a near neighbour.

    NO FUZZY MATCHING, deliberately. Mapping `procurements` to `procurement` would hide exactly
    the drift this records: a proposer that cannot spell a domain consistently is a proposer whose
    output nobody should be silently repairing. The same argument `capture/validate/schema.py`
    makes about S-3 — *"a value outside the set is never mapped to a near neighbour, because that
    would hide the drift that produced it."*
    """
    name = normalize_domain(value)
    if name is None:
        return ProposalVerdict(domain="", outcome=PROPOSED_MALFORMED)
    if name in registered_domains():
        return ProposalVerdict(domain=name, outcome=ACCEPTED)
    return ProposalVerdict(domain=name, outcome=PROPOSED_UNKNOWN)


__all__ = ["ACCEPTED", "MAX_DOMAIN_CHARS", "PROPOSED_MALFORMED", "PROPOSED_UNKNOWN",
           "ProposalVerdict", "normalize_domain", "registered_domains", "validate_proposal"]
