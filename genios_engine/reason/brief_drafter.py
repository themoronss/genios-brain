"""The company brief's drafter — one model call that PROPOSES lines from memory patterns (STEP-07).

A chief of staff on day one reads the founder's calendar and correspondence and writes down what
matters: the company, its goals, the work in motion, the key people, who introduces whom, which
portals and programs must never be missed. The drafter does that from memory PATTERNS
(`reason/brief_patterns`) — counts, names, domains, dates, the one-line objective memory holds for a
thread — never a message (`speedrun008/YC-II W27/` STEP-07 §3.3, §8.3).

IT PROPOSES; THE FOUNDER DECIDES. Every line it returns is written as a proposal
(`platform/company_brief_store.propose`), with the patterns it rests on as its evidence, and nothing
reaches a prompt until the founder accepts it. REFUSE, NEVER REPAIR: a line whose section is unknown,
whose evidence names no pattern, or whose address or domain is not in the patterns is refused with its
reason — the drafter cannot introduce a sender the memory never saw. Weekly (`reason/brief_review`) it
is asked again with the brief in force, for what is missing.

THE KIND OF WORK (STEP-11, `06` D31). Each in-motion line it proposes names its kind of work — one of
`contracts/company_brief.WORK_KINDS`, or none when none fits — and may name its counterparty, an address
or a domain the patterns show; the file that counterparty names reads that kind's playbook. Refused like
anything else, never repaired: a kind off the list, or a kind on a line of any other section. The kind is
proposed with the line, and the founder accepts, corrects or clears it with the line.

One Sonnet-class call (`Settings.company_brief_model`, `06` D28), recorded as `company_brief_draft`.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from genios_engine.contracts.company_brief import PROPOSABLE, WORK_KINDS, CompanyBriefLine

#: v2 (STEP-11): the prompt asks for each in-motion line's kind of work and counterparty.
PROMPT_VERSION = "company-brief-draft.v2"
COST_PURPOSE = "company_brief_draft"
MAX_LINES = 30
MAX_PER_SECTION = 8
MAX_TEXT = 160
MAX_TOKENS = 2400

_PROMPT = """You are a chief of staff with thirty years of experience, on your first day with a \
founder. Before you judge a single message for them you write down the company brief: what the \
company is, what the founder is trying to achieve now, the work in motion, the key people and their \
role, the connectors who introduce the founder to others, the domains whose mail must never be \
missed, and the founder's preferences.

You are shown PATTERNS from the founder's memory — who writes to whom and how often, which domains, \
days of outbound waves, senders who introduce people, recurring meetings, which domains carry \
deadlines, and the one-line objective memory holds for a thread. You are not shown any message.

Propose lines the founder will accept, edit or reject. Rules:
- Each line goes in exactly one section: company, goals, in_motion, people, connectors, watchlist, \
preferences.
- A people line may give the person's address. A connectors line MUST give the address the connector \
writes from. A watchlist line MUST give a domain: a government portal, a program or a fund whose mail \
must never be missed. Use only addresses and domains that appear in the patterns.
- An in_motion line names its kind of work: {kinds} — or null when none fits. It may give its \
counterparty, the one on the other side of that work: the person's address, or the domain of the fund, \
program, portal or company. No other section has a kind.
- Every line cites the ids of the patterns it rests on.
- Never invent a name, an amount, a date or a fact the patterns do not show. When unsure, leave it out.
- At most {per_section} lines in a section and {total} in all; each line under {chars} characters.
{current}
Return JSON only, in exactly this shape:
{{"lines": [{{"section": "...", "text": "...", "address": null, "domain": null, "kind": null, \
"evidence": ["p1"]}}]}}

THE COMPANY: {company}
US: {us}

PATTERNS:
{patterns}"""

_CURRENT = """
The brief already holds the lines below. Propose only what is missing — never a line it already says.

{block}
"""

#: How the prompt offers each kind of work (STEP-11). One per `WORK_KINDS`, in its order: a kind the
#: drafter is never offered is a kind no line is ever proposed with.
_KIND_GLOSSES: dict[str, str] = {
    "investor": "raising from a fund or an angel",
    "program": "an accelerator, incubator or program application",
    "compliance": "a registration, filing or certificate with a government portal",
    "hiring": "filling a role",
    "intro": "an introduction made or asked for",
    "partner": "a design partner, customer or distribution partner",
}


def _kinds_offered() -> str:
    return ", ".join(f"{k} ({_KIND_GLOSSES[k]})" if k in _KIND_GLOSSES else k for k in WORK_KINDS)


@dataclass(frozen=True)
class Proposal:
    section: str
    text: str
    address: str | None
    domain: str | None
    evidence: tuple[str, ...]
    kind: str | None = None             # STEP-11 · an in-motion line's kind of work, or none


@dataclass(frozen=True)
class DraftOutcome:
    """What one draft did. `proposed` counts the lines written; a line the brief already holds, or
    one the founder rejected lately, is not written again (`company_brief_store.propose`)."""
    proposed: int = 0
    refused: tuple[str, ...] = ()
    skipped: str | None = None
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    lines: tuple[Proposal, ...] = ()


def build_prompt(patterns: dict[str, Any], *, company_brief: str = "") -> str:
    """The drafter's prompt: the rules, the brief in force (if any), and the patterns as JSON lines."""
    import json

    company = ", ".join(p for p in (patterns.get("company"),
                                    f"founder {patterns['founder']}" if patterns.get("founder")
                                    else None) if p) or "not named"
    rendered = "\n".join(json.dumps(item, ensure_ascii=False, sort_keys=True)
                         for item in patterns.get("items", ()))
    return _PROMPT.format(per_section=MAX_PER_SECTION, total=MAX_LINES, chars=MAX_TEXT,
                          kinds=_kinds_offered(),
                          current=_CURRENT.format(block=company_brief.rstrip()) if company_brief else "",
                          company=company, us=" · ".join(patterns.get("us", ())) or "unknown",
                          patterns=rendered)


def parse(parsed: Any, patterns: dict[str, Any]) -> tuple[list[Proposal], list[str]]:
    """The model's lines that survive, and every refusal with its reason. Never repairs a line."""
    from genios_engine.reason.brief_patterns import addresses_in, domains_in

    lines = parsed.get("lines") if isinstance(parsed, dict) else None
    if not isinstance(lines, list):
        return [], ["the answer has no 'lines' list"]
    ids = {i["id"] for i in patterns.get("items", ())}
    addresses, domains = addresses_in(patterns), domains_in(patterns)
    kept: list[Proposal] = []
    refused: list[str] = []
    per_section: Counter = Counter()
    seen: set[tuple[str, str]] = set()
    for n, entry in enumerate(lines, 1):
        why = None
        if not isinstance(entry, dict):
            why = "not an object"
        else:
            section = str(entry.get("section") or "").strip()
            words = str(entry.get("text") or "").strip()
            address = str(entry.get("address") or "").strip().lower() or None
            domain = str(entry.get("domain") or "").strip().lower().lstrip("@") or None
            kind = str(entry.get("kind") or "").strip().lower() or None
            evidence = entry.get("evidence")
            if section not in PROPOSABLE:
                why = f"section {section!r} is not one a line may be filed under"
            elif not isinstance(evidence, list) or not evidence \
                    or not all(isinstance(e, str) and e in ids for e in evidence):
                why = "its evidence names no pattern, or one that does not exist"
            elif len(words) > MAX_TEXT:
                why = f"longer than {MAX_TEXT} characters"
            elif address and address not in addresses:
                why = f"address {address} is not in the patterns"
            elif domain and domain not in domains:
                why = f"domain {domain} is not in the patterns"
            elif per_section[section] >= MAX_PER_SECTION or len(kept) >= MAX_LINES:
                why = "over the line budget"
            elif (section, words.lower()) in seen:
                why = "a repeat of a line above"
            else:
                try:
                    CompanyBriefLine(line_id=f"draft_{n}", section=section, text=words,
                                     address=address, domain=domain, kind=kind)
                except ValueError as exc:
                    why = str(exc)
        if why:
            refused.append(f"line {n}: {why}")
            continue
        per_section[section] += 1
        seen.add((section, words.lower()))
        kept.append(Proposal(section=section, text=words, address=address, domain=domain,
                             evidence=tuple(evidence), kind=kind))
    return kept, refused


def _evidence(proposal: Proposal, patterns: dict[str, Any]) -> list[dict[str, Any]]:
    """What a proposal rests on, kept with it: the pattern items themselves — counts, names,
    domains and dates — so the founder sees why it was proposed long after the ids are gone."""
    by_id = {i["id"]: i for i in patterns.get("items", ())}
    return [{"pattern": e, **{k: v for k, v in by_id[e].items() if k != "id"}}
            for e in proposal.evidence if e in by_id]


def draft_company_brief(engine, org_id: str, llm: Any, *, now: datetime, cost_sink=None,
                        proposed_by: str = "drafter", apply: bool = True) -> DraftOutcome:
    """Ask once and propose what survives — or, with `apply=False`, only say what would be proposed.
    Nothing is accepted here."""
    from genios_engine.platform import company_brief_store as store
    from genios_engine.platform.company_brief import brief_for
    from genios_engine.reason.brief_patterns import patterns_for

    if llm is None:
        return DraftOutcome(skipped="no_model")
    with engine.connect() as c:
        patterns = patterns_for(c, org_id, now=now)
        current = brief_for(c, org_id).prompt_block()
    if not patterns["items"]:
        return DraftOutcome(skipped="no_patterns")
    model = str(getattr(llm, "model", "") or "unknown")
    res = llm.call(build_prompt(patterns, company_brief=current), max_tokens=MAX_TOKENS)
    it, ot = int(getattr(res, "input_tokens", 0) or 0), int(getattr(res, "output_tokens", 0) or 0)
    if cost_sink is not None:
        try:
            cost_sink(org_id=org_id, model=getattr(res, "model", "") or model, purpose=COST_PURPOSE,
                      input_tokens=it, output_tokens=ot, success=bool(getattr(res, "ok", False)),
                      error=getattr(res, "error", None))
        except Exception:      # noqa: BLE001 — accounting never costs the draft
            pass
    if not getattr(res, "ok", False):
        return DraftOutcome(skipped=f"model:{getattr(res, 'error', '') or 'no answer'}"[:200],
                            model=model, input_tokens=it, output_tokens=ot)
    proposals, refused = parse(res.parsed, patterns)
    written = 0
    if apply:
        with engine.begin() as c:
            for p in proposals:
                if store.propose(c, org_id=org_id, section=p.section, words=p.text, address=p.address,
                                 domain=p.domain, kind=p.kind, proposed_by=proposed_by, at=now,
                                 evidence=_evidence(p, patterns)) is not None:
                    written += 1
    return DraftOutcome(proposed=written, refused=tuple(refused), model=model, input_tokens=it,
                        output_tokens=ot, lines=tuple(proposals))


__all__ = ["COST_PURPOSE", "DraftOutcome", "MAX_LINES", "MAX_PER_SECTION", "PROMPT_VERSION",
           "Proposal", "build_prompt", "draft_company_brief", "parse"]
