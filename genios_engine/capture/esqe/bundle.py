"""L1.6.11 · the signal bundle — the signals that ARRIVED together, grouped once, at capture.

Four signals about one vendor renewal used to cross the L1 → L2 seam as four loose events, and
Layer 2 rebuilt the grouping from whatever survived the projection: four weak situations instead of
one strong one. The grouping was knowable here, where the evidence for it still exists, and was
thrown away at the boundary. That is `not_carried` one seam earlier than it usually appears.

⛔ INCOMING ONLY, AND THAT IS A STRUCTURAL RULE RATHER THAN A SCOPE DECISION.
This module joins signals that arrived together. It does **not** relate them to what the company
already knows — that needs the graph, the graph is Layer 3, and `capture/` importing `context/` is
an upward import `tests/test_layer_topology.py` fails the build on. Relating new signals to existing
situations is reasoning and happens above this seam. `docs/LAYER_MAP.md` records the rule.

So nothing here reads a database. It is a pure function over the signals one page produced, which
is also what makes it testable without a fixture.

⛔ THE TWO JOIN CLASSES ARE NOT THE SAME, AND TREATING THEM ALIKE IS THE BUG THIS AVOIDS.

    IDENTITY joins — same thread, same subject. A thread is a thread whether its messages are
    four minutes or four months apart, and splitting one on a clock would produce two half-threads
    that each look like a complete conversation. No window.

    PROXIMITY joins — same entity. "Acme" in January and "Acme" in September are the same company
    and NOT the same event. Without a window every mention of a frequent counterparty collapses
    into one ever-growing bundle that means nothing. Windowed.

⛔ COVERAGE IS MERGED BY TAKING THE WEAKEST, PER SOURCE. See `merged_coverage`.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from datetime import timedelta
from typing import Any

from genios_engine.contracts.signal import QualifiedEnterpriseSignalBundle

#: How far apart two signals may be and still be joined by a shared ENTITY alone.
#:
#: Seven days, and the reasoning is the unit of work rather than a tuning knob: a business thing
#: that happens to one counterparty — a renewal, an onboarding, an escalation — is worked within a
#: week, and two mentions further apart than that are two pieces of work about one company. Widening
#: it does not find more truth; it merges unrelated work under a familiar name.
#:
#: It does NOT apply to thread or subject joins. Those are identity, not proximity.
ENTITY_WINDOW = timedelta(days=7)


def join_keys(signal: Any) -> frozenset[str]:
    """Everything this signal could be grouped BY, namespaced so two kinds never collide.

    Namespacing is not cosmetic: a thread key and a subject key are both opaque strings, and an
    unprefixed set would join a thread to a contract that happened to hash the same way — a join
    nobody could explain afterwards from the bundle alone.
    """
    keys: set[str] = set()
    thread = getattr(signal, "thread_key", None)
    if thread:
        keys.add(f"thread:{thread}")
    subject = getattr(signal, "subject_key", None)
    if subject:
        keys.add(f"subject:{subject}")
    return frozenset(keys)


def entity_keys(signal: Any) -> frozenset[str]:
    """The entities this signal mentions, as resolved — the PROXIMITY join's keys.

    Kept apart from `join_keys` because they are windowed and those are not, and a caller that
    cannot tell the two apart will eventually apply the window to a thread.
    """
    extraction = getattr(signal, "extraction", None)
    mentions = getattr(extraction, "entities", None) or ()
    found: set[str] = set()
    for mention in mentions:
        key = (getattr(mention, "canonical_hint", None)
               or getattr(mention, "surface_form", None) or "").strip()
        if key:
            found.add(f"entity:{key.lower()}")
    return frozenset(found)


def _instant(signal: Any):
    return getattr(signal, "occurred_at", None) or getattr(signal, "ingested_at", None)


def _within_window(a: Any, b: Any) -> bool:
    """True when two signals are close enough for an ENTITY join to mean anything.

    A signal with no instant at all is joined rather than excluded: it is missing a date, not
    proven to be far away, and dropping it would silently shrink a bundle for a reason the bundle
    could not then state.
    """
    left, right = _instant(a), _instant(b)
    if left is None or right is None:
        return True
    return abs(left - right) <= ENTITY_WINDOW


def group_signals(signals: Sequence[Any]) -> list[tuple[Any, ...]]:
    """Partition one page's signals into groups. Order inside a group is qualification order.

    Union-find over shared keys. Identity keys join unconditionally; entity keys join only inside
    `ENTITY_WINDOW`. A signal that shares nothing with anything is its own group of one — a bundle
    of one is a real answer ("this arrived alone"), not a failure to group.
    """
    parent: dict[int, int] = {i: i for i in range(len(signals))}

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    identity = [join_keys(s) for s in signals]
    entities = [entity_keys(s) for s in signals]
    for i in range(len(signals)):
        for j in range(i + 1, len(signals)):
            if identity[i] & identity[j]:
                union(i, j)
            elif entities[i] & entities[j] and _within_window(signals[i], signals[j]):
                union(i, j)

    groups: dict[int, list[Any]] = {}
    for index, signal in enumerate(signals):
        groups.setdefault(find(index), []).append(signal)
    return [tuple(members) for _, members in sorted(groups.items())]


def bundle_id_for(org_id: str, signal_ids: Iterable[str]) -> str:
    """Deterministic over the org and the SORTED member ids.

    ⛔ This is the idempotence. A replayed connector page produces the same id, and the insert
    collapses to one row. A serial id would have made every replay a second bundle and every
    denominator computed from bundles wrong by however many times the page was retried.

    Sorted, because the group is a SET — the same three signals arriving in a different order are
    the same bundle, and an order-sensitive id would deny that.
    """
    material = f"{org_id}|" + "|".join(sorted(str(s) for s in signal_ids))
    return "sb_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:32]


def merged_coverage(signals: Sequence[Any]) -> dict[str, Any]:
    """The group's coverage — **per source, and the WEAKEST member's for each.**

    ⛔ WHY THE WEAKEST, AND NEVER AN AVERAGE. A claim about a group is only as licensed as its
    least-covered member: if one signal in the bundle was captured when 8% of the mail had been
    read, a negative claim about the GROUP rests on that 8% however well-covered its siblings were.
    Averaging would manufacture a licence nobody has — the same failure `ConfidenceVector` names
    when it bounds a composed score by its weakest axis.

    ⛔ AND STILL PER SOURCE. Never one number for the bundle: *"a tenant with complete calendar
    coverage and 8% email coverage has two different licences to make a negative claim."*

    UNKNOWN BEATS KNOWN. A source one member could not measure (`completeness_bp = None`) makes the
    group's coverage of that source unknown, because "we do not know what we read" is weaker than
    any percentage — and a caller must be able to tell it from a low one.

    The window is the widest the members span: a claim about the group covers the whole period the
    group occupies, and narrowing it would overstate what was searched.
    """
    per_source: dict[str, dict[str, Any]] = {}
    starts, ends = [], []
    for signal in signals:
        block: Mapping[str, Any] = getattr(signal, "coverage", None) or {}
        if block.get("window_from") is not None:
            starts.append(block["window_from"])
        if block.get("window_to") is not None:
            ends.append(block["window_to"])
        for entry in block.get("sources", ()) or ():
            source = entry.get("source")
            if not source:
                continue
            held = per_source.get(source)
            if held is None:
                per_source[source] = dict(entry)
                continue
            mine, theirs = held.get("completeness_bp"), entry.get("completeness_bp")
            # None is weaker than any number, so it wins. Otherwise the smaller share wins.
            if mine is None:
                continue
            if theirs is None or theirs < mine:
                per_source[source] = dict(entry)

    merged: dict[str, Any] = {"sources": [per_source[k] for k in sorted(per_source)]}
    if starts:
        merged["window_from"] = min(starts)
    if ends:
        merged["window_to"] = max(ends)
    return merged


def build_bundle(org_id: str, trace_id: str,
                 members: Sequence[Any]) -> QualifiedEnterpriseSignalBundle:
    """One group → the boundary object. Pure; nothing is written here."""
    signal_ids = tuple(str(getattr(s, "signal_id")) for s in members)
    subjects = {getattr(s, "subject_key", None) for s in members} - {None}
    entities: set[str] = set()
    for signal in members:
        entities |= entity_keys(signal)

    unresolved: list[str] = []
    if not subjects:
        # Stated rather than left blank: "these arrived together and nobody could name what they
        # are about" is a fact Layer 2 can act on — it is what an EvidenceNeed is raised from.
        unresolved.append("no subject could be named for this group")

    return QualifiedEnterpriseSignalBundle(
        bundle_id=bundle_id_for(org_id, signal_ids),
        org_id=org_id,
        trace_id=trace_id,
        # ⛔ One subject, or none. Two different subjects in one group is not a bundle with two
        # subjects — it is a group the joins over-merged, and naming one of them would hide that.
        subject_key=next(iter(subjects)) if len(subjects) == 1 else None,
        signal_ids=signal_ids,
        entity_keys=tuple(sorted(entities)),
        candidate_relationships=tuple(
            f"{sid} concerns {next(iter(subjects))}" for sid in signal_ids
        ) if len(subjects) == 1 else (),
        coverage=merged_coverage(members),
        unresolved=tuple(unresolved),
    )


def build_bundles(org_id: str, trace_id: str,
                  signals: Sequence[Any]) -> list[QualifiedEnterpriseSignalBundle]:
    """One page of qualified signals → its bundles."""
    return [build_bundle(org_id, trace_id, members) for members in group_signals(signals)]


__all__ = ["ENTITY_WINDOW", "build_bundle", "build_bundles", "bundle_id_for", "entity_keys",
           "group_signals", "join_keys", "merged_coverage"]
