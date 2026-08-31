"""A sweep over an unchanged graph must not write a new expertise package.

`expertise_packages` reached 4,086 rows and 995 MB on the design partner's database — 67% of the
whole database, for 127 distinct situations — and the Supabase project crossed its disk quota into
read-only, which stops every write the product makes, not only this one. Every row's payload
averaged 238 kB and every row's `semantic_hash` was distinct, which is the tell: the publisher's
`on conflict (org_id, expertise_id) do nothing` is correct, and it never fired because the id it
conflicts on was new every time.

Two fields did it, both observation metadata that was being hashed as content:

  * `ExpertisePackage.trace_id` — `domain_shadow` mints `new_id("trace")` per situation per sweep;
  * `SituationContextSlice.evaluation_time` — the wall clock, reaching the package's content
    address through `context_slice_hash` in its metadata.

`test_contract_envelope_and_compiler_are_deterministic` already asserted `first.id == second.id`
and passed throughout, because its fixture supplies a CONSTANT trace id and a constant NOW. It
proved the compiler deterministic in every field except the two that are never constant in
production. These tests vary exactly those two, the way a real sweep does.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import pathlib
import sys
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.packs.compiler import (
    DomainCompiler,
    ExpertBrainCatalog,
    InMemoryExpertisePublisher,
    InMemoryRuntimeBrains,
)
from genios_engine.packs.compiler.expertise_publisher import (
    PostgresExpertisePublisher,
    purge_superseded_expertise_packages,
)

# `tests/` is not a package and this repo sets no pytest `importmode`, so a plain sibling import
# resolves only when pytest happens to have imported the other module first — it passes when the
# suite runs and fails when this file runs alone. Load it explicitly. The alternative is copying
# ~120 lines of authoring-corpus fixture, which would then drift away from the module it was
# copied from and quietly stop testing the same compiler.
_FIXTURES = importlib.util.spec_from_file_location(
    "_compiler_fixtures",
    pathlib.Path(__file__).with_name("test_domain_expertise_compiler.py"))
_mod = importlib.util.module_from_spec(_FIXTURES)
sys.modules["_compiler_fixtures"] = _mod
_FIXTURES.loader.exec_module(_mod)

NOW = _mod.NOW
_authoring_root = _mod._authoring_root
_context = _mod._context
_situation = _mod._situation


def _compiler(tmp_path, publisher):
    return DomainCompiler(
        catalog=ExpertBrainCatalog(_authoring_root(tmp_path)),
        require_admission=False,
        runtime_brains=InMemoryRuntimeBrains(),
        publisher=publisher,
    )


def _sweep(compiler, *, trace: str, at):
    """One sweep's compile, with the two things a real sweep changes and nothing else."""
    situation = _situation()
    object.__setattr__(situation, "trace_id", trace)
    context = _context()
    object.__setattr__(context, "trace_id", f"{trace}_ctx")
    object.__setattr__(context, "evaluation_time", at)
    return compiler.compile(situation, context=context)


def test_a_repeat_compile_does_not_mint_a_new_package(tmp_path):
    """The unit fact. A different trace id and a different clock, same graph, same id and hash."""
    compiler = _compiler(tmp_path, InMemoryExpertisePublisher())
    first = _sweep(compiler, trace="trace_sweep_1", at=NOW)
    second = _sweep(compiler, trace="trace_sweep_2", at=NOW + timedelta(hours=6))

    assert first.id == second.id, "a sweep minted a new package id for unchanged knowledge"
    assert first.semantic_hash == second.semantic_hash
    # And the publisher therefore recognises it: the second compile gets back the package already
    # held, not a second copy of it. That identity is the dedup, expressed at the object level.
    assert second is first
    # The trace id is not erased — the held package keeps the observation that created it, and the
    # column exists precisely so a package can be traced back to a sweep.
    assert first.trace_id == "trace_sweep_1"


def test_the_graph_moving_still_mints_a_new_package(tmp_path):
    """The other half, and the one that makes the fix a fix rather than a mute button. Content
    changing MUST still produce a new package, or the compiled brain would serve stale knowledge
    forever and this test file would be describing a worse bug than the one it closed."""
    compiler = _compiler(tmp_path, InMemoryExpertisePublisher())
    baseline = _sweep(compiler, trace="trace_a", at=NOW)

    situation = _situation()
    object.__setattr__(situation, "trace_id", "trace_b")
    moved = _context()
    object.__setattr__(moved, "trace_id", "trace_b_ctx")
    object.__setattr__(moved, "graph_version", 8)          # the graph advanced
    after = compiler.compile(situation, context=moved)

    assert after.id != baseline.id, "an advanced graph must mint a new package"
    assert after.semantic_hash != baseline.semantic_hash


def test_two_sweeps_write_one_row_not_two(pg_store, tmp_path):
    """The consequence, on a real database, through the real publisher.

    This is the assertion that would have caught the incident: the in-memory publisher keys on the
    id too, so it agreed with the bug. Only a row count says whether the disk grew.

    A FRESH compiler per sweep, deliberately. Reusing one would let its in-memory publisher return
    the already-held package and the Postgres publisher would be handed the same object three
    times — which proves the in-memory dedup works and nothing about the id. Production runs each
    sweep in a process that holds no memory of the last one, so the test must too.
    """
    org = "org_1"
    with pg_store.engine.begin() as c:
        if not c.execute(text("select to_regclass('public.expertise_packages')")).scalar():
            pytest.skip("expertise_packages migration not applied")
        reqd = c.execute(text(
            "select column_name, data_type from information_schema.columns where table_name='orgs' "
            "and is_nullable='NO' and column_default is null and column_name<>'id'")).all()
        cols, ph, vals = ["id"], [":id"], {"id": org}
        for r in reqd:
            cols.append(r.column_name); ph.append(f":{r.column_name}")
            dt = r.data_type
            vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                                   else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                                   else False if dt == "boolean"
                                   else "{}" if dt in ("json", "jsonb") else "scratch")
        c.execute(text(f"insert into orgs ({', '.join(cols)}) values ({', '.join(ph)}) "
                       "on conflict (id) do nothing"), vals)
        c.execute(text("delete from expertise_packages where org_id = :o"), {"o": org})

    for i, at in enumerate((NOW, NOW + timedelta(hours=3), NOW + timedelta(days=1))):
        package = _sweep(_compiler(tmp_path, InMemoryExpertisePublisher()),
                         trace=f"trace_run_{i}", at=at)
        with pg_store.engine.begin() as c:
            PostgresExpertisePublisher(c).publish(package)

    with pg_store.engine.connect() as c:
        rows = c.execute(text("select count(*) from expertise_packages where org_id = :o"),
                         {"o": org}).scalar()
    assert rows == 1, f"three sweeps over an unchanged graph wrote {rows} packages"


def _seed_org(conn, org):
    reqd = conn.execute(text(
        "select column_name, data_type from information_schema.columns where table_name='orgs' "
        "and is_nullable='NO' and column_default is null and column_name<>'id'")).all()
    cols, ph, vals = ["id"], [":id"], {"id": org}
    for r in reqd:
        cols.append(r.column_name); ph.append(f":{r.column_name}")
        dt = r.data_type
        vals[r.column_name] = ("2026-01-01T00:00:00Z" if ("time" in dt or "date" in dt)
                               else 0 if ("int" in dt or "numeric" in dt or "double" in dt)
                               else False if dt == "boolean"
                               else "{}" if dt in ("json", "jsonb") else "scratch")
    conn.execute(text(f"insert into orgs ({', '.join(cols)}) values ({', '.join(ph)}) "
                      "on conflict (id) do nothing"), vals)


def _row(conn, org, situation, n, at):
    """A minimal row that satisfies migration 0047's shape checks — the ids are regex-constrained
    (`^expertise_[0-9a-f]{64}$`, `^brains_[0-9a-f]{64}$`) and the payload is projected against the
    columns, so a lazy fixture is rejected by the database rather than by review."""
    hexed = hashlib.sha256(f"{org}:{situation}:{n}".encode()).hexdigest()
    expertise = f"expertise_{hexed}"
    visibility = '{"scope":"org","principals":[],"excluded_subjects":[],"derived_from":"test"}'
    payload = json.dumps({
        "org_id": org, "id": expertise, "schema_version": "expertise-package.v1",
        "situation_id": situation, "brain_snapshot_id": f"brains_{hexed}",
        "visibility": json.loads(visibility),
    })
    conn.execute(text(
        "insert into expertise_packages (org_id,expertise_id,semantic_hash,schema_version,"
        "trace_id,situation_id,brain_snapshot_id,visibility,payload,created_at) values "
        "(:o,:id,:h,'expertise-package.v1',:t,:s,:b,cast(:vis as jsonb),cast(:pl as jsonb),:at)"),
        {"o": org, "id": expertise, "h": hexed, "t": f"trace_{n}", "s": situation,
         "b": f"brains_{hexed}", "vis": visibility, "pl": payload, "at": at})
    return expertise


def test_retention_keeps_the_current_package_and_a_replay_window(pg_store):
    """The other half of the incident, and the half content-addressing cannot reach.

    `SituationContextSlice.graph_version` is org-global, so any write anywhere in the tenant
    advances the version every situation's slice carries — a package legitimately mints a new id
    on each sync that touched anything. At ~238 kB and 73 live situations that is ~17 MB a sync
    for one tenant: slower than the bug that filled the disk, and still unbounded.

    Asserted per situation, not in total, because a global "keep the newest N" would silently
    delete every package of a quiet situation the moment a busy one produced N newer rows.
    """
    org = "org_retention"
    with pg_store.engine.begin() as c:
        if not c.execute(text("select to_regclass('public.expertise_packages')")).scalar():
            pytest.skip("expertise_packages migration not applied")
        _seed_org(c, org)
        c.execute(text("delete from expertise_packages where org_id = :o"), {"o": org})
        busy_ids: list[str] = []
        for i in range(7):                       # a busy situation: seven sweeps
            busy_ids = busy_ids + [_row(c, org, "sit_busy", i, NOW + timedelta(hours=i))]
        for i in range(2):                       # a quiet one: two, both inside the window
            _row(c, org, "sit_quiet", i, NOW + timedelta(hours=i))

    removed = purge_superseded_expertise_packages(pg_store.engine, keep=3)
    assert removed == 4, f"expected the four superseded busy rows, removed {removed}"

    with pg_store.engine.connect() as c:
        kept = dict(c.execute(text(
            "select situation_id, count(*) from expertise_packages where org_id=:o "
            "group by situation_id"), {"o": org}).all())
        newest = c.execute(text(
            "select expertise_id from expertise_packages where org_id=:o and situation_id='sit_busy' "
            "order by created_at desc limit 1"), {"o": org}).scalar()
    assert kept == {"sit_busy": 3, "sit_quiet": 2}
    # The one that matters: the package the CURRENT card cites must be the one that survives.
    assert newest == busy_ids[-1], "retention deleted the newest package"


def test_retention_is_tenant_scoped(pg_store):
    """A sweep is org-wide, so the window must partition by org too — otherwise a busy tenant's
    sweeps evict a quiet tenant's only package and that tenant's cards lose their provenance."""
    with pg_store.engine.begin() as c:
        if not c.execute(text("select to_regclass('public.expertise_packages')")).scalar():
            pytest.skip("expertise_packages migration not applied")
        for org in ("org_ret_a", "org_ret_b"):
            _seed_org(c, org)
            c.execute(text("delete from expertise_packages where org_id = :o"), {"o": org})
        for i in range(5):
            _row(c, "org_ret_a", "shared_situation_id", i, NOW + timedelta(hours=i))
        _row(c, "org_ret_b", "shared_situation_id", 0, NOW)

    purge_superseded_expertise_packages(pg_store.engine, keep=3)
    with pg_store.engine.connect() as c:
        per_org = dict(c.execute(text(
            "select org_id, count(*) from expertise_packages "
            "where org_id in ('org_ret_a','org_ret_b') group by org_id")).all())
    assert per_org == {"org_ret_a": 3, "org_ret_b": 1}


def test_the_heartbeat_sweeps_this_table():
    """Retention nobody runs is a comment. The sweep is the only scheduled pass in the product."""
    import inspect

    from genios_engine.api import routes
    source = inspect.getsource(routes.run_maintenance_sweep)
    assert "purge_superseded_expertise_packages" in source, (
        "the maintenance heartbeat does not sweep expertise_packages")
