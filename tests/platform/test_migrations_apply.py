"""The migration ledger's own guards — the test three tree units named and nobody had written.

    pytest tests/platform/test_migrations_apply.py -q
    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/platform/test_migrations_apply.py -q -m pg

⛔ WHY THIS FILE EXISTS. `tree.yaml` named `tests/platform/test_migrations_apply.py` as the verify
command for three separate units, and the file did not exist. A verify command that cannot run is not a
verify: it reads as tested work and proves nothing. Four migrations written in this programme —
`0186_signal_bundles`, `0187_evidence_needs`, `0188_pipeline_counters`, `0189_output_lane` — had no
automated proof they even parse.

⛔ MOST OF THIS RUNS WITHOUT A DATABASE, ON PURPOSE. The properties that actually break a deploy are
structural: a duplicate number, a file edited after it was applied, a `create table` with no
`if not exists`. Gating all of them behind a live Postgres would mean they are checked when somebody
remembers to set an environment variable — which is the same as not being checked.

The one thing only a real database can prove — that the whole ledger applies from empty and is
idempotent on a second run — is marked `pg` and skipped without `GENIOS_TEST_DATABASE_URL`.
"""

from __future__ import annotations

import os
import re
from collections import Counter
from pathlib import Path

import pytest

from genios_engine.platform import migrate

_DIR = Path(__file__).resolve().parents[2] / "migrations"
_FILES = sorted(_DIR.glob("*.sql"))
_NUMBERED = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")


def _sql(path: Path) -> str:
    return path.read_text(encoding="utf-8")


# =================================================================================================
# 1 · the ledger's own contract
# =================================================================================================
def test_the_migrations_directory_is_where_the_module_thinks_it_is():
    """⛔ A path computed with the wrong number of `parents[]` is the defect class this repo has hit
    before — `tests/scenarios/test_invariants.py` broke exactly that way during a folder move."""
    assert migrate._MIGRATIONS == _DIR
    assert _DIR.is_dir()


def test_there_are_migrations_to_apply():
    assert len(_FILES) > 100, "the directory resolved but is suspiciously empty"


def test_every_filename_is_numbered_and_snake_case():
    bad = [f.name for f in _FILES if not _NUMBERED.match(f.name)]
    assert bad == [], f"the ledger orders by filename, so a name it cannot parse sorts wrong: {bad}"


def test_no_two_migrations_share_a_number():
    """⛔ Two files with one number apply in an order that depends on the rest of the name. The
    ledger's key is the filename, so both would apply — in whichever order the OS sorted them."""
    nums = Counter(_NUMBERED.match(f.name).group(1) for f in _FILES)
    dupes = sorted(n for n, c in nums.items() if c > 1)
    assert dupes == [], f"duplicate migration numbers: {dupes}"


def test_the_numbers_are_strictly_increasing():
    """Filename order is apply order, so the sequence must be readable as one. Gaps are NOT asserted:
    measured, this repo has them, and a withdrawn migration leaving its number retired is the same
    rule `tree.yaml` follows for unit ids — an id is never reused."""
    nums = [int(_NUMBERED.match(f.name).group(1)) for f in _FILES]
    assert nums == sorted(nums)
    assert len(set(nums)) == len(nums)


# =================================================================================================
# 2 · ⛔ idempotence — GOING FORWARD ONLY, and the cutoff is the point
# =================================================================================================
#: ⛔ THESE ASSERTIONS APPLY FROM 0176 ONWARDS, AND MY FIRST VERSION APPLIED THEM TO ALL 180+ FILES.
#: Twenty-eight failed, and every one was correct behaviour.
#:
#: `platform/migrate.py`'s own comment explains why: *"Before this existed, every *.sql re-ran on
#: every invocation, so correctness silently depended on every statement being idempotent forever."*
#: The checksum ledger REMOVED that requirement. So `alter table … add constraint` with no preceding
#: drop — 24 files do it, up to 0175 — is not a defect; it is a statement the ledger guarantees runs
#: once.
#:
#: What IS worth guarding is the convention the newer files follow, so it does not quietly lapse. A
#: floor makes that a forward rule instead of a retroactive accusation. Raising it is fine; lowering
#: it means re-litigating a decision the ledger already settled.
_IDEMPOTENCE_FLOOR = 176

_RECENT = [f for f in _FILES if int(_NUMBERED.match(f.name).group(1)) >= _IDEMPOTENCE_FLOOR]


def test_the_floor_actually_covers_this_programmes_work():
    """A floor above the files it is meant to guard would make every assertion below vacuous — the
    'guard that passes because it has nothing to check' shape this programme found in Plane R."""
    assert len(_RECENT) >= 4
    for name in ("0186_signal_bundles.sql", "0187_evidence_needs.sql",
                 "0188_pipeline_counters.sql", "0189_output_lane.sql"):
        assert (_DIR / name) in _RECENT


@pytest.mark.parametrize("path", _RECENT, ids=lambda p: p.name)
def test_a_create_table_says_if_not_exists(path):
    """⛔ One non-idempotent statement aborts every later statement in its file — `migrate.py` says
    so: *"one tx per file"*. A restore, a branch deploy or a ledger row lost to a rollback all re-run
    a file the ledger thought was done."""
    sql = _sql(path).lower()
    for match in re.finditer(r"create\s+table\s+(?!if\s+not\s+exists)", sql):
        head = sql[match.start():match.start() + 60]
        assert "if not exists" in head, f"{path.name}: {head.strip()!r}"


@pytest.mark.parametrize("path", _RECENT, ids=lambda p: p.name)
def test_a_create_index_says_if_not_exists(path):
    sql = _sql(path).lower()
    for match in re.finditer(r"create\s+(unique\s+)?index\s+(?!if\s+not\s+exists|concurrently)",
                             sql):
        head = sql[match.start():match.start() + 70]
        assert "if not exists" in head, f"{path.name}: {head.strip()!r}"


@pytest.mark.parametrize("path", _RECENT, ids=lambda p: p.name)
def test_an_added_constraint_drops_itself_first(path):
    """`alter table … add constraint` is not idempotent in Postgres. The house pattern in 0186–0189
    is `drop constraint if exists` immediately before, which makes the pair re-runnable.

    A table constraint written INSIDE `create table` needs no drop — it is covered by that
    statement's own `if not exists` — so only the `alter table` form is checked."""
    sql = _sql(path).lower()
    for match in re.finditer(r"alter\s+table\s+[a-z0-9_.\"]+\s+add\s+constraint\s+([a-z0-9_]+)",
                             sql):
        name = match.group(1)
        assert f"drop constraint if exists {name}" in sql, f"{path.name}: {name}"


# =================================================================================================
# 3 · the four this programme wrote
# =================================================================================================
_OURS = ["0186_signal_bundles.sql", "0187_evidence_needs.sql",
         "0188_pipeline_counters.sql", "0189_output_lane.sql"]


@pytest.mark.parametrize("name", _OURS)
def test_the_migrations_this_programme_wrote_exist(name):
    assert (_DIR / name).exists(), f"{name} is referenced by a step document"


@pytest.mark.parametrize("name", _OURS)
def test_each_one_says_why_it_exists(name):
    """A migration is the one artifact nobody can read the intent of later. Every one in this
    programme opens with a comment block naming the defect it closes."""
    head = _sql(_DIR / name)[:900]
    assert head.lstrip().startswith("--"), f"{name} has no leading comment"
    assert len(head.split("\n--")) > 4, f"{name}'s comment is too thin to explain itself"


@pytest.mark.parametrize("name", ["0186_signal_bundles.sql", "0187_evidence_needs.sql"])
def test_a_tenant_scoped_table_cascades_on_org_deletion(name):
    """⛔ Doc 07: a table that survives a tenant deletion is a compliance defect, and it is the kind
    only discovered during an audit. `tests/test_account_erasure.py` enforces it at runtime; this
    checks the migration declared it."""
    sql = _sql(_DIR / name).lower()
    assert "references orgs" in sql or "org_cascade_fk" in sql
    assert "on delete cascade" in sql


def test_the_counters_table_refuses_a_negative_count():
    sql = _sql(_DIR / "0188_pipeline_counters.sql").lower()
    assert "check (n >= 0)" in sql


def test_the_lane_columns_are_nullable_so_old_rows_stay_honest():
    """⛔ NULL is an answer: a row written before routing existed was never routed, and a default
    would claim a decision nobody made."""
    sql = _sql(_DIR / "0189_output_lane.sql").lower()
    assert "add column if not exists output_lane text;" in sql
    assert "not null" not in sql.split("add column if not exists output_lane")[1][:60]


# =================================================================================================
# 4 · ⛔ immutability — the rule the checksum ledger enforces
# =================================================================================================
def test_the_ledger_refuses_a_file_edited_after_it_was_applied():
    """⛔ THE RULE THAT KEEPS TWO DEPLOYS IN AGREEMENT. `_pending` raises on checksum drift rather
    than re-applying, because a file changed after it ran means one database has the old statements
    and another has the new ones — with the same ledger row."""
    import inspect

    source = inspect.getsource(migrate._pending)
    assert "checksum drift" in source
    assert "raise" in source


def test_pending_is_filename_ordered():
    """Filename order IS apply order. Sorting anywhere else would make the sequence depend on how
    the filesystem happened to list the directory."""
    import inspect

    assert "sorted(" in inspect.getsource(migrate._pending)


def test_the_ledger_is_read_with_a_select_so_a_read_only_server_can_be_diagnosed():
    """⛔ The one way to learn whether there is anything to do that works on a read-only server —
    which is the state a database enters when it crosses its disk quota, as this one has."""
    import inspect

    source = inspect.getsource(migrate._read_ledger)
    assert "select filename, checksum from schema_migrations" in source


def test_a_read_only_database_raises_its_own_error_type():
    """`ReadOnlyDatabaseError` exists because the driver's error cannot be told from a genuine
    migration failure without reading its message, and the two need opposite handling at boot."""
    assert issubclass(migrate.ReadOnlyDatabaseError, RuntimeError)


# =================================================================================================
# 5 · the part only a real database can prove
# =================================================================================================
@pytest.mark.pg
@pytest.mark.skipif(not os.environ.get("GENIOS_TEST_DATABASE_URL"),
                    reason="needs GENIOS_TEST_DATABASE_URL pointing at a scratch database")
def test_the_whole_ledger_applies_from_empty_and_is_idempotent():
    """⛔ Applied twice, because that is the failure a deploy actually hits: the second run must be a
    no-op, not an error. The first run proves every file parses against a real server."""
    url = os.environ["GENIOS_TEST_DATABASE_URL"]

    first = migrate.apply_migrations(url)
    second = migrate.apply_migrations(url)

    assert first is not None
    assert not second or len(second) == 0, f"a second run applied {second}"
