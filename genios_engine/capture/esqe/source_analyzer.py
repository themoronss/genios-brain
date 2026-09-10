"""L1.6.4-U1 · Provenance and actor authority. *Who said it, and does that make it weigh more?*

Two numbers come out of this unit and ALG-17 reads both:

* ``evidence_authority_rank`` — the standing of the ARTIFACT (term 6). Not computed here at
  all: it is **delegated to ALG-14** (``capture/validate/authority.py``), which already owns
  the seven-class ladder and its basis-point multipliers. A second ranking table would be a
  second answer to a question that already has one, and the day the two disagree a signed
  contract outranks a Slack aside in the conflict resolver while losing to it in the scorer.
* ``actor_authority_bp`` — the standing of the PERSON (term 3). This unit's own work, and the
  half ALG-14's docstring explicitly refuses: *"whether the sender is the CFO or a no-reply
  robot is ``actor_authority_bp``, the other half of L1.6.4, and deliberately not here."*

WHY THE TWO ARE SEPARATE NUMBERS AND NOT ONE
--------------------------------------------
They move independently and they are not substitutes. A junior analyst can attach a
countersigned MSA (weak actor, rank-6 artifact) and the CFO can say "I think we're at $84K"
in a Slack thread (strongest actor, rank-1 artifact). Collapsing them into one authority
score makes those two indistinguishable, and every ranking built on the collapse then treats
a recollection as a receipt because of who typed it.

THE CASCADE, AND THE ONE PLACE IT DIVERGES FROM DOC 06
-------------------------------------------------------
Doc 06 lists the lookup in this order: graph role, ``internal_kind``, connection owner,
same-domain colleague, external counterparty, automated sender, unknown. Implemented in that
literal order the automated rung is **unreachable**: ``no-reply@ourcompany.com`` matches the
same-domain rung two steps earlier and scores 5000, and the doc's own acceptance line — *"a
``no-reply@`` sender scores 1000"* — fails. So the machine test is lifted above the two domain
rungs and below ``internal_kind``. Nothing else about the order changes, and the divergence is
one the acceptance criteria force rather than a preference.

RECONCILIATION WITH ``capture/internal_knowledge.py:123`` — REUSED VOCABULARY, REJECTED SCALE
----------------------------------------------------------------------------------------------
``internal_knowledge.authority_rank_for()`` is the partial authority table that exists today,
and doc 06 says to extend rather than replace it. What is REUSED is its vocabulary:
``normalize_kind``/``is_canon`` stay the single definition of "the company deliberately
asserting something about itself", so canon means one thing at the intake door, one thing in
ALG-14, and one thing here.

What is NOT reused is its numbers, and the reason is that it answers a different question on a
different scale. It returns 4 or 2 on the 0..4 ladder ``context.pipeline.FACT_CONF_BY_RANK`` is
keyed by, and it grades the ARTIFACT ("does this event carry company canon"), not the actor.
Feeding a 4 into an actor slot that runs 0..10000 basis points would read as 0.04% authority;
rescaling it here would put a third copy of the canon ladder in the tree. So this unit calls
``normalize_kind`` for the *decision* and assigns its own basis points for the *weight*, which
is exactly what ALG-14 does one layer down.

MACHINE SENDERS ARE ALREADY DETECTED — THIS UNIT DOES NOT RE-DETECT THEM
-------------------------------------------------------------------------
``capture/gate/rules.py`` owns the machine-sender regex, and the graph writer's own detector
(commit ``fc25ea1``) files those addresses as ``service`` nodes rather than ``person`` nodes.
Both exist because the same fact — this address is a robot — has to be true in the gate, in
the graph and in the scorer, and three regexes would drift into three different answers about
``notify@stripe.com``. The gate's table is the one imported: it is the conservative one
(``support@``/``info@``/``hello@`` are NOT machines there, because a small business really does
sell from ``hello@``), and conservative is the right direction for a rung that costs a sender
80% of its authority.

PURITY — no clock, no model, no database, no float
---------------------------------------------------
Authority does not age, so nothing here reads a clock. Every number is an integer basis point
so that two runs on two machines produce the same ordering. The graph lookup that rung 1
describes is a PARAMETER (``actor_role``), not a query: this unit is called once per event
inside the capture pipeline, and a unit that opened its own connection would make the pipeline
untestable and the ranking dependent on whether the graph happened to be reachable.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from genios_engine.capture.gate.rules import is_automated_sender
from genios_engine.capture.internal_knowledge import normalize_kind
from genios_engine.capture.validate.authority import (
    AuthorityWeight,
    Provenance,
    weigh_authority,
)
from genios_engine.contracts.source_event import SourceEvent

__all__ = [
    "ActorBasis",
    "SourceAttribution",
    "ROLE_AUTHORITY_BP",
    "RUNG_AUTHORITY_BP",
    "analyze_source",
    "role_authority_bp",
]


class ActorBasis(str, Enum):
    """WHICH rung of the cascade answered — the audit trail for an actor's basis points.

    Stored beside the number for the same reason ``AuthorityBasis`` is stored beside a rank:
    5000 from "same-domain colleague" and 5000 from "external counterparty" are the same
    integer and mean opposite things, and "why did this sender weigh what it weighed?" has to
    be answerable from the row rather than by re-running the cascade against a graph that has
    since learned the person's title.

    A ``str`` enum so it serialises as the doc's own words into an audit row.
    """

    #: The graph knew this person and knew their role. The only rung that can exceed 9000.
    ROLE_LADDER = "role_ladder"
    #: The event carries a canon ``internal_kind`` — the company asserting something itself.
    INTERNAL_KIND = "internal_kind"
    #: A machine: an ``agent``/``system`` actor type, or an automated local-part.
    AUTOMATED = "automated"
    #: The sender is the connected mailbox's own owner.
    CONNECTION_OWNER = "connection_owner"
    #: Same email domain as the org — a colleague whose title we do not know.
    SAME_DOMAIN = "same_domain"
    #: A recognisable human address on some other domain.
    EXTERNAL = "external"
    #: No address, or nothing about it we can rank. The conservative middle.
    UNKNOWN = "unknown"


#: Doc 06's cascade, in basis points, and the only place these six numbers appear.
#:
#: ``UNKNOWN`` at 3000 is the value worth defending: it sits BELOW both domain rungs and ABOVE
#: the machine rung, which is what "conservative" means for an actor we failed to identify. Put
#: it at the top and every unparsed sender is treated as a founder; put it at the floor and an
#: address our parser merely did not recognise is silently demoted to a robot, which is how a
#: real counterparty's mail stops reaching a card.
RUNG_AUTHORITY_BP: Mapping[ActorBasis, int] = MappingProxyType({
    ActorBasis.INTERNAL_KIND: 9000,
    ActorBasis.CONNECTION_OWNER: 8000,
    ActorBasis.SAME_DOMAIN: 5000,
    ActorBasis.EXTERNAL: 5000,
    ActorBasis.AUTOMATED: 1000,
    ActorBasis.UNKNOWN: 3000,
})

#: Rung 1 — the role ladder, applied to a title the GRAPH supplied. Basis points, integer.
#:
#: A ladder rather than a score: the gaps are uniform inside a tier and one tier apart between
#: tiers, so "does the CFO outrank a director" is a table read and not an argument. Titles are
#: normalised through ``_ROLE_ALIASES`` before the lookup, because a graph role arrives as
#: whatever the source wrote — "Chief Financial Officer", "cfo", "VP, Sales".
#:
#: The floor of the ladder is 5000, not 0: an intern is a real person who really wrote the
#: message, and a rung that ranks a known human below an unknown one (3000) would make
#: identifying somebody a way to lose authority.
ROLE_AUTHORITY_BP: Mapping[str, int] = MappingProxyType({
    "founder": 10000,
    "ceo": 10000,
    "owner": 10000,
    "president": 10000,
    "managing_director": 10000,
    "chairman": 10000,
    "cfo": 9500,
    "coo": 9500,
    "cto": 9500,
    "cmo": 9500,
    "cro": 9500,
    "cpo": 9500,
    "chief_of_staff": 9500,
    "vp": 9000,
    "head": 9000,
    "director": 9000,
    "partner": 9000,
    "manager": 8000,
    "lead": 8000,
    "principal": 8000,
    "employee": 6000,
    "analyst": 6000,
    "associate": 6000,
    "engineer": 6000,
    "specialist": 6000,
    "assistant": 6000,
    "intern": 5000,
    "contractor": 5000,
    "vendor": 5000,
})

#: Tolerant title -> ladder key. Free text in, one rung out, or nothing.
#:
#: Deliberately NOT a fuzzy matcher. An unrecognised title returns None and the cascade falls
#: through to the domain rungs, which is the honest answer — guessing that "Growth Ninja" is a
#: VP hands 9000 basis points to a job title nobody in this table ever read.
_ROLE_ALIASES: Mapping[str, str] = MappingProxyType({
    "co_founder": "founder", "cofounder": "founder", "founding_partner": "founder",
    "chief_executive_officer": "ceo", "chief_executive": "ceo",
    "md": "managing_director", "managing_partner": "managing_director",
    "chief_financial_officer": "cfo", "finance_head": "cfo",
    "chief_operating_officer": "coo",
    "chief_technology_officer": "cto", "chief_technical_officer": "cto",
    "chief_marketing_officer": "cmo",
    "chief_revenue_officer": "cro",
    "chief_product_officer": "cpo",
    "vice_president": "vp", "svp": "vp", "evp": "vp", "avp": "vp",
    "senior_vice_president": "vp", "executive_vice_president": "vp",
    "head_of": "head", "department_head": "head",
    "sr_director": "director", "senior_director": "director",
    "team_lead": "lead", "tech_lead": "lead", "teamlead": "lead",
    "senior_manager": "manager", "account_manager": "manager",
    "ic": "employee", "staff": "employee", "member": "employee",
    # `consultant` IS NOT HERE, and its removal is the point.
    #
    # It used to alias to `contractor` (5000, the floor). In a UK or Indian hospital a
    # Consultant is the SENIOR physician — the person whose sign-off the whole record turns on
    # — and this table filed them below an intern's manager. In a law firm, in management
    # consulting and in most of the NHS the same word carries the same seniority. The alias was
    # a guess about one industry's usage applied to every industry, and the guess actively
    # INVERTED the hierarchy it was trying to read.
    #
    # Falling through to None is strictly better: the cascade continues to the domain rungs and
    # attributes the person on evidence the system actually has, rather than on a word somebody
    # assumed meant "outsider". This is the same argument the comment above makes for refusing
    # to guess that "Growth Ninja" is a VP — and a tenant that really does mean contractor can
    # now say so in `org_role_authority` without a deploy.
    "freelancer": "contractor", "supplier": "vendor",
    "trainee": "intern", "internship": "intern",
})

#: Actor types that are machines whatever their address looks like. ``SourceEvent.actor.type``
#: is set by the connector, so an agent's own output re-entering capture is known to be a
#: machine before any regex sees it.
_MACHINE_ACTOR_TYPES: frozenset[str] = frozenset({"agent", "system", "bot", "service"})

_TITLE_JUNK = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True, slots=True)
class SourceAttribution:
    """The unit's answer: where the artifact stands, where its author stands, and why.

    Frozen, because the same event must attribute identically on a replay and a caller that
    edited one field between two reads is how one signal acquires two authorities.

    ``evidence`` is ALG-14's own ``AuthorityWeight`` object rather than a copy of its two
    numbers, so a consumer reads ``attribution.evidence.rank`` and
    ``attribution.evidence.multiplier_bp`` off the table that owns them. Copying the integers
    in here would freeze one run's reading of a table that is explicitly re-tunable.
    """

    #: ALG-14's verdict on the ARTIFACT — the class, the table that fired, and (as derived
    #: properties) the 0..6 rank and the 0..10000 multiplier ALG-17 term 6 multiplies by.
    evidence: AuthorityWeight
    #: ALG-17 term 3 — how much the PERSON who said it weighs, 0..10000, integer.
    actor_authority_bp: int
    #: Which rung of the cascade produced ``actor_authority_bp``.
    actor_basis: ActorBasis
    #: The address the cascade ranked, casefolded, or None when the event named nobody. Kept so
    #: an audit row can show WHO was ranked and not only how much.
    actor_email: str | None

    @property
    def evidence_authority_rank(self) -> int:
        """0..6 — doc 06's own field name for ALG-14's ladder position."""
        return self.evidence.rank

    @property
    def evidence_authority_multiplier_bp(self) -> int:
        """ALG-17 term 6's multiplier for this artifact class, in basis points."""
        return self.evidence.multiplier_bp


def _normalise_title(value: str | None,
                     ladder: Mapping[str, int] = ROLE_AUTHORITY_BP) -> str | None:
    """A free-text role -> a ladder key, or None.

    ``"Chief Financial Officer"``, ``"CFO"`` and ``"cfo "`` are one role written three ways, and
    folding them here is what keeps ``ROLE_AUTHORITY_BP`` free of case variants — the
    alternative being three rows per title, two of which nobody remembers to add.

    ``"VP, Sales"`` folds to ``"vp_sales"``, which is not a row, so the leading segment is tried
    as well: a compound title is still a VP. Only the LEADING segment, never the trailing one —
    "sales_vp" is a VP, but "vp_of_interns" must not resolve through "interns".
    """
    if not value:
        return None
    key = _TITLE_JUNK.sub("_", str(value).strip().lower()).strip("_")
    if not key:
        return None
    for candidate in (key, _ROLE_ALIASES.get(key)):
        if candidate and candidate in ladder:
            return candidate
    head = key.split("_", 1)[0]
    for candidate in (head, _ROLE_ALIASES.get(head)):
        if candidate and candidate in ladder:
            return candidate
    return None


#: A TENANT'S OWN LADDER, merged over the shipped one. Same shape as `org_qualification_floors`
#: and for the same reason: the rungs below are 29 rows of English corporate titles, and no list
#: of English corporate titles describes every business. A clinic says `consultant: 9500`; an
#: exporter says `proprietor: 10000`; a chambers says `silk: 10000`. None of those is a defect in
#: the shipped table — they are businesses it was never asked about.
#:
#: THE FLOOR RULE SURVIVES ANY OVERLAY. A rung below 3000 would rank a KNOWN human under an
#: unknown one, which makes identifying somebody a way to LOSE authority; and above 10000 is not
#: a basis point. Both are clamped rather than refused, because a tenant's typo must not silently
#: disable their whole ladder.
ROLE_AUTHORITY_TABLE = "org_role_authority"


def merged_ladder(overlay: Mapping[str, int] | None = None) -> Mapping[str, int]:
    """The shipped ladder with a tenant's rows written over it, normalised and clamped."""
    if not overlay:
        return ROLE_AUTHORITY_BP
    merged = dict(ROLE_AUTHORITY_BP)
    for role, value in overlay.items():
        key = _TITLE_JUNK.sub("_", str(role).strip().lower()).strip("_")
        if not key:
            continue
        try:
            merged[key] = max(3000, min(10000, int(value)))
        except (TypeError, ValueError):
            # A row that is not a number is not a rung. Skipped rather than defaulted: a
            # default here would hand a made-up authority to a role the tenant mis-typed.
            continue
    return merged


def role_authority_bp(actor_role: str | None,
                      overlay: Mapping[str, int] | None = None) -> int | None:
    """Rung 1 alone — the role ladder, for a caller that already holds a graph role.

    Returns None for a role the ladder has no row for, which is the signal to keep descending
    the cascade. Public because L1.6.7 scores a person the graph knows in contexts where no
    ``SourceEvent`` is in hand, and re-deriving "what is a CFO worth" at that call site is how
    two ladders come to exist.
    """
    ladder = merged_ladder(overlay)
    key = _normalise_title(actor_role, ladder)
    return None if key is None else ladder[key]


def _domain_of(email: str | None) -> str | None:
    """The part after the last ``@``, casefolded, or None when there is no address to split."""
    if not email:
        return None
    address = str(email).strip().casefold()
    if "@" not in address:
        return None
    domain = address.rsplit("@", 1)[1].strip()
    return domain or None


def _is_machine(event: SourceEvent, email: str | None) -> bool:
    """A machine sender, by the connector's own actor type or by the gate's address table.

    Both halves matter. The actor type catches an agent's output re-entering capture, which
    carries no giveaway address at all; the address table catches ``no-reply@``, ``notify.``
    and ``mailer-daemon`` on an otherwise ordinary ``external_contact``.
    """
    actor_type = (getattr(event.actor, "type", "") or "").strip().casefold()
    if actor_type in _MACHINE_ACTOR_TYPES:
        return True
    return bool(email) and is_automated_sender(email)


def analyze_source(event: SourceEvent, *,
                   source_ref: str | None = None,
                   executed: bool = False,
                   actor_role: str | None = None,
                   mailbox_owner: str | None = None,
                   org_domains: Iterable[str] = (),
                   role_overlay: Mapping[str, int] | None = None) -> SourceAttribution:
    """**L1.6.4-U1.** Rank one event's artifact and its author. Total, deterministic, pure.

    ``evidence_authority_rank`` is ALG-14's, produced by handing it a ``Provenance`` built from
    this event — the delegation doc 06 asks for in the words *"do not reimplement"*.

    ``actor_authority_bp`` is this unit's, from the cascade:

    1. a role the graph knows          -> ``ROLE_AUTHORITY_BP`` (5000..10000)
    2. a canon ``internal_kind``       -> 9000
    3. a machine sender                -> 1000  (lifted above the domain rungs; see module doc)
    4. the connected mailbox's owner   -> 8000
    5. same email domain as the org    -> 5000
    6. any other real address          -> 5000
    7. nothing rankable                -> 3000

    Never raises. Every unrankable input lands on rung 7 rather than an exception, for the same
    reason ALG-14 floors instead of failing: this runs unattended over real customer mail, and
    an exception costs a whole sweep while a conservative middle costs one signal some weight.

    Parameters that are lookups elsewhere are parameters here on purpose. ``actor_role`` is the
    graph's answer, ``mailbox_owner`` the connection's, ``executed`` the document layer's — this
    unit performs no I/O, so the same event with the same inputs attributes identically forever.
    """
    email = (getattr(event.actor, "email", None) or "").strip().casefold() or None

    attribution_evidence = weigh_authority(Provenance(
        source_ref=source_ref,
        source=event.source,
        object_type=event.object_type,
        internal_kind=event.internal_kind,
        executed=executed,
    ))

    def _answer(basis: ActorBasis, bp: int | None = None) -> SourceAttribution:
        return SourceAttribution(
            evidence=attribution_evidence,
            actor_authority_bp=RUNG_AUTHORITY_BP[basis] if bp is None else bp,
            actor_basis=basis,
            actor_email=email,
        )

    # The tenant's own rungs, merged over the shipped ladder. None on every call today — the
    # loader is `qualification`'s shape and the caller that holds `org_id` supplies it — and the
    # merge is a no-op in that case, so nothing changes for a tenant who has said nothing.
    by_role = role_authority_bp(actor_role, role_overlay)
    if by_role is not None:
        return _answer(ActorBasis.ROLE_LADDER, by_role)

    if normalize_kind(event.internal_kind) is not None:
        return _answer(ActorBasis.INTERNAL_KIND)

    if _is_machine(event, email):
        return _answer(ActorBasis.AUTOMATED)

    owner = (mailbox_owner or "").strip().casefold() or None
    if email is not None and owner is not None and email == owner:
        return _answer(ActorBasis.CONNECTION_OWNER)

    domain = _domain_of(email)
    if domain is not None:
        known = {d.strip().casefold().lstrip("@") for d in org_domains if d and str(d).strip()}
        owner_domain = _domain_of(owner)
        if owner_domain:
            known.add(owner_domain)
        if domain in known:
            return _answer(ActorBasis.SAME_DOMAIN)
        return _answer(ActorBasis.EXTERNAL)

    return _answer(ActorBasis.UNKNOWN)
