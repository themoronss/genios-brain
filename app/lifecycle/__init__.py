"""Fact lifecycle state machine (Phase 4.5).

Valid states:  ingest → validate → live ↔ fade → dormant → archive

Transitions are driven by two schedules:
  - hourly: freshness recompute, promote validate→live, demote live→fade
  - nightly: fade→dormant (14d), dormant→archive (30d unless corroborated)
"""
from app.lifecycle.machine import run_hourly, run_nightly

__all__ = ["run_hourly", "run_nightly"]
