"""Who is us — one answer, for every module that asks (STEP-04).

"Is this address, this person, this company one of us?" sits under every judgment the engine makes:
who owes the next move, who a card is about, whether a thread has been answered. It was answered in
eighteen places, from three or four different sources, and they disagreed (`speedrun008/YC-II W27/`
STEP-04 §8.2):

  * most read `orgs.email`, the active seats and `connections.external_account_id` — a column nothing
    writes — so an address of ours that is neither (`ceo@thegenios.com`, which only ever receives the
    founder's own mail) was an outside person: typed a service, put on "waiting longest" lines;
  * the support lane added the DOMAIN of `orgs.email`, with no exception for public mail, so a Gmail
    founder made every gmail.com sender one of us;
  * nothing made the company's own domain ours outside a single event's anchor exclusion.

Here it is decided once. `SelfIdentity` holds our addresses and the domains we declared, and answers
two questions — `is_us(email)` and `is_us_node(node_type, canonical_key)`. `identity_for(conn, org_id)`
reads it from the four sources, the tenant's declarations included (`org_self_identities`, migration
0193). A public mail domain is never ours as a domain: an exact address at gmail.com is ours; gmail.com
never is.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from genios_engine.capture.validate.canonical import CONSUMER_EMAIL_DOMAINS
from genios_engine.platform.identity import norm_email

#: Mail hosts anyone can sign up at. One list for the whole engine — the address half of an identity
#: may sit on one; the domain half never does.
PUBLIC_MAIL_DOMAINS: frozenset[str] = CONSUMER_EMAIL_DOMAINS


def norm_domain(domain: str | None) -> str | None:
    """A domain as company keys carry it: lowercase, trimmed, no leading `@` or dot."""
    value = str(domain or "").strip().lower().lstrip("@").strip(".")
    return value if value and "." in value and "@" not in value else None


@dataclass(frozen=True)
class SelfIdentity:
    """Our addresses and our declared domains, normalised. Build it with `of`."""

    addresses: frozenset[str] = field(default_factory=frozenset)
    domains: frozenset[str] = field(default_factory=frozenset)

    @classmethod
    def of(cls, addresses: Iterable[str | None] = (),
           domains: Iterable[str | None] = ()) -> "SelfIdentity":
        """Normalised: addresses the way person keys are (`platform/identity.norm_email`), domains
        lowercased — and a public mail domain dropped, never kept as ours."""
        norm_addresses = frozenset(a for a in (norm_email(x) for x in addresses) if a)
        norm_domains = frozenset(d for d in (norm_domain(x) for x in domains)
                                 if d and d not in PUBLIC_MAIL_DOMAINS)
        return cls(addresses=norm_addresses, domains=norm_domains)

    def __bool__(self) -> bool:
        return bool(self.addresses or self.domains)

    def is_us_domain(self, domain: str | None) -> bool:
        """A declared domain, or a subdomain of one."""
        d = norm_domain(domain)
        return bool(d) and any(d == ours or d.endswith("." + ours) for ours in self.domains)

    def is_us(self, email: str | None) -> bool:
        """An exact address of ours, or an address at a domain we declared."""
        address = norm_email(email)
        if not address:
            return False
        return address in self.addresses or self.is_us_domain(address.rsplit("@", 1)[1])

    def is_us_node(self, node_type: str | None, canonical_key: str | None) -> bool:
        """A graph node of ours: a person or service by its address, a company by its domain, and
        the tenant node itself. Threads, deals and every other kind are things, not parties."""
        kind = str(node_type or "")
        key = str(canonical_key or "")
        if kind in ("person", "service"):
            return self.is_us(key)
        if kind == "company":
            return self.is_us_domain(key)
        return kind == "tenant"


#: The four sources, in ONE statement — every caller pays one round trip. A deactivated seat is no
#: longer us; a connected account counts whatever the connection's state (the address stays ours).
_IDENTITY_SQL = (
    "select 'address' as kind, lower(email) as value from org_seats "
    " where org_id = :o and active and email is not null "
    "union select 'address', lower(email) from orgs where id = :o and email is not null "
    "union select 'address', lower(external_account_id) from connections "
    " where org_id = :o and external_account_id like '%@%' "
    "union select kind, value from org_self_identities where org_id = :o")


def identity_for(source, org_id: str) -> SelfIdentity:
    """Who `org_id` is: its active seats, `orgs.email`, its connected accounts and what it declared.

    `source` is a connection, an engine, or a store carrying `.engine` — the three handles the
    callers hold. A declared public mail domain is refused and said, never applied.
    """
    from sqlalchemy import text

    from genios_engine.platform.logging import get_logger

    def _read(conn) -> list:
        return conn.execute(text(_IDENTITY_SQL), {"o": org_id}).fetchall()

    if hasattr(source, "execute"):
        rows = _read(source)
    else:
        engine = getattr(source, "engine", source)
        with engine.connect() as conn:
            rows = _read(conn)
    addresses = [r.value for r in rows if r.kind == "address"]
    domains = [r.value for r in rows if r.kind == "domain"]
    refused = sorted({d for d in domains if norm_domain(d) in PUBLIC_MAIL_DOMAINS})
    if refused:
        get_logger("genios.platform.self_identity").warning(
            "org=%s declared public mail domain(s) %s as its own — refused, not applied",
            org_id, refused)
    return SelfIdentity.of(addresses=addresses, domains=domains)
