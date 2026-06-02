"""Cross-cutting foundations — config, db, encryption, audit, telemetry, metrics.

Every other module imports from here. No module imports another module's internals.

Modules:
- config         tunables + settings
- db             SQLAlchemy engine + session
- encryption     Fernet wrapper for at-rest secrets
- audit          immutable audit log writer
- telemetry      structured logging + Sentry
- metrics_store  SQLAlchemy models for audit_log + intervention/calibration/roi/resolution rollups
- intervention_rate  THE North Star metric (per org/module/day)
- calibration    ECE/Brier per confidence bucket
- roi            value vs cost tracking + resolution-rate (engine health)
- soc2_gdpr      data subject access + erasure + retention sweep
- scope_check    end-to-end scope audit (decisions -> facts)
- health_check   DB/Redis/LLM probes
- worker_invariant  AST-walk catching module-level mutables (CI test)
"""
