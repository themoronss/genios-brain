"""`scripts/brain_content_report.py` — the J4 gate command, and it has to be able to FAIL.

A gate that passes on an empty brain is worse than no gate, so most of what is asserted here is
the report refusing: an entry with no proposal behind it, an entry whose provenance nobody can
name, a lease that expired and was never cleared. The passing case is asserted once, end to end,
through the same pipeline production uses.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.contracts.learning import LearningPolicy
from genios_engine.packs.brains import adaptive_lease as al
from scripts import brain_content_report as report
from scripts._db import UnsafeDatabaseTarget

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
METRIC = "engagement.outbound_count_28d"
CAPABILITY = "admin.executive_support.commitment_tracking"


@pytest.fixture()
def conn(live_db_url):
    if not live_db_url:
        pytest.skip("no database configured")
    from genios_engine.platform.db import get_engine
    c = get_engine(live_db_url).connect()
    tx = c.begin()
    org = c.execute(text("select id from orgs limit 1")).scalar()
    if not org:
        tx.rollback(); c.close(); pytest.skip("no org")
    try:
        yield c, org
    finally:
        tx.rollback(); c.close()


def _seed_lease(c, org, *, n_start=0):
    from genios_engine.feedback.brain_pipeline import lease_from_card_feedback
    # `tests/packs/` is not a package, so pytest's prepend import mode puts THIS directory on
    # sys.path and the sibling module is importable by its bare name. Reusing its seeder rather
    # than copying it keeps one definition of "what a card verdict row looks like".
    from test_adaptive_lease import _seed_verdict

    for i in range(4):
        _seed_verdict(c, org, n=n_start + i, at=NOW - timedelta(days=i), actor=f"a{i % 2}")
    return lease_from_card_feedback(c, org_id=org, now=NOW, capability_ids=(CAPABILITY,))


def _seed_behavior_entries(c, org):
    from genios_engine.feedback.brain_pipeline import admit_proposals
    from genios_engine.packs.brains import behavior_distill as bd
    from test_behavior_distill import _fact_body

    for node in ("node_a", "node_b", "node_c"):
        field, body = _fact_body(node)
        c.execute(text(
            "insert into graph_facts (fact_version_id, fact_id, org_id, subject_node_id, field, "
            "value, value_type, status, authority_rank, confidence, occurred_at, valid_from, "
            "visibility_scope) values (:vid, :fid, :o, :n, :f, cast(:v as jsonb), 'json', "
            "'active', 100, 0.9, :now, :now, 'org') on conflict (fact_version_id) do nothing"),
            {"vid": f"fv_trend_{node}_{field}", "fid": f"f_trend_{node}_{field}", "o": org,
             "n": node, "f": field, "v": json.dumps(body, sort_keys=True), "now": NOW})
    policy = LearningPolicy(org_id=org, revision=1)
    proposals, _refusals = bd.distill(c, org_id=org, policy=policy)
    return admit_proposals(c, proposals, policy=policy, now=NOW)


# ---- the report reads what the pipeline wrote --------------------------------------------------

def test_a_distilled_entry_and_a_lease_are_attributed_to_the_pipelines_that_made_them(conn):
    c, org = conn
    assert _seed_behavior_entries(c, org).published == 3
    assert _seed_lease(c, org)["published"] == 1

    built = report.build_report(c, org_id=org, at=NOW)
    behavior = built.brain("behavior")
    assert behavior.entries == 3
    assert behavior.by_provenance == {"distilled": 3}
    assert behavior.outside_pipeline == 0 and behavior.unattributed == 0
    assert built.leases.from_card_feedback == 1 and built.leases.expired_not_cleared == 0
    assert built.expert_rows == 0
    # Behaviour, the lease and the pipeline rows all pass; only N-3's Organization row is short.
    failing = [label for label, ok, _m in built.checks if not ok]
    assert failing == ["organization entries >= 3"]


def test_an_entry_with_no_proposal_behind_it_is_a_write_outside_the_pipeline(conn):
    c, org = conn
    c.execute(text(
        "insert into learned_brain_entries (org_id, brain, subject, version, learning_id, value, "
        "visibility_scope, visibility) values (:o, 'behavior', 'behavior:x:node_a', 1, "
        "'lo_never_proposed', '{}', 'organization', '{}')"), {"o": org})
    built = report.build_report(c, org_id=org, at=NOW)
    assert built.outside_pipeline == 1
    assert not built.passed
    assert "writes outside the L6 pipeline == 0" in [label for label, ok, _m in built.checks
                                                     if not ok]
    assert "written outside the L6 pipeline" in report.render(built)


def test_an_entry_nobody_can_attribute_is_a_breach_not_an_other_bucket(conn):
    c, org = conn
    c.execute(text(
        "insert into learning_objects (org_id, learning_id, unit, target, subject, semantic_hash, "
        "proposed_value, evidence, visibility_scope, visibility, policy_key, first_seen_at, "
        "last_seen_at, state) values (:o, 'lo_mystery', 'some_unit_nobody_registered', "
        "'behavior', 's', 'h', '{}', '{}', 'organization', '{}', 'policy:x:1', :at, :at, "
        "'governed')"), {"o": org, "at": NOW})
    c.execute(text(
        "insert into learned_brain_entries (org_id, brain, subject, version, learning_id, value, "
        "visibility_scope, visibility) values (:o, 'behavior', 's', 1, 'lo_mystery', '{}', "
        "'organization', '{}')"), {"o": org})
    built = report.build_report(c, org_id=org, at=NOW)
    assert built.brain("behavior").by_provenance == {report.UNATTRIBUTED: 1}
    assert built.unattributed == 1 and not built.passed


def test_a_value_that_names_its_own_source_is_attributable_without_a_known_unit(conn):
    c, org = conn
    c.execute(text(
        "insert into learning_objects (org_id, learning_id, unit, target, subject, semantic_hash, "
        "proposed_value, evidence, visibility_scope, visibility, policy_key, first_seen_at, "
        "last_seen_at, state) values (:o, 'lo_console', 'console_writer', 'organization', 's', "
        "'h', '{}', '{}', 'organization', '{}', 'policy:x:1', :at, :at, 'governed')"),
        {"o": org, "at": NOW})
    c.execute(text(
        "insert into learned_brain_entries (org_id, brain, subject, version, learning_id, value, "
        "visibility_scope, visibility) values (:o, 'organization', 's', 1, 'lo_console', "
        "cast('{\"source\": \"admin\"}' as jsonb), 'organization', '{}')"), {"o": org})
    built = report.build_report(c, org_id=org, at=NOW)
    assert built.brain("organization").by_provenance == {"admin-confirmed": 1}
    assert built.unattributed == 0


def test_a_lease_that_expired_and_was_never_cleared_fails_the_gate(conn):
    c, org = conn
    _seed_lease(c, org)
    later = NOW + timedelta(seconds=al.LEASE_TTL_SECONDS + 1)
    built = report.build_report(c, org_id=org, at=later)
    assert built.leases.expired_not_cleared == 1
    assert built.leases.expired_subjects == (al.lease_subject(CAPABILITY),)
    assert not built.passed
    assert "expired, still active" in report.render(built)

    from genios_engine.feedback.brain_pipeline import expire_leases

    expire_leases(c, org_id=org, now=later)
    swept = report.build_report(c, org_id=org, at=later)
    assert swept.leases.expired_not_cleared == 0 and swept.leases.cleared == 1


def test_a_zero_that_is_the_clock_working_is_told_apart_from_a_broken_path(conn):
    """The gate row counts LIVE leases, and after the sweep it correctly reads 0.

    Two very different tenants read `adaptive leases from card feedback = 0`: one whose founder
    never earned a lease, and one whose lease ran out exactly as a lease is supposed to. The
    history number — reported, never gated — is the only thing that tells them apart, and an
    operator seeing a red row needs to know which one they are looking at.
    """
    c, org = conn
    never = report.build_report(c, org_id=org, at=NOW)
    assert never.leases.from_card_feedback == 0 and never.leases.from_card_feedback_ever == 0

    _seed_lease(c, org)
    later = NOW + timedelta(seconds=al.LEASE_TTL_SECONDS + 1)
    from genios_engine.feedback.brain_pipeline import expire_leases

    expire_leases(c, org_id=org, now=later)
    swept = report.build_report(c, org_id=org, at=later)
    assert swept.leases.from_card_feedback == 0, "a retired lease is not held by the brain"
    assert swept.leases.from_card_feedback_ever == 1
    assert "granted through card feedback in this tenant's history" in report.render(swept)
    # It is REPORTED, not gated: the history number never rescues the row it explains.
    assert not swept.passed


def test_the_instant_is_an_argument_not_a_clock_the_report_reads(conn):
    """The same rows, two instants, two honest answers — which is only possible if `at` decides."""
    c, org = conn
    _seed_lease(c, org)
    assert report.build_report(c, org_id=org, at=NOW).leases.live == 1
    assert report.build_report(
        c, org_id=org, at=NOW + timedelta(days=30)).leases.expired_not_cleared == 1


def test_the_report_writes_nothing_even_on_a_read_only_transaction(conn):
    """Asserted against PostgreSQL itself, the way `_gate.read_only_connection` runs it."""
    c, org = conn
    _seed_lease(c, org)
    savepoint = c.begin_nested()
    c.execute(text("set transaction read only"))
    built = report.build_report(c, org_id=org, at=NOW)
    savepoint.rollback()
    assert built.leases.live == 1


def test_an_empty_tenant_is_a_failure_and_says_so(conn):
    c, org = conn
    built = report.build_report(c, org_id=f"{org}_absent", at=NOW)
    assert not built.passed
    rendered = report.render(built)
    assert "NOTHING IS IN ANY BRAIN" in rendered
    assert "An empty brain is not a pass" in rendered


def test_the_json_form_carries_every_check(conn):
    c, org = conn
    built = report.build_report(c, org_id=org, at=NOW)
    payload = json.loads(json.dumps(built.as_dict()))
    assert [row["check"] for row in payload["checks"]] == [label for label, _ok, _m
                                                           in built.checks]
    assert payload["passed"] is False


# ---- the safety rails the script inherits ------------------------------------------------------

def test_the_script_refuses_to_run_without_a_named_database(monkeypatch):
    """`scripts/_db` has no fallback to the configured URL — which on a dev machine is production."""
    monkeypatch.delenv("GENIOS_TARGET_DATABASE_URL", raising=False)
    with pytest.raises(UnsafeDatabaseTarget):
        report.main(["--org", "org_x"])


def test_a_naive_instant_is_refused(monkeypatch):
    monkeypatch.setenv("GENIOS_TARGET_DATABASE_URL", "postgresql://u@localhost:5432/x")
    with pytest.raises(SystemExit):
        report.main(["--org", "org_x", "--at", "2026-06-01T12:00:00"])


def test_the_provenance_table_is_built_from_the_pipelines_own_constants():
    """A rename in either pipeline must not silently turn its entries into `unattributed`."""
    from genios_engine.packs.brains.behavior_distill import BEHAVIOR_UNIT

    units = report._pipeline_units()
    assert units[BEHAVIOR_UNIT] == "distilled"
    assert units[al.LEASE_UNIT] == "leased"
    # N-3's half of J4 shares this gate command, so its unit is read off its own constant too.
    from genios_engine.packs.brains.org_discovery import DISCOVERY_UNIT

    assert units[DISCOVERY_UNIT] == "discovered"


def test_a_lease_is_attributed_by_its_proposal_not_only_by_what_its_value_says(conn):
    """A value can say anything. The join to `learning_objects` is the attribution that counts."""
    c, org = conn
    c.execute(text(
        "insert into learning_objects (org_id, learning_id, unit, target, subject, semantic_hash, "
        "proposed_value, evidence, visibility_scope, visibility, policy_key, first_seen_at, "
        "last_seen_at, expires_at, state) values (:o, 'lo_quiet_lease', :u, 'runtime', 's', 'h', "
        "'{}', '{}', 'organization', '{}', 'policy:x:1', :at, :at, :exp, 'governed')"),
        {"o": org, "u": al.LEASE_UNIT, "at": NOW, "exp": NOW + timedelta(days=7)})
    c.execute(text(
        "insert into temporary_memories (org_id, memory_id, learning_id, subject, value, "
        "visibility_scope, visibility, expires_at) values (:o, 'tmem_quiet', 'lo_quiet_lease', "
        "'adaptive:card_timing:x', '{}', 'organization', '{}', :exp)"),
        {"o": org, "exp": NOW + timedelta(days=7)})
    built = report.build_report(c, org_id=org, at=NOW)
    assert built.leases.from_card_feedback == 1, "the unit join is what attributed it"
    assert built.leases.outside_pipeline == 0
