from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace

from genios_engine.api import upload_routes, workspace_routes
from genios_engine.reason import runner


class _Result:
    def __init__(self, *, rows=(), scalar=None, rowcount=1):
        self._rows = list(rows)
        self._scalar = scalar
        self.rowcount = rowcount

    def __iter__(self):
        return iter(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)

    def scalar(self):
        return self._scalar


class _Engine:
    def __init__(self, connection):
        self.connection = connection

    @contextmanager
    def begin(self):
        self.connection.events.append("begin")
        try:
            yield self.connection
        finally:
            self.connection.events.append("commit")


class _UploadConnection:
    def __init__(self):
        self.events: list[str] = []

    def execute(self, statement, _params=None):
        sql = str(statement)
        if "select storage_path from resource_uploads" in sql:
            return _Result(rows=(SimpleNamespace(storage_path=None),))
        if "select event_id from source_events" in sql:
            return _Result(rows=(SimpleNamespace(event_id="evt_1"),))
        if "delete from graph_facts" in sql:
            self.events.append("delete_facts")
        elif "delete from graph_observations" in sql:
            self.events.append("delete_observations")
        return _Result()


class _Graph:
    def __init__(self, connection):
        self.engine = _Engine(connection)
        self.connection = connection

    def bump_version(self, connection, org_id):
        assert connection is self.connection
        self.connection.events.append(f"bump:{org_id}")
        return 8


def test_upload_graph_erasure_bumps_before_graph_deletes_in_same_transaction(monkeypatch):
    connection = _UploadConnection()
    graph = _Graph(connection)
    monkeypatch.setattr(upload_routes, "_graph", graph)

    from genios_engine.platform import audit
    monkeypatch.setattr(audit, "record", lambda *_args, **_kwargs: None)

    assert upload_routes.delete_upload("org_1", "upl_1", org="org_1") == {"deleted": True}
    assert connection.events.index("bump:org_1") < connection.events.index("delete_facts")
    assert connection.events.index("bump:org_1") < connection.events.index("delete_observations")
    assert connection.events[0] == "begin"
    assert connection.events[-1] == "commit"


class _CommitmentConnection:
    def __init__(self):
        self.events: list[str] = []

    def execute(self, statement, _params=None):
        sql = str(statement)
        if "select fact_version_id from graph_facts" in sql:
            return _Result(rows=(SimpleNamespace(fact_version_id="factv_1"),))
        if "update graph_facts set valid_to" in sql:
            self.events.append("retire_fact")
        return _Result()


class _CommitmentGraph(_Graph):
    def write_fact(self, connection, **_kwargs):
        assert connection is self.connection
        self.connection.events.append("write_fact")
        return "factv_2"


def test_commitment_retirement_bumps_before_mutation_in_same_transaction(monkeypatch):
    connection = _CommitmentConnection()
    graph = _CommitmentGraph(connection)
    monkeypatch.setattr(workspace_routes, "_store", lambda: graph)

    result = workspace_routes.update_commitment(
        "org_1", "node_1", workspace_routes.CommitmentUpdate(status="fulfilled"), org="org_1")

    assert result == {"updated": True}
    assert connection.events.index("bump:org_1") < connection.events.index("retire_fact")
    assert connection.events[0] == "begin"
    assert connection.events[-1] == "commit"


def test_commitment_due_date_edit_bumps_before_fact_write(monkeypatch):
    connection = _CommitmentConnection()
    graph = _CommitmentGraph(connection)
    monkeypatch.setattr(workspace_routes, "_store", lambda: graph)

    workspace_routes.update_commitment(
        "org_1", "node_1",
        workspace_routes.CommitmentUpdate(due_date="2026-08-10T12:00:00Z"), org="org_1")

    assert connection.events.index("bump:org_1") < connection.events.index("write_fact")


def test_graph_version_guard_holds_tenant_row_share_lock():
    class _GuardConnection:
        def __init__(self):
            self.events: list[str] = []

        def execute(self, statement, params=None):
            self.events.append(str(statement))
            assert params == {"o": "org_1"}
            return _Result(scalar=12)

    connection = _GuardConnection()
    store = SimpleNamespace(engine=_Engine(connection))
    with runner._graph_version_guard(store, "org_1", 12) as stable:
        assert stable is True
        connection.events.append("publication")

    assert "for share" in connection.events[1].lower()
    assert connection.events.index("publication") < connection.events.index("commit")


def test_publication_guard_holds_and_matches_the_exact_pack_authority_revision():
    class _GuardConnection:
        def __init__(self):
            self.events: list[str] = []

        def execute(self, statement, params=None):
            sql = str(statement)
            self.events.append(sql)
            if "graph_versions" in sql:
                assert params == {"o": "org_1"}
                return _Result(scalar=12)
            assert params == {"o": "org_1", "p": "sales"}
            return _Result(scalar=7)

    connection = _GuardConnection()
    store = SimpleNamespace(engine=_Engine(connection))
    with runner._graph_version_guard(
            store, "org_1", 12, pack_id="sales", pack_authority_revision=7) as stable:
        assert stable is True

    assert sum("for share" in event.lower() for event in connection.events) == 1
    assert sum("for update" in event.lower() for event in connection.events) == 1


def test_runner_captures_graph_version_before_tenant_p90_and_retries_on_drift(monkeypatch):
    events: list[str] = []
    versions = iter((4, 5))

    class _Registry:
        def effective(self, _org_id, _pack_id):
            return ({"pack_id": "test", "version": "1", "state": "active",
                     "scoring": {}, "rules": [], "plays": {}}, "cfg_1")

    def version(*_args):
        events.append("version")
        return next(versions)

    def p90(*_args):
        events.append("p90")
        return 100.0

    monkeypatch.setattr(runner, "ensure_default", lambda *_args: None)
    monkeypatch.setattr(runner, "_pack_authority_revision", lambda *_args: 1)
    monkeypatch.setattr(runner, "_graph_version", version)
    monkeypatch.setattr(runner, "_tenant_deal_p90", p90)

    result = runner.run(
        org_id="org_1", store=SimpleNamespace(engine=object()), registry=_Registry())

    assert events == ["version", "p90", "version"]
    assert result["retry_required"] is True
    assert result["outcomes"] == {"graph_changed_retry": 1}
    assert result["pack"]["graph_version"] == 4
