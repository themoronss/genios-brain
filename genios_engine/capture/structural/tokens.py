"""ALG-04 · L1.3.5 — the Structural Parser: find and count, never interpret.

The one genuinely new component in S1, and the one S2 and S4 both depend on. Its job is to
record, with offsets, every token that is *objectively present* in the cleaned text, so that
three consumers can stop asking a language model for facts a regex already knows:

1. **ALG-05, the model tier router** — `currency_token` and `date_string` counts decide T1/T2/T3.
   *"This went to Opus because it had 4 currency tokens and 3 date strings"* is a sentence
   somebody can check; *"the model felt it was complex"* is not.
2. **ALG-12, the conflict detector** — needs the literal numbers the source contained, to see
   whether the model invented the one it reported.
3. **L1.5.1, the span validator** — an amount the model claims must correspond to a token
   found here.

**Find, do not interpret.** `$84K` is recorded as a `currency_token` with `raw="$84K"` at its
offsets. It is NOT parsed. Turning it into `Money(8_400_000, "USD")` belongs to ALG-10 in
`capture/validate/money.py` and must happen after the model has spoken, so that the claim and
the literal are two comparable objects. A parser that helpfully resolved the value here would
destroy the only artefact the conflict detector has to compare against, and the Globe fault —
a card reading "$84K" against a contract that said "$8.4K" — is exactly a comparison nobody
could make.

**Offsets round-trip, by construction.** Every `raw` is sliced out of the source at the
offsets the token carries, so `clean_text[t.start_offset:t.end_offset] == t.raw` is not a
promise this module keeps by discipline — it is the only way a token is built. Gate G2 asserts
zero round-trip failures across the pilot corpus, because an offset map that drifts is worse
than no offset map: every `EvidenceSpan` above it inherits the drift and still reports itself
as verified.

**Tokens may overlap; counts may not double-count.** `Oct 15, 2026` is a `date_string`, and
`2026` inside it is also a `bare_number`. Both are emitted — a consumer looking for literals
wants both — but `counts` charges only the OUTERMOST span at each position, because the tier
router adds a fixed score per counted token and an inflated count buys a more expensive model
for a document that did not earn it. See `_count_by_span`.

**Linear-time patterns only.** Every rule in `_RULES` is written so that no quantifier can
nest inside another quantifier over the same alphabet: repeated groups always require a
separator character the inner class cannot match, which makes the split deterministic. An
ingest stall caused by catastrophic backtracking is a silent, total outage of the capture
lane, and it arrives on whatever unlucky message happens to contain the pathological string.

**Identifier patterns are tenant-configurable and are NEVER a module constant.** Every company
numbers its invoices differently; a hardcoded `INV-\\d+` finds nothing at most tenants and
gives false confidence at the rest. `scan` takes them as a parameter, `compile_identifier_pattern`
validates a tenant's regex for linear-time execution *before* it is stored, and
`SAMPLE_IDENTIFIER_PATTERNS` is a starter set a tenant may adopt explicitly — never a default
that applies behind their back.

Public surface:

    scan(clean_text, *, identifier_patterns)     -> StructuralTokens    # L1.3.5-U1
    router_counts(tokens)                        -> RouterCounts        # L1.3.5-U2
    compile_identifier_pattern(name, regex)      -> IdentifierPattern   # L1.3.5-U3

PURE — no clock, no model, no database, no network, no float.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Sequence

# --------------------------------------------------------------------------------------------
# Token types — the vocabulary every consumer keys on
# --------------------------------------------------------------------------------------------

TOKEN_URL = "url"
TOKEN_EMAIL_ADDRESS = "email_address"
TOKEN_FILE_REF = "file_ref"
TOKEN_IDENTIFIER = "identifier"
TOKEN_PHONE = "phone"
TOKEN_TIME_STRING = "time_string"
TOKEN_DATE_STRING = "date_string"
TOKEN_DURATION_STRING = "duration_string"
TOKEN_PERCENTAGE = "percentage"
TOKEN_CURRENCY_TOKEN = "currency_token"
TOKEN_BARE_NUMBER = "bare_number"

#: Precedence order, most specific first. Two things read this order and nothing else does:
#: `counts` (an outer span suppresses the spans nested inside it, and among identical spans the
#: earlier type wins) and the emission order of `StructuralTokens.tokens` at equal offsets.
TOKEN_TYPES: tuple[str, ...] = (
    TOKEN_URL,
    TOKEN_EMAIL_ADDRESS,
    TOKEN_FILE_REF,
    TOKEN_IDENTIFIER,
    TOKEN_PHONE,
    TOKEN_TIME_STRING,
    TOKEN_DATE_STRING,
    TOKEN_DURATION_STRING,
    TOKEN_PERCENTAGE,
    TOKEN_CURRENCY_TOKEN,
    TOKEN_BARE_NUMBER,
)


@dataclass(frozen=True)
class StructuralToken:
    """One objectively present token and where it sits. `raw` is always the source's own
    characters at `[start_offset:end_offset]` — never a cleaned, trimmed or normalized form,
    because the whole point of the offsets is that a reader can go and look."""

    token_type: str
    raw: str
    start_offset: int
    end_offset: int


@dataclass(frozen=True)
class StructuralTokens:
    """Everything ALG-04 found, plus the de-duplicated counts ALG-05 consumes.

    `counts` always carries every key in `TOKEN_TYPES`, zeros included: a router that has to
    write `counts.get("currency_token", 0)` is a router where a missing key and a genuine zero
    are the same value, and a typo in the key name is invisible."""

    tokens: tuple[StructuralToken, ...]
    counts: Mapping[str, int]


@dataclass(frozen=True)
class RouterCounts:
    """L1.3.5-U2 — the counts in the exact shape ALG-05 reads them.

    Deliberately narrow: the tier table names `currency_token_count` and `date_token_count`
    and nothing else from S1 (content length, attachment presence, profile, thread depth and
    `internal_kind` all reach the router from elsewhere). `by_type` carries the rest for the
    audit trail, so a tier decision can be explained without re-scanning the document."""

    currency_token_count: int
    date_token_count: int
    by_type: Mapping[str, int]


@dataclass(frozen=True)
class IdentifierPattern:
    """One tenant's identifier format, already validated and compiled.

    Constructed only through `compile_identifier_pattern` — the validation is the point, and a
    tenant-supplied regex that reached `scan` unchecked is a tenant-supplied denial of service
    against every other tenant on the box."""

    name: str
    regex: str
    matcher: re.Pattern[str]


class UnsafeIdentifierPattern(ValueError):
    """A tenant pattern that must not be stored: it does not compile, it can backtrack
    catastrophically, or it matches the empty string."""


# --------------------------------------------------------------------------------------------
# Shared fragments
# --------------------------------------------------------------------------------------------

#: Digit-group separators seen in the corpus: period, comma, NBSP, narrow NBSP, thin space.
#: A PLAIN space is deliberately absent — "12 3" is two numbers in English far more often than
#: it is one French one, and a scanner that joined them would report a bare number that no
#: reader can find in the text.
_GROUP_SEP = r"[.,   ]"

#: One written number, separators and all: `84`, `84,000`, `84.000,50`, `84,00,000`. Each
#: repetition must consume a separator the digit class cannot match, so the split is
#: deterministic and the pattern is linear.
#: The repetition is BOUNDED at twelve groups. Unbounded, a failing match on 40KB of "1," has
#: to try every possible number of groups at every start position, which is quadratic — the
#: linearity row measures it. No written number has thirteen separated groups.
_NUM = rf"\d+(?:{_GROUP_SEP}\d+){{0,12}}"

#: Scale suffixes. `$84K` is a currency token whose raw text includes the K — resolving what
#: the K multiplies by is ALG-10's job, not this module's.
_SCALE = r"(?:\s?(?:[KkMmBb]|bn|mn|lakhs?|crores?|thousand|million|billion)\b)?"

#: Currency symbols, including the ones that actually appear in this product's corpus (₹ above
#: all). `$` is retained as written and never resolved to USD anywhere in S1.
_SYMBOLS = "$€£¥₹₩₪₺₦฿₫₴₽"

#: A CURATED scan list, not ISO 4217. `money.KNOWN_CURRENCIES` is the full set and is right for
#: PARSING a string somebody already decided is money; using it here would make "ALL 5 items"
#: (ALL = Albanian lek) a currency token, and an inflated currency count moves the tier router.
#: Longer literals first so the alternation cannot settle for a prefix.
_CURRENCY_CODES = (
    "USD", "EUR", "GBP", "INR", "JPY", "AUD", "CAD", "CHF", "SGD", "AED", "SAR", "CNY",
    "HKD", "NZD", "SEK", "NOK", "DKK", "ZAR", "BRL", "MXN", "KRW", "THB", "IDR", "MYR",
    "PHP", "PLN", "TRY", "ILS", "RUB", "KWD", "BHD", "OMR", "Rs",
)
_CODE_ALT = "|".join(_CURRENCY_CODES)

_MONTHS = (
    "january", "february", "march", "april", "may", "june", "july", "august", "september",
    "october", "november", "december",
    "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sept", "sep", "oct", "nov", "dec",
)
_MONTH_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))

#: FULL weekday names only for the bare form. "Sat", "Mar" and "May" are ordinary English words
#: as often as they are dates, and every false date token nudges the tier router toward a model
#: the document did not earn. The abbreviations are admitted only after `next`/`this`/`last`,
#: where the phrase is unambiguous.
_WEEKDAYS_FULL = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_WEEKDAYS_SHORT = ("mon", "tues", "tue", "weds", "wed", "thurs", "thur", "thu", "fri", "sat", "sun")
_WEEKDAY_FULL_ALT = "|".join(_WEEKDAYS_FULL)
_WEEKDAY_ANY_ALT = "|".join(sorted(_WEEKDAYS_FULL + _WEEKDAYS_SHORT, key=len, reverse=True))

#: A closed set of timezone abbreviations. An open `[A-Z]{2,5}` would swallow "3pm ASAP" into
#: the token, and a raw string that reads as nonsense destroys the reader's trust in the
#: offsets that produced it.
_TZ_ALT = ("IST|UTC|GMT|EST|EDT|CST|CDT|MST|MDT|PST|PDT|CET|CEST|BST|JST|SGT|AEST|AEDT|"
           "NZST|NZDT|HST|AKST|MSK|CAT|EAT|WAT|SAST")

_NUMBER_WORDS = ("a", "an", "one", "two", "three", "four", "five", "six", "seven", "eight",
                 "nine", "ten", "eleven", "twelve", "couple of", "few")
_NUMBER_WORD_ALT = "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True))

_DURATION_UNITS = ("business days", "business day", "working days", "working day",
                   "days", "day", "weeks", "week", "months", "month", "years", "year",
                   "hours", "hour", "minutes", "minute", "mins", "min")
_DURATION_UNIT_ALT = "|".join(_DURATION_UNITS)

_FILE_EXTENSIONS = ("pdf", "docx", "doc", "xlsx", "xls", "pptx", "ppt", "csv", "txt", "md",
                    "png", "jpeg", "jpg", "gif", "zip", "json", "xml", "html", "htm", "eml",
                    "msg", "key", "pages", "numbers")
_EXT_ALT = "|".join(sorted(_FILE_EXTENSIONS, key=len, reverse=True))

#: Bare-domain TLDs. Kept short and closed on purpose: an open `[a-z]{2,}` turns "e.g" and
#: "i.e" into URLs. Longest first so `.com` is never matched as `.co`.
_TLDS = ("info", "test", "dev", "app", "com", "org", "net", "edu", "gov", "biz", "xyz",
         "ai", "io", "co", "in", "uk", "de", "fr", "jp", "au", "ca", "us", "me")
_TLD_ALT = "|".join(sorted(_TLDS, key=len, reverse=True))

#: Characters that end a sentence rather than a URL. Trimmed off the tail of a URL match, with
#: unbalanced closing brackets, so `(see https://x.com/a)` records `https://x.com/a`.
_URL_TAIL_PUNCT = ".,;:!?'\"“”’"
_URL_CLOSERS = {")": "(", "]": "[", "}": "{", ">": "<"}


def _rules() -> tuple[tuple[str, re.Pattern[str]], ...]:
    """The ordered ALG-04 ruleset. Built in a function so the fragments above stay readable and
    so the ordering — which `counts` depends on — is stated once, in one list."""
    return (
        (TOKEN_URL, re.compile(r"(?<![\w@.])(?:https?://|www\.)[^\s<>\"'`]+")),
        # Bare domain. The label is ONE quantifier over a class that cannot match the dot that
        # separates labels, and the number of labels is bounded: the earlier, prettier
        # `[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?` form let a label be split more than one
        # way, and on 40KB of "a.b-" that is exponential. A domain with nine labels is not a
        # domain we are missing.
        (TOKEN_URL, re.compile(
            rf"(?<![\w@.-])(?:[A-Za-z0-9-]{{1,63}}\.){{1,8}}"
            rf"(?:{_TLD_ALT})(?![A-Za-z0-9-])(?:/[^\s<>\"'`]*)?")),
        (TOKEN_EMAIL_ADDRESS, re.compile(
            r"(?<![\w.+-])[A-Za-z0-9_%+-]+(?:\.[A-Za-z0-9_%+-]+){0,8}"
            r"@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63}){0,8}"
            r"\.[A-Za-z]{2,24}\b")),
        # The separator class is DISJOINT from the name class, and holds no space. Sharing `_`
        # and `-` between the two made "a_b_c…" partitionable in exponentially many ways, and
        # admitting a space made "Attached proposal_v2.pdf" one filename beginning with
        # "Attached". A file whose name contains a space is recorded from its last word.
        (TOKEN_FILE_REF, re.compile(
            rf"(?<![\w.])[A-Za-z0-9]+(?:[._-][A-Za-z0-9]+){{0,8}}\.(?:{_EXT_ALT})\b",
            re.IGNORECASE)),
        (TOKEN_PHONE, re.compile(
            r"(?<![\w/.])\+\d{1,3}[\s.-]?\(?\d{2,4}\)?(?:[\s.-]?\d{2,5}){1,4}(?!\d)")),
        (TOKEN_PHONE, re.compile(r"(?<![\w/.])\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)")),
        (TOKEN_TIME_STRING, re.compile(
            rf"(?<![\d:])\d{{1,2}}:\d{{2}}(?::\d{{2}})?(?:\s?[APap]\.?[Mm]\.?)?"
            rf"(?:\s(?:{_TZ_ALT}))?(?![\d:])")),
        (TOKEN_TIME_STRING, re.compile(
            rf"(?<![\d:])\d{{1,2}}\s?[APap]\.?[Mm]\.?(?:\s(?:{_TZ_ALT}))?\b")),
        (TOKEN_DATE_STRING, re.compile(r"(?<![\d-])\d{4}-\d{1,2}-\d{1,2}(?![\d-])")),
        (TOKEN_DATE_STRING, re.compile(r"(?<![\d/.-])\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}(?![\d/.-])")),
        (TOKEN_DATE_STRING, re.compile(
            rf"\b(?:{_MONTH_ALT})\.?\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?\b",
            re.IGNORECASE)),
        (TOKEN_DATE_STRING, re.compile(
            rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?(?:{_MONTH_ALT})\.?(?:,?\s+\d{{4}})?\b",
            re.IGNORECASE)),
        (TOKEN_DATE_STRING, re.compile(
            rf"\b(?:next|last|this|coming)\s+(?:{_WEEKDAY_ANY_ALT}|week|month|quarter|year)\b",
            re.IGNORECASE)),
        (TOKEN_DATE_STRING, re.compile(rf"\b(?:{_WEEKDAY_FULL_ALT})\b", re.IGNORECASE)),
        (TOKEN_DATE_STRING, re.compile(r"\b(?:today|tonight|tomorrow|yesterday)\b", re.IGNORECASE)),
        (TOKEN_DATE_STRING, re.compile(
            r"\b(?:end|start|beginning)\s+of\s+(?:the\s+)?(?:day|week|month|quarter|year)\b",
            re.IGNORECASE)),
        (TOKEN_DURATION_STRING, re.compile(
            rf"\b\d+\s?-?\s?(?:{_DURATION_UNIT_ALT})\b", re.IGNORECASE)),
        (TOKEN_DURATION_STRING, re.compile(
            rf"\b(?:{_NUMBER_WORD_ALT})\s+(?:{_DURATION_UNIT_ALT})\b", re.IGNORECASE)),
        (TOKEN_DURATION_STRING, re.compile(r"\b(?:Q[1-4]|H[12])(?:\s?(?:FY)?\d{2,4})?\b")),
        (TOKEN_DURATION_STRING, re.compile(r"\bFY\s?\d{2,4}\b", re.IGNORECASE)),
        (TOKEN_PERCENTAGE, re.compile(rf"(?<![\w.,]){_NUM}\s?%")),
        (TOKEN_PERCENTAGE, re.compile(
            rf"(?<![\w.,]){_NUM}\s?(?:percent|pct|per cent)\b", re.IGNORECASE)),
        (TOKEN_CURRENCY_TOKEN, re.compile(rf"[{re.escape(_SYMBOLS)}]\s?{_NUM}{_SCALE}")),
        (TOKEN_CURRENCY_TOKEN, re.compile(
            rf"(?<![A-Za-z])(?:{_CODE_ALT})\.?\s?{_NUM}{_SCALE}")),
        (TOKEN_CURRENCY_TOKEN, re.compile(
            rf"(?<![\w.,]){_NUM}{_SCALE}\s?(?:{_CODE_ALT})\b")),
        (TOKEN_BARE_NUMBER, re.compile(rf"(?<![\w.,]){_NUM}(?![\d])")),
    )


_COMPILED_RULES = _rules()

#: A starter set a tenant may adopt EXPLICITLY. It is not a default and `scan` never reaches
#: for it: the whole reason U3 exists is that a hardcoded identifier pattern finds nothing at
#: most tenants, and a default that silently applies is a hardcoded pattern wearing a
#: configuration's clothes.
SAMPLE_IDENTIFIER_PATTERNS: tuple[tuple[str, str], ...] = (
    ("invoice", r"\bINV[-/ ]?\d{2,6}(?:[-/]\d{2,6})*\b"),
    ("purchase_order", r"\bPO[-/ ]?\d{3,10}\b"),
    ("ticket", r"\b[A-Z]{2,6}-\d{1,6}\b"),
    ("contract", r"\b(?:MSA|SOW|NDA)[-/ ]?\d{2,8}\b"),
)


# --------------------------------------------------------------------------------------------
# L1.3.5-U3 · tenant-configurable identifier patterns
# --------------------------------------------------------------------------------------------

#: Longest tenant regex we will store. A pattern longer than this is a program, and a program
#: is not something we can reason about the runtime of.
MAX_IDENTIFIER_PATTERN_CHARS = 400

#: Largest bounded repetition a tenant may ask for. `{1,5000}` on a group is not catastrophic
#: backtracking but it is still thousands of steps per start position on every message.
MAX_IDENTIFIER_REPEAT = 100


class _PatternRejected(Exception):
    """Internal: the analyser found a shape it will not store. Carries the human reason."""


@dataclass(frozen=True)
class _Fragment:
    """What the analyser knows about one piece of a tenant regex.

    `has_variable_quantifier` — somewhere inside, a quantifier can match a variable number of
    repetitions. `anchored` — EVERY alternative of this piece contains at least one mandatory,
    fixed-length atom, which is the property that makes a repeated group unambiguous: the
    engine cannot re-partition a run of input across iterations when every iteration has to
    consume a specific character it can only find once."""

    has_variable_quantifier: bool
    anchored: bool


_ZERO_WIDTH_ESCAPES = frozenset("bBAZ")
_MAX_ANALYSIS_DEPTH = 20


def _parse_quantifier(regex: str, i: int) -> tuple[int, int | None, int | None]:
    """Read a quantifier at `i`. Returns `(next_index, minimum, maximum)`; `(i, None, None)`
    when there is no quantifier there, and `maximum=None` for an unbounded one. A `{` that is
    not a well-formed repetition is an ordinary literal brace, which is what `re` does too."""
    if i >= len(regex):
        return i, None, None
    ch = regex[i]
    if ch in "*+?":
        low, high = {"*": (0, None), "+": (1, None), "?": (0, 1)}[ch]
        j = i + 1
        if j < len(regex) and regex[j] in "?+":         # lazy / possessive modifier
            j += 1
        return j, low, high
    if ch != "{":
        return i, None, None
    close = regex.find("}", i)
    if close == -1:
        return i, None, None
    body = regex[i + 1:close]
    if not re.fullmatch(r"\d+(?:,\d*)?", body):
        return i, None, None
    low_text, _, high_text = body.partition(",")
    low = int(low_text)
    high = None if (_ and not high_text) else int(high_text or low_text)
    if low > MAX_IDENTIFIER_REPEAT or (high is not None and high > MAX_IDENTIFIER_REPEAT):
        raise _PatternRejected(f"repetition {{{body}}} exceeds {MAX_IDENTIFIER_REPEAT}")
    j = close + 1
    if j < len(regex) and regex[j] in "?+":
        j += 1
    return j, low, high


def _skip_class(regex: str, i: int) -> int:
    """Index just past the character class starting at `i`. Quantifiers inside a class are
    literal characters, so the class is opaque to the rest of the analysis."""
    j = i + 1
    if j < len(regex) and regex[j] == "^":
        j += 1
    if j < len(regex) and regex[j] == "]":
        j += 1
    while j < len(regex) and regex[j] != "]":
        j += 2 if regex[j] == "\\" else 1
    if j >= len(regex):
        raise _PatternRejected("unterminated character class")
    return j + 1


def _parse_alternation(regex: str, i: int, depth: int) -> tuple[int, _Fragment]:
    """Parse `alt|alt|alt` until `)` or the end of the pattern."""
    if depth > _MAX_ANALYSIS_DEPTH:
        raise _PatternRejected("nested more than "
                               f"{_MAX_ANALYSIS_DEPTH} groups deep")
    variable = False
    anchored = True
    while True:
        i, frag = _parse_sequence(regex, i, depth)
        variable = variable or frag.has_variable_quantifier
        anchored = anchored and frag.anchored             # every alternative must be anchored
        if i < len(regex) and regex[i] == "|":
            i += 1
            continue
        return i, _Fragment(has_variable_quantifier=variable, anchored=anchored)


def _parse_sequence(regex: str, i: int, depth: int) -> tuple[int, _Fragment]:
    """Parse one alternative: a run of atoms, each with an optional quantifier."""
    variable = False
    anchored = False
    n = len(regex)
    while i < n and regex[i] not in "|)":
        ch = regex[i]
        consuming = True
        inner: _Fragment | None = None
        if ch == "(":
            j = i + 1
            lookaround = False
            if regex.startswith("(?", i):
                if regex.startswith("(?P<", i):
                    j = regex.index(">", i) + 1 if ">" in regex[i:] else n
                elif regex.startswith("(?P=", i):
                    raise _PatternRejected("named backreference")
                elif regex.startswith("(?:", i):
                    j = i + 3
                elif regex.startswith(("(?=", "(?!"), i):
                    j, lookaround = i + 3, True
                elif regex.startswith(("(?<=", "(?<!"), i):
                    j, lookaround = i + 4, True
                elif regex.startswith("(?#", i):
                    raise _PatternRejected("inline comment group")
                else:                                      # inline flags, e.g. (?i)
                    close = regex.find(")", i)
                    if close == -1:
                        raise _PatternRejected("unbalanced (")
                    i = close + 1
                    continue
            j, inner = _parse_alternation(regex, j, depth + 1)
            if j >= n or regex[j] != ")":
                raise _PatternRejected("unbalanced (")
            i = j + 1
            consuming = not lookaround
        elif ch == "[":
            i = _skip_class(regex, i)
        elif ch == "\\":
            nxt = regex[i + 1] if i + 1 < n else ""
            if nxt.isdigit() and nxt != "0":
                raise _PatternRejected(f"backreference \\{nxt}")
            consuming = nxt not in _ZERO_WIDTH_ESCAPES
            i += 2
        elif ch in "^$":
            consuming = False
            i += 1
        else:
            i += 1
        i, low, high = _parse_quantifier(regex, i)
        quantified = low is not None
        varies = quantified and (high is None or high != low)
        variable = variable or varies
        if inner is not None and varies and inner.has_variable_quantifier and not inner.anchored:
            raise _PatternRejected(
                "nested quantifier: a repeated group whose body can match the same text in "
                "more than one way")
        if inner is not None:
            variable = variable or inner.has_variable_quantifier
        # A mandatory, fixed-length atom is what anchors a repetition. `a+` is mandatory but
        # variable-length, so it anchors nothing; `x` and `x{3}` do.
        if consuming and (not quantified or (low == high and low > 0)):
            if inner is None or inner.anchored:
                anchored = True
    return i, _Fragment(has_variable_quantifier=variable, anchored=anchored)


def _unsafe_reason(regex: str) -> str | None:
    """Return why this regex must not be stored, or None if it is safe to run on every message.

    The check is STATIC, and it is static on purpose: the alternative is timing a trial run,
    and a clock read in this package would be a lie about what `structural/` is — G1 greps the
    directory, not the suite. What it looks for is the shape that actually explodes: a
    quantified group whose body is itself variable AND carries no mandatory fixed atom to
    anchor each iteration — `(a+)+` and its disguises — plus backreferences, which turn
    matching into a search no linearity argument survives.

    `(?:[-/]\\d{2,6})*` passes, and it must: every iteration has to consume a literal
    separator that `\\d` cannot match, so there is exactly one way to partition any input and
    the match is linear. That pattern is what a real invoice format looks like, and an
    analyser that refused it would push tenants toward looser patterns, not safer ones.

    Known limitation, stated rather than hidden: alternation ambiguity inside a repeated group
    (`(?:ab|a)+`) is not detected. It is quadratic rather than exponential, and detecting it
    needs a full NFA-equivalence check.
    """
    try:
        i, _ = _parse_alternation(regex, 0, 0)
    except _PatternRejected as exc:
        return str(exc)
    if i != len(regex):
        return "unbalanced )"
    return None


def compile_identifier_pattern(name: str, regex: str) -> IdentifierPattern:
    """L1.3.5-U3 — validate one tenant identifier pattern and compile it.

    Called at WRITE time, before the row lands in `tenant_identifier_patterns`. A pattern is
    refused if it does not compile, if it can match the empty string (which would emit
    zero-width tokens whose offsets point at nothing), or if it carries the shape that
    backtracks catastrophically. Refusal is loud: an `UnsafeIdentifierPattern` at
    configuration time is a form somebody has to fix, whereas the same pattern stored and
    reached on a Tuesday is an ingest lane that stops without an error.

    Raises `UnsafeIdentifierPattern` — never returns a disabled pattern, because a pattern
    that is present and inert is indistinguishable from one that finds nothing.
    """
    label = name.strip()
    if not label:
        raise UnsafeIdentifierPattern("identifier pattern needs a name")
    if not regex:
        raise UnsafeIdentifierPattern(f"{label!r}: empty pattern")
    if len(regex) > MAX_IDENTIFIER_PATTERN_CHARS:
        raise UnsafeIdentifierPattern(
            f"{label!r}: pattern is {len(regex)} chars, limit is {MAX_IDENTIFIER_PATTERN_CHARS}")
    if (reason := _unsafe_reason(regex)) is not None:
        raise UnsafeIdentifierPattern(f"{label!r}: {reason}")
    try:
        matcher = re.compile(regex)
    except re.error as exc:                                     # noqa: PERF203 — one shot
        raise UnsafeIdentifierPattern(f"{label!r}: does not compile ({exc})") from exc
    if matcher.match("") is not None:
        raise UnsafeIdentifierPattern(f"{label!r}: matches the empty string")
    return IdentifierPattern(name=label, regex=regex, matcher=matcher)


def compile_identifier_patterns(
        specs: Sequence[tuple[str, str]]) -> tuple[IdentifierPattern, ...]:
    """Validate a whole tenant configuration. All or nothing: a partially applied identifier
    configuration silently changes which references are found, and "some of your patterns were
    dropped" is not a state anybody notices."""
    seen: set[str] = set()
    compiled: list[IdentifierPattern] = []
    for name, regex in specs:
        pattern = compile_identifier_pattern(name, regex)
        if pattern.name in seen:
            raise UnsafeIdentifierPattern(f"{pattern.name!r}: duplicate pattern name")
        seen.add(pattern.name)
        compiled.append(pattern)
    return tuple(compiled)


# --------------------------------------------------------------------------------------------
# L1.3.5-U1 · the scan
# --------------------------------------------------------------------------------------------

def _trim_url(text: str, start: int, end: int) -> int:
    """Give back the end offset of the URL without the sentence around it.

    `https://x.com/a.` ends at the `a`; `(https://x.com/a)` does too, because the closing
    bracket has no opener inside the match. Balanced brackets stay — plenty of real URLs carry
    them — so `https://en.wikipedia.org/wiki/A_(b)` survives whole."""
    while end > start:
        last = text[end - 1]
        if last in _URL_TAIL_PUNCT:
            end -= 1
            continue
        opener = _URL_CLOSERS.get(last)
        if opener is not None:
            body = text[start:end - 1]
            if body.count(opener) <= body.count(last):
                end -= 1
                continue
        break
    return end


def _count_by_span(tokens: Sequence[StructuralToken]) -> dict[str, int]:
    """Counts with nesting removed: charge the outermost span at each position, once.

    `Oct 15, 2026` is one date token; the `2026` inside it is emitted as a bare number but is
    not counted again, and neither is the `84,000` inside `$84,000`. Without this the tier
    router reads a document as carrying three numeric facts where it carries one, and the
    router adds a fixed score per token — so over-matching does not degrade counts gently, it
    buys a more expensive model.

    Two tokens that merely OVERLAP both count: neither contains the other, so both describe a
    region the other does not, and dropping either would lose a literal a consumer needs.

    One pass, not a pairwise sweep. `tokens` arrives sorted by start ascending and, within a
    start, by end DESCENDING, so every token already counted begins at or before this one and
    the containment test collapses to a single comparison against the furthest end counted so
    far. The pairwise version was quadratic and cost 180ms of the 40KB budget on its own —
    a scan slower than the model it exists to avoid calling is not a saving."""
    counts = {token_type: 0 for token_type in TOKEN_TYPES}
    furthest_end = -1
    for token in tokens:                              # already ordered container-first
        if token.end_offset <= furthest_end:
            continue
        furthest_end = token.end_offset
        counts[token.token_type] += 1
    return counts


def scan(clean_text: str,
         *,
         identifier_patterns: Sequence[IdentifierPattern] = ()) -> StructuralTokens:
    """ALG-04 · L1.3.5-U1 — every objectively identifiable token in `clean_text`, with offsets.

    `identifier_patterns` is the tenant's configuration (see `compile_identifier_pattern`) and
    defaults to NOTHING rather than to a house format: a tenant who has configured no invoice
    pattern gets no identifier tokens, which is honest, instead of the tokens some other
    company's numbering scheme happens to produce.

    Emission order is by start offset, then widest span, then `TOKEN_TYPES` precedence — the
    order a reader walking the document would meet them in, and the order `counts` needs to
    see containers before the tokens nested inside them.
    """
    if not clean_text:
        return StructuralTokens(tokens=(), counts=MappingProxyType(_count_by_span(())))

    rank = {token_type: i for i, token_type in enumerate(TOKEN_TYPES)}
    found: list[tuple[int, int, int, StructuralToken]] = []

    def record(token_type: str, start: int, end: int) -> None:
        if end <= start:
            return
        # The raw text is SLICED from the source at the offsets the token will carry, so the
        # G2 round-trip is a property of construction rather than of care.
        found.append((start, -end, rank[token_type],
                      StructuralToken(token_type=token_type, raw=clean_text[start:end],
                                      start_offset=start, end_offset=end)))

    for token_type, matcher in _COMPILED_RULES:
        for m in matcher.finditer(clean_text):
            start, end = m.start(), m.end()
            if token_type == TOKEN_URL:
                end = _trim_url(clean_text, start, end)
            record(token_type, start, end)

    for pattern in identifier_patterns:
        for m in pattern.matcher.finditer(clean_text):
            record(TOKEN_IDENTIFIER, m.start(), m.end())

    found.sort(key=lambda row: (row[0], row[1], row[2]))
    ordered = tuple(row[3] for row in found)
    # Identical (type, span) from two rules — the two URL rules both see `www.x.com` — is one
    # token, not two: it is one region of the document however many patterns recognised it.
    deduped: tuple[StructuralToken, ...] = tuple(
        t for i, t in enumerate(ordered) if i == 0 or t != ordered[i - 1])
    return StructuralTokens(tokens=deduped,
                            counts=MappingProxyType(_count_by_span(deduped)))


# --------------------------------------------------------------------------------------------
# L1.3.5-U2 · the counts the model router consumes
# --------------------------------------------------------------------------------------------

def router_counts(tokens: StructuralTokens) -> RouterCounts:
    """L1.3.5-U2 — the two counts ALG-05's tier table names, plus the full map for the audit.

    A separate callable rather than a field on `StructuralTokens` because it is a CONTRACT with
    the router: when ALG-05 starts scoring identifier density, this signature changes and every
    caller is recompiled against it, instead of the router growing a private opinion about
    which dictionary key means "dates"."""
    counts = tokens.counts
    return RouterCounts(
        currency_token_count=counts[TOKEN_CURRENCY_TOKEN],
        date_token_count=counts[TOKEN_DATE_STRING],
        by_type=MappingProxyType(dict(counts)),
    )


__all__ = [
    "IdentifierPattern",
    "MAX_IDENTIFIER_PATTERN_CHARS",
    "MAX_IDENTIFIER_REPEAT",
    "RouterCounts",
    "SAMPLE_IDENTIFIER_PATTERNS",
    "StructuralToken",
    "StructuralTokens",
    "TOKEN_BARE_NUMBER",
    "TOKEN_CURRENCY_TOKEN",
    "TOKEN_DATE_STRING",
    "TOKEN_DURATION_STRING",
    "TOKEN_EMAIL_ADDRESS",
    "TOKEN_FILE_REF",
    "TOKEN_IDENTIFIER",
    "TOKEN_PERCENTAGE",
    "TOKEN_PHONE",
    "TOKEN_TIME_STRING",
    "TOKEN_TYPES",
    "TOKEN_URL",
    "UnsafeIdentifierPattern",
    "compile_identifier_pattern",
    "compile_identifier_patterns",
    "router_counts",
    "scan",
]
