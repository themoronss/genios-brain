"""END-TO-END no-gap verification: one signal-rich email → L2 extraction → graph (nodes/obs/facts)
→ L3 reasoning (signals). Real LLM (a few Haiku calls). Runs on a scratch org, wiped clean first,
so it never touches real data. Prints a PASS/GAP report per stage.

Usage:  python -m scripts.e2e_verify
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text

from genios_engine.context.pipeline import norm_obs_kind, process_event
from genios_engine.platform.wiring import make_graph_store, make_llm_client
from genios_engine.reason.runner import run_all

ORG = "org_e2e_verify"
US = "founder@genios.in"
PROSPECT = "priya@chat360.io"

# One inbound email deliberately packed with distinct sales signals to exercise the corpus + the
# obs-kind normalizer + node discipline in a single pass.
EMAIL = (
    "Hi, we're excited to move forward — the budget is approved on our side. "
    "Can you send over the contract / order form to get started? "
    "One concern: your pricing is higher than Acme, the other vendor we're evaluating. "
    "Also, our legal team will need to review the MSA before we sign. "
    "SAP integration and our AWS S3 setup should be fine. Let's aim to wrap this up this quarter."
)

_GRAPH_TABLES = ["graph_source_refs", "graph_facts", "graph_observations", "graph_edges",
                 "discrepancies", "graph_change_outbox", "graph_nodes", "graph_versions",
                 "signals", "signal_suppression_log"]


def _wipe(store):
    with store.engine.begin() as c:
        for t in _GRAPH_TABLES:
            try:
                c.execute(text(f"delete from {t} where org_id=:o"), {"o": ORG})
            except Exception:      # noqa: BLE001 — table may not exist in this schema
                pass
        c.execute(text("delete from l2_extraction_results where org_id=:o"), {"o": ORG})


def _check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'GAP '}] {label}" + (f"  · {detail}" if detail else ""))
    return ok


def main() -> None:
    store, llm = make_graph_store(), make_llm_client()
    if llm is None:
        print("no LLM configured — cannot run the real extraction test"); return
    now = datetime.now(timezone.utc)
    print(f"== E2E verify on scratch org {ORG} (wiped first) ==")
    _wipe(store)

    # ---- L2: extraction → graph ------------------------------------------------------------
    res = process_event(org_id=ORG, event_id="evt_e2e_1", source="gmail", content=EMAIL,
                        sender_email=PROSPECT, recipient_emails=[US], occurred_at=now,
                        llm=llm, store=store, is_inbound=True, internal_emails=frozenset({US}))
    print(f"\n-- L2 extraction --  outcome={res.outcome} relevance={res.relevance} "
          f"nodes={res.nodes} facts={res.facts} obs={res.observations}")

    with store.engine.connect() as c:
        nodes = c.execute(text("select node_type, display_name, canonical_key from graph_nodes "
                               "where org_id=:o and valid_to is null"), {"o": ORG}).fetchall()
        obs = [r.kind for r in c.execute(text("select kind from graph_observations where org_id=:o "
                                              "and status='active'"), {"o": ORG})]
        facts = {r.field for r in c.execute(text("select field from graph_facts where org_id=:o "
                                                 "and valid_to is null and status='active'"), {"o": ORG})}

    node_types = sorted({n.node_type for n in nodes})
    from genios_engine.context.pipeline import _NODE_TYPES
    bad_types = [t for t in node_types if t not in _NODE_TYPES]
    orphan_mention_nodes = [n.display_name for n in nodes
                            if n.node_type in ("company", "product", "system") and n.canonical_key is None]

    print("\n-- STAGE CHECKS --")
    _check("extraction ran (committed, relevance>0)", res.outcome == "committed" and res.relevance > 0,
           f"relevance={res.relevance}")
    _check("sender became an anchored person node", any(
        n.node_type == "person" and (n.canonical_key or "") == PROSPECT for n in nodes),
           f"nodes={[(n.node_type, n.display_name) for n in nodes]}")
    _check("node-type whitelist held (no invented types)", not bad_types,
           f"bad={bad_types}" if bad_types else "only person/company/deal/…")
    _check("mentions NOT promoted to orphan nodes (SAP/S3 → observations)", not orphan_mention_nodes,
           f"leaked={orphan_mention_nodes}" if orphan_mention_nodes else "clean")
    canon_obs = sorted(set(obs))
    _check("observations extracted", len(obs) > 0, f"kinds={canon_obs}")
    from genios_engine.context.pipeline import _OBS_CANON
    non_canon = [o for o in canon_obs if not o.startswith("mention:") and o not in set(_OBS_CANON.values())
                 and o not in ("email_relevance", "note")]
    _check("obs kinds are canonical (normalizer applied)", not non_canon,
           f"non-canonical={non_canon}" if non_canon else f"canonical={[o for o in canon_obs if not o.startswith('mention:')]}")
    _check("thread state facts written (last_inbound + ball_in_court)",
           "thread.last_inbound" in facts and "thread.ball_in_court" in facts, f"facts={sorted(facts)}")

    # ---- L3: reasoning → signals -----------------------------------------------------------
    l3 = run_all(org_id=ORG, store=store, eval_time=now)
    with store.engine.connect() as c:
        fired = [r.reason_code for r in c.execute(text(
            "select reason_code from signals where org_id=:o and status='open'"), {"o": ORG})]
        suppressed = c.execute(text("select count(*) from signal_suppression_log where org_id=:o"),
                               {"o": ORG}).scalar() or 0
    print(f"\n-- L3 reasoning --  packs={l3['packs']} outcomes={l3['outcomes']}")
    _check("L3 evaluated without error", "error" not in str(l3["outcomes"]))
    _check("deep sales rules FIRED on the extracted signals", len(fired) > 0,
           f"fired={sorted(set(fired))} · suppressed={suppressed}")

    print("\n== summary ==")
    print(f"  nodes={len(nodes)} obs={len(obs)} facts={len(facts)} signals_fired={len(fired)}")
    print(f"  node types: {node_types}")
    print(f"  observations: {canon_obs}")
    print(f"  signals: {sorted(set(fired))}")


if __name__ == "__main__":
    main()
