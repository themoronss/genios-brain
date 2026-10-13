"""The card contract — what no card may say, whatever wrote it (STEP-14).

`speedrun008/YC-II W27/` STEP-14 §3.5 and §8.4 item 6, tree `yc2_w27_s14` M43.C4.L-contract.V0.U01 (s14-F10, s14-F11).
Production showed *"nsrcel — a dated payment obligation is open"* (the money situation gates on any dated
commitment), *"Which is right? Maria Exconde: party.role"* (a discrepancy card printing its field), *"8 data points,
1 unreadable"*. The validators that exist ground a fact's KEY (V-02), so a field name passes them; the expert's check
holds only the expert's words; and the second card writer (`reason/team/emit`) runs no validator at all. So the
contract lives HERE, in `contracts/`, where both writers may read it (`reason/` may not import `deliver/`), and it
refuses a card — with the rule and what it found — that:

  us        names us as its subject, or sends its draft to us (`platform/self_identity`);
  internal  shows an internal field name (`party.role`, `commitment.action`) or an unfilled slot (`{stage}`) in
            any text the founder reads;
  money     claims money — a currency, a payment, an invoice, a fee — with no money in its evidence;
  quote     quotes words (between quotation marks) that are neither in its quotes nor in its corpus;
  number    says a number or a date its own corpus does not hold (`platform/grounding`, the card validator's
            rule for digits).

What a card's corpus and quotes are is its writer's to hand in — the facts it was built from, the quotes it may
show, the lines code computed. Pure: no I/O, no clock, no model.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, fields
from typing import Any

from genios_engine.platform.grounding import corpus_of, digit_runs, fold
from genios_engine.platform.self_identity import SelfIdentity, names_us

# ── the rules — closed, in the order a card is read. One name to a line. ──────────────────────────────────────
US = "us"
INTERNAL = "internal"
MONEY = "money"
QUOTE = "quote"
NUMBER = "number"
RULES: tuple[str, ...] = (US, INTERNAL, MONEY, QUOTE, NUMBER)

#: The graph's field namespaces — a word of one followed by `.field` is a field's name, never the founder's words.
#: An address or a domain is not one (`@` or `.` before it).
_FIELD = re.compile(r"(?<![@\w.])(?:party|commitment|deal|thread|outreach|derived|meeting|cohort|expert|situation|"
                    r"account|contact|company|person|history|signal|signals|loop|graph)\.[a-z_]+(?![\w@])")
#: A template's slot left unfilled.
_SLOT = re.compile(r"\{[a-z_][a-z_0-9]*\}")
#: Money, claimed: a currency or a word that names money.
_MONEY = re.compile(r"[₹$€£]|\b(?:inr|usd|eur|rs\.?)\b|\b(?:payments?|invoices?|fees?|refunds?|lakhs?|crores?)\b",
                    re.IGNORECASE)
#: A quoted span: between curly double quotes, or straight ones.
_QUOTED = re.compile(r"“([^”]+)”|\"([^\"]+)\"")


@dataclass(frozen=True, slots=True)
class CardText:
    """Everything a card shows the founder — and whom it is about and to."""
    headline: str
    situation: str
    subject: str | None = None
    recipient: str | None = None
    draft: str | None = None
    why_now: str | None = None
    what_remains: tuple[str, ...] = ()
    recommended: str | None = None
    alternative: str | None = None
    wait_or_stop: str | None = None
    success: str | None = None
    do_nothing: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "what_remains", tuple(self.what_remains or ()))

    def shown(self) -> tuple[str, ...]:
        """The texts the founder reads, in the order a card is read."""
        return tuple(t for t in (self.headline, self.situation, self.why_now, *self.what_remains, self.recommended,
                                 self.alternative, self.wait_or_stop, self.draft, self.success, self.do_nothing)
                     if t)

    def as_mapping(self) -> dict[str, Any]:
        return {f.name: (list(getattr(self, f.name)) if f.name == "what_remains" else getattr(self, f.name))
                for f in fields(self)}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "CardText":
        return cls(**{f.name: raw.get(f.name) for f in fields(cls) if f.name in raw})


@dataclass(frozen=True, slots=True)
class Refusal:
    """One rule a card broke, and what it found."""
    rule: str
    found: str

    def __post_init__(self) -> None:
        if self.rule not in RULES:
            raise ValueError(f"a refusal names one of {RULES}, not {self.rule!r}")

    def as_mapping(self) -> dict[str, str]:
        return {"rule": self.rule, "found": self.found}

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "Refusal":
        return cls(rule=str(raw.get("rule") or ""), found=str(raw.get("found") or ""))


def _about_us(card: CardText, us: SelfIdentity, our_names: Iterable[str]) -> str | None:
    names = tuple(n for n in our_names if n)
    if card.subject and names_us(card.subject, us, names):
        return f"subject: {card.subject}"
    to = card.recipient
    if to and ((us.is_us(to) if "@" in to else names_us(to, us, names))):
        return f"recipient: {to}"
    return None


def _internal(texts: tuple[str, ...]) -> str | None:
    for t in texts:
        m = _FIELD.search(t) or _SLOT.search(t)
        if m:
            return m.group(0)
    return None


def _money(texts: tuple[str, ...], money_evidence: bool) -> str | None:
    if money_evidence:
        return None
    for t in texts:
        m = _MONEY.search(t)
        if m:
            return m.group(0)
    return None


def _quote(texts: tuple[str, ...], held: str) -> str | None:
    for t in texts:
        for m in _QUOTED.finditer(t):
            said = " ".join((m.group(1) or m.group(2) or "").split())
            if said and fold(said).lower() not in held:
                return said
    return None


def _number(texts: tuple[str, ...], nums: set[str]) -> str | None:
    for t in texts:
        unheld = sorted(digit_runs(t) - nums, key=lambda d: (t.find(d), d))
        if unheld:
            return unheld[0]
    return None


def check(card: CardText, *, us: SelfIdentity, our_names: Iterable[str] = (), quotes: Iterable[str] = (),
          corpus: Iterable[str] = (), money_evidence: bool = False) -> tuple[Refusal, ...]:
    """Every rule `card` breaks, once each, in the order of `RULES` — `()` when it may be shown. `quotes`: the words
    it may quote; `corpus`: what its words were made from (facts, quotes, the lines code computed); `money_evidence`:
    whether its evidence holds money."""
    texts = card.shown()
    quoted = [str(q) for q in quotes if q]
    held_text, nums = corpus_of([*quoted, *(str(c) for c in corpus if c)])
    held = fold(held_text).lower()
    found = {US: _about_us(card, us, our_names), INTERNAL: _internal(texts),
             MONEY: _money(texts, money_evidence), QUOTE: _quote(texts, held), NUMBER: _number(texts, nums)}
    return tuple(Refusal(rule, found[rule]) for rule in RULES if found[rule])


__all__ = ["CardText", "INTERNAL", "MONEY", "NUMBER", "QUOTE", "RULES", "Refusal", "US", "check"]
