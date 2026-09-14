"""Draft a reply for a screen follow-up — P10 (`POST /v1/followups/{id}/draft`).

One Haiku call writes a short reply (≤ 60 words) the manager could send to the follow-up's `who`,
in the same language and style as the item's grounding quote (Hinglish stays Hinglish), from the
item's kind, note, quote and due. The draft is returned, never stored and never sent anywhere; the
call's cost is recorded (purpose `followup_draft`); never credit-charged.
"""
from __future__ import annotations

from genios_engine.reason.moments import seat_profile as SP

PURPOSE = "followup_draft"
TIMEOUT_S = 6.0
MAX_WORDS = 60
MAX_OUTPUT_TOKENS = 220

_GOAL = {
    "ask": "they asked the manager for something: answer or commit to it",
    "my_promise": "the manager promised them something: give a short update on it",
    "their_promise": "they promised the manager something: a polite check-in about it",
    "deadline": "a date matters here: confirm it and what happens by then",
    "risk": "something could go wrong: address their concern calmly",
    "next_step": "propose the next step",
}

_PROMPT = """Write a short reply a busy manager could send to {who}.
What it is about: {note}{due}
Situation: {goal}.
Their words on screen (match THIS language and style exactly — if it is Hinglish, Hindi in
Latin letters mixed with English, reply in Hinglish; keep the same formality):
"{quote}"

At most {max_words} words. Do not invent facts, numbers, names or dates beyond what is above;
commit only to what the note says. Return only the reply text — no quotes, no subject line, no
explanation."""


def build_prompt(item: dict, *, due_local: str | None = None) -> str:
    return _PROMPT.format(
        who=item.get("who") or "the other person", note=item.get("text") or "",
        due=f" (due {due_local})" if due_local else "",
        goal=_GOAL.get(item.get("kind") or "", "reply helpfully"),
        quote=" ".join(str(item.get("quote") or item.get("text") or "").split()),
        max_words=MAX_WORDS)


def clean(raw: str | None) -> str | None:
    """Strip wrapping quotes; at most MAX_WORDS words."""
    s = (raw or "").strip().strip("\"“”").strip()
    words = s.split()
    if not words:
        return None
    if len(words) > MAX_WORDS:
        return " ".join(words[:MAX_WORDS]).rstrip(",;:") + "…"
    return s


def draft(engine, *, org_id: str, item: dict, due_local: str | None = None) -> str | None:
    """The reply text, or None (no model, failure, time ran out)."""
    return clean(SP.t1_text(engine, org_id=org_id, prompt=build_prompt(item, due_local=due_local),
                            max_tokens=MAX_OUTPUT_TOKENS, timeout_s=TIMEOUT_S, purpose=PURPOSE,
                            temperature=0.3))


__all__ = ["PURPOSE", "build_prompt", "clean", "draft"]
