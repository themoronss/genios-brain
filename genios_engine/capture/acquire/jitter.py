"""L1.2.6-U2 · Deterministic per-connection jitter.

Without jitter every connection of every tenant fires on the same interval boundary: thirty orgs
wake at 00:00, hit the same provider with thirty list calls in the same second, and queue behind
each other on our own workers. The fix is to spread each connection to its own point inside the
interval — but HOW that point is chosen decides whether the schedule can be operated at all.

`random.random()` would spread the herd and destroy everything else. A schedule that redraws its
offset on every restart cannot be predicted ("when does this connection next poll?" has no
answer), cannot be reproduced when a tenant reports a missed sync, and cannot be asserted on in a
test. So the offset is a pure function of a stable key — org, connection, source — and of nothing
else: same key, same offset, in this process, in the next restart, and in a different machine's
Python. `hash()` is not that function; it is salted per process by PYTHONHASHSEED, which is
precisely the unreproducibility this unit exists to avoid. blake2b is stable forever.

Integer basis points throughout — the offset is a whole number of seconds, so the same key gives
byte-identical instants rather than two floats that differ in the last place.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

#: +/- 10%, as basis points of the interval. Wide enough to smear a herd across 3 minutes of a
#: 15-minute cadence; narrow enough that a "15 minute" cadence still means roughly 15 minutes.
DEFAULT_SPREAD_BP = 1000
#: One whole in basis points — the same base every bp figure in Layer 1 divides by. Public so a
#: composing unit (the tick grace in `scheduler.py`) converts a spread to seconds against THIS
#: number rather than retyping 10_000 and drifting from it.
BP_FULL = 10_000
_BP = BP_FULL


@dataclass(frozen=True)
class JitterKey:
    """The stable identity a connection's offset is derived from.

    Source is part of the key as well as connection: one Composio connection can back gmail and
    gcal, and if both derived the same offset the two heaviest calls of that tenant would land on
    the same second — a herd of two, which is exactly what we are removing.
    """
    org_id: str
    connection_id: str
    source: str = ""

    def digest_key(self) -> str:
        # "|" separated with the field order fixed: concatenating without a separator would make
        # ("ab","c") and ("a","bc") the same connection as far as the hash is concerned.
        return f"{self.org_id}|{self.connection_id}|{self.source}"


@dataclass(frozen=True)
class JitterOffset:
    """A signed shift of the interval boundary, in seconds and in basis points of the interval."""
    offset_seconds: int
    fraction_bp: int              # signed, within +/- spread_bp


def jitter_offset(key: JitterKey, *, interval_seconds: int,
                  spread_bp: int = DEFAULT_SPREAD_BP) -> JitterOffset:
    """Deterministic +/- `spread_bp` jitter for one connection — U2's public unit.

    Uniform over the odd-sized range `[-spread_bp, +spread_bp]` by taking the digest modulo the
    range width; the 8-byte digest is ~10^19 wide against a range of ~2001, so the modulo bias is
    below one part in 10^15 and nothing about the spread depends on it.
    """
    if interval_seconds <= 0:
        raise ValueError(f"interval_seconds must be positive, got {interval_seconds}")
    if not 0 <= spread_bp < _BP:
        raise ValueError(f"spread_bp must be within [0, {_BP}), got {spread_bp}")
    if spread_bp == 0:
        return JitterOffset(0, 0)
    digest = hashlib.blake2b(key.digest_key().encode("utf-8"), digest_size=8).digest()
    fraction_bp = int.from_bytes(digest, "big") % (2 * spread_bp + 1) - spread_bp
    # Integer bp arithmetic, truncating toward zero on both signs so +f and -f are symmetric —
    # floor division would push every negative offset one second further out.
    magnitude = interval_seconds * abs(fraction_bp) // _BP
    return JitterOffset(magnitude if fraction_bp >= 0 else -magnitude, fraction_bp)
