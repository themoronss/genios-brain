"""Direction, roles and pack vocabulary reach the extractor.

Three defects sat under most of what a customer saw, and all three were seams that existed on
paper and carried nothing:

  * the model was handed a body with no From, no To and no direction, so an outbound offer and
    an inbound request were the same text — this is how "as requested, here is the demo",
    written BY the account owner, became a card telling him to book a demo with his own
    product's invite address;
  * "us" was sourced from `org_seats`, which a self-serve tenant never fills, so every
    self-filter passed everything;
  * the pack declared the field and observation names its rules read, and `registry.effective()`
    dropped them, so the extractor invented synonyms that were stored and never consulted.
"""
from __future__ import annotations

from genios_engine.context.extract.envelope import Envelope, envelope_from_raw
from genios_engine.context.extract.extractor import build_prompt
from genios_engine.context.extract.vocab import field_vocabulary, observation_vocabulary
from genios_engine.packs.general_v1 import GENERAL_V1
from genios_engine.packs.sales_v1 import SALES_V1

OWNER = "founder@startup.com"
INVESTOR = "partner@vc.com"
EFFECTIVE = {"sales": {"pack_id": "sales", **SALES_V1},
             "general": {"pack_id": "general", **GENERAL_V1}}


# ── direction ────────────────────────────────────────────────────────────────────────────────
def test_a_message_we_sent_is_outbound():
    env = Envelope(sender=OWNER, recipients=(INVESTOR,), self_identities=frozenset({OWNER}))
    assert env.direction == "outbound"
    assert env.counterparties == (INVESTOR,)


def test_a_message_they_sent_is_inbound():
    env = Envelope(sender=INVESTOR, recipients=(OWNER,), self_identities=frozenset({OWNER}))
    assert env.direction == "inbound"
    assert env.counterparties == (INVESTOR,), "we are never our own counterparty"


def test_direction_is_unknown_when_we_do_not_know_who_we_are():
    """An empty self-set must produce `unknown`, never a confident guess.

    This is the exact state the design partner was in — `org_seats` had zero rows — and the old
    code did not model it at all: absent "us" simply meant every guard passed, which reads as a
    working system right up until you ask which side of a conversation it thinks it is on.
    """
    env = Envelope(sender=OWNER, recipients=(INVESTOR,), self_identities=frozenset())
    assert env.direction == "unknown"


def test_the_prompt_states_the_direction_and_never_hides_an_unknown():
    outbound = build_prompt("gmail", "as requested, here is the demo",
                            envelope=Envelope(sender=OWNER, recipients=(INVESTOR,),
                                              self_identities=frozenset({OWNER})))
    assert "direction: outbound" in outbound
    assert OWNER in outbound and INVESTOR in outbound

    blind = build_prompt("gmail", "as requested, here is the demo", envelope=Envelope())
    assert "direction: unknown" in blind
    assert "do not " in blind, "an unknown direction must instruct the model not to assume one"


def test_envelope_is_built_from_a_connector_raw_object():
    env = envelope_from_raw({"to": [INVESTOR], "cc": ["analyst@vc.com"]},
                            {OWNER}, sender=OWNER)
    assert env.direction == "outbound"
    assert env.counterparties == (INVESTOR, "analyst@vc.com")


# ── pack vocabulary ──────────────────────────────────────────────────────────────────────────
def test_the_prompt_names_the_fields_the_rules_actually_read():
    """A field the rules read must be a name the model was given.

    Rules key on `deal.status`; the extractor, never told the name, wrote `status`. The rule was
    therefore dead on arrival — not misfiring, never reachable — and nothing in the system
    compared the two lists.
    """
    fields = field_vocabulary(EFFECTIVE)
    assert "deal.status" in fields, "a path the sales rules read is missing from the prompt"
    assert "thread.ball_in_court" in fields
    assert not any(f.startswith("derived.") for f in fields), (
        "derived.* is computed by the reasoner; offering it to the model invites an invented "
        "value the engine either overwrites or, worse, does not")

    prompt = build_prompt("gmail", "body", effective=EFFECTIVE)
    assert "deal.status" in prompt
    assert 'FIELD NAMES' in prompt


def test_the_observation_vocabulary_is_read_from_the_rules_not_the_reason_codes():
    """The kinds a rule CONSULTS, not the reason codes a pack EMITS.

    `schema.signal_vocab` lists `stalled_deal`, `closed_lost_risk` — rule names. Handing those
    to the extractor would ask it to emit rule ids as observations, the same category error that
    keyed the Layer 3 corpus on reason codes and made 73 of 73 situations unroutable.
    """
    kinds = observation_vocabulary(EFFECTIVE)
    assert "closed_lost_mention" in kinds, "an observation a live rule reads"
    assert "stalled_deal" not in kinds, "that is a reason code, not an observation kind"


def test_intent_bearing_kinds_survive_even_with_no_rule_to_read_them():
    """The pack guarantees its kinds; it must not narrow the model to only them.

    `meeting_request`, `question`, `next_step_agreed` and `positive_reply` are the highest-volume
    intent signals in the design partner's graph and no rule reads any of them. Restricting
    extraction to today's thin corpus would stop capturing the evidence tomorrow's rules need,
    which keeps the corpus thin by construction.
    """
    kinds = set(observation_vocabulary(EFFECTIVE))
    for intent in ("meeting_request", "question", "next_step_agreed", "positive_reply"):
        assert intent in kinds, f"{intent} must still be extractable"


def test_a_tenant_with_no_pack_still_gets_a_usable_vocabulary():
    """Degrade, never blank: an unmigrated tenant must keep extracting."""
    assert observation_vocabulary(None), "no pack must fall back to the canonical set"
    assert field_vocabulary(None), "the engine's own fields apply regardless of pack"


def test_the_prompt_separates_commitments_from_scheduling():
    """"Can we do next week?" is a question, not a promise.

    The prompt gave no definition of a commitment, so the extractor filed availability and
    scheduling questions as commitments; the pipeline then minted commitment nodes with invented
    due dates, which went overdue and produced cards ordering the founder to "Deliver" a
    sentence the other party had written.
    """
    prompt = build_prompt("gmail", "body")
    assert "scheduling_proposals" in prompt
    assert "COMMITMENTS" in prompt
    assert 'ends in "?"' in prompt, "the negative rule must be explicit, not implied"


def test_the_prompt_asks_who_each_party_is():
    prompt = build_prompt("gmail", "body")
    assert '"roles"' in prompt
    for role in ("counterparty", "introducer", "introduced", "owner"):
        assert role in prompt, f"the role vocabulary is missing {role!r}"


# ── the platform is not a counterparty ───────────────────────────────────────────────────────
def test_our_own_product_mail_is_never_a_business_relationship():
    """The vendor's transactional mail must not become a prospect in a customer's graph.

    The tenant's self-filter cannot catch this: we genuinely are not the customer, so it
    correctly answers "not us" and the address is admitted as a person. The design partner's
    feed carried three cards on `invite@thegenios.com` — one telling him to book a demo with his
    own product, from a message whose entire body was "Dear Rohit, The life is going to be
    changed for forever now."
    """
    from genios_engine.context.pipeline import is_platform_sender

    assert is_platform_sender("invite@thegenios.com")
    assert is_platform_sender("ceo@thegenios.com")
    assert is_platform_sender("noreply@mail.thegenios.com"), "subdomains are ours too"
    assert not is_platform_sender("partner@antler.co"), "a real counterparty must be unaffected"
    assert not is_platform_sender("thegenios.com"), "a bare domain is not an address"
    assert not is_platform_sender(""), "an empty address must not match anything"


def test_platform_domains_are_configuration_not_a_constant():
    """A white-labelled or self-hosted deployment sends from a different domain.

    Hardcoding the string would make the guard silently stop protecting anyone who rebrands —
    the failure would look exactly like the bug it was meant to fix.
    """
    from genios_engine.platform.config import get_settings

    assert hasattr(get_settings(), "platform_domains")


# ── thread state must not collide across conversations ───────────────────────────────────────
def test_a_thread_gets_its_own_node_so_state_stops_colliding():
    """`graph_facts` keys on (org, subject, field), so person-level thread state is one row.

    One person therefore held exactly one `thread.ball_in_court` across every conversation they
    were part of, last write wins. In the design partner's graph `boardy@boardy.ai` spans 254
    distinct threads and `theresa.hoffmann@antler.co` spans 3 — whichever message landed last
    decided whose turn it was in all of them, and that single fact drives 22 of 41 live signals.
    """
    from genios_engine.context.pipeline import _thread_node

    seen = {}

    class _Store:
        def find_or_create_node(self, _conn, *, org_id, node_type, canonical_key,
                                display_name, event_id):
            seen[canonical_key] = (node_type, display_name)
            return f"node_for_{canonical_key}"

    a = _thread_node(_Store(), None, org_id="o", thread_id="thread_aaa",
                     event_id="e1", counterparty="partner@vc.com")
    b = _thread_node(_Store(), None, org_id="o", thread_id="thread_bbb",
                     event_id="e2", counterparty="partner@vc.com")
    assert a != b, "two conversations with the SAME person must not share one key space"
    assert all(t == "thread" for t, _ in seen.values())


def test_no_thread_id_means_no_thread_node_rather_than_a_shared_one():
    """A message with no thread must not fall into a single catch-all conversation.

    Collapsing them would recreate the exact defect on a different key: every unthreaded message
    from anyone deciding one shared 'whose turn is it'.
    """
    from genios_engine.context.pipeline import _thread_node

    class _Store:
        def find_or_create_node(self, *a, **k):    # pragma: no cover — must never be reached
            raise AssertionError("a node was created for a message with no thread id")

    assert _thread_node(_Store(), None, org_id="o", thread_id=None,
                        event_id="e", counterparty="x@y.com") is None


# ── the loop must be able to settle ──────────────────────────────────────────────────────────
def test_authority_outlasts_the_repeat_window():
    """A decision does not stop being TRUE the moment its card leaves the queue.

    The adapter fed `cooldown_hours` straight into `expiry_hours`, so a card's visible life and
    the rule's suppression window were the same interval: the instant one lapsed the other
    unlocked and the next sweep minted a fresh card for an unchanged fact. There was never a
    moment when the decision still held and nobody was being told again — which is why every
    duplicate pair in the queue existed.
    """
    from types import SimpleNamespace

    from genios_engine.reason.adapters.legacy_pack import _authority_hours

    for cooldown in (48, 72, 120, 168):
        authority = _authority_hours(SimpleNamespace(cooldown_hours=cooldown))
        assert authority > cooldown, (
            "authority must outlast the cooldown, or re-firing is immediate and guaranteed")
    assert _authority_hours(SimpleNamespace(cooldown_hours=100_000)) <= 8_760, "capped at a year"


def test_a_human_verdict_does_not_erase_the_cooldown():
    """Pressing "wrong" must not be the thing that guarantees a repeat.

    The cooldown lookup required `status='open'`. Acting on a card moves its signal to 'acted',
    so it stopped matching and the next sweep raised the identical claim with a new id — the one
    action that most clearly means "stop telling me this" reset the memory of having said it.
    """
    import inspect

    from genios_engine.reason import runner

    sql = inspect.getsource(runner._recent_signal)
    assert "'acted'" in sql and "'resolved'" in sql, (
        "a signal the user has acted on must still count as 'we already said this'")
    assert "config_snapshot_id=:cfg" not in sql, (
        "a config change is not evidence the user wants to hear the same thing again")


# ── the reasoner must be able to choose ──────────────────────────────────────────────────────
def _manifest_for(rule_id: str):
    from genios_engine.packs.sales_v1 import SALES_V1
    from genios_engine.reason.adapters.legacy_pack import legacy_capability_manifest
    from genios_engine.reason.rules import rule_from_dict

    rule = rule_from_dict(next(r for r in SALES_V1["rules"] if r["id"] == rule_id))
    return legacy_capability_manifest(rule=rule, scoring=SALES_V1["scoring_defaults"],
                                      pack_id="sales", pack_version="1.10.0")


def test_waiting_is_a_ranked_candidate_not_an_absence():
    """A capability offering one option is not making a choice.

    The adapter passed a single play, so every run produced exactly one candidate, nothing was
    ever eliminated, and `decision.alternative` and `.stop_condition` had no producer — the card
    contract's fields for them were permanently empty. Waiting is frequently the right answer on
    a thread where only the clock has moved; making it a competitor means the trace can show it
    LOSING, which is what distinguishes choosing to act from being unable not to.
    """
    plays = {p.play_id: p for p in _manifest_for("closed_lost_risk").plays}
    assert len(plays) >= 2, "there must be something for the recommended action to beat"

    wait = next(p for p in plays.values() if p.metadata.get("do_nothing"))
    assert wait.effort_bp == 0 and wait.risk_bp == 0, "waiting costs nothing and risks nothing"
    assert wait.read_only and not wait.success_events


def test_the_wait_option_cannot_outrank_a_real_action_on_impact():
    """Cheap and safe must not mean "always wins" — waiting preserves the option, it does not
    advance the situation, so its impact sits below any play that does."""
    plays = list(_manifest_for("closed_lost_risk").plays)
    wait = next(p for p in plays if p.metadata.get("do_nothing"))
    acting = [p for p in plays if not p.metadata.get("do_nothing")]
    assert acting, "the manifest lost its real play"
    assert all(wait.impact_bp < p.impact_bp for p in acting)


def test_score_components_are_measured_not_placeholders():
    """Four of five ranking inputs were frozen at 5000 on every candidate.

    That makes any unit adjusting impact, risk or effort a no-op, and makes the persisted
    `score_components` read as measurements when nothing was measured.
    """
    plays = [p for p in _manifest_for("closed_lost_risk").plays
             if not p.metadata.get("do_nothing")]
    p = plays[0]
    assert len({p.impact_bp, p.success_probability_bp, p.effort_bp, p.risk_bp}) > 1, (
        "every component is still the same constant")


def test_the_pack_confidence_floor_reaches_the_manifest():
    """The pack has always declared `gate.c_min`; the adapter never carried it.

    So every live manifest omitted `confidence_floor_bp`, the decision maker read its default of
    0, and `confidence_bp < 0` was never true — the system has never once abstained. It can
    BLOCK a candidate, which nobody sees; it could not SAY it did not know.
    """
    from genios_engine.reason.decision_maker import CONFIDENCE_FLOOR_KEY

    floor = _manifest_for("closed_lost_risk").metadata.get(CONFIDENCE_FLOOR_KEY)
    assert floor and floor > 0, "a floor of 0 is a floor that can never be reached"


# ── the reasoning pass must be able to finish ────────────────────────────────────────────────
def test_baselines_are_computed_in_bounded_round_trips():
    """One query per person, and one write for the whole batch — not one of each per node.

    `build_baselines` issued a separate history query per person (110 here) and a separate insert
    per metric (330), each a full network turn against a remote Postgres. The pass took minutes
    and the connection died partway through, so a live verification run could not be completed at
    all — which meant no fix anywhere in the engine could be proven against real data.
    """
    import inspect

    from genios_engine.reason import baselines

    src = inspect.getsource(baselines.build_baselines)
    # the history read is one grouped query, not a lookup inside the person loop
    assert "by_email" in src, "per-person history queries are back"
    assert src.count("select occurred_at from source_events") == 0, (
        "a per-person history query reappeared inside the loop")
    # the write is a single statement over arrays
    assert "unnest" in src, "the batch write was replaced by per-row inserts"


# ── the system must be able to decline ───────────────────────────────────────────────────────
def test_a_card_can_say_it_is_not_advising():
    """`prescriptive` and `predictive` were the only two things a card could ever be.

    Both instruct. With zero reviewed capabilities in the corpus, that meant one hundred percent
    of what reached a user was advice on domains the system holds no accepted expertise for. It
    could BLOCK a candidate — a suppression row nobody sees — but it had no way to SAY it did not
    know, and those are different products.
    """
    from genios_engine.contracts.abstention import ABSTAINING, ACTIONABLE, VALID_LEVELS

    assert {"observation", "review", "wait", "suppress"} <= set(VALID_LEVELS)
    assert ACTIONABLE.isdisjoint(ABSTAINING), "a level either instructs or it does not"


def test_unreviewed_expertise_cannot_produce_an_instruction():
    """Authority, not confidence, decides whether a card may instruct.

    A low-confidence prescription is still a prescription — the user reads it as an instruction
    and acts on it. Downgrading keeps the observation, which is real and useful, and drops only
    the claim to know what should be done about it.
    """
    from genios_engine.deliver.pipeline import _apply_abstention

    out = _apply_abstention({"level": "prescriptive"}, {})
    assert out["level"] == "observation"
    assert out["abstained_because"], (
        "an abstention with no stated cause is indistinguishable from a bug — the user cannot "
        "tell 'outside my coverage' from 'something broke'")


def test_accepted_expertise_keeps_its_authority_to_instruct():
    """The gate must not disarm the product — reviewed expertise still advises."""
    from genios_engine.deliver.pipeline import _apply_abstention

    kept = _apply_abstention({"level": "prescriptive"},
                             {"expertise": {"review_state": "accepted"}})
    assert kept["level"] == "prescriptive" and "abstained_because" not in kept


def test_an_already_abstaining_card_is_left_alone():
    """Downgrading is one-way; re-running the gate must not rewrite a considered refusal."""
    from genios_engine.deliver.pipeline import _apply_abstention

    held = {"level": "wait", "abstained_because": "waiting for the 14 August decision"}
    assert _apply_abstention(held, {}) == held


# ── Layer 7: the learning loop must be honest about itself ───────────────────────────────────
def test_approving_a_review_object_actually_publishes_it():
    """Approval renamed the row and stopped — the human's decision changed nothing.

    `approved_unpublished`: the endpoint set `state='promoted'` and wrote a transition, but no
    brain version was ever written, so nothing any decision path reads had changed. A reviewer
    who approves has every reason to believe the system now knows something. It did not.
    """
    import inspect

    from genios_engine.api import learning_routes

    src = inspect.getsource(learning_routes.review)
    assert "_publish_approved" in src, "approval must publish, not only rename"
    # same transaction: an approval that commits without its publication is the exact split
    assert src.index("_publish_approved") > src.index("learning_transitions")


def test_the_feedback_seam_points_at_a_table_that_exists():
    """`canonical_judgments` is a CTE, not a table — no migration could ever have created it.

    `to_regclass('public.canonical_judgments')` returns NULL, so the seam resolved to nothing
    forever and `batch.feedback` was permanently empty. Every plan that treated this as "the
    table is missing" was chasing something that cannot exist.
    """
    from genios_engine.feedback.store import _OPTIONAL_FEEDBACK_TABLE

    assert _OPTIONAL_FEEDBACK_TABLE == "card_feedback_verdicts"


def test_a_review_queued_object_is_not_counted_as_published():
    """Two ledgers disagreed inside one transaction.

    `counts.published = 1` sat beside `result_state='human_review'` for the same object, because
    the counter incremented on every publish() call regardless of its sink. `published` is the
    number an operator reads, and it was wrong for every review-routed object — which today is
    100% of brain-target objects.
    """
    import inspect

    from genios_engine.feedback import orchestrator

    src = inspect.getsource(orchestrator)
    assert 'queued_for_review' in src
    assert 'if str(sink) == "queued_for_review"' in src, (
        "the counter must branch on the sink, not on the call returning")


def test_a_run_with_empty_inputs_reports_itself_degraded():
    """"Proposed nothing" and "had nothing to read" looked identical in the counts."""
    import inspect

    from genios_engine.feedback import orchestrator

    src = inspect.getsource(orchestrator.run_learning_for_org
                            if hasattr(orchestrator, "run_learning_for_org") else orchestrator)
    assert "degraded_seams" in src


def test_policy_prohibitions_are_loaded_not_defaulted_away():
    """The columns exist and governance enforces them; the SELECT omitted both.

    A tenant's "never learn about these targets" list was therefore loaded as empty on every run.
    Latent only because nothing can write them yet — a silent authority hole the moment a
    policy-write surface exists.
    """
    import inspect

    from genios_engine.feedback import orchestrator

    src = inspect.getsource(orchestrator.load_or_seed_policy)
    assert "blocked_targets" in src and "blocked_subject_prefixes" in src
    assert "blocked_targets=" in src, "loaded into the policy, not merely selected"


# ── the contract needs somewhere to land ─────────────────────────────────────────────────────
def test_the_card_contract_fields_are_produced_not_hardcoded():
    """`stakes` and `completion` were the literal string "missing".

    Not absent by accident — written that way in the read projection at request time. So a card
    that DID carry its cost-of-inaction and its completion criteria still reported that it did
    not, and no amount of upstream work could ever move the number.
    """
    import inspect

    from genios_engine.api import routes
    from genios_engine.deliver import card_builder

    projection = inspect.getsource(routes)
    assert '"stakes": "missing"' not in projection
    assert '"completion": "missing"' not in projection

    built = inspect.getsource(card_builder.build_draft)
    for field in ("business_subject", "relationship_role", "unresolved_item", "why_now",
                  "capability_review_state", "do_nothing_consequence", "confidence_vector"):
        assert field in built, f"{field} has no producer"


def test_business_subject_is_not_the_assignee():
    """`assignee` is a GeniOS seat — the person expected to act.

    The counterparty the action is AIMED at is a different party, and conflating them is how a
    card came to target an introducer as though they were the investor.
    """
    import inspect

    from genios_engine.deliver import card_builder

    src = inspect.getsource(card_builder.build_draft)
    assert '"business_subject": name' in src, (
        "business_subject must be the counterparty, never the seat expected to act")


def test_why_now_refuses_to_call_elapsed_time_a_reason():
    """"It has been 9 days" is a measurement, not a reason.

    Presenting it as one is what manufactured urgency on threads where nothing had happened.
    """
    from genios_engine.deliver.card_builder import _why_now

    assert _why_now("commitment_overdue", {"commitment.action": {"value": "send the deck"}},
                    {"days": 9}, None)
    # an unanswered email with no known ask has no why-now to state
    assert _why_now("unanswered_email", {}, {"days": "several"}, None) is None


def test_the_learned_brains_reach_the_manifest_as_structure():
    """Three brains entered the decision only as bytes inside a hash.

    Organization, Behavior and Adaptive values appeared at exactly two identity-only places — the
    manifest version string and `knowledge_hash` — and a repo-wide grep under `reason/` found
    zero read sites. A tenant could approve an organization rule, watch the hash change, and no
    decision would differ.
    """
    import inspect

    from genios_engine.reason.adapters import expertise

    src = inspect.getsource(expertise)
    assert '"brains"' in src and '"brain_influence"' in src
    assert '"hash_only"' in src, (
        "the manifest must be able to say that no brain influenced this decision")


# ── identity: ambiguity is not a match ───────────────────────────────────────────────────────
def test_a_name_shared_by_two_people_resolves_to_nobody():
    """Two "John"s at different companies is ordinary, not a duplicate.

    Handing a bare-name mention to whichever John was inserted first silently moves every fact,
    commitment and thread state written from that mention onto the wrong person — a merge nobody
    proposed, nobody reviewed, and nothing records. An unresolved mention stays an observation,
    which is recoverable; a wrong resolution is not.
    """
    from genios_engine.context.identity import resolve_alias

    class _Conn:
        def __init__(self, rows):
            self._rows = rows

        def execute(self, *_a, **_kw):
            rows = self._rows

            class _R:
                def fetchall(self):
                    return rows
            return _R()

    assert resolve_alias(_Conn([("node_a",), ("node_b",)]),
                         org_id="o", alias_type="person_name", alias_key="john") is None
    assert resolve_alias(_Conn([("node_a",)]),
                         org_id="o", alias_type="person_name", alias_key="john") == "node_a"
    assert resolve_alias(_Conn([]),
                         org_id="o", alias_type="person_name", alias_key="john") is None


def test_a_caller_can_tell_nobody_from_several():
    """`None` alone conflates "no such name" with "several people have it".

    A surface that wants to ask the user which John they meant needs those to be different
    answers, or it cannot tell a missing contact from an ambiguous one.
    """
    import inspect

    from genios_engine.context import identity

    assert hasattr(identity, "resolve_alias_candidates")
    assert "ambiguity" in inspect.getdoc(identity.resolve_alias).lower()


def test_every_receipt_can_be_traced_to_a_provider_message():
    """`source_object_id` existed as a column and nothing ever wrote it.

    All 3,132 rows carried NULL, so there was no path from a card back to the Gmail message that
    caused it — `evidence` held only derivation labels like {"derived": "email to/cc"}, which say
    what the engine concluded and not what it read.
    """
    import inspect

    from genios_engine.context.graph_store import GraphStore

    src = inspect.getsource(GraphStore._write_ref)
    assert "source_object_id" in src
    assert "from source_events se" in src, (
        "filled by subquery so no writer signature has to change — every threaded parameter is "
        "a chance to forget one call site and leave a silent NULL")
