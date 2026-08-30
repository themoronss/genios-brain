from __future__ import annotations

import json
import re
from datetime import datetime

from .slots import SENTINELS, grounded_slots

# E1 · Copy Renderer + validators (§5.10, §5.18). ONE temp-0 call fills headline, situation and
# the artifact together. Two deterministic gates stand between the model and the user:
#   V-01 length caps  — headline ≤60, situation ≤140 → reject + re-template (never truncate, Law 3)
#   V-02 invention    — every name/number/date in the output must exist in the fact set, else
#                       reject + raw-slot fallback (the hallucination guard, Law 2)
# The fallback is pure slot-interpolation from facts, so a card ALWAYS ships and is always honest.

HEADLINE_CAP = 60
SITUATION_CAP = 140


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
    for w in re.split(r"[\s‐-―/]+|(?<=[A-Za-z0-9])-(?=[A-Za-z0-9])", s):
        # THE APOSTROPHE IS PART OF THE WORD. Stripping every non-alphanumeric turned "We've"
        # into "Weve", "What's" into "Whats" and "They're" into "Theyre" — capitalised tokens
        # in no dictionary, so the guard read each as an invented company and threw the draft
        # away. Eight of the eleven artifact rejections on the design partner's live cards were
        # exactly this. A contraction is graded on its BASE word: "We've" is "we", which is
        # grammar. An entity's possessive ("Initech's") reduces to "Initech" and is still judged.
        bare = w.strip("\"'\u2018\u2019\u201c\u201d(),.;:!?[]{}")   # quotes AROUND a word are not part of it
        core = re.sub(r"[^A-Za-z0-9]", "", re.split(r"[\u2019']", bare, maxsplit=1)[0])
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


def _corpus(facts: dict, slots: dict,
            identities: tuple[str, ...] = (),
            quotes: list[dict] | None = None) -> tuple[str, set[str]]:
    """Everything the render is ALLOWED to say.

    Fact values, computed slots and human date expansions — plus the tenant's OWN identities.
    Signing a draft with the founder's own name is not a hallucination, but the corpus was built
    from the subject's facts alone, so "Best, Rohit" was rejected as an invented person on the
    account holder's own outgoing mail.
    """
    parts: list[str] = list(identities)
    # The quotes we HANDED the model must be legal for it to use. Grounding a claim means it
    # appears in the SOURCE, not merely in the extracted summary — checking a draft against the
    # fact dict alone is what made the corpus and the generator's own input the same tiny set,
    # so the only text that survived was text that repeated the facts back verbatim.
    for q in quotes or ():
        parts.append(str(q.get("quote") or ""))
        if q.get("name"):
            parts.append(str(q["name"]))
    for name, f in facts.items():
        # THE FIELD NAME IS HALF THE PROMPT, AND WAS NO PART OF THE CORPUS. `_prompt` dumps the
        # fact record with its KEYS — the model is handed `"thread.ball_in_court": "us"` and
        # writes the only English sentence that says — then the guard, which was built from the
        # VALUES alone, found no "ball" anywhere and judged it an invented company.
        #
        # Measured on the design partner's org after the 2026-08-30 re-sync: `V-02:name:Ball`
        # rejected the SITUATION line on 28 of 56 cards. Half the queue lost its written body to
        # one idiom, and because `first_response_overdue`'s fallback names no subject, 11 of
        # those collapsed onto a single byte-identical sentence in the Mac app.
        #
        # The module's law already covered this and was simply never applied to the keys: "a
        # word the system itself put in the prompt cannot be evidence of invention." A field name
        # is schema vocabulary, not a claim about the world — `response.opened_at`,
        # `derived.momentum`, `relationship.nature`. Where the extractor mints an `other.*` name
        # out of the mail itself (`other.yc_application_cycle` on this org), the token came from
        # the source text, so grounding it is right for exactly the same reason the quotes are.
        # Split on the separators so the corpus holds words rather than identifiers.
        parts.append(str(name).replace(".", " ").replace("_", " "))
        v = f.get("value") if isinstance(f, dict) else f
        s = json.dumps(v, default=str) if not isinstance(v, str) else v
        parts.append(s)
        parts.extend(_expand_dates(s))
    # GROUNDED slots only, for the same reason the prompt sees only those: a sentinel is not a
    # fact about this account, and leaving it in the corpus would license the model to say
    # "several open items" and have the invention guard agree that it was grounded.
    parts.extend(str(v) for v in grounded_slots(slots).values())
    text = " ".join(parts)
    nums = set()
    for p in parts:
        nums |= _digit_runs(p)
    return text.lower(), nums


def invention_ok(text: str, corpus_text: str, corpus_nums: set[str]) -> tuple[bool, str | None]:
    for num in _digit_runs(text):
        if num not in corpus_nums and num not in corpus_text:
            return False, f"number:{num}"
    for pn in _proper_nouns(text):
        if pn.lower() not in corpus_text:
            return False, f"name:{pn}"
    return True, None


#: Templates that read "{days}d ago" cannot render a duration the system does not have. The slot
#: collapses to the word "several", which the format string then turns into "severald" — a real
#: card shipped reading "Raised severald ago — still unanswered".
_UNKNOWN_DAYS = SENTINELS["days"]


def _interpolate(tpl: str, slots: dict) -> str:
    """Interpolate a fallback template, removing every clause we cannot substantiate.

    Saying nothing is honest; inventing a number is not; and printing a placeholder word where a
    fact belongs is neither. This started as a duration-only rule and the reason generalises to
    every slot: "No value set" and "several open items" are the same failure as "severald", worn
    differently. When a slot holds its sentinel, the clause that would have carried it is cut and
    the rest of the sentence still renders.
    """
    for name, value in sorted(slots.items()):
        placeholder = "{" + name + "}"
        if placeholder not in tpl or SENTINELS.get(name) != value:
            continue
        parts = [seg for seg in re.split(r"\s+[—·-]\s+", tpl) if placeholder not in seg]
        if parts:
            tpl = " — ".join(parts)
        # else: the placeholder has no clause of its own, so there is nothing to cut without
        # mangling the sentence — "Deliver {action} to {entity} today" would ship as "Deliver
        # to acme.com today". The sentinel stays, because a grammatical placeholder beats a
        # broken sentence and this line never reaches the model in either case.
    return re.sub(r"\s{2,}", " ", tpl.format(**slots)).strip(" —·-")


def _cap(text: str, cap: int) -> str:
    """Bring a deterministic line under `cap` WITHOUT cutting a sentence in half.

    `_fit` — whole sentences, then whole clauses — is the ladder the MODEL's output already
    walks, and the fallback was not walking it. `_trim_to_word` alone cuts at the last space
    before the cap, which is a word boundary and nothing more.

    Measured on the design partner's org after the 2026-08-30 re-sync: `first_response_overdue`
    interpolates to 165 characters against the 140 cap, and all eleven of its live cards shipped
    a body ending on the word "and" — "…not from a contract, and" — 25 characters short of the
    end of the clause. A word boundary is not a thought boundary, and a reader cannot tell a
    sentence that stopped from a card that broke.

    `_trim_to_word` stays as the last rung for the case it was written for: a single token longer
    than the cap has no sentence and no clause to fall back to.
    """
    if len(text) <= cap:
        return text
    return _fit(text, cap) or _trim_to_word(text, cap)


def _fallback(template: dict, slots: dict) -> dict:
    fb = template.get("fallback", {})
    head = _cap(_interpolate(fb.get("headline", "{entity}"), slots), HEADLINE_CAP)
    sit = _cap(_interpolate(fb.get("situation", "{stage}"), slots), SITUATION_CAP)
    # Cutting every unsubstantiated clause can empty the line. A card still has to name its
    # subject, so the entity carries it alone rather than the card shipping blank.
    head = head or _cap(str(slots.get("entity") or ""), HEADLINE_CAP)
    return {"headline": head, "situation": sit,
            "artifact": {"kind": template.get("artifact_kind", "draft"),
                         "body": "", "mode": "raw_slot"},
            "render_mode": "raw_slot", "reject_code": None}


#: Clause separators a headline is actually built from. These are the joins the authored
#: fallbacks use ("{entity} — relationship open, nothing moving") and the ones the model copies.
_CLAUSE_SPLIT = re.compile(r"\s+[—–·|]\s+|(?<=[a-z0-9]):\s+|,\s+(?=[a-z])")


def _fit_clauses(text: str, cap: int) -> str | None:
    """The longest leading run of complete CLAUSES that fits, or None if not even the first does.

    The sentence rule below cannot help a headline, because a headline is one clause-joined
    fragment with no terminal punctuation: `re.findall` returns it whole, the whole thing is over
    cap, and `_fit` returns None. Six of the design partner's twenty-four newest cards were
    rejected at 61 or 62 characters against a 60 cap and shipped the template's `{entity} —
    relationship open, nothing moving` instead — which for a contact whose address is fifty
    characters long then hard-sliced to `invoice+statements+acct_1ika5ja3kz32dpo1@stripe.com —
    relati`. A specific grounded line was replaced by a generic one cut mid-word.

    Dropping a trailing clause is the same move `_interpolate` makes when it cannot substantiate
    one, and the same move the sentence rule makes one level up. Nothing is cut mid-word and no
    ellipsis is added; what remains is whole.
    """
    parts = [p for p in _CLAUSE_SPLIT.split(text) if p and p.strip()]
    if len(parts) < 2:
        return None                 # nothing to drop — the sentence rule is the only hope left
    kept = parts[0].strip()
    if len(kept) > cap:
        return None
    for part in parts[1:]:
        candidate = f"{kept} — {part.strip()}"
        if len(candidate) > cap:
            break
        kept = candidate
    return kept or None


def _trim_to_word(text: str, cap: int) -> str:
    """Cap a line at a WORD boundary. A hard slice is what put
    `invoice+statements+acct_…@stripe.com — relati` in front of a founder."""
    if len(text) <= cap:
        return text
    cut = text[:cap]
    space = cut.rfind(" ")
    if space <= 0:
        # A single token longer than the cap has no boundary to fall back to; slicing it is the
        # only option left, and it is still better than shipping nothing. `rfind` returns -1
        # here, and `cut[:-1]` would silently drop a character off every such line.
        return cut
    return (cut[:space].rstrip(" —–·|,:") or cut).strip()


def _fit(text: str, cap: int) -> str | None:
    """The longest leading run of COMPLETE sentences that fits; whole clauses when there is no
    sentence to find; None when neither has anything that fits.

    This is not truncation (Law 3): nothing is cut mid-word, no ellipsis is added, and what
    remains is a whole grounded sentence — the same move `_interpolate` makes when it drops a
    clause it cannot substantiate. It exists because the alternative was measurably worse. Ten of
    the design partner's eighteen compiled cards came back 142–158 characters against a 140 cap,
    and the over-cap rejection replaced a correct, specific sentence with the fallback's bare
    `{stage}` slot: the literal word "open". Dropping the trailing sentence keeps the half that
    carries the meaning; falling back kept nothing.
    """
    if len(text) <= cap:
        return text
    kept = ""
    # SENTENCES FIRST, CLAUSES ONLY AFTER. This order was the other way round, and a clause
    # boundary can sit INSIDE a sentence — `_CLAUSE_SPLIT` breaks on ", owner" as readily as on an
    # em-dash — so the clause rule was allowed to keep a leading run that ended half a sentence
    # in. `queue_overloaded`'s 157-character fallback came out as "…has stopped moving. No queue",
    # stopping two words into its second sentence, while the sentence rule had a whole 93-character
    # answer available. Clause-splitting exists for the case the docstring of `_fit_clauses` names —
    # a headline, which is one fragment with no terminal punctuation and therefore no sentence run
    # to find — and asking it second costs that case nothing: the sentence rule returns nothing
    # there, and the clause rule still runs.
    #
    # A dot inside a hostname or an address is not a sentence boundary. Splitting naively cut
    # "antler.co passed on Residency" down to "antler." and
    # "deepthi.chandrashekhar@nsrcel.iimb.ac.in replied" to "deepthi. chandrashekhar@nsrcel. iimb.
    # ac." — headlines that name a company nobody can find. A boundary needs whitespace after the
    # stop, which is what separates "…ac.in replied" from "…replied. Next".
    for sentence in re.findall(
            r"(?:[^.!?]|[.!?](?!\s|$))+(?:[.!?]+(?=\s|$))?", text):
        # Normalise as we join: a sentence carries its leading space and `kept` already ends in
        # one, so the naive concatenation measures a double space and rejects a run that fits.
        candidate = re.sub(r"\s+", " ", kept + sentence).strip()
        if len(candidate) > cap:
            break
        kept = candidate + " "
    return kept.strip() or _fit_clauses(text, cap)


def _prompt(reason_code: str, template: dict, facts: dict, slots: dict,
            quotes: list[dict] | None = None) -> str:
    kind = template.get("artifact_kind", "draft")
    # WHAT WAS ACTUALLY SAID. The prompt used to be five typed key/value pairs and a rule id, and
    # the model was asked to write a thread-specific reply from that — so the copy had no content
    # because there was no content in the prompt. These quotes come from graph_source_refs, one
    # join from where the renderer was already looking.
    said = ""
    if quotes:
        lines = "\n".join(f'- [{q.get("kind")}] "{q.get("quote")}"' for q in quotes[:8])
        said = (f"\nWhat was actually said (verbatim, newest first) — quote or paraphrase THESE, "
                f"they are what makes the card specific:\n{lines}\n")
    # GROUNDED SLOTS ONLY. `compute_slots` fills an absent fact with a sentinel — days
    # "several", stage "open", money "no value set", concerns "several open items" — so the
    # deterministic fallback template still reads as a sentence. Handing those to the model
    # labelled "Key slots" presents them as facts, and the model correctly writes down what it
    # was told: all eighteen compiled cards on the design partner's org came back saying
    # "several open items blocking commitment ... in open stage for several days ... No value
    # set" about accounts with no deal in play. A slot we could not compute is not a fact about
    # the account, and the model must never see it.
    known = grounded_slots(slots)
    known_line = (f"Known values: {json.dumps(known, default=str)}\n" if known else "")
    # A field the system could not compute is stated as unknown rather than omitted: "we do not
    # know how long this has been waiting" is itself useful, and it stops the model reaching for
    # a plausible filler to occupy the sentence.
    unknown = sorted(k for k in slots if k not in known)
    unknown_line = (f"NOT KNOWN — never state or imply these: {', '.join(unknown)}\n"
                    if unknown else "")
    return (
        "You are GeniOS, writing ONE decision card for a salesperson. Use ONLY the facts and "
        "quotes below — never invent a name, number, company or date that is not present.\n\n"
        f"Situation type: {reason_code}\n"
        f"Facts (typed, from the graph):\n{json.dumps({k: (v.get('value') if isinstance(v, dict) else v) for k, v in facts.items()}, default=str, indent=0)}\n"
        f"{known_line}{unknown_line}"
        f"{said}\n"
        f"Guidance: {template.get('render_hint', '')}\n\n"
        "Write plainly and specifically. No filler: if you have nothing concrete to say about "
        "money, timing or open items, say nothing about them rather than reaching for a vague "
        "phrase.\n\n"
        "Return STRICT JSON only:\n"
        f'{{"headline": "HARD LIMIT {HEADLINE_CAP} characters — aim for {HEADLINE_CAP - 12}. '
        'Entity + what is true, concrete not clever",\n'
        f' "situation": "HARD LIMIT {SITUATION_CAP} characters — aim for {SITUATION_CAP - 25}. '
        'The facts that decide this, nothing else. Count the characters before answering",\n'
        f' "artifact": "the {kind} — the actual draft text, ready to use"}}'
    )


def render_copy(*, reason_code: str, template: dict, facts: dict, slots: dict,
                llm=None, cost_sink=None, org_id: str = "",
                identities: tuple[str, ...] = (),
                quotes: list[dict] | None = None,
                subject_ref: str | None = None) -> dict:
    """Try the model; fall back to raw slots on any validator rejection. Returns copy dict with
    headline/situation/artifact + render_mode ('llm'|'raw_slot') + reject_code (V-01/V-02|None)."""
    if llm is None:
        return _fallback(template, slots)

    prompt = _prompt(reason_code, template, facts, slots, quotes)
    res = llm.call(prompt, max_tokens=600)
    if cost_sink is not None and (res.input_tokens or res.output_tokens):
        try:
            # Attributed to the signal this render served — the difference between a monthly
            # bill and a computable cost-per-decision.
            cost_sink(org_id=org_id, model=res.model, purpose="l5_render",
                      input_tokens=res.input_tokens, output_tokens=res.output_tokens,
                      subject_ref=subject_ref)
        except Exception:       # noqa: BLE001 — cost logging never blocks delivery
            pass
    if not res.ok or not isinstance(res.parsed, dict):
        return _fallback(template, slots)

    head = str(res.parsed.get("headline", "")).strip()
    sit = str(res.parsed.get("situation", "")).strip()
    art = str(res.parsed.get("artifact", "")).strip()
    if not head or not sit:
        return _fallback(template, slots)

    # PER-FIELD, not whole-output. Both validators used to discard everything the model produced
    # the moment any one field failed: 39 of 43 live renders were rejected (27 V-02, 12 V-01) and
    # every rejection returned an empty artifact body, so 37 of 41 cards advertised "Draft reply"
    # over nothing. Yield was 4/43 while ~91% of the layer's LLM spend was paid for and thrown
    # away.
    #
    # The three fields fail INDEPENDENTLY, and they mostly fail for independent reasons: the
    # artifact is by far the longest chunk and by far the likeliest to name something ungrounded,
    # so an invented surname in a draft body was routinely destroying a perfectly grounded
    # headline and situation alongside it.
    fb = _fallback(template, slots)
    corpus_text, corpus_nums = _corpus(facts, slots, identities, quotes)
    rejects: dict[str, str] = {}
    notes: dict[str, str] = {}

    # V-01 — length. Deterministically repairable and NOT evidence of a bad render: a headline
    # three characters over the cap says nothing about whether the situation line is sound.
    # Never truncate (Law 3) — drop whole trailing sentences if any complete leading sentence
    # fits, and only swap the field for its template when none does. Ten of the eighteen
    # compiled cards were over by 2–18 characters and every one of them lost a specific,
    # grounded sentence in exchange for the template's bare `{stage}` slot, the word "open".
    for name, cap in (("headline", HEADLINE_CAP), ("situation", SITUATION_CAP)):
        value = head if name == "headline" else sit
        if len(value) <= cap:
            continue
        repaired = _fit(value, cap)
        if repaired is None:
            rejects[name] = f"V-01:len={len(value)}"
            notes[name] = rejects[name]
            value = fb[name]
        else:
            notes[name] = f"V-01-trimmed:{len(value)}->{len(repaired)}"
            value = repaired
        if name == "headline":
            head = value
        else:
            sit = value

    # V-02 — invention. A field that names something ungrounded is unusable; its siblings are
    # unaffected. Runs on the REPAIRED text: a trimmed situation is what would ship, so it is
    # what has to be grounded.
    for name, chunk in (("headline", head), ("situation", sit), ("artifact", art)):
        if name in rejects:
            continue
        ok, why = invention_ok(chunk, corpus_text, corpus_nums)
        if not ok:
            rejects[name] = f"V-02:{why}"
            notes[name] = rejects[name]

    if "headline" in rejects and rejects["headline"].startswith("V-02"):
        head = fb["headline"]
    if "situation" in rejects and rejects["situation"].startswith("V-02"):
        sit = fb["situation"]
    if "artifact" in rejects:
        art = ""

    # A card whose headline AND situation both survived is an LLM render even if the draft body
    # did not — calling that `raw_slot` understated the layer's real yield by conflating "we
    # could not write the copy" with "we could not write the attachment".
    llm_copy = "headline" not in rejects and "situation" not in rejects
    return {"headline": head, "situation": sit,
            "artifact": {"kind": template.get("artifact_kind", "draft"),
                         "body": art, "mode": "llm" if art else "raw_slot"},
            "render_mode": "llm" if llm_copy else "raw_slot",
            # The FIRST rejection is the headline reject_code (the column is single-valued);
            # `reject_detail` carries the whole per-field map so "which field, and why" survives
            # into the card row instead of collapsing to one letter-number pair.
            "reject_code": (sorted(rejects.values())[0].split(":")[0] if rejects else None),
            # `notes`, not `rejects`: a field that was REPAIRED (trailing sentence dropped) has
            # nothing rejected, so it must not set a reject_code — but the repair still has to be
            # readable from the card row, or "the model overshoots the cap" stays invisible.
            "reject_detail": (json.dumps(notes, sort_keys=True) if notes else None)}
