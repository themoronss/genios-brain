"""The four sync defects found resyncing the design partner on 11 Sep, each pinned by behaviour.

1. A re-read Gmail message re-landed its attachments under new attachmentIds (100 on one resume,
   393 extra copies on another tenant).
2. The progress bar could not move inside Layer 2, and a resumed job reset finished phases.
3. A sync interrupted by a deploy restarted from the newest page instead of where it stopped.
4. A new pack version never reached an existing tenant without a manual script.

    pytest tests/test_sync_resume_and_dedup.py -q
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from genios_engine.capture.landing.reread import drop_reread_attachments
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.contracts.source_event import compute_dedup_key

ORG = "org_sync_fix"


def _raw(object_type: str, source_object_id: str, parent: str | None = None):
    return SimpleNamespace(source="gmail", object_type=object_type,
                           source_object_id=source_object_id, parent_object_id=parent)


class _Repo(InMemorySourceEventRepository):
    """The in-memory ledger, with a message already landed under its real dedup key."""

    def __init__(self, landed_message_ids=()):
        super().__init__()
        for mid in landed_message_ids:
            self._by_key[(ORG, compute_dedup_key("gmail", "email_message", mid))] = object()


# ── 1 · attachments of a re-read message ─────────────────────────────────────────────────────────

def test_a_reread_messages_attachments_are_dropped_before_capture():
    page = [_raw("email_message", "m1"),
            _raw("email_attachment", "m1::ANGjdJ_second_read_id", parent="m1")]
    kept, dropped = drop_reread_attachments(page, org_id=ORG, repo=_Repo(["m1"]))
    assert [o.object_type for o in kept] == ["email_message"], "the message still reaches dedup"
    assert dropped == 1


def test_a_first_read_keeps_every_attachment():
    page = [_raw("email_message", "m2"),
            _raw("email_attachment", "m2::a", parent="m2"),
            _raw("email_attachment", "m2::b", parent="m2")]
    kept, dropped = drop_reread_attachments(page, org_id=ORG, repo=_Repo())
    assert len(kept) == 3 and dropped == 0


def test_only_the_reread_messages_attachments_go_on_a_mixed_page():
    page = [_raw("email_attachment", "old::x", parent="old"),
            _raw("email_attachment", "new::y", parent="new")]
    kept, dropped = drop_reread_attachments(page, org_id=ORG, repo=_Repo(["old"]))
    assert [o.source_object_id for o in kept] == ["new::y"] and dropped == 1


def test_a_versioned_attachment_is_a_new_version_not_a_reread():
    versioned = _raw("email_attachment", "m5::v2", parent="m5")
    versioned.content_version = "rev-2"
    kept, dropped = drop_reread_attachments([versioned], org_id=ORG, repo=_Repo(["m5"]))
    assert kept == [versioned] and dropped == 0, "an edit must land even when its parent has"


def test_a_failed_parent_lookup_keeps_the_attachment():
    class Broken:
        def exists(self, *_a):
            raise RuntimeError("ledger down")

    page = [_raw("email_attachment", "m3::z", parent="m3")]
    kept, dropped = drop_reread_attachments(page, org_id=ORG, repo=Broken())
    assert len(kept) == 1 and dropped == 0, "a duplicate is recoverable, a lost file is not"


def test_the_parent_key_is_the_one_the_pipeline_writes():
    """The drop asks the ledger for the parent under the SAME key `to_source_event` builds."""
    from genios_engine.capture.connectors.base import RawObject
    from genios_engine.capture.landing.normalize import to_source_event
    msg = RawObject(source="gmail", object_type="email_message", source_object_id="m4",
                    occurred_at=datetime(2026, 9, 1, tzinfo=timezone.utc),
                    actor_email="a@b.co", actor_type="external_contact", raw={"subject": "s"})
    event = to_source_event(msg, org_id=ORG, connection_id="c1")
    repo = InMemorySourceEventRepository()
    repo.add(event, outcome="emitted")
    kept, dropped = drop_reread_attachments([_raw("email_attachment", "m4::q", parent="m4")],
                                            org_id=ORG, repo=repo)
    assert dropped == 1 and kept == []


def test_both_capture_doors_drop_reread_attachments():
    import inspect

    from genios_engine.capture.acquire import sync_runner
    from genios_engine.capture.connectors import push_ingest
    assert "drop_reread_attachments(batch.objects" in inspect.getsource(sync_runner.run_sync)
    assert "drop_reread_attachments(objects" in inspect.getsource(
        push_ingest.ingest_pushed_objects)


# ── 2 · the progress bar moves inside Layer 2, and the Sync job provisions ───────────────────────

def test_layer_two_progress_moves_per_batch_and_the_sync_job_provisions(monkeypatch):
    from genios_engine.api import routes
    from genios_engine.platform import intelligence_onboarding, progress

    phases: list[dict] = []
    provisioned: list[str] = []
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=object()))
    monkeypatch.setattr(routes, "_pending_count", lambda _org: 60)
    monkeypatch.setattr(progress, "set_phase", lambda _e, _o, key, **kw: phases.append(
        {"key": key, **kw}))
    monkeypatch.setattr(intelligence_onboarding, "provision_intelligence",
                        lambda _e, org: provisioned.append(org))

    calls = {"n": 0}

    def fake_pending(**kw):
        calls["n"] += 1
        if calls["n"] > 1:
            return {"processed": 0}
        for done in (25, 50, 60):              # three L2 batches inside ONE chunk
            kw["on_progress"](done)
        return {"processed": 60}

    import genios_engine.context.runner as runner
    monkeypatch.setattr(runner, "process_pending", fake_pending)
    import genios_engine.reason.runner as l3
    monkeypatch.setattr(l3, "run_all", lambda **_kw: None)
    monkeypatch.setattr(routes, "_card_store", None)

    routes._process_and_reason_tracked(ORG)

    live = [p["done"] for p in phases if p["key"] == "processing" and "done" in p][1:4]
    assert live == [25, 50, 60], f"the bar must move inside the chunk, saw {phases}"
    assert provisioned == [ORG], "the Sync job must provision like the sweep does"


# ── 3 · a resumed sync continues where it stopped ─────────────────────────────────────────────────

@pytest.fixture
def sync_env(monkeypatch):
    from genios_engine.api import routes
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=None))
    monkeypatch.setattr(routes, "_llm_over_daily_cap", lambda _org: False)
    monkeypatch.setattr(routes, "_process_and_reason_tracked", lambda *_a, **_k: None)
    calls: list[dict] = []
    saved: list[dict] = []
    return routes, calls, saved


def _record(calls, *, fail_when_cursor: str | None = None):
    def fake(org_id, st, limit, max_rounds=None, on_round=None, start_cursor=None,
             on_cursor=None):
        calls.append({"src": st, "start": start_cursor, "max_rounds": max_rounds})
        if fail_when_cursor is not None and start_cursor == fail_when_cursor:
            raise RuntimeError("invalid pageToken")
        if on_cursor is not None:
            on_cursor("next-page", 1)
        return 1, 1, False
    return fake


def _snapshot(saved):
    import copy
    return lambda cp: saved.append(copy.deepcopy(cp))


def test_a_source_the_last_attempt_finished_is_not_read_again(sync_env, monkeypatch):
    routes, calls, saved = sync_env
    monkeypatch.setattr(routes, "_backfill_one_source", _record(calls))
    routes._onboarding_sync_bg(ORG, ["gmail", "gcal"],
                               checkpoint={"v": 1, "sources": {"gmail": {"state": "done"}}},
                               save_checkpoint=_snapshot(saved))
    assert [c["src"] for c in calls] == ["gcal"]
    assert saved[-1]["sources"] == {"gmail": {"state": "done"}, "gcal": {"state": "done"}}


def test_an_interrupted_source_resumes_from_its_saved_page(sync_env, monkeypatch):
    routes, calls, saved = sync_env
    monkeypatch.setattr(routes, "_backfill_one_source", _record(calls))
    routes._onboarding_sync_bg(
        ORG, ["gmail"],
        checkpoint={"sources": {"gmail": {"state": "running", "cursor": "page-9", "rounds": 7}}},
        save_checkpoint=_snapshot(saved))
    assert calls == [{"src": "gmail", "start": "page-9",
                      "max_rounds": routes._BACKFILL_MAX_ROUNDS - 7}]
    running = [s["sources"]["gmail"] for s in saved if s["sources"]["gmail"].get("cursor")]
    assert running[0] == {"state": "running", "cursor": "next-page", "rounds": 8}
    assert saved[-1]["sources"]["gmail"] == {"state": "done"}


def test_a_rejected_saved_page_restarts_that_source_once(sync_env, monkeypatch):
    routes, calls, saved = sync_env
    monkeypatch.setattr(routes, "_backfill_one_source", _record(calls, fail_when_cursor="stale"))
    routes._onboarding_sync_bg(
        ORG, ["gmail"],
        checkpoint={"sources": {"gmail": {"state": "running", "cursor": "stale", "rounds": 3}}},
        save_checkpoint=_snapshot(saved))
    assert [c["start"] for c in calls] == ["stale", None]
    assert saved[-1]["sources"]["gmail"] == {"state": "done"}


def test_a_fresh_job_starts_every_source_from_the_newest_page(sync_env, monkeypatch):
    routes, calls, saved = sync_env
    monkeypatch.setattr(routes, "_backfill_one_source", _record(calls))
    routes._onboarding_sync_bg(ORG, ["gmail"], checkpoint={}, save_checkpoint=_snapshot(saved))
    assert calls[0]["start"] is None and calls[0]["max_rounds"] == routes._BACKFILL_MAX_ROUNDS


def test_a_source_that_fails_stays_resumable(sync_env, monkeypatch):
    routes, calls, saved = sync_env

    def fails(org_id, st, limit, max_rounds=None, on_round=None, start_cursor=None,
              on_cursor=None):
        on_cursor("page-2", 1)
        raise RuntimeError("provider down")

    monkeypatch.setattr(routes, "_backfill_one_source", fails)
    routes._onboarding_sync_bg(ORG, ["gmail"], checkpoint={}, save_checkpoint=_snapshot(saved))
    assert saved[-1]["sources"]["gmail"] == {"state": "running", "cursor": "page-2", "rounds": 1}


def test_the_daily_cap_refuses_a_new_sync_but_never_a_resumed_one(sync_env, monkeypatch):
    routes, calls, saved = sync_env
    monkeypatch.setattr(routes, "_llm_over_daily_cap", lambda _org: True)
    monkeypatch.setattr(routes, "_backfill_one_source", _record(calls))
    routes._onboarding_sync_bg(ORG, ["gmail"], checkpoint={}, save_checkpoint=_snapshot(saved))
    assert calls == [], "a NEW sync over the cap does not start"
    routes._onboarding_sync_bg(
        ORG, ["gmail"],
        checkpoint={"sources": {"gmail": {"state": "running", "cursor": "page-4", "rounds": 2}}},
        save_checkpoint=_snapshot(saved))
    assert [c["start"] for c in calls] == ["page-4"], "a RESUMED sync finishes its window"


def test_the_worker_hands_the_job_its_checkpoint_and_persists_new_ones(monkeypatch):
    from genios_engine.api import routes
    from genios_engine.platform import sync_jobs as J

    beats: list = []
    seen: dict = {}
    monkeypatch.setattr(routes, "_graph", SimpleNamespace(engine=object()))
    monkeypatch.setattr(J, "claim_next", lambda _e, _w: {
        "id": "job_1", "org_id": ORG, "sources": ["gmail"], "attempts": 2,
        "checkpoint": {"sources": {"gmail": {"state": "done"}}}})
    monkeypatch.setattr(J, "complete", lambda _e, _j: None)
    monkeypatch.setattr(J, "heartbeat", lambda _e, jid, checkpoint=None: beats.append(
        (jid, checkpoint)))

    def fake_sync(org, sources, heartbeat=None, checkpoint=None, save_checkpoint=None):
        seen["checkpoint"] = checkpoint
        save_checkpoint({"sources": {"gmail": {"state": "done"}}})

    monkeypatch.setattr(routes, "_onboarding_sync_bg", fake_sync)
    assert routes.run_one_sync_job("w1") is True
    assert seen["checkpoint"] == {"sources": {"gmail": {"state": "done"}}}
    assert ("job_1", {"sources": {"gmail": {"state": "done"}}}) in beats


# ── 4 · a newer pack reaches an existing tenant ───────────────────────────────────────────────────

@pytest.mark.parametrize("current, state, pins, target, expected, why", [
    ("1.4.0", "active", [], "1.5.0", True, "an older version moves up"),
    ("1.5.0", "active", [], "1.5.0", False, "the same version is left alone"),
    ("1.6.0", "active", [], "1.5.0", False, "never downgrade"),
    ("1.9.0", "active", [], "1.10.0", True, "compared as numbers, not strings"),
    ("1.4.0", "disabled", [], "1.5.0", False, "a disabled pack stays disabled"),
    ("1.4.0", "active", ["version"], "1.5.0", False, "a version pin is respected"),
    ("1.4.0", "active", '["version"]', "1.5.0", False, "pins stored as JSON text"),
    ("1.4.0", "shadow", ["scoring_defaults.rule_offsets"], "1.5.0", True,
     "a config pin is not a version pin"),
    ("custom", "active", [], "1.5.0", False, "an unparseable version is not guessed at"),
])
def test_should_promote(current, state, pins, target, expected, why):
    from genios_engine.packs.wiring import should_promote
    assert should_promote(current, state, pins, target) is expected, why


class _FakeRegistry:
    def __init__(self, row):
        self.applied: list = []
        row_ = row

        class _Conn:
            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

            def execute(self, *_a, **_k):
                return SimpleNamespace(first=lambda: row_)

        self._engine = SimpleNamespace(connect=lambda: _Conn())

    def apply_to_tenant(self, org_id, pack_id, version, state="active"):
        self.applied.append((org_id, pack_id, version, state))


def test_an_existing_tenant_on_an_older_pack_is_promoted_keeping_its_state():
    from genios_engine.packs.wiring import ensure_default
    reg = _FakeRegistry(SimpleNamespace(version="1.4.0", state="shadow", pins=[]))
    ensure_default(reg, ORG, "general", "1.5.0")
    assert reg.applied == [(ORG, "general", "1.5.0", "shadow")]


def test_a_tenant_with_no_pack_still_gets_it():
    from genios_engine.packs.wiring import ensure_default
    reg = _FakeRegistry(None)
    ensure_default(reg, ORG, "general", "1.5.0")
    assert reg.applied == [(ORG, "general", "1.5.0", "active")]


def test_a_current_tenant_is_not_rewritten():
    from genios_engine.packs.wiring import ensure_default
    reg = _FakeRegistry(SimpleNamespace(version="1.5.0", state="active", pins=[]))
    ensure_default(reg, ORG, "general", "1.5.0")
    assert reg.applied == [], "a no-op must not bump the revision and un-authorise signals"


# ── 2b · a resumed job keeps the phases it finished (real Postgres: the table is jsonb) ─────────

@pytest.mark.skipif(not os.environ.get("GENIOS_TEST_DATABASE_URL"),
                    reason="GENIOS_TEST_DATABASE_URL not set — progress lives in a jsonb table")
def test_a_resumed_job_keeps_finished_phases():
    from sqlalchemy import text

    from genios_engine.platform import progress as P
    from genios_engine.platform.db import get_engine
    eng = get_engine(os.environ["GENIOS_TEST_DATABASE_URL"])
    org = "org_scratch_tests"              # seeded by conftest; onboarding_progress has an orgs FK
    with eng.begin() as c:
        c.execute(text("delete from onboarding_progress where org_id=:o"), {"o": org})
    P.start(eng, org, ["gmail"])
    P.set_phase(eng, org, "emails", state="done", done=850, total=850, detail="850 synced")
    P.start(eng, org, ["gmail"], resume=True)
    state = P.read(eng, org)
    emails = next(p for p in state["phases"] if p["key"] == "emails")
    assert emails["state"] == "done" and emails["done"] == 850
    assert state["overall_percent"] > 0, "a resume must not flash back to 0%"
    P.start(eng, org, ["gmail"])
    fresh = next(p for p in P.read(eng, org)["phases"] if p["key"] == "emails")
    assert fresh["state"] == "pending", "a NEW sync still starts clean"
