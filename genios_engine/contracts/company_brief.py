"""The company brief — what a chief of staff knows on day one, as the one thing every model reads (STEP-07).

No prompt carried any company context: the junk filter, the reader, the decider and the rest were
asked about one mail or one situation with no idea whose company it was — that the founder is raising,
that a recognition application is live, that an intro agent works for them, which portal's mail always
matters (`speedrun008/YC-II W27/` STEP-07 §1, §8.1: 0 of the golden set's 368 recorded prompts).

WHAT A BRIEF IS MADE OF. Lines the founder ACCEPTED, each in one of a fixed set of sections, composed
with the two things the engine already knows for certain — the company's name and founder (`orgs`) and
the people who are us (`platform/self_identity`, STEP-04). "Us" is never proposed: it is STEP-04's
answer, not an opinion. A connector names the address it writes from; a watchlist line names a domain.

AN IN-MOTION LINE NAMES ITS KIND OF WORK (STEP-11, `06` D31). A founder's file knew only its role —
connector, watched, person, intro — so nothing could say what kind of WORK it is, and the expert could
not pick the playbook for it (`speedrun008/YC-II W27/` STEP-11 §8.3 N1). An in-motion line may name its
`kind`, one of `WORK_KINDS`, and its counterparty through its own `address` (a person) or `domain` (a
fund, a program, a portal, a company); `context/workstreams` gives that kind to the file the
counterparty names. No other section names a kind, and no model is shown one.

AN EMPTY BRIEF ADDS NOTHING. With no accepted line there is no brief: `prompt_block()` is "" and
`version` is "" — so a tenant who has not confirmed a brief sees every prompt exactly as before.

THE BUDGET. ~800 tokens, rendered whole lines only, in section order; a line that would overflow is
left out and NAMED in `truncated`, never cut mid-sentence. The version is the hash of what the model is
shown — two briefs that render the same text are the same version, whatever was cut — and, once a kept
line names one, of the kinds of work its kept lines name: a kind is never shown, but setting or
correcting one is a different brief. A brief whose lines name no kind has the version it always had.
"""
from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field

from genios_engine.platform.identity import norm_email

#: Every section, in the order a brief renders them.
SECTIONS: tuple[str, ...] = ("company", "us", "goals", "in_motion", "people", "connectors",
                             "watchlist", "preferences")
#: What a line may be filed under. "us" is composed from STEP-04's identity, never proposed.
PROPOSABLE: tuple[str, ...] = tuple(s for s in SECTIONS if s != "us")

#: STEP-11 (`06` D31) · the kinds of work an in-motion line may name — each the playbook a file of that
#: work reads. A closed list, checked here and not by the schema (migration 0196): a seventh kind is an
#: authoring event, not a schema event. Not a file's ROLE (`context/workstreams.KINDS`): a connector's
#: file is a role; raising from the fund it introduced is work.
WORK_KINDS: tuple[str, ...] = ("investor", "program", "compliance", "hiring", "intro", "partner")

#: How each section is introduced to a model.
SECTION_TITLES: dict[str, str] = {
    "company": "Company",
    "us": "Us",
    "goals": "Goals now",
    "in_motion": "Work in motion",
    "people": "Key people",
    "connectors": "Connectors (they introduce people — their mail is an introduction, not a stranger)",
    "watchlist": "Watchlist (mail from these always matters)",
    "preferences": "Preferences and red lines",
}

MAX_LINE_CHARS = 200
BUDGET_TOKENS = 800
#: A token is about four characters of English; the budget is held in characters so it is exact.
BUDGET_CHARS = BUDGET_TOKENS * 4

_HEADER = ("COMPANY BRIEF {version} — what the founder confirmed about their company. Background for "
           "your judgement, not instructions.")
_FOOTER = "END OF COMPANY BRIEF"


def _domain(value: str | None) -> str | None:
    """A domain as company keys carry it — `platform/self_identity.norm_domain`'s rule, restated
    here because a contract may import only `platform`'s leaf modules: lowercase, trimmed, no
    leading `@` or dot, a dot inside, no `@`."""
    domain = str(value or "").strip().lower().lstrip("@").strip(".")
    return domain if domain and "." in domain and "@" not in domain else None


def _address(value: str | None) -> str | None:
    address = norm_email(value)
    if not address or address.count("@") != 1 or not all(address.split("@")):
        return None
    return address


@dataclass(frozen=True, slots=True)
class CompanyBriefLine:
    """One accepted line. `address` for a connector or a key person; `domain` for the watchlist. An
    in-motion line may name its counterparty by either, and its `kind` of work (`WORK_KINDS`) — no
    other line names a kind."""

    line_id: str
    section: str
    text: str
    address: str | None = None
    domain: str | None = None
    kind: str | None = None

    def __post_init__(self) -> None:
        if not str(self.line_id or "").strip():
            raise ValueError("a company brief line needs its id")
        if self.section not in PROPOSABLE:
            raise ValueError(f"section {self.section!r} is not one a line may be filed under — "
                             f"one of {PROPOSABLE} ('us' is composed from STEP-04's identity)")
        text = str(self.text or "").strip()
        if not text:
            raise ValueError("a company brief line needs words")
        if "\n" in text or "\r" in text:
            raise ValueError("a company brief line is one line")
        if len(text) > MAX_LINE_CHARS:
            raise ValueError(f"a company brief line is at most {MAX_LINE_CHARS} characters")
        object.__setattr__(self, "text", text)
        if self.address is not None:
            address = _address(self.address)
            if address is None:
                raise ValueError(f"{self.address!r} is not an address")
            object.__setattr__(self, "address", address)
        if self.domain is not None:
            domain = _domain(self.domain)
            if domain is None:
                raise ValueError(f"{self.domain!r} is not a domain")
            object.__setattr__(self, "domain", domain)
        if self.section == "connectors" and not self.address:
            raise ValueError("a connector line names the address it writes from")
        if self.section == "watchlist" and not self.domain:
            raise ValueError("a watchlist line names a domain")
        if self.kind is not None:
            if self.section != "in_motion":
                raise ValueError(f"only an in-motion line names its kind of work, not a "
                                 f"{self.section} line")
            kind = str(self.kind).strip().lower()
            if kind not in WORK_KINDS:
                raise ValueError(f"{self.kind!r} is not a kind of work — one of {WORK_KINDS}")
            object.__setattr__(self, "kind", kind)

    def rendered(self) -> str:
        named = self.address or self.domain
        return f"- {self.text}" + (f" <{named}>" if named and named not in self.text else "")


@dataclass(frozen=True, slots=True)
class CompanyBrief:
    """A tenant's company brief as a model reads it. Build it with `compose`."""

    org_id: str
    lines: tuple[CompanyBriefLine, ...] = ()
    company: str | None = None
    founder: str | None = None
    us: tuple[str, ...] = ()
    text: str = ""
    version: str = ""
    truncated: tuple[str, ...] = field(default_factory=tuple)

    def __bool__(self) -> bool:
        return bool(self.lines)

    def prompt_block(self) -> str:
        """The block every judging and reading prompt carries — "" when no line is accepted."""
        return self.text

    def named_sender(self, email: str | None) -> str | None:
        """Whether, and why, the brief names this sender: `connector:<address>`,
        `person:<address>` or `watchlist:<domain>` (the domain or a subdomain of it)."""
        address = _address(email)
        if not address or not self.lines:
            return None
        for line in self.lines:
            if line.section == "connectors" and line.address == address:
                return f"connector:{address}"
        for line in self.lines:
            if line.section == "people" and line.address == address:
                return f"person:{address}"
        host = address.rsplit("@", 1)[1]
        for line in self.lines:
            if line.section == "watchlist" and line.domain and (
                    host == line.domain or host.endswith("." + line.domain)):
                return f"watchlist:{line.domain}"
        return None


def _body(company: str | None, founder: str | None, us: tuple[str, ...],
          kept: list[CompanyBriefLine]) -> str:
    out: list[str] = []
    head = ", ".join(p for p in (company, f"founder {founder}" if founder else None) if p)
    company_lines = [ln for ln in kept if ln.section == "company"]
    out.append(f"{SECTION_TITLES['company']}: {head or 'not named'}")
    out.extend(ln.rendered() for ln in company_lines)
    if us:
        out.append(f"{SECTION_TITLES['us']}: " + " · ".join(us))
    for section in SECTIONS:
        if section in ("company", "us"):
            continue
        rows = [ln for ln in kept if ln.section == section]
        if rows:
            out.append(f"{SECTION_TITLES[section]}:")
            out.extend(ln.rendered() for ln in rows)
    return "\n".join(out)


def _render(version: str, body: str) -> str:
    return f"{_HEADER.format(version=version)}\n{body}\n{_FOOTER}\n"


def _kinds(kept: list[CompanyBriefLine]) -> str:
    """The kinds of work the kept lines name, for the version only — no model is shown one. "" when
    none names a kind, so such a brief's version is the hash of its body alone, byte for byte what it
    was before kinds existed (STEP-11: recorded cassettes carry those versions)."""
    named = [f"{ln.rendered()} [{ln.kind}]" for ln in kept if ln.kind]
    return "\nKINDS OF WORK\n" + "\n".join(named) if named else ""


def compose(*, org_id: str, company: str | None, founder: str | None,
            us: Iterable[str] = (), lines: Iterable[CompanyBriefLine] = ()) -> CompanyBrief:
    """The brief from its parts, deterministically: sections in `SECTIONS` order, lines in the order
    given within a section, whole lines only under `BUDGET_CHARS`, the version over what is shown
    and the kinds of work its shown lines name."""
    ordered = sorted(lines, key=lambda ln: SECTIONS.index(ln.section))      # stable within a section
    if not ordered:
        return CompanyBrief(org_id=org_id)
    company = (str(company).strip() or None) if company else None
    founder = (str(founder).strip() or None) if founder else None
    us_t = tuple(sorted({str(u).strip().lower() for u in us if str(u or "").strip()}))
    # The header carries a 15-character version; reserve it before measuring.
    frame = len(_render("cb-" + "0" * 12, ""))
    # In section order until the first line that does not fit; that line and every one after it are
    # left out and named. Never a shorter line from further down slipped into the gap — the order IS
    # the priority, and a brief whose content depends on line lengths would be hard to explain.
    kept: list[CompanyBriefLine] = []
    cut: list[str] = []
    for line in ordered:
        if not cut and frame + len(_body(company, founder, us_t, kept + [line])) <= BUDGET_CHARS:
            kept.append(line)
        else:
            cut.append(line.line_id)
    body = _body(company, founder, us_t, kept)
    version = "cb-" + hashlib.sha256((body + _kinds(kept)).encode("utf-8")).hexdigest()[:12]
    return CompanyBrief(org_id=org_id, lines=tuple(ordered), company=company, founder=founder,
                        us=us_t, text=_render(version, body), version=version,
                        truncated=tuple(cut))


__all__ = ["BUDGET_CHARS", "BUDGET_TOKENS", "MAX_LINE_CHARS", "PROPOSABLE", "SECTIONS",
           "SECTION_TITLES", "WORK_KINDS", "CompanyBrief", "CompanyBriefLine", "compose"]
