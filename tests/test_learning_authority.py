from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from genios_engine.feedback.calibrate import _PRECISION_SQL
from genios_engine.reason.foresight import play_win_rates


NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


class _Result:
    def fetchall(self):
        return []


class _Connection:
    def __init__(self):
        self.sql = ""
        self.params = None

    def execute(self, statement, params=None):
        self.sql = str(statement)
        self.params = dict(params or {})
        return _Result()


class _Engine:
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def connect(self):
        yield self.connection


class _Store:
    def __init__(self, connection):
        self.engine = _Engine(connection)


def _assert_historical_audit_binding(sql: str) -> None:
    lowered = sql.lower()
    assert "join reasoning_runs rr" in lowered
    assert "selected_rc.candidate_id=ro.selected_candidate_id" in lowered
    assert "s.authority_binding_version=1" in lowered
    assert "ro.decision_hash=s.reasoning_decision_hash" in lowered
    assert "selected_rc.disposition='eligible' and selected_rc.rank_position=1" in lowered
    assert "s.authority_expires_at =" in lowered
    assert "s.authority_expires_at > :authority_time" not in lowered


def test_calibration_cannot_learn_from_unbound_or_post_expiry_card_events():
    sql = str(_PRECISION_SQL)

    _assert_historical_audit_binding(sql)
    assert "ce.occurred_at >= ac.card_created_at" in sql.lower()
    assert "ce.occurred_at <= :as_of" in sql.lower()
    assert "where occurred_at >= :since" in sql.lower()
    assert "ce.occurred_at < ac.authority_expires_at" in sql.lower()
    assert "ce.kind='human.card_action'" in sql.lower()
    assert "row_number() over (partition by je.card_id" in sql.lower()
    assert "join card_feedback_verdicts" in sql.lower()
    assert "from ranked_judgments where judgment_position=1" in sql.lower()
    assert "from canonical_judgments" in sql.lower()
    assert "regexp_replace(rr.capability_id" in sql.lower()
    assert "group by s.rule_id" not in sql.lower()


def test_play_win_rates_group_by_the_audited_selected_candidate():
    connection = _Connection()

    assert play_win_rates(_Store(connection), "org_1", eval_time=NOW) == {}

    _assert_historical_audit_binding(connection.sql)
    assert "selected_rc.play_id as play" in connection.sql.lower()
    assert "ce.occurred_at >= ac.card_created_at" in connection.sql.lower()
    assert "ce.occurred_at <= :as_of" in connection.sql.lower()
    assert "ce.occurred_at < ac.authority_expires_at" in connection.sql.lower()
    assert "ce.kind='human.card_action'" in connection.sql.lower()
    assert "from canonical_judgments" in connection.sql.lower()
    assert connection.params == {"o": "org_1", "as_of": NOW}


def test_learning_migration_quarantines_unknown_lineage_and_uses_composite_authority_fks():
    sql = (Path(__file__).resolve().parents[1] /
           "migrations/0034_l4_learning_authority.sql").read_text().lower()
    assert "__legacy_unknown__" in sql
    assert "set active = false" in sql
    assert "foreign key (calibration_run_id, org_id, pack_id, pack_version)" in sql
    assert "references calibration_runs(run_id, org_id, pack_id, pack_version)" in sql
    assert "card_build_claims" in sql
    assert "alter column schema_version set default 2" in sql
