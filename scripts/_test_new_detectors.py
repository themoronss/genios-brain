#!/usr/bin/env python3
"""
Direct invocation test for new detectors against production data.
No celery, no proactive_scanner — just call the detector functions and
print what they would generate.

Verifies:
  - inbound_ack._detect_unacknowledged_inbound
  - change_point._detect_engagement_change_point
  - campaigns._detect_active_outbound_campaign

If any throws, we see it. If they return rows, deploy issue is just
that proactive_scanner hasn't run since deploy (will fire next cycle).
"""
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Force the gating env vars on so we test the actual logic, not the gate
os.environ["GENIOS_CAMPAIGN_DETECTORS_ENABLED"] = "true"
os.environ["GENIOS_RELATED_OUTBOUND_ENABLED"] = "true"

from app.database import SessionLocal
from app.graph.detectors.inbound_ack import _detect_unacknowledged_inbound
from app.graph.detectors.change_point import _detect_engagement_change_point
from app.graph.detectors.campaigns import _detect_active_outbound_campaign

ORG_ID = "0031178b-2f9d-4881-88d7-b39218292077"


def show_detector(name, fn):
    print(f"\n{'='*70}\n  {name}\n{'='*70}")
    db = SessionLocal()
    try:
        try:
            results = fn(db, ORG_ID)
        except Exception as e:
            print(f"  ❌ EXCEPTION: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return
        if not results:
            print("  → 0 candidates (criteria not met by current data)")
            return
        print(f"  → {len(results)} candidate(s):\n")
        for r in results[:3]:
            print(f"  • [{r['priority']}] {r['title']}")
            print(f"    detail: {r['detail'][:150]}")
            if r.get('metadata'):
                print(f"    meta:   {r['metadata']}")
            print()
        if len(results) > 3:
            print(f"  ... and {len(results) - 3} more")
    finally:
        db.close()


def main():
    print("Direct detector test — production DB, Rohit's org")
    show_detector("inbound_ack._detect_unacknowledged_inbound", _detect_unacknowledged_inbound)
    show_detector("change_point._detect_engagement_change_point", _detect_engagement_change_point)
    show_detector("campaigns._detect_active_outbound_campaign", _detect_active_outbound_campaign)


if __name__ == "__main__":
    main()
