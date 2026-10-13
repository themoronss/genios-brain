"""Every claim the expert makes is checked before anything of it reaches the founder (STEP-13).

`speedrun008/YC-II W27/` STEP-13 §3.1-§3.3 and §8.4, tree `yc2_w27_s13` M35.C2 (U02 claims, U03 numbers, U04
people, U05 the checked review). STEP-12 made a strong model's review of a file its one decision, and
refused a review whole when it said more than its dossier held (`contracts/expert_review.validate`). One
uncited fact then sent the file back to the path the expert replaced; and what `validate` cannot see —
whether the cited mail SAYS what a fact claims, whether a number is the right one of the dossier's, whom a
draft goes to — reached the card unchecked (STEP-13 §8.3 N1-N4). This module checks a review LINE BY LINE
and keeps the judgment that stands (`06` D59): `check_review` returns a `contracts/claim_check.
CheckedReview` — a verdict per line, the move's fate, the one question a held file asks, the card's words
once checked, and the ids its standing facts cite.

ONE PASS, IN ONE ORDER.

  1 · A FACT stands on its own lines (`reason/expert/dossier.lines_by_id`). It cites at least one id (else
      `uncited`), and every id it cites was printed (else `unknown_evidence`). If the move rests on it and
      it cites a mail whose words the dossier shows, it QUOTES those words, and they are there — case,
      spacing, quote marks, punctuation, a hyphen and a comma grouping digits aside, two words at least
      that carry anything (else `unquoted`, `misquoted`). A quote grounds nothing until it is MATCHED
      (M35.C2.L-logic.V1.U09): one the cited words do not hold — or given on an item whose words are not
      shown, an ask, a calculator, a situation, an older touch — drops on its own line (`quote:<n>`,
      `misquoted`) and reaches no line and no card. A fact the move rests on that cites only mails whose
      words are not shown — or a meeting with none, to report what was said there — needs a quote it
      cannot have (`unquoted`, M35.C2.L-logic.V1.U16); a claim about the meeting itself stands on its
      line. Every name it writes is on its lines, by the card
      validator's own rule (`platform/grounding.invention_ok`, else `unsupported`) — as a WHOLE word, or
      as how a domain on them begins ("Larkspur", `larkspurvc.test`; never "Avi" in `altavia`) — its own
      lines being its items, its matched quote and our names; beside them only the file's counterparty, a
      person of the file its items name, and — a fact citing no mail — the one other person the file has
      (`_Run.named`, M35.C2.L-logic.V1.U12). Never the file's head: its first-touch date grounds no month.
      An earned word is ordinary only where it opens a sentence. Every number it writes
      is on its lines — a decisive fact's on its quote, its mail's head and the readings it cites, never
      another sentence of the mail — read as what it is (`figures_in`, M35.C2.L-logic.V1.U10): a printed
      date or time is held to the dates and times its lines print and is never a count; a value carries
      its unit, magnitude and currency (6 days ≠ 6 weeks, lakh ≠ crore, M ≠ K, ₹ ≠ $); a calculator grounds
      only its own clause's value, never a sibling's printed on the same line. Else it is CORRECTED to the
      one value its one cited calculator line holds, in its unit, or it drops (`wrong_number`, RULE 08).
  2 · AN INFERENCE OR A PATTERN stands while one of its grounds stands (else `ungrounded`).
  3 · THE CARD'S WORDS. The headline (the move, or the reading when there is no move) stands on the lines
      of the facts the move rests on and the file's own head; the situation, what done looks like, what
      doing nothing costs (the card's "cost of ignoring", M35.C3.L-integration.V2.U05) and a proposed
      kind's reason on every standing fact's lines (the kind's on the lines it cites) — each carried in
      `CardWords` as checked; the draft on the move's own lines and head and what the
      brief says of us (`about_us`, M35.C2.L-logic.V1.U14) — never the rest of the dossier. A number
      corrected in a
      fact is corrected where the card restates it (M35.C2.L-logic.V1.U11): the same figure, as a value in
      its unit — never a date, a time or a code ("9:20", "9 Aug", "Q2") — in a sentence that repeats two of
      the fact's words; anywhere else it is held to its lines as written. A headline that fails HOLDS a
      moving review; a situation, a done-when, a draft or a proposed kind that fails is WITHHELD — the
      card shows the rest.
  4 · THE RIGHT PEOPLE (§3.3). The move goes to its `to` — or, none given, the first person its headline
      names — and is checked with or without a draft (M35.C2.L-logic.V1.U14, X20). A draft goes to someone
      the file's mail shows: with no `to`, or to someone not on the file, the draft is withheld; to us, the
      move is held; to the connector that
      introduced the file's counterparty — on a file that is not the connector's own — the review's own
      alternative becomes the move if it checks (the draft withheld), else the move is held. A move that
      answers an ask must answer one that waits on US. A card text that calls the founder "the founder",
      names us as a party, or names the founder by first name (X35) is NOTED (`speaks_of_you`, F178), for
      the live pass to count; rewording a card is `STEP-14`'s.
  5 · THE FATE. No fact stands: REFUSED. A moving review (act, find out) whose move lost a fact it rests on,
      whose headline failed, or whose recipient is us or a connector with no alternative: HELD — the file
      goes to Investigation and asks ONE question. Otherwise SHOWN — a find-out review asking its own move.
      Whether the ask a move answers is already ANSWERED is read here (`answered_by`, M35.C2.L-logic.V1.U15):
      the ask it names, or the one owed ask its ground cites; answered by our reply in its thread after it
      was LAST asked (M35.C2.L-logic.V1.U17: an ask asked again after our reply is not answered by that
      reply), or — a meeting ask — by a meeting with the asker booked after it. The move is then moot: SUPPRESSED,
      or — another ask still waiting on us — HELD, asking the next move on that one: never the whole file.
      A move whose standing ground is only what YOU told us — your answer, a question card; no mail, no
      meeting (M36.C2.L-logic.V2.U12, second crosscheck B2) — is confirmed with you first: HELD, asking "You
      said: “…”. Should we go ahead with “<the move>”?"; your yes to that (`confirms`: a closed yes, no
      negation, no "but") lets it stand, noted `confirmed_by_you`; any other answer SUPPRESSES it
      (`declined_by_you`). Whether a claim says what you SAID is not read (your "No" grounded the claim you
      denied): that is the bound, and the confirmation is what holds it. A question card's headline is our
      own question, never a ground (`_ours_blanked`).

WHAT `validate` STILL REFUSES WHOLE — the structure (`STRUCTURAL`): a moving mode with no move, a move
resting on no fact the review has, a stage the playbook does not name. A slip of one optional move field
drops its own line (M35.C1.L-contract.V0.U04): a `rests_on` ref beside the facts it names that is no fact
(`rests_on`), an `answers` that is no ask the dossier printed (`answers`). Grounding is per line here,
and a number in prose no founder is shown — a hypothesis, a scenario but doing nothing's, the appraisal's
reasons — is NOTED
(`unheld_number`), not refused: it reaches nobody, and a live model's hypotheses hold numbers.

Pure: no I/O, no clock, no model. The same review and dossier, the same verdicts, byte for byte.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from genios_engine.contracts import claim_check as C
from genios_engine.contracts.claim_check import NOTHING_TO_ASK
from genios_engine.contracts.expert_review import (
    ASK_PREFIX, MOVING, NO_NEXT_MOVE, NUMBER_PATTERN, UNGROUNDED_MOVE, UNKNOWN_STAGE, ExpertReview, fact_ref,
    number_tokens)
from genios_engine.platform.grounding import corpus_of, digit_runs, fold, haystack, invention_ok, proper_nouns
from genios_engine.platform.self_identity import names_us, speaks_of_us, to_you
from genios_engine.reason.expert.decide import is_event
from genios_engine.reason.expert.dossier import DossierLine, FilePeople, Person, label_of, lines_by_id

#: What `validate` still refuses whole — the review's STRUCTURE, never its grounding.
STRUCTURAL: frozenset[str] = frozenset({NO_NEXT_MOVE, UNGROUNDED_MOVE, UNKNOWN_STAGE})
#: A quote is the mail's own words — at least this many of them that carry anything (`FUNCTION_WORDS`
#: aside): "a call" is in a mail asking FOR a call, and proves nothing about it (crosscheck X17).
QUOTE_MIN_WORDS = 2
#: The words that carry no claim of their own — articles, pronouns, auxiliaries, prepositions,
#: conjunctions. A closed class: counted out of a quote's length, never out of what it must match.
FUNCTION_WORDS: frozenset[str] = frozenset(
    "a an the i me my we us our you your he him his she her it its they them their this that these those "
    "is am are was were be been being do does did have has had will would shall should can could may might "
    "must to of in on at by for with from into about up out over as and or but so if then than not no"
    .split())
#: Ordinary words the expert's card texts open a sentence with that the card validator's own stop-list does
#: not hold (`platform/grounding._GRAMMAR_WORDS`) — each EARNED by an observed failure, as that list's own
#: rule asks: the golden set's authored answers (12 Oct) — "Download the certificate" (F02), "Attaching the
#: deck" (F05), "Accept the invite" (F07), "Ahead of your partners' meeting" (F13, F42), "Beside the
#: application" and "File the form" (F23), "Finish the sheet" (F24, F30), "Block the slot" (F31), "Nothing
#: is owed" (F38-F41, F49, F54), "Say whether you met" and "Memory holds" (F54), "Sign in" (F01). Read as
#: the words they are, never as invented names; the card validator's list itself is unchanged, so a
#: narrator's card is judged exactly as before.
EARNED: frozenset[str] = frozenset({"accept", "ahead", "attaching", "beside", "block", "download", "file",
                                    "finish", "memory", "nothing", "say", "sign"})
_EARNED = re.compile(r"\b(?:" + "|".join(sorted(EARNED)) + r")\b", re.I)
#: What comes before a word that OPENS a sentence: nothing, or a stop, a question, an exclamation, a colon, a
#: semicolon, a dash or a line break — and any opening quote. An earned word anywhere else is read as written:
#: "copy Block on it" names a company (crosscheck X50).
_OPENS = re.compile(r"(?:\A|[.!?;:\n—–])\s*[\"'“‘(\[]*\Z")
_MONTH = re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|"
                    r"December)\b")
#: An ask a meeting answers (`contracts/open_loop.ASK_KINDS`): a meeting asked for, or a demo.
MEETING_ASKS: frozenset[str] = frozenset({"meeting_request", "demo_requested"})
#: How the dossier prints an open ask, and a meeting — held, or booked ahead (`reason/expert/dossier`).
_ASKED = re.compile(r"^- \[(?P<ask>loop:[^\[\]\s]+)\] (?P<kind>[\w-]+), .*open since "
                    r"(?P<at>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC"
                    r"(?:, last asked (?P<last>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC)?")
_MET = re.compile(r"\[(?P<evt>[^\[\]\s:]+)\] (?:(?P<held>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC · a meeting\b"
                  r"|a meeting at (?P<booked>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC)")
#: How a calculator prints its sample size, never its value (`contracts/measured.Measured.says`).
_SAMPLE = re.compile(r"\(n\s*=\s*\d[^)]*\)|\b\d+ times\b")
_FACT_REF = re.compile(r"^fact:(\d+)$")
#: An id as the dossier prints it — never a number, whatever digits it holds (`evt_marco_0811`).
_PRINTED_ID = re.compile(r"\[[^\[\]\s]+\]")
_THE_FOUNDER = re.compile(r"\bthe founder\b", re.I)
#: How the dossier prints a meeting — held (`· a meeting ·`) or booked ahead (`a meeting at`).
_A_MEETING = re.compile(r"(?:· a meeting\b|\ba meeting at\b)")
#: A claim that reports what was SAID or agreed — a verb of saying, with no negation before it ("nothing on
#: file says what was agreed" says that nothing was shown, not what was said).
_SAYING = re.compile(r"\b(?:said|says|say|told|tells|asked|asks|agreed|agrees|promised|promises|committed|"
                     r"commits|offered|offers|confirmed|confirms|mentioned|mentions|suggested|suggests|"
                     r"proposed|proposes|replied|replies|explained|explains|stated|states|wrote|writes|"
                     r"declined|declines|refused|refuses|accepted|accepts)\b", re.I)
_NEGATION = re.compile(r"\b(?:no|not|nothing|never|none|nobody|neither|nor)\b", re.I)
#: How the dossier prints a card of the file — its headline in quotes, then its state (`dossier._judged_before`);
#: greedy, so a headline holding quotes of its own is blanked whole (and, at worst, more with it).
_CARD_HEADLINE = re.compile(r"(\ba card )“.*”(, [a-z_]+(?:;|$))")
#: How the dossier prints your answer (`dossier._answers`): its id, then your words.
_YOUR_WORDS = re.compile(r"^- \[(?P<ref>answer:[^\[\]\s]+)\] “(?P<words>.*)”$")
#: The prefix of your answer's id (`dossier._answers`).
ANSWER_PREFIX = "answer:"
#: A confirmation you gave: your words OPEN with a yes — a closed class — and hold no negation, no "but" (STEP-13
#: M36.C2.L-logic.V2.U12). Anything else does not confirm: the move is not made on it.
_YES = re.compile(r"^\W*(?:yes|yeah|yep|yup|sure|ok|okay|correct|right|confirmed|agreed|absolutely|definitely|"
                  r"exactly|go ahead|please do|do it)\b", re.I)
_BUT = re.compile(r"\bbut\b", re.I)
#: Your own words as a question quotes them ("You said: “…”", "You answered: “…”") — yours to say, never us
#: naming you.
_YOUR_QUOTED = re.compile(r"\bYou (?:said|answered): “[^”]*”")


def _to_you_beside_yours(question: str, people: FilePeople) -> str | None:
    """A held question said to you — every name of ours outside your own quoted words as "you"
    (`platform/self_identity.to_you`), your words left as you wrote them — or None (M36.C2.L-logic.V2.U19)."""
    kept: list[str] = []

    def hide(m: re.Match[str]) -> str:
        kept.append(m.group(0))
        return f"\x00{len(kept) - 1}\x00"
    said = to_you(_YOUR_QUOTED.sub(hide, question), people.us, people.our_names)
    return None if said is None else re.sub(r"\x00(\d+)\x00", lambda m: kept[int(m.group(1))], said)


# ── words ─────────────────────────────────────────────────────────────────────────────────────────

def _flat(text: str | None) -> str:
    """A text as a quote is matched: compatibility-folded and lowercased, a comma grouping digits gone
    ("1,400" is "1400", "12,50,000" is "1250000" — X18), quote marks gone, every other mark but those inside
    a word (an address, a decimal, a hyphen) a space, the spacing one space."""
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    value = re.sub(r"(?<=\d),(?=\d)", "", value)
    value = re.sub(r"[\"'`“”‘’«»]", "", value)
    value = re.sub(r"[^\w\s@.%$€£₹-]", " ", value)
    value = re.sub(r"(?<!\w)[.@%-]+|[.@%-]+(?!\w)", " ", value)
    return " ".join(value.split())


def _pattern(flat: str) -> re.Pattern[str]:
    """A flat quote as the words it may be found in: whole words, a hyphen a boundary that may be written
    or not — "follow-up" is "follow up", "e-mail" is "email" (X18) — and a space a space or a hyphen."""
    out: list[str] = []
    for i, ch in enumerate(flat):
        if ch == " ":
            out.append(r"[\s-]")
        elif ch == "-":
            out.append(r"[\s-]?")
        else:
            out.append(re.escape(ch))
            if i + 1 < len(flat) and ch.isalnum() and flat[i + 1].isalnum():
                out.append("-?")
    return re.compile(r"(?<!\w)" + "".join(out) + r"(?!\w)")


def quoted_in(quote: str | None, words: Iterable[str]) -> bool:
    """Do these mail words hold this quote — whole words, at least `QUOTE_MIN_WORDS` of them that carry
    anything (`FUNCTION_WORDS` aside)?"""
    q = _flat(quote)
    if len([w for w in q.split() if w not in FUNCTION_WORDS]) < QUOTE_MIN_WORDS:
        return False
    found = _pattern(q)
    return any(found.search(_flat(w)) for w in words)


def value_of(line: str, ref: str) -> str | None:
    """The one value a calculator prints for `ref` on `line` — its own clause's number, the sample size
    aside — or None when the clause holds none, or more than one (a rate, "2 of 5")."""
    figure = _value_figure(line, ref)
    return figure[0] if figure is not None else None


def _clause(line: str, ref: str) -> str | None:
    """The clause of `line` that prints `ref` — from the last id or `;` before its marker, up to it."""
    marker = f"[{ref}]"
    if marker not in line:
        return None
    return re.split(r"\]|;", line.split(marker, 1)[0])[-1]


def _value_figure(line: str, ref: str) -> tuple[str, str, str] | None:
    """`value_of`, with its unit and currency — what a correction must keep (M35.C2.L-logic.V1.U10)."""
    clause = _clause(line, ref)
    if clause is None:
        return None
    figs = figures_in(_SAMPLE.sub(" ", clause))
    values = figs.values if not (figs.dates or figs.times or figs.days) else frozenset()
    return next(iter(values)) if len(values) == 1 else None


def numbers_in(text: str | None) -> frozenset[str]:
    """Every number a text writes — the ids it prints aside: an id's digits are no number."""
    return number_tokens(_PRINTED_ID.sub(" ", str(text or "")))


# ── figures: a number as what it is (M35.C2.L-logic.V1.U10) ─────────────────────────────────────────
_MONTHS: tuple[str, ...] = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_MON = (r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|"
        r"sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)")
#: A date as the dossier prints it — `2026-08-11 09:20 UTC`, its time with it — and as people write one.
_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{2}):(\d{2})(?::\d{2})?)?(?:\s*UTC\b)?")
_DAY_MONTH = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({_MON})\.?\b(?:,?\s+(\d{{4}}))?", re.I)
_MONTH_DAY = re.compile(rf"\b({_MON})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(\d{{4}}))?", re.I)
_CLOCK = re.compile(r"\b(\d{1,2})(?::(\d{2})\s*(am|pm|a\.m\.|p\.m\.)?|\.(\d{2})\s*(am|pm|a\.m\.|p\.m\.))"
                    r"(?!\d)", re.I)
_HOUR = re.compile(r"\b(\d{1,2})\s*(am|pm|a\.m\.|p\.m\.)(?!\w)", re.I)
_ORDINAL = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)\b", re.I)
#: A code — letters, then digits, in one word ("Q2", "FY26", "B2B"): a name for a thing, read whole.
_CODE = re.compile(r"\b[A-Za-z]+\d+[A-Za-z\d]*\b")
#: A value — its currency before it, its unit or magnitude after it, the words a text writes them in.
_VALUE = re.compile(
    r"(?P<cur>₹|\brs\.?\s?|\binr\s?|\$|\busd\s?|€|\beur\s?|£|\bgbp\s?)?"
    rf"(?<![\d.,])(?P<n>{NUMBER_PATTERN})"
    r"(?P<unit>\s?-?\s?(?:%|percent\b|per\s?cent\b|k\b|thousand\b|m\b|mn\b|million\b|b\b|bn\b|billion\b|"
    r"lakhs?\b|lacs?\b|crores?\b|cr\b|seconds?\b|secs?\b|minutes?\b|mins?\b|hours?\b|hrs?\b|days?\b|"
    r"weeks?\b|wks?\b|months?\b|years?\b|yrs?\b))?", re.I)
#: Each unit or magnitude word, as one name: a value's unit must be its line's (lakh ≠ crore, days ≠ weeks).
UNITS: dict[str, str] = {
    "%": "%", "percent": "%", "per cent": "%", "percent.": "%", "k": "k", "thousand": "k", "m": "m",
    "mn": "m", "million": "m", "b": "b", "bn": "b", "billion": "b", "lakh": "lakh", "lakhs": "lakh",
    "lac": "lakh", "lacs": "lakh", "crore": "crore", "crores": "crore", "cr": "crore", "second": "s",
    "seconds": "s", "sec": "s", "secs": "s", "minute": "min", "minutes": "min", "min": "min", "mins": "min",
    "hour": "h", "hours": "h", "hr": "h", "hrs": "h", "day": "d", "days": "d", "week": "w", "weeks": "w",
    "wk": "w", "wks": "w", "month": "mo", "months": "mo", "year": "y", "years": "y", "yr": "y", "yrs": "y"}
CURRENCIES: dict[str, str] = {"₹": "inr", "rs": "inr", "inr": "inr", "$": "usd", "usd": "usd", "€": "eur",
                              "eur": "eur", "£": "gbp", "gbp": "gbp"}


@dataclass(frozen=True, slots=True)
class Figures:
    """What a text writes in digits, each as what it is: dates (month, day, year or None), times (hour,
    minute), days of a month written alone ("the 11th"), and values (the number, its unit, its currency)."""
    dates: frozenset[tuple[int, int, int | None]] = frozenset()
    times: frozenset[tuple[int, int]] = frozenset()
    days: frozenset[int] = frozenset()
    values: frozenset[tuple[str, str, str]] = frozenset()


def _norm(token: str) -> str:
    whole, _, frac = token.replace(",", "").partition(".")
    frac = frac.rstrip("0")
    return f"{int(whole)}.{frac}" if frac else str(int(whole))


def _hour(h: str, ampm: str | None) -> int:
    return int(h) % 12 + (12 if ampm.lower().startswith("p") else 0) if ampm else int(h)


def figures_in(text: str | None) -> Figures:
    """Every figure `text` writes (see `Figures`) — its printed ids aside, and every date and time taken
    out BEFORE a value is read: a timestamp's digits are no count (crosscheck X02)."""
    rest, figures = _masked(text)
    for m in _VALUE.finditer(rest):
        raw = m.group("n")
        if raw.count(".") > 1:                         # a version: each part on its own, as number_tokens
            figures.values.update((_norm(part), "", "") for part in raw.replace(",", "").split("."))
            continue
        figures.values.add(_figure(m))
    return Figures(frozenset(figures.dates), frozenset(figures.times), frozenset(figures.days),
                   frozenset(figures.values))


def _figure(m: re.Match[str]) -> tuple[str, str, str]:
    """A value `_VALUE` found: its number, its unit, its currency — each as one name."""
    unit = " ".join((m.group("unit") or "").strip(" -").lower().split())
    cur = (m.group("cur") or "").strip().rstrip(".").lower()
    return _norm(m.group("n")), UNITS.get(unit, unit), CURRENCIES.get(cur, cur)


@dataclass
class _Read:
    dates: set[tuple[int, int, int | None]]
    times: set[tuple[int, int]]
    days: set[int]
    values: set[tuple[str, str, str]]


def _masked(text: str | None) -> tuple[str, _Read]:
    """`text` with its printed ids, dates, times, days of a month and codes blanked out — the same length,
    so what is left is found where it is written — and what was blanked, read (a code as a value of its
    own: "Q2" is Q2, never 2)."""
    rest = _PRINTED_ID.sub(lambda m: " " * len(m.group(0)), str(text or ""))
    dates: set[tuple[int, int, int | None]] = set()
    times: set[tuple[int, int]] = set()
    days: set[int] = set()
    values: set[tuple[str, str, str]] = set()

    def cut(m: re.Match[str]) -> str:
        return " " * len(m.group(0))

    def iso(m: re.Match[str]) -> str:
        dates.add((int(m.group(2)), int(m.group(3)), int(m.group(1))))
        if m.group(4):
            times.add((int(m.group(4)), int(m.group(5))))
        return cut(m)

    def day_month(m: re.Match[str]) -> str:
        dates.add((_MONTHS.index(m.group(2)[:3].lower()) + 1, int(m.group(1)),
                   int(m.group(3)) if m.group(3) else None))
        return cut(m)

    def month_day(m: re.Match[str]) -> str:
        dates.add((_MONTHS.index(m.group(1)[:3].lower()) + 1, int(m.group(2)),
                   int(m.group(3)) if m.group(3) else None))
        return cut(m)

    def clock(m: re.Match[str]) -> str:
        minute, ampm = (m.group(2), m.group(3)) if m.group(2) else (m.group(4), m.group(5))
        if int(minute) >= 60 or int(m.group(1)) > 23:
            return m.group(0)
        times.add((_hour(m.group(1), ampm), int(minute)))
        return cut(m)

    def hour(m: re.Match[str]) -> str:
        times.add((_hour(m.group(1), m.group(2)), 0))
        return cut(m)

    def ordinal(m: re.Match[str]) -> str:
        days.add(int(m.group(1)))
        return cut(m)

    def code(m: re.Match[str]) -> str:
        values.add((m.group(0).lower(), "", ""))
        return cut(m)

    rest = _ISO.sub(iso, rest)
    rest = _DAY_MONTH.sub(day_month, rest)
    rest = _MONTH_DAY.sub(month_day, rest)
    rest = _CLOCK.sub(clock, rest)
    rest = _HOUR.sub(hour, rest)
    rest = _ORDINAL.sub(ordinal, rest)
    rest = _CODE.sub(code, rest)
    return rest, _Read(dates, times, days, values)


@dataclass(frozen=True, slots=True)
class Stray:
    """A figure a text writes that its lines do not hold — as the detail names it, and, for a value, the
    value itself (what a calculator may correct)."""
    detail: str
    value: tuple[str, str, str] | None = None


def unheld(text: Figures, lines: Figures) -> list[Stray]:
    """Each figure of `text` that `lines` does not hold — a date its dates do not (the year too, when the
    text writes one), a time its times do not, a day of the month no date of its has, a value with no
    equal on its lines in its unit and currency (a bare count needs neither; a year stands on a date of
    that year). Sorted by what is written, so the same texts name the same first stray."""
    out: list[Stray] = []
    for month, day, year in text.dates:
        if not any(month == m and day == d and (year is None or year == y) for m, d, y in lines.dates):
            out.append(Stray(f"number:{day} {_MONTHS[month - 1].title()}" + (f" {year}" if year else "")))
    for h, mi in text.times:
        if (h, mi) not in lines.times:
            out.append(Stray(f"number:{h}:{mi:02d}"))
    for day in text.days:
        if day not in {d for _, d, _ in lines.dates} | set(lines.days) | {int(n) for n, _, _ in lines.values
                                                                            if n.isdigit()}:
            out.append(Stray(f"number:{day}"))
    years = {y for _, _, y in lines.dates if y is not None}
    for n, unit, cur in text.values:
        if any(n == ln and unit in ("", lu) and cur in ("", lc) for ln, lu, lc in lines.values):
            continue
        if not unit and not cur and n.isdigit() and int(n) in years:
            continue
        out.append(Stray(f"number:{n}", (n, unit, cur)))
    return sorted(out, key=lambda s: s.detail)


@dataclass(frozen=True, slots=True)
class Correction:
    """A fact's number its calculator corrected (M35.C2.L-logic.V1.U11): the figure as the fact wrote it —
    its number, unit and currency, and, a bare count, the word after it — the calculator's value, and the
    fact's own words, by which a card sentence is known to restate it."""
    said: str
    unit: str
    cur: str
    follows: str | None
    value: str
    words: frozenset[str]


_WORD = re.compile(r"[a-z]+")


#: A month as a word — written out or short — which a date writes, and no sentence restates a fact by.
_MONTH_WORDS: frozenset[str] = frozenset({*_MONTHS, "sept", "january", "february", "march", "april", "june",
                                          "july", "august", "september", "october", "november", "december"})


def _content(text: str) -> frozenset[str]:
    """A text's words that carry anything — its function words, its units and its months aside."""
    return frozenset(w for w in _WORD.findall(text.lower()) if len(w) > 2 and w not in FUNCTION_WORDS
                     and w not in UNITS and w not in _MONTH_WORDS)


def _after(text: str, end: int) -> str | None:
    """The word right after position `end` of `text`, lowercased — None when none follows."""
    m = re.match(r"\s*-?\s*([A-Za-z]+)", text[end:])
    return m.group(1).lower() if m else None


#: A card text's sentences: split after a stop, a question, an exclamation or a semicolon.
_SENTENCE = re.compile(r"(?<=[.!?;])\s+|\n+")
#: How many of a fact's words a sentence repeats to restate it, beside the number.
RESTATES_WORDS = 2


def _restates(text: str, at: int, correction: Correction) -> bool:
    """Does the sentence of `text` holding position `at` restate the corrected fact?"""
    start = 0
    for m in _SENTENCE.finditer(text):
        if m.start() >= at:
            return len(_content(text[start:m.start()]) & correction.words) >= RESTATES_WORDS
        start = m.end()
    return len(_content(text[start:]) & correction.words) >= RESTATES_WORDS


def correction_of(claim: str, said: tuple[str, str, str], value: str) -> Correction:
    """The correction of `claim`'s figure `said` (number, unit, currency) to `value`."""
    masked, _ = _masked(claim)
    follows = next((_after(masked, m.end("n")) for m in _VALUE.finditer(masked) if _figure(m) == said), None)
    return Correction(said=said[0], unit=said[1], cur=said[2], follows=follows if not said[1] else None,
                      value=value, words=_content(claim))


def _swap(text: str, corrections: Iterable[Correction]) -> str:
    """`text` with a corrected figure replaced by its calculator's value — ONLY where it writes the same
    figure as a value (never inside a date, a time or a code), in the same unit and currency (a bare count:
    with the same word after it), in a sentence that restates the fact (`_restates`). Anywhere else it is
    left as written, and held to its lines like any number (crosscheck X08)."""
    corrections = list(corrections)
    if not corrections:
        return text
    masked, _ = _masked(text)
    edits: list[tuple[int, int, str]] = []
    for m in _VALUE.finditer(masked):
        number, unit, cur = _figure(m)
        for c in corrections:
            if (number, unit) != (c.said, c.unit) or cur not in ("", c.cur):
                continue
            if not c.unit and _after(masked, m.end("unit") if m.group("unit") else m.end("n")) != c.follows:
                continue
            if _restates(text, m.start("n"), c):
                edits.append((m.start("n"), m.end("n"), c.value))
                break
    for start, end, value in reversed(edits):
        text = text[:start] + value + text[end:]
    return text


def answered_by(dossier_text: str, ask: str, people: FilePeople | None = None) -> str | None:
    """What answers this open ask, as an event id — or None (M35.C2.L-logic.V1.U15, crosscheck X14, X21):
      * our reply in the ask's thread, after it was LAST asked — any ask;
      * a MEETING ask: a meeting on the file after it was last asked (held or booked ahead, as the dossier
        prints both), first BOOKED after the ask was first made, and WITH THE ASKER — set up by them, or
        by us on the asker's own file (the counterparty's). A meeting booked before the ask, or with
        somebody else, answers nothing; a meeting never answers a question (replay 04).
    ⛔ AFTER ITS LATEST ASKING (M35.C2.L-logic.V1.U17, second crosscheck B1). The ledger reopens an ask
    asked again after our reply and keeps its `opened_at` (`context/open_loops.record_ask`): their asking
    again is direct evidence our reply did not resolve it, so a reply — or a meeting held — before the
    latest asking answers nothing. The latest asking is the ledger's `last_seen_at`, as the dossier prints
    it (`last asked`) and the file's people carry it (`AskSeen.last_asked_at`); an ask asked once is
    answered after it was opened, as before (a stale loop never asked again keeps its answer, golden F45).
    What a meeting's booking, its organiser, the ask's thread and asker are, the file's people say
    (`dossier.people_of`); without them nothing can be said to answer an ask. A closed ask needs no
    reading: the dossier shows open asks only, so a move cannot name one (`validate`)."""
    seen = next((a for a in (people.asks if people is not None else ()) if a.ref == ask), None)
    opened = latest = kind = None
    for line in dossier_text.splitlines():
        if (m := _ASKED.match(line.strip())) is not None and m.group("ask") == ask:
            kind, opened = m.group("kind"), m.group("at")
            latest = max(opened, m.group("last") or opened)              # the dossier's own clock, as text
            break
    if seen is None or opened is None or seen.opened_at is None:
        return None
    asked = max(seen.opened_at, seen.last_asked_at or seen.opened_at)
    if seen.thread:
        reply = next((r for r in people.replies if r.thread == seen.thread and r.at > asked), None)
        if reply is not None:
            return reply.event_id
    if kind not in MEETING_ASKS:
        return None
    met = {m.group("evt") for line in dossier_text.splitlines() for m in _MET.finditer(line)
           if (m.group("held") or m.group("booked")) > latest}
    for meeting in people.meetings:
        if meeting.event_id in met and meeting.booked_at is not None and meeting.booked_at > seen.opened_at \
                and _with_the_asker(meeting, seen, people):
            return meeting.event_id
    return None


def _with_the_asker(meeting, ask, people: FilePeople) -> bool:
    """Was this meeting with the one who asked — set up by them, or by us on their own file?"""
    by, asker = meeting.by, ask.asker
    if by is None or asker is None:
        return False
    if by.key and asker.key and by.key.casefold() == asker.key.casefold():
        return True
    if by.key and "@" in by.key and people.us.is_us(by.key):
        return asker == people.counterparty
    return bool(by.name) and matches(by.name, asker)


#: An ask's kind as the founder reads it.
_ASK_WORDS: dict[str, str] = {"question": "question", "meeting_request": "meeting request",
                              "demo_requested": "demo request"}


def _owed(dossier_text: str, people: FilePeople, but: str) -> list[tuple[str, str, str]]:
    """The OTHER open asks that wait on us and nothing has answered — (ref, kind, opened), as printed."""
    out = []
    for line in dossier_text.splitlines():
        m = _ASKED.match(line.strip())
        if m is None or m.group("ask") == but or "they wait on us" not in line:
            continue
        if answered_by(dossier_text, m.group("ask"), people) is None:
            out.append((m.group("ask"), m.group("kind"), m.group("at")))
    return out


# ── people ────────────────────────────────────────────────────────────────────────────────────────

def _words(text: str | None) -> list[str]:
    return re.findall(r"[\w.+@-]+", str(text or "").casefold())


def _name_of(person: Person) -> list[str]:
    """A person's name, word by word — or, for one the file knows only by an address (no name, or the
    address printed as their name), the words of the address before its `@`: *gaurav@stackfield.test* is
    Gaurav, as any reader of the mail takes it (the golden set's authored drafts, 12 Oct: F30, F48)."""
    key = str(person.key or "")
    if person.name and person.name.casefold() != key.casefold():
        return _words(person.name)
    if "@" not in key:
        return []
    return [w for w in re.split(r"[._+-]+", key.split("@", 1)[0].casefold()) if w]


def matches(to: str | None, person: Person | None) -> bool:
    """Does `to` name this person — by their address, by every word of their name, or, when `to` is one
    word, by their first name? (A person known only by an address is named by its words, `_name_of`.)"""
    if not to or person is None:
        return False
    said = _words(to)
    if person.key and person.key.casefold() in said:
        return True
    name = _name_of(person)
    if not name:
        return False
    return all(w in said for w in name) or (len(said) == 1 and said[0] == name[0])


def the_connector(to: str | None, people: FilePeople) -> bool:
    """Does `to` name the connector that introduced the file's counterparty — as the PERSON (`matches`:
    "Pankaj Mehta", "Pankaj", pankaj@saka.vc) or by their FIRM: the first label of their address's host, never a
    public mail host's (`dossier.label_of`: "Saka" for pankaj@saka.vc) — M35.C2.L-logic.V0.U13 (fix), second
    crosscheck G1. Named as the person only, `to='Saka'` went out to the very firm that made the introduction."""
    connector = people.connector
    if connector is None or not to:
        return False
    if matches(to, connector):
        return True
    firm = label_of(connector.key)
    return bool(firm) and firm in re.findall(r"[a-z0-9]+", str(to).casefold())


def _invented(text: str, corpus: str, people: FilePeople) -> str | None:
    """The first NAME `text` writes that `corpus` and our own names do not hold — the card validator's own
    rule (`platform/grounding.invention_ok`), its numbers left to `figures_in` — or None. Each name as a
    WHOLE word of them (M35.C2.L-logic.V1.U12, X16: "Avi" is no word of "Altavia"), held here, inside the
    check: the card validator's shared rule matches a substring, and is left as its callers have it."""
    held, _nums = corpus_of([corpus, *people.our_names])
    plain = _EARNED.sub(lambda m: m.group(0).lower() if _OPENS.search(text[:m.start()]) else m.group(0),
                        text)
    # A month written out is the month its lines write short — "4 Aug" grounds "August" (F51, 12 Oct): a
    # calendar word, never an invented name. A month its lines never write stays a name, and is refused.
    shorts = {w for w in re.findall(r"[a-z]+", held) if len(w) >= 3}
    plain = _MONTH.sub(lambda m: m.group(0).lower() if any(m.group(0).lower().startswith(w) for w in shorts)
                       else m.group(0), plain)
    ok, why = invention_ok(plain, held, digit_runs(plain))
    if not ok:
        return why or "name"
    words = haystack(fold(held))
    labels = [part for token in _ADDRESSES.findall(words) for part in re.split(r"[@.+_-]", token) if part]
    runs = [[pn.lower() for pn in proper_nouns(m.group(0))] for m in _CAPITALISED.finditer(plain)]
    for pn in proper_nouns(plain):
        low = pn.lower()
        if re.search(rf"(?<![a-z0-9]){re.escape(low)}(?![a-z0-9])", words) is None \
                and not _leads_a_label(low, runs, labels):
            return f"name:{pn}"
    return None


#: How much of a domain's label may follow the name it begins with — "vc", "hub", "cap", "labs", "seed":
#: the kind of firm, never the rest of another word ("Al" begins `altavia`, and is no name of it).
LABEL_TAIL = 4
#: An address or a domain as a corpus writes it — `marco@altavia.test`, `larkspurvc.test`.
_ADDRESSES = re.compile(r"[\w.+-]+@[\w.-]+|[\w-]+(?:\.[\w-]+)+")
#: Capitalised words written side by side — one name, perhaps of several words ("Vertex Angels").
_CAPITALISED = re.compile(r"[A-Z][^\s,;:()]*(?:\s+[A-Z][^\s,;:()]*)*")


def _leads_a_label(name: str, runs: list[list[str]], labels: list[str]) -> bool:
    """Is `name` — alone, or with the capitalised words written beside it — how an address or a domain
    of the corpus BEGINS? A file known by its domain is named by it: "Larkspur" for `larkspurvc.test`,
    "Vertex Angels" for `vertexangels.test` (the golden set's authored answers, 12 Oct). A name inside a
    label is none of it: "Avi" is no beginning of `altavia` (crosscheck X16)."""
    for run in runs:
        for k, word in enumerate(run):
            if word != name:
                continue
            for i in range(k + 1):
                for j in range(k, len(run)):
                    joined = "".join(run[i:j + 1])
                    if any(label.startswith(joined) and len(label) - len(joined) <= LABEL_TAIL
                           for label in labels):
                        return True
    return False


def _person(person: Person) -> str:
    """A person of the file as the words a text may name them by: their name, and their address (whose
    words are their name when the file knows no other — `priya.nair@…` is Priya Nair)."""
    return " ".join([person.name or "", person.key or ""])


#: An address, as a text writes one.
_AN_ADDRESS = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def _target(text: str | None, people: FilePeople) -> str | None:
    """The first person `text` names, as written — the connector, a person of the file, an address not ours —
    or, when it names none of them, the first of our names or addresses; else None: whom a move with no `to`
    goes to (M35.C2.L-logic.V1.U14, X20). A name is a capitalised whole word: "Send Introly the deck to pass on
    to Marco" goes to Introly. ⛔ NEVER TO US BESIDE THEM (second crosscheck F1): "Send the Nimbus Labs short
    deck to Marco", "Have Arjun Rao send Marco the short deck" name us FIRST and go to Marco — we are the
    recipient only of a move that names nobody else."""
    text = str(text or "")
    ours: list[tuple[int, str]] = []
    theirs: list[tuple[int, str]] = []
    for name in people.our_names:
        if (m := re.search(rf"(?<!\w){re.escape(name)}(?!\w)", text, re.I)) is not None:
            ours.append((m.start(), m.group(0)))
    for m in _AN_ADDRESS.finditer(text):
        (ours if people.us.is_us(m.group(0)) else theirs).append((m.start(), m.group(0)))
    firm = label_of(people.connector.key) if people.connector is not None else None
    for person in (people.connector, *people.people):
        words = _name_of(person)[:1] if person is not None else []
        if person is not None and person is people.connector and firm and firm not in words:
            words = [*words, firm]                    # the connector's firm names it too (G1)
        for word in words:
            for m in re.finditer(rf"(?<!\w){re.escape(word)}(?!\w)", text, re.I):
                if m.group(0)[0].isupper():
                    theirs.append((m.start(), m.group(0)))
                    break
    found = theirs or ours
    return min(found)[1] if found else None


#: Where the dossier prints the brief, and the brief's sections that are about OTHERS — every section
#: before them (the company, us, its goals) is what the founder confirmed of their own company.
_BRIEF = "## THE COMPANY BRIEF"
_NOT_US = ("Work in motion", "Key people", "Connectors", "Watchlist", "Preferences", "END OF COMPANY BRIEF")


def about_us(dossier_text: str) -> str:
    """What the dossier's brief says of US — the company, how it is reached, its goals — and nothing of
    the work in motion with others: what a draft, the founder's own words, may say of their company."""
    if _BRIEF not in dossier_text:
        return ""
    out: list[str] = []
    for line in dossier_text.split(_BRIEF, 1)[1].split("\n## ", 1)[0].splitlines():
        if line.startswith(_NOT_US):
            break
        out.append(line)
    return "\n".join(out)


def _quoted(headline: str | None, *, capital: bool = False) -> str:
    """A move as a question names it — in its CHECKED words (crosscheck X10: never the words that failed,
    nor a number the check corrected), or, none standing, as the move."""
    if headline:
        return f"“{headline.rstrip('.')}”"
    return "The move" if capital else "the move"


#: Why a move whose OWN words failed is held, as its question says it — per reason (G2).
_MOVE_FELL: dict[str, str] = {
    C.UNSUPPORTED: "the move names someone the facts it rests on do not",
    C.WRONG_NUMBER: "the move has a number the facts it rests on do not hold",
}


def _held_question(people: FilePeople, why: str) -> str:
    """What a held file asks you when what its move rests on — or the move itself — failed (M36.C2.L-logic.V2.U10,
    second crosscheck G2, `03` X10): what the next step is, and truly why the one found is held, worded per the
    reason it fell. ⛔ NEVER THE WORDS THAT FAILED: not the fell fact's claim, not the move as written — the
    name it misattributed, the number it got wrong — only the file's own counterparty and closed words of ours."""
    them = people.counterparty.name or people.counterparty.key or "them"
    return f"What is the next step with {them}? We held the one we found: {why}."


def _is_us(to: str, people: FilePeople) -> bool:
    return any("@" in w and people.us.is_us(w) for w in _words(to)) \
        or names_us(to, people.us, people.our_names)


# ── the run ───────────────────────────────────────────────────────────────────────────────────────

@dataclass
class _Run:
    review: ExpertReview
    lines: dict[str, tuple[DossierLine, ...]]
    people: FilePeople
    verdicts: list[C.LineVerdict] = field(default_factory=list)
    corrections: list[Correction] = field(default_factory=list)
    #: Each fact's quote, by number, once it is MATCHED in a worded line its fact cites — the only quotes
    #: that ground anything (M35.C2.L-logic.V1.U09): an unmatched one grounds no line and reaches no card.
    quotes: dict[int, str] = field(default_factory=dict)

    @property
    def names(self) -> str:
        """The file's people as words — whom a fact may name wherever it cites (the asker of an ask, the
        writer of a mail): the file shows them; a name it does not show is still refused."""
        return "\n".join(f"{p.name or ''} {p.key or ''}" for p in self.people.people)

    def named(self, fact, own: str) -> str:
        """The names a FACT may write beside its own lines and our names (M35.C2.L-logic.V1.U12, X09) — never
        the file's head, nor every person of the file:
          * the counterparty — the file is about them, and every item of it is theirs;
          * a person of the file its cited items name — their whole name, as the file knows it ("Priya"
            on the mail grounds "Priya Nair");
          * for a fact citing no mail (a reading: an ask, a calculator, a situation, a booking, whose line
            names nobody), the one person the file has beside its counterparty — the only one it can be."""
        cp = self.people.counterparty
        others = [p for p in self.people.people
                  if p != cp and not (p.key and "@" in p.key and self.people.us.is_us(p.key))]
        said = set(_words(own))
        out = [own, _person(cp)]
        out += [_person(p) for p in others if any(w in said for w in _name_of(p))]
        mails = [e for e in fact.evidence if is_event(e)
                 and not any(_A_MEETING.search(dl.line) for dl in self.lines.get(e, ()))]
        if not mails and len(others) == 1:
            out.append(_person(others[0]))
        return "\n".join(out)

    def items(self, ids: Iterable[str]) -> str:
        """The dossier items of `ids`, once each, in the order asked: each id's OWN entry — the item whose
        line it heads (`- [id] …`: a touch with its words, an ask, a situation) — or, for an id no line
        heads (a calculator), every item that prints it. A mention elsewhere (the coverage line naming
        the touch that answered our last mail) is no line of the touch: its dates are not the touch's."""
        out: list[str] = []
        for i in ids:
            places = self.lines.get(i, ())
            own = [dl for dl in places if dl.line.startswith(f"- [{i}]")]
            out += [self._ours_blanked(i, dl.item) for dl in (own or places)]
        return "\n".join(dict.fromkeys(out))

    def _ours_blanked(self, ref: str, item: str) -> str:
        """A QUESTION card's item with its headline blanked (M36.C2.L-logic.V2.U12, second crosscheck B2): the
        headline is our own question — for a held review the very claim its check dropped — never a ground
        for the claim it asked about. What it shows is that it was asked, and what became of it."""
        if ref not in self.people.question_cards:
            return item
        return _CARD_HEADLINE.sub(lambda m: f"{m.group(1)}“…”{m.group(2)}", item, count=1)

    def figures(self, ids: Iterable[str]) -> str:
        """The lines `ids` hold NUMBERS on: each id's items (`items`) — but a calculator only its own
        clause, never a sibling's on the same line (crosscheck X02: the timeline prints the usual gap, the
        longest and the quiet on one line, and "quiet 5.89 days" is the longest gap's value)."""
        out: list[str] = []
        for i in ids:
            if i.startswith("num:"):
                out += [f"{c}[{i}]" for dl in self.lines.get(i, ()) if (c := _clause(dl.line, i)) is not None]
            else:
                out.append(self.items([i]))
        return "\n".join(dict.fromkeys(out))

    def say(self, line: str, verdict: str, reason: str | None = None, detail: str = "") -> None:
        self.verdicts.append(C.LineVerdict(line, verdict, reason, detail))

    def reason(self, line: str) -> str | None:
        """The reason `line` was dropped for, or None."""
        return next((v.reason for v in self.verdicts if v.line == line and v.verdict == C.DROPPED), None)

    def why(self, line: str) -> str:
        return next((f"{v.reason}: {v.detail}" if v.detail else str(v.reason)
                     for v in self.verdicts if v.line == line and v.verdict == C.DROPPED), "dropped")

    def stands(self, text: str, corpus: str, *, head: bool = True,
               figures: str | None = None) -> tuple[str | None, str]:
        """`text` with its corrected numbers swapped in, when every figure of it is on `figures` (`corpus`
        when none is given: a date as a date, a time as a time, a value in its unit — `unheld`) and every
        name on `corpus` (with the file's own head, and our own names) — else None, and the first thing
        that is not. The head grounds a NAME — the counterparty, its introducer — never a number: its
        dates and times would ground any number at all."""
        swapped = _swap(text, self.corrections)
        stray = [s for s in unheld(figures_in(swapped), figures_in(corpus if figures is None else figures))
                 if s.value is None or not any(s.value[:2] == (c.value, c.unit) for c in self.corrections)]
        if stray:
            return None, stray[0].detail
        names = "\n".join([corpus, self.people.head, self.names]) if head else corpus
        return (swapped, "") if (why := _invented(swapped, names, self.people)) is None else (None, why)

    def text(self, line: str, text: str | None, corpus: str, *, speaks: bool = True,
             head: bool = True, figures: str | None = None) -> str | None:
        """Check one of the card's texts; record its verdict (and, when it speaks of you, the note)."""
        if not text:
            return None
        checked, why = self.stands(text, corpus, head=head, figures=figures)
        if checked is None:
            self.say(line, C.DROPPED, C.WRONG_NUMBER if why.startswith("number:") else C.UNSUPPORTED, why)
        elif checked != text:
            self.say(line, C.CORRECTED, C.BY_CALCULATOR, f"{text} -> {checked}")
        else:
            self.say(line, C.KEPT)
        if speaks:
            # ⛔ PROSE, NOT A SUBJECT (M36.C2.L-logic.V2.U19, second crosscheck F3): a card text names us by the
            # company's name at any length, a first or full name, an address or domain of ours
            # (`platform/self_identity.speaks_of_us`) — "the founder" as before.
            found = _THE_FOUNDER.search(text)
            us = speaks_of_us(text, self.people.us, self.people.our_names)
            if found or us:
                self.say(line, C.NOTED, C.SPEAKS_OF_YOU, found.group(0) if found else us)
        return checked


def _your_words(run: "_Run", told: list[str]) -> str | None:
    """Your words, as the dossier prints them, of the first answer among `told` — or None."""
    for ref in told:
        for dl in run.lines.get(ref, ()):
            if (m := _YOUR_WORDS.match(dl.line)) is not None:
                return m.group("words")
    return None


def _go_ahead(headline: str) -> str:
    """How a confirmation asks: whether to go ahead with the move, in its checked words."""
    return f"Should we go ahead with {_quoted(headline)}?"


def confirms(words: str | None) -> bool:
    """Do your words confirm — a yes, opening them, with no negation and no "but"?"""
    said = str(words or "")
    return _YES.search(said) is not None and _NEGATION.search(said) is None and _BUT.search(said) is None


def _reports_speech(claim: str) -> bool:
    """Does the claim say what someone SAID — a verb of saying, no negation before it?"""
    found = _SAYING.search(claim)
    return found is not None and _NEGATION.search(claim[:found.start()]) is None


def _unshown(run: "_Run", fact) -> str | None:
    """The event a fact rests on as WORDS nobody was shown (M35.C2.L-logic.V1.U16, X22) — a mail whose
    words the dossier does not print (an older touch, one memory holds no words for), or a meeting with
    none when the claim reports what was said there — or None. What such an event shows is its own line,
    when and with whom: a claim about the meeting itself stands on it."""
    for e in fact.evidence:
        if not is_event(e):
            continue
        meeting = any(_A_MEETING.search(dl.line) for dl in run.lines[e])
        if not meeting or _reports_speech(fact.claim):
            return e
    return None


def _rested_on(review: ExpertReview) -> set[int]:
    """The facts, by number, the move rests on — every fact when it names none; none without a move,
    for there is nothing to hold. A ref that names no fact of the review is no ground (`_strays`)."""
    move = review.next_move
    if move is None:
        return set()
    named = {n for r in move.rests_on if (n := fact_ref(r, len(review.facts))) is not None}
    return named or set(range(1, len(review.facts) + 1))


def _strays(review: ExpertReview) -> list[str]:
    """The refs of the move's `rests_on` that name no fact of the review — beside facts it does name, a
    slip of one field (M35.C1.L-contract.V0.U04): that line drops, the move stands on the facts it names.
    (A `rests_on` naming no fact at all, `validate` refuses whole — `ungrounded_move`.)"""
    move = review.next_move
    return [] if move is None else [r for r in move.rests_on if fact_ref(r, len(review.facts)) is None]


def _fact(run: _Run, n: int, decisive: bool) -> bool:
    """Check fact `n` (see the module docstring, 1); True when it stands."""
    fact, line = run.review.facts[n - 1], f"fact:{n}"
    if not fact.evidence:
        run.say(line, C.DROPPED, C.UNCITED)
        return False
    unseen = [e for e in fact.evidence if e not in run.lines]
    if unseen:
        run.say(line, C.DROPPED, C.UNKNOWN_EVIDENCE, unseen[0])
        return False
    # A quote grounds nothing until it is MATCHED (X01): in the words of a mail or meeting the fact cites,
    # as the dossier printed them — an ask, a calculator, a situation or an older touch prints none.
    worded = {e: dls for e in fact.evidence if is_event(e)
              if (dls := [dl for dl in run.lines[e] if dl.words])}
    quoted = [dl for dls in worded.values() for dl in dls
              if fact.quote and quoted_in(fact.quote, [dl.words or ""])]
    if decisive and worded:
        if not fact.quote:
            run.say(line, C.DROPPED, C.UNQUOTED)
            return False
        if not quoted:
            run.say(line, C.DROPPED, C.MISQUOTED, fact.quote)
            return False
    elif fact.quote and not quoted:
        run.say(f"quote:{n}", C.DROPPED, C.MISQUOTED, fact.quote)    # the fact needs none: it alone drops
    if decisive and not worded and (unshown := _unshown(run, fact)) is not None:
        run.say(line, C.DROPPED, C.UNQUOTED, unshown)              # it needs a quote it cannot have
        return False
    if quoted:
        run.quotes[n] = str(fact.quote)
    own = "\n".join([run.items(fact.evidence), run.quotes.get(n, "")])
    why = _invented(fact.claim, run.named(fact, own), run.people)
    if why is not None:
        run.say(line, C.DROPPED, C.UNSUPPORTED, why)
        return False
    # A decisive fact's NUMBERS are its quote's: the quote, the head of the mail it is in (its date), and
    # the readings it cites beside it — never another sentence of that mail, which the quote does not hold.
    ground = "\n".join([run.figures(fact.evidence), run.quotes.get(n, "")]) \
        if not (decisive and quoted) else "\n".join(
            [run.figures(e for e in fact.evidence if e not in worded), *(dl.line for dl in quoted),
             run.quotes[n]])
    missing = unheld(figures_in(fact.claim), figures_in(ground))          # its own lines, never the head
    if not missing:
        run.say(line, C.KEPT)
        return True
    calculators = [e for e in fact.evidence if e.startswith("num:")]
    values = {v for e in calculators for dl in run.lines[e] if (v := _value_figure(dl.line, e)) is not None}
    if len(missing) == 1 and len(calculators) == 1 and len(values) == 1 and missing[0].value is not None:
        (said, unit, cur), (value, its_unit, its_cur) = missing[0].value, next(iter(values))
        if unit in ("", its_unit) and cur in ("", its_cur):          # within its unit: 9 weeks is no 8.99 days
            run.corrections.append(correction_of(fact.claim, missing[0].value, value))
            run.say(line, C.CORRECTED, C.BY_CALCULATOR, f"number:{said} -> {value} ({calculators[0]})")
            return True
    run.say(line, C.DROPPED, C.WRONG_NUMBER, missing[0].detail)
    return False


def _grounds(run: _Run, kind: str, items, standing: set[int]) -> None:
    """Check each inference or pattern (see the module docstring, 2)."""
    for n, item in enumerate(items, start=1):
        held = [ref for ref in item.based_on
                if ((m := _FACT_REF.match(ref)) is not None and int(m.group(1)) in standing)
                or (m is None and ref in run.lines)]
        if held:
            run.say(f"{kind}:{n}", C.KEPT)
        else:
            run.say(f"{kind}:{n}", C.DROPPED, C.UNGROUNDED, ", ".join(item.based_on) or "rests on nothing")


def _prose(review: ExpertReview) -> list[str]:
    """Every text of the review no founder is shown."""
    eva, sc = review.expected_vs_actual, review.scenarios
    return [*(i.claim for i in review.inferences), *(p.claim for p in review.patterns),
            *(t for h in review.hypotheses for t in (h.proposition, h.needs)),
            *(t for u in review.unknowns for t in (u.question, u.relevance)), *review.frames.rivals,
            eva.expected, eva.actual, sc.act, sc.best, sc.worst, *sc.signals_to_watch,
            *review.appraisal.reasons, review.alternative, review.wait_or_stop]


def check_review(review: ExpertReview, dossier_text: str, people: FilePeople, *,
                 evidence_ids: Iterable[str] | None = None) -> C.CheckedReview:
    """`review`, checked line by line against the dossier it was written from (see the module docstring).
    `evidence_ids` — the dossier's own catalogue — narrows what counts as printed to exactly what the
    dossier cited; without it, every bracketed id of the text counts."""
    run = _Run(review=review, lines=lines_by_id(dossier_text, evidence_ids), people=people)
    rested = _rested_on(review)
    if strays := _strays(review):
        run.say("rests_on", C.DROPPED, C.UNKNOWN_EVIDENCE, ", ".join(strays))
    standing = {n for n in range(1, len(review.facts) + 1) if _fact(run, n, n in rested)}
    if not standing:
        return C.CheckedReview(verdicts=tuple(run.verdicts), fate=C.REFUSED, cited=(),
                               because=C.NOTHING_STANDS, words=C.CardWords(None, None, None, None, None))
    _grounds(run, "inference", review.inferences, standing)
    _grounds(run, "pattern", review.patterns, standing)
    unheld = sorted(set().union(*(numbers_in(t) for t in _prose(review))) - numbers_in(dossier_text))
    if unheld:
        run.say("prose", C.NOTED, C.UNHELD_NUMBER, ", ".join(f"number:{n}" for n in unheld))

    def corpus(numbers: Iterable[int], *, figures: bool = False) -> str:
        facts = [review.facts[n - 1] for n in sorted(numbers)]
        lines = (run.figures if figures else run.items)(e for f in facts for e in f.evidence)
        return "\n".join([lines, *(run.quotes.get(n, "") for n in sorted(numbers))])

    standing_corpus, move_corpus = corpus(standing), corpus(rested & standing)
    standing_figures, move_figures = corpus(standing, figures=True), corpus(rested & standing, figures=True)
    move = review.next_move
    said = move.what if move is not None else review.frames.primary
    headline = run.text("move", said, move_corpus if move is not None else standing_corpus,
                        figures=move_figures if move is not None else standing_figures)
    situation = run.text("situation", review.frames.primary, standing_corpus, figures=standing_figures)
    done_when = run.text("done_when", review.done_when, standing_corpus, figures=standing_figures)
    # WHAT DOING NOTHING COSTS reaches every shown card as its "cost of ignoring" (crosscheck X03): a card
    # text like the situation — its names and numbers on the standing facts' lines, "you" noted.
    do_nothing = run.text("do_nothing", review.scenarios.do_nothing, standing_corpus,
                          figures=standing_figures)
    kind = None
    if review.proposed_kind is not None:
        pk = review.proposed_kind
        unseen = [e for e in pk.evidence if e not in run.lines]
        if unseen:
            run.say("kind", C.DROPPED, C.UNKNOWN_EVIDENCE, unseen[0])
        else:
            kind = run.text("kind", pk.why, run.items(pk.evidence), speaks=False,
                            figures=run.figures(pk.evidence))

    held: str | None = None
    question: str | None = None
    draft = None
    # WHOM THE MOVE GOES TO, with or without a draft (M35.C2.L-logic.V1.U14, X20): its `to`, or — none
    # given — the first person its headline names. THE DRAFT stands on the move's own ground — its facts'
    # items and quotes, the file's head and people — and on what the brief says of us: never the rest of
    # the dossier (X23: another line of work, the what-if's numbers).
    to = move.to if move is not None else None
    target = to or (_target(said, people) if move is not None else None)
    if review.draft:
        ours = about_us(dossier_text)
        draft = run.text("draft", review.draft, "\n".join([move_corpus, ours]), speaks=False,
                         figures="\n".join([move_figures, ours]))
    if move is not None and (review.draft or target):
        if target and _is_us(target, people):
            to = target
            run.say("to", C.DROPPED, C.RECIPIENT_IS_US, to)
            held = C.HELD_BECAUSE[C.RECIPIENT_IS_US]
            question = f"Whom should {_quoted(headline)} go to? It is addressed to you."
        elif target and the_connector(target, people) and not matches(target, people.counterparty):
            to = target
            run.say("to", C.DROPPED, C.RECIPIENT_IS_CONNECTOR, to)
            other, _ = run.stands(review.alternative, move_corpus, figures=move_figures) \
                if review.alternative else (None, "")
            them = people.counterparty.name or people.counterparty.key
            if other is not None and not the_connector(other, people):
                run.verdicts = [v for v in run.verdicts if v.line != "move" or v.verdict == C.NOTED]
                run.say("move", C.CORRECTED, C.BY_ALTERNATIVE, f"{said} -> {other}")
                headline, to = other, them
            else:
                held = C.HELD_BECAUSE[C.RECIPIENT_IS_CONNECTOR]
                question = f"{_quoted(headline, capital=True)} goes to {to}, who introduced {them}. " \
                           "Whom should it go to?"
        elif not to:
            if review.draft:
                run.say("to", C.DROPPED, C.NO_RECIPIENT)
        elif not any(matches(to, p) for p in people.people):
            run.say("to", C.DROPPED, C.RECIPIENT_NOT_ON_FILE, to)
        else:
            run.say("to", C.KEPT)
        if any(v.line == "to" and v.verdict == C.DROPPED for v in run.verdicts):
            draft = None                    # its words were for someone it may not go to
    met = None
    # THE ASK THE MOVE ANSWERS (M35.C2.L-logic.V1.U15, X21): the one it names — or, naming none, the one
    # open ask waiting on us that the facts it rests on cite; then whether it is answered already. A fact
    # citing the ask WITH the event that answered it says the ask is answered (a stale open loop, golden
    # F45): it is no ground the move answers that ask on.
    addressed = None
    if move is not None and not move.answers:
        grounds = [review.facts[n - 1].evidence for n in sorted(rested & standing)]
        cited = {e for evidence in grounds for e in evidence if e.startswith(ASK_PREFIX)}
        owed = [e for e in sorted(cited)
                if any("they wait on us" in dl.line for dl in run.lines.get(e, ()))]
        found = answered_by(dossier_text, owed[0], people) if len(owed) == 1 else None
        if found is not None and not any(owed[0] in evidence and found in evidence for evidence in grounds):
            met, addressed = found, owed[0]
            run.say("answers", C.DROPPED, C.ANSWERED, f"{addressed} by {met}")
    if move is not None and move.answers:
        if not move.answers.startswith(ASK_PREFIX) or move.answers not in run.lines:
            # No ask its dossier printed — an unprinted `loop:`, or a mail, a promise, a calculator that is
            # no ask at all (M35.C1.L-contract.V0.U04): whether it is answered cannot be read — the line
            # drops, as a fact citing an unshown id does; the move stands on its facts.
            run.say("answers", C.DROPPED, C.UNKNOWN_EVIDENCE, move.answers)
        elif any("we wait on them" in dl.line for dl in run.lines.get(move.answers, ())):
            run.say("answers", C.DROPPED, C.NOT_OURS_TO_ANSWER, move.answers)
        elif (met := answered_by(dossier_text, move.answers, people)) is not None:
            addressed = move.answers
            run.say("answers", C.DROPPED, C.ANSWERED, f"{move.answers} by {met}")
        else:
            run.say("answers", C.KEPT)

    # A MOVE RESTING ONLY ON WHAT YOU TOLD US (M36.C2.L-logic.V2.U12, second crosscheck B2): the standing facts
    # it rests on cite your answer — or a question card — and no mail or meeting of the file. Its names and
    # numbers are on your words, but whether it says what you SAID is not read (your "No" grounded the claim
    # you denied): it is confirmed with you before it is shown — "You said: “…”. Should we go ahead with
    # “<the move>”?". You answered that: a yes (`confirms`) and it stands, noted; anything else and it is
    # not made — suppressed, the file's decision clearing. A move resting on a mail beside your answer is
    # grounded on the mail, and is not asked (the bound, declared: a claim's polarity is not read).
    yours = declined = None
    if move is not None and review.mode == "act" and headline:
        ground = [e for n in sorted(rested & standing) for e in review.facts[n - 1].evidence]
        told = [e for e in ground if e.startswith(ANSWER_PREFIX) or e in people.question_cards]
        if told and not any(is_event(e) for e in ground):
            yours = told
    fate = C.SHOWN
    if review.mode in MOVING and move is not None:
        fell = sorted(rested - standing)
        if fell:
            held = C.HELD_BECAUSE.get(run.reason(f"fact:{fell[0]}"), C.HELD_BECAUSE[C.HELD_MOVE])
            question = _held_question(people, held)
        elif headline is None:
            held = C.HELD_BECAUSE[C.HELD_MOVE]
            question = _held_question(people, _MOVE_FELL.get(run.reason("move"), held))
        elif yours is not None and held is None:
            tail = _go_ahead(headline)
            answered = next((a for a in people.answered if a.question.endswith(tail)), None)
            if answered is not None and confirms(answered.words):
                run.say("move", C.NOTED, C.CONFIRMED_BY_YOU, answered.ref)
            elif answered is not None:
                declined = answered.ref
                run.say("rests_on", C.DROPPED, C.DECLINED_BY_YOU, answered.ref)
            else:
                run.say("rests_on", C.DROPPED, C.ON_YOUR_ANSWER, ", ".join(yours))
                held = C.HELD_BECAUSE[C.ON_YOUR_ANSWER]
                words = _your_words(run, yours)
                question = f"You said: “{words}”. {tail}" if words else tail
        if met is not None:
            # Already done (§3.4): whatever else the move lacked, it is moot — the ask it answers is
            # answered. One ask, and only it (replay 04): the move drops, never the file — another ask
            # still waiting on us keeps the file's card, held on what the next move on it is (X14).
            fate, held, question = C.SUPPRESSED, f"{C.ANSWERED}:{met}", None
            if (still := _owed(dossier_text, people, but=str(addressed))):
                _ref, ask_kind, opened = still[0]
                when = datetime.strptime(opened, "%Y-%m-%d %H:%M")
                fate, held = C.HELD, C.HELD_BECAUSE[C.ANSWERED]
                question = (f"{_quoted(headline, capital=True)} is already answered. What is the next move "
                            f"on the {_ASK_WORDS.get(ask_kind, ask_kind.replace('_', ' '))} still waiting "
                            f"on you since {when.day} {when.strftime('%b')}?")
        elif declined is not None:
            fate, held, question = C.SUPPRESSED, f"{C.DECLINED_BY_YOU}:{declined}", None
        elif held:
            fate = C.HELD
        elif review.mode == "find_out":
            question = headline
    # A QUESTION TO YOU NEVER NAMES YOU (M36.C2.L-logic.V2.U19, second crosscheck F3): a held question that names
    # us — outside your own quoted words — is noted and asked as our closed question; a find-out file's
    # candidates (its first unknown, its move) are noted here, and asked in the second person, or passed over,
    # where it asks (`reason/expert/asks`).
    if question and (fate == C.HELD) and (hit := speaks_of_us(_YOUR_QUOTED.sub(" ", question), people.us,
                                                               people.our_names)):
        run.say("question", C.NOTED, C.SPEAKS_OF_YOU, hit)
        question = _to_you_beside_yours(question, people) or NOTHING_TO_ASK
    elif review.mode == "find_out" and fate == C.SHOWN:
        asked = [review.unknowns[0].question] if review.unknowns else []
        if (hit := next((h for t in (*asked, question) if t
                         and (h := speaks_of_us(t, people.us, people.our_names))), None)):
            run.say("question", C.NOTED, C.SPEAKS_OF_YOU, hit)
    shown = fate == C.SHOWN
    grounds = [review.facts[n - 1] for n in sorted(rested & standing)]
    words = C.CardWords(do_nothing=do_nothing, kind=kind,
                        headline=headline if shown else None, situation=situation, done_when=done_when,
                        draft=draft if shown else None, to=to if shown and draft else None,
                        evidence=tuple(e for f in grounds for e in f.evidence) if shown else (),
                        quotes=tuple(run.quotes[n] for n in sorted(rested & standing) if n in run.quotes)
                        if shown else ())
    return C.CheckedReview(
        verdicts=tuple(run.verdicts), fate=fate, words=words,
        cited=tuple(e for n in sorted(standing) for e in review.facts[n - 1].evidence),
        question=question if (fate == C.HELD or (shown and review.mode == "find_out")) else None,
        because=held if fate in (C.HELD, C.SUPPRESSED) else None)


__all__ = ["ANSWER_PREFIX", "CURRENCIES", "confirms", "the_connector", "EARNED", "FUNCTION_WORDS", "Figures", "MEETING_ASKS", "QUOTE_MIN_WORDS", "STRUCTURAL",
           "Correction", "RESTATES_WORDS", "Stray", "UNITS", "about_us", "answered_by", "check_review",
           "correction_of",
           "figures_in", "matches", "unheld",
           "quoted_in", "value_of"]
