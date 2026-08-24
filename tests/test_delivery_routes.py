"""Layer 5.2 · the control surface — a quiet-hours table nobody can edit is dead schema.

Thin routes over a gate that is already tested, but "thin" is where the production mistakes
live. Four things are asserted beyond the happy path because they are the ones that would
actually hurt:

  * **``/effective`` answers with the real gate**, not a re-implementation of it, so "did my
    setting work?" is a button rather than a support ticket.
  * **A refused write leaves nothing behind.** The router validates the *resolution*, not the
    body, and rolls back — so a row that is legal alone but broken in combination with an
    inherited one never reaches the table.
  * **Org scoping and the owner boundary hold**, including for a scoped API key.
  * **``/held`` explains a missing message from the row**, because by the time anyone asks, the
    clock has moved and the log has rotated.
"""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from genios_engine.api import delivery_routes as routes
from genios_engine.deliver.gate import WILDCARD
from genios_engine.platform import auth
from genios_engine.platform.auth import AuthCtx, get_auth_ctx

NIGHT = datetime(2026, 8, 7, 2, 0, tzinfo=timezone.utc)
MORNING = datetime(2026, 8, 7, 10, 0, tzinfo=timezone.utc)
ORG = "org_1"


# ── the doubled database ──────────────────────────────────────────────────────────────
class _Result:
    def __init__(self, rows=(), rowcount=None):
        self._rows = [dict(row) for row in rows]
        self.rowcount = len(self._rows) if rowcount is None else rowcount

    def mappings(self):
        return self

    def all(self):
        return list(self._rows)

    def first(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        return next(iter(self._rows[0].values())) if self._rows else None


class _Conn:
    """Answers the router's statements by substring, against a staged copy of the tables."""

    def __init__(self, db: "FakeDB", staged: dict):
        self.db = db
        self.preferences = staged

    # -- lifecycle ---------------------------------------------------------------------
    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type is None:
            self.db.preferences = self.preferences        # commit
        return False                                       # otherwise: discard = rollback

    # -- statements --------------------------------------------------------------------
    def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        p = dict(params or {})

        if sql.startswith("insert into delivery_preferences"):
            key = (p["o"], p["seat"], p["ch"])
            row = self.preferences.setdefault(
                key, {"org_id": p["o"], "seat_id": p["seat"], "channel": p["ch"],
                      "created_at": NIGHT, "updated_at": NIGHT, "updated_by": None})
            for column in routes._SETTABLE:
                if column in p:
                    row[column] = p[column]
            row["updated_by"] = p.get("by")
            return _Result(rowcount=1)

        if sql.startswith("delete from delivery_preferences"):
            key = (p["o"], p["seat"], p["ch"])
            return _Result(rowcount=1 if self.preferences.pop(key, None) else 0)

        if "from delivery_preferences" in sql and "seat_id in" in sql:
            return _Result([row for (org, seat, channel), row in self.preferences.items()
                            if org == p["o"] and seat in (p["seat"], p["any"])
                            and channel in (p["ch"], p["any"])])

        if "from delivery_preferences" in sql:
            return _Result([row for (org, _s, _c), row in self.preferences.items()
                            if org == p["o"]])

        if "timezone from orgs" in sql:
            # An org that has never been asked its timezone — the state 46 of 47 live orgs are in.
            return _Result([{"timezone": self.db.org_timezone}])

        if "from org_channels" in sql:
            return _Result([{"one": 1}] if self.db.channel_active else [])

        if "from org_seats" in sql:
            return _Result([{"one": 1}] if self.db.seat_active else [])

        if "count(*) as sent" in sql:
            return _Result([{"sent": self.db.burst, "oldest": self.db.burst_started}])

        if "from delivery_outbox" in sql:
            return _Result([row for row in self.db.outbox if row["org_id"] == p["o"]])

        raise AssertionError(f"unexpected statement: {sql}")


class FakeDB:
    def __init__(self, preferences=None, outbox=(), channel_active=True, seat_active=True,
                 burst=0, burst_started=None, org_timezone=None):
        self.preferences = dict(preferences or {})
        self.outbox = [dict(row) for row in outbox]
        self.channel_active = channel_active
        self.seat_active = seat_active
        self.burst = burst
        self.burst_started = burst_started
        self.org_timezone = org_timezone

    # the two shapes the router asks the engine for
    def connect(self):
        return _Conn(self, copy.deepcopy(self.preferences))

    def begin(self):
        return _Conn(self, copy.deepcopy(self.preferences))


class _Graph:
    def __init__(self, engine):
        self.engine = engine


def client(monkeypatch, db: FakeDB, *, scopes=None, org=ORG) -> TestClient:
    """Real routes, real credential boundary, doubled database.

    ``check_org_kill`` is stubbed because it reaches for a live engine; ``get_current_org`` and
    ``require_owner`` are left real, so the scoped-key test below exercises the actual boundary.
    """
    monkeypatch.setattr(routes, "_graph", _Graph(db))
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)

    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: AuthCtx(org_id=org, actor_id="seat_admin",
                                                             scopes=scopes)
    return TestClient(app)


def pref(seat=WILDCARD, channel=WILDCARD, **settings) -> dict:
    return {(ORG, seat, channel): {"org_id": ORG, "seat_id": seat, "channel": channel,
                                   "created_at": NIGHT, "updated_at": NIGHT,
                                   "updated_by": None, **settings}}


# ── /effective: the "did my setting work?" button ─────────────────────────────────────
def test_an_unconfigured_tenant_is_told_exactly_what_will_happen_tonight(monkeypatch):
    api = client(monkeypatch, FakeDB())
    body = api.get(f"/api/org/{ORG}/delivery/effective",
                   params={"at": NIGHT.isoformat()}).json()

    assert body["in_quiet_hours"] is True
    assert body["channel_class"] == "chat"
    assert body["verdicts"]["high"]["verdict"] == "defer"
    assert body["verdicts"]["high"]["reason_code"] == "quiet_hours"
    assert body["verdicts"]["high"]["not_before"] == "2026-08-07T08:00:00+00:00"
    # …and the one thing that is still allowed through, named as such.
    assert body["verdicts"]["critical_interrupt"]["verdict"] == "send"
    assert body["verdicts"]["critical_interrupt"]["reason_code"] == "override_band_critical"
    # A critical conclusion Layer 5 was not confident enough to flag still waits.
    assert body["verdicts"]["critical"]["verdict"] == "defer"


def test_the_same_tenant_in_the_morning_is_told_everything_sends(monkeypatch):
    api = client(monkeypatch, FakeDB())
    body = api.get(f"/api/org/{ORG}/delivery/effective",
                   params={"at": MORNING.isoformat()}).json()
    assert body["in_quiet_hours"] is False
    assert {v["verdict"] for v in body["verdicts"].values()} == {"send"}


def test_effective_reports_the_recipients_own_local_time_not_the_servers(monkeypatch):
    """A tenant in Kolkata asking "does 02:00 UTC wake me?" needs the answer in their clock."""
    api = client(monkeypatch, FakeDB(pref(tz_name="Asia/Kolkata")))
    body = api.get(f"/api/org/{ORG}/delivery/effective",
                   params={"at": NIGHT.isoformat()}).json()
    assert body["resolved"]["profile"]["timezone"] == "Asia/Kolkata"
    assert body["local_time"].startswith("2026-08-07T07:30:00")
    assert body["in_quiet_hours"] is True                       # 07:30 is still before 08:00
    assert body["verdicts"]["high"]["not_before"] == "2026-08-07T02:30:00+00:00"


def test_a_naive_instant_is_refused_rather_than_silently_read_as_utc(monkeypatch):
    """Answering about a completely different moment is worse than an error, because they
    would believe it."""
    api = client(monkeypatch, FakeDB())
    response = api.get(f"/api/org/{ORG}/delivery/effective",
                       params={"at": "2026-08-07T02:00:00"})
    assert response.status_code == 422
    assert "offset" in response.json()["detail"]


def test_an_opt_out_shows_up_as_a_suppression_at_every_band(monkeypatch):
    api = client(monkeypatch, FakeDB(pref(seat="seat_1", channel="slack", opted_out=True)))
    body = api.get(f"/api/org/{ORG}/delivery/effective",
                   params={"seat_id": "seat_1", "at": MORNING.isoformat()}).json()
    assert {v["verdict"] for v in body["verdicts"].values()} == {"suppress"}
    assert body["verdicts"]["critical_interrupt"]["reason_code"] == "recipient_opted_out"


# ── writing a rule ────────────────────────────────────────────────────────────────────
def test_a_saved_setting_takes_effect_on_the_very_next_question(monkeypatch):
    db = FakeDB()
    api = client(monkeypatch, db)
    saved = api.put(f"/api/org/{ORG}/delivery/preferences",
                    json={"tz_name": "Asia/Kolkata", "quiet_start_hour": 23})
    assert saved.status_code == 200
    assert saved.json()["scope"] == "org"
    assert sorted(saved.json()["set"]) == ["quiet_start_hour", "tz_name"]

    body = api.get(f"/api/org/{ORG}/delivery/effective",
                   params={"at": NIGHT.isoformat()}).json()
    assert body["resolved"]["profile"]["timezone"] == "Asia/Kolkata"
    assert body["resolved"]["profile"]["quiet_start_hour"] == 23
    # 02:00Z is 07:30 in Kolkata — still inside 23:00–08:00, and the window now opens at 08:00
    # local rather than at 08:00 UTC. Both halves moved, which is the point.
    assert body["local_time"].startswith("2026-08-07T07:30:00")
    assert body["in_quiet_hours"] is True
    assert body["verdicts"]["high"]["not_before"] == "2026-08-07T02:30:00+00:00"


def test_only_the_fields_actually_sent_are_written_so_null_can_mean_inherit(monkeypatch):
    """Collapsing "omitted" and "explicitly null" would make removing one override require
    deleting the row and re-typing every other setting on it."""
    db = FakeDB(pref(tz_name="Asia/Kolkata", quiet_start_hour=23))
    api = client(monkeypatch, db)
    api.put(f"/api/org/{ORG}/delivery/preferences", json={"quiet_weekends": True})
    stored = db.preferences[(ORG, WILDCARD, WILDCARD)]
    assert stored["tz_name"] == "Asia/Kolkata"                   # untouched
    assert stored["quiet_weekends"] is True

    api.put(f"/api/org/{ORG}/delivery/preferences", json={"tz_name": None})
    assert db.preferences[(ORG, WILDCARD, WILDCARD)]["tz_name"] is None   # cleared


def test_a_write_with_nothing_to_set_is_refused(monkeypatch):
    api = client(monkeypatch, FakeDB())
    response = api.put(f"/api/org/{ORG}/delivery/preferences", json={"seat_id": "seat_1"})
    assert response.status_code == 422


def test_a_refused_setting_leaves_the_table_exactly_as_it_was(monkeypatch):
    """The engine degrades a bad timezone so the drain survives; this surface refuses it so it
    is never written. Same predicate, opposite responses, each correct for its layer."""
    db = FakeDB(pref(tz_name="Asia/Kolkata"))
    api = client(monkeypatch, db)
    response = api.put(f"/api/org/{ORG}/delivery/preferences",
                       json={"tz_name": "Amercia/New_York"})
    assert response.status_code == 422
    assert "tz_name" in response.json()["detail"]
    assert db.preferences[(ORG, WILDCARD, WILDCARD)]["tz_name"] == "Asia/Kolkata"


def test_a_row_that_is_only_broken_in_combination_is_still_refused(monkeypatch):
    """This is what validating the *resolution* buys over validating the body. Nine-to-nine is
    a legal pair of numbers and an all-day quiet window once it merges with the org's row."""
    db = FakeDB(pref(quiet_end_hour=9))
    api = client(monkeypatch, db)
    response = api.put(f"/api/org/{ORG}/delivery/preferences",
                       json={"seat_id": "seat_1", "quiet_start_hour": 9})
    assert response.status_code == 422
    assert "quiet_start_hour" in response.json()["detail"]
    assert (ORG, "seat_1", WILDCARD) not in db.preferences


def test_a_stop_and_a_pause_cannot_both_be_stored(monkeypatch):
    db = FakeDB()
    api = client(monkeypatch, db)
    response = api.put(f"/api/org/{ORG}/delivery/preferences",
                       json={"delivery_enabled": False,
                             "hold_until": MORNING.isoformat()})
    assert response.status_code == 422
    assert db.preferences == {}


def test_a_hold_without_an_offset_is_refused(monkeypatch):
    api = client(monkeypatch, FakeDB())
    response = api.put(f"/api/org/{ORG}/delivery/preferences",
                       json={"hold_until": "2026-08-10T09:00:00"})
    assert response.status_code == 422
    assert "offset" in response.json()["detail"]


def test_clearing_a_rule_makes_its_settings_inherit_again(monkeypatch):
    db = FakeDB({**pref(tz_name="UTC"), **pref(seat="seat_1", tz_name="Asia/Kolkata")})
    api = client(monkeypatch, db)
    assert api.get(f"/api/org/{ORG}/delivery/effective",
                   params={"seat_id": "seat_1"}).json()["resolved"]["profile"]["timezone"] \
        == "Asia/Kolkata"

    deleted = api.delete(f"/api/org/{ORG}/delivery/preferences/seat_1/{WILDCARD}")
    assert deleted.json()["deleted"] == 1
    assert api.get(f"/api/org/{ORG}/delivery/effective",
                   params={"seat_id": "seat_1"}).json()["resolved"]["profile"]["timezone"] == "UTC"


# ── the boundary ──────────────────────────────────────────────────────────────────────
def test_a_caller_cannot_read_or_write_another_tenants_delivery_rules(monkeypatch):
    api = client(monkeypatch, FakeDB(), org="org_other")
    assert api.get(f"/api/org/{ORG}/delivery/effective").status_code == 403
    assert api.get(f"/api/org/{ORG}/delivery/preferences").status_code == 403
    assert api.put(f"/api/org/{ORG}/delivery/preferences",
                   json={"quiet_enabled": False}).status_code == 403


def test_a_scoped_key_cannot_silence_a_tenant(monkeypatch):
    """A rule at ('*','*') mutes an entire org, so the write boundary is owner-only."""
    db = FakeDB()
    api = client(monkeypatch, db, scopes=["cards:read"])
    assert api.put(f"/api/org/{ORG}/delivery/preferences",
                   json={"delivery_enabled": False}).status_code == 403
    assert db.preferences == {}


def test_the_settings_screen_never_has_to_explain_the_wildcard(monkeypatch):
    db = FakeDB({**pref(), **pref(channel="slack"), **pref(seat="seat_1"),
                 **pref(seat="seat_1", channel="slack")})
    api = client(monkeypatch, FakeDB(db.preferences))
    scopes = {row["scope"] for row in
              api.get(f"/api/org/{ORG}/delivery/preferences").json()["preferences"]}
    assert scopes == {"org", "org_channel", "seat", "seat_channel"}


# ── /held: why didn't I get told? ─────────────────────────────────────────────────────
def test_held_separates_a_hold_from_a_refusal_and_names_who_did_it(monkeypatch):
    """Cancelled means the subject stopped being live; suppressed means somebody said no.
    An operator seeing `suppressed` should look at preferences, not at Slack's status page."""
    db = FakeDB(outbox=[
        {"org_id": ORG, "card_id": "card_1", "channel": "slack", "recipient": "seat_1",
         "band": "high", "channel_class": "chat", "interrupt": False, "status": "queued",
         "defer_count": 2, "gate_unit": "timing", "gate_reason": "quiet_hours",
         "next_attempt_at": MORNING, "created_at": NIGHT, "last_error": None},
        {"org_id": ORG, "card_id": "card_2", "channel": "slack", "recipient": "seat_2",
         "band": "critical", "channel_class": "chat", "interrupt": True, "status": "suppressed",
         "defer_count": 0, "gate_unit": "policy", "gate_reason": "recipient_opted_out",
         "next_attempt_at": NIGHT, "created_at": NIGHT - timedelta(hours=1),
         "last_error": "policy:recipient_opted_out"},
    ])
    body = client(monkeypatch, db).get(f"/api/org/{ORG}/delivery/held").json()

    assert (body["deferred"], body["suppressed"]) == (1, 1)
    waiting, refused = body["held"]
    assert waiting["held_by"] == "timing" and waiting["reason_code"] == "quiet_hours"
    assert waiting["retryable"] is True and waiting["defer_count"] == 2
    assert waiting["next_attempt_at"] == MORNING.isoformat()
    assert refused["held_by"] == "policy" and refused["reason_code"] == "recipient_opted_out"
    assert refused["retryable"] is False


def test_held_reads_the_row_rather_than_a_log(monkeypatch):
    """By the time anybody asks, the clock has moved on and the log has rotated."""
    import inspect
    source = inspect.getsource(routes.held_messages)
    assert "gate_unit" in source and "gate_reason" in source
    assert "delivery_outbox" in source


@pytest.mark.parametrize("path", ["preferences", "effective", "held"])
def test_every_read_needs_a_configured_database_rather_than_pretending(monkeypatch, path):
    monkeypatch.setattr(routes, "_graph", None)
    monkeypatch.setattr(auth, "check_org_kill", lambda org_id: None)
    app = FastAPI()
    app.include_router(routes.router)
    app.dependency_overrides[get_auth_ctx] = lambda: AuthCtx(org_id=ORG, actor_id="a")
    assert TestClient(app).get(f"/api/org/{ORG}/delivery/{path}").status_code == 400


# ── schema conformance for the surface itself ─────────────────────────────────────────
def _migrations() -> str:
    from pathlib import Path
    root = Path(__file__).resolve().parents[1] / "migrations"
    return "\n".join(p.read_text() for p in sorted(root.glob("*.sql")))


def test_every_column_this_router_writes_actually_exists():
    """`_SETTABLE` is interpolated straight into the upsert. A name that drifted from the
    migration would not fail a unit test — it would fail at 3am on a tenant's first save."""
    import re
    body = _migrations().split(
        "create table if not exists delivery_preferences (")[1].split("\n);")[0]
    columns = set(re.findall(r"^\s{4}([a-z_]+)\s", body, re.MULTILINE))
    assert set(routes._SETTABLE) <= columns, sorted(set(routes._SETTABLE) - columns)


def test_every_column_the_held_view_reads_actually_exists():
    """The held query is hand-written SQL against a table two migrations built. Both halves are
    checked: the column is named in the query, and some migration creates it."""
    import inspect
    import re

    source = inspect.getsource(routes.held_messages)
    sql = _migrations()
    outbox_body = sql.split("create table if not exists delivery_outbox (")[1].split("\n);")[0]

    for column in ("card_id", "channel", "recipient", "band", "channel_class", "interrupt",
                   "status", "defer_count", "gate_unit", "gate_reason", "next_attempt_at",
                   "created_at", "last_error"):
        assert column in source, f"held query no longer reads {column} — update this lock"
        assert (f"add column if not exists {column} " in sql
                or re.search(rf"^\s{{4}}{column}\s", outbox_body, re.MULTILINE)), \
            f"{column} is read but no migration creates it"
