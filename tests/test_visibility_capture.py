"""L1-04: visibility was defined, unit-tested, and called by NOTHING on the capture path.

`grep -rn visibility genios_engine/capture/` returned zero matches and `source_events` had no
column — every event landed org-scoped, so a fact from a two-person private thread was
indistinguishable from one from a company-wide page, and every layer above was free to deliver
either to anyone in the tenant. The passing contract test was itself the hazard: it made the
layer look protected.
"""
from datetime import datetime, timezone

from genios_engine.capture.connectors.base import RawObject
from genios_engine.capture.gate.context import GateContext
from genios_engine.capture.gate.gate import run_gate
from genios_engine.capture.landing.normalize import to_source_event
from genios_engine.capture.visibility_rules import derive_visibility
from genios_engine.contracts.source_event import Actor, SourceEvent
from genios_engine.contracts.trace import EventTrace

NOW = datetime(2026, 8, 24, tzinfo=timezone.utc)


def _raw(**kw):
    base = dict(source="gmail", object_type="message", source_object_id="m1",
                occurred_at=NOW, actor_email="investor@antler.co",
                recipients=("rohit@genios.com",))
    return RawObject(**{**base, **kw})


def test_an_email_is_visible_to_its_participants_not_the_whole_org():
    """The ACL of an email IS its participant list: sender + To/Cc + the mailbox owner (who
    could see it by definition — it is their mailbox)."""
    v = derive_visibility(source="gmail", actor_email="Investor@Antler.co",
                          recipients=("rohit@x.com",), mailbox_owner="rohit@x.com")
    assert v.scope == "participants"
    assert v.principals == ["investor@antler.co", "rohit@x.com"]
    assert v.derived_from == "connector:gmail:participants"


def test_an_empty_recipient_list_is_a_small_audience_not_an_unknown_one():
    """A BCC-only or self-noted message is visible to the sender and the owner — a valid
    (small) participants set, not an absence to park over."""
    v = derive_visibility(source="gmail", actor_email="a@b.com", recipients=(),
                          mailbox_owner="owner@x.com")
    assert v.scope == "participants"
    assert v.principals == ["a@b.com", "owner@x.com"]


def test_every_derivation_is_named_so_a_wrong_audience_traces_to_its_rule():
    for source, expected in (("hubspot", "system_of_record:hubspot"),
                             ("notion", "connector:workspace_default"),
                             ("upload", "deliberate:upload"),
                             ("github", "family:operational")):
        v = derive_visibility(source=source, actor_email=None, recipients=None)
        assert v is not None and v.derived_from == expected, source


def test_company_canon_is_org_scoped_whatever_door_it_came_through():
    v = derive_visibility(source="upload", actor_email="founder@x.com", recipients=None,
                          internal_kind="pricing")
    assert v.scope == "org" and v.derived_from == "internal_kind:pricing"


def test_a_source_no_rule_covers_returns_none_never_a_guess():
    assert derive_visibility(source="weirdapp", actor_email="a@b.com", recipients=()) is None


def test_the_normalize_seam_stamps_visibility_once():
    ev = to_source_event(_raw(), org_id="o", connection_id="c", mailbox_owner="rohit@genios.com")
    assert ev.visibility is not None
    assert ev.visibility.scope == "participants"
    assert "rohit@genios.com" in ev.visibility.principals
    assert ev.schema_version == 5


def test_the_gate_parks_an_audience_nobody_can_name():
    """An audience we cannot name is not an audience we may assume. Park, not drop — adding the
    source's rule to visibility_rules.py re-admits the whole class on the next drain."""
    ev = SourceEvent(event_id="e1", org_id="o", connection_id="c", source="weirdapp",
                     object_type="thing", source_object_id="t1",
                     dedup_key="weirdapp:thing:t1",
                     actor=Actor(type="system"), occurred_at=NOW)
    res = run_gate(GateContext(event=ev, is_structured=True),
                   EventTrace(org_id="o", event_id="e1"))
    assert res.action == "park" and res.reason_code == "visibility_unknown"


def test_the_gate_re_derives_rather_than_parking_a_constructor_omission():
    """The question is "does any rule name this audience?" — NOT "did the caller remember to
    attach one?". An event built without visibility (a legacy path, a test double) is re-derived
    from the same shared rules; only a source genuinely outside them parks."""
    ev = SourceEvent(event_id="e1", org_id="o", connection_id="c", source="gmail",
                     object_type="message", source_object_id="m1",
                     dedup_key="gmail:message:m1",
                     actor=Actor(type="external_contact", email="a@b.com"), occurred_at=NOW)
    assert ev.visibility is None
    res = run_gate(GateContext(event=ev, raw={"subject": "contract",
                                              "snippet": "please send the contract"}),
                   EventTrace(org_id="o", event_id="e1"))
    assert res.action != "park" or res.reason_code != "visibility_unknown"
    assert ev.visibility is not None and ev.visibility.scope == "participants"


def test_the_provenance_check_runs_before_the_structured_short_circuit():
    """Same trap as MUT-01, avoided the same way: a check placed after the structured
    short-circuit can never fire for a structured source, and correct-but-unreachable is the
    same as absent, only harder to notice."""
    import inspect

    from genios_engine.capture.gate import gate

    src = inspect.getsource(gate.run_gate)
    assert src.index('trace.record("S0.6"') < src.index('trace.record("S1.5"')


# ── the situation's audience is the narrowest merge of its evidence ─────────────
def test_a_situation_built_from_private_threads_does_not_claim_org_visibility():
    """Both BSO builders stamped `Visibility(scope="org")` as a literal. Harmless while every
    event was org-scoped — and the capture fix ended that: communication events now land
    participants-scoped, so a situation built from a two-person thread claiming org visibility
    is exactly the widening `narrowest()` exists to prevent."""
    import inspect

    from genios_engine.context import situation_bso

    src = inspect.getsource(situation_bso)
    assert "narrowest(" in src
    assert "gather_visibility" in src
    # the literal survives only as the no-evidence fallback, and says so
    assert 'derived_from="l2:situation:no_members"' in src


def test_the_expertise_adapter_reports_what_it_refused_to_convert():
    """A 1,748-file corpus could compile successfully, hash into a new manifest version, and
    still emit one generic "review the situation" play — activation would LOOK successful while
    producing generic output. The receipt is what makes that state readable."""
    from genios_engine.reason.adapters.expertise import MAX_PLAYS, _plays

    def _rule(i, steps):
        return {"id": f"rule_{i:02d}", "definition": {"name": f"r{i}", "steps": steps}}

    # Sized OFF the cap, not off a literal. It was `range(6)` against a cap of 4; raising the cap
    # to 16 made the same input fit entirely, so the test passed a truncation assertion by never
    # truncating. A guard whose subject disappears when a constant moves is not a guard.
    overflow = MAX_PLAYS + 2

    class _Package:      # only the fields _plays reads; the full contract needs 15 args
        expert_rules = tuple([_rule(i, ["do a thing"]) for i in range(overflow)]
                             + [{"id": "heuristic_1", "definition": {"name": "h"}}])
        # Read since the adaptive brain reached the ranking: a play the tenant has measured
        # carries its own `success_probability_bp` instead of the 5,000bp default. Empty here —
        # this test is about the conversion receipt, not about learning.
        adaptive_preferences = ()

    plays, receipt = _plays(_Package())
    assert len(plays) == MAX_PLAYS
    assert receipt["plays_emitted"] == MAX_PLAYS
    assert receipt["skipped_rule_ids"]["heuristic_1"] == "no_steps_artifact_unsupported"
    assert receipt["truncation_reason"] is not None
    assert receipt["generic_fallback_used"] is False
    # deterministic: the surviving plays are the FIRST by rule id, not corpus order
    assert [p.play_id for p in plays] == [f"rule_{i:02d}" for i in range(MAX_PLAYS)]
    # and the ones that did not survive are NAMED, which is the whole point of the receipt
    assert sorted(k for k in receipt["skipped_rule_ids"] if k.startswith("rule_")) == [
        f"rule_{i:02d}" for i in range(MAX_PLAYS, overflow)]


def test_the_generic_fallback_is_tagged_non_prescriptive():
    """The fallback was written by the ADAPTER, not by any expert — a card built from it must
    never render as a confident instruction."""
    from genios_engine.reason.adapters.expertise import _plays

    class _Empty:
        expert_rules = ()
        adaptive_preferences = ()

    plays, receipt = _plays(_Empty())
    assert receipt["generic_fallback_used"] is True
    assert "non_prescriptive" in plays[0].tags
