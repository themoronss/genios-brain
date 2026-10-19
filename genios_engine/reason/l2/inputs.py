"""GeniOS-008 L2 B · what arrived — the L1 bundles since the last run, their signals, and whose they are.

Two L1 items land here, on the reading side:

  E1  the bundle (`signal_bundles`, written since `capture/esqe/bundle_store`) is where a run STARTS;
  E8  nothing L1 computed goes uncarried: each member signal's `ball_in_court`, `thread_key`, `direction`,
      `due_at`, `coverage` and quoted evidence were written to `qualified_signals` and read by nobody.
      They are read here, by the bundle's own signal ids, and printed in the dossier's SIGNALS block.

THE SUBJECT OF A RUN (L2-Q6 default). A bundle whose events belong to a FILE (`context/workstreams` — one
counterparty's work) is reasoned with that file: the founder asks "where are we with X", and the STEP-12
dossier already knows the file. A bundle no file holds is reasoned on its own SEED — its thread, else its
subject key — so a vendor invoice or a portal notice still gets a run. Several bundles of one subject in
one sweep are one run.

AN ORG-LEVEL READER: a signal a seat captured privately is never a run's evidence.
"""
from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any

from sqlalchemy import text

from genios_engine.capture.esqe.bundle_store import StoredBundle, read_bundles_since

#: The most quoted words printed per signal — the evidence a fact may quote.
QUOTES_PER_SIGNAL = 2

_SIGNALS = text(
    "select q.signal_id, q.event_id, q.signal_type, q.subject_key, q.occurred_at, q.due_at, q.thread_key, "
    "       q.direction, q.ball_in_court, q.importance_bp, q.state, q.coverage, q.internal_kind, q.evidence_refs, "
    "       q.visibility, e.actor "
    "  from qualified_signals q left join source_events e on e.org_id = q.org_id and e.event_id = q.event_id "
    " where q.org_id = :o and q.signal_id = any(:ids)")


def _loads(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (str, bytes)):
        try:
            return json.loads(value)
        except ValueError:
            return fallback
    return value


@dataclass(frozen=True, slots=True)
class L2Signal:
    """One published signal, with every field L1 computed and nobody read (E8)."""
    signal_id: str
    event_id: str
    signal_type: str
    subject_key: str | None
    occurred_at: datetime | None
    due_at: datetime | None = None
    thread_key: str | None = None
    direction: str | None = None
    ball_in_court: str | None = None
    importance_bp: int | None = None
    state: str | None = None
    coverage: Mapping[str, Any] | None = None
    internal_kind: str | None = None
    quotes: tuple[str, ...] = ()
    #: Who wrote it, as the source named them (`source_events.actor`) — a claim may name only who its lines name.
    sender: str | None = None
    #: L2 rebuild · the amounts its extraction named, as (currency, minor units) — for the money tool's arithmetic.
    amounts: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class Subject:
    """What one run is about, and what arrived for it this sweep."""
    subject_ref: str                     # `file:<anchor node>` or `seed:<thread or subject key>`
    file_id: str | None
    seed_key: str | None
    bundle_ids: tuple[str, ...]
    signals: tuple[L2Signal, ...]
    coverage: tuple[Mapping[str, Any], ...] = ()
    unresolved: tuple[str, ...] = ()
    newest_bundle_at: datetime | None = None
    #: The OLDEST bundle of this subject read this sweep — where the watermark must stay when the subject is
    #: carried, so its bundles are read again rather than passed over.
    oldest_bundle_at: datetime | None = None
    trigger: str = "bundle"

    @property
    def events(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(s.event_id for s in self.signals))


def _private(visibility: Any) -> bool:
    v = _loads(visibility, {}) or {}
    return isinstance(v, Mapping) and v.get("scope") == "private"


def _signal(row: Any) -> L2Signal:
    m = row._mapping if hasattr(row, "_mapping") else row
    refs = _loads(m["evidence_refs"], []) or []
    actor = _loads(m.get("actor") if hasattr(m, "get") else None, {}) or {}
    sender = None
    if isinstance(actor, Mapping):
        name, email = (actor.get("name") or "").strip(), (actor.get("email") or "").strip()
        sender = (f"{name} <{email}>" if name and email else name or email) or None
    quotes = tuple(dict.fromkeys(" ".join(str(r.get("quote") or "").split())
                                 for r in refs if isinstance(r, Mapping) and r.get("quote")))
    return L2Signal(signal_id=str(m["signal_id"]), event_id=str(m["event_id"]),
                    signal_type=str(m["signal_type"]), subject_key=m["subject_key"],
                    occurred_at=m["occurred_at"], due_at=m["due_at"], thread_key=m["thread_key"],
                    direction=m["direction"], ball_in_court=m["ball_in_court"],
                    importance_bp=m["importance_bp"], state=m["state"],
                    coverage=_loads(m["coverage"], None), internal_kind=m["internal_kind"],
                    quotes=quotes[:QUOTES_PER_SIGNAL], sender=sender)


#: The amounts each event's extraction named — one read for every signal of the pass (L2 rebuild, the money tool).
_AMOUNTS = text(
    "select event_id, output -> 'amounts' as amounts from l1_extraction_results "
    " where org_id = :o and event_id = any(:ids)")


def _amounts_of(raw: Any) -> tuple[tuple[str, int], ...]:
    out = []
    for a in _loads(raw, []) or []:
        if not isinstance(a, Mapping):
            continue
        cur, minor = str(a.get("currency") or "").strip().upper(), a.get("minor_units")
        if cur and isinstance(minor, int) and not isinstance(minor, bool) and minor >= 0:
            out.append((cur, minor))
    return tuple(out)


def read_signals(conn, org_id: str, signal_ids: Iterable[str]) -> dict[str, L2Signal]:
    ids = sorted(set(signal_ids))
    if not ids:
        return {}
    rows = conn.execute(_SIGNALS, {"o": org_id, "ids": ids}).all()
    signals = {str(r.signal_id): _signal(r) for r in rows if not _private(r.visibility)}
    events = sorted({s.event_id for s in signals.values()})
    named: dict[str, list[tuple[str, int]]] = {}
    for r in (conn.execute(_AMOUNTS, {"o": org_id, "ids": events}) if events else ()):
        for a in _amounts_of(r.amounts):
            if a not in named.setdefault(str(r.event_id), []):
                named[str(r.event_id)].append(a)
    return {k: (replace(s, amounts=tuple(named[s.event_id])) if s.event_id in named else s)
            for k, s in signals.items()}


def seed_of(bundle: StoredBundle, signals: Sequence[L2Signal]) -> str | None:
    """A bundle's own seed when no file holds it: its thread, else its subject — None when it has neither."""
    threads = sorted({s.thread_key for s in signals if s.thread_key})
    if threads:
        # L1 writes `thread:<provider thread id>` (`capture/pipeline` ThreadContext) — kept as it is, never
        # prefixed twice, so a need's `subject_ref` is the reference L1's fetcher reads.
        return threads[0] if threads[0].startswith("thread:") else f"thread:{threads[0]}"
    if bundle.subject_key:
        return f"subject:{bundle.subject_key}"
    subjects = sorted({s.subject_key for s in signals if s.subject_key})
    return f"subject:{subjects[0]}" if subjects else None


def subjects_for(bundles: Sequence[StoredBundle], signals: Mapping[str, L2Signal],
                 file_of_event: Mapping[str, str]) -> list[Subject]:
    """Group this sweep's bundles by what they are about. Pure — the same inputs, the same subjects,
    in a stable order (oldest arrival first)."""
    grouped: dict[str, dict[str, Any]] = {}
    for bundle in bundles:
        members = [signals[s] for s in bundle.signal_ids if s in signals]
        if not members:
            continue                         # every member private, or none stored: nothing to reason on
        files = sorted({file_of_event[s.event_id] for s in members if s.event_id in file_of_event})
        if files:
            ref, file_id, seed = f"file:{files[0]}", files[0], None
        else:
            seed = seed_of(bundle, members)
            if seed is None:
                continue
            ref, file_id = f"seed:{seed}", None
        g = grouped.setdefault(ref, {"file_id": file_id, "seed": seed, "bundles": [], "signals": {},
                                     "coverage": [], "unresolved": [], "at": None, "first": None})
        g["bundles"].append(bundle.bundle_id)
        for s in members:
            g["signals"][s.signal_id] = s
        if bundle.coverage:
            g["coverage"].append(dict(bundle.coverage))
        g["unresolved"].extend(bundle.unresolved)
        if bundle.created_at is not None and (g["at"] is None or bundle.created_at > g["at"]):
            g["at"] = bundle.created_at
        if bundle.created_at is not None and (g["first"] is None or bundle.created_at < g["first"]):
            g["first"] = bundle.created_at
    out = []
    for ref, g in grouped.items():
        sigs = sorted(g["signals"].values(), key=lambda s: (s.occurred_at is None, s.occurred_at, s.signal_id))
        out.append(Subject(subject_ref=ref, file_id=g["file_id"], seed_key=g["seed"],
                           bundle_ids=tuple(g["bundles"]), signals=tuple(sigs),
                           coverage=tuple(g["coverage"]), unresolved=tuple(dict.fromkeys(g["unresolved"])),
                           newest_bundle_at=g["at"], oldest_bundle_at=g["first"]))
    out.sort(key=lambda s: (s.newest_bundle_at is None, s.newest_bundle_at, s.subject_ref))
    return out


def read_subjects(conn, org_id: str, *, after: datetime | None, files: Sequence[Any],
                  limit: int = 500) -> tuple[list[Subject], datetime | None]:
    """The subjects of every bundle stored after `after`, and the newest bundle instant read (the next
    watermark — `None` when nothing new arrived)."""
    bundles = read_bundles_since(conn, org_id, after=after, limit=limit)
    if not bundles:
        return [], None
    signals = read_signals(conn, org_id, (s for b in bundles for s in b.signal_ids))
    file_of_event = {str(e): str(f.file_id) for f in files for e in (f.events or ())}
    newest = max((b.created_at for b in bundles if b.created_at is not None), default=None)
    return subjects_for(bundles, signals, file_of_event), newest


__all__ = ["L2Signal", "QUOTES_PER_SIGNAL", "Subject", "read_signals", "read_subjects", "seed_of",
           "subjects_for"]
