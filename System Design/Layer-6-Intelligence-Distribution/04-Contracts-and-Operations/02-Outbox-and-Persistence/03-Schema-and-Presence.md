# Schema and presence

Migration 0042 adds delivery preferences/gate materialization. Migration 0044 adds tenant-scoped
expiring presence leases and Atlas delivery fields/indexes.

Leases make stale clients self-expiring. Live PostgreSQL migration/contention proof remains part of
deployment, not local unit-test evidence.
