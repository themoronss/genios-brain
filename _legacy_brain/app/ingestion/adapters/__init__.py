"""Adapter shims kept after the g-i-1 v2 migration.

The full v1 adapter pipeline was deleted (heavy email_parser, classifier,
etc.). What remains here is a thin Inkbox API client used by
`workspace_integrations.py` to register/deregister webhooks and discover
phone numbers — Inkbox is a real GeniOS client per memory; the OAuth/webhook
plumbing has no v2-side equivalent yet.
"""
