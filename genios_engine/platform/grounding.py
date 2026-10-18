"""The invention rule — one rule for every text the engine shows a founder (moved here by STEP-13).

`speedrun008/YC-II W27/` STEP-13 §8.3 N1, tree `yc2_w27_s13` M35.C2.L-logic.V0.U08. The card validator's
V-02 (`deliver/render.invention_ok`: every name and number of a text must be in what grounds it) lived in
`deliver/`, the delivery layer — so reasoning, which sits below it (`genios_engine/LAYERS.py`), could not
ask it: an import upward is a build failure (`tests/test_layer_topology.py`). The executive layer had
already met that wall and grown its OWN copy (`executive/validate.py`), which is how one rule becomes two
that drift. STEP-13 holds the expert's claims to the card validator's own rule (`reason/expert/verify`),
so the rule moved here, to the cross-cutting layer every layer may import — BYTE FOR BYTE: the code below
is `deliver/render.py`'s as it stood at `c97155cd`, its comments included, and `deliver/render`
re-exports every name under the name its callers have always imported. Nothing about what it refuses
changed. Two things are added: public names for the same objects, and `corpus_of`, which reads plain texts
(a dossier's lines) the way `deliver/render._corpus` reads a card's facts — lowercased, every ISO date
expanded into the forms a faithful sentence may write it in, with their digit runs.

Pure: no I/O, no clock, no model.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from datetime import datetime

def _digit_runs(s: str) -> set[str]:
    return set(re.findall(r"\d+", s))


#: Ordinary capitalised English that is grammar, not a claim about the world.
#:
#: The guard exists to catch an INVENTED ENTITY — a person, company or product the facts do not
#: support. It was catching every capitalised token instead, and its dictionary was the same
#: five-field fact record the model had been given, so any readable sentence failed: "Thanks",
#: "Best", "Regards", "Monday", "Rohit". 25 of one org's 41 cards were rejected this way and
#: shipped as empty template stubs — the model was paid for, produced correct copy, and the copy
#: was thrown away for saying "Thanks".
_GRAMMAR_WORDS = frozenset({
    # greetings, sign-offs and connectives that start a clause
    "hi", "hey", "hello", "dear", "thanks", "thank", "regards", "best", "cheers", "sincerely",
    "warmly", "please", "sorry", "congrats", "congratulations", "welcome", "yes", "no", "ok",
    "okay", "sure", "great", "happy", "glad", "looking", "following", "just", "quick", "also",
    # Ordinary words that open a sentence in this kind of copy. Every one below was a real
    # rejection on a live card, not a guess. Position cannot replace this list: the tests hold
    # "Initech's team replied" and "Three items are open" — both sentence-initial, both correctly
    # judged — against "Decision needed on scope", which must not be. Only the WORD separates
    # them, so the list is the mechanism and each entry has to be earned by an observed failure.
    "cannot", "unable", "entity", "relationship", "worth", "deadline", "agenda", "new",
    "open", "closed", "active", "pending", "waiting", "still", "both", "each", "every",
    "after", "before", "during", "until", "unless", "once", "here", "there", "their",
    "meeting", "call", "email", "reply", "response", "message", "thread", "draft", "deck",
    "budget", "price", "pricing", "proposal", "contract", "invoice", "renewal", "demo",
    "confirm", "share", "schedule", "propose", "suggest", "offer", "ask", "check", "review",
    # Month and weekday NAMES are deliberately absent: a wrong month is exactly the invention
    # this guard exists for, and blanket-exempting the calendar would let "March 22" through on
    # evidence dated July. They are grounded in `_expand_dates` instead, from the fact date —
    # which grounds the RIGHT day and still rejects the wrong one.
    "decision", "context", "next", "status", "update", "note", "reason", "summary", "action",
    "and", "but", "so", "then", "if", "when", "while", "since", "as", "at", "on", "in", "for",
    "to", "of", "with", "from", "this", "that", "these", "those", "it", "we", "i", "you", "they",
    "he", "she", "our", "your", "their", "my", "his", "her", "there", "here", "what", "which",
    "who", "how", "why", "let", "lets", "im", "ive", "ill", "id", "well", "would", "could",
    "should", "can", "will", "shall", "may", "might", "is", "are", "was", "were", "be", "been",
    # imperative and clause-opening verbs. A draft written to a person opens with one of these
    # far more often than with anything else, and they are the reason a positional exemption
    # looked necessary — but position cannot tell "Reach" from "Initech", so the word does.
    "reach", "send", "ask", "book", "share", "follow", "reply", "confirm", "check", "give",
    "take", "move", "set", "draft", "note", "consider", "keep", "make", "offer", "propose",
    # Measured 2026-09-17 on live cards, each one a V-02 rejection of a real draft. `insert` is
    # NOT here on purpose: `V-02:name:INSERT` was a template placeholder leaking into a draft
    # body, which is the guard doing its job, and exempting the word would ship "[INSERT NAME]"
    # to a customer. `three` is not here either — `test_a_spelled_number_is_still_a_claim` pins
    # that deliberately, so the guard cannot depend on whether the model wrote "3" or "Three".
    "address", "reschedule", "clarify", "specifically", "repeating", "differentiation",
    "measured", "vcs",
    "suggest", "remind", "wait", "hold", "close", "open", "start", "stop", "try", "use", "add",
    "update", "review", "schedule", "forward", "introduce", "loop", "push", "bring", "get", "go",
    "come", "do", "does", "did", "have", "has", "had", "need", "want", "know", "think", "see",
    "look", "find", "help", "work", "call", "meet", "write", "read", "show", "tell", "put",
    "run", "turn", "watch", "answer", "handle", "resolve", "flag", "raise", "drop", "pick",
    "deliver", "chase", "nudge", "surface", "escalate", "assign", "attach", "include", "mention",
    "let", "leave", "return", "expect", "plan", "prepare", "build", "create", "define", "decide",
    # ORDINARY NOUNS AND CLAUSE-OPENERS THAT ARRIVE CAPITALISED. A card body is prose, and prose
    # capitalises the first word of every sentence — "Before the call...", "Decision needed on
    # pricing", "Meeting notes attached". None of these is entity-shaped, and all three were
    # rejected as invented companies on the design partner's live cards. They stay in the guard's
    # world only as ordinary vocabulary: a real account genuinely called "Meeting" would pass, and
    # that is the correct trade — the guard exists to catch a name nobody mentioned, not to
    # arbitrate which English words a business may use.
    "before", "after", "during", "once", "until", "unless", "however", "meanwhile", "otherwise",
    "given", "based", "regarding", "attached", "per", "via", "both", "either", "neither", "each",
    "every", "any", "all", "some", "most", "more", "less", "last", "next", "final",
    # Earned on 2026-08-30 from the design partner's 56 live cards, counts from `reject_detail`.
    # Every one is a form of a word ALREADY in this list, which is why they read as omissions
    # rather than as new judgements: `apologies` opens a late reply (6 rejected artifacts) and
    # `apologise` is nowhere here; `reaching` is "Reaching out about…" and `reach` is above it;
    # `met` is `meet`, `wanted` is `want`, `introduction` is `introduce`, and `where` is the one
    # wh-word missing from a row that already holds who/how/why/what/which/when. The suffix rule
    # cannot recover any of them — it strips ve/ll/re/s/t/d/m, and "met" is not "meet" plus a
    # letter — so each has to be written down.
    "apologies", "apologise", "apologize", "reaching", "where", "met", "wanted", "introduction",
    # Earned on 2026-08-27, each from a card that fell back to template copy on this word alone.
    # `the` is the striking one: the commonest word in English was not here, so any model
    # sentence opening "The proposal…" was read as an invented company. Articles are a closed
    # class and cannot be a name on their own, so all three go in together rather than waiting
    # for `a` and `an` to each cost their own card.
    "the", "a", "an",
    # The copy's OWN vocabulary, which the model naturally echoes back: it is told about
    # sentiment and engagement, then rejected for saying "Positive signals" or "Multiple threads
    # are open". A word the system itself put in the prompt cannot be evidence of invention.
    "positive", "negative", "neutral", "mixed", "multiple", "single", "fit", "unfit",
    "presentation", "signals", "engagement", "momentum", "sentiment", "contact",
    # NOT exempt, deliberately, and for the reason stated above the calendar note: a number word
    # is a factual claim ("Three open items" when there are two), and exempting the spelled form
    # while `_digit_runs` still checks "3" would make the guard depend on how the model chose to
    # write the same claim. Same for today/tomorrow/yesterday — those are date claims, and dates
    # are the one thing this guard is most careful about.
    "decision", "decisions", "meeting", "meetings", "call", "calls", "email", "emails",
    "reply", "replies", "thread", "threads", "deal", "deals", "account", "accounts", "team",
    "teams", "context", "status", "update", "updates", "summary", "notes", "note", "question",
    "questions", "answer", "answers", "options", "option", "action", "actions", "step", "steps",
    "timeline", "budget", "pricing", "price", "proposal", "contract", "invoice", "demo", "trial",
    "pilot", "scope", "risk", "risks", "issue", "issues", "blocker", "blockers", "goal", "goals",
    "problem", "problems", "solution", "product", "platform", "service", "support", "sales",
    "revenue", "cost", "value", "time", "today", "tomorrow", "yesterday", "week", "month",
    "quarter", "year", "morning", "afternoon", "evening", "now", "soon", "later",
    # Earned 14 Oct (STEP-15 M45.C5.L-integration.V1.U02's acceptance, the first time this guard
    # was ever run against `executive/morning_template.words_for`'s OWN words): "Quiet for 7
    # days." opens a WATCHED or STUCK line's second sentence — `words_for`'s own rendering, never
    # a model's — and read as an invented entity for the same reason "Pending"/"Waiting" above
    # already needed the guard's forgiveness. The template's faithful words failing the check they
    # are the ground truth for is the acceptance test's own job to catch.
    "quiet",
    # Same run, same cause: "By 9 Oct." opens the second sentence of a DECISION or PROMISE line
    # (`words_for`'s own "By {_day(...)}." for a deadline or a due date) — a preposition, not an
    # entity, and the calendar date after it is already grounded by `_expand_dates`, never by this
    # word.
    "by",
})

# Calendar words are deliberately NOT exempt. A weekday or a month is not an entity, but it IS a
# factual claim, and `_expand_dates` already puts the grounded forms of every fact date into the
# corpus. So "July 22" passes when the fact says 2026-07-22 and "March 22" is rejected — a draft
# that proposes a date the evidence does not support is inventing it, which is exactly what the
# guard is for. Exempting them would have quietly licensed made-up dates in outgoing mail.


def _proper_nouns(s: str) -> list[str]:
    """Capitalised tokens that could be an INVENTED entity — never ordinary grammar.

    Two filters, and both are needed — neither alone is right.

    POSITION IS NOT USED, and that is the point. Exempting a sentence's first word looks safe —
    "Reach out to them" opens with a capital that is pure grammar — but it also exempts
    "Initech will vouch for us", so an invented company escapes simply by starting a sentence.
    Position cannot distinguish the two; only the word can.

    So a stop-list decides, covering both the greetings and sign-offs that a positional rule
    misses in a multi-paragraph draft ("Thanks", "Best", the signature) and the imperative verbs
    a positional rule was there to protect ("Reach", "Send", "Book"). Everything left over that
    is capitalised is entity-shaped, which is exactly what the guard is for.
    """
    out: list[str] = []
    # A HYPHEN IS A WORD BOUNDARY, not a character to delete. The strip below removes every
    # non-alphanumeric, which turned "AI-guided" into "AIguided" — a token in no language and
    # therefore in no corpus, so the guard read it as an invented company and threw the card
    # away. Exactly the failure the apostrophe rule below already documents, wearing a different
    # punctuation mark. Judging the parts separately is what makes the question answerable:
    # "guided" is lowercase and never reaches the check, and "AI" is judged against the corpus
    # on its own, which is the right question about it.
    # THE SEPARATORS, AND WHY THE LIST GREW TWICE. Splitting only on whitespace, dashes and the
    # slash left every OTHER interior mark to be deleted by `core` — which does not separate two
    # words, it WELDS them. `Swerashi:GeniOS` became `SwerashiGeniOS`, `Centre(ITC)` became
    # `CentreITC`, `Ben&Jerry` became `BenJerry`: tokens in no language and therefore in no
    # corpus, so each threw its card away. Identical to the `AI-guided` -> `AIguided` failure the
    # hyphen rule below already documents, reached through a different mark.
    #
    # `.` AND `@` ARE DELIBERATELY ABSENT. `nikhil@addis.im` and `titancapital.vc` are single
    # tokens the corpus holds whole, and splitting them would ask the guard about `im` and `vc`
    # instead of about the address — the opposite mistake, made for the same reason.
    for w in re.split(r"[\s‐-―/:;,()\[\]{}&|]+|(?<=[A-Za-z0-9])-(?=[A-Za-z0-9])", s):
        # THE APOSTROPHE IS PART OF THE WORD. Stripping every non-alphanumeric turned "We've"
        # into "Weve", "What's" into "Whats" and "They're" into "Theyre" — capitalised tokens
        # in no dictionary, so the guard read each as an invented company and threw the draft
        # away. Eight of the eleven artifact rejections on the design partner's live cards were
        # exactly this. A contraction is graded on its BASE word: "We've" is "we", which is
        # grammar. An entity's possessive ("Initech's") reduces to "Initech" and is still judged.
        bare = w.strip("\"'\u2018\u2019\u201c\u201d(),.;:!?[]{}")   # quotes AROUND a word are not part of it
        core = re.sub(r"[^A-Za-z0-9]", "",
                      _fold(re.split(r"[\u2019']", bare, maxsplit=1)[0]))
        if len(core) < 2 or not core.isalpha():
            continue
        low = core.lower()
        if low in _GRAMMAR_WORDS:
            continue
        # A contraction that reached us ALREADY stripped. The apostrophe split above only helps
        # while the apostrophe survives, and by the time copy gets here it often has not — the
        # live cards rejected `Weve`, `Whats` and `Theyre` as invented companies, which is the
        # apostrophe rule failing in the one case it exists for. Grade the base word: "Weve" is
        # "we", which is grammar. `Wells` is not, because "well" is not a grammar word and the
        # suffix test alone never decides.
        if any(low.endswith(sfx) and low[: -len(sfx)] in _GRAMMAR_WORDS
               for sfx in ("ve", "ll", "re", "s", "t", "d", "m")):
            continue
        if core[0].isupper():
            out.append(core)
    return out


def _expand_dates(s: str) -> list[str]:
    """A faithful reformatting of a fact date is NOT invention: expand any ISO date in the facts
    into its human forms (month name + abbr + day + year) so 'July 22' for 2026-07-22 is grounded
    — while a hallucinated 'March 22' stays ungrounded (wrong month word) and is still rejected."""
    out: list[str] = []
    for m in re.finditer(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2})?", s):
        try:
            dt = datetime.fromisoformat(m.group(0).replace(" ", "T"))
        except ValueError:
            continue
        mon, abbr = dt.strftime("%B").lower(), dt.strftime("%b").lower()
        out += [mon, abbr, str(dt.day), str(dt.year), f"{mon} {dt.day}"]
        # THE CLOCK HALF, on the same principle as the month name and for the same reason it is
        # not in `_GRAMMAR_WORDS`: "UTC" and "PM" are FAITHFUL RENDERINGS of a fact timestamp, so
        # they are grounded from that timestamp and from nothing else. Two live cards were thrown
        # away over this on 2026-08-30 — `V-02:name:UTC` discarded a first-response body and
        # `V-02:name:PM` a draft reply, both for restating a time the facts carry. Blanket-
        # exempting them would license "9 AM" on an evidence timestamp of 21:00; deriving them
        # keeps the wrong one rejected. The offset is read from the ORIGINAL matched text, since
        # `fromisoformat` has already normalised it away.
        if m.group(0)[10:11] in ("T", " "):
            out.append(dt.strftime("%p").lower())
        if re.match(r"(?::\d{2}(?:\.\d+)?)?(?:\+00:00|Z)", s[m.end():m.end() + 24]):
            out += ["utc", "gmt"]
        # The WEEKDAY of a fact date is that date restated, not a new claim — "Friday" for
        # 2026-07-24 is as faithful as "July 24". A live draft was discarded whole over exactly
        # this word. Derived from the date, so a Friday that is really a Tuesday stays rejected.
        out += [dt.strftime("%A").lower(), dt.strftime("%a").lower()]
    return out


def _fold(s: str) -> str:
    """Accents off, letters kept. `Sofía` -> `Sofia`, `TÜV` -> `TUV`, `Padrón` -> `Padron`.

    THE LETTER SURVIVES, which is the whole point. `_proper_nouns` strips every character outside
    `[A-Za-z0-9]` to build its token, so before this a diacritic was DELETED rather than folded:
    `Sofía` became `Sofa` and `TÜV` became `TV`. Neither string can appear in any corpus, so the
    guard judged every non-ASCII name an invention unconditionally — including the account's own
    counterparties. Measured on the pilot: `V-02:name:Sofa` twice against a graph that holds
    "Sofía Padrón" verbatim, and `V-02:name:TV` twice on cards about TÜV Austria.

    Applied to BOTH sides in `invention_ok`, because folding one and not the other just moves
    which spelling can never match.
    """
    return "".join(ch for ch in unicodedata.normalize("NFKD", s)
                   if not unicodedata.combining(ch))


def _haystack(corpus_text: str) -> str:
    """The corpus, plus a punctuation-free alias for every token that has punctuation INSIDE it.

    `_proper_nouns` deletes the marks it does not split on — `.` and `@` deliberately, so that an
    address stays one token — and then asks whether the result is in the corpus, which keeps them.
    `Nikhil@Addis.im` therefore becomes `NikhilAddisim` and is compared against a corpus holding
    `nikhil@addis.im`: two strings that can never match. `_corpus` adds the quote author's address
    for exactly this case and its comment says so; adding it did not help, because the two sides
    were never normalised the same way.

    ONLY TOKENS THAT CHANGE GET AN ALIAS, and the aliases are joined by spaces. Collapsing the
    WHOLE corpus would weld its words together — "acme scope" becoming "acmescope" grounds the
    invented name "Mesco" as a substring — which is the guard quietly getting weaker in exchange
    for getting kinder. A token with no interior punctuation is already its own alias and adds
    nothing.
    """
    aliases = []
    for token in corpus_text.split():
        collapsed = re.sub(r"[^a-z0-9]", "", token.lower())
        if collapsed and collapsed != token.lower():
            aliases.append(collapsed)
    return corpus_text if not aliases else corpus_text + " " + " ".join(aliases)


def invention_ok(text: str, corpus_text: str, corpus_nums: set[str]) -> tuple[bool, str | None]:
    for num in _digit_runs(text):
        if num not in corpus_nums and num not in corpus_text:
            return False, f"number:{num}"
    # Folded HERE rather than in `_corpus` so every caller gets it — this function is public and
    # the tests build corpora by hand.
    folded_corpus = _haystack(_fold(corpus_text))
    for pn in _proper_nouns(text):
        if pn.lower() not in folded_corpus:
            return False, f"name:{pn}"
    return True, None


def corpus_of(texts: Iterable[str | None]) -> tuple[str, set[str]]:
    """Plain texts as the invention rule reads a corpus — as `deliver/render._corpus` reads a card's
    facts: lowercased, every ISO date expanded into its human forms, and the digit runs of all of it."""
    parts = [str(t or "") for t in texts]
    parts += [form for t in list(parts) for form in _expand_dates(t)]
    nums: set[str] = set()
    for p in parts:
        nums |= _digit_runs(p)
    return " ".join(parts).lower(), nums


# The same objects under public names — for the layers that ask the rule from outside.
GRAMMAR_WORDS = _GRAMMAR_WORDS
digit_runs = _digit_runs
proper_nouns = _proper_nouns
expand_dates = _expand_dates
fold = _fold
haystack = _haystack

__all__ = ["GRAMMAR_WORDS", "corpus_of", "digit_runs", "expand_dates", "fold", "haystack", "invention_ok",
           "proper_nouns"]
