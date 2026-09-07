"""LAW 3, ATTACKED — the Expert Brain is human territory, and the DATABASE is what says so.

Written by the J0-J4 gate. `tests/packs/brains/` already proves that `brain='expert'` is refused;
this file attacks the same law from the four other directions an attacker would actually take, and
each one is a different mechanism rather than a restatement of the first:

  * six SPELLINGS of the expert brain, including the casing and trailing-space variants a hand-run
    SQL statement produces, so the constraint is proven to be a closed whitelist and not a
    lowercase 'expert' denylist;
  * `learning_objects.target`, which is the rung BEFORE a brain write and has its own constraint —
    a proposal that cannot be created cannot be published;
  * `LearningTarget`, so the refusal is not merely enforced at the database but unrepresentable in
    the type the pipeline passes around;
  * the KNOWLEDGE_SUGGESTION sink under BOTH governance destinations, because must-not-regress #4
    is not "review is the usual path" but "there is no other path" — the PROMOTED branch must also
    reach no brain.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

pytestmark = pytest.mark.pg
NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def _orgs(pg_store):
    """learned_brain_entries carries an org FK; the CHECK is what this file attacks, so the row
    has to be legal in every other respect or the FK answers first and proves nothing."""
    with pg_store.engine.begin() as conn:
        cols = conn.execute(text(
            "select column_name, data_type, is_nullable, column_default from "
            "information_schema.columns where table_name='orgs'")).mappings().all()
        for org in ("gate_x", "gate_ok", "gate_o", "gate_ks"):
            names, holes, values = [], [], {}
            for r in cols:
                if r["is_nullable"] == "YES" or r["column_default"]:
                    if r["column_name"] != "id":
                        continue
                names.append(r["column_name"]); holes.append(f":{r['column_name']}")
                k = r["data_type"]
                values[r["column_name"]] = (
                    org if r["column_name"] == "id" else
                    "2026-01-01T00:00:00Z" if ("time" in k or "date" in k) else
                    0 if ("int" in k or "numeric" in k or "double" in k) else
                    False if k == "boolean" else "{}" if k in ("json", "jsonb") else "scratch")
            conn.execute(text(f"insert into orgs ({', '.join(names)}) values "
                              f"({', '.join(holes)}) on conflict (id) do nothing"), values)
INSERT = ("insert into learned_brain_entries (org_id, brain, subject, version, learning_id, "
          "value, active, visibility_scope, visibility) values "
          "(:o,:b,:s,1,'lrn_x','{}'::jsonb,true,'org','{}'::jsonb)")


def test_gate_the_database_itself_refuses_brain_expert(pg_store):
    for brain in ("expert", "Expert", "EXPERT", "expert ", "organisation", "domain"):
        with pytest.raises((IntegrityError, DBAPIError)) as exc:
            with pg_store.engine.begin() as conn:
                conn.execute(text(INSERT), {"o": "gate_x", "b": brain, "s": "sales.heu.x"})
        assert "learned_brain_no_expert" in str(exc.value), brain
        print(f"GATE-LAW3 brain={brain!r} refused by learned_brain_no_expert")
    for brain in ("organization", "behavior", "adaptive"):
        with pg_store.engine.begin() as conn:
            conn.execute(text("delete from learned_brain_entries where org_id='gate_ok'"))
            conn.execute(text(INSERT), {"o": "gate_ok", "b": brain, "s": "s_" + brain})
    print("GATE-LAW3 the three legal brains still insert")


def test_gate_learning_objects_refuse_target_expert(pg_store):
    with pytest.raises((IntegrityError, DBAPIError)) as exc:
        with pg_store.engine.begin() as conn:
            conn.execute(text(
                "insert into learning_objects (org_id, learning_id, unit, target, subject, "
                "proposed_value, evidence, visibility, policy_key, first_seen_at, "
                "last_seen_at, semantic_hash, visibility_scope) "
                "values ('gate_o','lrn_e','u','expert','s','{}'::jsonb,'{}'::jsonb,"
                "'{}'::jsonb,'k',:a,:a,'h','org')"), {"a": NOW})
    assert "learning_objects_no_expert" in str(exc.value)
    print("GATE-LAW3 learning_objects target='expert' refused by learning_objects_no_expert")


def test_gate_no_python_enum_member_can_name_the_expert_brain():
    from genios_engine.contracts.learning import LearningTarget
    names = {m.value for m in LearningTarget}
    print("GATE-LAW3 LearningTarget members:", sorted(names))
    assert "expert" not in names


def test_gate_knowledge_suggestions_stop_at_human_review(pg_store):
    """MUST-NOT-REGRESS #4 — the sink writes state='human_review' and reaches no brain."""
    from genios_engine.contracts.learning import (LearningEvidence, LearningObject,
                                                  LearningState, LearningTarget,
                                                  Visibility, VisibilityScope)
    from genios_engine.feedback.publisher import publish

    obj = LearningObject(
        org_id="gate_ks", unit="gate_unit", target=LearningTarget.KNOWLEDGE_SUGGESTION,
        subject="sales.heu.rewrite_me", proposed_value={"statement": "a proposed edit"},
        evidence=LearningEvidence(observations=5, independent_refs=3, distinct_days=3,
                                  positive=5, negative=0, confidence_bp=9000,
                                  distinct_entities=3),
        visibility=Visibility(scope=VisibilityScope.ORGANIZATION, derived_from=("gate",)),
        first_seen_at=NOW, last_seen_at=NOW, policy_key="k")
    for target_state in (LearningState.HUMAN_REVIEW, LearningState.PROMOTED):
        with pg_store.engine.begin() as conn:
            sink = publish(conn, obj, target_state=target_state, at=NOW)
        print(f"GATE-LAW3 knowledge target_state={target_state.value} -> sink={sink}")
    with pg_store.engine.connect() as conn:
        states = conn.execute(text(
            "select state from knowledge_suggestions where org_id='gate_ks'")).scalars().all()
        brains = conn.execute(text(
            "select count(*) from learned_brain_entries where org_id='gate_ks'")).scalar()
    print("GATE-LAW3 knowledge_suggestions states:", states, "brain rows for that org:", brains)
    assert set(states) == {"human_review"}
    assert brains == 0


def test_gate_the_api_reports_expert_brain_changed_false_on_every_route():
    """The publisher-side half of must-not-regress #4, read from the source of the routes."""
    import pathlib, re
    src = pathlib.Path("genios_engine/api/learning_routes.py").read_text()
    values = set(re.findall(r'"expert_brain_changed":\s*(\w+)', src))
    print("GATE-LAW3 expert_brain_changed literals in learning_routes.py:", values)
    assert values == {"False"}
