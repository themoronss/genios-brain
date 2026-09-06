"""What every Layer 1 gate report does identically: name a window, and refuse to write.

`l1_s1_report` (G2) landed first and grew both of these inside itself. G7, G8 and G10 each need
the same two things, and three more copies of a `--since` parser is three more places for a gate
to disagree with another gate about what `30d` means — which would make two reports about the
same week incomparable, and comparing reports is the whole reason the gates print numbers.

READ-ONLY IS A SERVER SETTING HERE, NOT A CONVENTION. `set transaction read only` is issued as
the first statement of the transaction, so Postgres refuses a write the script did not intend
rather than a reviewer catching it. Every gate report in this directory opens its connection
through `read_only_connection`, and the acceptance tests assert that it does — a gate script is
exactly the kind of "harmless" tool that ends up pointed at production.
"""
from __future__ import annotations

import argparse
import re
from datetime import timedelta

#: `--since` accepts whole days, hours or minutes, and nothing else. Whole units only: a window
#: is an operator's statement about what they want to look at, and "1.5d" is a way of writing 36h
#: that invites a float into a report whose subject is exact integers.
_SINCE = re.compile(r"^(\d+)([dhm])$")
_SINCE_UNITS = {"d": 86_400, "h": 3_600, "m": 60}


def parse_since(value: str) -> timedelta:
    """`30d` / `12h` / `90m` → a timedelta. Anything else is refused, loudly."""
    match = _SINCE.match(value.strip().lower())
    if not match:
        raise argparse.ArgumentTypeError(
            f"--since must be a whole number of days, hours or minutes (e.g. 30d, 12h, 90m); "
            f"got {value!r}")
    return timedelta(seconds=int(match.group(1)) * _SINCE_UNITS[match.group(2)])


def sql(statement: str):
    """`text()` without making every gate script import SQLAlchemy at module scope."""
    from sqlalchemy import text
    return text(statement)


def read_only_connection(engine):
    """A connection whose transaction the SERVER will refuse writes on.

    `set transaction read only` has to be the FIRST statement of the transaction, which is why it
    lives here rather than in each report's query helpers: SQLAlchemy begins implicitly on the
    first execute, so this call both opens the transaction and constrains it.
    """
    conn = engine.connect()
    conn.execute(sql("set transaction read only"))
    return conn


__all__ = ["parse_since", "read_only_connection", "sql"]
