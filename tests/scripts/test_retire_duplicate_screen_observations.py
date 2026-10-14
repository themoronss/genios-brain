"""G-2 (the STEP-17/18 second crosscheck) · a pre-0211 duplicate screen observation is retired.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/scripts/test_retire_duplicate_screen_observations.py -q

`yc2_w27_s1718` M48.C2.L-data.V2.U21 (`scripts/retire_duplicate_screen_observations.py`).

⛔ WHAT WAS WRONG. STEP-18 B13 (`reason/moments/screen_memory._retire`) retires a follow-up's
previous observation only when the row already names one (`observation_id`, 0211). A follow-up
rewritten more than once BEFORE 0211 landed — or, exactly the same shape, a row whose
`observation_id` is cleared back to null between writes — stayed as many `active` observations as
it had versions, and nothing ever retires the earlier ones retroactively: the first write after
0211 only retires the ONE it itself replaces.

This builds that exact shape with the real write path (`followups.upsert` + `screen_memory.write_items`,
`observation_id` nulled out after each write — what a row from before 0211 looks like), then proves
the one-off finds it, keeps the latest, and writes the survivor's id so an ordinary rewrite retires
it from here on.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text

from genios_engine.reason.moments import followups
from genios_engine.reason.moments.screen_memory import write_items
from scripts import retire_duplicate_screen_observations as R

ORG = "org_s1718_dup_screen_obs"
ORG2 = "org_s1718_dup_screen_obs_2"
SEAT = "seat_s1718"
THREAD = "wa:priya"
T0 = datetime(2026, 10, 12, 9, 0, tzinfo=timezone.utc)


@pytest.fixture
def engine(pg_store, live_db_url):
    if not live_db_url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the graph is Postgres's")
    _reset(pg_store.engine)
    with pg_store.engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'Duplicate screen obs')"), {"o": ORG})
    yield pg_store.engine
    _reset(pg_store.engine)


def _reset(engine) -> None:
    with engine.begin() as c:
        for table in ("graph_source_refs", "graph_observations", "screen_followups"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG})


def _upsert(engine, note: str, *, now: datetime, due: datetime | None = None) -> dict:
    return followups.upsert(engine, org_id=ORG, seat_id=SEAT, kind="ask", note=note, who=None,
                            due_at=due, thread_key=THREAD, app="whatsapp", topic="the deck",
                            tz_name=None, now=now)


def _write(engine, event_id: str, *, now: datetime) -> int:
    return write_items(engine, org_id=ORG, seat_id=SEAT, seat_email=None, thread_key=THREAD,
                       event_id=event_id, now=now)


def _forget(engine, followup_id: str) -> None:
    """What a row from before 0211 looked like: it never named the observation it became."""
    with engine.begin() as c:
        c.execute(text("update screen_followups set observation_id = null where id = :i"),
                  {"i": followup_id})


def _observations(engine, followup_id: str) -> list[tuple[str, str, str]]:
    """(status, observation_id, the words) for every observation of one follow-up, oldest first."""
    with engine.connect() as c:
        rows = c.execute(text(
            "select o.status, o.observation_id, r.evidence from graph_observations o "
            "join graph_source_refs r on r.org_id = o.org_id and r.observation_id = o.observation_id "
            "where o.org_id = :o order by o.created_at, o.observation_id"), {"o": ORG}).all()
    out = []
    for status, obs_id, evidence in rows:
        evidence = evidence if isinstance(evidence, dict) else json.loads(evidence)
        if evidence.get("followup_id") == followup_id:
            out.append((status, obs_id, evidence.get("text")))
    return out


def _pre_0211_duplicate(engine) -> str:
    """Three active observations for one follow-up — `write_items` ran three times and
    `observation_id` was forgotten after each, the pre-0211 shape."""
    item = _upsert(engine, "Send Priya the deck", now=T0)
    assert _write(engine, "evt_1", now=T0) == 1
    _forget(engine, item["id"])
    _upsert(engine, "Send Priya the deck and the model", now=T0 + timedelta(hours=1))
    assert _write(engine, "evt_2", now=T0 + timedelta(hours=1)) == 1
    _forget(engine, item["id"])
    _upsert(engine, "Send Priya the deck, the model and the budget",
           now=T0 + timedelta(hours=2))
    assert _write(engine, "evt_3", now=T0 + timedelta(hours=2)) == 1
    _forget(engine, item["id"])
    assert [s for s, _obs, _t in _observations(engine, item["id"])] == ["active"] * 3
    return item["id"]


def test_the_probe_finds_the_duplicate(engine):
    fid = _pre_0211_duplicate(engine)
    with engine.connect() as c:
        assert R.duplicates(c, ORG) == [(ORG, fid, 3)]


def test_the_dry_run_names_it_and_writes_nothing(engine, live_db_url, capsys):
    fid = _pre_0211_duplicate(engine)
    assert R.main(["--database-url", live_db_url, "--org", ORG]) == 0
    out = capsys.readouterr().out
    assert "would retire the extra observation(s) of 1 follow-up(s) in 1 org(s)" in out, out
    assert fid in out and "3 active, keeping the latest" in out and "DRY RUN" in out
    assert [s for s, _obs, _t in _observations(engine, fid)] == ["active"] * 3, (
        "a dry run writes nothing")


def test_apply_keeps_the_latest_and_supersedes_the_rest(engine, live_db_url, capsys):
    fid = _pre_0211_duplicate(engine)
    assert R.main(["--database-url", live_db_url, "--org", ORG, "--apply"]) == 0
    assert "superseded 2 observation(s) across 1 follow-up(s) in 1 org(s)" in capsys.readouterr().out
    seen = _observations(engine, fid)
    assert [s for s, _obs, _t in seen] == ["superseded", "superseded", "active"], seen
    assert seen[-1][2] == "Send Priya the deck, the model and the budget", (
        "the survivor is the latest version, not an arbitrary one")
    with engine.connect() as c:
        named = c.execute(text("select observation_id from screen_followups where id = :i"),
                          {"i": fid}).scalar()
    assert named == seen[-1][1], "the survivor's id is written back, so an ordinary rewrite retires it"
    with engine.connect() as c:
        assert R.duplicates(c, ORG) == [], "a second run finds nothing"


def test_an_ordinary_rewrite_after_apply_retires_the_survivor_the_usual_way(engine, live_db_url):
    """The point of writing the survivor's id back: `screen_memory._retire` takes it from here."""
    fid = _pre_0211_duplicate(engine)
    R.main(["--database-url", live_db_url, "--org", ORG, "--apply"])
    _upsert(engine, "Send Priya the deck, the model, the budget and the timeline",
           now=T0 + timedelta(hours=3))
    assert _write(engine, "evt_4", now=T0 + timedelta(hours=3)) == 1
    seen = _observations(engine, fid)
    assert [s for s, _obs, _t in seen] == ["superseded", "superseded", "superseded", "active"], seen


def test_a_follow_up_with_one_active_observation_is_not_touched(engine):
    """The ordinary case (0211 working as designed) is not this script's business."""
    item = _upsert(engine, "Send Priya the deck", now=T0)
    _write(engine, "evt_1", now=T0)
    with engine.connect() as c:
        assert R.duplicates(c, ORG) == []


def test_the_script_names_its_target_and_never_the_configured_database(monkeypatch):
    from scripts._db import TARGET_URL_ENV, UnsafeDatabaseTarget

    monkeypatch.delenv(TARGET_URL_ENV, raising=False)
    with pytest.raises(UnsafeDatabaseTarget):
        R.main(["--org", ORG])


def _raw_duplicate(engine, *, org: str, followup_id: str, n: int, start: datetime) -> None:
    """`n` active observations for `followup_id`, inserted directly (bypassing the real write
    path) — enough to prove `--org` scoping without the full `followups`/`screen_memory` setup."""
    with engine.begin() as c:
        for i in range(n):
            obs = f"obs_{org}_{followup_id}_{i}"
            c.execute(text(
                "insert into graph_observations (observation_id, org_id, kind, occurred_at, status) "
                "values (:id, :o, 'screen.ask', :at, 'active')"),
                {"id": obs, "o": org, "at": start + timedelta(hours=i)})
            c.execute(text(
                "insert into graph_source_refs (source_ref_id, org_id, observation_id, event_id, "
                "source, evidence) values (:r, :o, :obs, :e, 'screen_insight', cast(:ev as jsonb))"),
                {"r": f"ref_{obs}", "o": org, "obs": obs, "e": f"evt_{obs}",
                 "ev": json.dumps({"followup_id": followup_id})})


@pytest.fixture
def other_org(engine):
    with engine.begin() as c:
        c.execute(text("insert into orgs (id, name) values (:o, 'Other org')"), {"o": ORG2})
    yield ORG2
    with engine.begin() as c:
        for table in ("graph_source_refs", "graph_observations", "screen_followups"):
            c.execute(text(f"delete from {table} where org_id = :o"), {"o": ORG2})
        c.execute(text("delete from orgs where id = :o"), {"o": ORG2})


def test_org_scoping_never_touches_another_orgs_duplicates(engine, other_org):
    fid = _pre_0211_duplicate(engine)
    _raw_duplicate(engine, org=other_org, followup_id="fu_other", n=3, start=T0)
    moved = R.retire(engine, ORG)
    assert {f for _o, f, _obs, _n in moved} == {fid}, "only ORG's own follow-up moved"
    with engine.connect() as c:
        other_active = c.execute(text(
            "select count(*) from graph_observations where org_id = :o and status = 'active'"),
            {"o": other_org}).scalar()
    assert other_active == 3, "another org's duplicates are untouched by --org ORG"


def test_a_followup_already_resolved_between_read_and_recheck_is_skipped(engine, monkeypatch):
    """Defensive: `duplicates()` names a `(org, followup)` pair whose active count has since
    dropped to one (a concurrent write between the read and `retire`'s own per-followup
    re-check) — `retire` finds one active row, not more than one, and does nothing to it."""
    item = _upsert(engine, "Send Priya the deck", now=T0)
    _write(engine, "evt_1", now=T0)   # exactly one active observation
    monkeypatch.setattr(R, "duplicates", lambda conn, org=None: [(ORG, item["id"], 2)])
    assert R.retire(engine, ORG) == []
