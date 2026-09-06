"""One number, one migration. A collision is not cosmetic.

`platform/migrate.apply_migrations` applies `migrations/*.sql` in FILENAME order and records each
by filename, so two files sharing a number still apply deterministically — today. What the number
is actually load-bearing for is everything a human does with it: `0089` appeared in nine comments
across the engine and pointed at two different tables, an operator asked to "roll back 0089" has
two answers, and the next writer picking "the next number" reads the highest prefix and collides
again. `0089_qualified_signals.sql` and `0089_signal_lifecycle.sql` shipped in this build; the
second is now `0093`.

The suffix is deliberately not checked — only the number, because the number is the identity.
"""
from __future__ import annotations

import collections
import pathlib

MIGRATIONS = pathlib.Path(__file__).resolve().parents[1] / "migrations"


def test_every_migration_has_its_own_number():
    by_number: dict[str, list[str]] = collections.defaultdict(list)
    for path in sorted(MIGRATIONS.glob("*.sql")):
        by_number[path.name.split("_", 1)[0]].append(path.name)
    collisions = {n: names for n, names in by_number.items() if len(names) > 1}
    assert not collisions, (
        "two migrations share one number — 'roll back 0089' has two answers, and the next "
        f"writer reading the highest prefix will collide again: {collisions}")


def test_every_migration_is_numbered_at_all():
    """A file that sorts by name and carries no number sorts wherever its letters put it."""
    unnumbered = [p.name for p in sorted(MIGRATIONS.glob("*.sql"))
                  if not p.name.split("_", 1)[0].isdigit()]
    assert not unnumbered, f"migrations with no leading number: {unnumbered}"
