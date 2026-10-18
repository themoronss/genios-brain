"""Who a connector introduced — and which of them a later mail of its is about (STEP-09).

A connector the founder's company brief names (an intro network: Introly, Boardy) writes three kinds of
mail, and they belong in different files:

  * an INTRODUCTION — "Arjun, meet Rahul" — to the founder and the people it introduces. It is filed
    under each person introduced, never under the connector;
  * a NUDGE — "Rahul is still waiting" — to the founder alone, about someone it introduced. It joins
    that person's file;
  * its OWN ASK — "which stage are you raising at?" — to the founder alone, about no one it introduced.
    That one is the connector's own file (golden replay 02 m04).

NAMES, NEVER A MODEL. Which name in an introduction belongs to which person is decided here from what
the mail says and where it went: a person's name against the address's local part, an organisation
against the address's domain; when one person is introduced, the one name left over is theirs. A name
that fits two people fits no one, and a name that fits nobody is attached to nobody. The model's job
was to find the names in the text (`entity_mentions`); deciding whose they are is bookkeeping, and it
is done the same way every time.

ONE ANSWER TO "WHO IS A CONNECTOR". `connector_roles` is what the live drain (`context/pipeline`) and
a rebuild (`context/backfill.backfill_correlations`) both read, so the two file a connector's mail
the same way.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import text

# The pipeline's own list: a personal mailbox's domain names no organisation (`pipeline._company_domain`).
from genios_engine.capture.structured.apply import _PERSONAL_DOMAINS
from genios_engine.contracts.company_brief import CompanyBrief

#: Domain labels that say nothing about whose domain it is.
_GENERIC_LABELS = frozenset({"mail", "email", "mx", "gov", "com", "org", "net", "edu", "co", "in",
                             "io", "ai", "test", "www", "info", "notify", "news"})
#: Mention types that name an organisation (the extraction's words for it).
_ORG_TYPES = frozenset({"organization", "organisation", "company"})
#: The shortest stem or name an organisation is matched on — "ai" or "lab" match too much.
_MIN_STEM = 4

_WORD = re.compile(r"[^\W\d_]+")


def _tokens(name: str | None) -> list[str]:
    return _WORD.findall(str(name or "").casefold())


def _compact(name: str | None) -> str:
    return "".join(_tokens(name))


def _local_tokens(address: str) -> list[str]:
    local = address.split("@", 1)[0].casefold()
    return [t for t in re.split(r"[._+\-]+", local) if t]


def _stem(address_or_domain: str) -> str | None:
    """The label of a domain that names its owner: `kestrelcap` of `rahul@kestrelcap.test`,
    `startupsetu` of `notify.startupsetu.gov.test` — and none of a personal mailbox's."""
    domain = address_or_domain.rsplit("@", 1)[-1].casefold()
    if domain in _PERSONAL_DOMAINS:
        return None
    labels = [lb for lb in domain.split(".")[:-1]
              if lb not in _GENERIC_LABELS and len(lb) >= 3]
    return max(labels, key=len) if labels else None


def person_fits(name: str, address: str) -> bool:
    """Does this person's name go with this address? Its first local token is one of the name's
    words ("rahul" ↔ "Rahul Menon"), or the whole local part spells the name ("rmenon" does not)."""
    words, local = _tokens(name), _local_tokens(address)
    if not words or not local:
        return False
    return (len(local[0]) >= 2 and local[0] in words) or "".join(local) == "".join(words)


def org_fits(name: str, address: str) -> bool:
    """Does this organisation go with this address's domain? One of the two spellings starts with
    the other, and the shorter is at least `_MIN_STEM` letters ("Kestrel Capital" ↔ kestrelcap)."""
    stem, compact = _stem(address), _compact(name)
    if not stem or not compact or min(len(stem), len(compact)) < _MIN_STEM:
        return False
    return compact.startswith(stem) or stem.startswith(compact)


def _is_person(mention: dict) -> bool:
    return str(mention.get("type") or "").strip().lower() == "person"


def _is_org(mention: dict) -> bool:
    return str(mention.get("type") or "").strip().lower() in _ORG_TYPES


def _name(mention: dict) -> str:
    return str(mention.get("name") or "").strip()


@dataclass(frozen=True, slots=True)
class Assigned:
    """The names an introduction used for one person: their own (`person`), their organisation's
    (`organisation`) — each only when exactly one fits — and every name that fits (`names`)."""
    person: str | None
    organisation: str | None
    names: tuple[str, ...]


def assign_names(mentions: Iterable[dict], contacts: Iterable[str], *,
                 not_theirs: Iterable[str] = ()) -> dict[str, Assigned]:
    """Whose is each name an introduction used. `contacts` are the addresses introduced;
    `not_theirs` the addresses whose names are never a contact's — the connector's and ours."""
    contacts = list(dict.fromkeys(a.casefold() for a in contacts))
    others = [a.casefold() for a in not_theirs]
    people, orgs = [], []
    for m in mentions or ():
        name = _name(m)
        if not name:
            continue
        if _is_person(m) and not any(person_fits(name, a) for a in others):
            people.append(name)
        elif _is_org(m) and not any(org_fits(name, a) for a in others):
            orgs.append(name)
    people, orgs = list(dict.fromkeys(people)), list(dict.fromkeys(orgs))
    fits = {a: ([n for n in people if person_fits(n, a)], [n for n in orgs if org_fits(n, a)])
            for a in contacts}
    # A name that fits two people is nobody's.
    for kind in (0, 1):
        counts: dict[str, int] = {}
        for a in contacts:
            for n in fits[a][kind]:
                counts[n] = counts.get(n, 0) + 1
        for a in contacts:
            fits[a][kind][:] = [n for n in fits[a][kind] if counts[n] == 1]
    if len(contacts) == 1:
        p, o = fits[contacts[0]]
        if not p and len(people) == 1:
            p.append(people[0])
        if not o and len(orgs) == 1:
            o.append(orgs[0])
    return {a: Assigned(person=fits[a][0][0] if len(fits[a][0]) == 1 else None,
                        organisation=fits[a][1][0] if len(fits[a][1]) == 1 else None,
                        names=tuple(dict.fromkeys(fits[a][0] + fits[a][1])))
            for a in contacts}


@dataclass(frozen=True, slots=True)
class Introduction:
    """Someone a connector introduced: their node and address, their organisation's node, and the
    names they are known by."""
    contact: str
    address: str
    company: str | None
    names: tuple[str, ...]


_INTRODUCED_BY = text(
    "select p.node_id as contact, p.canonical_key as address, p.display_name as person, "
    "       c.node_id as company, c.canonical_key as domain, c.display_name as org "
    "  from graph_edges e "
    "  join graph_nodes p on p.org_id = e.org_id and p.node_id = e.to_node_id "
    "       and p.valid_to is null "
    "  left join graph_edges w on w.org_id = e.org_id and w.edge_type = 'works_at' "
    "       and w.from_node_id = p.node_id and w.valid_to is null "
    "  left join graph_nodes c on c.org_id = w.org_id and c.node_id = w.to_node_id "
    "       and c.node_type = 'company' and c.valid_to is null "
    " where e.org_id = :o and e.edge_type = 'introduced' and e.from_node_id = :n "
    "   and e.valid_to is null "
    " order by p.node_id")


def connector_roles(conn, *, org_id: str, company_brief: CompanyBrief | None) -> dict[str, str]:
    """Every node the founder's company brief names as a connector, as `introducer` — the role
    correlation reads (`correlation.NON_ANCHORING_ROLES`) and carries to the connector's company
    (`correlation._lift_roles`). Wherever the connector appears: on a mail's From or To, or only
    named in its prose; an intro network is infrastructure in every conversation it brokers. Alone
    at its tier — its own ask — it still anchors (`correlation.choose_anchors` falls back). Empty
    without a brief, and then nothing is read."""
    addresses = sorted({line.address for line in (getattr(company_brief, "lines", None) or ())
                        if line.section == "connectors" and line.address})
    if not addresses:
        return {}
    return {r.node_id: "introducer" for r in conn.execute(text(
        "select node_id from graph_nodes "
        " where org_id = :o and canonical_key = any(:k) and valid_to is null"),
        {"o": org_id, "k": addresses})}


def introductions_by(conn, *, org_id: str, connector_node: str) -> list[Introduction]:
    """Everyone this connector introduced, with the names the graph knows them by."""
    out: dict[str, Introduction] = {}
    for r in conn.execute(_INTRODUCED_BY, {"o": org_id, "n": connector_node}):
        names = tuple(n for n, key in ((r.person, r.address), (r.org, r.domain))
                      if n and str(n).casefold() != str(key or "").casefold())
        if r.contact not in out:
            out[r.contact] = Introduction(contact=r.contact, address=str(r.address),
                                          company=r.company, names=names)
    return list(out.values())


def _known_as(name: str, intro: Introduction) -> bool:
    words = _tokens(name)
    for known in intro.names:
        k = _tokens(known)
        if words and k and (words[0] == k[0] or _compact(name) == _compact(known)):
            return True
    return False


def named_in(mentions: Iterable[dict], introductions: Iterable[Introduction]) -> list[Introduction]:
    """The people among `introductions` this mail names — by their own name or their organisation's."""
    named = []
    mentions = list(mentions or ())
    for intro in introductions:
        for m in mentions:
            name = _name(m)
            if not name:
                continue
            if _is_person(m) and (person_fits(name, intro.address) or _known_as(name, intro)):
                named.append(intro)
                break
            if _is_org(m) and (org_fits(name, intro.address) or _known_as(name, intro)):
                named.append(intro)
                break
    return named


__all__ = ["Assigned", "Introduction", "assign_names", "connector_roles", "introductions_by",
           "named_in", "org_fits", "person_fits"]
