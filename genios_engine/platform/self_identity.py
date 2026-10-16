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


#: Words that open a name and are no first name of anyone ("The Genios Company" is not "The").
_NOT_A_FIRST_NAME = frozenset({"the", "a", "an", "team", "and", "of"})


def speaks_of_us(text: str | None, us: SelfIdentity, names: Iterable[str | None] = ()) -> str | None:
    """Whether PROSE — a question to the founder, a card's sentence — names one of us, and how: the first
    thing it names us by, as written — or None (STEP-13 M36.C2.L-logic.V2.U19, second crosscheck F3).

    `names_us` reads a SUBJECT, where a one-word name must be the whole of it and a first name claims nothing
    ("Rohit Sharma" is somebody else). Prose is another matter: "whether GeniOS is incubated" and "whether
    Rohit went to the event" both speak of us. So here a name of ours matches as whole words AT ANY LENGTH —
    a one-word company name too — written as a name (its first letter a capital), and a PERSON's first name
    as well: the first word of a name of ours of two words or more, a title or an article aside. An address
    or a domain of ours, anywhere in it, is us (`names_us`'s own reading)."""
    import re

    value = " ".join(str(text or "").split())
    if not value:
        return None
    for m in re.finditer(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+|[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+", value):
        token = m.group(0).lower()
        if (us.is_us(token) if "@" in token else us.is_us_domain(token)):
            return m.group(0)
    found: list[tuple[int, str]] = []
    for raw in names:
        words = " ".join(str(raw or "").split()).split()
        while len(words) > 2 and words[0].lower().rstrip(".") in _HONORIFICS:
            words = words[1:]
        name = " ".join(words)
        if len(name) < 3 or "@" in name:
            continue
        candidates = [name]
        if len(words) >= 2 and words[0].lower() not in _NOT_A_FIRST_NAME and len(words[0]) >= 3:
            candidates.append(words[0])
        for candidate in candidates:
            for hit in re.finditer(rf"(?<![\w]){re.escape(candidate)}(?![\w])", value, re.I):
                if hit.group(0)[0].isupper():
                    found.append((hit.start(), hit.group(0)))
                    break
    return min(found, key=lambda f: (f[0], -len(f[1])))[1] if found else None   # the longest where two begin


#: A verb left agreeing with the third person once a name of ours is "you" — and how "you" says it.
_YOU_AGREE: dict[str, str] = {"is": "are", "was": "were", "has": "have", "does": "do", "isn't": "aren't",
                              "wasn't": "weren't", "hasn't": "haven't", "doesn't": "don't"}


def to_you(text: str | None, us: SelfIdentity, names: Iterable[str | None] = ()) -> str | None:
    """`text` with every name or address of ours it speaks of (`speaks_of_us`) said as "you" — "<name>'s" as
    "your", "is"/"was"/"has"/"does" after it as "are"/"were"/"have"/"do" — or None when it cannot be said so: a
    domain of ours, or a verb left in the third person ("Rohit wants" — "you wants"). STEP-13
    M36.C2.L-logic.V2.U19: the second-person rephrase of a question to you; None, and the closed question is
    asked instead."""
    import re

    out = " ".join(str(text or "").split())
    for _ in range(8):
        hit = speaks_of_us(out, us, names)
        if hit is None:
            break
        if "@" not in hit and "." in hit:
            return None                                # a domain of ours: no "you" says it
        m = re.search(rf"(?<![\w]){re.escape(hit)}(?![\w])('s|’s)?", out)
        if m is None:
            return None
        said = "your" if m.group(1) else "you"
        if m.start() == 0 or re.search(r"[.!?]\s*$", out[:m.start()]):
            said = said.capitalize()
        out = out[:m.start()] + said + out[m.end():]
    else:
        return None
    out = re.sub(r"\b([Tt])he (your)\b", lambda m: "Your" if m.group(1) == "T" else "your", out)
    out = re.sub(r"\b([Yy]ou) (is|was|has|does|isn't|wasn't|hasn't|doesn't)\b",
                 lambda m: f"{m.group(1)} {_YOU_AGREE[m.group(2)]}", out)
    def asked(m: re.Match[str]) -> str:                # "Does Arjun want" → "Do you want"
        verb = _YOU_AGREE[m.group(1).lower()]
        return f"{verb.capitalize() if m.group(1)[0].isupper() else verb} you"
    out = re.sub(r"\b(Is|is|Was|was|Has|has|Does|does) you\b", asked, out)
    if re.search(r"\b[Yy]ou (?!are\b|were\b|have\b|do\b)[a-z]*[^siu]s\b", out):   # "you wants", never "you discuss"
        return None
    return out


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
