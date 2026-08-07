# Architecture and schema ratchets

Topology tests allow Delivery to consume the Layer 5 execution seam while preventing it from importing Layer 6 feedback authority. Missing-module and SQL-reference scans catch stale imports/table references. Platform-auth and tenant-erasure tests protect organization isolation around shared operational data.

The selected ratchet set (`test_account_erasure.py`, `test_executive_store_schema.py`, `test_layer_topology.py`, `test_migrate.py`, `test_no_missing_module_deps.py`, `test_platform_auth.py`, `test_sql_references_real_tables.py`) completed with **59 passed** on 2026-08-07.

`test_delivery_control_plane.py` additionally checks that migration 0046 declares the expected tenant-scoped tables, composite foreign keys, logical uniqueness, execution lineage, claim shape, priorities and budget domain. These are text/source ratchets. `test_migrate.py` verifies the project's synthetic SQLite migration ledger, not execution of PostgreSQL DDL 0046 against real legacy data.

Adapter contracts keep channels substitutable and return typed outcomes; adapters do not gain routing, policy, attention-budget or execution-authority power.
