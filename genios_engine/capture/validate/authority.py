"""ALG-14 · L1.5.8-U1 — the authority ranking table. *A signed PDF is not a Slack aside.*

One question, answered from frozen tables and nothing else: **how much does the artifact
this claim came out of count?** A countersigned agreement outranks the company's own
uploaded pricing policy, which outranks a HubSpot deal field, which outranks the PDF quote
attached to an email, which outranks the email's own prose, which outranks a Slack
one-liner, which outranks something we merely inferred. Seven classes, seven ranks, a
strict total order, no ties.

WHY THIS UNIT IS IN WAVE W1 AND NOT W2
--------------------------------------
The plan's component map (doc 05, line 31) schedules L1.5.8 for W2. Its own WHY paragraph
contradicts that: *"Conflict resolution (ALG-12) and confidence composition (ALG-13) both
depend on this ordering."* ALG-13 is L1.5.7, which ships in **W1**. A W1 unit cannot depend
on a W2 unit without W1 shipping with a hole where its authority input should be, so this
was pulled forward into W1. Nothing else about the unit changed — same table, same doc.

WHAT THIS UNIT DECIDES, AND WHAT IT REFUSES TO DECIDE
-----------------------------------------------------
It decides **evidence authority**: the standing of the ARTIFACT. It says nothing about the
PERSON — whether the sender is the CFO or a no-reply robot is ``actor_authority_bp``, the
other half of L1.6.4, and deliberately not here. Conflating the two would let a founder's
offhand Slack message outrank the contract they signed, which is the precise inversion the
ranking exists to prevent.

It also does not resolve conflicts. ALG-12 compares two ranks and requires a gap of **>= 2**
before it will recommend a winner (doc 05, step 4) — one step of authority is never enough to
silence the other side. That threshold only means anything because the ranks here are a
dense, evenly-spaced ladder rather than scores: subtracting two of these and comparing the
difference to 2 is arithmetic that becomes meaningless the moment the scale changes. Hence
``rank_of`` returns a small integer and ``multiplier_bp_of`` returns basis points, and the
two are never mixed.

WHY A TABLE AND NOT A CASCADE OF ``if``
---------------------------------------
Adding a source must be adding a ROW. A branch ladder grows a new leg per source, each leg
reachable only by the test somebody remembered to write, and the day two legs overlap the
answer depends on the order they were typed in. The tables below are the whole algorithm;
``weigh_authority`` only chooses which table to consult first, and records that choice in
``AuthorityWeight.basis`` so the answer is explainable without re-running anything.

TOTALITY — the unmapped case is a rank, never an exception
-----------------------------------------------------------
Doc 05's acceptance line is explicit: *"unmapped prefix -> rank 0 and a logged warning,
never a crash."* An unknown provenance is exactly when the pipeline is least able to absorb
an exception — it happens on real customer data, at 3am, on the one source nobody had seen
— so an unknown lands at ``Authority.INFERRED``, rank 0, the floor. Falling to the floor is
conservative in the only direction that matters: an unknown artifact can never win a
conflict against a known one, and rank 0 carries the smallest importance multiplier.

RECONCILIATION WITH ``capture/internal_knowledge.py`` — TWO SCALES, ON PURPOSE
------------------------------------------------------------------------------
``internal_knowledge.authority_rank_for()`` is the partial table that exists today, and doc
06 says to extend rather than replace it. What is reused is its **vocabulary**: ``is_canon``
is still the single definition of "the company deliberately asserting something about
itself", so company canon cannot mean one thing here and another at the intake door.

What is NOT reused is its **numbers**, and this is the important half. That table is on a
0..4 scale keyed to Layer 2's ``context.pipeline.FACT_CONF_BY_RANK`` (canon 4, system of
record 3, observed prose 2). ALG-14 is on a 0..6 scale that inserts a signed-document tier
above canon and separates chat from prose below it. The two scales share the digits 0..4 and
mean different things by them:

    legacy 4 = company canon          ALG-14 4 = a structured source of record
    legacy 3 = system of record       ALG-14 3 = an attached document

Passing an ALG-14 rank into a legacy call site therefore does not fail — it silently demotes
canon to a CRM row, or raises ``KeyError`` on 5 and 6. ``to_legacy_rank`` is the one
sanctioned converter across that seam, so the translation lives in a tested table instead of
being re-derived (usually as ``rank - 1``, which is wrong for four of the seven classes) at
each call site. ``internal_knowledge`` is left untouched: it is on the live Layer 2 write
path, and re-basing it would move every stored fact's confidence tier.

Everything here is data plus lookups. No clock — authority does not age, and the recency
tie-break that does is ALG-12's, taking ``eval_time`` as an argument. No model — this
produces a number consumed by ranking, and ranking must be byte-identical across machines
and across replays. No floats — ranks are small integers, multipliers are basis points.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType

from genios_engine.capture.internal_knowledge import normalize_kind
from genios_engine.contracts.conflict import MAX_AUTHORITY_RANK, Authority

log = logging.getLogger(__name__)

#: Doc 05's ALG-14 table, verbatim, and the only place these seven numbers appear.
#:
#: Injective by construction — seven classes, seven distinct ranks — which is what makes the
#: order STRICT and therefore total: any two classes are comparable and never equal unless
#: they are the same class. A duplicated rank would make two provenances indistinguishable to
#: ALG-12 and silently convert an authority resolution into a recency coin-flip.
#:
#: Read as a ladder rather than a score. The gaps are uniform on purpose: ALG-12's "gap >= 2"
#: rule means adjacent classes never auto-resolve against each other (an attachment does not
#: silence the email that carried it), while two steps apart does (a signed contract silences
#: a chat aside). Re-spacing this table re-tunes conflict resolution globally.
AUTHORITY_RANK: Mapping[Authority, int] = MappingProxyType({
    Authority.SIGNED_DOCUMENT: 6,    # countersigned / executed agreement
    Authority.COMPANY_CANON: 5,      # uploaded pricing policy, handbook — `internal_kind`
    Authority.STRUCTURED_SOURCE: 4,  # HubSpot deal field, client DB row — a typed field
    Authority.ATTACHMENT: 3,         # the PDF quote inside an email
    Authority.EMAIL_PROSE: 2,        # "the $84K contract" — a recollection of a document
    Authority.CHAT_ASIDE: 1,         # a Slack one-liner: the weakest thing a human wrote
    Authority.INFERRED: 0,           # inferred / unattributed — no evidence pointer
})

#: ALG-17 term 6, ``evidence_authority_multiplier_bp`` (doc 06): the importance scorer's
#: multiplier for each rank, so a signed document outweighs a Slack aside on identical facts.
#:
#: It lives here, not in the scorer, because doc 06 says "from ALG-14" and because a second
#: copy beside the ranks is a second thing to re-tune — the day one moves without the other,
#: importance and conflict resolution start disagreeing about which source is stronger.
#:
#: Basis points, ``0..10000``, integer. Note the floor is 4000 and not 0: an unattributed
#: claim is discounted, not erased. Zeroing it would multiply every other term away and drop
#: signals whose only fault is that their provenance was not recognised — which is a bug in
#: this table, not a reason to hide the signal.
RANK_MULTIPLIER_BP: Mapping[int, int] = MappingProxyType({
    6: 10000, 5: 9500, 4: 9000, 3: 8500, 2: 8000, 1: 6500, 0: 4000,
})

#: ``EvidenceSpan.source_ref`` prefix -> provenance class. The prefix is the part before the
#: first ``:``; doc 08 fixes two literal shapes (``prepared_content:<event_id>``,
#: ``chunk:<doc_id>:<n>``) and doc 03 line 385 adds ``structured:<mapping_id>#<field>``.
#:
#: This is the LAST table consulted, because a ref names the CONTAINER the text was read out
#: of, not the standing of the artifact: every email body and every chat message alike arrive
#: as ``prepared_content:``. It is therefore the coarse fallback for when the source event's
#: identity is unavailable, and ``prepared_content`` maps to EMAIL_PROSE rather than to the
#: lower CHAT_ASIDE because doc 05's own rank-2 example ("the $84K contract") is exactly a
#: prepared email body. The failure that admits — an unrecognised chat platform read one rank
#: too strong — is bounded by ALG-12's gap-of-2 rule, which never resolves on one step.
SOURCE_REF_PREFIX_AUTHORITY: Mapping[str, Authority] = MappingProxyType({
    "structured": Authority.STRUCTURED_SOURCE,
    "chunk": Authority.ATTACHMENT,
    "prepared_content": Authority.EMAIL_PROSE,
})

#: ``(source, object_type)`` -> provenance class. The most specific table, consulted first,
#: and deliberately tiny: it holds only the pairs where the source and the object type would
#: otherwise disagree.
#:
#: The case it exists for is the bare object type ``message``, which the registry declares for
#: Gmail and which every chat connector also produces. On object type alone that reads as
#: prose (rank 2); on source alone a document shared into Slack would read as a chat aside
#: (rank 1). Pinning the pair lets the coarser tables stay right for everything else.
SOURCE_OBJECT_AUTHORITY: Mapping[tuple[str, str], Authority] = MappingProxyType({
    ("slack", "message"): Authority.CHAT_ASIDE,
    ("teams", "message"): Authority.CHAT_ASIDE,
    ("whatsapp", "message"): Authority.CHAT_ASIDE,
    ("sms", "message"): Authority.CHAT_ASIDE,
})

#: ``SourceEvent.object_type`` -> provenance class, for the object types the connectors and
#: the source registry actually emit. Consulted before the source, because the KIND of object
#: is a stronger statement about an artifact than the system it came from: a PDF is an
#: attachment whether it arrived by mail or by chat.
#:
#: ``action`` — an agent's own output re-entering capture — maps to INFERRED on purpose, and
#: it is the row worth defending. Our own conclusion is not evidence for itself; letting it
#: land above rank 0 would launder yesterday's inference into today's receipt and let the
#: system corroborate its own mistakes. ``internal_knowledge`` draws the same line when it
#: excludes Company Memory from the canon vocabulary.
OBJECT_TYPE_AUTHORITY: Mapping[str, Authority] = MappingProxyType({
    "email_message": Authority.EMAIL_PROSE,
    "message": Authority.EMAIL_PROSE,
    "email_attachment": Authority.ATTACHMENT,
    "document_chunk": Authority.ATTACHMENT,
    "file": Authority.ATTACHMENT,
    "page": Authority.ATTACHMENT,
    "calendar_event": Authority.STRUCTURED_SOURCE,
    "deal": Authority.STRUCTURED_SOURCE,
    "subscription": Authority.STRUCTURED_SOURCE,
    "action": Authority.INFERRED,
})

#: ``SourceEvent.source`` -> provenance class, for sources where EVERY object is one class
#: whatever its type. Consulted after the object type, as the next-coarsest fallback.
#:
#: Two groups only. Systems of record, whose objects are typed fields rather than prose —
#: doc 00's route table puts "hubspot / stripe / gcal / client DB" at rank 4 as a class, and
#: the tenant's own database tables are unenumerable so they can only be caught here. And
#: GeniOS's own outputs, at rank 0, for the reason ``action`` is at rank 0.
#:
#: Mail and document sources are deliberately ABSENT: Gmail emits both an ``email_message``
#: and an ``email_attachment`` and those are two different ranks, so a per-source answer for
#: Gmail would have to be wrong for one of them.
SOURCE_AUTHORITY: Mapping[str, Authority] = MappingProxyType({
    "slack": Authority.CHAT_ASIDE,
    "teams": Authority.CHAT_ASIDE,
    "whatsapp": Authority.CHAT_ASIDE,
    "sms": Authority.CHAT_ASIDE,
    "hubspot": Authority.STRUCTURED_SOURCE,
    "salesforce": Authority.STRUCTURED_SOURCE,
    "pipedrive": Authority.STRUCTURED_SOURCE,
    "stripe": Authority.STRUCTURED_SOURCE,
    "razorpay": Authority.STRUCTURED_SOURCE,
    "mixpanel": Authority.STRUCTURED_SOURCE,
    "gcal": Authority.STRUCTURED_SOURCE,
    "mscal": Authority.STRUCTURED_SOURCE,
    "postgres": Authority.STRUCTURED_SOURCE,
    "mysql": Authority.STRUCTURED_SOURCE,
    "database": Authority.STRUCTURED_SOURCE,
    "genios": Authority.INFERRED,
    "agent": Authority.INFERRED,
})

#: Where an unrecognised provenance lands. Named rather than inlined so the floor is one
#: edit, and so a reader can see that it is the same member the tables use for our own
#: inference — an unattributed claim and a self-generated one are worth the same: nothing.
UNMAPPED_AUTHORITY: Authority = Authority.INFERRED

#: ALG-14 -> the legacy 0..4 scale that ``context.pipeline.FACT_CONF_BY_RANK`` is keyed by.
#: See the module docstring for why the two scales exist. Every value is a live key of that
#: dict (4, 3, 2, 1), so a translated rank can never raise ``KeyError`` at the Layer 2 fact
#: write; INFERRED floors at 1 because the legacy dict has no 0 tier.
#:
#: Not ``rank - 1``: that is right for STRUCTURED_SOURCE and ATTACHMENT and wrong for the
#: other five. Signed documents and canon both collapse onto legacy 4 because Layer 2 has no
#: tier above canon to collapse them into — a real loss of resolution at that seam, and the
#: reason ALG-12 and ALG-13 must compare ALG-14 ranks and never legacy ones.
LEGACY_RANK: Mapping[Authority, int] = MappingProxyType({
    Authority.SIGNED_DOCUMENT: 4,
    Authority.COMPANY_CANON: 4,
    Authority.STRUCTURED_SOURCE: 3,
    Authority.ATTACHMENT: 3,
    Authority.EMAIL_PROSE: 2,
    Authority.CHAT_ASIDE: 1,
    Authority.INFERRED: 1,
})


class AuthorityBasis(str, Enum):
    """WHICH table answered — the audit trail for a rank.

    Stored on every ``AuthorityWeight`` because "why is this a 3?" has to be answerable from
    the record rather than by re-running the cascade against provenance that may since have
    changed. It is also the only way ``UNMAPPED`` is visible: a rank 0 from the fallback and
    a rank 0 from a recognised agent action are the same number and mean opposite things —
    one is "we know this is our own inference", the other is "we did not recognise this at
    all, and a row is missing from a table".

    A ``str`` enum so it serialises as the doc's own words into an audit row.
    """

    #: The caller stated the artifact is executed / countersigned. Beats every table.
    EXECUTED = "executed"
    #: `internal_kind` normalised to a declared canon kind (`internal_knowledge.is_canon`).
    COMPANY_CANON_KIND = "company_canon_kind"
    #: An exact `(source, object_type)` row.
    SOURCE_OBJECT = "source_object"
    #: An `object_type` row.
    OBJECT_TYPE = "object_type"
    #: A `source` row.
    SOURCE = "source"
    #: The `source_ref` prefix — the coarse fallback.
    SOURCE_REF_PREFIX = "source_ref_prefix"
    #: Nothing matched. Rank 0, a logged warning, and a missing table row to go and add.
    UNMAPPED = "unmapped"


@dataclass(frozen=True, slots=True)
class Provenance:
    """Everything about WHERE a claim came from that can change its rank — and nothing else.

    A typed input rather than keyword arguments or a dict, so that adding a provenance
    dimension later is a field with a default instead of a silently-ignored key at some call
    site. Every field is optional because every one of them genuinely can be missing: an
    extractor holds a span and its ``source_ref`` but not always the event, and the fallback
    ladder in ``weigh_authority`` exists precisely to answer from whatever is present.

    Frozen: the same provenance must produce the same rank on a replay, and a mutable input
    that a caller edits between two calls is how one claim acquires two ranks.
    """

    #: ``EvidenceSpan.source_ref``. Its prefix is the last thing consulted.
    source_ref: str | None = None
    #: ``SourceEvent.source`` — "gmail", "slack", "hubspot", the tenant's database.
    source: str | None = None
    #: ``SourceEvent.object_type`` — "email_message", "email_attachment", "deal".
    object_type: str | None = None
    #: ``SourceEvent.internal_kind`` — set when the company deliberately asserted this.
    #: Free text by design at the intake door, so it is normalised through
    #: ``internal_knowledge.normalize_kind`` rather than compared raw.
    internal_kind: str | None = None
    #: The artifact is countersigned / executed, established by the caller (a signature
    #: block, a DocuSign envelope, an explicit human mark) — never guessed here.
    #:
    #: It is a flag rather than a table row because "signed" is orthogonal to source and
    #: object type: the same ``email_attachment`` from the same mailbox is rank 3 as a draft
    #: and rank 6 once executed, and doc 05's own failure table names "a draft vs a signed
    #: version" as the false conflict the ranking has to separate. A caller that cannot
    #: establish it leaves it False, and the attachment stays at rank 3 — understating a
    #: signed contract by three ranks is recoverable, promoting a draft to rank 6 is not.
    executed: bool = False


@dataclass(frozen=True, slots=True)
class AuthorityWeight:
    """The unit's answer: a provenance class, the table that produced it, and the two numbers
    downstream reads off it.

    ``rank`` and ``multiplier_bp`` are derived properties, not stored fields, so this object
    cannot be constructed carrying a rank that disagrees with ``AUTHORITY_RANK``. That
    disagreement is exactly the bug the type would otherwise invite: a card explaining "the
    signed document has higher authority" beside a rank somebody set by hand.

    Note what a consumer stores is a different question. ``ConflictClaim.authority_rank``
    keeps a COPY of the integer on purpose, because a stored conflict must keep explaining
    the resolution it actually made even after this table is re-tuned.
    """

    #: The provenance class. The vocabulary is the contract's ``Authority`` enum — this
    #: module owns the class-to-rank mapping, contracts own the closed set of class names,
    #: and neither holds a copy of the other (see ``contracts/conflict.py``'s docstring).
    authority: Authority
    #: Which table fired. See ``AuthorityBasis``.
    basis: AuthorityBasis

    @property
    def rank(self) -> int:
        """0..6 — what ALG-12 subtracts and ALG-13 weighs. A ladder position, never a score."""
        return AUTHORITY_RANK[self.authority]

    @property
    def multiplier_bp(self) -> int:
        """ALG-17 term 6, integer basis points in ``0..10000``. Never divided here: the
        scorer applies ``... * multiplier_bp // 10000`` so the rounding happens once, at the
        end, in integers."""
        return RANK_MULTIPLIER_BP[AUTHORITY_RANK[self.authority]]

    @property
    def recognised(self) -> bool:
        """False when no table matched and the floor was used.

        Worth branching on: an unrecognised provenance is a missing table row, and a caller
        that surfaces it (a counter, a warning on the audit row) is how the row gets added
        instead of the source quietly scoring 4000 bp forever.
        """
        return self.basis is not AuthorityBasis.UNMAPPED


def rank_of(authority: Authority) -> int:
    """The rank of a provenance class — the ranking table's single read.

    Total over ``Authority`` by construction: the enum is closed, ``AUTHORITY_RANK`` has a
    row for every member, and the test suite asserts that correspondence so a member added to
    the contract without a row here fails at the gate rather than at a ``KeyError`` in
    production. Callers that already hold a class — ALG-12 reading ``ConflictClaim.authority``
    — use this directly instead of routing a synthetic ``Provenance`` through the cascade.
    """
    return AUTHORITY_RANK[authority]


def multiplier_bp_of(authority: Authority) -> int:
    """ALG-17's ``evidence_authority_multiplier_bp`` for a provenance class.

    Separate from ``rank_of`` because the two are different scales with different consumers,
    and a single function returning "the authority number" is how a 0..6 ladder position ends
    up multiplied into a basis-point product.
    """
    return RANK_MULTIPLIER_BP[AUTHORITY_RANK[authority]]


def to_legacy_rank(authority: Authority) -> int:
    """ALG-14's class -> the 0..4 scale ``context.pipeline.FACT_CONF_BY_RANK`` is keyed by.

    The ONE sanctioned crossing between the two scales; see the module docstring for why they
    differ and why neither is being re-based. Every result is a live key of that dict, so the
    Layer 2 fact write cannot raise on a translated rank.

    Lossy in one direction and honestly so: signed documents and company canon both land on
    legacy 4, because Layer 2 has no tier above canon. That is why conflict resolution and
    confidence composition compare ALG-14 ranks — translate at the write, never before.
    """
    return LEGACY_RANK[authority]


def _key(value: str | None) -> str | None:
    """Case-folded, whitespace-trimmed lookup key, or None when there is nothing to look up.

    Source and object-type strings arrive from connector payloads and from tenant
    configuration, so "Slack", " slack " and "slack" are one source written three ways. Doing
    this once here is what keeps the tables free of case variants — the alternative is three
    rows per source, two of which nobody remembers to add.
    """
    if not isinstance(value, str):
        return None
    folded = value.strip().casefold()
    return folded or None


def _prefix_of(source_ref: str | None) -> str | None:
    """The scheme of a ``source_ref`` — the text before the first ``:``.

    ``"chunk:doc-1:4"`` -> ``"chunk"``. A ref with no colon has no prefix and returns None
    rather than being treated as one: ``"garbage"`` is a malformed ref, and silently reading
    the whole string as a scheme would make a typo look like an unmapped source type.
    """
    key = _key(source_ref)
    if key is None or ":" not in key:
        return None
    return key.split(":", 1)[0] or None


def weigh_authority(provenance: Provenance) -> AuthorityWeight:
    """Rank one piece of evidence by where it came from. Total, deterministic, table-driven.

    The cascade is most-specific-first, and each step is a single table probe rather than a
    condition — the ordering is the only logic in this module:

    1. ``executed``                       -> SIGNED_DOCUMENT (6). Orthogonal to everything
       else: an executed agreement is rank 6 whatever carried it.
    2. a canon ``internal_kind``          -> COMPANY_CANON (5), via ``normalize_kind`` so the
       definition of canon is shared with the intake door rather than copied.
    3. ``(source, object_type)``          -> the disambiguating pairs.
    4. ``object_type``                    -> the kind of artifact.
    5. ``source``                         -> the system, for sources with one class.
    6. the ``source_ref`` prefix          -> the container the text was read out of.
    7. nothing matched                    -> INFERRED (0), and a warning naming what was
       unrecognised, so the missing table row can be added.

    Steps 3-6 run in that order because specificity beats coarseness: a PDF shared into Slack
    is an attachment (step 4) before Slack is chat (step 5), and both are known before the
    ref prefix, which cannot tell an email body from a chat message at all.

    Never raises. Every failure mode of this function is a rank-0 answer with a basis of
    ``UNMAPPED``, because the caller is a capture pipeline running unattended over real
    customer data and an exception there costs a whole sync, while a floored rank costs one
    signal some importance and can never win a conflict it should have lost.
    """
    if provenance.executed:
        return AuthorityWeight(Authority.SIGNED_DOCUMENT, AuthorityBasis.EXECUTED)

    if normalize_kind(provenance.internal_kind) is not None:
        return AuthorityWeight(Authority.COMPANY_CANON, AuthorityBasis.COMPANY_CANON_KIND)

    source = _key(provenance.source)
    object_type = _key(provenance.object_type)

    if source is not None and object_type is not None:
        pair = SOURCE_OBJECT_AUTHORITY.get((source, object_type))
        if pair is not None:
            return AuthorityWeight(pair, AuthorityBasis.SOURCE_OBJECT)

    if object_type is not None:
        by_object = OBJECT_TYPE_AUTHORITY.get(object_type)
        if by_object is not None:
            return AuthorityWeight(by_object, AuthorityBasis.OBJECT_TYPE)

    if source is not None:
        by_source = SOURCE_AUTHORITY.get(source)
        if by_source is not None:
            return AuthorityWeight(by_source, AuthorityBasis.SOURCE)

    prefix = _prefix_of(provenance.source_ref)
    if prefix is not None:
        by_prefix = SOURCE_REF_PREFIX_AUTHORITY.get(prefix)
        if by_prefix is not None:
            return AuthorityWeight(by_prefix, AuthorityBasis.SOURCE_REF_PREFIX)

    # Doc 05's acceptance, in full: rank 0 AND a warning. The warning is the half that gets
    # the table fixed — a floor that is silent is indistinguishable from a correct answer,
    # and the source stays under-ranked for as long as nobody looks.
    log.warning(
        "ALG-14: unmapped provenance — source=%r object_type=%r source_ref_prefix=%r; "
        "ranking at %s (%d). Add a row to the authority table.",
        provenance.source, provenance.object_type, prefix,
        UNMAPPED_AUTHORITY.value, AUTHORITY_RANK[UNMAPPED_AUTHORITY])
    return AuthorityWeight(UNMAPPED_AUTHORITY, AuthorityBasis.UNMAPPED)


__all__ = [
    "AUTHORITY_RANK",
    "LEGACY_RANK",
    "MAX_AUTHORITY_RANK",
    "OBJECT_TYPE_AUTHORITY",
    "RANK_MULTIPLIER_BP",
    "SOURCE_AUTHORITY",
    "SOURCE_OBJECT_AUTHORITY",
    "SOURCE_REF_PREFIX_AUTHORITY",
    "UNMAPPED_AUTHORITY",
    "Authority",
    "AuthorityBasis",
    "AuthorityWeight",
    "Provenance",
    "multiplier_bp_of",
    "rank_of",
    "to_legacy_rank",
    "weigh_authority",
]
