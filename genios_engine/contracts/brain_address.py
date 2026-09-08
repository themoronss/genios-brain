"""The ONE vocabulary a situation and a brain entry both speak.

**THE DEFECT THIS CLOSES.** Layer 3 held knowledge in four brains and could not decide which of it
applied to a live situation, so it applied none of it. `scripts/l3_pilot_report.py` measured the
end state on a tenant holding **6 behaviour entries, 5 organization entries and a live adaptive
lease**: `packages_with_a_brain_slice = 0` across four compiled packages. Not an empty brain — an
unaddressable one. Three independent faults, each a different spelling of the same missing idea:

1. `packs/compiler/runtime_brains._selectors` read `situation.brain_subject_keys`, and
   `grep -rn brain_subject_keys genios_engine/` returned two READERS and no writer. The selector
   meant to bind a situation to its knowledge was dead metadata.
2. A published Behaviour subject is `behavior:<metric>:<node_id>`; a correlated situation's entity
   ids are EMAIL ADDRESSES (`context/situation_bso.gather_members` groups by `actor->>'email'`).
   `_relevant` split the subject on `:` and intersected the segments with those ids. A node id and
   an email address never intersect, so the match could not fire — and the Behaviour value carried
   no `capability_id` to fall back on.
3. An Organization subject is `orgrule:<category>:<subject_type>`. None of `orgrule`, the category
   or the subject type is anything a situation knows about itself, and that value carried no
   capability either. An approved company policy could be published, versioned and governed, and
   still never reach a decision.

**WHY A VOCABULARY AND NOT THREE PATCHES.** Each fault could be patched where it was found — teach
Behaviour to key by capability, teach Organization to key by category, teach the reader a second
table. That is how one idea becomes four spellings that disagree in the fifth place nobody looked;
it is the shape of the bug already, three times over. What is actually missing is a shared answer
to one question — *what is this knowledge ABOUT* — that a producer writes and a consumer reads,
and that is a contract, so it lives here beside the other contracts rather than inside the
compiler that happens to be today's only consumer.

**THE ADDRESS IS A SET OF TOKENS, NOT A PATH.** A rule can be about a company AND a capability AND
a jurisdiction at once, and a hierarchy would force an author to pick which one it is "really"
filed under. Every dimension is emitted as its own `kind:value` token; selection is set
intersection; and a token that no situation ever emits simply never matches, which is the correct
behaviour for knowledge that is out of scope rather than an error.

**WHAT IS DELIBERATELY NOT HERE.** No wildcards, no globbing, no `*`. A token matches itself and
nothing else. `orgwide` is the ONE token that means "this tenant, everywhere", it can only be
minted by `org_scope`, and it is emitted only by knowledge whose authority is the organization
itself — an approved policy, which is org-wide by construction and useless if it must guess which
capability will need it. Behaviour and Adaptive entries may never carry it: a measured pattern and
a temporary preference are observations, and an observation that applied everywhere by default
would be indistinguishable from a rule.

**LEGACY SUBJECTS STILL RESOLVE.** Entries published before this contract carry no address, and
they are not rewritten — Layer 6 owns publication and Layer 3 never edits what it is handed.
`legacy_tokens` derives the tokens such a subject implies, so a `behavior:<metric>:<node_id>` row
written last week binds today without a backfill and without a second code path.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from genios_engine.contracts.validators import (
    freeze_mapping,
    require_sorted_unique,
    require_text,
)

#: The address vocabulary. Every token a producer may mint and every token a situation may emit is
#: one of these kinds; `require_kind` refuses anything else, so a typo is a failure at the writer
#: rather than a row that silently never matches.
#:
#: WHY EACH ONE EXISTS, since a dimension nobody can name is a dimension nobody maintains:
#:   org             the tenant. Present on every address; it is what makes cross-tenant leakage a
#:                   type error rather than a `where` clause somebody has to remember.
#:   orgwide         "this tenant, everywhere". See the module docstring — one token, one minter.
#:   domain          admin | sales | customer_support. The corpus folder the knowledge belongs to.
#:   capability      a capability id, e.g. `admin.records_and_documentation.document_control`.
#:   object          a business-object id the knowledge is about, e.g. `admin.obj.core.document`.
#:   situation       one situation id — knowledge pinned to a single live situation.
#:   situation_type  every situation of a type, e.g. `document_under_control`.
#:   node            a graph node id (`node_<hex>`). The stable entity identity.
#:   email           a lowercased email address. The identity a correlated situation actually
#:                   carries, kept as its OWN kind rather than folded into `node`: they are
#:                   resolved through different tables and an unresolved email must not read as a
#:                   node that exists.
#:   person          a graph node id known to be a person. Narrower than `node`, emitted alongside
#:                   it, so knowledge about people cannot bind to a company that shares an id
#:                   space.
#:   company         a graph node id known to be a company/organization node.
#:   jurisdiction    an ISO-3166 country code or a regulator id. Never inferred; only ever
#:                   authored. A statutory rule that does not say where it applies must not be
#:                   allowed to apply everywhere.
#:   metric          an L2 trend metric name, so a Behaviour pattern is addressable by what it
#:                   measured as well as by whom it measured.
#:   actor           the user a preference belongs to, for Adaptive leases that are per-person.
KINDS = (
    "org", "orgwide", "domain", "capability", "object", "situation", "situation_type",
    "node", "email", "person", "company", "jurisdiction", "metric", "actor",
)

#: The tenant-wide token's fixed value. `orgwide:<org_id>` rather than a bare `orgwide` so that a
#: snapshot built from two tenants' rows — which should never happen, and did once — cannot match
#: across them by accident.
ORGWIDE = "orgwide"

#: Brains whose entries may NEVER be org-wide. See the module docstring: a measurement and a
#: preference are observations, and an observation that binds everywhere by default is a rule
#: nobody approved. `require_address` refuses it rather than dropping it silently, because a
#: producer that tried is a producer with a wrong idea about what it publishes.
OBSERVATIONAL_BRAINS = frozenset({"behavior", "adaptive"})

_SEPARATOR = ":"


def require_kind(kind: str) -> str:
    """The one place a token kind is validated.

    A typo must be a refusal and not a row nothing will ever select — which is the failure mode
    already documented three times over in this module's docstring, and it looks exactly like
    working knowledge right up until a decision needed it.
    """
    text = require_text(kind, "brain address kind")
    if text not in KINDS:
        raise ValueError(f"unknown brain address kind {kind!r}; expected one of {KINDS}")
    return text


def token(kind: str, value: Any) -> str:
    """`kind:value` — the only way a token is ever spelled.

    The value is lowercased for `email` alone. Node ids are opaque and case-bearing, capability
    ids are authored lowercase already, and lowercasing an id we did not mint is how a selector
    stops matching the row it was written from. An address is an exact-match vocabulary; the one
    place case genuinely varies in the wild is the local part of an email a human typed.
    """
    normalized_kind = require_kind(kind)
    text = require_text(value, f"brain address {normalized_kind} value")
    if normalized_kind == "email":
        text = text.lower()
    if _SEPARATOR in text and normalized_kind not in {"capability", "object", "situation_type"}:
        # Capability, object and situation-type ids are dotted, never colonned; the three kinds
        # listed are exempt only because an authored id MAY legitimately carry a colon and we
        # must not refuse the corpus. Everything else with a colon in it would make the token
        # ambiguous to split, and an ambiguous token is one that matches the wrong thing.
        raise ValueError(
            f"brain address {normalized_kind} value {value!r} contains {_SEPARATOR!r}, "
            "which would make the token ambiguous")
    return f"{normalized_kind}{_SEPARATOR}{text}"


def org_scope(org_id: str) -> tuple[str, ...]:
    """The two tokens every tenant-scoped address carries: the tenant, and tenant-wide.

    The ONLY minter of `orgwide`. Knowledge that wants to apply across a tenant has to come
    through here, so "what can bind everywhere" is answerable by reading this function's callers
    rather than by grepping for a string.
    """
    return (token("org", org_id), token(ORGWIDE, org_id))


def legacy_tokens(brain: str, subject_key: str, org_id: str) -> tuple[str, ...]:
    """What an address-less subject key IMPLIES, so pre-contract rows bind without a backfill.

    Layer 6 owns publication and Layer 3 never rewrites what it is handed (`runtime_brains`'s own
    docstring), so a migration that edited `learned_brain_entries.value` in place would put Layer 3
    on the wrong side of that line for the sake of one release. This derives the same tokens at
    READ time instead, from the two subject shapes the producers actually wrote:

        behavior:<metric>:<node_id>       -> metric:<metric>, node:<node_id>
        adaptive:card_timing:<capability> -> capability:<capability>
        orgrule:<category>:<subject_type> -> orgwide:<org_id>

    The Organization case is the one that carries a judgement, and it is the judgement the
    Organization brain is FOR: a rule extracted from the tenant's own approved policy document,
    governed and human-confirmed, is a statement about the tenant. It has no narrower address to
    derive — the category (`approval`, `spend`) and the subject type are the rule's own taxonomy,
    not a business object anyone else names — and the alternative to tenant-wide is the state it is
    in today, which is unreachable. Behaviour and Adaptive are NOT given this treatment: they are
    observational (`OBSERVATIONAL_BRAINS`) and their subjects already name what they are about.
    """
    parts = [part for part in str(subject_key).split(_SEPARATOR) if part]
    if brain == "behavior" and len(parts) >= 3:
        return (token("metric", parts[1]), token("node", _SEPARATOR.join(parts[2:])))
    if brain == "adaptive" and len(parts) >= 3:
        return (token("capability", _SEPARATOR.join(parts[2:])),)
    if brain == "organization":
        return (token(ORGWIDE, org_id),)
    return ()


@dataclass(frozen=True, slots=True)
class BrainAddress:
    """What one brain entry is ABOUT, in the vocabulary a situation also speaks.

    Serialised onto the published entry's `value["address"]` by the producer, read back by
    `packs/compiler/runtime_brains`. It is part of the entry's content, so it is hashed into the
    entry's identity and changing an address mints a new version rather than silently re-aiming
    knowledge a decision already cited.
    """

    org_id: str
    brain: str
    #: The tokens, sorted and unique. Selection is `set(tokens) & set(situation tokens)`.
    tokens: tuple[str, ...] = ()
    #: Free-form provenance the compiler does not select on but a receipt must be able to print:
    #: the source document, its version, the approving human, the effective window.
    authority: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        setter = object.__setattr__
        setter(self, "org_id", require_text(self.org_id, "brain address org id"))
        setter(self, "brain", require_text(self.brain, "brain address brain"))
        tokens = require_sorted_unique(self.tokens, "brain address token")
        for item in tokens:
            kind, _, value = item.partition(_SEPARATOR)
            if not value:
                raise ValueError(f"malformed brain address token {item!r}")
            require_kind(kind)
        if self.brain in OBSERVATIONAL_BRAINS and any(
                item.startswith(f"{ORGWIDE}{_SEPARATOR}") for item in tokens):
            raise ValueError(
                f"{self.brain} entries may not be org-wide: a measurement or a preference is an "
                "observation, and an observation that binds everywhere is a rule nobody approved")
        setter(self, "tokens", tokens)
        setter(self, "authority", freeze_mapping(self.authority))

    def as_value(self) -> dict[str, Any]:
        """The mapping a producer puts on `value["address"]`."""
        return {"org_id": self.org_id, "brain": self.brain,
                "tokens": list(self.tokens), "authority": dict(self.authority)}


def build_address(*, org_id: str, brain: str, tokens: Iterable[str] = (),
                  authority: Mapping[str, Any] | None = None) -> BrainAddress:
    """`BrainAddress` with the tenant token always present, so no producer can forget it."""
    every = [token("org", org_id), *tokens]
    return BrainAddress(org_id=org_id, brain=brain, tokens=tuple(every),
                        authority=authority or {})


def address_tokens(value: Mapping[str, Any] | None) -> tuple[str, ...]:
    """Read the tokens back off a published `value`, tolerating every absent shape.

    Returns `()` for a value with no address, a malformed address, or an address whose `tokens` is
    not a list of strings. Tolerant on purpose: this runs against rows Layer 6 published under an
    older contract, and a compile that raised on one of them would cost the tenant every OTHER
    piece of knowledge in the same snapshot. An unreadable address means "no address", which the
    caller then resolves through `legacy_tokens`.
    """
    if not isinstance(value, Mapping):
        return ()
    address = value.get("address")
    if not isinstance(address, Mapping):
        return ()
    raw = address.get("tokens")
    if isinstance(raw, str) or not isinstance(raw, Sequence):
        return ()
    out: list[str] = []
    for item in raw:
        if not isinstance(item, str) or _SEPARATOR not in item:
            continue
        kind, _, rest = item.partition(_SEPARATOR)
        if kind in KINDS and rest:
            out.append(item)
    return tuple(sorted(set(out)))


def selection_basis(entry_tokens: Iterable[str], situation_tokens: Iterable[str]) \
        -> tuple[str, ...]:
    """WHICH tokens matched — the receipt, not the boolean.

    A package that says "this policy applied" and cannot say why is a package an operator has to
    take on faith, and taking Layer 3 on faith is what produced a J5 row reading zero for three
    months. Returned sorted so a receipt is stable across compiles.
    """
    return tuple(sorted(set(entry_tokens) & set(situation_tokens)))


__all__ = [
    "BrainAddress",
    "KINDS",
    "ORGWIDE",
    "OBSERVATIONAL_BRAINS",
    "address_tokens",
    "build_address",
    "legacy_tokens",
    "org_scope",
    "require_kind",
    "selection_basis",
    "token",
]
