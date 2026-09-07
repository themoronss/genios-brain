"""The two halves of must-not-regress #1 and #8 that Y0-Y4 left undefended.

WRITTEN BY THE J0-J4 GATE, after both invariants survived a mutation.

**#1 · SNAPSHOT PINNING HAS TWO HALVES, AND ONLY ONE WAS TESTED.** Doc 06 states the invariant as
*"same (situation, snapshot) -> byte-identical package"*, and `test_byte_identical_compile.py`
proves that half thoroughly. The other half is what makes the first half MEAN anything: a snapshot
that does not move when its sources move pins a package to bytes nobody reviewed. Deleting
`content_hash` from `brain_resolver`'s source digest leaves the whole compiled corpus addressed by
`(kind, id, version)` — so an author can edit any artifact, the compile keeps the OLD
`brain_snapshot_id`, and Law 2's "same snapshot = same package" becomes a promise about a name
rather than about content. That mutation passed 718 tests. The package id still moved (the package
carries the artifact text itself), which is exactly why nothing noticed: every existing assertion
is on the package, none on the snapshot's own sensitivity.

**#8 · ONE ACTIVE VERSION IS A DATABASE GUARANTEE, NOT A CONVENTION.** `publisher.publish_brain`
deactivates the predecessor before inserting, and every test drives that ordering — so downgrading
`learned_brain_one_active` from a UNIQUE index to a plain one passed 140 tests. The index is the
half that survives a second writer, a retry, or a future caller that forgets the ordering, and
"no version noise" in an interleaved write is precisely what it buys.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from l3_inputs import NOW, build_authoring_root, build_situation, build_slice
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from genios_engine.packs.compiler import (DomainCompiler, ExpertBrainCatalog,
                                          InMemoryRuntimeBrains)

ACTIVE_ROW = (
    "insert into learned_brain_entries (org_id, brain, subject, version, learning_id, value, "
    "active, visibility_scope, visibility) "
    "values (:o,'organization','approvals',:v,:l,'{}'::jsonb,true,'org','{}'::jsonb)")


def _snapshot(root: Path) -> tuple[str, str]:
    """`(brain_snapshot_id, package_id)` for one fixed situation over the corpus at `root`."""
    compiler = DomainCompiler(catalog=ExpertBrainCatalog(root),
                              runtime_brains=InMemoryRuntimeBrains(), publisher=None,
                              require_admission=False)
    package = compiler.compile(build_situation(trace_id="trace_snap"),
                               build_slice(trace_id="trace_snap_ctx", evaluation_time=NOW))
    return package.brain_snapshot_id, package.id


@pytest.mark.unit
def test_the_brain_snapshot_moves_when_an_artifact_changes(tmp_path):
    """MUST-NOT-REGRESS #1, the sensitivity half: edit a byte of authored knowledge, and the
    snapshot the package pins to must be a different snapshot."""
    root = build_authoring_root(tmp_path)
    before_snapshot, before_package = _snapshot(root)

    # The OBJECT document — a first-class knowledge source in the expert slice. Its own bytes are
    # edited, not its id or version, which is the exact shape of an author revising a definition
    # in place: `content_hash` is `semantic_hash(parsed)`, so a comment would prove nothing and a
    # changed VALUE proves everything.
    artifact = root / "Sales Expertise/objects/core/account.yaml"
    body = artifact.read_text()
    assert "The buying organisation." in body, body
    artifact.write_text(body.replace("The buying organisation.",
                                     "The buying organisation, as revised."))

    after_snapshot, after_package = _snapshot(root)
    assert after_snapshot != before_snapshot, (
        f"{artifact.name} changed and brain_snapshot_id did not — a snapshot that ignores its "
        f"own sources makes 'same snapshot, same package' a claim about a name")
    assert after_package != before_package


@pytest.mark.unit
def test_an_unchanged_corpus_keeps_the_same_snapshot(tmp_path):
    """The other direction, so the test above cannot be satisfied by a snapshot that simply
    changes every time — which would be the churn bug wearing this test as a disguise."""
    root = build_authoring_root(tmp_path)
    assert _snapshot(root)[0] == _snapshot(root)[0]


@pytest.mark.pg
def test_the_database_refuses_a_second_active_brain_entry(pg_store):
    """MUST-NOT-REGRESS #8. Not "the publisher deactivates first" — that is the convention this
    index exists to survive. Two writers, no deactivation, and the second INSERT must fail."""
    org = "gate_one_active"
    with pg_store.engine.begin() as conn:
        cols = conn.execute(text(
            "select column_name, data_type, is_nullable, column_default from "
            "information_schema.columns where table_name='orgs'")).mappings().all()
        names, holes, values = [], [], {}
        for row in cols:
            if row["is_nullable"] == "YES" or row["column_default"]:
                if row["column_name"] != "id":
                    continue
            names.append(row["column_name"])
            holes.append(f":{row['column_name']}")
            kind = row["data_type"]
            values[row["column_name"]] = (
                org if row["column_name"] == "id"
                else "2026-01-01T00:00:00Z" if ("time" in kind or "date" in kind)
                else 0 if ("int" in kind or "numeric" in kind or "double" in kind)
                else False if kind == "boolean"
                else "{}" if kind in ("json", "jsonb") else "scratch")
        conn.execute(text(f"insert into orgs ({', '.join(names)}) values "
                          f"({', '.join(holes)}) on conflict (id) do nothing"), values)
        conn.execute(text("delete from learned_brain_entries where org_id = :o"), {"o": org})
        conn.execute(text(ACTIVE_ROW), {"o": org, "v": 1, "l": "lrn_one"})

    with pytest.raises((IntegrityError, DBAPIError)) as exc:
        with pg_store.engine.begin() as conn:
            conn.execute(text(ACTIVE_ROW), {"o": org, "v": 2, "l": "lrn_two"})
    assert "learned_brain_one_active" in str(exc.value)

    # And the legitimate supersession — deactivate, then insert — still works, so the index
    # constrains version NOISE rather than versioning.
    with pg_store.engine.begin() as conn:
        conn.execute(text("update learned_brain_entries set active = false "
                          "where org_id = :o and version = 1"), {"o": org})
        conn.execute(text(ACTIVE_ROW), {"o": org, "v": 2, "l": "lrn_two"})
    with pg_store.engine.connect() as conn:
        live = conn.execute(text("select count(*) from learned_brain_entries "
                                 "where org_id = :o and active"), {"o": org}).scalar()
    assert live == 1
