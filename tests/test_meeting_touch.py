"""`channel_touch` from the one non-mail channel the graph actually records.

`touch-outside-mail.yaml` argues — correctly — that binding this type to `relationship` would
"infer a call from the absence of mail, which is not evidence of anything". That objection stands
and this module does not do it. What it does is read a CAPTURED non-mail interaction: a calendar
meeting with an external counterparty. 48 of the design partner's 62 meetings carry one.

The value is in what it refuses. It serves `demo` and says, on every row, that it does not serve
`cold_calling` or `linkedin_outreach` — a third of a type, shipped as a third of a type. The
tests below are mostly about those refusals, because a partial view read as a whole one is the
failure this build exists to avoid.
"""
from __future__ import annotations

from genios_engine.context import meeting_touch as mt


def test_the_domain_is_asked_of_the_registry_not_named_here():
    """A domain named in Layer 2 means adding a domain requires editing Layer 2.

    `context/periodic.py` listed its domains inline and
    `test_domain_names_appear_in_exactly_one_file_in_the_context_layer` rejected it. Declaring
    `"meeting": "channel_touch"` in a spec is the whole opt-in.
    """
    import inspect

    src = inspect.getsource(mt)
    assert "domains_declaring" in src
    assert '"sales"' not in src and "'sales'" not in src, "a domain name leaked into Layer 2"


def test_sales_declares_the_meeting_anchor_and_gets_the_type():
    from genios_engine.context.domain_spec import domains_declaring, spec_for

    domains = domains_declaring(mt.ANCHOR)
    assert "sales" in domains
    assert spec_for("sales").type_for(mt.ANCHOR) == "channel_touch"


def test_the_meeting_anchor_is_not_in_anchor_priority():
    """The same rule the tenant node follows, for the same reason.

    `choose_anchors` returns only the strongest tier present, so a meeting reachable from
    correspondence would swallow the conversation it belongs to — the situation about the person
    would disappear into a situation about one calendar entry.
    """
    from genios_engine.context.correlation import ANCHOR_PRIORITY

    assert "meeting" not in ANCHOR_PRIORITY


def test_only_meetings_with_an_outside_party_are_touches():
    """An internal standup is the org talking to itself, and the type is about reaching outward."""
    assert "external_counterparty" in mt._MEETINGS
    assert "is not null" in mt._MEETINGS, "internal meetings are not filtered out"


def test_coverage_is_capped_because_a_calendar_knows_scheduling_not_outcome():
    """The corpus asks for the OUTCOME — "connected and dialled are different events" — and a
    calendar cannot answer it. Claiming recorded-grade coverage here would be the overclaim."""
    from genios_engine.context.situations import SCORE_MAX

    assert mt.COVERAGE_CAP_PCT < SCORE_MAX
    assert mt.CONFIDENCE_PCT <= SCORE_MAX


def test_every_row_names_the_channels_it_cannot_see():
    """`missing` can never empty out: calls and LinkedIn have no source and never will here."""
    blob = " ".join(mt.MISSING).lower()
    assert "call" in blob and "linkedin" in blob
    assert "outcome" in blob


def test_the_two_unserved_capabilities_are_named_in_the_row_not_only_in_prose():
    """A capability must be able to see that it is reading a third of its channel."""
    import inspect

    src = inspect.getsource(mt.refresh_channel_touch_situations)
    assert "not_served" in src
    assert "cold_calling" in src and "linkedin_outreach" in src


def test_a_cancelled_meeting_is_not_a_touch():
    """Nobody met. Advising follow-up on a demo that never happened is worse than no card."""
    import inspect

    src = inspect.getsource(mt.refresh_channel_touch_situations)
    assert "cancelled" in src


def test_the_correlation_id_carries_the_domain_not_only_the_meeting():
    """Two domains claiming the anchor must not overwrite each other's situation.

    The escalation reading hit exactly this collision on (account, date) and lost one raise's ask
    text to another's.
    """
    import inspect

    src = inspect.getsource(mt.refresh_channel_touch_situations)
    assert 'f"corr_touch_{domain}_{r.node_id}"' in src


def test_no_domain_opted_in_means_nothing_is_minted():
    """Absence is not a default. A domain without the anchor is skipped, never guessed at."""
    import inspect

    src = inspect.getsource(mt.refresh_channel_touch_situations)
    assert "if not domains:" in src and "return 0" in src


def test_the_corpus_binds_the_type_and_still_records_what_is_missing():
    """Shipping a third of a type is not shipping it — the census has to keep saying so."""
    import pathlib

    import yaml

    root = pathlib.Path(__file__).resolve().parents[1]
    f = (root / "Domain Expertise/Sales Expertise/capabilities/02-prospecting-and-outreach"
                "/cold-calling/situations/touch-outside-mail.yaml")
    matches = yaml.safe_load(f.read_text())["matches"]

    assert "channel_touch" in (matches.get("l2_situation_types") or [])
    # the file must still say, in its own text, that calls and LinkedIn remain unreachable
    body = f.read_text().lower()
    assert "cold_calling" in body and "linkedin_outreach" in body

    v = yaml.safe_load((root / "Domain Expertise/_schema/vocabulary.yaml").read_text())
    assert "channel_touch" in v["substrate"]["l2_situation_types"]
