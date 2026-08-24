from __future__ import annotations

import json
import re
from datetime import datetime

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
    for w in s.split():
        core = re.sub(r"[^A-Za-z0-9]", "", w)
        if len(core) < 2 or not core.isalpha():
            continue
        if core.lower() in _GRAMMAR_WORDS:
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
    for f in facts.values():
        v = f.get("value") if isinstance(f, dict) else f
        s = json.dumps(v, default=str) if not isinstance(v, str) else v
        parts.append(s)
        parts.extend(_expand_dates(s))
    parts.extend(str(v) for v in slots.values())
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
_UNKNOWN_DAYS = "several"


def _drop_unknown_duration(tpl: str, slots: dict) -> str:
    """Interpolate a fallback template, removing any duration clause we cannot substantiate.

    Saying nothing about elapsed time is honest; inventing a number is not; and printing a word
    where a number belongs is neither. When the clock fact is missing, the clause that would have
    carried it is cut and the rest of the sentence still renders.
    """
    if slots.get("days") == _UNKNOWN_DAYS and "{days}" in tpl:
        # Drop the clause containing the placeholder, keeping the surrounding sentence.
        parts = [seg for seg in re.split(r"\s+[—·-]\s+", tpl) if "{days}" not in seg]
        tpl = " — ".join(parts) if parts else tpl.replace("{days}d", "").replace("{days}", "")
    return tpl.format(**slots).strip(" —·-")


def _fallback(template: dict, slots: dict) -> dict:
    fb = template.get("fallback", {})
    head = _drop_unknown_duration(fb.get("headline", "{entity}"), slots)[:HEADLINE_CAP]
    sit = _drop_unknown_duration(fb.get("situation", "{stage}"), slots)[:SITUATION_CAP]
    return {"headline": head, "situation": sit,
            "artifact": {"kind": template.get("artifact_kind", "draft"),
                         "body": "", "mode": "raw_slot"},
            "render_mode": "raw_slot", "reject_code": None}


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
    return (
        "You are GeniOS, writing ONE decision card for a salesperson. Use ONLY the facts and "
        "quotes below — never invent a name, number, company or date that is not present.\n\n"
        f"Situation type: {reason_code}\n"
        f"Facts (typed, from the graph):\n{json.dumps({k: (v.get('value') if isinstance(v, dict) else v) for k, v in facts.items()}, default=str, indent=0)}\n"
        f"Key slots: {json.dumps(slots, default=str)}\n"
        f"{said}\n"
        f"Guidance: {template.get('render_hint', '')}\n\n"
        "Return STRICT JSON only:\n"
        '{"headline": "<= 60 chars, entity + problem, concrete not clever",\n'
        ' "situation": "<= 140 chars, the two facts that matter + the money",\n'
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

    # V-01 — length. Deterministically repairable and NOT evidence of a bad render: a headline
    # three characters over the cap says nothing about whether the situation line is sound.
    # Never truncate (Law 3) — swap that one field for its template.
    if len(head) > HEADLINE_CAP:
        rejects["headline"] = f"V-01:len={len(head)}"
        head = fb["headline"]
    if len(sit) > SITUATION_CAP:
        rejects["situation"] = f"V-01:len={len(sit)}"
        sit = fb["situation"]

    # V-02 — invention. A field that names something ungrounded is unusable; its siblings are
    # unaffected.
    for name, chunk in (("headline", head), ("situation", sit), ("artifact", art)):
        if name in rejects:
            continue
        ok, why = invention_ok(chunk, corpus_text, corpus_nums)
        if not ok:
            rejects[name] = f"V-02:{why}"

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
            "reject_detail": (json.dumps(rejects, sort_keys=True) if rejects else None)}
