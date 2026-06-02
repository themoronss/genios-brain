"""HTTP API layer — FastAPI routers wrapping the engine.

This is the public surface that frontend + customer integrations talk to.
The brain's internal modules expose pure Python APIs; this package adapts
them to REST + a thin MCP-over-HTTP transport.

Routers:
- auth          API-key middleware (org_id resolution)
- intelligence  query / explain / feedback / graph_view  (wraps MCP tools)
- metrics       intervention_rate / calibration / roi / resolution
- usermodel     persona CRUD + propose-confirm + delete
- mapping       custom-source mapping propose + confirm
- ingestion     /v1/ingest for customer-deployed memory adapters
- audit         read-only audit log query
- health        DB / Redis / LLM deep probes

Each router is mounted at /v1/ in core/main.py.
"""
