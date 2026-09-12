"""The shipped projections a structured object takes into L2 — values, and edges.

Both go through `targets.sift_mapping_targets` first, and that is the whole of W2's residual
sink-hole fix. `commit_structured` writes what these two functions return straight into the
graph — ``write_fact(field=<target>)`` and ``write_edge(edge_type=<edge_type>)`` — so a name that
gets past here is a name that is stored, and `FieldMap.target` is a string a customer types into
`GENIOS_STRUCTURED_MAPPINGS`. Sifting HERE rather than at each call site is what closes both
production paths at once: `capture/pipeline.py`'s structured route and `context/runner.py`'s L2
drain call these two functions and nothing else.
"""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any

from genios_engine.platform.identity import norm_email

from .registry import StructuredMapping
from .targets import sift_mapping_targets

# personal mailbox domains — an attendee here is a person, never evidence of a company
_PERSONAL_DOMAINS = {"gmail.com", "googlemail.com", "outlook.com", "hotmail.com",
                     "yahoo.com", "icloud.com", "proton.me", "protonmail.com"}


def apply_mapping(mapping: StructuredMapping, raw_fields: dict[str, Any]) -> dict[str, Any]:
    """Map a structured source object's fields to target fields per the mapping.

    Deterministic, no LLM. Unknown source fields are ignored (never guessed), and a target name
    the graph cannot be queried by is REFUSED — `sift_mapping_targets` decides which, and hands
    the refused name to the open lane instead of to `write_fact`.

    A dict, still, because `commit_structured` and `GatedEvent.structured_fields` take one; what
    changed is that every key in it is now a name a rule can address. `sift_mapping_targets` is
    pure and idempotent, so putting it on this path costs one pass over the mapping's declared
    fields and nothing else.
    """
    fields = dict(sift_mapping_targets(mapping, raw_fields).fields)
    # WHOSE MONEY, when the mapping knows. Written here rather than in either caller because
    # this module's own docstring states that `capture/pipeline.py`'s structured route and
    # `context/runner.py`'s L2 drain "call these two functions and nothing else" — so one seam
    # covers both production paths.
    #
    # ONLY WHEN DECLARED. An undeclared mapping writes no fact, which keeps "we do not know
    # whose money this is" distinguishable from "it is ours" — the distinction the whole field
    # exists for, and one a default would destroy on every source written before it.
    if mapping.money_direction:
        fields[f"{mapping.namespace}.money_direction"] = mapping.money_direction
    return fields


def _emails_from(value: Any) -> list[tuple[str, str | None]]:
    """Normalise an attendees-style field into (email, display_name) pairs. Accepts a bare
    string, a list of strings, or a list of {email, displayName} dicts (Google/CRM shapes)."""
    items = value if isinstance(value, list) else [value]
    out: list[tuple[str, str | None]] = []
    for it in items:
        if isinstance(it, str):
            email, name = it, None
        elif isinstance(it, dict):
            email, name = it.get("email") or it.get("address"), it.get("displayName") or it.get("name")
        else:
            continue
        canonical = norm_email(email)
        if canonical:
            out.append((canonical, name))
    return out


def apply_relations(mapping: StructuredMapping, raw_fields: dict[str, Any]) -> list[dict[str, Any]]:
    """Resolve a structured object's declared relations into edge specs the commit layer can
    write: {node_type, canonical_key, display_name, edge_type, direction}. Deterministic, no LLM.
    Person identity is the lowercased email so attendee-persons MERGE with pipeline-created
    persons."""
    out: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    # The SIFTED relations: `edge_type` and `related_node_type` are written into the graph as an
    # edge kind and a node kind, so a relation naming either in a form no query uses is refused
    # into the open lane exactly as a bad field target is.
    for rel in sift_mapping_targets(mapping, raw_fields).mapping.relations:
        raw_val = raw_fields.get(rel.source_field)
        if raw_val in (None, "", []):
            continue
        if rel.identity == "email":
            for email, name in _emails_from(raw_val):
                key = (rel.edge_type, email)
                if key in seen:
                    continue
                seen.add(key)
                out.append({"node_type": rel.related_node_type, "canonical_key": email,
                            "display_name": name or email, "edge_type": rel.edge_type,
                            "direction": rel.direction})
    return out


# ── Calendar availability (no LLM) ─────────────────────────────────────────────────────────────
# Google marks an out-of-office block with eventType "outOfOffice"; people also block leave as an
# all-day event titled "Leave" / "OOO" / "Vacation" / "Holiday". Either is the calendar owner
# saying "I am not available then" — the most authoritative availability statement there is.
_LEAVE_TITLE = re.compile(
    r"\b(out of (the )?office|ooo|on leave|leave|annual leave|sick leave|vacation|holidays?|pto|"
    r"time off|day off|off sick|sick|chutti|travel(l)?ing|business trip)\b", re.I)
# All-day events that merely MENTION the word ("Holiday party", "Leave policy review").
_NOT_ABSENCE = re.compile(
    r"\b(party|lunch|dinner|celebration|planning|plan|policy|review|sync|meeting|call|list|"
    r"calendar|deadline|sale|agenda)\b", re.I)
# A group / resource / holiday calendar address is not a person.
_GROUP_CALENDAR = re.compile(r"(calendar\.google\.com$|#|resource\.calendar)", re.I)


def _date_of(value: Any) -> tuple[date | None, datetime | None]:
    """A gcal start/end → (date, datetime-if-timed)."""
    if not isinstance(value, str) or not value:
        return None, None
    if len(value) == 10:
        try:
            return date.fromisoformat(value), None
        except ValueError:
            return None, None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None, None
    return dt.date(), dt


def _title_kind(title: str) -> str:
    t = title.lower()
    if "sick" in t:
        return "sick"
    if "travel" in t or "business trip" in t:
        return "travel"
    if "ooo" in t or "out of" in t:
        return "ooo"
    return "leave"


def calendar_availability(raw: dict[str, Any] | None) -> dict[str, Any] | None:
    """A calendar event → {person, kind, from, to, cancelled, title, updated}, or None if it is
    not an availability block. Deterministic. None whenever the owner cannot be named — a block we
    cannot attribute stays the meeting node it already is, never assigned to a guessed person."""
    raw = raw or {}
    title = str(raw.get("summary") or "").strip()
    start_d, _ = _date_of(raw.get("start"))
    end_d, end_dt = _date_of(raw.get("end"))
    if start_d is None:
        return None
    all_day = isinstance(raw.get("start"), str) and len(raw["start"]) == 10
    if str(raw.get("eventType") or "") == "outOfOffice":
        kind = _title_kind(title) if _LEAVE_TITLE.search(title) else "ooo"
    elif all_day and _LEAVE_TITLE.search(title) and not _NOT_ABSENCE.search(title):
        kind = _title_kind(title)
    else:
        return None

    person = norm_email(raw.get("calendar_owner"))
    if person is None:
        # No `self` flag: the organizer owns it only when it is a real person's block (nobody
        # else invited) — a shared calendar's all-day event is not the organizer's leave.
        organizer = norm_email(raw.get("organizer"))
        others = {norm_email(a) for a in (raw.get("attendees") or []) if norm_email(a)} - {organizer}
        if organizer and not _GROUP_CALENDAR.search(organizer) and not others:
            person = organizer
    if person is None or _GROUP_CALENDAR.search(person):
        return None

    if end_d is None:
        to_d = start_d
    elif all_day:
        to_d = end_d - timedelta(days=1)            # an all-day end date is EXCLUSIVE
    elif end_dt is not None and end_dt.time() == datetime.min.time() and end_d > start_d:
        to_d = end_d - timedelta(days=1)            # ends at midnight → the day before
    else:
        to_d = end_d
    to_d = max(to_d, start_d)
    return {"person": person, "kind": kind, "from": start_d.isoformat(), "to": to_d.isoformat(),
            "cancelled": str(raw.get("status") or "").lower() == "cancelled", "title": title,
            "updated": raw.get("updated")}
