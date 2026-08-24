"""L2 · Correlation Engine — which events describe the same business situation.

The engine's failure modes are asymmetric, and these tests are weighted accordingly:

  * Splitting one situation in two → a duplicate card. Annoying.
  * Merging two situations → a chimera, reasoned about at full confidence. Two
    customers' problems fused into one recommendation.

So most of these assert that things stay APART. The scenarios below are the real ones
an enterprise produces, not synthetic shapes.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.context.correlation import (CORRELATION_WINDOW_DAYS, DEFAULT_DOMAIN,
                                               JOINED_VIA_ANCHOR, JOINED_VIA_THREAD,
                                               Anchor, choose_anchors, joins_window,
                                               merged_span, plan_correlation,
                                               resolve_domain)

NOW = datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)


def _days(n: int) -> datetime:
    return NOW + timedelta(days=n)


# ── domain resolution ────────────────────────────────────────────────────────────

def test_the_strongest_hint_wins() -> None:
    """Ranked by ORIGIN, not by arrival order.

    A source prior is a fact about the connector — mail from a support desk IS support — so
    nothing outranks it. Position used to decide, which worked only because L1 happened to
    append priors first.
    """
    assert resolve_domain([{"domain": "sales", "source": "scope"},
                           {"domain": "support", "source": "keyword"}]) == "sales"
    # …and still wins when it arrives second, which position could never guarantee
    assert resolve_domain([{"domain": "support", "source": "keyword"},
                           {"domain": "sales", "source": "scope"}]) == "sales"


def test_the_model_outranks_a_keyword() -> None:
    """The model read the whole message; a keyword is a substring test with no idea where it hit.

    A regex matching "error" four times inside a confidentiality footer typed the design
    partner's most important fundraising thread as `support`, while the model's own reading of
    that same message — ["venture_capital", "startup_funding"] — was written into an observation
    and then discarded.
    """
    assert resolve_domain([{"domain": "support", "source": "keyword"},
                           {"domain": "venture_capital", "source": "model"}]) == "venture_capital"


def test_two_keywords_still_resolve_deterministically() -> None:
    """Ties inside a rank keep arrival order — never alphabetical, never dict-ordered."""
    hints = [{"domain": "sales", "source": "keyword"}, {"domain": "admin", "source": "keyword"}]
    assert resolve_domain(hints) == "sales"
    assert resolve_domain(hints) == "sales"


def test_no_hint_is_a_bucket_not_an_error() -> None:
    assert resolve_domain([]) == DEFAULT_DOMAIN
    assert resolve_domain(None) == DEFAULT_DOMAIN


# ── anchoring ────────────────────────────────────────────────────────────────────

def test_only_the_strongest_tier_anchors() -> None:
    """An email to a person AT a company is ONE company situation. Anchoring at both
    tiers would duplicate every conversation and double every count."""
    anchors = choose_anchors({"n_person": "person", "n_company": "company"}, "sales")
    assert [a.node_id for a in anchors] == ["n_company"]


def test_a_deal_outranks_its_company() -> None:
    """The deal IS the business object. Anchoring on the company instead is what makes
    two deals at one customer collapse into a single situation."""
    anchors = choose_anchors({"n_deal": "deal", "n_company": "company",
                              "n_person": "person"}, "sales")
    assert [a.node_id for a in anchors] == ["n_deal"]


def test_a_person_anchors_when_there_is_no_company() -> None:
    """A freelancer or a personal gmail address still deserves a situation."""
    anchors = choose_anchors({"n_person": "person"}, "sales")
    assert [(a.node_id, a.node_type) for a in anchors] == [("n_person", "person")]


def test_an_intro_naming_two_companies_creates_two_situations() -> None:
    """Both are real relationships. Dropping one loses it entirely."""
    anchors = choose_anchors({"n_a": "company", "n_b": "company"}, "sales")
    assert {a.node_id for a in anchors} == {"n_a", "n_b"}


def test_anchoring_is_order_independent() -> None:
    """Dict iteration order must never change which situation an event lands in."""
    a = choose_anchors({"n_b": "company", "n_a": "company"}, "sales")
    b = choose_anchors({"n_a": "company", "n_b": "company"}, "sales")
    assert [x.node_id for x in a] == [x.node_id for x in b]


def test_nothing_anchored_is_a_real_answer() -> None:
    """A newsletter, an automated alert, a note about no one. Inventing a group here
    would fill the graph with situations about nobody."""
    assert choose_anchors({}, "sales") == []
    assert choose_anchors({"n_doc": "document", "n_meeting": "meeting"}, "sales") == []


def test_the_same_entity_in_two_domains_is_two_situations() -> None:
    """Acme's renewal and Acme's outage are not one problem. Same node, different key."""
    sales = choose_anchors({"n_acme": "company"}, "sales")[0]
    support = choose_anchors({"n_acme": "company"}, "support")[0]
    assert sales.base_key != support.base_key


def test_the_same_entity_and_domain_is_one_situation() -> None:
    a = Anchor("n_acme", "company", "sales")
    b = Anchor("n_acme", "company", "sales")
    assert a.base_key == b.base_key


# ── time windows ─────────────────────────────────────────────────────────────────

def test_a_live_conversation_stays_one_situation() -> None:
    assert joins_window(group_first=_days(-10), group_last=_days(-1), event_at=NOW)


def test_a_long_silence_starts_a_new_situation() -> None:
    """The renewal lost in March is not the renewal being worked in September."""
    stale = _days(-(CORRELATION_WINDOW_DAYS + 10))
    assert not joins_window(group_first=stale, group_last=stale, event_at=NOW)


def test_a_late_arriving_event_joins_instead_of_forking() -> None:
    """A connector recovering from an outage delivers OLD events after new ones. Measuring
    only from the group's latest event would push them into a fresh generation and split
    one situation in two — correlation quietly getting worse after every outage."""
    assert joins_window(group_first=_days(-5), group_last=NOW, event_at=_days(-20))


def test_an_event_older_than_the_whole_window_still_forks() -> None:
    assert not joins_window(group_first=NOW, group_last=NOW,
                            event_at=_days(-(CORRELATION_WINDOW_DAYS + 1)))


def test_an_undated_event_never_extends_a_window() -> None:
    """No occurred_at means no evidence about WHEN. Letting it join would silently
    stretch a situation's span to include a period nothing happened in."""
    assert not joins_window(group_first=_days(-1), group_last=NOW, event_at=None)


def test_an_empty_group_accepts_its_first_event() -> None:
    assert joins_window(group_first=None, group_last=None, event_at=NOW)


def test_the_span_widens_in_both_directions() -> None:
    """A late old event legitimately moves a situation's START backwards."""
    first, last = merged_span(group_first=_days(-5), group_last=NOW, event_at=_days(-20))
    assert (first, last) == (_days(-20), NOW)
    first, last = merged_span(group_first=_days(-5), group_last=_days(-1), event_at=NOW)
    assert (first, last) == (_days(-5), NOW)


def test_an_undated_event_does_not_move_the_span() -> None:
    assert merged_span(group_first=_days(-5), group_last=NOW,
                       event_at=None) == (_days(-5), NOW)


# ── the whole decision ───────────────────────────────────────────────────────────

def test_a_bare_reply_inherits_its_conversation() -> None:
    """"sounds good, thanks" — no company named, no keyword, nothing anchored. Without
    thread inheritance every reply becomes its own island, and correlation looks like it
    is working while doing nothing."""
    plan = plan_correlation(thread_correlation_ids=["corr_1"], node_types={},
                            domain_hints=[])
    assert plan.via == JOINED_VIA_THREAD
    assert plan.inherited_correlation_ids == ("corr_1",)
    assert plan.anchors == ()


def test_a_thread_beats_the_events_own_anchor() -> None:
    """The 5th email in a thread mentioning 'pricing' must not fork the conversation into
    a second, sales-domain situation. It also must not land in BOTH — one conversation
    living in two places is the same corruption as two conversations in one."""
    plan = plan_correlation(thread_correlation_ids=["corr_1"],
                            node_types={"n_acme": "company"},
                            domain_hints=[{"domain": "sales"}])
    assert plan.via == JOINED_VIA_THREAD
    assert plan.anchors == ()
    assert plan.inherited_correlation_ids == ("corr_1",)


def test_a_thread_spanning_two_situations_joins_both() -> None:
    """A reply on a thread that was itself an intro to two companies belongs to both."""
    plan = plan_correlation(thread_correlation_ids=["corr_a", "corr_b"],
                            node_types={}, domain_hints=[])
    assert plan.inherited_correlation_ids == ("corr_a", "corr_b")


def test_a_repeated_thread_correlation_is_not_doubled() -> None:
    """Two facts from one event pointing at the same group must not join it twice."""
    plan = plan_correlation(thread_correlation_ids=["corr_a", "corr_a", "corr_b"],
                            node_types={}, domain_hints=[])
    assert plan.inherited_correlation_ids == ("corr_a", "corr_b")


def test_a_first_email_with_no_thread_uses_its_anchor() -> None:
    plan = plan_correlation(thread_correlation_ids=[],
                            node_types={"n_acme": "company"},
                            domain_hints=[{"domain": "sales"}])
    assert plan.via == JOINED_VIA_ANCHOR
    assert [a.node_id for a in plan.anchors] == ["n_acme"]
    assert plan.anchors[0].domain == "sales"


def test_an_unanchored_threadless_event_correlates_to_nothing() -> None:
    plan = plan_correlation(thread_correlation_ids=[], node_types={}, domain_hints=[])
    assert plan.is_empty


def test_the_decision_is_pure_and_repeatable() -> None:
    """Same inputs, same grouping — every time, including on replay. A correlation that
    depends on when it ran cannot be rebuilt, and a graph that cannot be rebuilt cannot
    be trusted."""
    args = dict(thread_correlation_ids=[], node_types={"n_a": "company", "n_b": "company"},
                domain_hints=[{"domain": "sales"}])
    assert plan_correlation(**args) == plan_correlation(**args)


# ── the documented limitation ────────────────────────────────────────────────────

def test_two_deals_at_one_company_separate_when_the_deals_are_known() -> None:
    plan_a = plan_correlation(thread_correlation_ids=[],
                              node_types={"deal_1": "deal", "n_acme": "company"},
                              domain_hints=[{"domain": "sales"}])
    plan_b = plan_correlation(thread_correlation_ids=[],
                              node_types={"deal_2": "deal", "n_acme": "company"},
                              domain_hints=[{"domain": "sales"}])
    assert plan_a.anchors[0].base_key != plan_b.anchors[0].base_key


def test_two_deals_at_one_company_merge_when_no_crm_is_connected() -> None:
    """THE KNOWN LIMITATION, pinned so it stays a decision rather than a surprise.

    Same company, same domain, same period, no deal object — nothing deterministically
    available tells these apart. Splitting them on wording would be exactly the
    over-correlation this engine refuses. Connect a CRM and the test above applies.
    """
    plan_a = plan_correlation(thread_correlation_ids=[], node_types={"n_acme": "company"},
                              domain_hints=[{"domain": "sales"}])
    plan_b = plan_correlation(thread_correlation_ids=[], node_types={"n_acme": "company"},
                              domain_hints=[{"domain": "sales"}])
    assert plan_a.anchors[0].base_key == plan_b.anchors[0].base_key


# ── every lane must reach the same situations ────────────────────────────────────
#
# The headline case is four systems reporting one reality: Slack and email say part of
# it, the CRM deal and the calendar invite say the rest. If only the email lane
# correlates, two of the four never meet and the engine looks like it works.

def test_the_structured_lane_correlates_too() -> None:
    """CRM deals and calendar events go through commit_structured, which bypasses the
    extraction pipeline entirely. Correlating in only one lane silently excludes every
    deal and every meeting from every situation."""
    import inspect

    from genios_engine.context.structured import commit_structured
    source = inspect.getsource(commit_structured)
    assert "correlate_event(" in source


def test_the_structured_lane_correlates_before_committing() -> None:
    import inspect

    from genios_engine.context.structured import commit_structured
    source = inspect.getsource(commit_structured)
    assert source.index("correlate_event(") < source.index("store.write_change(")


def test_our_own_attendees_never_anchor_a_meeting() -> None:
    """A calendar invite lists US as attendees. Anchoring on our own people would file
    every meeting in the company into one enormous situation."""
    import inspect

    from genios_engine.context.structured import commit_structured
    source = inspect.getsource(commit_structured)
    assert "internal_emails" in source
    assert 'rel["node_type"] == "person" and key in internal' in source


def test_a_newsletter_never_joins_a_customers_situation() -> None:
    """A marketing blast naming one of your contacts must not become evidence in a live
    deal. The mention still creates the node and keeps every fact — only the grouping is
    skipped, matching how noise already gets no network edges."""
    import inspect

    from genios_engine.context.pipeline import process_event
    source = inspect.getsource(process_event)
    assert "[] if is_noise else correlate_event(" in source


def test_a_person_is_lifted_to_their_company_before_anchoring() -> None:
    """The same human anchors differently per lane otherwise: the extraction lane builds
    a company from the sender's domain, the structured lane creates a bare attendee. An
    email and a meeting about ONE deal would then sit in two situations that never meet.
    """
    import inspect

    from genios_engine.context.correlation import correlate_event
    assert "lift_people_to_their_companies" in inspect.getsource(correlate_event)


def test_lifting_never_creates_the_company_it_looks_for() -> None:
    """Correlation merges reality; it does not invent entities in order to merge them.
    No company node yet → the person stays the anchor, which is the honest answer."""
    import inspect

    from genios_engine.context.correlation import lift_people_to_their_companies
    source = inspect.getsource(lift_people_to_their_companies)
    assert "insert into" not in source.lower()
    assert "return node_types" in source          # unchanged when nothing is found


def test_no_query_binds_an_untyped_null() -> None:
    """`:param is null` gives Postgres no type to infer and raises at runtime — a failure
    that appears only against a real database, long after the tests looked green."""
    import inspect

    from genios_engine.context import correlation
    assert ":excl is null" not in inspect.getsource(correlation)


# ── surviving an entity merge ────────────────────────────────────────────────────

def test_an_entity_merge_folds_situations_instead_of_repointing_them() -> None:
    """Learning that two customers were one customer must not abort the merge.

    A blind `update anchor_node_id` trips `unique (org, anchor, domain, generation)` the
    moment both nodes hold a sales situation — which is precisely the case when they
    really were the same customer. Postgres would roll the entire merge back.
    """
    from genios_engine.context.merge import _NODE_REFERENCES, _merge_correlations
    assert "context_correlations" not in {table for table, _ in _NODE_REFERENCES}
    assert _merge_correlations is not None


def test_folding_recounts_evidence_instead_of_adding_it() -> None:
    """The same email often reached BOTH nodes before we knew they were one. Summing the
    two totals would claim more evidence than exists."""
    import inspect

    from genios_engine.context.merge import _merge_correlations
    source = inspect.getsource(_merge_correlations)
    assert "count(*) from context_correlation_members" in source
    assert "event_count + " not in source


def test_folding_widens_the_span_across_both_groups() -> None:
    import inspect

    from genios_engine.context.merge import _merge_correlations
    source = inspect.getsource(_merge_correlations)
    assert "least(c.first_event_at" in source
    assert "greatest(c.last_event_at" in source


def test_correlations_run_inside_the_graph_transaction() -> None:
    """A situation must never reference nodes that rolled back. Correlating after the
    commit would leave groups pointing at entities that were never written."""
    import inspect

    from genios_engine.context.pipeline import process_event
    source = inspect.getsource(process_event)
    correlate_at = source.index("correlate_event(")
    commit_at = source.index("store.write_change(")
    assert correlate_at < commit_at


def test_our_own_company_never_anchors_a_situation() -> None:
    """Every outbound email passes through our own domain. Anchoring on it would file
    the entire company into one situation containing everything."""
    import inspect

    from genios_engine.context.pipeline import process_event
    source = inspect.getsource(process_event)
    assert "internal_nodes" in source
    assert "if n not in internal_nodes" in source


def test_correlation_never_scores_or_ranks() -> None:
    """The engine merges reality and stops. Priority, risk and recommendation belong to
    layers that are allowed to have opinions."""
    import inspect

    from genios_engine.context import correlation
    source = inspect.getsource(correlation).lower()
    for forbidden in ("priority", "urgency", "risk_score", "recommend", "llm"):
        assert f"def {forbidden}" not in source
