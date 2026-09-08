"""The tenant J5 is measured against — driven through the PRODUCTION lane, not constructed.

WHY THIS MODULE EXISTS. J5 was last scored against `test_admin_support_packs._run_admin`, which
commits ONE admin email and goes straight to `refresh_situations`. Three of J5's rows came back
"NOT EARNED" and were read as tenant limits. They were not. They were what that shortcut leaves
out:

  * `context/runner.py::process_pending` runs a DERIVED block between the drain and the situation
    refresh — `derived.compute`, `derived.compute_deal_view`, `derived.compute_account_view` — and
    those are what put `thread.ball_in_court` and the correspondence roll-ups on the node a
    situation is ANCHORED on. Skip them and every authored `path:` predicate reads an empty
    anchor, so no corpus rule can fire and the gate reports "no admin rule fires on this fixture".
  * the one admin situation it seeds (`account_admin`) is company-anchored, and the corpus's own
    blocking doctrine for that lane is gated on `commitment.due_at`, which no roll-up reaches a
    company with (see FINDINGS below).
  * `deliver/pipeline.build_cards_for_org` — the last hop, and the one doc 06 calls the
    measurement that says the unlock reached a card — was never called at all.

So this module seeds a tenant the way the product would: real events through `process_event`,
then the production derived block IN PRODUCTION ORDER, then the situation refresh, then the live
compile, then the delivery build. `test_the_seed_runs_the_same_derived_passes_production_runs`
reads `context/runner.py` and fails if that order drifts.

WHAT IS SEEDED, and why each situation is here rather than a third one:

  A · `account_admin` (company-anchored). A counterparty confirms a filing and asks for a signed
      form. This is the lane the shipped admin test proves, kept because it is what carries a
      QUOTED HEURISTIC into `signals.citations` — J5's first hop.
  B · `admin_contact` (person-anchored), a decision parked 45 days ago with no reply since. This
      one exists to trip authored doctrine: `admin.sit.dormant_commitment_reopenable` routes on
      `has_obs: decision_deferred` + 30 days of silence, which pulls
      `admin.executive_support.opportunity_tracking` into the package — and that capability owns
      the BLOCKING rule `no_reopening_on_an_inferred_satisfaction`, whose `when` is a single
      `has_obs: decision_deferred` read off the anchor's own observations. It fires, and it
      eliminates the very play the capability would otherwise have recommended
      (`reopen_with_the_evidence_named`). The doctrine and the play disagree, and the doctrine
      wins. Nothing here is tuned to make that happen: the situation is the one the corpus author
      wrote the rule for.

FINDINGS THIS SEED MADE VISIBLE, recorded here because they are worth more than the gate rows:

  1. Of the Admin corpus's nine rules, six are `severity: blocking` — so Admin does NOT ship
     doctrine that binds nothing. But only ONE of the six can fire on a situation that reaches a
     signal. See `tests/reason/adapters/test_l3_pilot_report.py::
     test_the_admin_corpus_rules_are_enumerated_with_what_each_one_needs` for the enumeration.
  2. `admin.rule.inbox_and_correspondence.a_draft_may_not_commit_the_principal` is authored
     `enforced_by: L5_validation`, so the rule compiler refuses it by name
     (`rule_enforced_by_l5_validation`). It is a blocking rule that Layer 4 correctly never runs.
  3. Two blocking rules (`gatekeeping.evidence_then_a_structural_fix`,
     `goal_and_progress.no_goal_no_reading`) DO fire — on the tenant-anchored
     `admin_period_review` situation — and no card can ever come of it: a period correlation has
     no evidence members, so `core.constraint` eliminates every candidate with
     `evidence_required` and the decision is BLOCKED before a signal is written.
  4. `commitment.due_at` never reaches a COMPANY node. `derived.compute_deal_view`'s two-hop
     commitment roll-up walks `company -> person -> commitment`, and `pipeline._works_at` writes
     the edge `person -> company`. That is the same edge-direction defect `derived._person_
     neighbours` documents for two other roll-ups and fixed for itself; this third instance is
     still open. Three admin rules — `commitment_tracking.no_chase_while_we_hold_the_ball`,
     `approval_coordination.an_unowned_decision_is_not_a_slow_one` and the situation
     `admin.sit.money_owed_either_way` — are gated on that fact and are dark because of it.

NO PRODUCTION CODE IS TOUCHED HERE, and nothing is activated: `l3_activation` is not imported and
`use_domain_compiler` is not read or written.
"""
from __future__ import annotations

from datetime import timedelta

from sqlalchemy import text

from genios_engine.context import situations
from genios_engine.context.pipeline import process_event

from ...l1_supply import attach_l1_signals

from ...test_admin_support_packs import NOW, _FakeLLM, _seed_event, _seed_org

#: The instant the whole seed is evaluated at. One clock for the drain, the roll-ups, the
#: situation refresh, the compile and the delivery build — a sweep that reads two clocks is not
#: replayable, and J5's byte-identity row is a claim about replay.
EVAL_TIME = NOW

#: How far back situation B's last inbound sits. `admin.sit.dormant_commitment_reopenable`
#: routes on `days_since(thread.last_inbound) >= 30`; 45 clears it without sitting on the
#: boundary, where a one-day change in `EVAL_TIME` would silently un-route the situation and take
#: the elimination row with it.
DORMANT_DAYS = 45

#: The blocking rule this seed exists to trip, and the play it removes. Named here so the test
#: asserts against the corpus's own ids rather than against "some rule fired".
BLOCKING_RULE = "admin.rule.opportunity_tracking.no_reopening_on_an_inferred_satisfaction"
ELIMINATED_PLAY = "admin.pb.opportunity_tracking.reopen_with_the_evidence_named"

# =================================================================================================
# THE TWO EMAILS. Every fact, commitment and observation below is SUBSTRING-BACKED against its own
# content: `keep_grounded` silently discards anything it cannot find in the text, so a canned
# payload that ignores that tests the fixture rather than the system.
# =================================================================================================

_ACCOUNT_CONTENT = (
    "Meera at Northwind Registry confirmed our filing was received and is under review. "
    "She asked us to send the signed authorisation form by 27 August. "
    "We said we will send it on Tuesday.")

_ACCOUNT_CANNED = {
    "relevance": 0.9, "noise_type": "none", "domains": ["admin"],
    "entity_mentions": [
        {"type": "person", "name": "Meera", "email": "meera@northwind-registry.test",
         "evidence_text": "Meera at Northwind Registry"},
        {"type": "company", "name": "Northwind Registry", "email": None,
         "evidence_text": "at Northwind Registry"}],
    "fact_candidates": [
        {"subject": "Meera", "field": "thread.ball_in_court", "value": "us",
         "evidence_text": "asked us to send the signed authorisation form"}],
    # `due_text`, not `due_at`. `pipeline.py` reads `cm["due_text"]` and nothing else, so the
    # shipped admin fixture's `due_at` produced no commitment NODE at all — the promise was
    # extracted and then dropped one line before it became a row.
    "commitments": [
        {"actor": "us", "action": "send the signed authorisation form",
         "due_text": "2026-08-27",
         "evidence_text": "We said we will send it on Tuesday"}],
    "questions": [],
    "observations": [{"kind": "next_step_agreed",
                      "evidence_text": "We said we will send it on Tuesday"}],
}

#: A FREE-MAIL sender, deliberately. `pipeline` never mints a company from gmail.com, and
#: `correlation.ANCHOR_PRIORITY` ranks company above person — so with a corporate domain this
#: same email would anchor on the company and type `account_admin`, and the person-anchored
#: `admin_contact` lane the corpus authored `dormant_commitment_reopenable` for would never open.
_DORMANT_CONTENT = (
    "Rana wrote back about the authorisation we asked for last month. "
    "She said the committee has parked the decision until the next sitting "
    "and there is no date for it yet. "
    "She also said our earlier request is still on file.")

_DORMANT_CANNED = {
    "relevance": 0.9, "noise_type": "none", "domains": ["admin"],
    "entity_mentions": [
        {"type": "person", "name": "Rana", "email": "rana.desai@gmail.com",
         "evidence_text": "Rana wrote back about the authorisation"}],
    "fact_candidates": [
        {"subject": "Rana", "field": "thread.ball_in_court", "value": "us",
         "evidence_text": "our earlier request is still on file"}],
    "commitments": [],
    "questions": [],
    "observations": [
        {"kind": "decision_deferred",
         "evidence_text": "the committee has parked the decision until the next sitting"}],
}


def _commit(store, org: str, *, event_id: str, content: str, canned: dict,
            sender: str, occurred_at) -> None:
    with store.engine.begin() as conn:
        _seed_event(conn, org, event_id, "admin")
        # `_seed_event` stamps every row at NOW; this one is the tenant's older correspondence and
        # the situation that reads it is a silence detector, so the event has to carry its real
        # date or `days_since` measures nothing.
        conn.execute(text("update source_events set occurred_at = :t "
                          "where org_id = :o and event_id = :e"),
                     {"t": occurred_at, "o": org, "e": event_id})
    result = process_event(org_id=org, event_id=event_id, source="gmail", content=content,
                           sender_email=sender, occurred_at=occurred_at, llm=_FakeLLM(canned),
                           store=store, is_inbound=True, internal_emails=frozenset(),
                           domain_hints=[{"domain": "admin"}])
    assert result.outcome == "committed", f"{event_id}: {result.outcome}"


def derive(store, org: str, *, eval_time=EVAL_TIME) -> int:
    """The derived block `context/runner.py::process_pending` runs between drain and refresh.

    Three passes, in production's order and with production's clock. This is not decoration: the
    anchor a situation compiles against holds NO fact of its own until they run — a company node
    is empty by construction — and every authored `path:` predicate in the corpus reads the anchor.
    Without this block the Admin corpus's rules cannot be evaluated at all, which is exactly the
    state J5 last measured and read as "no admin rule fires".
    """
    from genios_engine.context.derived import compute as compute_derived
    from genios_engine.context.derived import compute_account_view, compute_deal_view
    written = compute_derived(store, org, now=eval_time)
    written += compute_deal_view(store, org, now=eval_time)
    written += compute_account_view(store, org, now=eval_time)
    return written


def seed_runtime_brains(store, org: str, *, eval_time=EVAL_TIME) -> dict:
    """Publish one Organization rule, one Behaviour pattern and one Adaptive lease FOR THIS TENANT.

    **WHY THE SEED HAS TO DO THIS AT ALL.** J5's row 4 — *a package with non-empty
    Org/Behavior/Adaptive slices* — is the layer's headline claim: the tenant's own learned
    knowledge changes a decision. It read 0 for three months, and the report could not tell a
    reader whether that meant "the brains are empty" (a Layer 6 problem) or "the brains are full
    and unselectable" (a Layer 3 problem). It meant the second, measured on a tenant holding six
    Behaviour entries, five Organization entries and a live lease.

    So the seed publishes all three, and it publishes them **through `feedback/publisher`** — the
    production writers — rather than by INSERT. A fixture that hand-writes rows proves the
    selector can find rows that fixture wrote; this proves it can find what the product writes,
    including the visibility normalisation (`organization` -> `org`) and the missing columns
    (`temporary_memories` has no `brain` and no `version`) that the compiler's readers have to
    absorb.

    **THE THREE ADDRESSES ARE THE THREE SHAPES THAT USED TO FAIL**, one each:

      * ORGANIZATION — `orgrule:approval:contract`. Its subject names its own taxonomy and nothing
        a situation knows about itself, so it matched nothing. It is org-wide by construction and
        binds through `brain_address.org_scope`.
      * BEHAVIOUR — `behavior:<metric>:<node_id>`. It knew which entity it measured; the situation
        knew its counterparties by EMAIL. The address carries the node id, and
        `gather_brain_subject_keys` resolves the situation's emails to the same node ids.
      * ADAPTIVE — a lease in `temporary_memories`, a table Layer 3 never read at all. It is
        published with a real TTL so the expiry is judged against the compile's frozen clock.
    """
    from genios_engine.contracts.brain_address import BrainAddress, org_scope
    from genios_engine.contracts.brain_address import token as address_token
    from genios_engine.contracts.learning import (LearningEvidence, LearningObject,
                                                  LearningTarget, Visibility, VisibilityScope)
    from genios_engine.feedback.publisher import publish_brain, publish_runtime

    def _object(*, target, subject, value, expires_at=None) -> LearningObject:
        return LearningObject(
            org_id=org, unit="l3_pilot_seed", target=target, subject=subject,
            proposed_value=value,
            evidence=LearningEvidence(observations=3, independent_refs=3, distinct_days=3,
                                      positive=3, negative=0, confidence_bp=9000,
                                      distinct_entities=1),
            visibility=Visibility(scope=VisibilityScope.ORGANIZATION),
            first_seen_at=eval_time - timedelta(days=30), last_seen_at=eval_time,
            expires_at=expires_at, policy_key="l3_pilot")

    # THE NODE MUST BE ONE THE SITUATION IS ACTUALLY ABOUT, and that is the property under test.
    #
    # Read through `canonical_key` from a seeded correspondent's ADDRESS rather than taking the
    # first person node in the tenant: the whole defect was that a Behaviour pattern names a
    # `node_id` while a correlated situation names EMAIL ADDRESSES, and this seed only proves the
    # two now meet if the node it publishes against is the node that email resolves to. Picking an
    # arbitrary person would make the test pass or fail on node-id sort order.
    #
    # A Behaviour entry measured on somebody this situation is NOT about must still not bind, and
    # it does not — that is selection working, not a gap.
    def _node(email: str) -> str:
        with store.engine.connect() as c:
            node = c.execute(text(
                "select node_id from graph_nodes where org_id = :o and valid_to is null "
                "and node_type = 'person' and lower(canonical_key) = :email"),
                {"o": org, "email": email}).scalar()
        assert node, (f"{email} has no graph node — the Behaviour address has nothing to name, "
                      "and the L1 -> L2 identity lane is the thing that broke")
        return node

    # TWO BEHAVIOUR ENTRIES, and the second one is the control.
    #
    # `rana.desai@gmail.com` is the ANCHOR of the `admin_contact` situation, so a pattern measured
    # on their node is a pattern about a person this situation is about, and it must bind.
    # `meera@northwind-registry.test` corresponds on the OTHER situation and is not named by this
    # one, so a pattern measured on her must NOT bind. Without the control, a selector that
    # returned every behaviour row in the tenant would pass this seed and look like the fix.
    person = _node("rana.desai@gmail.com")
    unrelated = _node("meera@northwind-registry.test")

    results: dict[str, str] = {}
    with store.engine.begin() as c:
        results["organization"] = publish_brain(c, _object(
            target=LearningTarget.ORGANIZATION, subject="orgrule:approval:contract",
            value={
                "category": "approval", "subject_type": "contract",
                "statement": "Any contract above INR 5,00,000 requires the founder's approval.",
                "authority_source": "org_rule_discovery",
                "address": BrainAddress(org_id=org, brain="organization",
                                        tokens=org_scope(org)).as_value(),
            }), at=eval_time)
        results["behavior"] = publish_brain(c, _object(
            target=LearningTarget.BEHAVIOR, subject=f"behavior:reply_latency_hours:{person}",
            value={
                "kind": "behavior_pattern", "active": True, "metric": "reply_latency_hours",
                "pattern_statement": "This correspondent replies within a day on 9 threads of 10.",
                "subject_node_id": person,
                "address": BrainAddress(
                    org_id=org, brain="behavior",
                    tokens=(address_token("node", person),
                            address_token("metric", "reply_latency_hours"))).as_value(),
            }), at=eval_time)
        results["behavior_unrelated"] = publish_brain(c, _object(
            target=LearningTarget.BEHAVIOR, subject=f"behavior:reply_latency_hours:{unrelated}",
            value={
                "kind": "behavior_pattern", "active": True, "metric": "reply_latency_hours",
                "pattern_statement": "This correspondent replies within the hour.",
                "subject_node_id": unrelated,
                "address": BrainAddress(
                    org_id=org, brain="behavior",
                    tokens=(address_token("node", unrelated),
                            address_token("metric", "reply_latency_hours"))).as_value(),
            }), at=eval_time)
        results["adaptive"] = publish_runtime(c, _object(
            target=LearningTarget.RUNTIME,
            subject="adaptive:card_timing:admin.executive_support.commitment_tracking",
            value={
                "kind": "timing_lease",
                "capability_id": "admin.executive_support.commitment_tracking",
                "statement": "Three of four recent cards here were marked badly timed.",
                "address": BrainAddress(
                    org_id=org, brain="adaptive",
                    tokens=(address_token(
                        "capability",
                        "admin.executive_support.commitment_tracking"),)).as_value(),
            },
            # Comfortably beyond the compile's frozen clock, so this measures SELECTION and not
            # expiry. The expiry itself is measured by its own test.
            expires_at=eval_time + timedelta(days=7)), at=eval_time)
    return results


def seed_admin_pilot(store, org: str, *, eval_time=EVAL_TIME, build_cards: bool = True,
                     with_brains: bool = False) -> dict:
    """Drive one admin tenant end to end and return every stage's counts.

    Returns ``{"derived": n, "compile": {...}, "delivery": {...}}`` — the raw tallies, so a test
    that wants to assert on a stage does it against the number the stage reported rather than
    against a re-derived one.
    """
    from genios_engine.packs.wiring import ensure_defaults, make_registry

    _seed_org(store, org)
    _commit(store, org, event_id="pilot_account", content=_ACCOUNT_CONTENT,
            canned=_ACCOUNT_CANNED, sender="meera@northwind-registry.test",
            occurred_at=eval_time)
    _commit(store, org, event_id="pilot_dormant", content=_DORMANT_CONTENT,
            canned=_DORMANT_CANNED, sender="rana.desai@gmail.com",
            occurred_at=eval_time - timedelta(days=DORMANT_DAYS))

    out: dict = {"derived": derive(store, org, eval_time=eval_time)}
    situations.refresh_situations(store, org, eval_time=eval_time)
    # LAYER 1'S HALF, which this seed never supplied and a customer always does. L2's admission
    # gate (`context/situation_publisher`, migration 0122) refuses to publish a situation carrying
    # no VERIFIED EVIDENCE SPAN, and a verified span only ever arrives on a `qualified_signals`
    # row. This seed drives `process_event` straight into `refresh_situations`, so before this
    # line every situation it produced was HELD and `shadow_compile` returned a clean
    # `admission_hold` with no `compiled`, no `reasoned` and no `emitted` — a pilot tenant that
    # reasoned about nothing, which is not what the module docstring above claims to seed.
    #
    # The gate is untouched and still refuses a tenant without these rows; what changed is that
    # the seed now supplies what a customer supplies. See `tests/l1_supply` for why the span takes
    # `verify_evidence_spans`' documented "no source text -> Layer 1's flag stands" branch.
    out["l1_signals"] = attach_l1_signals(store, org, eval_time=eval_time)

    url = store.engine.url.render_as_string(hide_password=False)
    registry = make_registry(url)
    ensure_defaults(registry, org)

    # BEFORE THE COMPILE, because the compile is what has to find them. Published after the graph
    # exists, because the Behaviour address names a node the graph had to mint first.
    if with_brains:
        out["brains"] = seed_runtime_brains(store, org, eval_time=eval_time)

    from genios_engine.reason.domain_shadow import shadow_compile
    out["compile"] = dict(shadow_compile(store=store, org_id=org, eval_time=eval_time,
                                         live=True, registry=registry))
    if build_cards:
        from genios_engine.deliver.pipeline import build_cards_for_org
        from genios_engine.deliver.store import CardStore
        out["delivery"] = build_cards_for_org(
            graph=store, card_store=CardStore(url), org_id=org, llm=None,
            registry=registry, eval_time=eval_time)
    return out


__all__ = ["BLOCKING_RULE", "DORMANT_DAYS", "ELIMINATED_PLAY", "EVAL_TIME", "NOW",
           "derive", "seed_admin_pilot", "seed_runtime_brains"]
