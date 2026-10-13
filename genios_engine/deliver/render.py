from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime

from .slots import SENTINELS, grounded_slots

from genios_engine.context.llm.client import TRUNCATED

# THE INVENTION RULE IS THE ENGINE'S, NOT THE CARD'S (STEP-13, `yc2_w27_s13` M35.C2.L-logic.V0.U08). It
# moved, byte for byte, to `platform/grounding`, so reasoning can hold the expert's claims to the card
# validator's own rule without importing upward. Re-exported here under the names every caller has
# always imported: one rule, one place.
from genios_engine.platform.grounding import (  # noqa: F401
    _GRAMMAR_WORDS, _digit_runs, _expand_dates, _fold, _haystack, _proper_nouns, invention_ok)

# E1 · Copy Renderer + validators (§5.10, §5.18). ONE temp-0 call fills headline, situation and
# the artifact together. Two deterministic gates stand between the model and the user:
#   V-01 length caps  — headline ≤60, situation ≤140 → reject + re-template (never truncate, Law 3)
#   V-02 invention    — every name/number/date in the output must exist in the fact set, else
#                       reject + raw-slot fallback (the hallucination guard, Law 2)
# The fallback is pure slot-interpolation from facts, so a card ALWAYS ships and is always honest.

HEADLINE_CAP = 60
SITUATION_CAP = 140


def situation_cap(template: dict) -> int:
    """The authored briefing owns its prose budget; existing nudges keep 140.

    A measured 201-character situation was reduced to 111, losing its evidence. This
    validates configuration, not output: no model response can enlarge its own allowance.
    """
    value = template.get("situation_cap")
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else SITUATION_CAP


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
        # The author's address is grounded for exactly the reason the quote is: it came off the
        # source event, not from the model. Without it "nikhil@addis.im asked about pricing" —
        # the whole point of the card — is rejected as an invented name whenever the address is
        # not already a fact value.
        if q.get("author"):
            parts.append(str(q["author"]))
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
    # A SLOT NOBODY WRITES IS UNGROUNDED, NOT A CRASH.
    #
    # `tpl.format(**slots)` raised KeyError on any `{name}` the slot vocabulary does not carry,
    # and three SHIPPED situation files named six such slots between them — `{organization}`,
    # `{quote}`, `{sent_on}`, `{longest_wait_days}`, `{age_days}`. The whole card died at render.
    # An authoring mistake taking down the delivery of an otherwise correct decision is the
    # wrong failure: the clause that cannot be substantiated should go, exactly as it does when
    # a slot holds its sentinel, and the rest of the sentence should still reach the reader.
    #
    # THE VALIDATOR IS WHERE THIS IS SUPPOSED TO BE CAUGHT — `_tools/validate.py` now refuses an
    # authored fallback naming a slot the engine cannot fill. This is the second lock, for the
    # gap between an author writing a slot and the engine learning to write it.
    unknown = {name for name in re.findall(r"\{(\w+)\}", tpl) if name not in slots}
    ungrounded = [(name, True) for name in sorted(unknown)]
    ungrounded += [(name, False) for name, value in sorted(slots.items())
                   if SENTINELS.get(name) == value]

    for name, is_unknown in ungrounded:
        placeholder = "{" + name + "}"
        if placeholder not in tpl:
            continue
        parts = [seg for seg in re.split(r"\s+[—·-]\s+", tpl) if placeholder not in seg]
        if parts:
            tpl = " — ".join(parts)
        # else: the placeholder has no clause of its own, so there is nothing to cut without
        # mangling the sentence — "Deliver {action} to {entity} today" would ship as "Deliver
        # to acme.com today". The sentinel stays, because a grammatical placeholder beats a
        # broken sentence and this line never reaches the model in either case.
    # `format_map` OVER A DEFAULTING MAPPING rather than `format(**slots)`. A placeholder with no
    # clause of its own survives the cut above by design (see the comment there), so an unknown
    # one can still reach this line — and a KeyError here would undo the whole point.
    # `_UNWRITTEN` is deliberately a phrase no real value can equal, so it reads as an absence to
    # a person and to the model rather than as a fact.
    return re.sub(r"\s{2,}", " ", tpl.format_map(_Defaulting(slots))).strip(" —·-")


#: What an unwritten slot degrades to when its clause could not be cut. A phrase, not a blank:
#: an empty string leaves "Sent  — 4 of 7 have not replied" and reads as a rendering bug, where
#: this reads as the missing fact it is.
_UNWRITTEN = "not recorded"


class _Defaulting(dict):
    """`str.format_map` support: an unwritten slot resolves rather than raising."""

    def __missing__(self, key: str) -> str:      # noqa: D105 — the docstring above covers it
        return _UNWRITTEN


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


#: ── THE HEADLINE MUST NOT OUTRANK THE CARD ───────────────────────────────────────────────────
#: `card_builder` downgrades a card's `level` when it cannot say what to do — its own comment:
#: *"it just stops claiming the authority to give an order it cannot phrase."* The level is
#: decided in E0. The headline is written here, in E1. **The two stages never meet**, and this
#: module contained no reference to `level` at all, so a card whose authority had been withdrawn
#: still shipped an imperative.
#:
#: MEASURED on the pilot's fifteen live cards: eleven carry `level = review` — the card's own body
#: saying "there is no instruction to give, a human must look" — and three carry `observation`.
#: Exactly ONE is `prescriptive`. Their headlines read
#: *"Deliver fundraising opportunities to sanchiconnect.tech NOW"*,
#: *"Renew Growth plan at $599/month now"*, *"Reply to Sehan Sanjula now"*.
#: The push gate honours the level (`deliver/pipeline.py` checks `is_actionable` before it
#: interrupts) — the SENTENCE does not.
#:
#: THIS IS A SAFETY TRANSFORM, NOT COPYWRITING, and the distinction governs the design. It does
#: not rewrite the sentence, because deterministic verb surgery on
#: *"Send Lalitha A R the product context materials"* produces fragments. It reframes: the trailing
#: urgency word goes, and a prefix states what the card actually is. A slightly stiff honest
#: headline beats a fluent false one, and stiffness is the price of never inventing a clause.
_URGENCY_TAIL = re.compile(r"[\s,;:—-]*\b(now|today|immediately|asap)\s*[.!]*\s*$", re.IGNORECASE)

#: What each non-actionable level says the card IS. Keyed by `abstention.Level` values; a level
#: absent from this map is left alone, which is the fail-open direction on purpose — an unknown
#: level must not silently restyle a headline nobody has reasoned about.
_LEVEL_FRAME: dict[str, str] = {
    "review": "Needs a decision",
    "observation": "Unresolved",
    "wait": "Waiting",
    "suppress": "Closed",
}


def state_not_command(headline: str, level: str | None) -> str:
    """Reframe a headline whose card is not allowed to instruct. Actionable cards pass through.

    Idempotent: a headline already carrying its frame is returned unchanged, so a rebuild cannot
    stack "Unresolved — Unresolved — …".
    """
    from genios_engine.contracts.abstention import is_actionable

    head = (headline or "").strip()
    if not head or is_actionable(level):
        return head
    frame = _LEVEL_FRAME.get(str(level or "").strip().lower())
    if frame is None:
        return head
    # ANY existing frame is stripped, not just this level's. A card whose level moves between
    # builds — `observation` on Monday, `review` on Tuesday once the owner went absent — otherwise
    # accumulates them: "Needs a decision — Unresolved — Reply to Sehan Sanjula". Guarding only
    # against the matching prefix makes the transform idempotent for a fixed level and stacking
    # for a moving one, which is the case that actually happens.
    for existing in _LEVEL_FRAME.values():
        prefix_form = existing.lower() + " — "
        if head.lower().startswith(prefix_form):
            head = head[len(prefix_form):].strip()
            break
    if head.lower().startswith(frame.lower() + " —"):
        return head
    body = _URGENCY_TAIL.sub("", head).strip()
    # THE BUDGET IS SPENT ON THE BODY, NEVER THE FRAME. Capping the joined string lets `_cap`
    # treat the em dash as a clause boundary and cut everything after it — which returned the bare
    # words "Needs a decision" for the pilot's top card, a headline strictly worse than the
    # imperative it replaced. The frame is fixed-width and known, so the body is cut to what
    # remains and the two are joined afterwards.
    prefix = f"{frame} — "
    room = HEADLINE_CAP - len(prefix)
    if room < 12:
        # No headline budget can carry both. Keep the body, which at least says what this is
        # about; the level still travels on the card and the surface can render it.
        return _cap(body, HEADLINE_CAP)
    return prefix + _cap(body, room)


def _verified_quotes(quotes) -> tuple[str, ...]:
    return tuple(sorted({q["quote"] for q in quotes or ()
        if q.get("source_verified") is True and q.get("event_id")
        and isinstance(q.get("quote"), str) and q["quote"].strip()}, key=lambda q: (-len(q), q)))


def _mask_quotes(value: str, quotes):
    """Protect verified bytes (including newlines) from sentence/whitespace fitting.

    Quotes previously spent the 140-character prose budget and were then removed first.
    Source verification is supplied by the loader, never inferred from quotation marks.
    """
    masked, tokens = value, {}
    for quote in _verified_quotes(quotes):
        for block in (f'"{quote}"', f'“{quote}”', quote):
            if block not in masked:
                continue
            token = chr(0xE000 + len(tokens))
            while token in value or token in tokens:
                token = chr(ord(token) + 1)
            tokens[token] = (block, len(block) - len(quote))
            masked = masked.replace(block, token)
    return masked, tokens


def _restore_quotes(value, tokens):
    for token, (block, _) in tokens.items():
        value = value.replace(token, block)
    return value


def _prose_length(value, quotes):
    masked, tokens = _mask_quotes(value, quotes)
    return len(masked) + sum(masked.count(token) * (cost - 1)
                             for token, (_, cost) in tokens.items())


def _fit_situation(value, cap, quotes):
    if _prose_length(value, quotes) <= cap:
        return value
    masked, tokens = _mask_quotes(value, quotes)
    cost = sum(masked.count(token) * (weight - 1) for token, (_, weight) in tokens.items())
    fitted = _fit(masked, max(0, cap - cost))
    # Removing an evidence block is not a prose repair. Use the authored fallback instead.
    if fitted is None or any(fitted.count(token) != masked.count(token) for token in tokens):
        return None
    return _restore_quotes(fitted, tokens)


def _cap_situation(value, cap, quotes):
    fitted = _fit_situation(value, cap, quotes)
    if fitted is not None:
        return fitted
    masked, tokens = _mask_quotes(value, quotes)
    if not tokens:
        return _cap(value, cap)
    # An oversized authored fallback still keeps its evidence blocks. Reserve their
    # delimiters and joins, then shorten only prose; no source bytes are rewritten.
    blocks = [tokens[ch] for ch in masked if ch in tokens]
    prose = "".join(ch for ch in masked if ch not in tokens).strip()
    room = max(0, cap - sum(cost for _, cost in blocks) - len(blocks))
    leading = _cap(prose, room) if room else ""
    return " ".join(part for part in (leading, *(block for block, _ in blocks)) if part)


def _fallback(template: dict, slots: dict, quotes=None) -> dict:
    fb = template.get("fallback", {})
    head = _cap(_interpolate(fb.get("headline", "{entity}"), slots), HEADLINE_CAP)
    # Interpolation normalises prose whitespace. Protect source slots before that step,
    # otherwise a verified newline/indent is lost before quote-aware fitting even runs.
    protected, restorations = dict(slots), {}
    for key, val in slots.items():
        if isinstance(val, str) and val in _verified_quotes(quotes):
            token = f"\ue100{key}\ue101"
            protected[key] = token
            restorations[token] = (val, 0)
    sentence = _restore_quotes(_interpolate(fb.get("situation", "{stage}"), protected), restorations)
    sit = _cap_situation(sentence, situation_cap(template), quotes)
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


def _speaker(q: dict) -> str:
    """Who said this line — the counterparty, the account holder, or nobody we can name.

    Tri-state because `from_counterparty` is: None means the event that minted the observation is
    no longer there to name an author, and "unattributed" is the only truthful label for it. The
    model is told plainly rather than left to guess, because a guess here reads as a fact.
    """
    stance = q.get("from_counterparty")
    if stance is False:
        return "the account holder wrote"
    if stance is True:
        return f'{q.get("author") or "the other side"} wrote'
    return "source unattributed"


def _prompt(reason_code: str, template: dict, facts: dict, slots: dict,
            quotes: list[dict] | None = None) -> str:
    kind = template.get("artifact_kind", "draft")
    prose_cap = situation_cap(template)
    # WHAT WAS ACTUALLY SAID. The prompt used to be five typed key/value pairs and a rule id, and
    # the model was asked to write a thread-specific reply from that — so the copy had no content
    # because there was no content in the prompt. These quotes come from graph_source_refs, one
    # join from where the renderer was already looking.
    said = ""
    if quotes:
        # ATTRIBUTED, because an unlabelled list of sentences is a misattribution waiting to
        # happen. 161 of the 526 observations on the design partner's org were extracted from the
        # FOUNDER'S OWN outgoing mail, and handed to the model in one undifferentiated block they
        # read exactly like the counterparty's — "they asked about pricing" written off a sentence
        # we sent. Naming the speaker is also half of what the card owes the reader: who wrote,
        # what they asked, how long ago, whose turn it is.
        lines = "\n".join(
            f'- [{q.get("kind")}] {_speaker(q)}: "{q.get("quote")}"' for q in quotes[:8])
        said = (f"\nWhat was actually said (verbatim, newest first) — quote or paraphrase THESE, "
                f"they are what makes the card specific. Attribute each line to the speaker named "
                f"beside it and NEVER present something the account holder wrote as something the "
                f"other side asked:\n{lines}\n")
    # GROUNDED SLOTS ONLY. `compute_slots` fills an absent fact with a sentinel — days
    # "several", stage "open", money "no value set", concerns "several open items" — so the
    # deterministic fallback template still reads as a sentence. Handing those to the model
    # labelled "Key slots" presents them as facts, and the model correctly writes down what it
    # was told: all eighteen compiled cards on the design partner's org came back saying
    # "several open items blocking commitment ... in open stage for several days ... No value
    # set" about accounts with no deal in play. A slot we could not compute is not a fact about
    # the account, and the model must never see it.
    # MANAGER MODE, AND THE ONE LINE THAT DECIDED EVERY HEADLINE IN THE PRODUCT.
    #
    # This asked for "Entity + what is true". The model complied, and 69 of the design partner's
    # 78 cards are LLM-rendered — so the whole queue read as a clock: "willow@myzyner.com: 34
    # days, no reply", "hv@errorcore.dev: 43 days". Each one states a measurement and leaves the
    # move buried in the artifact, which is the last field a reader reaches.
    #
    # `packs/general_v1.py` has carried the right rule since it was written — "headline is a
    # direct order (verb first, name who), never a passive fact" — and it is why the only cards in
    # the live queue that read like advice ("Reply to Sehan Sanjula now") are the ones that pack
    # authored. The compiled corpus never inherited it because that rule lived in a pack template
    # rather than here.
    #
    # A CARD THAT DECLINES TO ADVISE MUST NOT BE ORDERED TO GIVE AN ORDER. Where the situation
    # author declared `states_absence`, the finding IS the gap and an imperative would be the
    # model asserting a move the card has no basis for — so that case keeps the descriptive rule.
    # Read off the template rather than passed in, so it cannot drift from what the author wrote.
    absence = bool(((template or {}).get("fallback") or {}).get("states_absence"))
    headline_rule = (
        "what is missing and who must look — this card declines to instruct, so do NOT write a "
        "command" if absence else
        "A DIRECT ORDER, AND IT MUST NAME THE THING. Verb + who + WHAT. "
        "'Send Titan Capital your traction metrics', 'Answer Divyanshu's pricing question', "
        "'Get Leslie's calendar availability'. "
        "A bare 'Reply to X today' is REJECTED — it names who and not what, which the reader's "
        "own inbox already tells them. The specific is in the quotes and the draft below; if you "
        "can write the draft you can name the thing in the headline. "
        "Only when nothing on the record says what they want may you fall back to the bare "
        "instruction. Never a status line, never a day count on its own"
    )
    known = grounded_slots(slots)
    # SORTED, here and in the facts below: dict order follows the order rows came back from the
    # database, so the same situation built a different prompt from one run to the next
    # (yc2_w27/M19.C3.L-logic.V1.U03). What the model is told is unchanged; the order is fixed.
    known_line = (f"Known values: {json.dumps(known, default=str, sort_keys=True)}\n"
                  if known else "")
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
        f"Facts (typed, from the graph):\n{json.dumps({k: (v.get('value') if isinstance(v, dict) else v) for k, v in facts.items()}, default=str, indent=0, sort_keys=True)}\n"
        f"{known_line}{unknown_line}"
        f"{said}\n"
        f"Guidance: {template.get('render_hint', '')}\n\n"
        "Write plainly and specifically. No filler: if you have nothing concrete to say about "
        "money, timing or open items, say nothing about them rather than reaching for a vague "
        "phrase.\n\n"
        "Return STRICT JSON only:\n"
        f'{{"headline": "HARD LIMIT {HEADLINE_CAP} characters — aim for {HEADLINE_CAP - 12}. '
        + headline_rule + '",\n'
        f' "situation": "HARD LIMIT {prose_cap} characters — aim for {max(1, prose_cap - 25)}. '
        'The facts that decide this, nothing else. Source-verified verbatim quotes do not count '
        'against this prose limit; preserve their bytes. Count the prose before answering",\n'
        f' "artifact": "the {kind} — the actual draft text, ready to use"}}'
    )


def review_copy(copy: dict, template: dict) -> dict:
    """A covered file's card copy, the expert's review's own: the fallback the decision carried (the
    move as the headline, the expert's reading as the situation — `reason/expert/decide._render`),
    and the review's draft as the artifact. STEP-12 M33.C1.L-interface.V1.U08: no narrator is asked;
    the words were validated with the review (`contracts/expert_review.validate`)."""
    body = str(template.get("draft") or "").strip()
    artifact = {**(copy.get("artifact") or {}), "body": body,
                "mode": "review" if body else (copy.get("artifact") or {}).get("mode", "raw_slot")}
    return {**copy, "artifact": artifact, "render_mode": "review"}


def render_copy(*, reason_code: str, template: dict, facts: dict, slots: dict,
                llm=None, cost_sink=None, org_id: str = "",
                identities: tuple[str, ...] = (),
                quotes: list[dict] | None = None,
                subject_ref: str | None = None) -> dict:
    """Try the model; fall back to raw slots on any validator rejection. Returns copy dict with
    headline/situation/artifact + render_mode ('llm'|'raw_slot') + reject_code (V-01/V-02|None)."""
    if llm is None:
        return _fallback(template, slots, quotes)

    prompt = _prompt(reason_code, template, facts, slots, quotes)
    res = llm.call(prompt, max_tokens=600)
    if cost_sink is not None and (res.input_tokens or res.output_tokens):
        # ⛔ HOW THE CALL ENDED (`yc2_w27_s18` M50.C3.L-logic.V1.U15, s5t-F6): the sink was handed the
        # tokens alone and `record_cost` defaults to success, so every `l5_render` call was one — a
        # 400, an unparseable answer and a cut one included. A cut answer is a failure, parsed or not.
        cut = bool(getattr(res, "truncated", False))
        try:
            # Attributed to the signal this render served — the difference between a monthly
            # bill and a computable cost-per-decision.
            cost_sink(org_id=org_id, model=res.model, purpose="l5_render",
                      input_tokens=res.input_tokens, output_tokens=res.output_tokens,
                      success=bool(getattr(res, "ok", False)) and not cut,
                      error=(getattr(res, "error", None)
                             or (f"{TRUNCATED} (max_tokens=600)" if cut else None)),
                      subject_ref=subject_ref)
        except Exception:       # noqa: BLE001 — cost logging never blocks delivery
            pass
    if not res.ok or not isinstance(res.parsed, dict):
        return _fallback(template, slots, quotes)

    head = str(res.parsed.get("headline", "")).strip()
    sit = str(res.parsed.get("situation", "")).strip()
    art = str(res.parsed.get("artifact", "")).strip()
    if not head or not sit:
        return _fallback(template, slots, quotes)

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
    fb = _fallback(template, slots, quotes)
    corpus_text, corpus_nums = _corpus(facts, slots, identities, quotes)
    rejects: dict[str, str] = {}
    notes: dict[str, str] = {}

    # V-01 — length. Deterministically repairable and NOT evidence of a bad render: a headline
    # three characters over the cap says nothing about whether the situation line is sound.
    # Never truncate (Law 3) — drop whole trailing sentences if any complete leading sentence
    # fits, and only swap the field for its template when none does. Ten of the eighteen
    # compiled cards were over by 2–18 characters and every one of them lost a specific,
    # grounded sentence in exchange for the template's bare `{stage}` slot, the word "open".
    for name, cap in (("headline", HEADLINE_CAP), ("situation", situation_cap(template))):
        value = head if name == "headline" else sit
        if (len(value) if name == "headline" else _prose_length(value, quotes)) <= cap:
            continue
        repaired = _fit(value, cap) if name == "headline" else _fit_situation(value, cap, quotes)
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
    # ⛔ LOCAL, AND THAT IS STRUCTURAL, NOT STYLE. `claim_validator` imports `invention_ok` from
    # THIS module, so a module-level import here is a cycle. The validator depends on the
    # renderer because it must use the renderer's own folding rules; the renderer depends on the
    # validator only at call time.
    from .claim_validator import claims_ok

    for name, chunk in (("headline", head), ("situation", sit), ("artifact", art)):
        if name in rejects:
            continue
        # ⛔ `claims_ok`, WHICH CALLS `invention_ok` FIRST AND REPORTS ITS REFUSALS UNCHANGED.
        # The widening is per SENTENCE rather than per field: the same corpus, the same folding
        # helpers, the same `V-02:number:12` vocabulary, and strictly more refusals — never fewer.
        # `tests/deliver/test_a_fact_and_a_guess_do_not_look_alike.py` holds the old function's
        # verdict and this one side by side on the cases it refuses.
        #
        # It is swapped in HERE, at the only place the old function was called, because a widened
        # validator nothing calls is the "built, tested, green, and called by nothing" defect this
        # programme has now found eight times — once in its own work, one step ago.
        ok, why, _refusals = claims_ok(chunk, corpus_text, corpus_nums,
                                       quotes_something=bool(quotes))
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
