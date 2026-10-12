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

import re
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


#: Titles that come before a name and are not part of it.
_HONORIFICS = frozenset({"mr", "mrs", "ms", "miss", "dr", "prof", "shri", "smt"})


def names_us(text: str | None, us: SelfIdentity, names: Iterable[str | None] = ()) -> bool:
    """Whether a SUBJECT written as text — a card's `business_subject`, a thread label's who — is
    one of us.

    An address in it is asked of `us` (`is_us`), a bare domain of `us.is_us_domain`; a name of ours
    — the founder's full name, the company's name, the display name of a node of ours — matches as
    whole words when it has two words or more ("Mr Rohit Swerashi" holds "Rohit Swerashi"), and
    only exactly when it is one word, so a one-word company name cannot claim every subject that
    contains it, and a first name alone claims nothing ("Rohit Sharma" is somebody else).
    """
    import re

    value = " ".join(str(text or "").split()).lower()
    if not value:
        return False
    tokens = re.findall(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+|[a-z0-9-]+(?:\.[a-z0-9-]+)+", value)
    if any(us.is_us(t) if "@" in t else us.is_us_domain(t) for t in tokens):
        return True
    for raw in names:
        name = " ".join(str(raw or "").split()).lower()
        # A title is not part of the name: signup stores "Mr Rohit Swerashi" as readily as
        # "Rohit Swerashi", and a subject may carry either.
        words = name.split()
        while len(words) > 2 and words[0].rstrip(".") in _HONORIFICS:
            words = words[1:]
        name = " ".join(words)
        if len(name) < 3 or "@" in name:
            continue
        if " " in name:
            if re.search(rf"(?<![0-9a-z]){re.escape(name)}(?![0-9a-z])", value):
                return True
        elif value == name:
            return True
    return False


#: STEP-15 · mailboxes that are a ROLE, not a person — a name spelled from one would name nobody: "Events" did not
#: meet you at the mixer, its organiser's mailbox sent the invitation (F54). Matched against the whole local part.
ROLE_MAILBOXES: frozenset[str] = frozenset({
    "accounts", "admin", "apply", "applications", "billing", "careers", "community", "contact", "deals",
    "events", "founders", "hello", "help", "hi", "hr", "info", "invest", "investors", "jobs", "mail", "media",
    "news", "newsletter", "noreply", "notifications", "office", "partners", "partnerships", "press",
    "program", "programme", "programs", "sales", "startups", "support", "team", "updates"})

_SPOKEN_PART = re.compile(r"^[a-z]{2,}$")


def spoken_name(display_name: str | None, key: str | None = None) -> str | None:
    """How the brief says who someone is (STEP-15, `yc2_w27_s15` M44.C2.L-data.V0.U03): their display name when it
    is a name; else the word their address or domain spells — `gaurav@stackfield.test` "Gaurav",
    `kavitha.nair@…` "Kavitha Nair", `bluepeak.test` "Bluepeak" — and None when there is no such word: a role
    mailbox (`events@`, `no-reply@`), a local part with digits, a public mail host. Never an address."""
    name = " ".join(str(display_name or "").split())
    if name and "@" not in name and not re.fullmatch(r"[\w-]+(?:\.[\w-]+)+", name):
        return name
    raw = str(key or (name if name else "")).strip().lower()
    if not raw:
        return None
    if "@" in raw:
        local = raw.rsplit("@", 1)[0].split("+", 1)[0]
        if local.replace("-", "").replace("_", "").replace(".", "") in ROLE_MAILBOXES:
            return None
        parts = [p for p in re.split(r"[._-]", local) if p]
        if not parts or len(parts) > 3 or not all(_SPOKEN_PART.match(p) for p in parts) \
                or any(p in ROLE_MAILBOXES for p in parts):
            return None
        return " ".join(p.capitalize() for p in parts)
    domain = norm_domain(raw)
    if domain is None or domain in PUBLIC_MAIL_DOMAINS:
        return None
    label = domain.split(".", 1)[0]
    return label.capitalize() if _SPOKEN_PART.match(label) else None


def identity_sql(org: str = ":o") -> str:
    """The four sources of who `org` is, as ONE union of `(kind, value)` rows — the only place the
    engine names them. `org` is the SQL expression for the tenant: `:o` for one tenant
    (`identity_for`), or a column — `c.org_id` — where a statement must correlate per row, as a
    receipt over every tenant does (`platform/receipts`). A deactivated seat is no longer us; a
    connected account counts whatever the connection's state (the address stays ours)."""
    return (
        "select 'address' as kind, lower(email) as value from org_seats "
        f" where org_id = {org} and active and email is not null "
        f"union select 'address', lower(email) from orgs where id = {org} and email is not null "
        "union select 'address', lower(external_account_id) from connections "
        f" where org_id = {org} and external_account_id like '%@%' "
        f"union select kind, value from org_self_identities where org_id = {org}")


#: For one tenant, in ONE statement — every caller pays one round trip.
_IDENTITY_SQL = identity_sql()


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
