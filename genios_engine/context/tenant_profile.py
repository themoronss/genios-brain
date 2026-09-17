"""What KIND of company this is, and who is reading — declared once, stored as facts.

Every card this product builds is answered differently depending on five things the system does
not currently know: what kind of company this is, what category it sells into, who the reader is,
what they are answerable for, and which numbers they are judged on. The authored corpus already
has a mechanism for the first two — `verticals/`, `models/`, `offerings/`, resolved
`vertical -> model -> canonical` — and every tenant reaches it holding an empty list, so every
tenant reads the identical canonical text.

THIS MODULE IS THE INPUT THAT MECHANISM NEVER HAD. It does three things and refuses to do a
fourth:

  * it reads the corpus to learn WHICH categories and personas exist — the vocabulary is the
    corpus, never a list maintained beside it;
  * it turns a declaration into the graph facts that record it, on the tenant node;
  * it turns those facts into the `variant_ids` Layer 3 already knows how to resolve.

WHAT IT REFUSES: it does not INFER. Measured on the pilot 2026-09-16, the graph holds no
self-description to infer from — `company.industry` has 3 rows and they describe counterparties,
and the only other candidate is `thread.objective`, free prose whose 236 values are unique to
their threads by construction. Matching those to a category means keyword rules tuned on one
tenant's vocabulary, which is the failure this layer exists to avoid. A category nobody declared
stays absent, and absent is a state the whole stack already handles: the compile falls through to
canonical exactly as it does today.

`party.role` IS NOT THIS. That field is about the COUNTERPARTY and holds free prose —
`organiser`, `Managing Partner`, `ex-Israeli Military Intelligence`, `Architect of The Unstuck
Entrepreneur`. It answers "what are they to us". This answers "what are we", which nothing has
ever asked.

THE THREE-WAY DRIFT THIS CLOSES. A role name appears in the vocabulary, in a corpus folder
name, and in `l3_activation.variant_ids`. If any two disagree the variant resolves to nothing and
the card falls back to canonical doctrine silently — the same shape as the overlay bug that made
one whole corpus unreachable. So the vocabulary is not maintained here at all: it is READ from the
corpus, and `undeclared()` names anything asked for that no corpus declares.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from sqlalchemy import text

from genios_engine.platform.corpus import corpus_root

#: `{axis: directory}`. The three that exist plus the one this work adds. An axis is a QUESTION
#: about the tenant, and each is answered separately: how the work is run (`models`), what kind of
#: company it is (`verticals`), what it sells (`offerings`), who is reading (`personas`).
VARIANT_AXES: dict[str, str] = {
    "model": "models",
    "vertical": "verticals",
    "offering": "offerings",
    # `role` and NOT `persona`: `objects/core/persona.yaml` already exists in the Sales corpus and
    # means a BUYER persona. One word with two meanings in one corpus is the collision that
    # `commitment` (pipeline node vs reading anchor) and `party.role` (the counterparty vs our own
    # team) have each already cost this project a day.
    "role": "roles",
}

#: The tenant-node fields a declaration writes. Each value is paired with its own `_basis`, the
#: same shape `commitment.owner`/`commitment.owner_basis` already uses one layer down — so a
#: reader can always tell a thing somebody stated from a thing the system assumed.
CATEGORY_FIELD = "org.category"
CATEGORY_BASIS_FIELD = "org.category_basis"
#: `org.reader_role`, not `org.role`: `orgs.role` is a PERMISSION column (admin /
#: member) and `party.role` is free prose about a COUNTERPARTY. Three different
#: questions; three different names.
ROLE_FIELD = "org.reader_role"
ROLE_BASIS_FIELD = "org.reader_role_basis"

#: Only one of these is ever written by this module. There is no `inferred` arm, and that is the
#: point — see WHAT IT REFUSES above. `unknown` exists for a declaration that was recorded before
#: anyone asked who made it, which is a real state on a backfilled row and not a licence to guess.
BASIS_DECLARED = "declared"
BASIS_UNKNOWN = "unknown"


def tenant_key(org_id: str) -> str:
    """The tenant node's canonical key. Imported rather than re-spelled where possible; duplicated
    here only because `context.periodic` owns the writer and importing it would make this module
    depend on the periodic pass to answer a question about identity."""
    return f"tenant:{org_id}"


@lru_cache(maxsize=8)
def _axis_entries(axis: str) -> tuple[tuple[str, str, str], ...]:
    """`(slug, domain_folder, declared_id)` for every document on one axis, across every corpus.

    Read from disk, sorted, and cached — the corpus is immutable within a process. A folder with
    no file of the expected name, a file that will not parse, and a document with no
    `identity.id` are each skipped by themselves: ONE BAD BRANCH MUST NOT HIDE THE OTHERS, the
    same rule `platform/corpus.authored_domains` keeps one level up.
    """
    directory = VARIANT_AXES.get(axis)
    if directory is None:
        return ()
    filename = f"{axis}.yaml"
    found: list[tuple[str, str, str]] = []
    try:
        root = corpus_root()
        domains = sorted(p for p in root.iterdir()
                         if p.is_dir() and not p.name.startswith("_"))
    except OSError:
        return ()
    for domain_root in domains:
        axis_root = domain_root / directory
        if not axis_root.is_dir():
            continue
        for branch in sorted(p for p in axis_root.iterdir() if p.is_dir()):
            document = branch / filename
            if not document.is_file():
                continue
            try:
                import yaml

                data = yaml.safe_load(document.read_text()) or {}
            except Exception:      # noqa: BLE001 — one bad branch, not the whole axis
                continue
            if not isinstance(data, dict):
                continue
            declared = str((data.get("identity") or {}).get("id") or "").strip()
            if declared:
                found.append((branch.name, domain_root.name, declared))
    return tuple(sorted(found))


def declared(axis: str) -> tuple[str, ...]:
    """Every value this axis offers, as the slugs a declaration may name. The VOCABULARY."""
    return tuple(sorted({slug for slug, _domain, _id in _axis_entries(axis)}))


def categories() -> tuple[str, ...]:
    """What kinds of company the corpus can speak to. Group A's closed set."""
    return declared("vertical")


def reader_roles() -> tuple[str, ...]:
    """What readers the corpus can speak as. Group B's closed set."""
    return declared("role")


def undeclared(axis: str, values) -> tuple[str, ...]:
    """Values asked for that no corpus declares — the drift, named before it is written.

    A tenant switched on for a role nobody authored resolves to nothing, and the compile falls
    back to canonical doctrine WITHOUT SAYING SO. Refusing at the point of declaration is the only
    place the mistake is still cheap.
    """
    known = set(declared(axis))
    return tuple(sorted({str(v) for v in values if str(v) not in known}))


def resolvable_slugs(axis: str) -> tuple[str, ...]:
    """Slugs whose folder name matches the last segment of their own declared id.

    `KnowledgeRetriever._resolve_variants` matches a request against three aliases — the full
    identifier, its last dotted segment, and the identity name slugified. A branch whose FOLDER
    says `ai_agency` while its `identity.id` ends `.ai_agency_v2` is authored, loaded, and
    unreachable by its folder name. This names the ones that will actually resolve, so a
    declaration cannot be accepted for a branch that cannot answer it.
    """
    return tuple(sorted({slug for slug, _domain, declared_id in _axis_entries(axis)
                         if declared_id.rsplit(".", 1)[-1] == slug}))


def unreachable_slugs(axis: str) -> tuple[tuple[str, str], ...]:
    """`(slug, declared_id)` for branches whose folder name is not one of their own aliases."""
    return tuple(sorted((slug, declared_id) for slug, _domain, declared_id in _axis_entries(axis)
                        if declared_id.rsplit(".", 1)[-1] != slug))


def profile_facts(*, category: str | None = None, reader_role: str | None = None,
                  basis: str = BASIS_DECLARED) -> tuple[tuple[str, str, str], ...]:
    """`(field, value, value_type)` for a declaration — what goes on the tenant node.

    ABSENT IS NOT EMPTY. A tenant that declared no role gets no `org.reader_role` fact at all,
    rather than one holding `""`. An empty string is a value a reader can act on; the absence of
    the field is the honest statement that nobody said. It is also the difference between a
    package that re-addresses and one that does not, because these facts reach the situation's
    metadata and metadata is hashed into the expertise package's content address.
    """
    if basis not in (BASIS_DECLARED, BASIS_UNKNOWN):
        raise ValueError(f"unknown profile basis: {basis!r}")
    facts: list[tuple[str, str, str]] = []
    if category:
        facts.append((CATEGORY_FIELD, str(category), "enum"))
        facts.append((CATEGORY_BASIS_FIELD, basis, "enum"))
    if reader_role:
        facts.append((ROLE_FIELD, str(reader_role), "enum"))
        facts.append((ROLE_BASIS_FIELD, basis, "enum"))
    return tuple(facts)


def read_profile(conn, org_id: str) -> dict[str, str]:
    """What this tenant has declared, read off the tenant node. `{}` before anyone declares.

    Returns only fields that are present. A caller distinguishing "no category" from "category
    unknown" reads the absence of the key, not a sentinel.
    """
    rows = conn.execute(text(
        "select f.field, f.value from graph_facts f "
        "join graph_nodes n on n.org_id = f.org_id and n.node_id = f.subject_node_id "
        "where f.org_id = :o and n.canonical_key = :k "
        "and f.field in (:c, :cb, :p, :pb) "
        "and f.status = 'active' and f.valid_to is null"),
        {"o": org_id, "k": tenant_key(org_id),
         "c": CATEGORY_FIELD, "cb": CATEGORY_BASIS_FIELD,
         "p": ROLE_FIELD, "pb": ROLE_BASIS_FIELD}).fetchall()
    return {str(row.field): str(row.value).strip('"') for row in rows}


def variant_ids_for(profile: dict[str, str]) -> tuple[str, ...]:
    """The `l3_activation.variant_ids` a declared profile implies.

    ORDER IS THE RESOLUTION ORDER — persona before vertical — and it is not cosmetic: the corpus
    resolves `role -> vertical -> model -> canonical`, most specific first, and a reader of the
    stored row should see the same precedence the compiler applies.

    A value this returns is a slug, which is what `_resolve_variants` matches on. It is NOT
    validated here against the corpus: `undeclared()` is that check and it belongs at the moment
    somebody declares, not at the moment the row is read — a corpus branch deleted after a tenant
    was switched on must surface as `unresolved_variant_ids` on the package, which is a receipt,
    rather than vanish from the row that records the decision.
    """
    out: list[str] = []
    for field in (ROLE_FIELD, CATEGORY_FIELD):
        value = (profile.get(field) or "").strip()
        if value:
            out.append(value)
    return tuple(out)


def answerable_domains(role: str | None) -> frozenset[str]:
    """Which corpus domains this reader role is answerable for, from its `answerable_for:` block.

    THE ONE THING RANKING NEEDS AND THE ONLY THING IT ASKS FOR. A role file could declare a
    great deal about a reader; ranking reads exactly this, and reads it at the coarsest grain the
    corpus has — a domain, of which there are three — because that is the grain a human can
    actually author. There are 534 capabilities; nobody maintains a per-capability remit by hand,
    and a list nobody maintains is a list that quietly stops being true.

    EMPTY MEANS "NOT STATED", AND NOT STATED MEANS NO PENALTY. A role that declares no remit
    ranks exactly as this tenant ranks today. That is deliberate: a reader whose remit nobody
    wrote down should not have cards pushed down the brief on the strength of an omission.

    Read from every corpus that authors this role and unioned. Admin's view of a CTO and
    Sales's view of a CTO are separate documents by design, and a CTO answerable for `admin` in
    one and `sales` in the other is answerable for both — the union is the reader, not either
    file's opinion of them.
    """
    if not role:
        return frozenset()
    directory = VARIANT_AXES["role"]
    remit: set[str] = set()
    try:
        root = corpus_root()
        domains = sorted(d for d in root.iterdir()
                         if d.is_dir() and not d.name.startswith("_"))
    except OSError:
        return frozenset()
    for domain_root in domains:
        document = domain_root / directory / role / "role.yaml"
        if not document.is_file():
            continue
        try:
            import yaml

            data = yaml.safe_load(document.read_text()) or {}
        except Exception:      # noqa: BLE001 — one unreadable branch, not the whole remit
            continue
        if isinstance(data, dict):
            remit.update(str(value) for value in (data.get("answerable_for") or ()))
    return frozenset(remit)


class UndeclaredProfileValue(ValueError):
    """A category or persona no corpus authors. Refused at the declaration, never stored.

    Storing it would put a value in `variant_ids` that `_resolve_variants` cannot match, and an
    unmatched request degrades to "no overlay" — named in `unresolved_variant_ids` on the package,
    but invisible on the screen, where the tenant simply keeps reading canonical doctrine while
    the console shows them as configured. That is the shape of every silent-fallback bug in this
    layer, and the declaration is the last place it is still cheap to refuse.
    """

    def __init__(self, axis: str, values: tuple[str, ...], known: tuple[str, ...]) -> None:
        self.axis, self.values, self.known = axis, values, known
        super().__init__(
            f"no corpus declares {axis} {', '.join(values)!r} — authored: "
            f"{', '.join(known) or '(none)'}")


def declare(engine, store, org_id: str, *, category: str | None = None,
            reader_role: str | None = None, by: str) -> dict[str, Any]:
    """Record what this tenant is, and point Layer 3's branches at it. Returns what it did.

    THE ORDER IS FACTS FIRST, THEN THE SWITCH, and it is not arbitrary. The facts are the record
    of what somebody declared; `variant_ids` is a SELECTION derived from them. If the switch were
    written first and the fact write failed, the tenant would be compiling against a branch with
    nothing in the graph saying why — a configuration with no stated reason, which is exactly what
    `l3_activation` already holds today (`variant_ids: []`, and nobody able to say what the tenant
    is). Derived state must never outlive its source.

    EVERY ACTIVATED DOMAIN GETS THE SAME PROFILE. A tenant is one company: it does not sell into
    one vertical for Admin and another for Sales. The BRANCH each corpus resolves differs — Admin
    authors `verticals/ai_agency`, Sales may not — and that difference is the corpus's to make,
    reported as `unresolved_variant_ids` where a corpus has not authored the branch. Declaring
    per domain would make the tenant answer the same question three times and let the answers
    disagree.

    REFUSES BEFORE IT WRITES. A value no corpus declares raises and nothing is stored — see
    `UndeclaredProfileValue`. A tenant with no activated domain gets its facts written and no
    switch touched, which is the honest half-state: we know what they are, Layer 3 is not on.
    """
    from genios_engine.platform.l3_activation import activated_domains, set_variants

    for axis, value in (("vertical", category), ("role", reader_role)):
        if value:
            missing = undeclared(axis, [value])
            if missing:
                raise UndeclaredProfileValue(axis, missing, declared(axis))

    facts = profile_facts(category=category, reader_role=reader_role)
    written: list[str] = []
    if facts:
        with engine.begin() as conn:
            node_id = store.find_or_create_node(
                conn, org_id=org_id, node_type="tenant", canonical_key=tenant_key(org_id),
                display_name="This organisation", event_id=None)
            for field, value, value_type in facts:
                # `authority_rank=6` — a statement by the account holder about their own company
                # outranks anything an extractor infers from prose. `event_id` names the
                # declaration rather than a message, because no message caused this.
                store.write_fact(
                    conn, org_id=org_id, subject_node_id=node_id, field=field,
                    value=value, value_type=value_type, confidence=1.0,
                    occurred_at=None, event_id=f"declared:{org_id}",
                    evidence={"declared_by": by}, source="declaration", authority_rank=6)
                written.append(field)

    profile = {field: value for field, value, _t in facts}
    variants = variant_ids_for(profile)
    switched: list[str] = []
    for domain in sorted(activated_domains(engine, org_id)):
        if set_variants(engine, org_id, domain=domain, variant_ids=variants, by=by) is not None:
            switched.append(domain)
    return {"facts_written": tuple(written), "variant_ids": variants,
            "domains_switched": tuple(switched)}


__all__ = [
    "UndeclaredProfileValue",
    "BASIS_DECLARED", "BASIS_UNKNOWN",
    "CATEGORY_BASIS_FIELD", "CATEGORY_FIELD", "ROLE_BASIS_FIELD", "ROLE_FIELD",
    "VARIANT_AXES",
    "answerable_domains", "categories", "declare", "declared", "reader_roles", "profile_facts", "read_profile",
    "resolvable_slugs", "tenant_key", "undeclared", "unreachable_slugs", "variant_ids_for",
]
