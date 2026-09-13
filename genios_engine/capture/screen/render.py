"""Screen session → RawObjects (P2 contract §3.1, docs/plans/SCREEN_INTEL_P2_BUILD.md). PURE.

One held delta (one decrypted `ScreenSession` document at one watermark) becomes up to two
objects for a dedicated reader — what the seat SENT (`#out`) and what they RECEIVED (`#in`) — or
one `#doc` object for the generic reader. Splitting by direction is what lets Layer 1 name a
direction at all: a screen message has no From header, and a sender with no address was refused
extraction as `direction_unknown`.

Every object is bounded (`#pN` parts above 40 messages or the character budget), because the
extractor refuses over-limit content rather than truncating it. Context messages / blocks — the
unchanged lines around the new ones — are carried under an explicit header, quoted, so a model
can read a new line in place without extracting old lines as new facts.

No clock, no database, no settings: the promoter decides visibility (the door), counts alias
hits and removes already-seen messages before calling this.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlsplit

from genios_engine.capture.connectors.base import RawObject
from genios_engine.platform.identity import norm_email, person_name_key

SOURCE = "screen_session"
CHAT_THREAD = "screen_chat_thread"
#: The seat's OWN outgoing chat lines. A separate object type because authority is table-driven
#: on (source, object_type): what the seat itself wrote ("I'll send it Friday") weighs as prose
#: (rank 2, plan §7.6), what others wrote in the same chat stays a chat aside (rank 1).
CHAT_SENT = "screen_chat_sent"
EMAIL_THREAD = "screen_email_thread"
DOC = "screen_doc"
OBJECT_TYPES: tuple[str, ...] = (CHAT_THREAD, CHAT_SENT, EMAIL_THREAD, DOC)

CHAT_APPS = frozenset({"whatsapp", "linkedin", "slack"})
EMAIL_APPS = frozenset({"gmail", "outlook"})
GENERIC_APPS = frozenset({"generic", "web"})

MAX_MESSAGES_PER_PART = 40
#: Split thresholds for the NEW text of one object (subject included).
MAX_CHARS = 6000
MAX_CHARS_GENERIC = 12000
#: Ceiling on the FULL prepared text (subject + new text + context section), pinned by group B
#: (§3.1): profile limits 8k / 16k minus the extractor's 58-char fence, with margin. Context is
#: trimmed into the headroom between the split threshold and this ceiling — most recent first.
MAX_BODY = 7900
MAX_BODY_GENERIC = 15900
CONTEXT_HEADER = "context — do not extract"
OUT, IN, DOC_DIR = "out", "in", "doc"


@dataclass(frozen=True)
class Rendered:
    """One object plus the new messages (or blocks) it carries — the promoter claims their
    fingerprints against the event the object becomes."""
    raw: RawObject
    direction: str
    messages: tuple[dict, ...]


def object_type_for(app: str | None) -> str:
    a = (app or "").strip().lower()
    if a in CHAT_APPS:
        return CHAT_THREAD
    if a in EMAIL_APPS:
        return EMAIL_THREAD
    # generic, and any dedicated reader with no thread shape of its own (gcal)
    return DOC


# ── identities ──────────────────────────────────────────────────────────────────────────────
def norm_linkedin_url(url: str | None) -> str | None:
    """§3.2: `https://www.linkedin.com/in/<slug>`, lower-cased, query / fragment / trailing slash
    stripped. Group C's `context.identity.norm_linkedin_url` states the same rule for Layer 2;
    Layer 1 may not import `context`, so the rule is written here too and both must agree."""
    if not url:
        return None
    s = str(url).strip()
    if "://" not in s:
        s = "https://" + s
    try:
        parts = urlsplit(s)
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    if host != "linkedin.com" and not host.endswith(".linkedin.com"):
        return None
    segs = [p for p in (parts.path or "").split("/") if p]
    if len(segs) < 2 or segs[0].lower() != "in":
        return None
    return f"https://www.linkedin.com/in/{segs[1].lower()}"


def linkedin_handle(url: str | None) -> str | None:
    n = norm_linkedin_url(url)
    return f"li:{n}" if n else None


def _parse_ts(value) -> datetime | None:
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip():
        try:
            dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _host(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return (urlsplit(url if "://" in url else "https://" + url).hostname or "").lower() or None
    except ValueError:
        return None


class People:
    """Participants indexed by name key, and the seat's own display name."""

    def __init__(self, participants: Sequence[Mapping], seat_email: str) -> None:
        self.seat_email = seat_email
        self.self_name = None
        self.by_name: dict[str, Mapping] = {}
        self.others: list[Mapping] = []
        for p in participants or ():
            if not isinstance(p, Mapping):
                continue
            if p.get("self"):
                self.self_name = str(p.get("name") or "").strip() or None
                continue
            self.others.append(p)
            key = person_name_key(p.get("name"))
            if key:
                self.by_name.setdefault(key, p)
        self.self_label = self.self_name or seat_email

    def participant_for(self, message: Mapping) -> Mapping | None:
        p = self.by_name.get(person_name_key(message.get("sender")) or "")
        if p is None and len(self.others) == 1:
            p = self.others[0]
        return p

    def identity_of(self, message: Mapping) -> tuple[str | None, str | None]:
        """(actor key, display name) for an incoming message: email, else `li:` URL, else None."""
        p = self.participant_for(message) or {}
        email = norm_email(message.get("sender_email") or message.get("email")
                           or p.get("email"))
        name = str(message.get("sender") or p.get("name") or "").strip() or None
        if email:
            return email, name
        return linkedin_handle(message.get("linkedin_url") or p.get("linkedin_url")), name

    def emails(self) -> list[str]:
        out: list[str] = []
        for p in self.others:
            e = norm_email(p.get("email"))
            if e and e not in out:
                out.append(e)
        return out


def is_outgoing(message: Mapping) -> bool:
    return bool(message.get("is_outgoing")) or str(message.get("sender") or "").lower() == "self"


def _clip(line: str, limit: int) -> str:
    return line if len(line) <= limit else line[: max(1, limit - 1)] + "…"


# ── message and block lines ─────────────────────────────────────────────────────────────────
def _message_line(m: Mapping, people: People) -> str:
    name = people.self_label if is_outgoing(m) else (str(m.get("sender") or "").strip()
                                                     or "Unknown")
    text = " ".join(str(m.get("text") or "").split())
    return f"{name}: {text}" if text else ""


def _cell(v) -> str:
    return " ".join(str("" if v is None else v).split()).replace("|", "/")


def block_lines(block: Mapping, people: People) -> list[tuple[str, str | None]]:
    """A block as (line, table header to repeat when a part starts mid-table)."""
    role = str(block.get("role") or "").lower()
    if role == "heading":
        t = " ".join(str(block.get("text") or "").split())
        return [(t, None)] if t else []
    if role == "kv":
        label, value = _cell(block.get("label")), _cell(block.get("value"))
        return [(f"{label}: {value}", None)] if (label or value) else []
    if role == "table":
        header = block.get("header") or []
        head = ("| " + " | ".join(_cell(h) for h in header) + " |") if header else None
        out: list[tuple[str, str | None]] = [(head, None)] if head else []
        for row in block.get("rows") or []:
            if isinstance(row, (list, tuple)):
                out.append(("| " + " | ".join(_cell(c) for c in row) + " |", head))
        return out
    if role == "message":
        line = _message_line(block, people)
        return [(line, None)] if line else []
    t = block.get("text")
    if t is None:
        t = block.get("value")
    if t is None:
        t = " ".join(str(v) for k, v in block.items()
                     if k not in ("fp", "role") and isinstance(v, (str, int, float)))
    t = " ".join(str(t).split())
    return [(t, None)] if t else []


def _context_lines(lines: list[str], budget: int) -> list[str]:
    """Most recent context first to be kept, output in original order, `> ` quoted."""
    kept: list[str] = []
    used = len(CONTEXT_HEADER) + 2
    for line in reversed([ln for ln in lines if ln]):
        q = "> " + _clip(line, max(8, budget - used - 3))
        if used + len(q) + 1 > budget:
            break
        kept.append(q)
        used += len(q) + 1
    return list(reversed(kept))


def _parts(units: list[tuple[str, str | None, int]], *, budget: int,
           max_units: int | None) -> list[list[tuple[str, int]]]:
    """Fill parts line by line. A unit is (line, repeat header, source index)."""
    parts: list[list[tuple[str, int]]] = []
    cur: list[tuple[str, int]] = []
    used = 0
    count_idx: set[int] = set()
    for line, head, idx in units:
        line = _clip(line, budget)
        new_idx = idx not in count_idx
        over_count = max_units is not None and new_idx and len(count_idx) >= max_units
        if cur and (used + len(line) + 1 > budget or over_count):
            parts.append(cur)
            cur, used, count_idx = [], 0, set()
            if head and head != line:
                cur.append((head, -1))
                used = len(head) + 1
        cur.append((line, idx))
        used += len(line) + 1
        count_idx.add(idx)
    if cur:
        parts.append(cur)
    return parts


def render_session(session: Mapping, *, seat_email: str, watermark: int,
                   received_at: datetime, captured_at: datetime | None = None,
                   alias_hits: int = 0) -> list[Rendered]:
    """§3.1. `session` is the decrypted upload document (messages / blocks already filtered of
    anything the fingerprint ledger has seen)."""
    seat_email = (seat_email or "").strip().lower()
    app = str(session.get("app") or "").strip().lower()
    otype = object_type_for(app)
    thread_key = str(session.get("thread_key") or session.get("session_key") or "")
    title = " ".join(str(session.get("title") or "").split())
    captured = _parse_ts(captured_at) or _parse_ts(session.get("captured_at"))
    people = People(session.get("participants") or [], seat_email)
    split = MAX_CHARS_GENERIC if otype == DOC else MAX_CHARS
    full = MAX_BODY_GENERIC if otype == DOC else MAX_BODY
    title = title[:500]
    overhead = (len(title) + 2) if title else 0
    base_raw = {"subject": title, "message_watermark": int(watermark),
                "alias_hits": int(alias_hits), "app": app, "host": _host(session.get("url")),
                "bundle_id": session.get("bundle_id"), "thread_key": thread_key,
                "session_key": session.get("session_key")}

    groups: list[tuple[str, list[dict], list[str]]] = []      # (direction, items, context lines)
    if app in GENERIC_APPS or session.get("blocks"):
        blocks = [b for b in session.get("blocks") or [] if isinstance(b, Mapping)]
        ctx = [ln for b in session.get("context_blocks") or [] if isinstance(b, Mapping)
               for ln, _ in block_lines(b, people)]
        groups.append((DOC_DIR, [dict(b) for b in blocks], ctx))
    else:
        msgs = [m for m in session.get("messages") or [] if isinstance(m, Mapping)]
        ctx = [_message_line(m, people) for m in session.get("context_messages") or []
               if isinstance(m, Mapping)]
        out_msgs = [dict(m) for m in msgs if is_outgoing(m)]
        in_msgs = [dict(m) for m in msgs if not is_outgoing(m)]
        if otype == DOC:                 # a dedicated reader with no thread shape (gcal)
            groups.append((DOC_DIR, out_msgs + in_msgs, ctx))
        else:
            groups.append((OUT, out_msgs, ctx))
            groups.append((IN, in_msgs, ctx))

    rendered: list[Rendered] = []
    for direction, items, ctx_src in groups:
        if not items:
            continue
        if direction == DOC_DIR and (app in GENERIC_APPS or session.get("blocks")):
            units = [(ln, head, i) for i, b in enumerate(items)
                     for ln, head in block_lines(b, people)]
            max_units = None
        else:
            units = [(_message_line(m, people), None, i) for i, m in enumerate(items)]
            max_units = MAX_MESSAGES_PER_PART
        units = [u for u in units if u[0]]
        if not units:
            continue
        # subject + new (≤ split) + "\n\n" + header + context (≤ full - split) ≤ full
        ctx_lines = _context_lines(ctx_src, full - split) if ctx_src else []
        budget = max(200, split - overhead)
        parts = _parts(units, budget=budget, max_units=max_units)
        for n, part in enumerate(parts, start=1):
            idxs = sorted({i for _, i in part if i >= 0})
            part_items = tuple(items[i] for i in idxs)
            body = "\n".join(line for line, _ in part)
            if ctx_lines:
                body += "\n\n" + CONTEXT_HEADER + "\n" + "\n".join(ctx_lines)
            stamps = [t for t in (_parse_ts(m.get("ts")) for m in part_items) if t is not None]
            occurred = max(stamps) if stamps else (captured or _parse_ts(received_at))
            oid = f"{thread_key}#{int(watermark)}#{direction}"
            if len(parts) > 1:
                oid += f"#p{n}"
            raw = {**base_raw, "body": body, "direction": direction, "part": n,
                   "parts": len(parts)}
            recipients: tuple[str, ...] = ()
            actor_email: str | None = None
            actor_name: str | None = None
            actor_type = "external_contact"
            if direction == OUT:
                actor_email, actor_name, actor_type = seat_email or None, people.self_name, \
                    "internal_user"
                raw["labelIds"] = ["SENT"]
                recipients = tuple(people.emails())
            elif direction == IN:
                last = part_items[-1] if part_items else {}
                actor_email, actor_name = people.identity_of(last)
                recipients = tuple(e for e in [seat_email, *people.emails()]
                                   if e and e != actor_email)
            else:
                raw["block_stats"] = {
                    "kv": sum(1 for b in part_items if str(b.get("role")).lower() == "kv"),
                    "table": sum(1 for b in part_items
                                 if str(b.get("role")).lower() == "table")}
            rendered.append(Rendered(
                raw=RawObject(source=SOURCE,
                              object_type=CHAT_SENT if (direction == OUT and otype == CHAT_THREAD)
                              else otype,
                              source_object_id=oid,
                              occurred_at=occurred, actor_email=actor_email,
                              actor_name=actor_name, actor_type=actor_type,
                              parent_object_id=thread_key or None,
                              content_version=str(int(watermark)), recipients=recipients,
                              raw=raw),
                direction=direction, messages=part_items))
    return rendered


__all__ = ["CHAT_SENT", "CHAT_THREAD", "CONTEXT_HEADER", "DOC", "EMAIL_THREAD", "MAX_CHARS", "People",
           "MAX_CHARS_GENERIC", "MAX_MESSAGES_PER_PART", "OBJECT_TYPES", "Rendered", "SOURCE",
           "block_lines", "is_outgoing", "linkedin_handle", "norm_linkedin_url",
           "object_type_for", "render_session"]
