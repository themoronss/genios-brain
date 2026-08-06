"""L2 · Canon Correlation — company knowledge as a participant, not a passenger.

THE BUG THIS STEP CLOSES

Layer 1 built the door for company knowledge and gave it the highest authority in the
system. Layer 2 then did almost nothing with it: the author is an internal seat, so every
extracted fact attached to the AUTHOR's person node, and internal nodes are excluded from
correlation anchors. **A refund policy became facts about the colleague who typed it, and
reached no situation at all.**

The most authoritative material in the system was also the least connected.
"""
from __future__ import annotations

import inspect

from genios_engine.capture.internal_knowledge import (ANCHORING_KINDS, INTERNAL_KINDS,
                                                      is_anchoring)
from genios_engine.context.canon import (canon_key, canon_title_key, anchors_situations,
                                         resolve_canon_mention)
from genios_engine.context.correlation import ANCHOR_PRIORITY, choose_anchors
from genios_engine.context.identity import ALIAS_CANON, ALIAS_COMPANY_NAME


# ── anchoring vs reference ───────────────────────────────────────────────────────

def test_work_in_flight_anchors_but_standing_knowledge_does_not() -> None:
    """The line is not about importance — pricing may matter more than any one project.
    It is about whether other events CLUSTER around it. Emails cluster around a project;
    nothing clusters around a refund policy."""
    assert is_anchoring("project") is True
    for reference in ("policy", "sop", "pricing", "product", "wiki", "asset",
                      "org_structure", "employee_profile", "goal", "kpi"):
        assert is_anchoring(reference) is False, reference


def test_a_policy_never_opens_its_own_situation() -> None:
    """One situation per policy document would bury the handful that need attention under
    a filing cabinet — the opposite of what situations are for."""
    assert anchors_situations("policy") is False
    assert anchors_situations("pricing") is False


def test_every_anchoring_kind_is_a_real_kind() -> None:
    assert ANCHORING_KINDS <= INTERNAL_KINDS


def test_a_project_outranks_the_company_it_belongs_to() -> None:
    """"The Phoenix migration" must not be filed under "Acme" alongside the renewal — a
    named project is the more specific thing."""
    assert ANCHOR_PRIORITY.index("project") < ANCHOR_PRIORITY.index("company")
    assert ANCHOR_PRIORITY.index("deal") < ANCHOR_PRIORITY.index("project")


def test_a_project_anchors_over_a_company_in_practice() -> None:
    anchors = choose_anchors({"n_proj": "project", "n_acme": "company",
                              "n_person": "person"}, "general")
    assert [a.node_id for a in anchors] == ["n_proj"]


def test_the_anchor_list_is_derived_not_restated() -> None:
    """Adding an anchoring kind must be ONE edit in the Layer 1 vocabulary. A second
    hand-written list in Layer 2 is how the source registry drifted before it was
    unified."""
    from genios_engine.context.correlation import _anchor_priority
    assert "ANCHORING_KINDS" in inspect.getsource(_anchor_priority)
    assert set(ANCHORING_KINDS) <= set(ANCHOR_PRIORITY)


# ── canon identity ───────────────────────────────────────────────────────────────

def test_a_canon_node_reads_like_a_system_of_record() -> None:
    """Shaped like the structured lane's `<source>:<object id>` — because canon IS a
    system of record, and the company is the system."""
    assert canon_key("policy", "refund-policy") == "internal:policy:refund-policy"


def test_the_same_document_is_one_entity_however_it_is_written() -> None:
    assert canon_title_key("Refund Policy") == canon_title_key("refund  policy")
    assert canon_title_key("Project Phoenix!") == canon_title_key("project phoenix")


def test_an_untitled_document_resolves_to_nothing_rather_than_everything() -> None:
    assert canon_title_key("") is None
    assert canon_title_key(None) is None


def test_a_project_named_like_a_customer_does_not_collide_with_it() -> None:
    """A project called "Acme" and the customer called "Acme" are different things.
    Separate alias namespaces mean they can never contend for the same key, so no false
    merge proposal is raised and a company mention still resolves to the company."""
    assert ALIAS_CANON != ALIAS_COMPANY_NAME


def test_canon_mentions_resolve_by_name_because_type_is_unavailable() -> None:
    """FORCED, not chosen. The extraction prompt never asks for a "project" entity type
    and _NODE_TYPES has no entry for one — so a type-based lookup would silently never
    fire, and the whole feature would look built while doing nothing."""
    from genios_engine.context.extract.prompt import B3_PROMPT
    from genios_engine.context.pipeline import _NODE_TYPES
    assert "project" not in _NODE_TYPES
    assert '"type": "project"' not in B3_PROMPT
    assert "alias_type=ALIAS_CANON" in inspect.getsource(resolve_canon_mention)


def test_resolving_a_mention_never_creates_anything() -> None:
    """A name nobody declared as company knowledge is just a name. Inventing a project
    because someone capitalised a word would fill the graph with work that does not
    exist."""
    source = inspect.getsource(resolve_canon_mention)
    assert "insert" not in source.lower()
    assert "find_or_create" not in source


# ── the hot path ─────────────────────────────────────────────────────────────────

def test_canon_facts_attach_to_the_document_not_its_author() -> None:
    """The whole bug. Without this a refund policy is facts about a colleague."""
    from genios_engine.context.pipeline import process_event
    source = inspect.getsource(process_event)
    assert "content_subject = canon_node or sender_node" in source
    assert "_resolve_subject(f.get(\"subject\"), name_to_node, content_subject)" in source


def test_network_edges_are_not_rerouted_to_the_document() -> None:
    """Who corresponded with whom is a fact about PEOPLE. Rerouting it would make a
    policy document appear to have colleagues."""
    from genios_engine.context.pipeline import process_event
    source = inspect.getsource(process_event)
    assert "_works_at(sender_email, sender_node)" in source
    assert "(sender_node, rnode)" in source


def test_an_ordinary_email_is_completely_unaffected() -> None:
    """process_event is the hot path for EVERY event. Canon handling must be inert when
    internal_kind is absent, or this step's blast radius is the entire product."""
    from genios_engine.context.pipeline import process_event
    source = inspect.getsource(process_event)
    assert "canon_node = None" in source
    assert "if internal_kind:" in source


def test_one_uploaded_file_becomes_one_entity_not_one_per_chunk() -> None:
    """A 30-chunk pricing PDF keyed on the event would give thirty separate "Pricing"
    entities, each holding a slice of one document — the graph would look like thirty
    price lists."""
    from genios_engine.api.upload_routes import _emit_chunk
    source = inspect.getsource(_emit_chunk)
    assert '"knowledge_key": file_id' in source


def test_canon_participates_in_correlation() -> None:
    """The point of the whole step: the canon node reaches the anchor set."""
    from genios_engine.context.pipeline import process_event
    assert "touched[canon_node] = internal_kind" in inspect.getsource(process_event)


def test_a_resolved_mention_carries_its_real_node_type() -> None:
    """The bug that would have made this feature inert.

    Correlation anchors on node TYPE. A resolver returning only an id forces the caller to
    invent one, and an invented type matches nothing in ANCHOR_PRIORITY — so a Slack
    message naming "Project Phoenix" would resolve to the project perfectly and then
    correlate under nothing. Built, green, and doing nothing.
    """
    import typing
    hints = typing.get_type_hints(resolve_canon_mention)
    assert hints["return"] == typing.Optional[tuple[str, str]]
    source = inspect.getsource(resolve_canon_mention)
    assert "select node_type from graph_nodes" in source

    from genios_engine.context.pipeline import process_event
    pipeline_source = inspect.getsource(process_event)
    assert "canon_id, canon_type = canon_hit" in pipeline_source
    assert "touched.setdefault(canon_id, canon_type)" in pipeline_source


def test_a_company_mention_wins_over_a_canon_title() -> None:
    """When one name could mean either, the customer wins: its alias is derived from a
    real email domain, which is harder evidence than a title somebody typed. An earlier
    draft checked canon first, contradicting the comment that documented this."""
    from genios_engine.context.pipeline import process_event
    source = inspect.getsource(process_event)
    assert source.index("resolve_company_mention(") < source.index("resolve_canon_mention(")


# ── what Step 6 refuses ──────────────────────────────────────────────────────────

def test_layer2_does_not_compare_events_against_policy() -> None:
    """"1000 leads uploaded, only 130 match ICP" is domain expertise — Layer 3. Building
    it here would repeat the risk-detector mistake: two layers with an opinion about the
    same thing and no way to tell which one was wrong."""
    from genios_engine.context import canon
    source = inspect.getsource(canon).lower()
    for forbidden in ("def compare", "icp", "def evaluate", "violat"):
        assert forbidden not in source


def test_layer2_does_not_track_progress_against_goals() -> None:
    """Goal progress is a judgement about how things are going — Layer 4's job."""
    from genios_engine.context import canon
    source = inspect.getsource(canon).lower()
    for forbidden in ("progress", "on_track", "attainment"):
        assert forbidden not in source


def test_canon_never_anchors_on_our_own_company() -> None:
    """That would recreate the Step 2 bug where every outbound email filed into one
    enormous situation containing the whole business."""
    from genios_engine.context.pipeline import process_event
    source = inspect.getsource(process_event)
    assert "if n not in internal_nodes" in source
