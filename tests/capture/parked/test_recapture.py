"""L1.3.8-U3 · the recapture drain — the third park class, and why the other two are wrong for it.

`visibility_unknown` and `MUT-01` were in NO drain class. The consequence is the paragraph
`drain.py` already wrote about DOC-07/08/09: `drain_parked` counted them into `by_reason` and
walked past, `parked_aging` called them ``"terminal"``, the refetch claim never selected them, and
`scripts/l1_s1_report.py` — the G2 surface — could not see them. Held events accumulated at
``status='pending'`` while every number read clean.

The tests below are table-driven, one row per condition, and the two that matter most are
NEGATIVE: an audience that still cannot be named is NOT published, and a versionless mutable
object is NEVER re-emitted. Those are the two ways a well-meaning fix here would be worse than the
silence it replaced.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from genios_engine.capture.parked.drain import STALE_AFTER, parked_aging
from genios_engine.capture.parked.recapture import (NEEDS_RECAPTURE, STATUS_PENDING,
                                                    STATUS_RECOVERED, STATUS_SUPERSEDED,
                                                    RecaptureAction, RecaptureCandidate,
                                                    drain_recapture, plan_recapture, summarise)

WAVE = "W2"
GATE = "G2"

NOW = datetime(2026, 3, 11, 10, 30, tzinfo=timezone.utc)
ORG = "org_recapture"


def _candidate(*, reason_code: str, source: str = "gmail", status: str = STATUS_PENDING,
               actor_email: str | None = "priya@acme.test",
               recipients: tuple[str, ...] = ("founder@genios.test",),
               internal_kind: str | None = None, has_later_capture: bool = False,
               parked_at: datetime | None = None) -> RecaptureCandidate:
    return RecaptureCandidate(
        event_id="evt_rc", org_id=ORG, reason_code=reason_code, status=status, source=source,
        source_object_id="obj_1", object_type="email_message",
        parked_at=parked_at or (NOW - timedelta(days=5)), actor_email=actor_email,
        recipients=recipients, internal_kind=internal_kind,
        has_later_capture=has_later_capture)


# ── ownership: whose rows are these ──────────────────────────────────────────────────────────

_OWNERSHIP = [
    ("visibility park",        "visibility_unknown", STATUS_PENDING,  False),
    ("mutable park",           "MUT-01",             STATUS_PENDING,  False),
    ("a refetch park",         "DOC-05",             STATUS_PENDING,  True),
    ("a re-adjudicable park",  "low_relevance",      STATUS_PENDING,  True),
    ("already recovered",      "visibility_unknown", STATUS_RECOVERED, True),
    ("already superseded",     "MUT-01",             STATUS_SUPERSEDED, True),
]


@pytest.mark.parametrize("label,code,status,skipped", _OWNERSHIP, ids=[r[0] for r in _OWNERSHIP])
def test_only_pending_recapture_parks_are_this_units_rows(label, code, status, skipped):
    """A drain that acted on another class's rows would settle a park twice — which is how a
    queue gets two owners and no accountability."""
    plan = plan_recapture(_candidate(reason_code=code, status=status,
                                     source="unknown_saas" if code == "MUT-01" else "gmail"),
                          eval_time=NOW)
    assert (plan.action is RecaptureAction.SKIP) is skipped, plan.reason


def test_the_class_holds_exactly_the_two_orphaned_codes():
    assert NEEDS_RECAPTURE == frozenset({"visibility_unknown", "MUT-01"})


# ── visibility_unknown: re-derive, or refuse ─────────────────────────────────────────────────

def test_a_source_that_now_has_a_visibility_rule_is_rederived_and_released():
    """`gmail` is a registered communication source, so the derivation succeeds — which is what
    a source's family being registered after the park looks like."""
    plan = plan_recapture(_candidate(reason_code="visibility_unknown", source="gmail"),
                          eval_time=NOW)
    assert plan.action is RecaptureAction.REDERIVED, plan.reason
    assert plan.visibility is not None
    assert plan.visibility.scope == "participants"
    assert "priya@acme.test" in plan.visibility.principals


def test_a_source_no_rule_still_covers_is_NOT_published():
    """THE NEGATIVE THAT MATTERS. Publishing under a guessed audience is the one outcome the
    park exists to prevent, and it is exactly what `RE_ADJUDICABLE` would have done."""
    plan = plan_recapture(
        _candidate(reason_code="visibility_unknown", source="a_source_no_registry_knows"),
        eval_time=NOW)
    assert plan.action is RecaptureAction.STILL_BLOCKED
    assert plan.visibility is None
    assert "no visibility rule" in plan.reason


def test_the_mailbox_owner_widens_a_participants_set_and_omitting_it_narrows():
    """The owner can only ADD a principal, so an unresolvable owner is safe by construction —
    the audience comes out narrower, never wider than the evidence."""
    candidate = _candidate(reason_code="visibility_unknown", source="gmail")
    with_owner = plan_recapture(candidate, eval_time=NOW,
                                mailbox_owner="owner@genios.test").visibility
    without = plan_recapture(candidate, eval_time=NOW).visibility
    assert with_owner is not None and without is not None
    assert set(without.principals) < set(with_owner.principals)
    assert "owner@genios.test" in with_owner.principals


def test_an_internal_kind_park_derives_org_scope():
    plan = plan_recapture(_candidate(reason_code="visibility_unknown",
                                     source="a_source_no_registry_knows",
                                     internal_kind="policy"), eval_time=NOW)
    assert plan.action is RecaptureAction.REDERIVED
    assert plan.visibility is not None and plan.visibility.scope == "org"


# ── MUT-01: superseded by a later capture, never re-emitted ──────────────────────────────────

def test_a_versionless_mutable_park_with_a_later_capture_is_superseded():
    plan = plan_recapture(_candidate(reason_code="MUT-01", has_later_capture=True),
                          eval_time=NOW)
    assert plan.action is RecaptureAction.SUPERSEDED
    assert plan.visibility is None, "a MUT-01 settlement must never stamp an audience"


def test_a_versionless_mutable_park_with_no_later_capture_stays_blocked():
    plan = plan_recapture(_candidate(reason_code="MUT-01", has_later_capture=False),
                          eval_time=NOW)
    assert plan.action is RecaptureAction.STILL_BLOCKED
    assert "version stamp" in plan.reason


def test_no_mut01_outcome_ever_re_emits_the_frozen_copy():
    """Re-emitting is what `RE_ADJUDICABLE` does, and for MUT-01 it would PUBLISH the stale
    first-seen state — the precise failure the park names."""
    for later in (True, False):
        plan = plan_recapture(_candidate(reason_code="MUT-01", has_later_capture=later),
                              eval_time=NOW)
        assert plan.action is not RecaptureAction.REDERIVED


# ── ageing and counting ──────────────────────────────────────────────────────────────────────

_AGES = [("today", timedelta(0), 0), ("two days", timedelta(days=2), 2),
         ("nine days", timedelta(days=9), 9)]


@pytest.mark.parametrize("label,age,days", _AGES, ids=[r[0] for r in _AGES])
def test_a_blocked_park_reports_its_age_in_whole_days(label, age, days):
    plan = plan_recapture(_candidate(reason_code="MUT-01", parked_at=NOW - age), eval_time=NOW)
    assert plan.age_days == days
    assert isinstance(plan.age_days, int)


def test_the_summary_counts_each_outcome_and_names_the_blocked_codes():
    plans = [
        plan_recapture(_candidate(reason_code="visibility_unknown", source="gmail"),
                       eval_time=NOW),
        plan_recapture(_candidate(reason_code="visibility_unknown", source="nowhere"),
                       eval_time=NOW),
        plan_recapture(_candidate(reason_code="MUT-01", has_later_capture=True), eval_time=NOW),
        plan_recapture(_candidate(reason_code="MUT-01", has_later_capture=False,
                                  parked_at=NOW - timedelta(hours=2)), eval_time=NOW),
    ]
    report = summarise(plans)
    assert report.examined == 4
    assert report.rederived == 1 and report.superseded == 1 and report.still_blocked == 2
    assert report.settled == 2
    assert dict(report.blocked_by_reason) == {"visibility_unknown": 1, "MUT-01": 1}
    # Only the one parked five days ago is stale; the two-hour-old one is not.
    assert report.stale == 1


def test_a_stale_backlog_is_counted_by_the_same_threshold_the_aging_surface_uses():
    old = plan_recapture(_candidate(reason_code="MUT-01",
                                    parked_at=NOW - STALE_AFTER - timedelta(hours=1)),
                         eval_time=NOW)
    fresh = plan_recapture(_candidate(reason_code="MUT-01", parked_at=NOW - timedelta(hours=1)),
                           eval_time=NOW)
    assert summarise([old]).stale == 1
    assert summarise([fresh]).stale == 0


# ── the aging surface no longer lies ─────────────────────────────────────────────────────────

class _Row:
    def __init__(self, **kw) -> None:
        self.__dict__.update(kw)


class _Result:
    def __init__(self, rows) -> None:
        self._rows = rows

    def fetchall(self):
        return self._rows

    def all(self):
        return self._rows


class _Conn:
    def __init__(self, rows) -> None:
        self._rows = rows
        self.writes: list[tuple[str, dict]] = []

    def execute(self, statement, params=None):
        text = str(statement)
        if text.strip().lower().startswith("update"):
            self.writes.append((text, dict(params or {})))
            return _Result([])
        return _Result(self._rows)

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class _Engine:
    def __init__(self, rows) -> None:
        self.conn = _Conn(rows)

    def connect(self):
        return self.conn

    def begin(self):
        return self.conn


@pytest.mark.parametrize("code", sorted(NEEDS_RECAPTURE))
def test_the_aging_surface_labels_a_recapture_park_by_its_class(code):
    """It used to say ``terminal`` — "stop looking" — about a queue nobody had settled."""
    rows = [_Row(reason_code=code, status="pending", refetch_failure_kind=None, n=3,
                 oldest=NOW - timedelta(days=9))]
    aging = parked_aging(_Engine(rows), org_id=ORG, now=NOW)
    assert aging[0]["class"] == "needs_recapture"


def test_a_code_no_drain_claims_is_still_labelled_terminal():
    """The label is not being retired — it is being made reachable only when it is TRUE."""
    rows = [_Row(reason_code="INVENTED-99", status="pending", refetch_failure_kind=None, n=1,
                 oldest=NOW)]
    assert parked_aging(_Engine(rows), org_id=ORG, now=NOW)[0]["class"] == "terminal"


# ── the drain writes exactly the transitions the plan named ──────────────────────────────────

def _db_row(**kw):
    base = dict(event_id="evt_rc", org_id=ORG, reason_code="visibility_unknown",
                status=STATUS_PENDING, created_at=NOW - timedelta(days=5), source="gmail",
                source_object_id="obj_1", object_type="email_message",
                actor={"type": "external_contact", "email": "priya@acme.test"},
                recipients=["founder@genios.test"], internal_kind=None,
                has_later_capture=False)
    base.update(kw)
    return _Row(**base)


def test_a_rederived_park_writes_the_audience_and_releases_the_event():
    engine = _Engine([_db_row()])
    report = drain_recapture(engine, eval_time=NOW)
    assert report.rederived == 1 and report.still_blocked == 0
    statements = " | ".join(sql for sql, _ in engine.conn.writes)
    assert "visibility_scope" in statements and "outcome = 'emitted'" in statements
    assert "parked_events set status" in statements
    params = [p for _sql, p in engine.conn.writes]
    assert any(p.get("scope") == "participants" for p in params)
    assert any(p.get("status") == STATUS_RECOVERED for p in params)


def test_a_still_blocked_park_writes_NOTHING():
    """The strongest statement about the negative case: not a status change, not an outcome
    flip, nothing. A park that cannot be settled is left exactly as it was, and counted."""
    engine = _Engine([_db_row(source="a_source_no_registry_knows")])
    report = drain_recapture(engine, eval_time=NOW)
    assert report.still_blocked == 1 and report.rederived == 0
    assert engine.conn.writes == []
    assert dict(report.blocked_by_reason) == {"visibility_unknown": 1}


def test_a_superseded_park_settles_the_queue_without_touching_source_events():
    engine = _Engine([_db_row(reason_code="MUT-01", source="hubspot",
                              object_type="deal", has_later_capture=True)])
    report = drain_recapture(engine, eval_time=NOW)
    assert report.superseded == 1
    assert len(engine.conn.writes) == 1, engine.conn.writes
    sql, params = engine.conn.writes[0]
    assert "parked_events" in sql and "source_events" not in sql
    assert params["status"] == STATUS_SUPERSEDED


def test_the_drain_reads_an_actor_column_the_driver_handed_back_as_json_text():
    """`actor` is jsonb; psycopg returns a dict, but a driver or a view can hand back text. A
    drain that only handled one shape would silently derive an audience with no sender in it."""
    import json
    engine = _Engine([_db_row(actor=json.dumps({"type": "external_contact",
                                                "email": "priya@acme.test"}))])
    report = drain_recapture(engine, eval_time=NOW)
    assert report.rederived == 1
    params = [p for _sql, p in engine.conn.writes]
    assert any("priya@acme.test" in (p.get("principals") or []) for p in params)
