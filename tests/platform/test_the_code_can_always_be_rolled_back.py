"""Rolling the code back has to stay possible, and nothing was keeping it possible.

P-9 asks for a rollback path. Half of it is not ours: a point-in-time restore of the DATABASE is
the platform's (Supabase PITR / backups), and no amount of code produces one. The other half is,
and it is the half that decides whether the platform's half is ever needed — **can the previous
image run against the current schema?**

Today it can, by accident rather than by rule. Measured across all 161 migrations:

    drop table            0
    drop column           0
    alter column … type   0
    rename column         0
    drop constraint      17   — relaxing one is backward compatible: old code still writes
                                rows the looser constraint accepts
    rename to             1   — migration 0080, `l2_extraction_results` -> `l1_extraction_results`

So the de-facto policy is additive-only, and the one exception already shows why it matters: a
rename leaves the previous image querying a table that no longer answers to that name. 0080 is
declared below rather than grandfathered silently — it is the counterexample, and a list with no
entries teaches nobody why it exists.

WHAT THIS DOES NOT CLAIM. Additive migrations make a code rollback safe; they say nothing about
rolling DATA back. A migration that backfills a column cannot be undone by redeploying, and this
test would not object to one — correctly, because that is what the database snapshot is for.
"""
from __future__ import annotations

import io
import re
from pathlib import Path

import pytest

#: Statements that make the PREVIOUS image unable to run against the new schema, and why each is
#: on the list. `drop constraint` is deliberately absent: loosening a rule never breaks a writer
#: that was already obeying the stricter one.
BREAKS_THE_PREVIOUS_IMAGE = {
    r"\bdrop\s+table\b": "the previous image queries a table that is gone",
    r"\bdrop\s+column\b": "the previous image selects a column that is gone",
    r"\brename\s+to\b": "the previous image queries the old name",
    r"\brename\s+column\b": "the previous image selects the old column name",
    r"\balter\s+column\s+\w+\s+type\b": "the previous image writes a value the column no longer takes",
}

#: The one migration that broke the rule, kept so the rule has a worked example. 0080 renamed
#: `l2_extraction_results` to `l1_extraction_results` and says in its own comment why a rename
#: rather than a re-create: "those rows ARE the money already spent". It was right to rename and
#: it did cost a rollback window; both facts belong in the record.
DECLARED_EXCEPTIONS = {"0080_l1_extraction_results.sql"}


def _statements(path: Path) -> str:
    """The file's SQL with comments stripped — this file's own rule is quoted in several of those
    comments, and matching prose would fail a migration for explaining itself."""
    text = io.open(path, encoding="utf-8").read()
    lines = [ln for ln in text.splitlines() if not ln.strip().startswith("--")]
    return re.sub(r"\s+", " ", " ".join(lines)).lower()


MIGRATIONS = sorted(Path("migrations").glob("*.sql"))


def test_there_are_migrations_to_check():
    assert len(MIGRATIONS) > 100, "the migration directory moved; this test is checking nothing"


@pytest.mark.parametrize("path", MIGRATIONS, ids=lambda p: p.name)
def test_no_migration_locks_out_the_previous_image(path):
    """Every new migration is a rollback decision whether or not anybody makes it deliberately."""
    if path.name in DECLARED_EXCEPTIONS:
        pytest.skip(f"{path.name} is a declared exception — see DECLARED_EXCEPTIONS")
    sql = _statements(path)
    found = [why for pattern, why in BREAKS_THE_PREVIOUS_IMAGE.items() if re.search(pattern, sql)]

    assert not found, (
        f"{path.name} would strand the previous image: {found[0]}. If that is genuinely intended, "
        f"add it to DECLARED_EXCEPTIONS with the reason — and know that deploying it closes the "
        f"code-rollback window until every running image is past it.")


def test_the_exceptions_are_real_files():
    """A stale exception is a rule with a hole in it: the file it names is gone, the hole stays."""
    names = {p.name for p in MIGRATIONS}

    for declared in DECLARED_EXCEPTIONS:
        assert declared in names, f"{declared} is declared an exception and does not exist"


def test_each_exception_actually_needed_one():
    """The other direction. An entry that no longer breaks anything is a permission nobody is
    using, and permissions that outlive their reason are how a rule stops meaning anything."""
    for declared in DECLARED_EXCEPTIONS:
        sql = _statements(Path("migrations") / declared)
        assert any(re.search(p, sql) for p in BREAKS_THE_PREVIOUS_IMAGE), (
            f"{declared} is exempted and contains nothing this rule would stop — remove it")


def test_relaxing_a_constraint_is_not_treated_as_a_break():
    """17 migrations drop a constraint and every one of them is safe: a writer obeying the
    stricter rule still satisfies the looser one. Listing it would make the rule cry wolf
    seventeen times, which is how a rule stops being run."""
    assert not any("drop constraint" in p for p in BREAKS_THE_PREVIOUS_IMAGE)
