"""`06` D33 · how long a file may go quiet, by its kind of work — the reader context cannot own.

A file's counterparty is named by an in-motion line of the company brief, with its kind of work
(`contracts/company_brief.WORK_KINDS`, `06` D31); the kind's playbook carries a stop rule
(`packs/compiler/playbook_reader`, STEP-11: investor 90 days, program 90 — practitioner judgement and
Hub71's three months, each labelled; the others with M31). Context correlates and ages files, and
may read neither the brief's kinds nor the playbooks (`tests/test_layer_topology.py`), so this module
— the composition root's, which may read anything — answers the days for an anchor node and
`install()` hands that reader down (`context/correlation.use_quiet_days`).

None means: no in-motion line names this counterparty, or its kind has no stop rule yet — and the
domain's clock, then the engine's 45 days, decide, as they did before D33 reached the code.
"""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy import text

_NODE = text("select node_type, canonical_key from graph_nodes "
             " where org_id = :o and node_id = :n and valid_to is null limit 1")


@lru_cache(maxsize=None)
def stop_days(kind: str) -> int | None:
    """The kind's playbook stop rule in days, or None — no playbook, or one with no stop rule."""
    from genios_engine.packs.compiler.playbook_reader import playbook_for
    playbook = playbook_for(kind).playbook
    stop = playbook.stop if playbook is not None else None
    after = stop.dormant_after if stop is not None else None
    return int(after.value) if after is not None and after.value else None


def quiet_days(conn, org_id: str, node_id: str) -> int | None:
    """The quiet window of the file anchored on `node_id`, by the kind of work its brief line names."""
    from genios_engine.context.workstreams import _anchor_domain, _work_kind, _work_lines
    from genios_engine.platform.company_brief import brief_for

    work = _work_lines(brief_for(conn, org_id))
    if not work:
        return None
    row = conn.execute(_NODE, {"o": org_id, "n": node_id}).first()
    if row is None or not row.canonical_key:
        return None
    key = str(row.canonical_key).strip().lower()
    kind = _work_kind(work, {key} if "@" in key else set(), _anchor_domain(key))
    return stop_days(kind) if kind else None


def install() -> None:
    """Hand the reader down to context — called once by `platform/wiring` at import."""
    from genios_engine.context.correlation import use_quiet_days
    use_quiet_days(quiet_days)


__all__ = ["install", "quiet_days", "stop_days"]
