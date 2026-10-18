"""Probe: a connector's NEWSLETTER that names a person it introduced — a nudge? filed by a rebuild?"""
import os, sys
sys.path.insert(0, os.getcwd())
from sqlalchemy import text
from genios_engine.context.backfill import backfill_correlations
from genios_engine.context.graph_store import GraphStore
from genios_engine.platform import company_brief, company_brief_store
import tests.context.workstream_world as W
store = GraphStore("postgresql+psycopg://postgres:scratch@127.0.0.1:55432/genios_test")
ORG = "org_s09_probe_noise_nudge"
W.tenant(store, ORG)
try:
    with store.engine.begin() as c:
        company_brief_store.add(c, org_id=ORG, section="connectors", address=W.CONNECTOR,
                                words="Introly", decided_by="probe", at=W.T0)
    b = company_brief.current(store, ORG)
    W.process(store, ORG, event_id="e_intro", sender=W.CONNECTOR, recipients=(W.FOUNDER, "rahul@kestrelcap.test"),
              thread="t_intro", headers=W.UNSUBSCRIBE, mentions=(W.mention("Rahul Menon"),), company_brief=b)
    real = W.extraction
    def newsletter(mentions=(), _noise="none"):
        ex = real(mentions); ex.noise_type = "newsletter"; return ex
    W.extraction = newsletter
    W.process(store, ORG, event_id="e_digest", sender=W.CONNECTOR, thread="t_digest", headers=W.UNSUBSCRIBE,
              mentions=(W.mention("Rahul"),), company_brief=b, at=W.later(2))
    W.extraction = real
    with store.engine.connect() as c:
        pres = c.execute(text("select count(*) from graph_observations where org_id=:o and created_by_event_id='e_digest' "
                              "and kind like 'event_presence%'"), {"o": ORG}).scalar()
        kinds = [r.kind for r in c.execute(text("select kind from graph_observations where org_id=:o and created_by_event_id='e_digest'"), {"o": ORG})]
    print("live: digest anchors", sorted(W.anchors(store, ORG, "e_digest")), "| observations", kinds)
    backfill_correlations(store, ORG, rebuild=True)
    print("rebuilt: digest anchors", sorted(W.anchors(store, ORG, "e_digest")))
finally:
    W.reset(store, ORG); company_brief.invalidate(ORG)
