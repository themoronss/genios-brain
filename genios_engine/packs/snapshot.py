from __future__ import annotations

import hashlib
import json

# D4 Snapshot Hasher — canonical JSON (sorted keys, no whitespace) → sha256 → snapshot_id.
# Idempotent: same content → same id. Key reorder / whitespace never change the hash; any
# single value change does. This is the truth of record stamped on every signal (Law 6).


def canonical(cfg: dict) -> str:
    return json.dumps(cfg, sort_keys=True, separators=(",", ":"), default=str)


def snapshot_id(cfg: dict) -> str:
    return "cfg_" + hashlib.sha256(canonical(cfg).encode("utf-8")).hexdigest()[:16]
