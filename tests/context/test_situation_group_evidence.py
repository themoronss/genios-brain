"""Actual correlation members key on event_id, not a representative node."""
from sqlalchemy import text

from .test_derived_provenance import provenance_db
from .test_support_derived_provenance import NOW
from genios_engine.context import outreach_situations as outreach


def _finding(**kwargs):
    return outreach._Finding(anchor="campaign", concerns_node="representative",
        correlation_id="synthetic-campaign", inputs={}, **kwargs)


def test_a_campaign_counts_its_complete_events_without_assuming_a_correlation_row(provenance_db):
    receipts = outreach._group_receipts(provenance_db, org_id="o", now=NOW,
        finding=_finding(event_ids=("e1", "e2", "e1", "foreign")))
    assert [r.event_id for r in receipts] == ["e1", "e2"]


def test_real_correlation_members_are_read_by_event_id_and_tenant(provenance_db):
    c = provenance_db
    c.execute(text("create table context_correlation_members (org_id text,correlation_id text,event_id text,joined_via text,joined_at timestamp)"))
    c.execute(text("insert into context_correlation_members values ('o','real-group','e1','email',null),('o','real-group','e2','email',null),('other','real-group','foreign','email',null),('o','unrelated','foreign','email',null)"))
    finding = _finding()
    finding.inputs = {"correlation_ids": ["real-group", "real-group"]}
    receipts = outreach._group_receipts(c, org_id="o", now=NOW, finding=finding)
    assert [r.event_id for r in receipts] == ["e1", "e2"]


def test_a_future_member_does_not_refresh_an_old_campaign(provenance_db):
    provenance_db.execute(text("update source_events set occurred_at='2026-09-11T12:00:00+00:00' where event_id='e2'"))
    receipts = outreach._group_receipts(provenance_db, org_id="o", now=NOW,
        finding=_finding(event_ids=("e1", "e2")))
    assert [r.event_id for r in receipts] == ["e1"]


def test_unavailable_membership_refinement_returns_to_the_neighborhood_path(provenance_db):
    assert outreach._group_receipts(provenance_db, org_id="o", now=NOW, finding=_finding()) is None
    assert provenance_db.execute(text("select 1")).scalar() == 1
