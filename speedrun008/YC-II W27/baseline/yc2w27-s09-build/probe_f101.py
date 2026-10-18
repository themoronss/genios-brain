"""Probe: does a rebuild file a NEWSLETTER the drain kept out of every file? (no brief at all)"""
import os, sys
sys.path.insert(0, os.getcwd())
from genios_engine.context.backfill import backfill_correlations
from genios_engine.context.graph_store import GraphStore
import tests.context.workstream_world as W
store = GraphStore("postgresql+psycopg://postgres:scratch@127.0.0.1:55432/genios_test")
ORG = "org_s09_probe_rebuild_noise"
W.tenant(store, ORG)
try:
    real = W.extraction
    def newsletter(mentions=(), _noise="none"):
        ex = real(mentions); ex.noise_type = "newsletter"; return ex
    W.extraction = newsletter
    W.process(store, ORG, event_id="e_news", sender="editor@letters.test", thread="t_news",
              company_brief=None)
    W.extraction = real
    print("live:", sorted(W.anchors(store, ORG, "e_news")))
    out = backfill_correlations(store, ORG)            # the incremental pass every drain runs
    print("incremental backfill:", out, sorted(W.anchors(store, ORG, "e_news")))
    backfill_correlations(store, ORG, rebuild=True)
    print("rebuilt:", sorted(W.anchors(store, ORG, "e_news")))
finally:
    W.reset(store, ORG)
