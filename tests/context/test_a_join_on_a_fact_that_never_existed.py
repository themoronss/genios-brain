"""`meeting_follow_through` produced zero cards for every customer since it shipped.

    pytest tests/context/test_a_join_on_a_fact_that_never_existed.py -q

TWO INDEPENDENT FAULTS IN ONE LANE, and fixing the first only revealed the second.

1. `outreach_situations` gathered its meetings with `text(_MEETINGS)` — a name it never imported.
   Every sweep raised `NameError`, `_optional` caught it, and the reading was fed an empty list.
   (Pinned in `test_a_gather_that_raised_on_every_sweep.py`.)

2. With that fixed the query still returned nothing, because it joined `graph_facts` on
   `meeting.external_counterparty` for the attendee. MEASURED ACROSS EVERY ORG IN THE DATABASE, at
   every version, live and closed: **zero rows have ever carried that field.** Its only producer is
   `meeting_lifecycle.reduce_meeting`, whose sole caller is `reason/runner` — Layer 4, which
   computes the boolean in memory for its own reasoning and never writes it to the graph. The join
   could not match on any tenant, on any day.

The module docstring still says the calendar connector wrote "62 meetings, 48 of them carrying
`meeting.external_counterparty`". No table in this database has ever been in that state.

REMOVING THE JOIN LOOSENS NOTHING, which is the only reason it is the right fix rather than giving
the fact a writer. The query already decides externality from data that exists: an attendee is
external when they are not one of our seats, not the account owner, and not a connected mailbox —
the identical rule `reduce_meeting` applies, evaluated against the `attended` edges the calendar
connector really writes. The fact restated a test the query was already performing, and it was the
only half of it that could fail.
"""
from __future__ import annotations

import ast
import inspect

import pytest

from genios_engine.context.meeting_touch import _MEETINGS

pytestmark = pytest.mark.unit


def test_the_query_does_not_wait_on_a_fact_nothing_writes() -> None:
    """THE DEFECT ITSELF. A join against a field with no producer cannot fail loudly — it returns
    an empty result, which is indistinguishable from a tenant with no meetings."""
    assert "meeting.external_counterparty" not in _MEETINGS, (
        "the meetings query joins on a field no writer in this engine produces")


def test_externality_is_still_decided_and_decided_by_who_we_are() -> None:
    """The half that does the real work, kept. Without it every meeting would list the founder as
    someone it reached, and an internal calendar entry would be reported as an outside touch.

    RESTATED BY STEP-04 (`yc2_w27_s04 · M22.C2.L-logic.V2.U03`). This pinned the inline rule —
    `org_seats`, `connections`, `not in` — and STEP-04 moved it out of the SQL on purpose: who is
    us is `platform/self_identity`, so `meeting_rows` asks `is_us_node` of every attendee and the
    sweep reads the identity once (`identity_for`). The inline union could not see a declared
    address (`ceo@thegenios.com`), so a meeting of the founder and his own second address was a
    touch. By the AST, so a word in a comment cannot satisfy it."""
    from genios_engine.context import meeting_touch

    def calls(fn) -> set[str]:
        tree = ast.parse(inspect.getsource(fn))
        return {n.func.attr if isinstance(n.func, ast.Attribute) else getattr(n.func, "id", None)
                for n in ast.walk(tree) if isinstance(n, ast.Call)}

    assert "is_us_node" in calls(meeting_touch.meeting_rows), "attendees are no longer asked if they are us"
    assert "identity_for" in calls(meeting_touch.refresh_channel_touch_situations), (
        "the sweep no longer reads who we are")
    assert "org_seats" not in _MEETINGS and "connections" not in _MEETINGS, (
        "the query re-derives who we are inline again — a second answer that will disagree")


def test_a_meeting_with_nobody_external_is_not_a_touch() -> None:
    """A meeting with only our own people in it is a real event and not an interaction with
    anybody, and each outside attendee is kept by name.

    RESTATED BY STEP-04. This pinned `having count(distinct att.node_id) > 0` as what drops an
    internal entry. It never was: the attendee join is inner, so the count is at least one on every
    row, and the dropping was done by the WHERE that STEP-04 moved into `meeting_rows`. Checked as
    the outcome, on rows shaped like the query's, with no database."""
    from types import SimpleNamespace

    from genios_engine.context.meeting_touch import meeting_rows
    from genios_engine.platform.self_identity import SelfIdentity

    class _Rows:
        def execute(self, *_args, **_kwargs):
            def row(node_id, *attendees):
                return SimpleNamespace(node_id=node_id, display_name=node_id, start_at=None,
                                       status=None, attendees=[list(a) for a in attendees])
            founder = ("Founder", "person", "founder@us.test")
            return [row("m_standup", founder, ("Second", "person", "ceo@us.test")),
                    row("m_pitch", founder, ("Priya", "person", "priya@them.test"),
                        ("Sam", "person", "sam@them.test"))]

    us = SelfIdentity.of(addresses=["founder@us.test"], domains=["us.test"])
    rows = meeting_rows(_Rows(), "org", us)
    assert [r["node_id"] for r in rows] == ["m_pitch"], "a meeting of only us was kept as a touch"
    assert rows[0]["counterparties"] == ["Priya", "Sam"], "an outside attendee was dropped, or one of us kept"


def test_a_retired_attendance_is_not_an_attendance() -> None:
    """`merge.py` closes edges during an identity merge, and without this the meeting reported an
    attendee the graph had already retired."""
    assert "e.valid_to is null" in _MEETINGS


def test_every_external_attendee_is_kept(  ) -> None:
    """Not one picked by sort order: an earlier cut used `max()` and four unrelated meetings all
    reported the same counterparty.

    RESTATED BY STEP-04: the aggregate now carries each attendee's type and key beside the name, so
    `meeting_rows` can ask who is us — still every attendee, still distinct, the name first."""
    assert "jsonb_agg(distinct jsonb_build_array(att.display_name" in _MEETINGS
    assert "max(att." not in _MEETINGS


def test_the_boolean_l4_computes_is_the_same_rule_this_query_applies() -> None:
    """The justification for deleting the join rather than giving the fact a writer: the two are
    the same test. If `reduce_meeting` ever stops deciding externality by seat membership, this
    equivalence — and therefore the deletion — needs revisiting."""
    from genios_engine.context import meeting_lifecycle

    src = inspect.getsource(meeting_lifecycle.reduce_meeting)
    assert "external" in src
    tree = ast.parse(src)
    assigns = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign)
               for t in n.targets if isinstance(t, ast.Name)}
    assert "external_counterparty" in assigns, (
        "reduce_meeting no longer derives external_counterparty; re-check that the meetings "
        "query's seat predicate is still the same rule")


def test_the_lane_is_reachable_end_to_end() -> None:
    """Query -> gather -> reading -> anchor -> situation type. Every link, since this lane had two
    separate breaks in it and each one hid the next."""
    from genios_engine.context.domain_spec import domains_declaring, spec_for
    from genios_engine.context.outreach_situations import ANCHOR_MEETING, READINGS

    assert ANCHOR_MEETING in {anchor for anchor, _ in READINGS}
    domains = domains_declaring(ANCHOR_MEETING)
    assert domains, "no domain declares the meeting anchor"
    assert any(spec_for(d).situation_types.get(ANCHOR_MEETING) for d in domains)
