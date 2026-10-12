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
      spacing, quote marks and punctuation aside (else `unquoted`, `misquoted`). Every name it writes is on
      its lines, by the card validator's own rule (`platform/grounding.invention_ok`, else `unsupported`).
      Every number it writes is on its lines — else it is CORRECTED to the one value its one cited
      calculator line holds, or it drops (`wrong_number`, RULE 08).
  2 · AN INFERENCE OR A PATTERN stands while one of its grounds stands (else `ungrounded`).
  3 · THE CARD'S WORDS. The headline (the move, or the reading when there is no move) stands on the lines
      of the facts the move rests on and the file's own head; the situation, what done looks like and a
      proposed kind on every standing fact's lines; the draft on the whole dossier. A number corrected in a
      fact is corrected wherever the card repeats it. A headline that fails HOLDS a moving review; a
      situation, a done-when, a draft or a proposed kind that fails is WITHHELD — the card shows the rest.
  4 · THE RIGHT PEOPLE (§3.3). A draft goes to someone the file's mail shows (`to`): with no `to`, or to
      someone not on the file, the draft is withheld; to us, the move is held; to the connector that
      introduced the file's counterparty — on a file that is not the connector's own — the review's own
      alternative becomes the move if it checks (the draft withheld), else the move is held. A move that
      answers an ask must answer one that waits on US. A card text that calls the founder "the founder" or
      names us as a party is NOTED (`speaks_of_you`, F178), for the live pass to count; rewording a card is
      `STEP-14`'s.
  5 · THE FATE. No fact stands: REFUSED. A moving review (act, find out) whose move lost a fact it rests on,
      whose headline failed, or whose recipient is us or a connector with no alternative: HELD — the file
      goes to Investigation and asks ONE question. Otherwise SHOWN — a find-out review asking its own move.
      Whether the ask a move answers is already ANSWERED is read live (`reason/expert/answered`).

WHAT `validate` STILL REFUSES WHOLE — the structure (`STRUCTURAL`): a moving mode with no move, a move
resting on a fact the review does not have, a stage the playbook does not name. Grounding is per line here,
and a number in prose no founder is shown — a hypothesis, a scenario, the appraisal's reasons — is NOTED
(`unheld_number`), not refused: it reaches nobody, and a live model's hypotheses hold numbers.

Pure: no I/O, no clock, no model. The same review and dossier, the same verdicts, byte for byte.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field

from genios_engine.contracts import claim_check as C
from genios_engine.contracts.expert_review import (
    MOVING, NO_NEXT_MOVE, UNGROUNDED_MOVE, UNKNOWN_STAGE, ExpertReview, number_tokens)
from genios_engine.platform.grounding import corpus_of, digit_runs, invention_ok
from genios_engine.platform.self_identity import names_us
from genios_engine.reason.expert.decide import is_event
from genios_engine.reason.expert.dossier import DossierLine, FilePeople, Person, lines_by_id

#: What `validate` still refuses whole — the review's STRUCTURE, never its grounding.
STRUCTURAL: frozenset[str] = frozenset({NO_NEXT_MOVE, UNGROUNDED_MOVE, UNKNOWN_STAGE})
#: A quote is the mail's own words — at least this many of them.
QUOTE_MIN_WORDS = 2
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
_MONTH = re.compile(r"\b(?:January|February|March|April|May|June|July|August|September|October|November|"
                    r"December)\b")
#: An ask a meeting answers (`contracts/open_loop.ASK_KINDS`): a meeting asked for, or a demo.
MEETING_ASKS: frozenset[str] = frozenset({"meeting_request", "demo_requested"})
#: How the dossier prints an open ask, and a meeting — held, or booked ahead (`reason/expert/dossier`).
_ASKED = re.compile(r"^- \[(?P<ask>loop:[^\[\]\s]+)\] (?P<kind>[\w-]+), .*open since "
                    r"(?P<at>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC")
_MET = re.compile(r"\[(?P<evt>[^\[\]\s:]+)\] (?:(?P<held>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC · a meeting\b"
                  r"|a meeting at (?P<booked>\d{4}-\d{2}-\d{2} \d{2}:\d{2}) UTC)")
#: How a calculator prints its sample size, never its value (`contracts/measured.Measured.says`).
_SAMPLE = re.compile(r"\(n\s*=\s*\d[^)]*\)|\b\d+ times\b")
_FACT_REF = re.compile(r"^fact:(\d+)$")
#: An id as the dossier prints it — never a number, whatever digits it holds (`evt_marco_0811`).
_PRINTED_ID = re.compile(r"\[[^\[\]\s]+\]")
_THE_FOUNDER = re.compile(r"\bthe founder\b", re.I)


# ── words ─────────────────────────────────────────────────────────────────────────────────────────

def _flat(text: str | None) -> str:
    """A text as a quote is matched: compatibility-folded and lowercased, quote marks gone, every other
    mark but those inside a word (an address, a decimal, a hyphen) a space, the spacing one space."""
    value = unicodedata.normalize("NFKC", str(text or "")).casefold()
    value = re.sub(r"[\"'`“”‘’«»]", "", value)
    value = re.sub(r"[^\w\s@.%$€£₹-]", " ", value)
    value = re.sub(r"(?<!\w)[.@%-]+|[.@%-]+(?!\w)", " ", value)
    return " ".join(value.split())


def quoted_in(quote: str | None, words: Iterable[str]) -> bool:
    """Do these mail words hold this quote — whole words, at least `QUOTE_MIN_WORDS` of them?"""
    q = _flat(quote)
    if len(q.split()) < QUOTE_MIN_WORDS:
        return False
    return any(f" {q} " in f" {_flat(w)} " for w in words)


def value_of(line: str, ref: str) -> str | None:
    """The one value a calculator prints for `ref` on `line` — its own clause's number, the sample size
    aside — or None when the clause holds none, or more than one (a rate, "2 of 5")."""
    marker = f"[{ref}]"
    if marker not in line:
        return None
    clause = re.split(r"\]|;", line.split(marker, 1)[0])[-1]
    values = numbers_in(_SAMPLE.sub(" ", clause))
    return next(iter(values)) if len(values) == 1 else None


def numbers_in(text: str | None) -> frozenset[str]:
    """Every number a text writes — the ids it prints aside: an id's digits are no number."""
    return number_tokens(_PRINTED_ID.sub(" ", str(text or "")))


def _swap(text: str, corrections: dict[str, str]) -> str:
    """`text` with each corrected number replaced by its calculator's value, as a whole number."""
    for old, new in sorted(corrections.items()):
        text = re.sub(rf"(?<![\d.,]){re.escape(old)}(?!\d|[.,]\d)", new, text)
    return text


def answered_by(dossier_text: str, ask: str) -> str | None:
    """The meeting that answers a MEETING ask — on the file, after it was asked, held or booked ahead —
    as the dossier prints both; None for any other ask, or none since. A closed ask needs no reading: the
    dossier shows open asks only, so a move cannot name one (`validate`, `unknown_evidence`)."""
    opened = kind = None
    for line in dossier_text.splitlines():
        if (m := _ASKED.match(line.strip())) is not None and m.group("ask") == ask:
            kind, opened = m.group("kind"), m.group("at")
            break
    if kind not in MEETING_ASKS or opened is None:
        return None
    for line in dossier_text.splitlines():
        for m in _MET.finditer(line):
            if (m.group("held") or m.group("booked")) > opened:        # the dossier's own clock, as text
                return m.group("evt")
    return None


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


def _invented(text: str, corpus: str, people: FilePeople) -> str | None:
    """The first NAME `text` writes that `corpus` and our own names do not hold — the card validator's own
    rule (`platform/grounding.invention_ok`), its numbers left to `number_tokens` — or None."""
    held, _nums = corpus_of([corpus, *people.our_names])
    plain = _EARNED.sub(lambda m: m.group(0).lower(), text)
    # A month written out is the month its lines write short — "4 Aug" grounds "August" (F51, 12 Oct): a
    # calendar word, never an invented name. A month its lines never write stays a name, and is refused.
    shorts = {w for w in re.findall(r"[a-z]+", held) if len(w) >= 3}
    plain = _MONTH.sub(lambda m: m.group(0).lower() if any(m.group(0).lower().startswith(w) for w in shorts)
                       else m.group(0), plain)
    ok, why = invention_ok(plain, held, digit_runs(plain))
    return None if ok else (why or "name")


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
    corrections: dict[str, str] = field(default_factory=dict)

    @property
    def names(self) -> str:
        """The file's people as words — whom a fact may name wherever it cites (the asker of an ask, the
        writer of a mail): the file shows them; a name it does not show is still refused."""
        return "\n".join(f"{p.name or ''} {p.key or ''}" for p in self.people.people)

    def items(self, ids: Iterable[str]) -> str:
        """The dossier items of `ids`, once each, in the order asked: each id's OWN entry — the item whose
        line it heads (`- [id] …`: a touch with its words, an ask, a situation) — or, for an id no line
        heads (a calculator), every item that prints it. A mention elsewhere (the coverage line naming
        the touch that answered our last mail) is no line of the touch: its dates are not the touch's."""
        out: list[str] = []
        for i in ids:
            places = self.lines.get(i, ())
            own = [dl for dl in places if dl.line.startswith(f"- [{i}]")]
            out += [dl.item for dl in (own or places)]
        return "\n".join(dict.fromkeys(out))

    def say(self, line: str, verdict: str, reason: str | None = None, detail: str = "") -> None:
        self.verdicts.append(C.LineVerdict(line, verdict, reason, detail))

    def why(self, line: str) -> str:
        return next((f"{v.reason}: {v.detail}" if v.detail else str(v.reason)
                     for v in self.verdicts if v.line == line and v.verdict == C.DROPPED), "dropped")

    def stands(self, text: str, corpus: str, *, head: bool = True) -> tuple[str | None, str]:
        """`text` with its corrected numbers swapped in, when every number of it is on `corpus` and every
        name on `corpus` (with the file's own head, and our own names) — else None, and the first thing
        that is not. The head grounds a NAME — the counterparty, its introducer — never a number: its
        dates and times would ground any number at all."""
        swapped = _swap(text, self.corrections)
        stray = sorted(numbers_in(swapped) - numbers_in(corpus) - set(self.corrections.values()))
        if stray:
            return None, f"number:{stray[0]}"
        names = "\n".join([corpus, self.people.head, self.names]) if head else corpus
        return (swapped, "") if (why := _invented(swapped, names, self.people)) is None else (None, why)

    def text(self, line: str, text: str | None, corpus: str, *, speaks: bool = True,
             head: bool = True) -> str | None:
        """Check one of the card's texts; record its verdict (and, when it speaks of you, the note)."""
        if not text:
            return None
        checked, why = self.stands(text, corpus, head=head)
        if checked is None:
            self.say(line, C.DROPPED, C.WRONG_NUMBER if why.startswith("number:") else C.UNSUPPORTED, why)
        elif checked != text:
            self.say(line, C.CORRECTED, C.BY_CALCULATOR, f"{text} -> {checked}")
        else:
            self.say(line, C.KEPT)
        if speaks:
            found = _THE_FOUNDER.search(text)
            if found or names_us(text, self.people.us, self.people.our_names):
                self.say(line, C.NOTED, C.SPEAKS_OF_YOU, found.group(0) if found else "us")
        return checked


def _rested_on(review: ExpertReview) -> set[int]:
    """The facts, by number, the move rests on — every fact when it names none; none without a move,
    for there is nothing to hold."""
    move = review.next_move
    if move is None:
        return set()
    named = {int(m.group(1)) for r in move.rests_on if (m := _FACT_REF.match(r)) is not None}
    return named or set(range(1, len(review.facts) + 1))


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
    worded = [dl.words for e in fact.evidence if is_event(e) for dl in run.lines[e] if dl.words]
    if decisive and worded:
        if not fact.quote:
            run.say(line, C.DROPPED, C.UNQUOTED)
            return False
        if not quoted_in(fact.quote, worded):
            run.say(line, C.DROPPED, C.MISQUOTED, fact.quote)
            return False
    own = "\n".join([run.items(fact.evidence), fact.quote or ""])
    why = _invented(fact.claim, "\n".join([own, run.people.head, run.names]), run.people)
    if why is not None:
        run.say(line, C.DROPPED, C.UNSUPPORTED, why)
        return False
    missing = sorted(numbers_in(fact.claim) - numbers_in(own))            # its own lines, never the head
    if not missing:
        run.say(line, C.KEPT)
        return True
    calculators = [e for e in fact.evidence if e.startswith("num:")]
    values = {v for e in calculators for dl in run.lines[e] if (v := value_of(dl.line, e)) is not None}
    if len(missing) == 1 and len(calculators) == 1 and len(values) == 1:
        value = next(iter(values))
        run.corrections[missing[0]] = value
        run.say(line, C.CORRECTED, C.BY_CALCULATOR, f"number:{missing[0]} -> {value} ({calculators[0]})")
        return True
    run.say(line, C.DROPPED, C.WRONG_NUMBER, f"number:{missing[0]}")
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
            eva.expected, eva.actual, sc.do_nothing, sc.act, sc.best, sc.worst, *sc.signals_to_watch,
            *review.appraisal.reasons, review.alternative, review.wait_or_stop]


def check_review(review: ExpertReview, dossier_text: str, people: FilePeople, *,
                 evidence_ids: Iterable[str] | None = None) -> C.CheckedReview:
    """`review`, checked line by line against the dossier it was written from (see the module docstring).
    `evidence_ids` — the dossier's own catalogue — narrows what counts as printed to exactly what the
    dossier cited; without it, every bracketed id of the text counts."""
    run = _Run(review=review, lines=lines_by_id(dossier_text, evidence_ids), people=people)
    rested = _rested_on(review)
    standing = {n for n in range(1, len(review.facts) + 1) if _fact(run, n, n in rested)}
    if not standing:
        return C.CheckedReview(verdicts=tuple(run.verdicts), fate=C.REFUSED, cited=(),
                               because=C.NOTHING_STANDS, words=C.CardWords(None, None, None, None, None))
    _grounds(run, "inference", review.inferences, standing)
    _grounds(run, "pattern", review.patterns, standing)
    unheld = sorted(set().union(*(numbers_in(t) for t in _prose(review))) - numbers_in(dossier_text))
    if unheld:
        run.say("prose", C.NOTED, C.UNHELD_NUMBER, ", ".join(f"number:{n}" for n in unheld))

    def corpus(numbers: Iterable[int]) -> str:
        facts = [review.facts[n - 1] for n in sorted(numbers)]
        return "\n".join([run.items(e for f in facts for e in f.evidence), *(f.quote or "" for f in facts)])

    standing_corpus, move_corpus = corpus(standing), corpus(rested & standing)
    move = review.next_move
    said = move.what if move is not None else review.frames.primary
    headline = run.text("move", said, move_corpus if move is not None else standing_corpus)
    situation = run.text("situation", review.frames.primary, standing_corpus)
    done_when = run.text("done_when", review.done_when, standing_corpus)
    if review.proposed_kind is not None:
        pk = review.proposed_kind
        unseen = [e for e in pk.evidence if e not in run.lines]
        if unseen:
            run.say("kind", C.DROPPED, C.UNKNOWN_EVIDENCE, unseen[0])
        else:
            run.text("kind", pk.why, run.items(pk.evidence), speaks=False)

    held: str | None = None
    question: str | None = None
    draft = to = None
    if review.draft:
        to = move.to if move is not None else None
        draft = run.text("draft", review.draft, dossier_text, speaks=False, head=False)
        if not to:
            run.say("to", C.DROPPED, C.NO_RECIPIENT)
        elif _is_us(to, people):
            run.say("to", C.DROPPED, C.RECIPIENT_IS_US, to)
            held = f"{C.RECIPIENT_IS_US}: {to}"
            question = f"Whom should “{said}” go to? It is addressed to you."
        elif people.connector is not None and matches(to, people.connector) \
                and not matches(to, people.counterparty):
            run.say("to", C.DROPPED, C.RECIPIENT_IS_CONNECTOR, to)
            other, _ = run.stands(review.alternative, move_corpus) if review.alternative else (None, "")
            them = people.counterparty.name or people.counterparty.key
            if other is not None and not matches(other, people.connector):
                run.verdicts = [v for v in run.verdicts if v.line != "move" or v.verdict == C.NOTED]
                run.say("move", C.CORRECTED, C.BY_ALTERNATIVE, f"{said} -> {other}")
                headline, to = other, them
            else:
                held = f"{C.RECIPIENT_IS_CONNECTOR}: {to}"
                question = f"“{said}” goes to {to}, who introduced {them}. Whom should it go to?"
        elif not any(matches(to, p) for p in people.people):
            run.say("to", C.DROPPED, C.RECIPIENT_NOT_ON_FILE, to)
        else:
            run.say("to", C.KEPT)
        if any(v.line == "to" and v.verdict == C.DROPPED for v in run.verdicts):
            draft = None                    # its words were for someone it may not go to
    met = None
    if move is not None and move.answers:
        if move.answers not in run.lines:
            # An ask its dossier never printed: whether it is answered cannot be read — the line drops,
            # as a fact citing an unshown id does; the move stands on its facts.
            run.say("answers", C.DROPPED, C.UNKNOWN_EVIDENCE, move.answers)
        elif any("we wait on them" in dl.line for dl in run.lines.get(move.answers, ())):
            run.say("answers", C.DROPPED, C.NOT_OURS_TO_ANSWER, move.answers)
        elif (met := answered_by(dossier_text, move.answers)) is not None:
            run.say("answers", C.DROPPED, C.ANSWERED, f"{move.answers} by {met}")
        else:
            run.say("answers", C.KEPT)

    fate = C.SHOWN
    if review.mode in MOVING and move is not None:
        fell = sorted(rested - standing)
        if fell:
            held = f"{run.why(f'fact:{fell[0]}')} (fact {fell[0]})"
            claim = review.facts[fell[0] - 1].claim.rstrip(".")
            question = f"Is it so: “{claim}”? It is not in what it cites."
        elif headline is None:
            held = f"{run.why('move')} (the move)"
            question = f"Is it so: “{said.rstrip('.')}”? It is not in what it rests on."
        if met is not None:
            # Already done (§3.4): whatever else the move lacked, it is moot — the ask it answers is
            # answered. One ask, and only it (replay 04): no other loop of the file is touched.
            fate, held, question = C.SUPPRESSED, f"{C.ANSWERED}:{met}", None
        elif held:
            fate = C.HELD
        elif review.mode == "find_out":
            question = headline
    shown = fate == C.SHOWN
    grounds = [review.facts[n - 1] for n in sorted(rested & standing)]
    words = C.CardWords(headline=headline if shown else None, situation=situation, done_when=done_when,
                        draft=draft if shown else None, to=to if shown and draft else None,
                        evidence=tuple(e for f in grounds for e in f.evidence) if shown else (),
                        quotes=tuple(f.quote for f in grounds if f.quote) if shown else ())
    return C.CheckedReview(
        verdicts=tuple(run.verdicts), fate=fate, words=words,
        cited=tuple(e for n in sorted(standing) for e in review.facts[n - 1].evidence),
        question=question if (fate == C.HELD or (shown and review.mode == "find_out")) else None,
        because=held if fate in (C.HELD, C.SUPPRESSED) else None)


__all__ = ["EARNED", "MEETING_ASKS", "QUOTE_MIN_WORDS", "STRUCTURAL", "answered_by", "check_review", "matches",
           "quoted_in", "value_of"]
