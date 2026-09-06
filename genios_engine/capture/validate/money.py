"""ALG-10 · L1.5.3-U1 — the one place a written amount becomes an integer.

The Globe Worked fault is literally this unit's absence: *"the card said $84K but the contract
said $8.4K"* — a locale decimal-separator bug. Nothing normalized the amount once, at the
source, so every layer above propagated the wrong number faithfully and confidently, and the
number that reached a human carried no trace of the string it came from. The fix is not a
smarter card. It is a single normalization point with three properties:

* **Integer arithmetic end to end.** There is no binary fraction anywhere in this module, not
  even transiently. The fractional digits are parsed as their own integer and folded in by a
  power-of-ten shift, because ``84.50`` scaled through a binary fraction is where a cent goes
  missing, and a cent that drifts inside a sum is a cent nobody can trace back to a source
  string. `Money` refuses a non-exact ``int`` at construction, so a slip here fails loudly.
* **Ambiguity returns nothing.** ``"84,000"`` with no declared locale is 84000 in en-US and
  84.000 in de-DE — a factor of a thousand. This module answers `None`, never a guess. Same
  for the symbol: an ambiguous ``$`` with no locale yields ``currency="UNKNOWN"``, retained and
  surfaced, and *never* defaulted to USD, because guessing between USD, CAD and AUD is how a
  40% error enters a renewal number with no warning attached to it.
* **The source string survives.** `Money.as_written` holds the caller's bytes verbatim, so a
  card can show what was actually written next to what we made of it, and ALG-12 can display
  both sides of a conflict in the words each source used.

Normalization is also the one place where repairing input is legitimate. `contracts/units.py`
deliberately refuses to title-case ``"usd"`` — a contract that quietly repairs its input lets a
malformed value reach a human with the repair invisible. This module runs *before* the
contract, and canonicalising a code the source wrote in lower case is exactly its job; what it
must never do is invent a currency, a separator convention, or a digit of precision.

Public surface:

    parse_money(as_written, *, locale)          -> Money | None      # ALG-10, the named entry
    parse_money_outcome(as_written, *, locale)  -> MoneyParse        # same, with a typed reason
    minor_unit_exponent(currency)               -> int               # ISO 4217, no dependency

PURE — no clock, no model, no database, no network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from genios_engine.contracts.units import UNKNOWN_CURRENCY, Money

# --------------------------------------------------------------------------------------------
# ISO 4217 minor-unit exponents (ALG-10 step 4)
# --------------------------------------------------------------------------------------------

#: Currencies with no minor unit. ¥84,000 is 84_000 minor units, not 8_400_000 — multiplying a
#: yen amount by 100 is a hundredfold error that looks entirely plausible on a card.
_EXPONENT_0 = frozenset({
    "JPY", "KRW", "VND", "CLP", "ISK", "PYG", "RWF", "UGX", "VUV",
    "XAF", "XOF", "XPF", "KMF", "DJF", "GNF", "BIF",
})

#: Three-decimal currencies. KWD 84.500 is 84_500 fils; treating it as two decimals loses a
#: factor of ten on every Gulf contract in the corpus.
_EXPONENT_3 = frozenset({"KWD", "BHD", "OMR", "JOD", "TND", "LYD", "IQD"})

#: Two-decimal currencies we are willing to *recognise as a currency at all*. The set is a
#: whitelist rather than "any three uppercase letters" on purpose: without it, ``"NET 84"``
#: reads as 84 units of a currency called NET, and a three-letter word next to a number is far
#: more common in email than an exotic ISO code is.
_EXPONENT_2 = frozenset({
    "USD", "EUR", "GBP", "INR", "CAD", "AUD", "NZD", "SGD", "HKD", "CHF", "CNY", "SEK",
    "NOK", "DKK", "PLN", "CZK", "HUF", "RON", "UAH", "RUB", "TRY", "ZAR", "BRL", "MXN",
    "ARS", "COP", "PEN", "AED", "SAR", "QAR", "ILS", "EGP", "NGN", "KES", "THB", "MYR",
    "IDR", "PHP", "TWD", "PKR", "LKR", "NPR", "BDT",
})

KNOWN_CURRENCIES = _EXPONENT_0 | _EXPONENT_2 | _EXPONENT_3

#: ALG-10 step 5. Above this an "amount" is a parse artefact — a phone number, an id, a
#: concatenation — and admitting it as money puts a fabricated figure at the top of every
#: sorted list in the product.
MAX_MINOR_UNITS = 10 ** 15


def minor_unit_exponent(currency: str) -> int:
    """Minor-unit exponent for an ISO 4217 code — 2 for USD, 0 for JPY, 3 for KWD.

    Shipped as a table rather than a dependency: the exceptions are a closed set that changes
    on a decade timescale, and a package that has to be installed to answer "does yen have
    cents" is a package that will one day not be installed in the worker that renders a card.
    Raises for anything unrecognised, including ``UNKNOWN_CURRENCY``, because the exponent for
    a currency nobody has identified is not 2 — it is unanswerable, and callers that need one
    must decide with `_currency_from_symbol`'s candidate logic instead of assuming.
    """
    if currency in _EXPONENT_0:
        return 0
    if currency in _EXPONENT_3:
        return 3
    if currency in _EXPONENT_2:
        return 2
    raise ValueError(f"no ISO 4217 minor-unit exponent known for {currency!r}")


# --------------------------------------------------------------------------------------------
# Currency markers (ALG-10 step 1)
# --------------------------------------------------------------------------------------------

#: Symbols that name exactly one currency in practice. ``£`` is listed here rather than as an
#: ambiguity because the other pound-family currencies write themselves differently (E£, ل.ل);
#: pretending ``£`` is ambiguous would return None for the single most common European amount.
_UNAMBIGUOUS_SYMBOL = {
    "€": "EUR", "£": "GBP", "₹": "INR", "₩": "KRW", "₪": "ILS", "₽": "RUB",
    "฿": "THB", "₺": "TRY", "₫": "VND", "₴": "UAH", "₦": "NGN", "₱": "PHP",
}

#: Symbols shared by several currencies, with the candidates spelled out. Resolution order is
#: locale first (step 1), then the exponent test in `_currency_from_symbol` — never a default.
_AMBIGUOUS_SYMBOL_CANDIDATES = {
    "$": ("USD", "CAD", "AUD", "NZD", "SGD", "HKD"),
    "¥": ("JPY", "CNY"),
    "RS": ("INR", "PKR", "LKR", "NPR"),
}

#: The connection's declared locale is what disambiguates a shared symbol. A tag that is not in
#: this map leaves the symbol ambiguous rather than falling back to the majority currency.
_SYMBOL_BY_LOCALE = {
    "$": {
        "EN-US": "USD", "EN-CA": "CAD", "FR-CA": "CAD", "EN-AU": "AUD", "EN-NZ": "NZD",
        "EN-SG": "SGD", "EN-HK": "HKD", "ZH-HK": "HKD", "ES-MX": "MXN",
    },
    "¥": {"JA-JP": "JPY", "ZH-CN": "CNY", "ZH-TW": "TWD"},
    "RS": {"EN-IN": "INR", "HI-IN": "INR", "UR-PK": "PKR", "SI-LK": "LKR", "TA-LK": "LKR",
           "NE-NP": "NPR"},
}

#: Words that mean "rupee-family symbol", folded onto the same ambiguity as ``₨``. "Rs 84,00,000"
#: is how the Indian corpus actually writes an amount; refusing the spelling would strand it.
_RUPEE_WORDS = frozenset({"RS", "RS.", "RUPEE", "RUPEES", "INR."})


# --------------------------------------------------------------------------------------------
# Multipliers (ALG-10 step 3)
# --------------------------------------------------------------------------------------------

#: Suffix -> power of ten. Both the western scale and the Indian one, because an org that writes
#: "84L" and an org that writes "$8.4M" are the same tenant on two different threads.
_MULTIPLIER = {
    "K": 3, "THOUSAND": 3, "THOUSANDS": 3,
    "M": 6, "MM": 6, "MN": 6, "MIL": 6, "MILLION": 6, "MILLIONS": 6,
    "B": 9, "BN": 9, "BILLION": 9, "BILLIONS": 9,
    "L": 5, "LAC": 5, "LACS": 5, "LAKH": 5, "LAKHS": 5,
    "CR": 7, "CRORE": 7, "CRORES": 7,
}


# --------------------------------------------------------------------------------------------
# Separator conventions (ALG-10 step 2 — the actual fix for the $84K/$8.4K class of bug)
# --------------------------------------------------------------------------------------------

#: (group separator, decimal separator) per grouping family.
_SEPARATORS = {
    "western": (",", "."),
    "indian": (",", "."),
    "euro": (".", ","),
    "french": (" ", ","),
    "swiss": ("'", "."),
}

#: Locale tag -> grouping family. en-IN shares western's separator *characters*; the lakh
#: grouping it adds is a difference in group widths, and group widths never change the value
#: (stripping separators yields the same digits either way), so the width check in
#: `_ungroup` accepts both shapes for every locale instead of branching here.
_LOCALE_FAMILY = {
    "EN-US": "western", "EN-GB": "western", "EN-CA": "western", "EN-AU": "western",
    "EN-NZ": "western", "EN-IE": "western", "EN-SG": "western", "EN-HK": "western",
    "EN-IN": "indian", "HI-IN": "indian", "TA-IN": "indian", "BN-IN": "indian",
    "UR-PK": "indian", "SI-LK": "indian", "NE-NP": "indian", "BN-BD": "indian",
    "JA-JP": "western", "ZH-CN": "western", "ZH-TW": "western", "ZH-HK": "western",
    "KO-KR": "western", "TH-TH": "western", "HE-IL": "western", "MS-MY": "western",
    "DE-DE": "euro", "DE-AT": "euro", "ES-ES": "euro", "ES-MX": "euro", "IT-IT": "euro",
    "NL-NL": "euro", "PT-BR": "euro", "PT-PT": "euro", "DA-DK": "euro", "TR-TR": "euro",
    "ID-ID": "euro", "VI-VN": "euro", "RO-RO": "euro",
    "FR-FR": "french", "FR-CA": "french", "RU-RU": "french", "SV-SE": "french",
    "PL-PL": "french", "CS-CZ": "french", "NB-NO": "french", "FI-FI": "french",
    "UK-UA": "french",
    "DE-CH": "swiss", "FR-CH": "swiss", "IT-CH": "swiss",
}

#: Language-only tags. Safe because every region under each of these writes the same way; a
#: language whose regions disagree (e.g. "es", "en" would if en-IN did not share characters
#: with en-US) is deliberately absent, and an absent tag means "locale unknown", not "guess".
_LANGUAGE_FAMILY = {
    "EN": "western", "JA": "western", "ZH": "western", "KO": "western", "TH": "western",
    "HE": "western", "MS": "western",
    "DE": "euro", "IT": "euro", "NL": "euro", "PT": "euro", "DA": "euro", "TR": "euro",
    "ID": "euro", "RO": "euro", "VI": "euro",
    "FR": "french", "RU": "french", "SV": "french", "PL": "french", "CS": "french",
    "NB": "french", "FI": "french", "UK": "french",
    "HI": "indian",
}

#: Separators that can never be a decimal point in any locale, so their presence is decidable
#: without a locale at all. This is what lets "84 000" parse with locale=None.
_GROUP_ONLY = frozenset({" ", "'", "’"})

#: Every space-ish code point a mail client may have emitted, folded to a plain space before
#: any separator reasoning runs — otherwise a narrow no-break space reads as an unknown symbol
#: and a perfectly good French amount is rejected.
_SPACE_FOLD = {ord(ch): " " for ch in (" ", " ", " ", " ", "\t")}

#: A run of digits possibly interrupted by separators. Anchored on digits at both ends so a
#: trailing sentence period or a leading "Rs." never lands inside the number.
_NUMERIC_CORE = re.compile(r"\d[\d ,.'’]*\d|\d")

#: Prefix/suffix tokens: a word, or a single non-word character (symbol, sign, bracket).
_TOKEN = re.compile(r"[A-Za-z]+\.?|[^\sA-Za-z0-9]")


class MoneyParseFailure(str, Enum):
    """Why ALG-10 refused. A reason, not an exception: an unparseable amount is an ordinary
    outcome of reading human text, and the extractor keeps the span as a structural token
    rather than aborting the event. Every member is a case where answering would mean guessing.
    """

    #: Nothing to parse.
    EMPTY = "empty"
    #: No digits in the string at all.
    NO_DIGITS = "no_digits"
    #: Two or more separate numbers — a range like "$84,000-$90,000". Which one is *the* amount
    #: is a question for the extractor, not for the normalizer.
    MULTIPLE_AMOUNTS = "multiple_amounts"
    #: A token that is neither a currency marker nor a multiplier ("about", "per seat").
    UNPARSEABLE_TOKEN = "unparseable_token"
    #: A bare number. ALG-10's failure table is explicit: "84" with no currency is not a `Money`,
    #: it stays a bare number in structural_tokens.
    NO_CURRENCY_MARKER = "no_currency_marker"
    #: Two different currencies in one amount ("USD 84,000 EUR").
    CONFLICTING_CURRENCY = "conflicting_currency"
    #: The $84K/$8.4K bug, caught: one separator, three digits after it, and no locale to say
    #: whether it groups or divides. The answers differ by 1000x, so there is no safe default.
    AMBIGUOUS_SEPARATOR = "ambiguous_separator"
    #: Separators that do not form a valid number under the declared convention ("84,0000").
    MALFORMED_GROUPING = "malformed_grouping"
    #: An ambiguous symbol whose candidates disagree on the minor-unit exponent — ``¥`` is JPY
    #: (0) or CNY (2), so even `UNKNOWN_CURRENCY` cannot carry an honest integer.
    AMBIGUOUS_MINOR_EXPONENT = "ambiguous_minor_exponent"
    #: More precision than the currency has, with a non-zero digit in the excess ("$84.567").
    #: Rounding here would be inventing or destroying money.
    FRACTIONAL_PRECISION = "fractional_precision"
    #: More than one multiplier ("84K M").
    MULTIPLE_MULTIPLIERS = "multiple_multipliers"
    #: Beyond `MAX_MINOR_UNITS` (ALG-10 step 5).
    OUT_OF_RANGE = "out_of_range"


@dataclass(frozen=True, slots=True)
class MoneyParse:
    """The outcome of one ALG-10 run: exactly one of `money` or `failure` is set.

    `parse_money` is the signature the plan names and it collapses this to ``Money | None``.
    This richer form exists because the caller that stores a parked amount, and the QA lane that
    asks *why* the corpus lost 3% of its numbers, both need the reason — and a reason that only
    exists in a log line cannot be asserted on.
    """

    money: Money | None
    failure: MoneyParseFailure | None

    def __post_init__(self) -> None:
        if (self.money is None) == (self.failure is None):
            raise ValueError("a MoneyParse carries exactly one of money or failure")

    @property
    def ok(self) -> bool:
        return self.money is not None


def parse_money(as_written: str, *, locale: str | None) -> Money | None:
    """ALG-10 — normalise a written amount to integer minor units, or refuse.

    ``"$84,000"`` and ``"$84K"`` produce equal `Money` values carrying different `as_written`,
    which is the whole contract: upper layers compare integers and render strings. Returns None
    for every case where an answer would be a guess; see `MoneyParseFailure` for which.
    """
    return parse_money_outcome(as_written, locale=locale).money


def parse_money_outcome(as_written: str, *, locale: str | None) -> MoneyParse:
    """`parse_money` with the refusal reason attached. See `MoneyParse`."""
    if not isinstance(as_written, str) or not as_written.strip():
        return MoneyParse(None, MoneyParseFailure.EMPTY)

    text = as_written.translate(_SPACE_FOLD).strip()
    negative = False

    # Accounting negation. Done before tokenising so the brackets never reach the token loop,
    # where they would read as unparseable punctuation.
    if text.startswith("(") and text.endswith(")"):
        negative = True
        text = text[1:-1].strip()

    cores = _NUMERIC_CORE.findall(text)
    if not cores:
        return MoneyParse(None, MoneyParseFailure.NO_DIGITS)
    if len(cores) > 1:
        return MoneyParse(None, MoneyParseFailure.MULTIPLE_AMOUNTS)

    core = cores[0]
    start = text.index(core)
    prefix, suffix = text[:start], text[start + len(core):]
    # A sentence's punctuation is not part of the amount; a currency code might be, so only the
    # closing marks are shed.
    suffix = suffix.rstrip(" .;:!?")

    markers = _Markers()
    for segment, is_suffix in ((prefix, False), (suffix, True)):
        failure = _read_tokens(segment, is_suffix=is_suffix, markers=markers)
        if failure is not None:
            return MoneyParse(None, failure)
    negative = negative or markers.negative

    tag = _canonical_locale(locale)

    # The number is resolved before the currency on purpose: "84,000" with no locale is
    # unreadable *and* uncurrencied, and AMBIGUOUS_SEPARATOR is the reason a reader needs — it
    # names the 1000x question, where NO_CURRENCY_MARKER would suggest a missing symbol was the
    # only thing wrong with the string.
    digits = _split_number(core, _family_for(tag))
    if isinstance(digits, MoneyParseFailure):
        return MoneyParse(None, digits)
    integer_digits, fraction_digits = digits

    resolved = _resolve_currency(markers, tag)
    if isinstance(resolved, MoneyParseFailure):
        return MoneyParse(None, resolved)
    currency, exponent = resolved

    minor = _to_minor_units(
        integer_digits + fraction_digits,
        fraction_len=len(fraction_digits),
        multiplier=markers.multiplier,
        exponent=exponent,
    )
    if isinstance(minor, MoneyParseFailure):
        return MoneyParse(None, minor)
    if minor > MAX_MINOR_UNITS:
        return MoneyParse(None, MoneyParseFailure.OUT_OF_RANGE)

    # `as_written` is the caller's original bytes, not `text` — the folded spaces and the
    # stripped brackets are our reading of the source, and the card must show the source.
    return MoneyParse(
        Money(minor_units=-minor if negative else minor,
              currency=currency,
              as_written=as_written),
        None,
    )


# --------------------------------------------------------------------------------------------
# internals
# --------------------------------------------------------------------------------------------


@dataclass(slots=True)
class _Markers:
    """What the non-numeric tokens said: at most one currency code, one symbol, one multiplier.

    Collected rather than applied on sight so that ``"US$ 84 USD"`` can be checked for agreement
    instead of resolved twice, and so a second multiplier is an error rather than a silent
    overwrite that multiplies by the wrong power of ten.
    """

    code: str | None = None
    symbol: str | None = None
    multiplier: int = 0
    negative: bool = False
    conflict: bool = False


def _read_tokens(segment: str, *, is_suffix: bool, markers: _Markers) -> MoneyParseFailure | None:
    """Classify everything that is not the number itself, refusing anything unrecognised.

    Failing closed on an unknown token is what keeps ``"$84 per seat"`` from being stored as a
    total contract value: the amount is real but the sentence says it is a rate, and a
    normalizer that drops the words it does not understand is a normalizer that changes the
    meaning of the number it returns.
    """
    for token in _TOKEN.findall(segment):
        if token in ("-", "−", "–"):
            if markers.negative:
                return MoneyParseFailure.UNPARSEABLE_TOKEN
            markers.negative = True
            continue
        if token == "+":
            continue
        if token in _UNAMBIGUOUS_SYMBOL or token in _AMBIGUOUS_SYMBOL_CANDIDATES:
            _set_symbol(markers, token)
            continue
        if token == "₨":  # the rupee sign, same ambiguity as the spelled-out "Rs"
            _set_symbol(markers, "RS")
            continue
        if not token[0].isalpha():
            return MoneyParseFailure.UNPARSEABLE_TOKEN

        word = token.upper()
        if word in _RUPEE_WORDS:
            _set_symbol(markers, "RS")
            continue
        bare = word.rstrip(".")
        if bare in KNOWN_CURRENCIES:
            if markers.code is not None and markers.code != bare:
                markers.conflict = True
            markers.code = bare
            continue
        if is_suffix and bare in _MULTIPLIER:
            if markers.multiplier:
                return MoneyParseFailure.MULTIPLE_MULTIPLIERS
            markers.multiplier = _MULTIPLIER[bare]
            continue
        return MoneyParseFailure.UNPARSEABLE_TOKEN
    return None


def _set_symbol(markers: _Markers, symbol: str) -> None:
    if markers.symbol is not None and markers.symbol != symbol:
        markers.conflict = True
    markers.symbol = symbol


def _resolve_currency(markers: _Markers, tag: str | None) -> tuple[str, int] | MoneyParseFailure:
    """ALG-10 step 1 — code beats symbol, locale disambiguates a shared symbol, nothing defaults.

    The one non-obvious branch is the last: when a shared symbol survives with no locale, the
    amount is still worth keeping, so the currency becomes `UNKNOWN_CURRENCY` — *provided* the
    candidates agree on the minor-unit exponent. ``$`` candidates all have two decimals, so the
    integer is honest and only the label is missing. ``¥`` candidates do not (JPY 0, CNY 2), so
    there is no integer to store and the parse fails instead of picking a scale.
    """
    if markers.conflict:
        return MoneyParseFailure.CONFLICTING_CURRENCY

    if markers.code is not None:
        if markers.symbol is not None and not _symbol_allows(markers.symbol, markers.code):
            return MoneyParseFailure.CONFLICTING_CURRENCY
        return markers.code, minor_unit_exponent(markers.code)

    if markers.symbol is None:
        return MoneyParseFailure.NO_CURRENCY_MARKER

    symbol = markers.symbol
    if symbol in _UNAMBIGUOUS_SYMBOL:
        code = _UNAMBIGUOUS_SYMBOL[symbol]
        return code, minor_unit_exponent(code)

    by_locale = _SYMBOL_BY_LOCALE[symbol]
    if tag is not None and tag in by_locale:
        code = by_locale[tag]
        return code, minor_unit_exponent(code)

    exponents = {minor_unit_exponent(c) for c in _AMBIGUOUS_SYMBOL_CANDIDATES[symbol]}
    if len(exponents) != 1:
        return MoneyParseFailure.AMBIGUOUS_MINOR_EXPONENT
    return UNKNOWN_CURRENCY, exponents.pop()


def _symbol_allows(symbol: str, code: str) -> bool:
    """Does an explicit code agree with the symbol standing next to it? ``$84 USD`` agrees;
    ``€84 USD`` does not, and reporting that as a conflict is better than silently preferring
    one of two contradictory statements the source made about its own currency."""
    if symbol in _UNAMBIGUOUS_SYMBOL:
        return _UNAMBIGUOUS_SYMBOL[symbol] == code
    return code in _AMBIGUOUS_SYMBOL_CANDIDATES[symbol]


def _canonical_locale(locale: str | None) -> str | None:
    """``"en_us"`` -> ``"EN-US"``. Case and the underscore form are connection-configuration
    noise, not a claim about the amount, so folding them is safe; an unrecognised tag is *not*
    folded to anything and simply leaves the locale unknown, which fails closed."""
    if locale is None:
        return None
    tag = locale.strip().replace("_", "-").upper()
    return tag or None


def _family_for(tag: str | None) -> str | None:
    """Grouping family for a locale tag, or None when the locale is unknown or unrecognised.

    An unrecognised tag deliberately degrades to None rather than raising: the worst outcome is
    that an ambiguous string returns None instead of a value, whereas guessing a family for a
    typo'd tag reintroduces exactly the separator bug this unit exists to prevent.
    """
    if tag is None:
        return None
    if tag in _LOCALE_FAMILY:
        return _LOCALE_FAMILY[tag]
    return _LANGUAGE_FAMILY.get(tag.split("-")[0])


def _split_number(core: str, family: str | None) -> tuple[str, str] | MoneyParseFailure:
    """ALG-10 step 2 — decide which separators group and which one divides, then split.

    Returns ``(integer digits, fraction digits)`` as *strings of digits*, deliberately: the
    fractional part is folded in later by a power-of-ten shift on an integer, so it must never
    be scaled on its own. With a locale the convention is read from the table; without one, only
    the decidable cases are answered — a lone separator followed by exactly three digits is the
    $84K/$8.4K bug in miniature and returns AMBIGUOUS_SEPARATOR rather than a number.
    """
    seps = {ch for ch in core if not ch.isdigit()}
    if not seps:
        return core, ""

    if family is not None:
        group_char, decimal_char = _SEPARATORS[family]
        if not seps <= ({group_char, decimal_char} | _GROUP_ONLY):
            return MoneyParseFailure.MALFORMED_GROUPING
        has_decimal = decimal_char in seps and decimal_char not in _GROUP_ONLY
    else:
        undecided = seps & {".", ","}
        if not seps <= ({".", ","} | _GROUP_ONLY):
            return MoneyParseFailure.MALFORMED_GROUPING
        if not undecided:
            decimal_char, has_decimal = "", False
        elif len(undecided) == 2:
            # Both characters present: the rightmost one divides, the other groups. No locale
            # needed — "84.000,50" and "84,000.50" each state their own convention.
            decimal_char = "." if core.rindex(".") > core.rindex(",") else ","
            has_decimal = True
        else:
            decimal_char = undecided.pop()
            if core.count(decimal_char) > 1:
                has_decimal = False  # repeated -> it groups; a decimal point appears once
            elif seps & _GROUP_ONLY:
                has_decimal = True  # grouping is already accounted for by the spaces
            elif len(core.split(decimal_char)[1]) == 3:
                return MoneyParseFailure.AMBIGUOUS_SEPARATOR
            else:
                has_decimal = True

    if has_decimal:
        if core.count(decimal_char) != 1:
            return MoneyParseFailure.MALFORMED_GROUPING
        integer_part, fraction_part = core.split(decimal_char)
        if not fraction_part.isdigit():
            return MoneyParseFailure.MALFORMED_GROUPING
    else:
        integer_part, fraction_part = core, ""

    ungrouped = _ungroup(integer_part)
    if isinstance(ungrouped, MoneyParseFailure):
        return ungrouped
    return ungrouped, fraction_part


def _ungroup(integer_part: str) -> str | MoneyParseFailure:
    """Strip thousands separators, refusing shapes no convention produces.

    Group widths never change the value — ``8,400,000`` and ``84,00,000`` both ungroup to
    8400000 — so this check is about well-formedness, not arithmetic, and it accepts the western
    (3) and Indian (2) widths together instead of branching on locale. What it rejects is
    ``84,0000``: a four-digit group means the separator was not grouping, and parsing it anyway
    would return a number no reading of the source supports.
    """
    used = {ch for ch in integer_part if not ch.isdigit()}
    if not used:
        return integer_part or MoneyParseFailure.MALFORMED_GROUPING
    if len(used) > 1:
        return MoneyParseFailure.MALFORMED_GROUPING

    groups = integer_part.split(used.pop())
    if not 1 <= len(groups[0]) <= 3 or not groups[0].isdigit():
        return MoneyParseFailure.MALFORMED_GROUPING
    for group in groups[1:-1]:
        if len(group) not in (2, 3) or not group.isdigit():
            return MoneyParseFailure.MALFORMED_GROUPING
    if len(groups[-1]) != 3 or not groups[-1].isdigit():
        return MoneyParseFailure.MALFORMED_GROUPING
    return "".join(groups)


def _to_minor_units(
    digits: str, *, fraction_len: int, multiplier: int, exponent: int
) -> int | MoneyParseFailure:
    """ALG-10 step 4 — one integer, shifted once, by a power of ten.

    ``8.4K`` in USD is ``84`` shifted by ``3 + 2 - 1 = 4`` -> 840_000, and ``84K`` is ``84``
    shifted by ``3 + 2 - 0 = 5`` -> 8_400_000: the two cannot collide because the fractional
    digit is part of the integer and the shift already accounts for it. When the shift is
    negative the source stated more precision than the currency has, and the division must be
    exact — ``$84.500`` is 8450 minor units, but ``$84.567`` is money we would have to round, so
    it is refused. Rounding is how a cent goes missing without anyone choosing to lose it.
    """
    value = int(digits)
    shift = multiplier + exponent - fraction_len
    if shift >= 0:
        return value * 10 ** shift
    divisor = 10 ** -shift
    whole, remainder = divmod(value, divisor)
    if remainder:
        return MoneyParseFailure.FRACTIONAL_PRECISION
    return whole


__all__ = [
    "KNOWN_CURRENCIES",
    "MAX_MINOR_UNITS",
    "MoneyParse",
    "MoneyParseFailure",
    "minor_unit_exponent",
    "parse_money",
    "parse_money_outcome",
]
