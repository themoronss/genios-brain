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


def test_externality_is_still_decided_and_decided_from_the_seats() -> None:
    """The half that does the real work, kept. Without it every meeting would list the founder as
    someone it reached, and an internal calendar entry would be reported as an outside touch."""
    assert "org_seats" in _MEETINGS
    assert "connections" in _MEETINGS
    assert "not in" in _MEETINGS.replace("  ", " ")


def test_a_meeting_with_nobody_external_is_not_a_touch() -> None:
    """The `having` is what drops an internal calendar entry. A meeting with only our own people
    in it is a real event and not an interaction with anybody."""
    assert "having count(distinct att.node_id) > 0" in _MEETINGS


def test_a_retired_attendance_is_not_an_attendance() -> None:
    """`merge.py` closes edges during an identity merge, and without this the meeting reported an
    attendee the graph had already retired."""
    assert "e.valid_to is null" in _MEETINGS


def test_every_external_attendee_is_kept(  ) -> None:
    """Not one picked by sort order: an earlier cut used `max()` and four unrelated meetings all
    reported the same counterparty."""
    assert "array_agg(distinct att.display_name)" in _MEETINGS


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
