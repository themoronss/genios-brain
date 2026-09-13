"""The team post-pass (registered in `postpass.PASSES`): P-10/P-11 deadline-at-risk + P-12 readiness.

One read connection builds the TeamContext (directory, commitments, windows — a handful of
statements), then each situation is emitted in its own transaction, so one bad situation never
blocks the rest. Returns how many situations were (re-)emitted; an unchanged rerun returns 0.
"""
from __future__ import annotations

from datetime import datetime

from genios_engine.platform.logging import get_logger
from genios_engine.reason.team import away, readiness
from genios_engine.reason.team.common import TeamContext
from genios_engine.reason.team.emit import close_stale, emit_situation

_log = get_logger("genios.team.passes")
#: The team situations THIS pass owns (and may close). Verify situations are group B's.
_OWNED_PREFIXES = ("deadline_at_risk:", "readiness:")


def run(engine, card_store, org_id: str, *, now: datetime) -> int:
    with engine.connect() as c:
        ctx = TeamContext.load(c, org_id, now=now)
        situations = [*away.deadline_situations(c, ctx), *readiness.situations(c, ctx)]
    emitted = 0
    for s in situations:
        try:
            if emit_situation(engine, card_store, org_id, kind="team", key=s.key,
                              seat_id=s.seat_id, subject_node_ids=s.subject_node_ids,
                              headline=s.headline, body=s.body, actions=list(s.actions),
                              evidence=list(s.evidence), priority=s.priority,
                              ttl_seconds=s.ttl_seconds, digest=s.digest,
                              capability_id=s.capability_id, now=now,
                              expires_at=s.expires_at) is not None:
                emitted += 1
        except Exception:      # noqa: BLE001 — one situation never blocks the rest
            _log.exception("team situation %s failed for org_id=%s", s.key, org_id)
    try:
        close_stale(engine, org_id, kind="team", prefixes=_OWNED_PREFIXES,
                    keep_keys={s.key for s in situations}, now=now)
    except Exception:          # noqa: BLE001 — a stale card is a nuisance, never a failed pass
        _log.exception("closing stale team situations failed for org_id=%s", org_id)
    return emitted


__all__ = ["run"]
