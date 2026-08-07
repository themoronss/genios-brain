from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from genios_engine.deliver.agent_api import claim, result


NOW = datetime(2026, 8, 6, 12, tzinfo=timezone.utc)


class _Result:
    def __init__(self, row=None, *, rowcount=1):
        self.row = row
        self.rowcount = rowcount

    def mappings(self):
        return self

    def first(self):
        return self.row


class _Connection:
    def __init__(self, *, claim=None, card=None, claim_won=True, holder=None):
        self.claim = claim
        self.card = card
        self.claim_won = claim_won
        self.holder = holder
        self.calls: list[tuple[str, dict]] = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.calls.append((sql, dict(params or {})))
        if "from agent_claims" in sql and "for update" in sql:
            return _Result(self.claim)
        if "select k.card_id, k.state" in sql:
            return _Result(self.card)
        if "returning agent_id" in sql:
            return _Result({"agent_id": "agent_1"} if self.claim_won else None)
        if "select agent_id, expires_at from agent_claims" in sql:
            return _Result(self.holder)
        return _Result()


class _Store:
    def __init__(self, connection):
        self.connection = connection
        self.engine = self

    @contextmanager
    def begin(self):
        yield self.connection


def _claim(**overrides):
    value = {
        "card_id": "card_1",
        "expires_at": NOW + timedelta(minutes=10),
        "released_at": None,
        "result": None,
    }
    value.update(overrides)
    return value


def test_agent_result_rejects_non_owner_before_metering_or_mutation():
    connection = _Connection(claim=None)

    response = result(
        _Store(connection), "org_1", "sig_1", "agent_intruder", "done", eval_time=NOW)

    assert response == {"ok": False, "status": 403, "error": "claim_not_owned"}
    assert len(connection.calls) == 1
    assert connection.calls[0][1] == {
        "o": "org_1", "s": "sig_1", "a": "agent_intruder"}


def test_agent_result_rejects_expired_claim_without_touching_card_or_signal():
    connection = _Connection(claim=_claim(expires_at=NOW))

    response = result(
        _Store(connection), "org_1", "sig_1", "agent_1", "failed", eval_time=NOW)

    assert response == {"ok": False, "status": 409, "error": "claim_expired"}
    assert len(connection.calls) == 1


def test_agent_result_done_is_tenant_scoped_and_authority_revalidated():
    connection = _Connection(claim=_claim(), card={"card_id": "card_1", "state": "claimed"})

    response = result(
        _Store(connection), "org_1", "sig_1", "agent_1", "done", eval_time=NOW)

    sql = "\n".join(statement.lower() for statement, _ in connection.calls)
    assert response == {"ok": True, "status": 200, "result": "done"}
    assert "from graph_versions" in sql and "for share" in sql
    assert "reasoning_run_outputs" in sql
    assert "update agent_claims" in sql
    assert "where org_id=:o and signal_id=:s and agent_id=:a" in sql
    assert "update cards set state='acted'" in sql and "org_id=:o" in sql
    assert "update signals set status='acted'" in sql and "status='open'" in sql


def test_revoked_authority_records_owned_late_result_but_does_not_resolve_signal():
    connection = _Connection(claim=_claim(), card=None)

    response = result(
        _Store(connection), "org_1", "sig_1", "agent_1", "done",
        detail={"provider_id": "sent_1"}, eval_time=NOW)

    sql = "\n".join(statement.lower() for statement, _ in connection.calls)
    assert response["code"] == "V-08" and response["note"] == "late_result_noop"
    assert "update agent_claims" in sql and "agent.result.late" in sql
    assert "update cards set state='acted'" not in sql
    assert "update signals set status='acted'" not in sql


def test_agent_result_status_is_closed_enum():
    connection = _Connection(claim=_claim())

    response = result(
        _Store(connection), "org_1", "sig_1", "agent_1", "maybe", eval_time=NOW)

    assert response == {"ok": False, "status": 422, "error": "invalid_result_status"}
    assert connection.calls == []


def test_agent_claim_holds_graph_and_authority_rows_until_the_grant_commits():
    connection = _Connection(card={
        "card_id": "card_1",
        "state": "queued",
        "expires_at": NOW + timedelta(hours=1),
        "approval_required": False,
    })

    response = claim(
        _Store(connection), "org_1", "sig_1", "agent_1", eval_time=NOW)

    sql = "\n".join(statement.lower() for statement, _ in connection.calls)
    assert response["ok"] is True
    assert "select graph_version from graph_versions" in sql
    assert "for share" in sql
    assert "for update of k, s" in sql
    assert "for share of rr, ro, selected_rc, rcap, authority_ctx" in sql
    assert "authority_cfg, authority_pack" in sql


def test_second_agent_gets_visible_v07_contention_instead_of_false_404():
    connection = _Connection(
        card={
            "card_id": "card_1",
            "state": "claimed",
            "expires_at": NOW + timedelta(hours=1),
            "approval_required": False,
        },
        claim_won=False,
        holder={"agent_id": "agent_owner", "expires_at": NOW + timedelta(minutes=10)},
    )

    response = claim(
        _Store(connection), "org_1", "sig_1", "agent_other", eval_time=NOW)

    assert response == {
        "ok": False,
        "status": 409,
        "code": "V-07",
        "holder": "agent_owner",
        "expires_at": (NOW + timedelta(minutes=10)).isoformat(),
    }
    card_query = next(statement for statement, _ in connection.calls
                      if "select k.card_id, k.state" in statement)
    assert "'claimed'" in card_query
