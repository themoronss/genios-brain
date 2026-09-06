"""G1 · ALG-10 amount parsing (L1.5.3-U1) — the money half of the pure-validator gate.

    pytest tests/capture/validate/test_money.py -q

The suite is a table with one row per format the plan names, and it is built to make exactly
three failures impossible to ship:

* **A locale separator bug.** ``$84.000`` is $84.00 in en-US and €84,000 in de-DE — the same
  eleven characters, a thousandfold apart. That pair is asserted directly, and so is the
  refusal to answer when no locale was declared. This is the Globe Worked fault, written as a
  test rather than as a post-mortem.
* **A defaulted currency.** Every ambiguous-symbol row asserts `UNKNOWN`, never USD.
* **A lost cent.** Nothing here checks "the module looks pure"; the rows assert the exact
  integer, and `Money` itself rejects a non-exact int at construction, so any binary fraction
  that appeared even transiently in ALG-10 would surface as a `ValidationError` in these rows
  rather than as a rounding difference three layers up. The source grep is the belt to that
  pair of braces, and it asserts an ABSENCE — the one thing a source-text assertion is good for.

`parse_money` returns None for everything it cannot answer honestly, so the failure table
asserts the typed reason from `parse_money_outcome` instead: a suite that only checked for None
would pass just as happily if every string failed for the wrong reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import ValidationError

from genios_engine.capture.validate import money as money_module
from genios_engine.capture.validate.money import (
    KNOWN_CURRENCIES,
    MAX_MINOR_UNITS,
    MoneyParse,
    MoneyParseFailure,
    minor_unit_exponent,
    parse_money,
    parse_money_outcome,
)
from genios_engine.contracts.units import UNKNOWN_CURRENCY, Money

WAVE = "W1"
GATE = "G1"

pytestmark = pytest.mark.unit

NBSP = " "


@dataclass(frozen=True)
class Row:
    """One written amount, the locale it was written under, and the only answer we accept."""

    written: str
    locale: str | None
    minor_units: int
    currency: str
    why: str


PARSED: tuple[Row, ...] = (
    # --- the plan's own acceptance rows ------------------------------------------------------
    Row("$84K", "en-US", 8_400_000, "USD", "K multiplier"),
    Row("$8.4K", "en-US", 840_000, "USD", "K on a fractional value — must not collide with 84K"),
    Row("$84,000", "en-US", 8_400_000, "USD", "thousands separator"),
    Row("84.000,50 EUR", "de-DE", 8_400_050, "EUR", "de-DE grouping, code after the amount"),
    Row("₹84,00,000", "en-IN", 840_000_000, "INR", "Indian lakh grouping"),
    Row("¥84000", "ja-JP", 84_000, "JPY", "zero minor-unit exponent"),
    Row("$84", None, 8_400, "UNKNOWN", "ambiguous symbol, no locale — retained, never USD"),
    # --- separators ---------------------------------------------------------------------------
    Row("$84,000.50", "en-US", 8_400_050, "USD", "en-US group and decimal together"),
    Row("$8,400,000", "en-US", 840_000_000, "USD", "repeated group separator"),
    Row("$84.000", "en-US", 8_400, "USD", "en-US: the dot divides"),
    Row("€84.000", "de-DE", 8_400_000, "EUR", "de-DE: the same dot groups"),
    Row("€84,50", "de-DE", 8_450, "EUR", "de-DE decimal comma"),
    Row("84 000,50 EUR", "fr-FR", 8_400_050, "EUR", "fr-FR space grouping"),
    Row(f"84{NBSP}000 EUR", "fr-FR", 8_400_000, "EUR", "no-break space as a group separator"),
    Row("CHF 84'000.50", "de-CH", 8_400_050, "CHF", "Swiss apostrophe grouping"),
    Row("$84 000", None, 8_400_000, "UNKNOWN", "a space can never divide, so no locale is needed"),
    Row("INR 74,00,000", None, 740_000_000, "INR", "two groups decide it without a locale"),
    Row("$8.4", None, 840, "UNKNOWN", "one dot, one digit after it — decidable without a locale"),
    Row("€84.000,50", None, 8_400_050, "EUR", "both separators present: the rightmost divides"),
    Row("€84,000.50", None, 8_400_050, "EUR", "and the other way round"),
    # --- multipliers ---------------------------------------------------------------------------
    Row("$84k", "en-US", 8_400_000, "USD", "lower-case k"),
    Row("$1.5M", "en-US", 150_000_000, "USD", "M on a fractional value"),
    Row("$84 million", "en-US", 8_400_000_000, "USD", "spelled-out multiplier"),
    Row("$2bn", "en-US", 200_000_000_000, "USD", "bn"),
    Row("₹84L", "en-IN", 840_000_000, "INR", "L = lakh"),
    Row("₹8.4Cr", "en-IN", 8_400_000_000, "INR", "Cr = crore"),
    Row("Rs. 5 crore", "en-IN", 5_000_000_000, "INR", "spelled-out crore, Rs. resolved by locale"),
    Row("84 lakh INR", "en-IN", 840_000_000, "INR", "multiplier between the number and the code"),
    Row("84K USD", "en-US", 8_400_000, "USD", "multiplier and code both after the number"),
    Row("₹84,00,000.50", "en-IN", 840_000_050, "INR", "lakh grouping with a decimal part"),
    # --- currency markers ----------------------------------------------------------------------
    Row("USD 84,000", "en-US", 8_400_000, "USD", "code before"),
    Row("84,000 USD", "en-US", 8_400_000, "USD", "code after"),
    Row("usd 84,000", "en-US", 8_400_000, "USD", "lower-case code, canonicalised before Money"),
    Row("$84,000 USD", "en-US", 8_400_000, "USD", "symbol and code that agree"),
    Row("Rs 84,00,000", "en-IN", 840_000_000, "INR", "Rs resolved by locale"),
    Row("Rs 84,00,000", None, 840_000_000, "UNKNOWN", "Rs candidates share an exponent"),
    Row("£84,000", "en-GB", 8_400_000, "GBP", "£ names one currency in practice"),
    Row("84000 JPY", None, 84_000, "JPY", "explicit code carries the exponent"),
    Row("KWD 84.500", "en-US", 84_500, "KWD", "three minor digits"),
    Row("KWD 84", "en-US", 84_000, "KWD", "exponent 3 with no fraction"),
    Row("¥84,000", "ja-JP", 84_000, "JPY", "grouping under a zero-exponent currency"),
    # --- precision and sign ---------------------------------------------------------------------
    Row("$84.50", "en-US", 8_450, "USD", "ordinary cents"),
    Row("$84.500", "en-US", 8_450, "USD", "excess precision that is all zeros loses nothing"),
    Row("$0.99", "en-US", 99, "USD", "under one unit"),
    Row("-$84K", "en-US", -8_400_000, "USD", "leading minus"),
    Row("($84,000)", "en-US", -8_400_000, "USD", "accounting parentheses"),
    Row("$84,000-", "en-US", -8_400_000, "USD", "trailing minus"),
    Row("$84,000.", "en-US", 8_400_000, "USD", "sentence punctuation is not part of the amount"),
)


FAILURES: tuple[tuple[str, str | None, MoneyParseFailure, str], ...] = (
    ("84,000", None, MoneyParseFailure.AMBIGUOUS_SEPARATOR,
     "84000 or 84.000 — a factor of 1000, and no locale to decide"),
    ("$84,000", None, MoneyParseFailure.AMBIGUOUS_SEPARATOR,
     "a known symbol does not tell you the writer's separator convention"),
    ("$84.000,50", "en-US", MoneyParseFailure.MALFORMED_GROUPING,
     "a de-DE amount under an en-US locale — the Globe fault, refused instead of read"),
    ("$84,0000", "en-US", MoneyParseFailure.MALFORMED_GROUPING, "no convention groups by four"),
    ("$84,00,000", "de-DE", MoneyParseFailure.MALFORMED_GROUPING,
     "comma is the decimal point in de-DE and cannot appear twice"),
    ("84", None, MoneyParseFailure.NO_CURRENCY_MARKER, "a bare number is not money"),
    ("84,000.50", "en-US", MoneyParseFailure.NO_CURRENCY_MARKER,
     "still bare even when the separators are unambiguous"),
    ("¥84000", None, MoneyParseFailure.AMBIGUOUS_MINOR_EXPONENT,
     "JPY has no minor unit and CNY has two, so UNKNOWN cannot carry an honest integer"),
    ("$84.567", "en-US", MoneyParseFailure.FRACTIONAL_PRECISION,
     "rounding here would be inventing or destroying money"),
    ("$1.234", "en-US", MoneyParseFailure.FRACTIONAL_PRECISION,
     "under en-US the dot divides, so this is three decimals and not 1234"),
    ("JPY 84.5", "ja-JP", MoneyParseFailure.FRACTIONAL_PRECISION,
     "yen has no minor unit, so half a yen is not a storable amount"),
    ("$84,000-$90,000", "en-US", MoneyParseFailure.MULTIPLE_AMOUNTS,
     "which end of a range is the amount is not a normalizer's question"),
    ("$84 per seat", "en-US", MoneyParseFailure.UNPARSEABLE_TOKEN,
     "a rate is not a total, and dropping the words would change the meaning"),
    ("NET 84", "en-US", MoneyParseFailure.UNPARSEABLE_TOKEN,
     "a three-letter word next to a number is not a currency code"),
    ("USD 84,000 EUR", "en-US", MoneyParseFailure.CONFLICTING_CURRENCY, "two codes"),
    ("€84 USD", "en-US", MoneyParseFailure.CONFLICTING_CURRENCY, "symbol contradicts the code"),
    ("$84K M", "en-US", MoneyParseFailure.MULTIPLE_MULTIPLIERS, "two multipliers"),
    ("$99999999999999999", "en-US", MoneyParseFailure.OUT_OF_RANGE,
     "an id or a phone number, not an amount"),
    ("", None, MoneyParseFailure.EMPTY, "nothing to parse"),
    ("   ", None, MoneyParseFailure.EMPTY, "whitespace only"),
    ("$", "en-US", MoneyParseFailure.NO_DIGITS, "a symbol with no number"),
)


def _row_id(row: Row) -> str:
    return f"{row.written}@{row.locale}"


@pytest.mark.gate
@pytest.mark.parametrize("row", PARSED, ids=_row_id)
def test_written_amount_normalises_to_exact_minor_units(row: Row) -> None:
    """One row per format the plan names — exact integer, exact currency, verbatim source."""
    result = parse_money(row.written, locale=row.locale)

    assert result is not None, f"{row.written!r} ({row.why}) should parse"
    assert result.minor_units == row.minor_units, row.why
    assert result.currency == row.currency, row.why
    assert result.as_written == row.written, "as_written must be the source's bytes, not ours"
    # A binary fraction anywhere upstream arrives here as a non-exact int, which `Money` would
    # have refused at construction; asserting the runtime type keeps that guarantee visible.
    assert type(result.minor_units) is int


@pytest.mark.gate
@pytest.mark.parametrize(
    ("written", "locale", "expected", "why"),
    FAILURES,
    ids=[f"{w}@{loc}" for w, loc, _, _ in FAILURES],
)
def test_unanswerable_amounts_refuse_with_a_typed_reason(
    written: str, locale: str | None, expected: MoneyParseFailure, why: str
) -> None:
    """Ambiguity returns nothing, and says why. None with the wrong reason is still a bug."""
    outcome = parse_money_outcome(written, locale=locale)

    assert outcome.money is None, f"{written!r} ({why}) must not produce a Money"
    assert outcome.failure is expected, why
    assert parse_money(written, locale=locale) is None


def test_eighty_four_k_and_eighty_four_thousand_are_one_amount() -> None:
    """THE rule: two spellings, one value, both source strings preserved.

    `Money.__eq__` compares `as_written` too, so the objects are deliberately NOT equal — the
    equality that matters downstream is `same_amount`, which is what ALG-12 compares. A conflict
    detector using object equality would report a disagreement between two sources that agree.
    """
    compact = parse_money("$84K", locale="en-US")
    grouped = parse_money("$84,000", locale="en-US")

    assert compact is not None and grouped is not None
    assert compact.minor_units == grouped.minor_units == 8_400_000
    assert compact.currency == grouped.currency == "USD"
    assert compact.same_amount(grouped)
    assert compact.as_written != grouped.as_written
    assert compact != grouped, "the value is shared; the source string is not"


def test_eight_point_four_k_never_collides_with_eighty_four_k() -> None:
    """The Globe Worked fault as a single assertion: $84K and $8.4K are 1000x apart."""
    big = parse_money("$84K", locale="en-US")
    small = parse_money("$8.4K", locale="en-US")

    assert big is not None and small is not None
    assert big.minor_units == 8_400_000
    assert small.minor_units == 840_000
    assert big.minor_units == small.minor_units * 10
    assert not big.same_amount(small)


def test_same_digits_two_locales_two_answers_and_no_locale_no_answer() -> None:
    """``84.000`` is $84.00 under en-US and €84,000 under de-DE.

    The declared locale is load-bearing, not decoration, and with no locale the only honest
    answer is None. This is the exact shape of the bug that made a card say $84K against a
    contract that said $8.4K.
    """
    us = parse_money("$84.000", locale="en-US")
    de = parse_money("€84.000", locale="de-DE")

    assert us is not None and de is not None
    assert us.minor_units == 8_400
    assert de.minor_units == 8_400_000
    assert de.minor_units == us.minor_units * 1000

    assert parse_money("$84.000", locale=None) is None


def test_indian_lakh_grouping_is_read_as_lakhs_not_as_thousands() -> None:
    """``74,00,000`` is seventy-four lakh — 7.4 million, not 74 thousand.

    Asserted on both the symbol and the code spelling because the Indian corpus writes it both
    ways, and on `en-IN` and no locale alike: two group separators decide the shape on their own.
    """
    for written in ("INR 74,00,000", "₹74,00,000"):
        for locale in ("en-IN", None):
            parsed = parse_money(written, locale=locale)
            assert parsed is not None, (written, locale)
            assert parsed.minor_units == 7_400_000_00, (written, locale)
            assert parsed.currency == "INR", (written, locale)


def test_ambiguous_symbol_is_retained_as_unknown_and_never_defaulted() -> None:
    """ALG-10 hard rule 2. The amount survives; the currency is marked missing, not invented."""
    parsed = parse_money("$84K", locale=None)

    assert parsed is not None
    assert parsed.currency == UNKNOWN_CURRENCY
    assert parsed.currency_known is False
    assert parsed.minor_units == 8_400_000

    # A locale is the only thing that turns the symbol into a currency, and different locales
    # turn it into different ones — which is precisely why a default would be a 40% error.
    assert parse_money("$84K", locale="en-US").currency == "USD"
    assert parse_money("$84K", locale="en-AU").currency == "AUD"
    assert parse_money("$84K", locale="en-CA").currency == "CAD"
    # An unrecognised tag degrades to "no locale", never to a guess.
    assert parse_money("$84K", locale="xx-YY").currency == UNKNOWN_CURRENCY


def test_lowercase_currency_code_is_refused_by_the_contract() -> None:
    """`Money` never repairs its input — a contract that quietly title-cases lets a malformed
    value reach a human with the repair invisible. ALG-10 canonicalises BEFORE construction, so
    ``"usd 84,000"`` parses to USD while a hand-built lowercase `Money` still raises."""
    with pytest.raises(ValidationError):
        Money(minor_units=8_400_000, currency="usd", as_written="usd 84,000")

    parsed = parse_money("usd 84,000", locale="en-US")
    assert parsed is not None and parsed.currency == "USD"


@pytest.mark.parametrize("row", PARSED, ids=_row_id)
def test_every_emitted_currency_is_a_code_the_table_knows(row: Row) -> None:
    """No parse may emit a currency that is neither ISO 4217 nor the UNKNOWN sentinel — that is
    how a symbol-detection bug would otherwise reach storage as a three-character label."""
    parsed = parse_money(row.written, locale=row.locale)

    assert parsed is not None
    assert parsed.currency == parsed.currency.upper()
    assert parsed.currency in KNOWN_CURRENCIES or parsed.currency == UNKNOWN_CURRENCY


def test_minor_unit_exponents_follow_iso_4217() -> None:
    """Two decimals is the common case, not the universal one. Multiplying a yen amount by 100
    is a hundredfold error that looks entirely plausible on a card."""
    assert minor_unit_exponent("USD") == 2
    assert minor_unit_exponent("EUR") == 2
    assert minor_unit_exponent("INR") == 2
    assert minor_unit_exponent("JPY") == 0
    assert minor_unit_exponent("KRW") == 0
    assert minor_unit_exponent("KWD") == 3
    assert minor_unit_exponent("BHD") == 3

    # UNKNOWN has no exponent — answering 2 for it is the guess this unit exists to refuse.
    with pytest.raises(ValueError):
        minor_unit_exponent(UNKNOWN_CURRENCY)
    with pytest.raises(ValueError):
        minor_unit_exponent("ZZZ")


def test_range_check_admits_the_boundary_and_rejects_beyond_it() -> None:
    """ALG-10 step 5 — above the cap an "amount" is a parse artefact, and admitting one puts a
    fabricated figure at the top of every sorted list in the product."""
    at_cap = parse_money("$10,000,000,000,000.00", locale="en-US")
    assert at_cap is not None and at_cap.minor_units == MAX_MINOR_UNITS

    beyond = parse_money_outcome("$10,000,000,000,000.01", locale="en-US")
    assert beyond.money is None
    assert beyond.failure is MoneyParseFailure.OUT_OF_RANGE


def test_outcome_carries_exactly_one_of_money_or_failure() -> None:
    """The type makes "parsed, but also failed" unrepresentable, so no caller has to check both."""
    ok = parse_money_outcome("$84K", locale="en-US")
    assert ok.ok and ok.failure is None

    bad = parse_money_outcome("84,000", locale=None)
    assert not bad.ok
    assert bad.money is None and bad.failure is not None

    with pytest.raises(ValueError):
        MoneyParse(None, None)
    with pytest.raises(ValueError):
        MoneyParse(ok.money, MoneyParseFailure.EMPTY)


def test_as_written_is_kept_verbatim_including_surrounding_whitespace() -> None:
    """The card shows what the source wrote next to what we made of it; stripping the string
    here would quietly edit the evidence a user is meant to check us against."""
    written = "  $84,000  "
    parsed = parse_money(written, locale="en-US")

    assert parsed is not None
    assert parsed.as_written == written
    assert parsed.minor_units == 8_400_000


@pytest.mark.gate
def test_module_source_contains_no_binary_fraction_no_clock_and_no_model() -> None:
    """The G1 gate greps the SOURCE, so this asserts an absence rather than a behaviour.

    A validator that reads a clock cannot be replayed, a validator that calls a model is not a
    validator, and a validator that touches binary fractions has already lost the cent it was
    checking. Each of those is a property no single input can prove, which is why the gate looks
    at the file — and why this is the only assertion in the suite that reads source text.
    """
    source = Path(money_module.__file__).read_text(encoding="utf-8")

    for forbidden in ("float(", "datetime.now", "date.today", "time.time",
                      "LLMClient", "anthropic", "Decimal", "psycopg", "requests.", "httpx"):
        assert forbidden not in source, f"{forbidden!r} must not appear in ALG-10"
