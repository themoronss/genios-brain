"""ALG-11 · L1.5.4 — the entity canonicalizer. *"AWS" and "Amazon Web Services" are one vendor.*

One question, answered from frozen data and string equality: **what is this mention probably
about?** An enterprise names one company five ways in a week — ``aws.amazon.com`` in an address,
"AWS" in Slack, "Amazon Web Services" in a contract, "Amazon Web Services, Inc." in an invoice,
"amazon web services" in a CRM export. Until something folds those together, every rule that
asks "what is happening with our AWS spend?" sees a fifth of the truth.

THE SPEC THIS UNIT WAS BUILT AGAINST DID NOT EXIST
--------------------------------------------------
Doc 05's component map (line 30) lists ``L1.5.4 | Entity Canonicalizer | ALG-11 | 2 units | W2``
and then never writes the units: the document jumps from L1.5.3 (Currency Normalizer) straight
to L1.5.5 (Conflict Detector). Doc 00's algorithm map has ALG-11's row — *"Entity
canonicalization, L1.5.4, rule cascade, doc 05"* — pointing at a section that is not there.
Two units promised, zero specified; by doc 00's own rule a blank template field is a defect in
the plan, not a licence to improvise. The two unit specs were therefore derived from the four
sources that DO constrain this unit, and are written out in the build report:

* doc 00 §4 MAP B, row 1: *entity resolution ("AWS" == "Amazon Web Services") -> **NO**
  embeddings -> instead: deterministic alias + domain matching (L1.5.4)*. That row is the
  entire algorithm brief. "Rule cascade" (doc 00 §6) is its shape.
* doc 08 C-04: ``canonical_hint: str | None  # L1.5.4 fills this; L2 is authoritative``.
* ``contracts/extraction.py``'s own comment on the field: a hint *"is a guess ... and it is NOT
  authoritative. L2 owns identity; a hint that hardened into a decision here would merge two
  vendors on a shared substring and do it invisibly, three layers below the place that is
  supposed to resolve them."*
* doc 05 L1.5.0-U1 (ALG-22), which consumes the output: ``subject_key`` step 3 is
  ``f"entity:{canonical_hint}:{field_family}"``. That is what forces the hint to be a **stable,
  bare, replayable string** — a hint that changes spelling between runs silently splits one
  subject into two, and conflict detection stops comparing claims that are about the same thing.

A HINT, AND THE TYPE SAYS SO
----------------------------
``propose_canonical`` returns a ``CanonicalProposal``. Every noun in that type is a proposal
noun: ``hint``, ``basis``, ``alternatives``. There is deliberately no entity id, no node id, no
``resolved``/``merged`` flag and no boolean that a caller could read as permission — the type
cannot express an identity assertion, so no call site can accidentally make one. The single
write path onto a claim is ``CanonicalProposal.apply_to``, and it writes exactly one field.
L2's ``context/identity.py`` remains the only place a real merge happens, and even there a
collision writes a PROPOSAL for a human. This unit is one layer further from that authority,
not closer to it.

The other half of "never assert identity" is refusing to answer when the data is ambiguous. If
two canonical entities claim the same alias key, this returns ``hint=None`` with both
candidates in ``alternatives`` — the same law L2 obeys (*"AMBIGUITY IS NOT A MATCH"*). Picking
the first row would be exactly the invisible merge the contract's comment warns about.

WHY LOOKUP AND NOT SIMILARITY
-----------------------------
MAP B is a decision, not a preference: no embeddings in Layer 1 v2, because a similarity score
is not a business conclusion and an entity resolved by cosine distance cannot name the rule
that resolved it. So fuzziness lives entirely in how a key is DERIVED — lowercase, fold
punctuation, collapse whitespace, drop legal-form tokens, take a domain's label — and never in
how two keys are COMPARED. Comparison is ``==``, forever. That is what makes "Acme, Inc." and
"Acme Inc" converge while "Apex Legal" and "Apex Logistics" stay apart: they differ by a whole
word, and no threshold anywhere can be nudged until they merge.

The derivation primitives are ``platform/identity.py``'s — ``company_slug``, ``domain_root``,
``norm_email``, ``person_name_key`` — reused rather than re-written. They are pure, they are
already the definition every writer in Layer 2 uses to mint keys, and a second copy here would
guarantee that L1's hint and L2's lookup key drift apart, at which point the hint stops being
useful to the layer it exists to help.

CLOSURE, AND WHY THE CASCADE RE-CHECKS THE ALIAS TABLE TWICE
-------------------------------------------------------------
The cascade is closed under re-application: feeding a hint back in as a surface form yields the
same hint. That is not decoration — an ``ExtractionResult`` is cached permanently and replayed,
a subject_key derived from a hint must be stable across those replays, and a canonicalizer that
moved a value on second application would make "the same real-world subject produces the same
key" (ALG-22) false. Closure is why the domain-label rule looks the alias table up again on the
label it just computed: without that, ``acme.io -> "acme"`` and then ``"acme" -> "acme corp"``
would be two different answers for one mention.

FAMILIES, AND THE ONE MERGE THAT IS THE WHOLE POINT
---------------------------------------------------
Lookup is namespaced by entity FAMILY, for the reason ``context/identity.py`` gives about its
own ``canon`` namespace: *"a project called Acme must not collide with the customer called
Acme"*. ``organization`` and ``vendor`` deliberately share the ``org`` family, because "AWS"
arrives typed ``vendor`` from one message and "Amazon Web Services" typed ``organization`` from
the next, and giving them different hints would defeat the unit's stated purpose. The family
travels on the proposal so a consumer that needs a namespaced key can build one; the hint
itself stays bare, because ALG-22 already prefixes it and a hint that carried its own prefix
would no longer be idempotent.

PURE. No clock (nothing here ages), no model, no database, no network, and no float — there are
no scores in this unit at all, and that is on purpose: a similarity number is precisely what
MAP B forbids. The alias table is DATA — a frozen module constant, or one the caller passes in.
It is never a live lookup: a hint that depended on what the database happened to hold at 3am
would not replay, and replayability is the only reason a cached extraction can be audited.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType

from genios_engine.contracts.extraction import EntityMention
from genios_engine.platform.identity import (company_slug, domain_root, norm_email,
                                             person_name_key)

# ======================================================================================
# Families — the lookup namespaces
# ======================================================================================


class EntityFamily(str, Enum):
    """The namespace a key is looked up in.

    Coarser than doc 04's ``entity_type`` on purpose in exactly one place: ``organization``
    and ``vendor`` are the same family, because the same company is typed both ways by two
    different messages and the unit exists to fold those together. Everything else keeps its
    own namespace, so a project named "Acme" and the customer named "Acme" never contend for
    one alias key and therefore never raise a false ambiguity against each other.
    """

    PERSON = "person"
    ORG = "org"
    PRODUCT = "product"
    PROJECT = "project"
    DOCUMENT = "document"
    #: An ``entity_type`` outside doc 04's closed set. It still gets a key (totality: an
    #: unknown kind is never a crash), but it lands in a namespace the shipped table never
    #: populates, so an unrecognised type can never pick up somebody else's canonical name.
    OTHER = "other"


#: doc 04's ENTITY_TYPE -> family. The only many-to-one row is org/vendor, and it is the row
#: the unit was built for.
ENTITY_TYPE_FAMILY: Mapping[str, EntityFamily] = MappingProxyType({
    "person": EntityFamily.PERSON,
    "organization": EntityFamily.ORG,
    "vendor": EntityFamily.ORG,
    "product": EntityFamily.PRODUCT,
    "project": EntityFamily.PROJECT,
    "document": EntityFamily.DOCUMENT,
})


def _family_of(entity_type: str | None) -> EntityFamily:
    """Total: any string maps to a family, an unrecognised one to ``OTHER``."""
    return ENTITY_TYPE_FAMILY.get(str(entity_type or "").strip().lower(), EntityFamily.OTHER)


# ======================================================================================
# L1.5.4-U1 · key derivation
# ======================================================================================


class KeyKind(str, Enum):
    """What the surface form turned out to BE, which decides how it is normalised."""

    #: An address: "priya@acme.io", "Priya <priya+cal@acme.io>", "mailto:billing@aws.amazon.com".
    EMAIL = "email"
    #: A bare host or URL: "acme.io", "https://aws.amazon.com/pricing", "www.acme.co.uk".
    HOST = "host"
    #: Anything else — a written name. The overwhelmingly common case.
    NAME = "name"
    #: Nothing normalisable survived (empty, or punctuation only).
    NONE = "none"


#: Final labels that make a dotted string a HOST rather than a name. Deliberately a short,
#: frozen list and not the IANA root zone: the failure of an unlisted TLD is that "acme.zw"
#: degrades to the NAME key "acme zw", which is conservative — it can never merge two things
#: that a host match would have merged. The failure of the opposite policy is loud and real:
#: "Node.js" and "Sched.io" are product names, and treating every dotted token as a host would
#: canonicalize the product "Node.js" to the company label "node".
#:
#: An address is exempt from this check. The "@" is the proof; a mail host needs no allowlist.
_HOST_TLDS: frozenset[str] = frozenset({
    "com", "net", "org", "edu", "gov", "int", "mil", "biz", "info",
    "io", "ai", "co", "dev", "app", "cloud", "tech", "xyz", "me", "sh", "so",
    "in", "uk", "us", "ca", "au", "nz", "de", "fr", "es", "it", "nl", "be", "ch",
    "se", "no", "fi", "dk", "pl", "pt", "ie", "at", "cz", "ru", "jp", "cn", "kr",
    "sg", "hk", "il", "ae", "za", "br", "mx", "ar", "cl", "eu",
})

#: Free/consumer mail hosts. A person's address at one of these is still that person's key —
#: it is the strongest identity string we have for them. But the DOMAIN of such an address
#: says nothing about a company, and "rohit@gmail.com" typed as an organization must not
#: canonicalize an org to "gmail". No hint at all is the correct answer there.
CONSUMER_EMAIL_DOMAINS: frozenset[str] = frozenset({
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "yahoo.co.uk",
    "hotmail.com", "outlook.com", "live.com", "msn.com", "aol.com",
    "icloud.com", "me.com", "mac.com", "proton.me", "protonmail.com",
    "gmx.com", "gmx.de", "zoho.com", "yandex.com", "mail.com", "rediffmail.com",
    "qq.com", "163.com", "126.com",
})

_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$")


@dataclass(frozen=True, slots=True)
class EntityKey:
    """L1.5.4-U1's answer: the comparison key a surface form reduces to, and how.

    Carries the ``host`` separately from the ``key`` because the cascade needs both: the full
    host is what an alias table registers ("aws.amazon.com"), while the key is the label a
    host reduces to when no table knows it ("acme.io" -> "acme").
    """

    family: EntityFamily
    kind: KeyKind
    #: The normalised comparison key, or None when nothing survived normalisation.
    key: str | None
    #: The normalised host, present only for EMAIL and HOST kinds.
    host: str | None = None


def _clean_host(candidate: str) -> str | None:
    """Trim a host out of whatever surrounded it. Path, query, port, ``www.``, stray dots."""
    host = candidate.split("/", 1)[0].split("?", 1)[0].split("#", 1)[0]
    host = host.split(":", 1)[0].strip().strip(".").strip()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def _is_hostlike(host: str, *, require_known_tld: bool) -> bool:
    parts = host.split(".")
    if len(parts) < 2 or not all(_LABEL.match(part) for part in parts):
        return False
    tld = parts[-1]
    if not tld.isalpha() or len(tld) < 2:
        return False
    return tld in _HOST_TLDS if require_known_tld else True


def _locate(surface_form: str) -> tuple[KeyKind, str | None, str | None]:
    """(kind, host, email) — the shape-detection half of U1, before any normalisation."""
    text = surface_form.strip()
    if "<" in text and ">" in text and text.index("<") < text.rindex(">"):
        inner = text[text.index("<") + 1:text.rindex(">")].strip()
        if inner:
            text = inner
    lowered = text.lower()
    if lowered.startswith("mailto:"):
        lowered = lowered[7:].strip()
    if "://" in lowered:
        lowered = lowered.split("://", 1)[1]
    if "@" in lowered:
        local, _, raw_host = lowered.rpartition("@")
        host = _clean_host(raw_host)
        local = local.strip()
        if local and host and " " not in local and _is_hostlike(host, require_known_tld=False):
            return KeyKind.EMAIL, host, f"{local}@{host}"
        return KeyKind.NAME, None, None
    host = _clean_host(lowered)
    if host and _is_hostlike(host, require_known_tld=True):
        return KeyKind.HOST, host, None
    return KeyKind.NAME, None, None


def derive_key(surface_form: str, *, entity_type: str) -> EntityKey:
    """**L1.5.4-U1.** Reduce one written surface form to its comparison key. No table involved.

    This is the only place fuzziness is allowed to live: case is folded, punctuation becomes
    whitespace, whitespace collapses, legal-form tokens ("Inc.", "Pvt Ltd") are dropped, a
    ``+tag`` is stripped from an address, a URL becomes its host. Everything downstream then
    compares keys with ``==``.

    Deterministic and total — no input raises, and an unusable one returns ``key=None`` rather
    than a guess. It asserts nothing about identity: two real companies can genuinely reduce to
    one key, which is exactly why the caller treats the result as a candidate.
    """
    family = _family_of(entity_type)
    raw = (surface_form or "").strip()
    if not raw:
        return EntityKey(family=family, kind=KeyKind.NONE, key=None)

    kind, host, email = _locate(raw)

    if family is EntityFamily.PERSON:
        # A person IS their address; a person's employer domain is not a person. So the host
        # is never promoted to this person's key, and a bare host typed `person` is read as
        # the odd name it is rather than silently becoming the company.
        if kind is KeyKind.EMAIL and email:
            key = norm_email(email)
            if key:
                return EntityKey(family=family, kind=KeyKind.EMAIL, key=key, host=host)
        name_key = person_name_key(raw)
        return EntityKey(family=family,
                         kind=KeyKind.NAME if name_key else KeyKind.NONE, key=name_key)

    if kind in (KeyKind.EMAIL, KeyKind.HOST) and host:
        return EntityKey(family=family, kind=kind, key=domain_root(host), host=host)

    slug = company_slug(raw)
    return EntityKey(family=family, kind=KeyKind.NAME if slug else KeyKind.NONE, key=slug)


# ======================================================================================
# The alias table — data, frozen, never a live lookup
# ======================================================================================


@dataclass(frozen=True, slots=True)
class AliasEntry:
    """One canonical entity and every deterministic key it answers to.

    ``canonical`` must already BE its own derived key (lowercase, no punctuation, no legal
    suffix). ``AliasTable.build`` enforces that rather than normalising silently, because a
    canonical that does not survive ``derive_key`` unchanged breaks closure: the hint it
    produces would resolve to something else on the next pass.
    """

    canonical: str
    #: doc 04 entity_type; decides which namespace the entry's keys are registered in.
    entity_type: str
    #: Written forms, in any casing/punctuation — they are put through ``derive_key`` here.
    aliases: tuple[str, ...] = ()
    #: Full hosts this entity owns: "aws.amazon.com", not "amazon.com". Subdomains resolve to
    #: the longest registered suffix, so registering a parent would silently claim its
    #: siblings — "amazon.com" would make the retailer answer to the cloud vendor's name.
    domains: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class AliasHit:
    """A table lookup's answer. ``canonical`` and ``alternatives`` are mutually exclusive."""

    canonical: str | None = None
    #: Populated only when more than one canonical claims the key: every claimant, sorted.
    alternatives: tuple[str, ...] = ()

    @property
    def ambiguous(self) -> bool:
        return bool(self.alternatives)


_MISS = AliasHit()


@dataclass(frozen=True, slots=True)
class AliasTable:
    """Frozen indexes over a set of ``AliasEntry``. Built once; read with string equality.

    Two authoring mistakes are treated very differently, and the difference is deliberate:

    * A **malformed entry** (a canonical that is not its own key, a domain with no dot, an
      alias that normalises to nothing) raises at build time. Those are programming errors in
      a constant, and the loudest possible failure is the cheapest one.
    * A **collision** between two entries does not raise. It is recorded, and every lookup of
      the contested key answers "ambiguous, here are the claimants". A caller-supplied table
      arrives at runtime, and refusing to answer one key is correct where refusing to start is
      not.
    """

    entries: tuple[AliasEntry, ...]
    by_name: Mapping[tuple[EntityFamily, str], str]
    by_domain: Mapping[tuple[EntityFamily, str], str]
    ambiguous_names: Mapping[tuple[EntityFamily, str], tuple[str, ...]]
    ambiguous_domains: Mapping[tuple[EntityFamily, str], tuple[str, ...]]
    #: Human-readable diagnostics, "name:org:acme" / "domain:org:acme.io", sorted.
    conflicts: tuple[str, ...] = field(default=())

    @classmethod
    def build(cls, entries: Iterable[AliasEntry]) -> AliasTable:
        rows = tuple(entries)
        names: dict[tuple[EntityFamily, str], set[str]] = {}
        domains: dict[tuple[EntityFamily, str], set[str]] = {}

        for entry in rows:
            canonical = (entry.canonical or "").strip()
            if not canonical:
                raise ValueError("alias entry has no canonical name")
            family = _family_of(entry.entity_type)
            if family is EntityFamily.OTHER:
                raise ValueError(
                    f"alias entry {canonical!r} has entity_type {entry.entity_type!r}, "
                    "which is outside doc 04's ENTITY_TYPE set")
            self_key = derive_key(canonical, entity_type=entry.entity_type).key
            if self_key != canonical:
                raise ValueError(
                    f"canonical {canonical!r} is not its own derived key ({self_key!r}); "
                    "a canonical that renormalises breaks hint idempotence")
            # The canonical answers to itself. This is what closes the cascade.
            names.setdefault((family, canonical), set()).add(canonical)
            for alias in entry.aliases:
                alias_key = derive_key(alias, entity_type=entry.entity_type).key
                if not alias_key:
                    raise ValueError(
                        f"alias {alias!r} of {canonical!r} normalises to nothing")
                names.setdefault((family, alias_key), set()).add(canonical)
            for domain in entry.domains:
                host = _clean_host(str(domain).strip().lower()) or ""
                if not host or not _is_hostlike(host, require_known_tld=False):
                    raise ValueError(
                        f"domain {domain!r} of {canonical!r} is not a host")
                domains.setdefault((family, host), set()).add(canonical)

        conflicts: list[str] = []
        resolved_names: dict[tuple[EntityFamily, str], str] = {}
        ambiguous_names: dict[tuple[EntityFamily, str], tuple[str, ...]] = {}
        for key, claimants in names.items():
            if len(claimants) == 1:
                resolved_names[key] = next(iter(claimants))
            else:
                ambiguous_names[key] = tuple(sorted(claimants))
                conflicts.append(f"name:{key[0].value}:{key[1]}")

        resolved_domains: dict[tuple[EntityFamily, str], str] = {}
        ambiguous_domains: dict[tuple[EntityFamily, str], tuple[str, ...]] = {}
        for key, claimants in domains.items():
            if len(claimants) == 1:
                resolved_domains[key] = next(iter(claimants))
            else:
                ambiguous_domains[key] = tuple(sorted(claimants))
                conflicts.append(f"domain:{key[0].value}:{key[1]}")

        return cls(entries=rows,
                   by_name=MappingProxyType(resolved_names),
                   by_domain=MappingProxyType(resolved_domains),
                   ambiguous_names=MappingProxyType(ambiguous_names),
                   ambiguous_domains=MappingProxyType(ambiguous_domains),
                   conflicts=tuple(sorted(conflicts)))

    def lookup_name(self, family: EntityFamily, key: str | None) -> AliasHit:
        if not key:
            return _MISS
        contested = self.ambiguous_names.get((family, key))
        if contested:
            return AliasHit(alternatives=contested)
        canonical = self.by_name.get((family, key))
        return AliasHit(canonical=canonical) if canonical else _MISS

    def lookup_domain(self, family: EntityFamily, host: str | None) -> AliasHit:
        if not host:
            return _MISS
        contested = self.ambiguous_domains.get((family, host))
        if contested:
            return AliasHit(alternatives=contested)
        canonical = self.by_domain.get((family, host))
        return AliasHit(canonical=canonical) if canonical else _MISS


#: The shipped table. Small on purpose: every row is an alias pair we have actually seen split
#: one vendor into two in customer data, and a table nobody can audit is a table that merges
#: something it should not. It is a CONSTANT, evaluated at import from literals — never read
#: from a database, because a hint that depends on today's rows does not replay tomorrow.
DEFAULT_ALIAS_ENTRIES: tuple[AliasEntry, ...] = (
    AliasEntry(canonical="amazon web services", entity_type="vendor",
               aliases=("AWS", "aws", "Amazon Web Services", "Amazon Web Services, Inc.",
                        "AWS Inc"),
               domains=("aws.amazon.com", "awscloud.com")),
    AliasEntry(canonical="google cloud platform", entity_type="vendor",
               aliases=("GCP", "Google Cloud", "Google Cloud Platform"),
               domains=("cloud.google.com",)),
    AliasEntry(canonical="microsoft azure", entity_type="vendor",
               aliases=("Azure", "MS Azure", "Microsoft Azure"),
               domains=("azure.microsoft.com", "azure.com")),
    AliasEntry(canonical="google workspace", entity_type="vendor",
               aliases=("GSuite", "G Suite", "Google Apps", "Google Workspace"),
               domains=("workspace.google.com",)),
    AliasEntry(canonical="salesforce", entity_type="vendor",
               aliases=("SFDC", "Salesforce", "Salesforce.com", "Salesforce, Inc."),
               domains=("salesforce.com", "force.com")),
    AliasEntry(canonical="hubspot", entity_type="vendor",
               aliases=("HubSpot", "Hubspot, Inc."),
               domains=("hubspot.com",)),
    AliasEntry(canonical="stripe", entity_type="vendor",
               aliases=("Stripe", "Stripe, Inc."),
               domains=("stripe.com",)),
    AliasEntry(canonical="slack", entity_type="vendor",
               aliases=("Slack", "Slack Technologies"),
               domains=("slack.com",)),
)

DEFAULT_ALIAS_TABLE: AliasTable = AliasTable.build(DEFAULT_ALIAS_ENTRIES)


# ======================================================================================
# L1.5.4-U2 · the rule cascade
# ======================================================================================


class HintBasis(str, Enum):
    """Which rule of the cascade answered — the explanation that travels with the hint.

    Recorded because a hint with no basis is unreviewable: "why did GeniOS think this invoice
    was about Amazon Web Services?" must be answerable without re-running anything, and the
    honest answers ("the alias table says so" vs "nothing matched, so this is just the name
    folded") are worth very different amounts to a human reading a card.
    """

    #: An explicit alias hit. The strongest rule: a human wrote this equivalence down.
    ALIAS_TABLE = "alias_table"
    #: A registered domain (or a subdomain of one) hit.
    DOMAIN_TABLE = "domain_table"
    #: A person's address, normalised. The strongest key a person has.
    EMAIL_IDENTITY = "email_identity"
    #: An unregistered domain reduced to its label: "acme.io" -> "acme".
    DOMAIN_LABEL = "domain_label"
    #: Nothing matched; the hint is the surface form's own normalised key.
    NORMALISED_FORM = "normalised_form"
    #: More than one canonical claims the key. NO hint — see ``alternatives``.
    AMBIGUOUS = "ambiguous"
    #: Nothing usable: an empty form, punctuation only, or a company mention whose only
    #: evidence was a consumer mail host.
    NO_BASIS = "no_basis"


#: The bases that produce a hint. The complement (AMBIGUOUS, NO_BASIS) always carries None.
HINTED_BASES: frozenset[HintBasis] = frozenset({
    HintBasis.ALIAS_TABLE, HintBasis.DOMAIN_TABLE, HintBasis.EMAIL_IDENTITY,
    HintBasis.DOMAIN_LABEL, HintBasis.NORMALISED_FORM,
})


@dataclass(frozen=True, slots=True)
class CanonicalProposal:
    """L1.5.4-U2's answer: a **proposal**, and nothing this type holds can be read as more.

    There is no entity id here, and no flag a caller could take as authority to merge. The
    only thing it can do to a claim is ``apply_to``, which writes ``canonical_hint`` and
    nothing else. L2 (``context/identity.py``) owns identity; this is the layer that hands L2
    a better-shaped question.
    """

    #: The proposed canonical name — bare, lowercase, stable across replays. None when the
    #: cascade refused to answer.
    hint: str | None
    basis: HintBasis
    family: EntityFamily
    #: The derived comparison key the cascade started from, kept for audit.
    key: str | None = None
    #: Every canonical that claimed the key, when more than one did. Empty otherwise.
    alternatives: tuple[str, ...] = ()

    def apply_to(self, mention: EntityMention, *, overwrite: bool = False) -> EntityMention:
        """Return a NEW mention carrying this hint. ``surface_form`` is never touched.

        The surface form is testimony — the string a human typed is what a human can check —
        so canonicalization adds a field beside it and never rewrites it. An existing hint is
        left alone by default: a value this unit did not write is not this unit's to discard.
        """
        if mention.canonical_hint is not None and not overwrite:
            return mention
        if self.hint is None:
            return mention
        return mention.model_copy(update={"canonical_hint": self.hint})


def _host_suffixes(host: str) -> tuple[str, ...]:
    """"eu.aws.amazon.com" -> that, "aws.amazon.com", "amazon.com". Longest first.

    Longest-first is the whole safety property: a subdomain resolves to the most specific
    registered host, so registering "aws.amazon.com" claims its subdomains and never claims
    "amazon.com" itself.
    """
    parts = host.split(".")
    return tuple(".".join(parts[index:]) for index in range(len(parts) - 1))


def _from_hit(hit: AliasHit, entity_key: EntityKey, basis: HintBasis) -> CanonicalProposal:
    if hit.ambiguous:
        return CanonicalProposal(hint=None, basis=HintBasis.AMBIGUOUS,
                                 family=entity_key.family, key=entity_key.key,
                                 alternatives=hit.alternatives)
    return CanonicalProposal(hint=hit.canonical, basis=basis,
                             family=entity_key.family, key=entity_key.key)


def _none(entity_key: EntityKey) -> CanonicalProposal:
    return CanonicalProposal(hint=None, basis=HintBasis.NO_BASIS,
                             family=entity_key.family, key=entity_key.key)


def propose_canonical(mention: EntityMention, *,
                      table: AliasTable = DEFAULT_ALIAS_TABLE) -> CanonicalProposal:
    """**L1.5.4-U2 (ALG-11).** The rule cascade: first match wins, ambiguity wins over both.

    For a PERSON:
      1. an address -> the alias table, else the normalised address itself (EMAIL_IDENTITY);
      2. otherwise the normalised name -> the alias table, else itself (NORMALISED_FORM).
      A person's employer domain is never consulted: a person is not their company.

    For everything else:
      1. a host (from an address or a URL), longest suffix first -> DOMAIN_TABLE;
      2. a consumer mail host -> NO hint, because a free mail domain names no company;
      3. the host's label, re-checked against the alias table -> ALIAS_TABLE / DOMAIN_LABEL;
      4. the normalised name -> the alias table -> ALIAS_TABLE, else NORMALISED_FORM;
      5. nothing normalisable -> NO hint.

    Total (no input raises), deterministic (same mention + same table -> same proposal),
    order-free (no state carries between calls, so a batch canonicalizes identically in any
    order) and closed (proposing on a hint returns that hint). It never mutates the mention;
    the write is ``CanonicalProposal.apply_to``.
    """
    entity_key = derive_key(mention.surface_form, entity_type=mention.entity_type)
    family = entity_key.family

    if family is EntityFamily.PERSON:
        if entity_key.key is None:
            return _none(entity_key)
        hit = table.lookup_name(family, entity_key.key)
        if hit.canonical or hit.ambiguous:
            return _from_hit(hit, entity_key, HintBasis.ALIAS_TABLE)
        basis = (HintBasis.EMAIL_IDENTITY if entity_key.kind is KeyKind.EMAIL
                 else HintBasis.NORMALISED_FORM)
        return CanonicalProposal(hint=entity_key.key, basis=basis,
                                 family=family, key=entity_key.key)

    if entity_key.host:
        for candidate in _host_suffixes(entity_key.host):
            hit = table.lookup_domain(family, candidate)
            if hit.canonical or hit.ambiguous:
                return _from_hit(hit, entity_key, HintBasis.DOMAIN_TABLE)
        # Every suffix, not just the last two labels: "mail.yahoo.co.uk" is a consumer host
        # and its last two labels are "co.uk", which is a public suffix and not a mailbox
        # provider. Walking the same suffix ladder the table lookup walks is what makes the
        # guard hold for compound TLDs without shipping a public-suffix list.
        if any(suffix in CONSUMER_EMAIL_DOMAINS
               for suffix in _host_suffixes(entity_key.host)):
            return _none(entity_key)
        if entity_key.key is None:
            return _none(entity_key)
        hit = table.lookup_name(family, entity_key.key)
        if hit.canonical or hit.ambiguous:
            return _from_hit(hit, entity_key, HintBasis.ALIAS_TABLE)
        return CanonicalProposal(hint=entity_key.key, basis=HintBasis.DOMAIN_LABEL,
                                 family=family, key=entity_key.key)

    if entity_key.key is None:
        return _none(entity_key)
    hit = table.lookup_name(family, entity_key.key)
    if hit.canonical or hit.ambiguous:
        return _from_hit(hit, entity_key, HintBasis.ALIAS_TABLE)
    return CanonicalProposal(hint=entity_key.key, basis=HintBasis.NORMALISED_FORM,
                             family=family, key=entity_key.key)


def fill_canonical_hints(mentions: Sequence[EntityMention], *,
                         table: AliasTable = DEFAULT_ALIAS_TABLE,
                         overwrite: bool = False) -> tuple[EntityMention, ...]:
    """U2's seam: the mentions of one extraction, each carrying its proposed hint.

    Pure wiring over ``propose_canonical`` — it makes no decision of its own. Returns new
    objects; the input mentions are never mutated, because an ``ExtractionResult`` is cached
    and replayed and a validator that edits its input in place makes a replay differ from a
    first run.
    """
    return tuple(propose_canonical(mention, table=table).apply_to(mention,
                                                                  overwrite=overwrite)
                 for mention in mentions)
