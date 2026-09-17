"""Router check 5 — what a RULE can answer, so the model is not asked (plan §10.1, Fig 10.1).

The router was built with checks 1–4 (never-read, diff, 24 h verdict, dwell) and then handed
everything that survived to the model. Check 5 is the missing one: *is this something a rule can
already answer?* On a chat screen most of it is.

A message line carries its own sender and its own words, and the device has already resolved the
dates in it against the manager's clock. So when a real person writes a real request with a real
date, nothing has to be inferred:

    Priya Shah: kal tak revised quote bhej dena
    → ask · who "Priya Shah" · due 2026-09-18 18:00 · quote the line itself

THE QUOTE IS THE ITEM. No paraphrase is needed, so no model is needed. That is the whole idea.

PRECISION OVER RECALL. A rule fires only when it is plainly right — a sender, and an unmistakable
request or commitment marker in that person's own words. Everything softer ("jo pending hai wo
bhej dena", an implied deadline, a hint) is left to the model, which is what the model is for.
A wrong item costs the manager's trust; a missed one costs one model call.

The markers are English and Hinglish because the manager's screen is. They are the same families
the device's `matcher/intents.rs` uses, kept here per LINE rather than per screen: a screen may
hold one person's ask and the manager's own promise, and those are two items with two owners.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

#: "Priya Shah: kal tak bhej dena" — the shape the device sends (`{who}: {text}`). Bounded name
#: so a sentence containing a colon is not read as a sender.
_LINE = re.compile(r"^(?P<who>[^:]{1,60}?):\s+(?P<text>\S.*)$")
#: What the device calls the manager's own lines.
_SELF = frozenset({"you", "me", "self"})
#: An item's quote never runs longer than this (followups keeps ≤ 12 words).
QUOTE_WORDS = 12
MAX_ITEMS = 3
#: A day named without a time is due at the end of that working day (followups.DAY_ONLY_HOUR).
DAY_ONLY_HOUR = 18
#: A rule item is structural, not a guess — but it is not certain either, and the field exists so
#: a floor can one day be set against measurement rather than feeling.
RULE_CONFIDENCE = 0.9

#: SOMEONE IS ASKING THE MANAGER FOR SOMETHING. Imperatives and requests, in both languages.
_ASK = (
    r"\bbhej\s*d(?:o|ena|ijiye)\b", r"\bbhejna\b", r"\bshare\s+kar\s*d(?:o|ena)\b",
    r"\bkar\s*d(?:o|ena|ijiye)\b", r"\bde\s*d(?:o|ena|ijiye)\b", r"\bchahiye\b",
    r"\bkab\s+tak\b", r"\bkya\s+hua\b", r"\bupdate\s+d(?:o|ena)\b",
    r"\bplease\s+(?:send|share|forward|confirm|review|sign|approve|check)\b",
    # "send it please" — the same request with the courtesy at the other end.
    r"\b(?:send|share|forward|confirm|review|sign|approve)\b[^.?!]{0,30}\bplease\b",
    r"\b(?:can|could|would)\s+you\s+(?:please\s+)?(?:send|share|forward|confirm|review|sign|approve|check)\b",
    r"\bsend\s+(?:me|us|over|across)\b", r"\bwaiting\s+(?:on|for)\b",
    r"\bneed\s+(?:the|it|this|that|your)\b", r"\bfollowing\s+up\b", r"\bany\s+update\b",
)
#: THE SPEAKER IS COMMITTING TO SOMETHING. First person, future.
_COMMIT = (
    r"\b(?:bhej|kar|de|bhijwa)\s*(?:deta|deti|dunga|dungi|doonga|doongi|denge)\b",
    r"\b\w+(?:unga|ungi|oonga|oongi)\b",
    r"\bkarta\s+hoon\b", r"\bkarti\s+hoon\b", r"\bbhejta\s+hoon\b", r"\bbhejti\s+hoon\b",
    r"\bi(?:'|’)?ll\b", r"\bi\s+will\b", r"\bwe(?:'|’)?ll\b", r"\bwe\s+will\b",
    r"\blet\s+me\s+(?:send|share|check|confirm|get)\b", r"\bsending\s+(?:it|this|the|you)\b",
    r"\bwill\s+(?:send|share|revert|confirm|get\s+back)\b",
)
#: Lines that look like a request but are not one: a button, a menu, a status, a notice.
_FURNITURE = (
    r"^\s*(?:join|open|reply|forward|delete|archive|sign\s+in|log\s+in|see|show|view|download)\b\s*\S{0,12}\s*$",
    r"^\s*\d+\s+(?:unread|new)\b", r"^\s*(?:typing|online|last\s+seen|delivered|read)\b",
)

_ASK_RE = re.compile("|".join(_ASK), re.I)
_COMMIT_RE = re.compile("|".join(_COMMIT), re.I)
_FURNITURE_RE = re.compile("|".join(_FURNITURE), re.I)


class Line:
    """One message on screen: who wrote it, what they wrote, and whether it is the manager's."""

    __slots__ = ("who", "text", "outgoing")

    def __init__(self, who: str | None, text: str, outgoing: bool) -> None:
        self.who, self.text, self.outgoing = who, text, outgoing

    def __repr__(self) -> str:      # pragma: no cover - debugging only
        return f"Line({'You' if self.outgoing else self.who!r}, {self.text!r})"


def _is_me(who: str, me: list[str] | None) -> bool:
    """Is this line the manager's own? The device writes "You:" when its reader knows the
    direction — but the GENERIC reader often does not, and on a mailbox that would turn the
    manager's own sent mail into somebody asking them for something. Their own name or address
    on the line settles it."""
    from genios_engine.reason.moments.screen_insight import is_me
    return who.casefold() in _SELF or is_me(who, me)


def lines(visible, me: list[str] | None = None) -> list[Line]:
    """`visible_messages` → the lines a PERSON wrote, in order.

    Two shapes arrive: `{sender, text}` from a dedicated reader, and `"Priya Shah: …"` strings
    from the generic one — which is what the device actually sends today. Handling only the dict
    is why `said_lines` came back empty for every real request, and why the structural
    "was this said by someone?" reject never fired outside tests.
    """
    out: list[Line] = []
    for item in visible or []:
        if isinstance(item, dict):
            who = str(item.get("sender") or "").strip()
            text = " ".join(str(item.get("text") or "").split())
            if not who or not text:
                continue
            mine = _is_me(who, me)
            out.append(Line(None if mine else who, text, mine))
            continue
        m = _LINE.match(" ".join(str(item or "").split()))
        if m is None:
            continue
        who, text = m.group("who").strip(), m.group("text").strip()
        if not who or not text:
            continue
        mine = _is_me(who, me)
        out.append(Line(None if mine else who, text, mine))
    return out


def said(visible, me: list[str] | None = None) -> list[str]:
    """The normalised text of every line a person wrote — the grounding check's "was this said?"."""
    return [" ".join(re.sub(r"[^\w\s]", " ", ln.text).split()).casefold()
            for ln in lines(visible, me)]


def _quote(text: str) -> str:
    words = text.split()
    return " ".join(words[:QUOTE_WORDS])


def _due_in(text: str, dates, tz_name: str | None) -> str | None:
    """The device already resolved this screen's date phrases against the manager's own clock.
    If one of them is in THIS line, that is the item's due — nothing is computed here."""
    from genios_engine.reason.moments.screen_insight import _phrase
    hay = text.casefold()
    best = None
    for d in dates or []:
        phrase, day, clock = _phrase(d)
        p = phrase.casefold()
        if p and day and p in hay and (best is None or len(p) > len(best[0])):
            best = (p, day, clock)
    if best is None:
        return None
    _, day, clock = best
    return f"{day}T{clock or f'{DAY_ONLY_HOUR:02d}:00'}"


def _kind(ln: Line) -> str | None:
    """What this one line is, or None when no rule is sure enough to say."""
    if _FURNITURE_RE.search(ln.text):
        return None
    commit = bool(_COMMIT_RE.search(ln.text))
    if ln.outgoing:
        # The manager's own line. Only a promise they made is an item; their questions to the
        # other side are not something GeniOS owes them a reminder for.
        return "my_promise" if commit else None
    if _ASK_RE.search(ln.text):
        return "ask"
    return "their_promise" if commit else None


def extract(visible, *, dates=None, tz_name: str | None = None, me: list[str] | None = None,
            now: datetime | None = None) -> list[dict]:
    """Items this screen states outright, newest last — or [] when it needs reading rather than
    matching. Same shape `screen_insight.judge` produces, so the caller cannot tell them apart.

    One item per person per kind: a chat where someone asks three times is one ask, and the
    newest wording is the one worth quoting back.
    """
    found: dict[tuple[str, str], dict] = {}
    for ln in lines(visible, me):
        kind = _kind(ln)
        if kind is None:
            continue
        quote = _quote(ln.text)
        if len(quote.split()) < 2:
            continue
        who = None if kind == "my_promise" else ln.who
        found[(kind, (who or "").casefold())] = {
            "kind": kind,
            "text": quote,
            "who": who,
            "due": _due_in(ln.text, dates, tz_name),
            "quote": quote,
            "confidence": RULE_CONFIDENCE,
            "source": "rule",
        }
    items = list(found.values())
    # An ask the manager answered later on the same screen is already handled; the structural
    # "answered" check owns that, and raising it here would undo it.
    return items[:MAX_ITEMS]


def answered_after(visible, quote: str, me: list[str] | None = None) -> bool:
    """Did the manager write anything BELOW the line this quote came from? Then the ask on that
    line is already answered on this very screen, and nothing should be raised for it."""
    q = " ".join(re.sub(r"[^\w\s]", " ", quote or "").split()).casefold()
    if not q:
        return False
    seen = False
    for ln in lines(visible, me):
        norm = " ".join(re.sub(r"[^\w\s]", " ", ln.text).split()).casefold()
        if not seen and q in norm:
            seen = True
            continue
        if seen and ln.outgoing:
            return True
    return False


def propose_adds(items: list[dict], *, open_items: list[dict] | None,
                 meetings: list[dict] | None, thread_key: str | None,
                 tz_name: str | None, now: datetime) -> tuple[str, str] | None:
    """The one reason a popup may exist here, and the line that says it — BOTH computed, neither
    written by a model. Five reasons, checked in the order that a manager would care about, and
    every one of them is arithmetic on what GeniOS already holds.

    `screen_insight.verify_adds` then checks the proposal exactly as it checks the model's, so
    there is one gate and not two: this path cannot slip a popup past a rule the other obeys.
    """
    from genios_engine.reason.moments import screen_insight as SI

    def who_of(it) -> str:
        return " ".join(re.sub(r"[^\w\s]", " ", str(it.get("who") or "")).split()).casefold()

    whos = {who_of(i) for i in items if who_of(i)}
    prior = list(open_items or [])
    name = next((i["who"] for i in items if i.get("who")), "They")

    candidates: list[tuple[str, str]] = []
    if any(p.get("kind") == "ask" and who_of(p) in whos for p in prior):
        candidates.append(("repeat_ask", f"{name} asked for this before — it is still open"))
    if any(p.get("kind") == "my_promise" and who_of(p) in whos for p in prior):
        candidates.append(("promise_to_them", f"You already owe {name} something"))
    if any(who_of(p) in whos and p.get("thread_key") != thread_key for p in prior):
        candidates.append(("same_ask_elsewhere", f"The same thing is open with {name} elsewhere"))
    clash = _clashing_meeting(items, meetings, tz_name)
    if clash:
        candidates.append(("conflict", f"That time collides with {clash}"))
    soon = _hours_to_due(items, tz_name, now)
    if soon is not None:
        when = "now" if soon <= 0 else (f"in {soon} h" if soon > 1 else "within the hour")
        candidates.append(("urgent_risk", f"Due {when}"))

    for adds, note in candidates:
        if SI.verify_adds(adds, items=items, open_items=prior, meetings=meetings,
                          thread_key=thread_key, tz_name=tz_name, now=now):
            return adds, note[:140]
    return None


def _clashing_meeting(items, meetings, tz_name) -> str | None:
    from genios_engine.reason.moments.common import parse_ts
    from genios_engine.reason.moments.screen_insight import _local_due
    for it in items:
        due = _local_due(it, tz_name)
        if due is None:
            continue
        for m in meetings or []:
            start = parse_ts(m.get("start_at"))
            if start is None:
                continue
            end = parse_ts(m.get("end_at")) or (start + timedelta(minutes=30))
            if start <= due < end:
                return str(m.get("title") or "a meeting")[:60]
    return None


def _hours_to_due(items, tz_name, now: datetime) -> int | None:
    from genios_engine.reason.moments.screen_insight import _local_due
    best = None
    for it in items:
        due = _local_due(it, tz_name)
        if due is not None and due <= now + timedelta(hours=24):
            h = int((due - now).total_seconds() // 3600)
            best = h if best is None else min(best, h)
    return best


#: Router check 6. A screen with none of these is not ambiguous — it is empty. "got it, thanks",
#: "ok", a status line, a forwarded article: there is no request, no promise, no clock and no
#: number in it, so the model would read it and answer nothing. That answer is free here.
_WORTH_ASKING = re.compile(
    r"[?？]"                                        # somebody asked something
    r"|\b(?:need|want|send|share|sign|approve|confirm|review|pay|invoice|quote|contract|deadline"
    r"|urgent|asap|pending|chahiye|bhej|karo|kar\s*d|dena|jaldi|kab|kyu|kaise)\b"
    r"|[₹$€£]\s?\d|\b\d+\s?(?:%|k|lakh|cr|crore|million)\b"   # money or a quantity
    r"|\b(?:today|tomorrow|tonight|monday|tuesday|wednesday|thursday|friday|saturday|sunday"
    r"|eod|cob|kal|aaj|parso|subah|shaam)\b",       # a clock
    re.I)


def worth_asking(visible, dates=None) -> bool:
    """ROUTER CHECK 6: is there anything here a model could even find?

    Rules could not read this screen — but that does not make it ambiguous. Most screens that
    reach here carry no request, no commitment, no date and no amount, and the model returns
    nothing for them. Asking anyway is the purest waste in the lane, so it is not asked.

    Deliberately generous: one question mark, one date the device resolved, one amount, one
    request word in either language is enough. The point is to refuse the plainly empty, not to
    judge the borderline — that judgement is exactly what the model is for.
    """
    if dates:
        return True
    # Every line, not only the ones with a sender: a PAGE has no senders at all, and a page is
    # exactly where an invoice amount or a due date sits without anybody saying it.
    return any(_WORTH_ASKING.search(str(item.get("text") or "") if isinstance(item, dict)
                                    else str(item or ""))
               for item in visible or [])


def enough(items: list[dict], *, verdict_known: bool) -> bool:
    """May the model be skipped entirely for this screen?

    Only when BOTH hold: a rule read something real off it, and somebody has already decided
    this thread is work. Work-vs-personal is the one judgement no rule here makes — it is about
    a life, not a sentence — so the first sighting of a thread always costs one call, and every
    sighting after it for the next 24 h can be free.
    """
    return bool(items) and verdict_known


__all__ = ["Line", "MAX_ITEMS", "QUOTE_WORDS", "RULE_CONFIDENCE", "answered_after", "enough",
           "extract", "lines", "propose_adds", "said", "worth_asking"]
