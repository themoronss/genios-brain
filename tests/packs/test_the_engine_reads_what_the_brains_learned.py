"""STEP-13b · what the tenant's brains learned, for a file — the third family the engine reads.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… .venv/bin/python -m pytest -q tests/packs/test_the_engine_reads_what_the_brains_learned.py

Tree `yc2_w27_s13b · M37.C2.L-data.V2.U02`. `packs/compiler/engine_reader.learned_for` reads what Layer
6 published to the Organization, Behaviour and Adaptive brains (`learned_brain_entries`) and the
Adaptive lease store (`temporary_memories`) — the SAME two stores `runtime_brains.PostgresRuntimeBrains`
reads for a compiled situation — but keyed on a FILE's address tokens (`contracts/brain_address`)
rather than on a `BusinessSituationObject`, because a file is not a situation and has none to build
one from. An Organization rule is tenant-wide (`06` D3's reading of the Organization brain: an approved
policy binds everywhere) and is read whatever tokens are given; a Behaviour pattern or an Adaptive
entry binds only where its own published address — or its raw `subject`, for a legacy row with none —
meets one of the file's tokens. A lease is read only as of an `eval_time` (never `now()`): with none
given, no lease is read at all, exactly as `PostgresRuntimeBrains` already refuses to invent one.

Each entry becomes one line — `org:`, `pat:` or `pref:` — carrying the producer's own `statement`
(`pattern_statement` for Behaviour), its confidence and since when it has stood (`effective_at`, read
from `created_at`). Read, never gated (`06` D3, D-s13b-6): the company's own history is not a corpus
draft, so these lines carry no `NOT_REVIEWED` label — `EngineLine.label` already refuses one to any
family but `AUTHORED`, and this test holds that, not re-derives it. Bounded per family, every cut
counted, reusing the same `_Lines` the authored read already carries.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.contracts import engine_read as E
from genios_engine.packs.compiler import engine_reader as R

pytestmark = pytest.mark.pg

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
ORG = "org_learned_for_test"
OTHER_ORG = "org_learned_for_other"


@pytest.fixture
def db():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the brains read Postgres")
    from sqlalchemy import create_engine, text

    engine = create_engine(url)
    with engine.begin() as c:
        _wipe(c)
        for org in (ORG, OTHER_ORG):
            c.execute(text("insert into orgs (id, name, email, company) values (:o, 'Test', :e, 'Co')"),
                      {"o": org, "e": f"{org}@tenant.test"})
    with engine.begin() as c:
        yield c
    with engine.begin() as c:
        _wipe(c)
    engine.dispose()


def _wipe(c) -> None:
    from sqlalchemy import text
    for org in (ORG, OTHER_ORG):
        c.execute(text("delete from temporary_memories where org_id = :o"), {"o": org})
        c.execute(text("delete from learned_brain_entries where org_id = :o"), {"o": org})
        c.execute(text("delete from orgs where id = :o"), {"o": org})


_VISIBILITY = json.dumps({"scope": "org", "principals": []})


def _entry(c, *, org=ORG, brain="organization", subject, version=1, value, active=True,
          days_ago=1.0, visibility=_VISIBILITY, learning_id=None) -> None:
    from sqlalchemy import text
    c.execute(text(
        "insert into learned_brain_entries (org_id, brain, subject, version, learning_id, value, "
        " visibility_scope, visibility, active, created_at) "
        "values (:o, :b, :s, :v, :lid, cast(:val as jsonb), 'org', cast(:vis as jsonb), :act, :at)"),
        {"o": org, "b": brain, "s": subject, "v": version, "lid": learning_id or f"{subject}:v{version}",
         "val": json.dumps(value), "vis": visibility, "act": active, "at": NOW - timedelta(days=days_ago)})


def _lease(c, *, org=ORG, memory_id, subject, value, expires_in_days: float, active=True,
          days_ago=0.5, visibility=_VISIBILITY, learning_id=None) -> None:
    from sqlalchemy import text
    c.execute(text(
        "insert into temporary_memories (org_id, memory_id, learning_id, subject, value, "
        " visibility_scope, visibility, expires_at, active, created_at) "
        "values (:o, :m, :lid, :s, cast(:val as jsonb), 'org', cast(:vis as jsonb), :exp, :act, :at)"),
        {"o": org, "m": memory_id, "lid": learning_id or memory_id, "s": subject,
         "val": json.dumps(value), "vis": visibility,
         "exp": NOW + timedelta(days=expires_in_days), "act": active, "at": NOW - timedelta(days=days_ago)})


def _read(db, *, tokens=(), eval_time=NOW, org=ORG, **kw) -> E.EngineRead:
    return R.learned_for(db, org_id=org, tokens=tokens, eval_time=eval_time, **kw)


# ── Organization — tenant-wide, read whatever tokens are given ────────────────────────────────

def test_an_organization_rule_is_read_whatever_tokens_are_given(db):
    _entry(db, brain="organization", subject="orgrule:spend:threshold",
          value={"statement": "A spend over 2,00,000 needs two approvers.", "confidence_bp": 9000})
    read = _read(db, tokens=())
    assert len(read.of_family(E.ORGANIZATION)) == 1
    line = read.of_family(E.ORGANIZATION)[0]
    assert line.ref.startswith(E.PREFIX[E.ORGANIZATION])
    assert "A spend over 2,00,000 needs two approvers." in line.words
    since = (NOW - timedelta(days=1)).date().isoformat()  # `_entry`'s default days_ago=1.0
    assert line.words.endswith(f"confidence 90%, since {since}"), "confidence before since, in that order"
    assert line.label is None, "a learned line never carries the authored NOT_REVIEWED label"


def test_an_organization_rule_with_no_confidence_of_its_own_reads_the_governance_floor(db):
    _entry(db, brain="organization", subject="orgrule:approval:signoff",
          value={"statement": "A contract needs a named signatory."})
    line = _read(db, tokens=()).of_family(E.ORGANIZATION)[0]
    assert "confidence 60%" in line.words, "06000 bp is the published governance floor"


# ── Behaviour and Adaptive — bound by the file's own tokens ───────────────────────────────────

def test_a_behaviour_pattern_is_read_only_where_a_token_matches(db):
    _entry(db, brain="behavior", subject="behavior:engagement:node_abc",
          value={"pattern_statement": "Kiran replies within a day on 9 of the last 10 threads.",
                 "confidence_bp": 8200, "address": {"tokens": ["node:node_abc", "metric:engagement"]}})
    assert _read(db, tokens=["node:node_abc"]).of_family(E.BEHAVIOUR), "the matching token reads it"
    assert not _read(db, tokens=["node:someone_else"]).of_family(E.BEHAVIOUR), (
        "a token that names nobody on this file reads nothing")
    line = _read(db, tokens=["metric:engagement"]).of_family(E.BEHAVIOUR)[0]
    assert "Kiran replies within a day" in line.words


def test_an_adaptive_lease_is_read_only_as_of_an_eval_time_and_never_without_one(db):
    _lease(db, memory_id="mem_1", subject="adaptive:card_timing:admin.x",
          value={"statement": "Nudges on this card before 10am read as bad timing.",
                 "address": {"tokens": ["capability:admin.x"]}},
          expires_in_days=2)
    assert _read(db, tokens=["capability:admin.x"], eval_time=NOW).of_family(E.ADAPTIVE)
    assert not _read(db, tokens=["capability:admin.x"], eval_time=None).of_family(E.ADAPTIVE), (
        "a missing clock licenses no lease — PostgresRuntimeBrains' own rule")


def test_an_expired_lease_is_not_read_as_of_the_given_instant(db):
    _lease(db, memory_id="mem_2", subject="adaptive:card_timing:admin.y",
          value={"statement": "Expired.", "address": {"tokens": ["capability:admin.y"]}},
          expires_in_days=-1)
    assert not _read(db, tokens=["capability:admin.y"]).of_family(E.ADAPTIVE)


def test_a_legacy_row_with_no_address_still_matches_by_its_raw_subject(db):
    _entry(db, brain="behavior", subject="legacy_subject_123",
          value={"pattern_statement": "A pre-address row.", "confidence_bp": 7000})
    assert _read(db, tokens=["legacy_subject_123"]).of_family(E.BEHAVIOUR)


def test_an_inactive_entry_is_not_read(db):
    _entry(db, brain="organization", subject="orgrule:old", active=False,
          value={"statement": "Superseded."})
    assert _read(db, tokens=()).of_family(E.ORGANIZATION) == ()


def test_another_tenant_s_entries_are_never_read(db):
    _entry(db, org=OTHER_ORG, brain="organization", subject="orgrule:theirs",
          value={"statement": "Not ours."})
    assert _read(db, tokens=(), org=ORG).of_family(E.ORGANIZATION) == ()


# ── shape: family, since-when, bounded, counted ────────────────────────────────────────────────

def test_a_learned_line_is_marked_reviewed_the_company_s_own_history_not_a_draft(db):
    _entry(db, brain="organization", subject="orgrule:marked", value={"statement": "X."})
    line = _read(db, tokens=()).of_family(E.ORGANIZATION)[0]
    assert line.reviewed is True, "it is cosmetic for the label (AUTHORED-only) but still pinned"


def test_each_family_gets_its_own_prefix(db):
    _entry(db, brain="organization", subject="orgrule:a", value={"statement": "A."})
    _entry(db, brain="behavior", subject="behavior:x:node_1",
          value={"pattern_statement": "B.", "address": {"tokens": ["node:node_1"]}})
    _entry(db, brain="adaptive", subject="adaptive:card_timing:cap.z",
          value={"statement": "C.", "address": {"tokens": ["capability:cap.z"]}})
    read = _read(db, tokens=["node:node_1", "capability:cap.z"])
    assert {line.family for line in read.lines} == {E.ORGANIZATION, E.BEHAVIOUR, E.ADAPTIVE}
    for line in read.lines:
        assert line.ref.startswith(E.PREFIX[line.family])


def test_a_line_names_since_when_it_has_stood(db):
    _entry(db, brain="organization", subject="orgrule:since", days_ago=12,
          value={"statement": "Since a while back."})
    line = _read(db, tokens=()).of_family(E.ORGANIZATION)[0]
    assert (NOW - timedelta(days=12)).date().isoformat() in line.words


def test_the_family_is_bounded_and_the_cut_counted(db):
    for i in range(3):
        _entry(db, brain="organization", subject=f"orgrule:{i}", value={"statement": f"Rule {i}."})
    read = _read(db, tokens=(), limits={E.ORGANIZATION: 2})
    assert len(read.of_family(E.ORGANIZATION)) == 2
    assert read.cut[E.ORGANIZATION] == 1


def test_no_tokens_and_no_rows_reads_an_empty_engine_read(db):
    read = _read(db, tokens=())
    assert read.lines == () and read.empty


# ── STEP-13b M37.C5.L-logic.V4.U01 · the fingerprint's name for what the brains hold ───────────

def test_the_snapshot_is_none_when_the_brains_hold_nothing_for_the_file(db):
    assert R.learned_snapshot(db, org_id=ORG, tokens=("node:node_a",)) == "none"


def test_the_snapshot_moves_with_an_entry_a_version_or_a_retirement(db):
    _entry(db, brain="organization", subject="orgrule:spend", value={"statement": "Two approvers."})
    one = R.learned_snapshot(db, org_id=ORG, tokens=())
    assert one.startswith("learned-") and one == R.learned_snapshot(db, org_id=ORG, tokens=())
    from sqlalchemy import text
    db.execute(text("update learned_brain_entries set active=false where org_id=:o"), {"o": ORG})
    _entry(db, brain="organization", subject="orgrule:spend", version=2, value={"statement": "Three approvers."})
    two = R.learned_snapshot(db, org_id=ORG, tokens=())
    assert two != one, "a new version is a different snapshot"
    db.execute(text("update learned_brain_entries set active=false where org_id=:o"), {"o": ORG})
    assert R.learned_snapshot(db, org_id=ORG, tokens=()) == "none", "a retired entry is read no more"


def test_the_snapshot_reads_what_learned_for_would_and_no_more(db):
    _entry(db, brain="behavior", subject="node:node_a", value={"pattern_statement": "Replies on Mondays."})
    _entry(db, brain="behavior", subject="node:node_b", value={"pattern_statement": "Replies on Fridays."})
    a = R.learned_snapshot(db, org_id=ORG, tokens=("node:node_a",))
    assert a != "none" and a != R.learned_snapshot(db, org_id=ORG, tokens=("node:node_b",))
    assert R.learned_snapshot(db, org_id=ORG, tokens=("node:node_c",)) == "none"
    assert R.learned_snapshot(db, org_id=OTHER_ORG, tokens=("node:node_a",)) == "none", "another tenant's is not ours"
    assert len(_read(db, tokens=("node:node_a",)).of_family(E.BEHAVIOUR)) == 1


def test_the_snapshot_by_an_address_token_of_the_entry(db):
    _entry(db, brain="adaptive", subject="pref:x",
           value={"statement": "Keep it short.", "address": {"tokens": ["capability:founder_office.x"]}})
    assert R.learned_snapshot(db, org_id=ORG, tokens=("capability:founder_office.x",)) != "none"
    assert R.learned_snapshot(db, org_id=ORG, tokens=("capability:other",)) == "none"
