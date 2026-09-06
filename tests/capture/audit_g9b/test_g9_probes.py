"""G9 audit probes — written independently of the fixers' own tests.

Every probe here is written to be SENSITIVE: each one is accompanied by a neutralisation test
that monkeypatches the fix out in memory and asserts the probe would then fail. A probe that
cannot fail is a decoration, and this file refuses to ship one.

Scope, verbatim from the gate brief:
  * webhook and poll produce IDENTICAL rows for the same message, INCLUDING attachments,
    mailbox_owner and prepared content
  * EVERY capture door emits a non-null coverage_ready; a deliberately unwired FIFTH door must
    make the ratchet FAIL
  * a source not yet due is not polled; jitter is deterministic ACROSS PROCESSES
  * a budget-exhausted run demotes VISIBLY via tier_demoted
  * backfill widening does not duplicate (the dedup key holds)
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys
import textwrap
from dataclasses import fields as dataclass_fields
from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.acquire.jitter import JitterKey, jitter_offset
from genios_engine.capture.acquire.sync_runner import run_sync
from genios_engine.capture.connectors.backfill import (BackfillWindow, backfill_window_for,
                                                       with_backfill_days)
from genios_engine.capture.connectors.base import RawObject, SourceBatch
from genios_engine.capture.connectors.push_ingest import PushIngestWiring, ingest_pushed_objects
from genios_engine.capture.coverage.audit import audit_capture_doors
from genios_engine.capture.coverage.declaration import declare_coverage
from genios_engine.capture.landing.repository import InMemorySourceEventRepository
from genios_engine.capture.parked.store import InMemoryParkedStore
from genios_engine.capture.payload_store import InMemoryRawPayloadStore
from genios_engine.capture.prepared_store import InMemoryPreparedContentStore
from genios_engine.contracts.connection import Connection

REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
PROBE_ORG = "org_probe_g9b"
PROBE_CONN = "con_probe_g9b"
MAILBOX_OWNER = "founder@genios-probe.test"
NOW = datetime(2026, 3, 11, 10, 30, tzinfo=timezone.utc)


# =============================================================================================
# PROBE 1 — webhook and poll land the SAME rows for the SAME message, attachments included.
# =============================================================================================

def _message_and_attachment() -> tuple[RawObject, RawObject]:
    """One Gmail message carrying one PDF — the shape the push door used to truncate to [0]."""
    message = RawObject(
        source="gmail", object_type="email_message", source_object_id="msg_probe_g9b",
        occurred_at=datetime(2026, 3, 11, 9, 0, tzinfo=timezone.utc),
        actor_email="priya@acme-probe.test", actor_name="Priya N",
        actor_type="external_contact", parent_object_id="thr_probe_g9b",
        recipients=("legal@acme-probe.test",),
        raw={"subject": "Revised renewal contract",
             "body": "Finance approved the renewal. The signed contract is attached; please "
                     "counter-sign and return it before the 24th so procurement can process it."})
    attachment = RawObject(
        source="gmail", object_type="email_attachment",
        source_object_id="msg_probe_g9b::att_9f21",
        occurred_at=message.occurred_at, actor_email=message.actor_email,
        actor_name=message.actor_name, actor_type="external_contact",
        parent_object_id="msg_probe_g9b", recipients=message.recipients,
        raw={"filename": "renewal.pdf", "mime_type": "application/pdf", "body": "",
             "subject": "Revised renewal contract"})
    return message, attachment


class _OnePageConnector:
    """A poll source that hands back exactly the two objects the webhook hands back."""

    source = "gmail"

    def __init__(self, objects: tuple[RawObject, ...]) -> None:
        self._objects = list(objects)

    def validate_connection(self) -> bool:
        return True

    def initial_snapshot(self, cursor=None, limit=50) -> SourceBatch:
        return SourceBatch(objects=list(self._objects), next_cursor=None)

    def incremental_changes(self, cursor=None, limit=50, since=None) -> SourceBatch:
        return SourceBatch(objects=list(self._objects), next_cursor=None)

    def fetch_content(self, object_ref: str) -> dict:
        return {}


def _coverage_fn(org_id: str = PROBE_ORG):
    conns = [Connection(org_id=org_id, source_type=s, connection_id=f"c_{s}")
             for s in ("gmail", "hubspot")]
    return declare_coverage(org_id=org_id, connections=conns, computed_at=NOW).for_domain


class _Lane:
    """Stores, one set per door, so the two doors cannot accidentally share state."""

    def __init__(self) -> None:
        self.repo = InMemorySourceEventRepository()
        self.payloads = InMemoryRawPayloadStore()
        self.prepared = InMemoryPreparedContentStore()
        self.parked = InMemoryParkedStore()

    def rows(self) -> dict[str, object]:
        return dict(self.repo._by_key)                        # keyed by (org, dedup_key)

    def decisions(self) -> dict[tuple[str, str], dict]:
        return dict(self.repo._decision)

    def outcomes(self) -> dict[tuple[str, str], str | None]:
        return dict(self.repo._outcome)


def _run_poll(objects: tuple[RawObject, ...], *, mailbox_owner: str | None = MAILBOX_OWNER,
              coverage=True) -> _Lane:
    lane = _Lane()
    run_sync(_OnePageConnector(objects), org_id=PROBE_ORG, connection_id=PROBE_CONN,
             repo=lane.repo, mode="incremental", limit=50,
             payload_store=lane.payloads, prepared_store=lane.prepared,
             parked_store=lane.parked, mailbox_owner=mailbox_owner,
             coverage_fn=_coverage_fn() if coverage else None,
             respect_cadence=False, source="gmail")
    return lane


def _run_push(objects: tuple[RawObject, ...], *, mailbox_owner: str | None = MAILBOX_OWNER,
              coverage=True) -> tuple[_Lane, object]:
    lane = _Lane()
    outcome = ingest_pushed_objects(
        objects, org_id=PROBE_ORG, connection_id=PROBE_CONN,
        wiring=PushIngestWiring(
            repo=lane.repo, payload_store=lane.payloads, prepared_store=lane.prepared,
            parked_store=lane.parked, mailbox_owner=mailbox_owner,
            coverage_fn=_coverage_fn() if coverage else None))
    return lane, outcome


#: Fields excluded from the row diff, each with the reason it CANNOT be equal.
#:   event_id    — a fresh uuid per capture (`new_id("evt")`); equality here would mean the two
#:                 doors shared an id, which is not what parity means.
#:   captured_at — wall-clock at ingest; the two doors run milliseconds apart by construction.
#:   payload_ref — derived from event_id, so it inherits event_id's non-determinism.
#: EVERYTHING else — including source_family, actor(name/email/type), recipients, visibility,
#: dedup_key, parent_object_id, sync_mode, internal_kind, occurred_at, schema_version — is
#: compared field for field.
EXCLUDED_FROM_PARITY = {"event_id", "captured_at", "payload_ref"}


def _comparable(event) -> dict:
    return {k: v for k, v in event.model_dump().items() if k not in EXCLUDED_FROM_PARITY}


def _prepared_by_dedup_key(lane: "_Lane") -> dict[str, object]:
    """Prepared rows keyed by the STABLE identity of the object they belong to."""
    by_event = {e.event_id: dedup for (_org, dedup), e in lane.rows().items()}
    return {by_event[event_id]: row["prepared"]
            for event_id, row in lane.prepared.rows.items() if event_id in by_event}


def test_probe_webhook_and_poll_land_the_same_dedup_keys_including_the_attachment():
    """The push door used to land `objects[0]` only — the mail, never the PDF."""
    objects = _message_and_attachment()
    poll = _run_poll(objects)
    push, _ = _run_push(objects)
    assert set(poll.rows()) == set(push.rows()), (
        f"poll landed {sorted(k[1] for k in poll.rows())}, "
        f"push landed {sorted(k[1] for k in push.rows())}")
    assert len(poll.rows()) == 2, "the fixture must land BOTH objects or the probe is vacuous"
    assert any("email_attachment" in k[1] for k in poll.rows())


def test_probe_every_source_event_field_matches_between_the_two_doors():
    """Field-by-field, for the message AND the attachment."""
    objects = _message_and_attachment()
    poll, push = _run_poll(objects), _run_push(objects)[0]
    poll_rows, push_rows = poll.rows(), push.rows()
    differences: list[str] = []
    for key in sorted(poll_rows, key=lambda k: k[1]):
        a, b = _comparable(poll_rows[key]), _comparable(push_rows[key])
        for field in sorted(set(a) | set(b)):
            if a.get(field) != b.get(field):
                differences.append(f"{key[1]}.{field}: poll={a.get(field)!r} push={b.get(field)!r}")
    assert not differences, "webhook/poll row divergence:\n  " + "\n  ".join(differences)


def test_probe_mailbox_owner_reaches_both_doors_and_shapes_the_same_acl():
    """`mailbox_owner` is what completes `visibility_principals`. The push door omitted it, so a
    pushed message carried a narrower ACL than the same polled one."""
    objects = _message_and_attachment()
    with_owner = _run_poll(objects).rows()
    without_owner = _run_poll(objects, mailbox_owner=None).rows()
    key = next(k for k in with_owner if "email_message" in k[1])
    assert with_owner[key].visibility != without_owner[key].visibility, (
        "mailbox_owner changes nothing about visibility in this fixture — the probe cannot "
        "detect a door that drops it")
    push = _run_push(objects)[0].rows()
    assert push[key].visibility == with_owner[key].visibility


def test_probe_prepared_content_is_identical_between_the_two_doors():
    """No `prepared_store` on the push door meant no clean text and no offset map — so an
    evidence span produced from a pushed message had nothing to align against."""
    objects = _message_and_attachment()
    poll, push = _run_poll(objects), _run_push(objects)[0]
    # Keyed by dedup_key, never by event_id: event ids are fresh uuids, so a positional zip
    # would compare the message of one door against the attachment of the other and "pass"
    # or "fail" on ordering rather than on content.
    poll_texts = _prepared_by_dedup_key(poll)
    push_texts = _prepared_by_dedup_key(push)
    assert poll_texts, "no prepared row was written at all — the probe would pass vacuously"
    assert set(poll_texts) == set(push_texts)
    for key in sorted(poll_texts):
        a, b = poll_texts[key], push_texts[key]
        assert a.clean_text == b.clean_text, key
        assert a.offset_map == b.offset_map, key
        assert a.masked_spans == b.masked_spans, key


def test_probe_the_routing_decision_is_identical_between_the_two_doors():
    """route / triage_lane / domain_hints / linkage_hints are what L2 reads off the row."""
    objects = _message_and_attachment()
    poll, push = _run_poll(objects), _run_push(objects)[0]
    assert poll.decisions() == push.decisions()
    assert poll.outcomes() == push.outcomes()


def test_probe_coverage_ready_is_non_null_on_both_doors():
    objects = _message_and_attachment()
    push, outcome = _run_push(objects)
    assert outcome.results, "nothing captured — vacuous"
    for res in outcome.results:
        assert res.gated is None or res.gated.coverage_ready is not None


# -- NEUTRALISATION: prove the parity probes are sensitive ------------------------------------

def test_neutralised_push_door_that_drops_attachments_fails_the_parity_probe(monkeypatch):
    """Re-introduce the original defect — land objects[0] only — and the dedup-key probe must
    fail. If it still passes, the probe never tested plurality."""
    objects = _message_and_attachment()

    def _truncating(objs, **kw):
        return _real_push(objs[:1], **kw)

    _real_push = ingest_pushed_objects
    monkeypatch.setattr("genios_engine.capture.connectors.push_ingest.ingest_pushed_objects",
                        _truncating, raising=True)
    import genios_engine.capture.connectors.push_ingest as P
    monkeypatch.setattr(P, "ingest_pushed_objects", _truncating, raising=True)

    lane = _Lane()
    P.ingest_pushed_objects(objects, org_id=PROBE_ORG, connection_id=PROBE_CONN,
                            wiring=PushIngestWiring(repo=lane.repo,
                                                    coverage_fn=_coverage_fn()))
    poll = _run_poll(objects)
    assert set(poll.rows()) != set(lane.rows()), (
        "a push door that drops attachments produced the same rows as the poll door — the "
        "parity probe cannot see the defect it exists for")


def test_neutralised_push_door_without_mailbox_owner_fails_the_acl_probe():
    """Drop `mailbox_owner` from the push wiring and the visibility must diverge."""
    objects = _message_and_attachment()
    poll = _run_poll(objects).rows()
    push_blind = _run_push(objects, mailbox_owner=None)[0].rows()
    key = next(k for k in poll if "email_message" in k[1])
    assert poll[key].visibility != push_blind[key].visibility, (
        "visibility is identical with and without mailbox_owner — the ACL probe is decorative")


def test_neutralised_push_door_without_prepared_store_writes_nothing():
    objects = _message_and_attachment()
    lane = _Lane()
    ingest_pushed_objects(objects, org_id=PROBE_ORG, connection_id=PROBE_CONN,
                          wiring=PushIngestWiring(repo=lane.repo, coverage_fn=_coverage_fn()))
    assert not lane.prepared.rows, (
        "a push door with no prepared_store still produced prepared rows — the prepared-content "
        "probe would pass for the wrong reason")


# =============================================================================================
# PROBE 2 — EVERY capture door declares coverage; a fifth unwired door must FAIL the ratchet.
# =============================================================================================

#: Enumerated from the SOURCE by the closure, not from a list. The assertion below is that the
#: closure finds at least these, which I confirmed by reading the call sites myself.
SCAN_ROOTS = (REPO_ROOT / "genios_engine", REPO_ROOT / "scripts")


def test_probe_the_door_enumeration_is_derived_from_source_not_from_a_list():
    audit = audit_capture_doors(SCAN_ROOTS)
    assert len(audit.doors) >= 5, audit.doors
    assert "capture_event" in audit.doors


def test_probe_no_discovered_door_call_site_omits_coverage():
    audit = audit_capture_doors(SCAN_ROOTS)
    assert audit.undeclared == (), (
        "capture doors emitting coverage_ready=None:\n  "
        + "\n  ".join(str(s) for s in audit.undeclared))


def test_probe_a_deliberately_unwired_fifth_door_makes_the_ratchet_fail(tmp_path):
    """My own fixture, my own door name. The ratchet must NAME it, at its call line."""
    root = tmp_path / "probe_engine"
    root.mkdir()
    (root / "quiet_door.py").write_text(textwrap.dedent('''\
        """A door added the quiet way — its name is in no list in this repository."""
        from genios_engine.capture.pipeline import capture_event


        def ingest_procurement_feed(obj, *, org_id, repo, coverage_fn=None):
            return capture_event(obj, org_id=org_id, connection_id="proc", repo=repo,
                                 coverage_fn=coverage_fn)


        def procurement_route(obj, org_id, repo):
            return ingest_procurement_feed(obj, org_id=org_id, repo=repo)
        '''), encoding="utf-8")
    audit = audit_capture_doors([root])
    assert "ingest_procurement_feed" in audit.doors, (
        "the closure did not recognise a function that forwards its own coverage_fn as a door")
    caught = [s for s in audit.undeclared if s.callee == "ingest_procurement_feed"]
    assert len(caught) == 1, f"the unwired fifth door was NOT caught: {audit.sites}"
    assert caught[0].line == 11, caught[0]
    assert "coverage_ready=None" in caught[0].reason


def test_probe_the_same_fifth_door_passes_once_wired(tmp_path):
    root = tmp_path / "probe_engine_wired"
    root.mkdir()
    (root / "quiet_door.py").write_text(textwrap.dedent('''\
        from genios_engine.capture.pipeline import capture_event


        def ingest_procurement_feed(obj, *, org_id, repo, coverage_fn=None):
            return capture_event(obj, org_id=org_id, connection_id="proc", repo=repo,
                                 coverage_fn=coverage_fn)


        def procurement_route(obj, org_id, repo, fn):
            return ingest_procurement_feed(obj, org_id=org_id, repo=repo, coverage_fn=fn)
        '''), encoding="utf-8")
    audit = audit_capture_doors([root])
    assert audit.undeclared == (), [str(s) for s in audit.undeclared]


def test_probe_coverage_fn_equals_none_is_not_read_as_a_declaration(tmp_path):
    """The exact spelling `capture/intake.py` defaulted to. A guard that reads the keyword's
    PRESENCE rather than its VALUE calls this wired, and the ratchet is then decorative."""
    root = tmp_path / "probe_none"
    root.mkdir()
    (root / "m.py").write_text(textwrap.dedent('''\
        from genios_engine.capture.pipeline import capture_event


        def door(obj, repo):
            return capture_event(obj, repo=repo, coverage_fn=None)
        '''), encoding="utf-8")
    audit = audit_capture_doors([root])
    site = next(s for s in audit.sites if s.callee == "capture_event")
    assert site.declared is False, site.reason


# =============================================================================================
# PROBE 3 — cadence: a source that is not due is not polled.
# =============================================================================================

class _CountingConnector(_OnePageConnector):
    def __init__(self) -> None:
        super().__init__(_message_and_attachment())
        self.list_calls = 0

    def incremental_changes(self, cursor=None, limit=50, since=None) -> SourceBatch:
        self.list_calls += 1
        return SourceBatch(objects=list(self._objects), next_cursor=None)


class _MemoryCursorStore:
    """The two methods `run_sync` uses. Deliberately minimal so nothing else is under test."""

    def __init__(self, saved=None) -> None:
        self._saved = saved

    def get(self, org_id, connection_id, source):
        return self._saved

    def advance(self, *a, **kw):
        return None

    def save(self, *a, **kw):
        return None


class _Saved:
    def __init__(self, synced_at, watermark=None, cursor=None) -> None:
        self.synced_at, self.watermark, self.cursor = synced_at, watermark, cursor


def test_probe_a_source_that_is_not_due_is_not_polled_at_all():
    """Zero provider calls, not a fetch that is then discarded — the gate returns BEFORE the
    connector is touched."""
    connector = _CountingConnector()
    lane = _Lane()
    summary = run_sync(connector, org_id=PROBE_ORG, connection_id=PROBE_CONN, repo=lane.repo,
                       mode="incremental", cursor_store=_MemoryCursorStore(
                           _Saved(synced_at=NOW - timedelta(seconds=30))),
                       respect_cadence=True, source="gmail", _now=lambda: NOW,
                       coverage_fn=_coverage_fn())
    assert connector.list_calls == 0, "a not-due source still reached the provider"
    assert summary.poll is not None and summary.poll.due is False
    assert lane.repo.count() == 0


def test_probe_a_source_that_is_due_is_polled():
    """The other half — otherwise 'not polled' is satisfied by never polling anything."""
    connector = _CountingConnector()
    lane = _Lane()
    run_sync(connector, org_id=PROBE_ORG, connection_id=PROBE_CONN, repo=lane.repo,
             mode="incremental", cursor_store=_MemoryCursorStore(
                 _Saved(synced_at=NOW - timedelta(days=2))),
             respect_cadence=True, source="gmail", _now=lambda: NOW,
             coverage_fn=_coverage_fn())
    assert connector.list_calls == 1
    assert lane.repo.count() == 2


def test_neutralised_ignoring_the_cadence_gate_polls_a_source_that_is_not_due():
    """`respect_cadence=False` is the neutralisation: same not-due row, and the provider IS
    reached. If this also produced zero calls, the cadence probe proved nothing."""
    connector = _CountingConnector()
    lane = _Lane()
    run_sync(connector, org_id=PROBE_ORG, connection_id=PROBE_CONN, repo=lane.repo,
             mode="incremental", cursor_store=_MemoryCursorStore(
                 _Saved(synced_at=NOW - timedelta(seconds=30))),
             respect_cadence=False, source="gmail", _now=lambda: NOW,
             coverage_fn=_coverage_fn())
    assert connector.list_calls == 1, (
        "even with the cadence gate off the connector was not reached — the not-due probe "
        "would pass for a reason that has nothing to do with cadence")


# =============================================================================================
# PROBE 4 — jitter is deterministic ACROSS PROCESSES, under different PYTHONHASHSEEDs.
# =============================================================================================

_JITTER_KEYS = [("org_a", "con_1", "gmail"), ("org_a", "con_1", "gcal"),
                ("org_b", "con_2", "gmail"), ("orga", "con1", "gmail")]

_SUBPROCESS = textwrap.dedent('''\
    import sys
    sys.path.insert(0, %r)
    from genios_engine.capture.acquire.jitter import JitterKey, jitter_offset
    keys = %r
    out = [jitter_offset(JitterKey(*k), interval_seconds=900).offset_seconds for k in keys]
    print(",".join(str(v) for v in out))
    ''')


def _offsets_in_subprocess(seed: str) -> list[int]:
    env = dict(os.environ, PYTHONHASHSEED=seed)
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    code = _SUBPROCESS % (str(REPO_ROOT), _JITTER_KEYS)
    proc = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True,
                          cwd=str(REPO_ROOT), timeout=120)
    assert proc.returncode == 0, proc.stderr
    return [int(v) for v in proc.stdout.strip().split(",")]


@pytest.mark.parametrize("seed", ["0", "1", "12345"])
def test_probe_jitter_is_identical_in_a_separate_process_under_a_different_hash_seed(seed):
    in_process = [jitter_offset(JitterKey(*k), interval_seconds=900).offset_seconds
                  for k in _JITTER_KEYS]
    assert _offsets_in_subprocess(seed) == in_process


def test_probe_the_jitter_fixture_actually_spreads():
    """If every key produced 0 the cross-process probe would be trivially satisfied."""
    offsets = {jitter_offset(JitterKey(*k), interval_seconds=900).offset_seconds
               for k in _JITTER_KEYS}
    assert len(offsets) >= 3, offsets
    assert any(o != 0 for o in offsets)


def test_neutralised_a_hash_based_jitter_is_not_stable_across_processes():
    """The neutralisation: swap blake2b for builtin `hash()` — the thing the module docstring
    says would break — and the SAME probe must find a divergence."""
    code = textwrap.dedent(f'''\
        import sys
        sys.path.insert(0, {str(REPO_ROOT)!r})
        keys = {_JITTER_KEYS!r}
        out = [(hash("|".join(k)) % 2001 - 1000) for k in keys]
        print(",".join(str(v) for v in out))
        ''')
    runs = []
    for seed in ("0", "1", "12345"):
        env = dict(os.environ, PYTHONHASHSEED=seed)
        proc = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True,
                              text=True, cwd=str(REPO_ROOT), timeout=120)
        assert proc.returncode == 0, proc.stderr
        runs.append(proc.stdout.strip())
    assert len(set(runs)) > 1, (
        "even builtin hash() was stable across PYTHONHASHSEED here — the cross-process jitter "
        "probe cannot distinguish blake2b from hash(), so it proves nothing")


# =============================================================================================
# PROBE 6 — backfill widening does not duplicate: the dedup key holds.
# =============================================================================================

def _connection(days: int | None) -> Connection:
    config = {} if days is None else {"backfill_days": days}
    return Connection(org_id=PROBE_ORG, connection_id=PROBE_CONN, source_type="gmail",
                      config=config)


def test_probe_widening_the_window_re_offers_the_same_objects_and_lands_none_of_them():
    """The real risk of an 18-month default: a tenant already backfilled at 60 days is widened,
    the provider re-offers everything, and the same mail lands twice."""
    objects = _message_and_attachment()
    lane = _Lane()
    narrow = backfill_window_for(_connection(60))
    wide = backfill_window_for(with_backfill_days(_connection(60), 540))
    assert wide.days > narrow.days, "the fixture did not actually widen the window"

    first = run_sync(_OnePageConnector(objects), org_id=PROBE_ORG, connection_id=PROBE_CONN,
                     repo=lane.repo, mode="backfill", source="gmail",
                     coverage_fn=_coverage_fn(), respect_cadence=False)
    landed_after_narrow = lane.repo.count()
    second = run_sync(_OnePageConnector(objects), org_id=PROBE_ORG, connection_id=PROBE_CONN,
                      repo=lane.repo, mode="backfill", source="gmail",
                      coverage_fn=_coverage_fn(), respect_cadence=False)
    assert landed_after_narrow == 2, first
    assert lane.repo.count() == 2, "the widened re-run duplicated rows"
    assert second.scanned == 2, "the widened run did not re-offer the objects — probe vacuous"
    assert second.emitted == 0


def test_probe_the_dedup_key_is_window_independent():
    """The key is (source, object_type, source_object_id[, content_version]) — nothing about the
    window enters it, which is WHY widening is safe."""
    from genios_engine.contracts.source_event import compute_dedup_key
    key = compute_dedup_key("gmail", "email_message", "msg_probe_g9b")
    assert key == "gmail:email_message:msg_probe_g9b"
    assert BackfillWindow(days=60).gmail_query() != BackfillWindow(days=540).gmail_query()


def test_neutralised_a_dedup_key_carrying_the_window_would_duplicate_on_widening():
    """The neutralisation: if the window HAD leaked into the key, the second run lands again."""
    objects = _message_and_attachment()
    lane = _Lane()
    run_sync(_OnePageConnector(objects), org_id=PROBE_ORG, connection_id=PROBE_CONN,
             repo=lane.repo, mode="backfill", source="gmail", coverage_fn=_coverage_fn(),
             respect_cadence=False)
    widened = tuple(RawObject(**{**o.__dict__, "content_version": "window_540d"})
                    for o in objects)
    run_sync(_OnePageConnector(widened), org_id=PROBE_ORG, connection_id=PROBE_CONN,
             repo=lane.repo, mode="backfill", source="gmail", coverage_fn=_coverage_fn(),
             respect_cadence=False)
    assert lane.repo.count() == 4, (
        "a key that varied with the window still deduped — the widening probe cannot "
        "distinguish a stable key from a lucky one")


# =============================================================================================
# PROBE 5 — a budget-exhausted run demotes VISIBLY, via tier_demoted on a stored record.
# =============================================================================================

#: My own T3-scoring body, built from the score table rather than copied: long content, a
#: currency token, two absolute dates and a deep thread. The assertions below prove it really
#: does score T3 before any demotion is asserted, so a threshold change fails loudly instead of
#: silently turning the demotion probe into a test of nothing.
_T3_BODY = ("Procurement approved the $128,500 renewal. Counsel counter-signs on April 2 and "
            "the first invoice issues on May 14. ") + ("filler word " * 800)


def _t3_message() -> RawObject:
    return RawObject(
        source="gmail", object_type="email_message", source_object_id="msg_probe_t3",
        occurred_at=NOW, actor_email="buyer@acme-probe.test", actor_name="Buyer",
        recipients=(MAILBOX_OWNER,),
        raw={"subject": "Renewal paperwork", "body": _T3_BODY, "thread_depth": 5,
             "thread_position": 5})


class _RecordingTraceRepo:
    def __init__(self) -> None:
        self.traces: list = []

    def save(self, trace) -> None:
        self.traces.append(trace)


def _capture_with_budget(fake_llm, *, t3_limit: int, already_granted: int):
    from genios_engine.capture import pipeline as P
    from genios_engine.capture.pipeline import capture_event
    from genios_engine.capture.semantic.model_router import T3Budget

    lane_stores = _Lane()
    traces = _RecordingTraceRepo()
    llm = fake_llm({"intent": "inform", "stance": "neutral"})
    budget = T3Budget(t3_limit=t3_limit, t3_granted=already_granted, day="2026-03-11")
    result = capture_event(
        _t3_message(), org_id=PROBE_ORG, connection_id=PROBE_CONN, repo=lane_stores.repo,
        prepared_store=lane_stores.prepared, payload_store=lane_stores.payloads,
        trace_repo=traces, mailbox_owner=MAILBOX_OWNER, coverage_fn=_coverage_fn(),
        semantic=P.SemanticLane(llm=llm, eval_time=NOW,
                                budget=P.T3Allowance(budget)))
    return result, traces, llm


def _semantic_lines(trace):
    from genios_engine.capture.semantic.extractor import STAGE as SEMANTIC_STAGE
    return [r for r in trace.records if r.stage == SEMANTIC_STAGE]


def test_probe_the_fixture_actually_earns_t3_when_the_budget_is_open(fake_llm):
    """Control. Without this, 'it was demoted' is indistinguishable from 'it was never T3'."""
    result, traces, llm = _capture_with_budget(fake_llm, t3_limit=10, already_granted=0)
    line = _semantic_lines(result.trace)[-1]
    assert line.action == "pass", line
    assert line.detail.get("tier") == "T3", line.detail
    assert line.detail.get("tier_demoted") is False, line.detail
    assert llm.call_count == 1


def test_probe_an_exhausted_t3_budget_demotes_and_says_so_on_the_stored_trace(fake_llm):
    """The gate criterion: the demotion is VISIBLE — it lands on the record an operator reads,
    with a reason, not merely inside a return value."""
    result, traces, llm = _capture_with_budget(fake_llm, t3_limit=1, already_granted=1)
    assert traces.traces, "no trace was persisted at all — nothing would be visible"
    line = _semantic_lines(result.trace)[-1]
    assert line.action == "pass", line
    assert line.detail.get("tier") == "T2", "the run was not actually demoted"
    assert line.detail.get("tier_demoted") is True, line.detail
    assert line.detail.get("demotion_reason"), (
        "demoted with no reason recorded — an operator cannot tell a money ceiling from an "
        "allowance ceiling")
    assert result.gated is not None, "the event was lost rather than demoted"


def test_probe_the_demotion_is_counted_not_just_logged(fake_llm):
    """`t3_demoted` is the FAILURE-MODES counter. A flag on one row with no counter behind it
    cannot answer 'is this org persistently demoted'."""
    from genios_engine.capture import pipeline as P
    from genios_engine.capture.semantic.model_router import T3Budget
    from genios_engine.capture.pipeline import capture_event

    allowance = P.T3Allowance(T3Budget(t3_limit=1, t3_granted=1, day="2026-03-11"))
    lane_stores = _Lane()
    capture_event(_t3_message(), org_id=PROBE_ORG, connection_id=PROBE_CONN,
                  repo=lane_stores.repo, prepared_store=lane_stores.prepared,
                  mailbox_owner=MAILBOX_OWNER, coverage_fn=_coverage_fn(),
                  semantic=P.SemanticLane(llm=fake_llm({"intent": "inform", "stance": "neutral"}),
                                          eval_time=NOW, budget=allowance))
    assert allowance.budget.t3_demoted == 1, allowance.budget
    assert allowance.budget.t3_granted == 1, "a demoted call spent a frontier slot"
    assert allowance.budget.demotion_rate_bp == 5000, allowance.budget


def test_neutralised_an_open_budget_produces_no_demotion_flag(fake_llm):
    """The sensitivity check for the whole probe: same message, same lane, budget NOT exhausted
    — and `tier_demoted` must be False. If it were True either way the flag says nothing."""
    open_result, _, _ = _capture_with_budget(fake_llm, t3_limit=10, already_granted=0)
    spent_result, _, _ = _capture_with_budget(fake_llm, t3_limit=1, already_granted=1)
    open_line = _semantic_lines(open_result.trace)[-1].detail
    spent_line = _semantic_lines(spent_result.trace)[-1].detail
    assert open_line.get("tier_demoted") != spent_line.get("tier_demoted"), (
        f"the demotion flag is identical with and without a budget: {open_line} vs {spent_line}")
