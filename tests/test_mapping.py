"""Custom-source mapping: introspect → propose → confirm → active/list (skips without DB)."""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    not os.environ.get("GENIOS_TEST_DATABASE_URL"),
    reason="GENIOS_TEST_DATABASE_URL not set")

_SAMPLES = [{"body": "hello", "created_at": "2026-01-01T10:00:00",
             "assignee": "priya@x.io", "labels": ["a"], "extra": 5}]


def test_mapping_flow():
    from genios_engine.api import mapping_routes as M
    from genios_engine.context.graph_store import GraphStore
    from genios_engine.platform.migrate import apply_migrations
    url = os.environ["GENIOS_TEST_DATABASE_URL"]
    apply_migrations(database_url=url)
    M._graph = GraphStore(url)
    org = "map_org"
    with M._graph.engine.begin() as c:
        c.execute(text("insert into orgs (id,name) values (:o,'S') on conflict do nothing"),
                  {"o": org})

    req = M.IntrospectRequest(source_type="zendesk", samples=_SAMPLES)
    intro = M.introspect(req, org=org)
    kinds = {f["name"]: f["inferred_type"] for f in intro["fields"]}
    assert kinds["created_at"] == "datetime" and kinds["extra"] == "number"

    rows = {r["canonical_field"]: r["proposed_source_field"] for r in M.propose(req, org=org)["rows"]}
    assert rows == {"content": "body", "timestamp": "created_at",
                    "owner": "assignee", "tags": "labels"}

    c1 = M.confirm(M.ConfirmRequest(connection_id="c1", source_type="zendesk",
                                    confirmed_by="u", samples=_SAMPLES), org=org)
    assert c1["version"] == 1 and c1["field_map"]["content"]["source_field"] == "body"
    assert M.get_active(connection_id="c1", source_type="zendesk", org=org)["version"] == 1

    # required-field guard: content unmapped → 422
    with pytest.raises(Exception):
        M.confirm(M.ConfirmRequest(connection_id="c2", source_type="bare",
                                   confirmed_by="u", samples=[{"foo": "bar"}],
                                   edits=[M.Edit(canonical_field="content", source_field=None)]),
                  org=org)

    # re-confirm bumps version, keeps exactly one active
    c2 = M.confirm(M.ConfirmRequest(connection_id="c1", source_type="zendesk",
                                    confirmed_by="u", samples=_SAMPLES), org=org)
    assert c2["version"] == 2 and M.list_mappings(org=org)["count"] == 1
