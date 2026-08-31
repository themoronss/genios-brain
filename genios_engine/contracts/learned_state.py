"""The learned-state consumption contract — who may read which brain, fail-closed.

This lived in `feedback/consumer.py`, whose docstring called it "the ONLY safe way a lower
layer reads" learned state — and no lower layer ever imported it, because none legally COULD:
the layer topology forbids an upward import, and feedback is layer 7. A consumption contract
that only the producing layer may import is a decoy seam; the vocabulary belongs here in
`contracts/`, which every layer may read. `feedback/consumer.py` re-exports for compatibility.

The persistence boundary stays the TABLES (`learned_brain_entries`, `temporary_memories`) —
same pattern as `packs/compiler/runtime_brains.py`, the one pre-existing reader.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.learning import BrainTarget, VisibilityScope

#: Which brains each consuming layer may read. Absence means nothing — an unknown consumer
#: gets an empty state, never an error, because fail-closed here means "no learned influence",
#: not "no decision".
CONSUMER_ALLOWLIST: dict[str, frozenset[BrainTarget]] = {
    "context":   frozenset({BrainTarget.ORGANIZATION, BrainTarget.ADAPTIVE}),
    "reasoning": frozenset({BrainTarget.ORGANIZATION, BrainTarget.BEHAVIOR}),
    "executive": frozenset({BrainTarget.BEHAVIOR, BrainTarget.ADAPTIVE}),
    "delivery":  frozenset({BrainTarget.ADAPTIVE, BrainTarget.RUNTIME}),
}

_OPEN_SCOPES = {VisibilityScope.ORGANIZATION.value, VisibilityScope.PUBLIC.value}


def _visible(scope: str | None, principals, viewer: set[str]) -> bool:
    """Open scopes pass; constrained scopes need a principal intersection; unknown fails closed."""
    if scope in _OPEN_SCOPES:
        return True
    if scope in (VisibilityScope.PRIVATE.value, VisibilityScope.PARTICIPANTS.value):
        return bool(viewer & {str(p).strip().lower() for p in (principals or ())})
    return False


@dataclass(frozen=True, slots=True)
class LearnedState:
    """A read-only snapshot of the learned values a consumer may use for one subject."""

    org_id: str
    consumer: str
    subject: str
    brains: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)

    def brain(self, name: str) -> Any | None:
        """One brain's value, or None — reading a brain outside the allowlist is not an error,
        it is an absence, because fail-closed means "no learned influence", not "no decision"."""
        return self.brains.get(name)

    @property
    def is_empty(self) -> bool:
        return not self.brains and not self.runtime


def snapshot(conn, *, org_id: str, consumer: str, subject: str, now: datetime,
             viewer_principals: set[str] | None = None) -> LearnedState:
    """Read the learned state a ``consumer`` may use for ``subject``. Fail-closed on every axis."""
    allowed = CONSUMER_ALLOWLIST.get(consumer)
    if allowed is None:
        return LearnedState(org_id=org_id, consumer=consumer, subject=subject)
    viewer = viewer_principals or set()

    brains: dict[str, Any] = {}
    brain_names = tuple(b.value for b in allowed if b is not BrainTarget.RUNTIME)
    if brain_names:
        rows = conn.execute(text(
            "select brain, value, visibility_scope, visibility from learned_brain_entries "
            "where org_id = :o and subject = :s and active and brain = any(:brains)"),
            {"o": org_id, "s": subject, "brains": list(brain_names)}).mappings().all()
        for r in rows:
            principals = (r["visibility"] or {}).get("principals")                 if isinstance(r["visibility"], dict) else None
            if _visible(r["visibility_scope"], principals, viewer):
                brains[r["brain"]] = r["value"]

    runtime: dict[str, Any] = {}
    if BrainTarget.RUNTIME in allowed:
        rows = conn.execute(text(
            "select subject, value, visibility_scope, visibility from temporary_memories "
            "where org_id = :o and subject = :s and active and expires_at > :now"),
            {"o": org_id, "s": subject, "now": now}).mappings().all()
        for r in rows:
            principals = (r["visibility"] or {}).get("principals")                 if isinstance(r["visibility"], dict) else None
            if _visible(r["visibility_scope"], principals, viewer):
                runtime[r["subject"]] = r["value"]

    return LearnedState(org_id=org_id, consumer=consumer, subject=subject,
                        brains=brains, runtime=runtime)


def snapshot_all(conn, *, org_id: str, consumer: str, now: datetime,
                 viewer_principals: set[str] | None = None) -> dict[str, dict[str, Any]]:
    """Every active learned value this consumer may read, grouped brain → {subject: value}.

    The per-subject ``snapshot`` is the right read for a caller that knows what it is asking
    about; the live reasoning sweep does not — it needs the org's whole learned state ONCE per
    sweep, not one query per node. Same allowlist, same visibility fail-closed rules, one query.
    """
    del now  # symmetry with snapshot(); brain entries carry no expiry (Runtime leases do)
    allowed = CONSUMER_ALLOWLIST.get(consumer)
    if allowed is None:
        return {}
    viewer = viewer_principals or set()
    brain_names = tuple(b.value for b in allowed if b is not BrainTarget.RUNTIME)
    if not brain_names:
        return {}
    out: dict[str, dict[str, Any]] = {}
    rows = conn.execute(text(
        "select brain, subject, value, visibility_scope, visibility from learned_brain_entries "
        "where org_id = :o and active and brain = any(:brains) order by brain, subject"),
        {"o": org_id, "brains": list(brain_names)}).mappings().all()
    for r in rows:
        principals = (r["visibility"] or {}).get("principals")             if isinstance(r["visibility"], dict) else None
        if _visible(r["visibility_scope"], principals, viewer):
            out.setdefault(r["brain"], {})[r["subject"]] = r["value"]
    return out


def may_consume(consumer: str, brain: BrainTarget) -> bool:
    return brain in CONSUMER_ALLOWLIST.get(consumer, frozenset())


__all__ = ["CONSUMER_ALLOWLIST", "LearnedState", "may_consume", "snapshot", "snapshot_all"]
