"""Probe: does a rebuild keep a company the mail named in prose (resolved to a known node)?"""
import os, sys
from pathlib import Path
sys.path.insert(0, os.getcwd())               # run from the repository root
from genios_engine.context.graph_store import GraphStore
from genios_engine.context.backfill import backfill_correlations
from tests.context.workstream_world import (FOUNDER, anchors, brief, later, mention, process, reset, tenant)
store = GraphStore("postgresql+psycopg://postgres:scratch@127.0.0.1:55432/genios_test")
ORG = "org_s09_probe_f98"
tenant(store, ORG)
try:
    process(store, ORG, event_id="e_vc", sender="rahul@kestrelcap.test", thread="t_vc", company_brief=None)
    process(store, ORG, event_id="e_mention", sender="priya@northwind.test", thread="t_n",
            mentions=(mention("Kestrelcap", "organization"),), company_brief=None, at=later(1))
    live = anchors(store, ORG, "e_mention")
    backfill_correlations(store, ORG, rebuild=True)
    rebuilt = anchors(store, ORG, "e_mention")
    print("live:", sorted(live), "| rebuilt:", sorted(rebuilt), "| differ:", live != rebuilt)
finally:
    reset(store, ORG)
