"""L2.7 · the blockers the graph could not name — a surface for a refusal, not a silence.

`correlation_dependency` runs every sweep and publishes four fields. Three of them reach a reader.
`derived.dependency.missing_prerequisite` reached NOTHING: it was computed, written, bounded,
evidence-carrying, and selected by no query in the engine. This module is the missing half.

WHAT THE FIELD HOLDS, and why it is the most interesting of the four. The traversal resolves both
ends of every dependency claim through the identity cascade. When the BLOCKED end resolves and the
BLOCKER end does not, it refuses to invent a node — doc 03's hard rule, and the module's own
sentence for it is *"a false chain is worse than a missing one"* — and files a typed absence
instead. `MissingPrerequisite`'s docstring names the examples: *"Finance", "legal", "the security
review"*.

THOSE ARE NOT RESOLVER FAILURES. They are real blockers that were never people in a mailbox, and
the graph is correct to hold no node for them. So the most common case here is not a defect at
all: it is an open dependency on something outside the record, which the deterministic layer sees
clearly, refuses to make an edge for, and — until this module — never said out loud. A founder
blocked on their lawyer had that fact computed on every sweep and shown to nobody.

TWO KINDS OF ABSENCE, AND THE CARD MAY NOT CONFLATE THEM. `AbsenceType.GENUINELY_ABSENT` is only
reached when the caller declared a coverage basis; everything else is `UNKNOWABLE`. The
correlator's own header is explicit: *"'we could not find the blocker' is not the same claim as
'the blocker does not exist', and only the second one licenses telling a human there is nobody
there."* The headline below is built from that flag, not from the absence of a node.

ONE FINDING PER (SUBJECT, NAMED BLOCKER), because they end separately: the day "Finance" resolves
to a node, that absence is gone and "the security review" is still open. The anchor is its own —
`condition_situations` made the same call for the same reason.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from sqlalchemy import text

#: ONE SPELLING, IMPORTED FROM THE WRITER. `correlation_dependency` builds the name as
#: `f"{FACT_PREFIX}.missing_prerequisite"`, so a literal here would keep selecting nothing the day
#: the prefix moved — the exact trap `condition_situations` records against its own twin, and the
#: one `tests/test_nothing_is_written_and_never_read.py` was written to catch.
from genios_engine.context.correlation_dependency import (
    FIELD_MISSING_PREREQUISITE as BLOCKER_FIELD)

#: SUBJECT NODE, whose value is `{"absences": [ …one per named blocker… ]}` — so a person waiting
#: on three unnamed things is one fact carrying three entries, not three facts.
_BLOCKER_ROWS = (
    "select f.subject_node_id as node_id, f.value as value "
    "from graph_facts f "
    "where f.org_id = :o and f.field = :field and f.status = 'active' "
    "and f.valid_to is null "
    "order by f.subject_node_id"
)

#: How many of one node's absences become findings. Bounded for the reason every reader here is:
#: a node with a long history can accumulate them and one busy subject must not fill a feed.
#: Ordered by the blocker's name before the cut so the survivors are stable across sweeps — an
#: unstable cut would open and close the same card forever.
MAX_PER_NODE = 6

#: The absence flag that licenses the stronger sentence. Anything else — including a missing or
#: unrecognised value — reads as "we could not find it", which is the claim that is always safe.
GENUINELY_ABSENT = "genuinely_absent"

#: One blocker nobody could resolve. Its own anchor rather than the waiting person's: a subject can
#: be blocked on several unnamed things at once and they close one at a time.
ANCHOR_UNNAMED_BLOCKER = "unnamed_blocker"


def blocker_key(subject_node_id: str, blocker_named: str) -> str:
    """The content address of one absence. Stable across sweeps and safe in a canonical key.

    Hashed rather than interpolated because the blocker is FREE TEXT out of a counterparty's
    sentence — "the security review", "Finance / legal", a name with a colon in it — and a
    canonical key is parsed on a delimiter elsewhere in this layer.
    """
    payload = "\x1f".join((subject_node_id.strip(), " ".join(blocker_named.split()).lower()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _entries(value: Any) -> tuple[Mapping, ...]:
    """The absences inside one stored row, defensively.

    The column is `jsonb` and arrives as a mapping from Postgres and as a string from a driver
    that has not decoded it; both are accepted. Anything else yields nothing rather than raising —
    a malformed row is one silent blocker, an exception is every blocker on the tenant. Lifted
    whole from `condition_situations._entries`, which learned it the same way.
    """
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return ()
    if not isinstance(value, Mapping):
        return ()
    found = value.get("absences")
    if not isinstance(found, (list, tuple)):
        return ()
    return tuple(entry for entry in found if isinstance(entry, Mapping))


def _quote(entry: Mapping) -> str | None:
    """The sentence that named the blocker — the receipt that makes the absence checkable.

    Only the quote is taken. The offsets address a `prepared_content` frame this layer does not
    hold, and carrying them would invite a reader to resolve them against the wrong text; the
    condition reader states the same rule against the same span shape.
    """
    spans = entry.get("evidence")
    if not isinstance(spans, (list, tuple)):
        return None
    for span in spans:
        if isinstance(span, Mapping):
            quote = str(span.get("quote") or "").strip()
            if quote:
                return quote
    return None


def _absence_type(entry: Mapping) -> str | None:
    absence = entry.get("absence")
    if not isinstance(absence, Mapping):
        return None
    value = absence.get("absence_type")
    return None if value is None else str(value).strip().lower()


def read_unnamed_blockers(rows: Mapping[str, object], now: datetime,
                          employers: dict | None = None) -> list:
    """One finding per named blocker that resolved to nobody.

    An entry with no name yields nothing: "somebody is blocked by something" is not a card, and
    the name is the only part a reader can act on. The QUOTE is not required — a claim reaching
    this point already passed `DependencyLink`'s evidence gate, so a missing quote here means the
    span did not survive serialisation, and dropping the finding for that would hide a real
    blocker to protect a formatting detail.

    `now` and `employers` are unused and present because `READINGS` dispatches every reader
    through one signature. The absence payload carries no timestamp — `MissingPrerequisite` holds
    the typed absence, the name and the spans, and none of the three records WHEN the dependency
    was stated — so this reading has no clock to read and declares the gap instead of inventing
    an age from the sweep time.
    """
    from genios_engine.context.outreach_situations import _Finding

    findings: list = []
    for node_id, value in rows.items():
        if str(node_id).startswith("_"):
            continue
        entries = _entries(value)
        if not entries:
            continue
        ordered = sorted(entries, key=lambda e: str(e.get("blocker_named") or ""))[:MAX_PER_NODE]
        for entry in ordered:
            named = " ".join(str(entry.get("blocker_named") or "").split())
            if not named:
                continue

            facts: list[tuple[str, object, str]] = [("blocker.named", named, "string")]
            quote = _quote(entry)
            if quote:
                facts.append(("blocker.quote", quote, "string"))

            # THE FLAG THAT DECIDES WHAT THE CARD IS ALLOWED TO SAY. Carried as a fact rather than
            # folded into the headline alone, so a renderer downstream cannot reach the stronger
            # sentence without reading the same value this one did.
            absence = _absence_type(entry)
            searched = absence == GENUINELY_ABSENT
            if absence:
                facts.append(("blocker.absence_type", absence, "enum"))
            facts.append(("blocker.we_searched", searched, "bool"))

            # "not in your records" is a claim about a SEARCH; "we could not find" is a claim about
            # this system. Only the first is licensed, and only when a coverage basis was declared.
            display = (f"blocked on {named} — not in your records" if searched
                       else f"blocked on {named} — we could not find it")

            findings.append(_Finding(
                anchor=ANCHOR_UNNAMED_BLOCKER,
                canonical_key=f"blocker:{blocker_key(str(node_id), named)}",
                display_name=display,
                facts=facts,
                concerns_node=str(node_id),
                correlation_id=f"blocker:{blocker_key(str(node_id), named)}",
                # DECLARED, NOT DISCOVERED. `blocker.identity` is absent by definition — the
                # absence IS the finding — and declaring it keeps the coverage score honest
                # rather than scoring this reading as complete. `blocker.stated_at` is absent for
                # a duller reason: the published payload carries no timestamp at all, so nothing
                # here can say how long this has been true.
                missing=["blocker.identity", "blocker.stated_at"],
                inputs={"reading": ANCHOR_UNNAMED_BLOCKER,
                        "derived_from": "correlation_dependency missing_prerequisite; "
                                        "blocked end resolved, blocker end did not"},
            ))
    return findings


def gather_unnamed_blockers(conn, org_id: str) -> dict[str, object]:
    """The stored absence rows for one org, keyed by subject node."""
    rows = conn.execute(text(_BLOCKER_ROWS), {"o": org_id, "field": BLOCKER_FIELD}).mappings().all()
    return {str(row["node_id"]): row["value"] for row in rows}


__all__ = ["ANCHOR_UNNAMED_BLOCKER", "BLOCKER_FIELD", "GENUINELY_ABSENT", "MAX_PER_NODE",
           "blocker_key", "gather_unnamed_blockers", "read_unnamed_blockers"]
