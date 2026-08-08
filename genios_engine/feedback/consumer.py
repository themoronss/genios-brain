"""Layer 6 → lower layers — the typed learned-state consumer seam (Part 12 · P0).

Layer 6 publishes learned state; this is the ONLY safe way a lower layer reads it. Lower layers must
not import Layer 6's internals — they call ``snapshot`` and get an allowlisted, tenant-scoped,
ACL-filtered, version-current, TTL-honouring, fail-closed view. What each layer is *allowed* to read
is a fixed allowlist here; what a reviewer decides each layer should *trust* is layered on top by
the caller. Nothing here guesses: a missing or unauthorised value is absent, and the caller falls
back to its own deterministic default.

Enforced invariants:
  · tenant     — every query is bound to ``org_id``; path/args are never authority.
  · allowlist  — a consumer only sees the brains it is permitted (Context ≠ Delivery).
  · visibility — private/participant values need the viewer among the principals; else invisible.
  · version    — only the single active brain version (so a rollback is reflected immediately).
  · TTL        — a Runtime memory is read only while unexpired.
  · fail-closed— any ambiguity resolves to "no learned value", never a fabricated one.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import text

from genios_engine.contracts.learning import BrainTarget, VisibilityScope

#: What each lower-layer consumer is allowed to read. The mechanism is fixed; the per-field trust a
#: reviewer signs off (Part 12) is applied by the caller on top of this.
CONSUMER_ALLOWLIST: dict[str, frozenset[BrainTarget]] = {
    "context":   frozenset({BrainTarget.ORGANIZATION, BrainTarget.ADAPTIVE}),
    "reasoning": frozenset({BrainTarget.ORGANIZATION, BrainTarget.BEHAVIOR}),
    "executive": frozenset({BrainTarget.BEHAVIOR, BrainTarget.ADAPTIVE}),
    "delivery":  frozenset({BrainTarget.ADAPTIVE, BrainTarget.RUNTIME}),
}

_OPEN_SCOPES = {VisibilityScope.ORGANIZATION.value, VisibilityScope.PUBLIC.value}


@dataclass(frozen=True, slots=True)
class LearnedState:
    """A read-only snapshot of the learned values a consumer may use for one subject.

    ``brains`` maps brain name → value (active version only); ``runtime`` maps subject → value
    (unexpired leases only). Emptiness is the deterministic fallback — the caller uses its own
    default and never a guessed learned value.
    """

    org_id: str
    consumer: str
    subject: str
    brains: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)

    def brain(self, name: str) -> Any | None:
        return self.brains.get(name)

    @property
    def is_empty(self) -> bool:
        return not self.brains and not self.runtime


def _visible(scope: str, principals: list[str] | None, viewer_principals: set[str]) -> bool:
    """Org/public values are visible to any org member; narrower ones need the viewer in-principals."""
    if scope in _OPEN_SCOPES:
        return True
    return bool(set(principals or ()) & viewer_principals)


def snapshot(conn, *, org_id: str, consumer: str, subject: str, now: datetime,
             viewer_principals: set[str] | None = None) -> LearnedState:
    """Read the learned state a ``consumer`` may use for ``subject``. Fail-closed on every axis."""
    allowed = CONSUMER_ALLOWLIST.get(consumer)
    if allowed is None:
        return LearnedState(org_id=org_id, consumer=consumer, subject=subject)   # unknown consumer → nothing
    viewer = viewer_principals or set()

    brains: dict[str, Any] = {}
    brain_names = tuple(b.value for b in allowed if b is not BrainTarget.RUNTIME)
    if brain_names:
        rows = conn.execute(text(
            "select brain, value, visibility_scope, visibility from learned_brain_entries "
            "where org_id = :o and subject = :s and active and brain = any(:brains)"),
            {"o": org_id, "s": subject, "brains": list(brain_names)}).mappings().all()
        for r in rows:
            principals = (r["visibility"] or {}).get("principals") if isinstance(r["visibility"], dict) else None
            if _visible(r["visibility_scope"], principals, viewer):
                brains[r["brain"]] = r["value"]

    runtime: dict[str, Any] = {}
    if BrainTarget.RUNTIME in allowed:
        rows = conn.execute(text(
            "select subject, value, visibility_scope, visibility from temporary_memories "
            "where org_id = :o and subject = :s and active and expires_at > :now"),
            {"o": org_id, "s": subject, "now": now}).mappings().all()
        for r in rows:
            principals = (r["visibility"] or {}).get("principals") if isinstance(r["visibility"], dict) else None
            if _visible(r["visibility_scope"], principals, viewer):
                runtime[r["subject"]] = r["value"]

    return LearnedState(org_id=org_id, consumer=consumer, subject=subject,
                        brains=brains, runtime=runtime)


def may_consume(consumer: str, brain: BrainTarget) -> bool:
    """Is ``consumer`` allowed to read ``brain`` at all? The allowlist gate, for a caller to assert."""
    return brain in CONSUMER_ALLOWLIST.get(consumer, frozenset())


__all__ = ["CONSUMER_ALLOWLIST", "LearnedState", "may_consume", "snapshot"]
