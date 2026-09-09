"""The Cross Organization READING — where the correlator becomes a situation.

    pytest tests/context/test_organization_silence.py -q

THE DEFECT THIS FILE EXISTS BECAUSE OF, and it is the one this branch keeps finding: a capability
that exists and nobody consumes at the point that needs it. `textguard` was written and unimported
by capture. The `owns` edge was written and never read. `derived.timeline.condition_review` was
written since it shipped and surfaced by nothing. `correlation_conversation` shipped on this
branch and `context/runner.py` does not import it — measured, not assumed:

    correlation_resource   -> runner.py     correlation_timeline -> runner.py
    correlation_dependency -> runner.py     correlation_conversation -> NOTHING

`correlation_organization.py` would have been the fifth. `read_organization_silence` is the seam
that stops it: it travels the same `find_or_create_node` / `_write_fact` / `concerns`-edge path
every other state reading takes, dispatched from the same `READINGS` tuple, so there is no second
persistence route to drift from the first.

WHAT IT MUST NOT BECOME is the cohort reading with a different key — `admin.sit.campaign_going_
quiet` groups by OBJECTIVE and says so three times. The tests below pin the difference by
behaviour rather than by comment.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from genios_engine.context.correlation_organization import OrgGroup, OrgMember
from genios_engine.context.outreach_situations import (
    ANCHOR_ORGANIZATION,
    READINGS,
    read_organization_silence,
)

pytestmark = pytest.mark.unit

NOW = datetime(2026, 9, 9, tzinfo=timezone.utc)


def member(node_id: str, name: str, role: str | None = None) -> OrgMember:
    return OrgMember(node_id=node_id, name=name, role=role)


def peak_xv(*, roles: tuple[str | None, str | None] = (None, None)) -> OrgGroup:
    return OrgGroup(company_node_id="c_peak", company="peakxv.com",
                    members=(member("p_harshita", "Harshita", roles[0]),
                             member("p_vidushi", "Vidushi", roles[1])))


#: `()` is a real answer — a tenant with no multi-person firm — and `or` would swallow it into
#: the default. The empty-groups test failed on this fixture, not on the reading.
_DEFAULT = object()


def rows(*, waiting: dict[str, float], groups=_DEFAULT, extra: dict | None = None) -> dict:
    held: dict = {node: {"thread.days_waiting": days, "_name": node}
                  for node, days in waiting.items()}
    for node, patch in (extra or {}).items():
        held.setdefault(node, {}).update(patch)
    held["_organizations"] = (peak_xv(),) if groups is _DEFAULT else groups
    held["_mailbox_owner"] = None
    held["_conditions"] = {}
    return held


def read(**kw):
    return read_organization_silence(rows(**kw), NOW, {})


def facts_of(finding) -> dict:
    return {name: value for name, value, _kind in finding.facts}


# =============================================================================================
# The firm the system held eight situations about and never named.
# =============================================================================================
def test_two_silent_people_at_one_firm_is_one_finding():
    [finding] = read(waiting={"p_harshita": 28, "p_vidushi": 31})

    assert finding.anchor == ANCHOR_ORGANIZATION
    assert facts_of(finding)["organization.name"] == "peakxv.com"
    assert facts_of(finding)["organization.awaiting"] == 2


def test_the_reading_is_dispatched_like_every_other_one():
    """A reading that is not in `READINGS` is a function nobody calls — which is the defect this
    whole file exists to close, committed one layer up instead of one layer down."""
    assert (ANCHOR_ORGANIZATION, read_organization_silence) in READINGS


def test_the_denominator_counts_everyone_we_know_there():
    """"Two of the two partners are silent" and "two of nine" are different facts, and only the
    first is a firm going dark. The group is therefore computed over the whole tenant, not over
    the waiting rows."""
    big = OrgGroup(company_node_id="c", company="afore.vc",
                   members=tuple(member(f"p{i}", f"P{i}") for i in range(5)))

    [finding] = read(waiting={"p0": 20, "p1": 22}, groups=(big,))

    assert facts_of(finding)["organization.contacted"] == 5
    assert facts_of(finding)["organization.awaiting"] == 2


def test_the_longest_silence_is_reported_and_is_the_subject():
    """The card needs a real person to hang evidence and an owner on — a REPRESENTATIVE, not the
    finding's scope, which `organization.awaiting` states separately."""
    [finding] = read(waiting={"p_harshita": 28, "p_vidushi": 44})

    assert facts_of(finding)["organization.longest_wait_days"] == 44
    assert finding.concerns_node == "p_vidushi"


def test_everyone_silent_is_named():
    [finding] = read(waiting={"p_harshita": 28, "p_vidushi": 31})

    people = facts_of(finding)["organization.people"]
    assert "Harshita" in people and "Vidushi" in people


def test_the_correlation_id_is_the_company_node():
    """Stable across sweeps and unique per firm, so six drains a day produce one row rather than
    six — and two firms sharing a display name stay two situations."""
    [finding] = read(waiting={"p_harshita": 28, "p_vidushi": 31})

    assert finding.correlation_id == "organization:c_peak"


# =============================================================================================
# What must NOT mint a finding.
# =============================================================================================
def test_one_silent_contact_of_two_is_not_a_silent_firm():
    """The single fact this card exists to report would be wrong. The per-person card already
    covers it, and this one would be a duplicate with a firm's name on it."""
    assert read(waiting={"p_harshita": 28}) == []


def test_a_message_sent_this_morning_is_not_a_silence():
    """Same two-day floor `read_awaiting_response` uses. The two readings must agree about what
    waiting means, or the firm's numbers will not match the cards underneath it."""
    assert read(waiting={"p_harshita": 1, "p_vidushi": 1}) == []


def test_a_thread_covered_by_its_party_is_not_a_second_silent_person():
    """ONE SITUATION PER CONVERSATION, carried through to the group. `waiting.py` writes the same
    facts onto a thread and onto the party who corresponded on it; counting both would report a
    one-person silence as a firm going quiet."""
    group = OrgGroup(company_node_id="c", company="x.com",
                     members=(member("p_a", "A"), member("t_a", "Thread A")))

    found = read(waiting={"p_a": 30, "t_a": 30}, groups=(group,),
                 extra={"t_a": {"_covered_by_party": "A"}})

    assert found == []


def test_a_firm_with_nobody_waiting_is_not_reported():
    assert read(waiting={}) == []


def test_no_groups_is_not_an_error():
    assert read(waiting={"p_harshita": 28, "p_vidushi": 31}, groups=()) == []


# =============================================================================================
# CC-37 at the card seam — what the firm IS to us.
# =============================================================================================
def test_a_firm_we_know_nothing_about_gets_no_relationship_and_says_so():
    """The pilot holds ONE role fact across every node, so this is every row on it. The field is
    declared MISSING rather than guessed — a coverage score can see that, and a card cannot
    accidentally print a label that was never recorded."""
    [finding] = read(waiting={"p_harshita": 28, "p_vidushi": 31})

    assert "organization.relationship" not in facts_of(finding)
    assert "organization.relationship" in finding.missing


def test_one_agreed_role_may_be_stated():
    [finding] = read(waiting={"p_harshita": 28, "p_vidushi": 31},
                     groups=(peak_xv(roles=("investor", "investor")),))

    assert facts_of(finding)["organization.relationship"] == "investor"
    assert finding.missing == []


def test_two_roles_are_never_folded_into_one():
    """CC-37 proper. A supplier in one process and a customer in another share an identity and
    share nothing else — obligation direction, money direction and confidentiality all differ.
    Both travel, and no single relationship is claimed."""
    [finding] = read(waiting={"p_harshita": 28, "p_vidushi": 31},
                     groups=(peak_xv(roles=("supplier", "customer")),))

    assert "organization.relationship" not in facts_of(finding)
    assert facts_of(finding)["organization.roles"] == "customer, supplier"
    assert "organization.relationship" in finding.missing


def test_half_a_role_is_not_a_relationship():
    [finding] = read(waiting={"p_harshita": 28, "p_vidushi": 31},
                     groups=(peak_xv(roles=("investor", None)),))

    assert "organization.relationship" not in facts_of(finding)


# =============================================================================================
# It is not the cohort reading with a different key.
# =============================================================================================
def test_two_firms_in_one_campaign_are_two_findings():
    """`campaign_going_quiet` groups by OBJECTIVE and spans funds on purpose. This groups by firm,
    so the same raise going quiet at two funds is two relationships going quiet, not one."""
    afore = OrgGroup(company_node_id="c_afore", company="afore.vc",
                     members=(member("p_joseph", "Joseph"), member("p_madison", "Madison")))

    found = read(waiting={"p_harshita": 28, "p_vidushi": 31, "p_joseph": 28, "p_madison": 30},
                 groups=(peak_xv(), afore))

    assert {facts_of(f)["organization.name"] for f in found} == {"peakxv.com", "afore.vc"}


def test_the_objective_plays_no_part_in_the_grouping():
    """Two people at one firm on two different objectives — a raise and a vendor thread — are one
    firm that has stopped answering. The sibling reading correctly calls them two campaigns."""
    found = read(waiting={"p_harshita": 28, "p_vidushi": 31},
                 extra={"p_harshita": {"thread.objective": "fundraising"},
                        "p_vidushi": {"thread.objective": "procurement"}})

    assert len(found) == 1


def test_the_inputs_record_where_this_came_from():
    """Every reading states its derivation so a card's provenance is legible without reading the
    module that wrote it."""
    [finding] = read(waiting={"p_harshita": 28, "p_vidushi": 31})

    assert finding.inputs["reading"] == ANCHOR_ORGANIZATION
    assert finding.inputs["organization"] == "peakxv.com"


# =============================================================================================
# Direction — the one way this card can be wrong that reads perfectly.
# =============================================================================================
def test_a_firm_waiting_on_US_has_not_gone_quiet():
    """MEASURED, AND IT CORRECTED THE MEASUREMENT ABOVE IT. Handed all 82 waiting anchors, the
    grouping primitive returns FOUR firms on the pilot; only two have gone quiet. Afore and Peak
    XV sit at `ball_in_court = them` with 29 days each. Reticle sits at `ball_in_court = us` with
    `thread.last_heard_days` of 35 and 36 — WE are the silent party, and a card saying Reticle
    went dark would invert the one fact it exists to report and send the reader to chase somebody
    who is waiting on them.

    The guard is structural rather than a second check: `waiting.py` writes `thread.days_waiting`
    only while the last message in the exchange was ours, so a firm we owe carries no value to
    fire on. This pins that, because a future writer relaxing that condition would turn every
    "you owe them" into "they went quiet" silently.
    """
    group = OrgGroup(company_node_id="c_reticle", company="reticle.sh",
                     members=(member("p_div", "Divyanshu"), member("p_hardik", "Hardik")))
    held = {
        "p_div": {"thread.last_heard_days": 36, "thread.ball_in_court": "us", "_name": "Divyanshu"},
        "p_hardik": {"thread.last_heard_days": 35, "thread.ball_in_court": "us", "_name": "Hardik"},
        "_organizations": (group,),
    }

    assert read_organization_silence(held, NOW, {}) == []


def test_a_member_the_waiting_pass_never_saw_is_not_silent():
    """Vectorly's two contacts carry no waiting row at all. Absent is not zero and it is not
    silence — it is a conversation this pass knows nothing about, and counting it would put a
    firm on the feed on the strength of no observation."""
    group = OrgGroup(company_node_id="c_v", company="vectorly.app",
                     members=(member("p_alex", "Alex"), member("p_dima", "Dima")))

    assert read_organization_silence({"_organizations": (group,)}, NOW, {}) == []
