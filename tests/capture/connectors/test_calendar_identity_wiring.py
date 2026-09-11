"""Calendar uses the same seats, owner and connected-mailbox identity as the drain."""
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, text

from genios_engine.platform import wiring


@pytest.fixture
def identities(monkeypatch):
    engine = create_engine("sqlite://")
    with engine.begin() as conn:
        for ddl in (
            "create table orgs (id text, email text)",
            "create table org_seats (org_id text, email text, active boolean)",
            "create table connections (org_id text, external_account_id text)",
        ):
            conn.execute(text(ddl))
        conn.execute(text("insert into orgs values ('o','owner@example.com'), ('other','foreign@example.net')"))
        conn.execute(text("insert into org_seats values ('o','seat@example.com',true), ('o','inactive@example.com',false)"))
        conn.execute(text("insert into connections values ('o','mailbox@example.com')"))
    monkeypatch.setattr(wiring, "get_settings", lambda: SimpleNamespace(
        use_real_composio=True, composio_api_key="fixture", composio_gmail_account=""))
    monkeypatch.setattr(wiring, "make_graph_store", lambda: SimpleNamespace(engine=engine))
    yield engine
    engine.dispose()


def _connector():
    return wiring.make_connector_for(SimpleNamespace(
        org_id="o", source_type="gcal", composio_user_id="fixture", config={}))


def _actor(connector, email):
    return connector._to_raw({"id": "event", "organizer": {"email": email},
        "start": {"dateTime": "2026-08-11T10:00:00Z"}}).actor_type


@pytest.mark.parametrize("email, expected", [
    ("owner@example.com", "internal_user"),
    ("seat@example.com", "internal_user"),
    ("mailbox@example.com", "internal_user"),
    ("inactive@example.com", "external_contact"),
    ("foreign@example.net", "external_contact"),
    ("theresa.hoffmann@antler.co", "external_contact"),
])
def test_the_calendar_factory_injects_only_this_tenants_authoritative_identity_set(identities, email, expected):
    assert _actor(_connector(), email) == expected


def test_an_unavailable_identity_read_does_not_break_existing_calendar_ingestion(identities):
    with identities.begin() as conn:
        conn.execute(text("drop table org_seats"))
    assert _actor(_connector(), "external@example.net") == "internal_user"


def test_a_factory_without_a_database_preserves_its_previous_calendar_behaviour(identities, monkeypatch):
    monkeypatch.setattr(wiring, "make_graph_store", lambda: None)
    assert _actor(_connector(), "external@example.net") == "internal_user"
