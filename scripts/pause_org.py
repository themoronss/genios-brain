"""Pause / resume ONE org's processing (feature_flags kill_switch:{org}).

Wiping an org while the in-process scheduler is live is a race the wipe always loses: the sweep
fires 45s after every restart (`scheduler_enabled`, `sync_initial_delay_seconds`) and repopulates
the graph mid-delete. Pause first, wipe, then resume — that ordering is the whole point of this.

    python scripts/pause_org.py org_xxx --pause
    python scripts/pause_org.py org_xxx --resume
"""
from __future__ import annotations

import os
import sys

from sqlalchemy import text

from genios_engine.platform.db import get_engine


def main() -> int:
    if len(sys.argv) < 3 or sys.argv[2] not in ("--pause", "--resume"):
        print(__doc__)
        return 2
    org, want_live = sys.argv[1], sys.argv[2] == "--resume"
    e = get_engine(os.environ["GENIOS_DATABASE_URL"])
    with e.connect() as c, c.begin():
        c.execute(text("insert into feature_flags (key, enabled) values (:k, :e) "
                       "on conflict (key) do update set enabled = :e"),
                  {"k": f"kill_switch:{org}", "e": want_live})
    print(f"{org} -> {'RESUMED' if want_live else 'PAUSED'}")
    if not want_live:
        print("Cached for up to 30s (_ORG_KILL_TTL) before every request 503s.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
