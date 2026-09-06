"""L1.2.6-U2 · deterministic jitter.

Two properties, and the unit is worthless without either one.

DETERMINISM is asserted across a real subprocess, not just twice in this interpreter. The
tempting implementation is `hash(connection_id) % spread`, which passes an in-process repeat test
and then returns a different offset on every deploy, because CPython salts `hash()` per process
with PYTHONHASHSEED. The subprocess here runs with an explicitly hostile seed for exactly that
reason: it is the only assertion that can tell a stable digest from a per-process one.

SPREAD is asserted over a population. A "deterministic" jitter that returns the same offset for
every key is perfectly reproducible and does nothing at all — the thundering herd stays a herd.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from genios_engine.capture.acquire.jitter import (
    DEFAULT_SPREAD_BP,
    JitterKey,
    jitter_offset,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
INTERVAL = 15 * 60          # gmail's cadence, so the numbers below are the real ones


def test_same_key_gives_the_same_offset():
    key = JitterKey("org_7173", "con_abc", "gmail")
    first = jitter_offset(key, interval_seconds=INTERVAL)
    assert all(jitter_offset(key, interval_seconds=INTERVAL) == first for _ in range(5))
    # equal-by-value keys are the same connection, not two
    assert jitter_offset(JitterKey("org_7173", "con_abc", "gmail"),
                         interval_seconds=INTERVAL) == first


def test_offset_is_stable_across_processes_and_hash_seeds():
    """The assertion `hash()` cannot pass. Two child interpreters, two different PYTHONHASHSEEDs,
    and the same three offsets as this process computed."""
    keys = [("org_7173", "con_abc", "gmail"), ("org_7173", "con_abc", "gcal"),
            ("org_other", "con_zzz", "notion")]
    expected = [jitter_offset(JitterKey(*k), interval_seconds=INTERVAL).offset_seconds
                for k in keys]
    script = (
        "import json,sys;"
        "from genios_engine.capture.acquire.jitter import JitterKey, jitter_offset;"
        f"ks={keys!r};"
        f"print(json.dumps([jitter_offset(JitterKey(*k), interval_seconds={INTERVAL})"
        ".offset_seconds for k in ks]))"
    )
    got = []
    for seed in ("0", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        out = subprocess.run([sys.executable, "-c", script], cwd=REPO_ROOT, env=env,
                             capture_output=True, text=True, check=True)
        got.append([int(v) for v in json.loads(out.stdout)])
    assert got[0] == expected, "offset changed across processes — the seed is not stable"
    assert got[1] == expected, "offset moved with PYTHONHASHSEED — hash() is not a jitter seed"


def test_different_keys_land_on_different_offsets():
    offsets = [jitter_offset(JitterKey("org_a", f"con_{i}", "gmail"),
                             interval_seconds=INTERVAL).offset_seconds
               for i in range(500)]
    distinct = set(offsets)
    # +/-10% of 900s is a 181-second window, so 500 connections cannot all be distinct — but a
    # herd is what happens when they collapse onto a handful of instants.
    assert len(distinct) > 100, f"only {len(distinct)} distinct offsets — connections still herd"
    assert max(offsets) > 0 and min(offsets) < 0, "jitter must pull both earlier and later"
    # no single instant may take more than a small share of the population
    worst = max(offsets.count(o) for o in distinct)
    assert worst < len(offsets) // 10


@pytest.mark.parametrize("a,b", [
    (JitterKey("org_a", "con_1", "gmail"), JitterKey("org_a", "con_1", "gcal")),
    (JitterKey("org_a", "con_1", "gmail"), JitterKey("org_b", "con_1", "gmail")),
    (JitterKey("org_a", "con_1", "gmail"), JitterKey("org_a", "con_2", "gmail")),
])
def test_every_field_participates_in_the_key(a, b):
    """One connection backing gmail AND gcal must not fire both on the same second."""
    assert (jitter_offset(a, interval_seconds=INTERVAL).fraction_bp
            != jitter_offset(b, interval_seconds=INTERVAL).fraction_bp)


def test_key_separator_prevents_field_smearing():
    """("ab","c") and ("a","bc") are different connections; a bare concatenation says otherwise."""
    assert (jitter_offset(JitterKey("ab", "c", ""), interval_seconds=INTERVAL)
            != jitter_offset(JitterKey("a", "bc", ""), interval_seconds=INTERVAL))


@pytest.mark.parametrize("interval", [60, 900, 3600, 12 * 3600])
def test_offset_stays_within_the_configured_spread(interval):
    for i in range(200):
        got = jitter_offset(JitterKey("org", f"con_{i}", "gmail"), interval_seconds=interval)
        assert abs(got.fraction_bp) <= DEFAULT_SPREAD_BP
        assert abs(got.offset_seconds) <= interval * DEFAULT_SPREAD_BP // 10_000


def test_zero_spread_disables_jitter():
    got = jitter_offset(JitterKey("org", "con", "gmail"), interval_seconds=INTERVAL, spread_bp=0)
    assert (got.offset_seconds, got.fraction_bp) == (0, 0)


@pytest.mark.parametrize("interval,spread", [(0, 1000), (-900, 1000), (900, -1), (900, 10_000)])
def test_invalid_inputs_raise(interval, spread):
    with pytest.raises(ValueError):
        jitter_offset(JitterKey("org", "con", "gmail"),
                      interval_seconds=interval, spread_bp=spread)
