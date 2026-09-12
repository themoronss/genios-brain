"""A still-true signal is not retired just because nothing new happened.

The regeneration gate refuses to RE-EMIT a (rule, subject) whose evidence has not moved since the
last signal — re-saying it would repeat itself. It used to `continue` before the subject reached
`fired`, and lifecycle retirement resolves every open signal missing from `fired`. So on the very
next sweep a rule that still matched, about a subject that still needed action, had its open
signal resolved and its card expired: the card vanished because nothing had changed.

Real Postgres only (the lifecycle UPDATE is the behaviour under test); skips without
GENIOS_TEST_DATABASE_URL.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from genios_engine.packs.wiring import ensure_defaults, make_registry
from genios_engine.reason.runner import run_all

NOW = datetime(2026, 9, 10, 12, 0, tzinfo=timezone.utc)
ORG = "nne_keeps_signal"


def _seed_org(store) -> None:
    with store.engine.begin() as conn:
        reqd = conn.execute(text(
            "select column_name, data_type from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'")).all()
        cols, ph, vals = ["id"], [":id"], {"id": ORG}
        for r in reqd:
            cols.append(r.column_name)
            ph.append(f":{r.column_name}")
            dt = r.data_type
            vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                                   else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                                   else "o@x.test" if "email" in r.column_name else ORG)
        conn.execute(text(f"insert into orgs ({','.join(cols)}) values ({','.join(ph)}) "
                          "on conflict do nothing"), vals)


def _fresh_graph(store) -> None:
    """One person we owe a reply to: the ball is in our court and their last message is five
    days old. `unanswered_email` matches; nothing about them changes between the two sweeps."""
    from genios_engine.api.account_routes import _wipe

    stale = NOW - timedelta(days=5)
    with store.engine.begin() as conn:
        _wipe(conn, ORG)
        conn.execute(text("delete from signals where org_id=:o"), {"o": ORG})
        # The publication watermark outlives `/reset`; a previous run of this file left it at
        # NOW+6h, and a sweep evaluated before the watermark is refused as stale.
        conn.execute(text("delete from reasoning_publication_watermarks where org_id=:o"),
                     {"o": ORG})
        conn.execute(text(
            "insert into graph_nodes (node_id, org_id, node_type, display_name, canonical_key) "
            "values ('nne_p1', :o, 'person', 'Ada Buyer', 'ada@acme.test')"), {"o": ORG})
        for i, (field, value) in enumerate((("thread.ball_in_court", "us"),
                                            ("thread.last_inbound", stale.isoformat()))):
            conn.execute(text(
                "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, "
                "field, value, value_type, status, occurred_at) values "
                "(:fv, :f, :o, 'nne_p1', :field, cast(:v as jsonb), 'string', 'active', :t)"),
                {"fv": f"nne_fv{i}", "f": f"nne_f{i}", "o": ORG, "field": field,
                 "v": json.dumps(value), "t": stale})


def _open_signals(store, rule_id: str) -> list[str]:
    with store.engine.connect() as conn:
        return [r.status for r in conn.execute(text(
            "select status from signals where org_id=:o and rule_id=:r and "
            "subject_node_id='nne_p1'"), {"o": ORG, "r": rule_id})]


def test_a_matched_subject_with_no_new_evidence_keeps_its_open_signal(pg_store):
    _seed_org(pg_store)
    _fresh_graph(pg_store)
    registry = make_registry(pg_store.engine.url.render_as_string(hide_password=False))
    ensure_defaults(registry, ORG)

    first = run_all(org_id=ORG, store=pg_store, eval_time=NOW, registry=registry)
    assert _open_signals(pg_store, "unanswered_email") == ["open"], first

    # The next sweep: same facts, nothing new since the signal. It must not re-emit, and it must
    # not retire the signal either — the rule still matches and the reply is still owed.
    second = run_all(org_id=ORG, store=pg_store, eval_time=NOW + timedelta(hours=6),
                     registry=registry)
    assert second["outcomes"].get("no_new_evidence", 0) >= 1, second
    assert second["outcomes"].get("resolved", 0) == 0, second
    assert _open_signals(pg_store, "unanswered_email") == ["open"], second
