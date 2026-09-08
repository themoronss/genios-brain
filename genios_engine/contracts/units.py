"""C-02 `Money` and C-03 `ResolvedDate` — the two dimensioned values Layer 1 may extract.

A number without its unit is not data, it is a rumour. Both types here exist to stop L1 from
handing an upper layer a bare `84000` or a bare timestamp, because every layer above then
propagates the missing dimension faithfully and confidently. The Globe Worked fault is
literally this: a card that said "$84K" against a contract that said "$8.4K" — a locale
decimal-separator bug that nothing normalized once, at the source.

Two rules are load-bearing, and both are enforced at construction rather than three layers
downstream where the damage is already rendered:

* **Money is never a float.** Integer minor units plus an ISO 4217 code. Binary floating point
  cannot hold 84000.10 exactly, and a cent that drifts inside a sum is a cent nobody can trace
  back to a source string. `as_written` keeps the literal text, so the card and the conflict
  display can show what was actually written rather than our reading of it.
* **A relative phrase is not a date.** "next week" is a RANGE plus a certainty; collapsing it
  to one timestamp invents precision the source never carried, and the deadline-proximity term
  of the importance formula (ALG-17) would then read invented urgency as real urgency.
  `resolved_against` records the `eval_time` the resolution ran against, so replaying a March
  event resolves "next week" against March instead of against today's clock.

Parsing lives elsewhere on purpose. ALG-10 (`capture/validate/money.py`) and ALG-09
(`capture/validate/dates.py`) own the string -> value cascades; this module owns only what a
value must be true of once it exists. That keeps the boundary vocabulary importable from
anywhere and leaves the normalizers free to change their heuristics without touching a
contract that other layers have already stored.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, field_validator, model_validator

from genios_engine.contracts.evidence import EvidenceSpan
from genios_engine.contracts.validators import require_aware

#: ISO 4217 alphabetic code. Anchored and uppercase-only: "usd" raises rather than being
#: title-cased for the caller, because a contract that quietly repairs its input is a contract
#: that lets a malformed value reach a human with the repair invisible.
ISO_4217 = re.compile(r"^[A-Z]{3}$")

#: The one non-ISO code `currency` accepts. ALG-10 step 1 is explicit — an ambiguous "$" with
#: no declared locale resolves to UNKNOWN and *never* defaults to USD, because guessing between
#: USD, CAD and AUD is how a 40% error enters a renewal number without anyone seeing a warning.
#: The amount is still worth keeping and surfacing; only the currency is missing.
#:
#: GAP FLAG (cross-doc): doc 08's C-02 validator states `^[A-Z]{3}$` while doc 05's ALG-10 hard
#: rule 2 mandates this literal seven-character sentinel. Enforcing the regex alone would make
#: the W1 normalizer unable to construct the very object it is told to return, so both forms
#: are accepted and the lowercase case still raises, which is what the regex was protecting.
UNKNOWN_CURRENCY = "UNKNOWN"


def _exact_int(value: Any, label: str) -> int:
    """A genuine `int` — not a bool, not a float pydantic would happily round on our behalf.

    Lax mode coerces `84000.0` to `84000` and `True` to `1`. Both satisfy the `int` annotation
    while quietly proving the opposite of what this module promises, and a float that survives
    one coercion is a float that reaches the ledger. Mirrors `validators.require_bp`, which
    refuses the same two inputs for the same reason and with the same exception type.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an exact integer, not {type(value).__name__}")
    return value


def _verbatim(value: Any, label: str) -> str:
    """Non-empty, and returned UNSTRIPPED.

    `validators.require_text` is the usual helper and is deliberately not used here: it strips,
    and the entire point of an `as_written` field is that it holds the source's bytes rather
    than ours. Empty still raises — a dimensioned value with no source string is a value nobody
    wrote, which is the definition of a fabricated one.
    """
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required — a value nobody wrote is a fabricated one")
    return value


class Money(BaseModel):
    """Integer minor units + an ISO code. Never a float, never a formatted string.

    `$84,000` -> `Money(minor_units=8_400_000, currency="USD", as_written="$84,000")`, and
    `"$84K"` -> the same amount carrying a different `as_written`. Normalization happens exactly
    once, at L1.5.3 (ALG-10); every layer above compares the integers and renders the string.
    """

    #: The amount in the currency's smallest unit — $84,000 -> 8_400_000, and ¥84,000 -> 84_000
    #: because JPY has a zero minor-unit exponent. Integer arithmetic end to end; the exponent
    #: table belongs to ALG-10, which is the only code allowed to do the multiplication.
    minor_units: int
    #: ISO 4217, uppercase, or `UNKNOWN_CURRENCY` when the symbol was ambiguous and the
    #: connection declared no locale. An unknown currency is recorded and surfaced, never
    #: defaulted.
    currency: str
    #: The literal source string. Kept for the card and for conflict display, so a user can see
    #: what was actually written next to what we made of it — the only way a normalization bug
    #: is visible to the person it would otherwise mislead. Never discarded after normalization.
    as_written: str

    @field_validator("minor_units", mode="before")
    @classmethod
    def _integer_only(cls, value: Any) -> int:
        return _exact_int(value, "minor_units")

    @field_validator("currency")
    @classmethod
    def _iso_code(cls, value: str) -> str:
        if value != UNKNOWN_CURRENCY and not ISO_4217.fullmatch(value):
            raise ValueError(
                f"currency must be an uppercase ISO 4217 code or {UNKNOWN_CURRENCY!r}, "
                f"got {value!r}")
        return value

    @field_validator("as_written")
    @classmethod
    def _source_string(cls, value: str) -> str:
        return _verbatim(value, "as_written")

    @property
    def currency_known(self) -> bool:
        """False when ALG-10 could not establish the currency. An amount whose currency is
        unknown is still worth showing and is never worth arithmetic."""
        return self.currency != UNKNOWN_CURRENCY

    def same_amount(self, other: Money) -> bool:
        """Value identity ignoring `as_written` — ALG-12's money comparison.

        "$84K" and "USD 84,000" are one amount written two ways; a conflict detector comparing
        the raw strings would report a disagreement between two sources that agree. Exact on
        both fields, with no percentage tolerance, and two currencies are never the same amount
        even when the integers match — 84,000 JPY is not 84,000 USD. Two UNKNOWN currencies
        compare equal on the integer alone, so a caller that needs certainty checks
        `currency_known` first rather than reading this as proof the sources agreed.
        """
        return self.minor_units == other.minor_units and self.currency == other.currency


class DateCertainty(str, Enum):
    """How much precision the source actually carried. Read this before reading the range."""

    #: An explicit date — "October 15, 2026", "Friday", "tomorrow". earliest == latest.
    EXACT = "exact"
    #: A bounded phrase — "next week", "end of month". The window is derived, not invented.
    RANGE = "range"
    #: "soon" / "shortly" / "later". The window is a heuristic guess (ALG-09 rows 9-10) and
    #: downstream must never treat it as a deadline.
    RELATIVE = "relative"
    #: Could not be resolved at all — an ambiguous numeric date with no declared locale, or a
    #: phrase no cascade row matched. earliest and latest are None; guessing is not an option.
    UNRESOLVED = "unresolved"


class ResolvedDate(BaseModel):
    """"Next week" is not a date — it is a range plus a certainty.

    *"Our renewal is coming up pretty soon"* is worthless as a string and dangerous as a
    fabricated timestamp, so this type refuses to be either. The window says when the thing
    could happen, `certainty` says how much of that window we derived versus guessed, and
    `resolved_against` pins the clock the derivation used so a replay resolves identically.
    """

    #: The literal phrase — "pretty soon", "by Friday". Same contract as `Money.as_written`:
    #: the source's bytes, retained so a wrong window is visible next to the words that produced
    #: it instead of silently replacing them.
    as_written: str
    #: Start of the window, tz-aware UTC, or None only when certainty is UNRESOLVED. No default:
    #: passing None must be a decision somebody typed, because a window that defaults itself to
    #: absent is a deadline that disappears without anyone choosing to drop it.
    earliest: datetime | None
    #: End of the window, on the same terms. For EXACT this equals `earliest`.
    latest: datetime | None
    certainty: DateCertainty
    #: The `eval_time` ALG-09 was handed. Required, never defaulted to `datetime.now()`: a clock
    #: read inside a contract makes replay non-deterministic, and "next week" resolved against a
    #: March event has to keep resolving to March forever.
    resolved_against: datetime
    #: Universal rule 4 — every claim carries its receipt. Non-empty is enforced below, because
    #: a date with no span behind it is a date the model produced rather than one a human wrote.
    evidence: list[EvidenceSpan]

    @field_validator("as_written")
    @classmethod
    def _source_string(cls, value: str) -> str:
        return _verbatim(value, "as_written")

    @field_validator("earliest", "latest")
    @classmethod
    def _aware_bound(cls, value: datetime | None, info: Any) -> datetime | None:
        """Tz-aware, normalised to UTC. ALG-09 resolves in the org's timezone and stores UTC; a
        naive datetime arriving here is an unanswered timezone question, and the silent offset it
        carries expresses itself later as a reminder that fires on the wrong day."""
        return None if value is None else require_aware(value, info.field_name)

    @field_validator("resolved_against")
    @classmethod
    def _aware_eval_time(cls, value: datetime) -> datetime:
        return require_aware(value, "resolved_against")

    @model_validator(mode="after")
    def _window_matches_certainty(self) -> ResolvedDate:
        """The certainty band and the window must tell the same story.

        Each branch closes a way of claiming precision the source never had: an EXACT date
        spanning nine days, an UNRESOLVED phrase that nonetheless carries a start, a RANGE with
        only half a window, or a window that runs backwards.
        """
        if self.certainty is DateCertainty.UNRESOLVED:
            if self.earliest is not None or self.latest is not None:
                raise ValueError(
                    "an UNRESOLVED date carries no window — earliest and latest must be None")
        elif self.earliest is None or self.latest is None:
            raise ValueError(
                f"{self.certainty.value} requires both earliest and latest; "
                "only UNRESOLVED may omit the window")
        elif self.certainty is DateCertainty.EXACT:
            if self.earliest != self.latest:
                raise ValueError(
                    "EXACT means a single instant — earliest and latest must be equal")
        elif self.earliest > self.latest:
            raise ValueError("earliest must not be later than latest")

        if not self.evidence:
            raise ValueError("a resolved date requires evidence — a claim with no receipt "
                             "is a guess")
        return self

    @property
    def window(self) -> tuple[datetime, datetime] | None:
        """The closed interval, or None when nothing was resolved. This is what ALG-17 reads for
        deadline proximity — a point value would hand it invented urgency."""
        if self.earliest is None or self.latest is None:
            return None
        return (self.earliest, self.latest)

    @property
    def date_in_past(self) -> bool:
        """The whole window closed before the eval_time it was resolved against (ALG-09 rule 6).

        Derived, never stored: a stored flag drifts out of agreement with the window after any
        correction, and there is nothing a field could know that `latest` and `resolved_against`
        do not already say. ALG-09 returns such a date as written and refuses to roll it forward
        — "the renewal was Friday", said on Monday, is a fact about a date that was missed, and
        advancing it to next Friday erases the only interesting thing about it.
        """
        return self.latest is not None and self.latest < self.resolved_against

    def overlaps(self, other: ResolvedDate) -> bool:
        """Do the two windows intersect? — ALG-12's date comparison.

        Closed intervals, so touching endpoints overlap: "by Friday" and "Friday" are one claim
        written twice. An UNRESOLVED date overlaps nothing, which is *not* the same as disagreeing
        with everything — a caller reads False as a conflict only once it has confirmed both
        `window`s exist. Silence about a deadline is not a competing claim about it.
        """
        mine, theirs = self.window, other.window
        if mine is None or theirs is None:
            return False
        return mine[0] <= theirs[1] and theirs[0] <= mine[1]


#: `15%` -> 1500, `7.5%` -> 750, `1/3` is NOT a ratio this parser accepts. Anchored, so a token
#: with anything else attached (`15%-20%`, `15%,`) does not silently parse as its first half — a
#: threshold read looser than it was written is an approval limit somebody could be held to.
_RATIO_TOKEN = re.compile(r"^(\d{1,3})(?:[.,](\d{1,2}))?\s*%$")


class Ratio(BaseModel):
    """A percentage threshold, in basis points. The dimension `Money` could not carry.

    **WHY THIS TYPE EXISTS.** *"A discount greater than 15% requires approval from the founder"*
    has a condition, a consequence and an authority — a rule by every clause of CLG-09's own
    definition, and `packs/brains/org_rule_extract`'s production prompt offers `20%` as a legal
    `threshold_as_written`. But `threshold_as_written` was validated by ALG-10, a MONEY parser,
    which answers `UNPARSEABLE_TOKEN` for `15%` — and `org_discovery.gate_candidates` refused the
    WHOLE RULE, not just the threshold. Discount authority is the most common approval rule a
    sales-led startup writes down, and the Organization brain could not hold one.

    **BASIS POINTS, FOR THE REASON MONEY IS MINOR UNITS.** `0.155` is not representable in binary
    floating point, and a threshold that drifts in the last place is one nobody can trace back to
    the sentence it came from. 15.5% is 1550, exactly, forever.

    **`as_written` IS NOT DECORATION.** Same contract as `Money.as_written`: the literal characters
    from the document, kept so a card can show what the policy said next to what we made of it.
    It is the only way a normalisation bug is visible to the person it would otherwise mislead.
    """

    #: 0..10000. A threshold above 100% is refused rather than clamped: it is a parse that went
    #: wrong, and clamping it to 10000 would turn a bug into a rule that always fires.
    basis_points: int
    #: The literal source string, e.g. `"15%"`.
    as_written: str

    @field_validator("basis_points", mode="before")
    @classmethod
    def _integer_only(cls, value: Any) -> int:
        result = _exact_int(value, "basis_points")
        if not 0 <= result <= 10_000:
            raise ValueError(f"basis_points must be 0..10000, got {result}")
        return result

    @field_validator("as_written")
    @classmethod
    def _source_string(cls, value: str) -> str:
        return _verbatim(value, "as_written")

    @property
    def percent_str(self) -> str:
        """`1550` -> `"15.5%"`. Rendering only; nothing compares against this."""
        whole, rest = divmod(self.basis_points, 100)
        return f"{whole}%" if rest == 0 else f"{whole}.{rest:02d}".rstrip("0") + "%"


def parse_ratio(as_written: Any) -> Ratio | None:
    """`"15%"` -> `Ratio(1500, "15%")`; anything else -> `None`.

    Deterministic and total: no model, no locale table, no cascade. A percentage is one of the few
    quantities that means the same thing in every locale a comma or a full stop can be written
    with, so `15,5%` and `15.5%` both resolve to 1550 without needing to know where the document
    came from — which is exactly the ambiguity that makes ALG-10's money cascade a locale problem.

    `None` rather than an exception: the caller is a gate that has a refusal vocabulary of its own,
    and a threshold this cannot read must land there rather than as a traceback.
    """
    if as_written is None:
        return None
    text = str(as_written).strip()
    match = _RATIO_TOKEN.match(text)
    if match is None:
        return None
    whole = int(match.group(1))
    fraction = (match.group(2) or "").ljust(2, "0")
    basis_points = whole * 100 + int(fraction)
    if basis_points > 10_000:
        # "150%" — a real string a document could contain, and not a threshold anyone approves
        # against. Refused, never clamped.
        return None
    return Ratio(basis_points=basis_points, as_written=text)


__all__ = ["ISO_4217", "UNKNOWN_CURRENCY", "DateCertainty", "Money", "Ratio", "ResolvedDate",
           "parse_ratio"]
