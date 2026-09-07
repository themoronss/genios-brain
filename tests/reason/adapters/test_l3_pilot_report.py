"""J5's harness, driven against a SEEDED org — and the citation's last two hops, end to end.

`test_weld_reaches_a_signal.py` proves a compiled signal names its losers. This proves what J5
asks on top of that: that the expert CLAIM — a heuristic, quoted byte-for-byte — survives into a
durable row, that the corpus's own BLOCKING doctrine removes a recommendation and signs the
removal, and that a card gets built at the end of it.

WHAT CHANGED AND WHY IT MATTERS. J5 last scored three rows NOT EARNED and two of them were read as
tenant limits. They were fixture limits. `tests/reason/adapters/l3_pilot_seed.py` seeds the same
tenant through the PRODUCTION lane instead — including the derived roll-up block
`context/runner.py::process_pending` runs between the drain and the situation refresh, without
which every authored `path:` predicate reads an empty anchor, and including
`deliver/pipeline.build_cards_for_org`, which was never called at all. Read that module's
docstring for the four findings the exercise turned up.

Real Postgres, real Layer 1 ingestion, real corpus, real reasoning, real delivery.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from sqlalchemy import text

from .l3_pilot_seed import (BLOCKING_RULE, ELIMINATED_PLAY, EVAL_TIME, seed_admin_pilot)

pytestmark = pytest.mark.pg

#: The corpus this gate is a pilot for.
_ADMIN_RULES = Path("Domain Expertise/Admin Expertise/rules")


# ── the detectors, and the report's own boundaries ──────────────────────────────

def test_the_generic_play_id_is_the_one_the_adapter_actually_mints():
    """The fake-success detector must not be able to drift away from what it detects."""
    from scripts.l3_pilot_report import GENERIC_PLAY_ID

    source = Path("genios_engine/reason/adapters/expertise.py").read_text()
    assert f'"{GENERIC_PLAY_ID}", "1.0.0"' in source, (
        "the adapter's fallback play id changed and the J5 detector did not follow it")


def test_the_report_cannot_activate_anything():
    """Y5's ordering rule is absolute, so the reporting tool must not be a way around it."""
    source = Path("scripts/l3_pilot_report.py").read_text()
    for forbidden in ("activate(", "deactivate(", "insert into", "update ", "delete from"):
        assert forbidden not in source.lower(), forbidden
    assert "read_only_connection" in source


def test_the_report_can_tell_an_empty_brain_from_an_unselected_one():
    """Row 4 reads packages; a zero there has two causes and they live in different layers.

    Measured on a tenant whose Behaviour brain held six ACTIVE entries and whose Adaptive brain
    held a live lease: `packages_with_a_brain_slice` was still 0. Without these two reads the
    report says "the brains are empty" about a tenant whose brains are full, and sends the reader
    to J4 for a defect that is in Layer 3's selector.
    """
    source = Path("scripts/l3_pilot_report.py").read_text()
    assert "learned_brain_entries" in source
    assert "temporary_memories" in source


def test_the_seed_runs_the_derived_passes_the_production_drain_runs():
    """The seed's roll-up block must be production's, in production's order.

    This is the pin on the whole exercise. The reason J4/J5 read "no admin rule fires on this
    fixture" is that the fixture went from `process_event` straight to `refresh_situations`, and
    the three passes below are what put a fact on the node a situation is ANCHORED on. If
    `context/runner.py` grows a fourth pass, or reorders these, the seed is measuring a lane the
    product no longer runs and this test says so.
    """
    from tests.reason.adapters import l3_pilot_seed

    production = Path("genios_engine/context/runner.py").read_text()
    seeded = Path(l3_pilot_seed.__file__).read_text()
    order = ("compute_derived(", "compute_deal_view(", "compute_account_view(")
    for where, source in (("context/runner.py", production), ("the seed", seeded)):
        # The CALL, not the import: both files import the two account passes on one line, in
        # alphabetical order, which says nothing about the order they run in.
        positions = [source.rindex(name) for name in order]
        assert positions == sorted(positions), f"{where} calls the derived passes out of order"


# ── the corpus enumeration: does Admin ship doctrine that binds anything? ───────

def test_the_admin_corpus_ships_blocking_doctrine_and_one_of_it_can_fire():
    """Every Admin rule, its severity, its enforcing layer and what its `when` needs.

    THE FINDING, because the gate's note ("no admin rule fires on this fixture") invited the
    conclusion that the V1 Admin domain ships doctrine that binds nothing. It does not: six of
    nine rules are `severity: blocking`. But only ONE of the six can reach a signal, and the other
    five are dark for three separate and nameable reasons, printed below and asserted here so a
    corpus change moves the numbers instead of the story:

      * `inbox_and_correspondence.a_draft_may_not_commit_the_principal` is authored
        `enforced_by: L5_validation`. `rule_compiler` refuses it BY NAME — correctly, since
        compiling it here would enforce it twice, in the wrong layer.
      * `gatekeeping.evidence_then_a_structural_fix` and `goal_and_progress.no_goal_no_reading`
        are gated on `period.*`, which only the tenant-anchored `admin_period_review` situation
        carries. Both DO fire there — and a period correlation has no evidence members, so
        `core.constraint` eliminates every candidate with `evidence_required` and the decision is
        BLOCKED before a signal exists. (`goal_and_progress` also owns no playbook, so even a
        firing verdict has no play to block.)
      * `commitment_tracking.no_chase_while_we_hold_the_ball` and
        `approval_coordination.an_unowned_decision_is_not_a_slow_one` both need
        `commitment.due_at` on the ANCHOR, and no roll-up puts it on one — see finding 4 in the
        seed module's docstring.

    Which leaves `opportunity_tracking.no_reopening_on_an_inferred_satisfaction`, whose `when` is
    one `has_obs` read off the anchor's own observations. That is the rule the seed trips, and the
    reason it is trippable is the reason it is the only one: it asks for something Layer 2 writes
    on the thing the situation is about.
    """
    rows = []
    for path in sorted(_ADMIN_RULES.glob("*/*.yaml")):
        document = yaml.safe_load(path.read_text())
        rule = document["rule"]
        rows.append({
            "id": document["identity"]["id"],
            "severity": rule.get("severity"),
            "enforced_by": rule.get("enforced_by"),
            "scope": document["identity"].get("scope"),
            "owner": document["identity"].get("owner_capability"),
            "when": rule.get("when"),
        })
    print("\nADMIN-RULE-ENUMERATION " + json.dumps(rows, sort_keys=True, default=str))

    assert len(rows) == 9, "the Admin rule corpus changed size; re-read the enumeration above"
    blocking = [r for r in rows if r["severity"] == "blocking"]
    assert len(blocking) >= 1, (
        "the Admin domain ships NO blocking rule — the V1 corpus binds nothing, and that is the "
        "finding, not the gate row")
    # Every rule is capability-scoped, which is what gives a blocking verdict a blast radius the
    # compiler can intersect instead of invent.
    assert all(r["scope"] == "capability" and r["owner"] for r in rows)

    trippable = next(r for r in rows if r["id"] == BLOCKING_RULE)
    assert trippable["severity"] == "blocking"
    assert trippable["enforced_by"] == "L4_constraint"
    # One term, and it reads the anchor's own observations — the only shape in this corpus that a
    # situation reaching a signal can satisfy today.
    assert trippable["when"] == [{"has_obs": "decision_deferred"}]


# ── the seam, on real Postgres ─────────────────────────────────────────────────

def test_a_compiled_signal_carries_the_expert_claim_it_rests_on(pg_store):
    """MIGRATION 0114's reason for existing, proven on the live path rather than asserted."""
    from genios_engine.contracts.domain_expertise import citation_statement_hash

    org = "pk_l3_pilot_citation"
    counts = seed_admin_pilot(pg_store, org, build_cards=False)["compile"]
    assert counts.get("emitted", 0) > 0, dict(counts)

    with pg_store.engine.connect() as conn:
        rows = conn.execute(text(
            "select citations, capability_id from signals where org_id = :o"),
            {"o": org}).mappings().all()
    carried = []
    for row in rows:
        value = row["citations"]
        if isinstance(value, str):
            value = json.loads(value)
        carried.extend(value or ())
    assert carried, "the compiled lane still writes no citations — the claim dies in memory"
    for citation in carried:
        assert set(citation) >= {"artifact_id", "artifact_class", "statement", "statement_hash",
                                 "source_ref"}
        assert citation["artifact_class"] == "heuristic"
        assert citation["statement"].strip() == citation["statement"], (
            "a stored quote was reflowed; V-1 exists so a card can render it verbatim")
        # And the stored quote is still the authored one, re-hashed with the contract's own
        # function rather than compared against a copy of it.
        assert citation_statement_hash(citation["statement"]) == citation["statement_hash"]


def test_an_admin_blocking_rule_eliminates_a_candidate_and_signs_the_elimination(pg_store):
    """J5 ROW 7, on Admin, through the production lane.

    The gate scored this 0 with the note "no admin rule fires on this fixture", and J1 had already
    proved the machinery on a SALES rule. This is the same mechanism carrying the ADMIN corpus's
    own doctrine, on a situation the corpus author wrote the rule for: a decision the counterparty
    parked, 45 days of silence, and `admin.sit.dormant_commitment_reopenable` pulling
    `opportunity_tracking` into the package — the capability that both owns the blocking rule and
    owns the play the rule removes. The doctrine and the play disagree and the doctrine wins.
    """
    org = "pk_l3_pilot_elimination"
    seed_admin_pilot(pg_store, org, build_cards=False)

    with pg_store.engine.connect() as conn:
        rows = conn.execute(text(
            "select capability_id, play, rejected_candidates from signals where org_id = :o"),
            {"o": org}).mappings().all()

    eliminations = []
    for row in rows:
        rejected = row["rejected_candidates"]
        rejected = json.loads(rejected) if isinstance(rejected, str) else (rejected or ())
        for candidate in rejected:
            for elimination in (candidate or {}).get("eliminated_by") or ():
                eliminations.append((candidate, elimination))
    assert eliminations, "no candidate on this tenant was eliminated by authored doctrine"

    candidate, elimination = next(
        (c, e) for c, e in eliminations if e["rule_id"] == BLOCKING_RULE)
    assert candidate["play_id"] == ELIMINATED_PLAY
    assert candidate["disposition"] == "eliminated"
    assert elimination["severity"] == "blocking"

    # The quote travels with the elimination and is the AUTHORED sentence, byte for byte — the
    # card layer renders the doctrine that removed an option without opening the corpus.
    authored = yaml.safe_load(
        (_ADMIN_RULES / "opportunity_tracking"
         / "no-reopening-on-an-inferred-satisfaction.yaml").read_text())
    assert elimination["statement"] == authored["rule"]["statement"]

    # And the winner is a DIFFERENT play: an elimination that changed nothing would be a receipt
    # for a decision that was going to happen anyway.
    assert all(row["play"] != ELIMINATED_PLAY for row in rows)


def test_a_card_is_built_and_the_report_says_what_it_does_not_carry(pg_store):
    """J5 ROW 6's SECOND HOP, settled rather than assumed.

    The gate reported `cards_total = 0` and the report noted the row was "blocked on delivery".
    Delivery was simply never driven: `deliver/pipeline.build_cards_for_org` takes a graph, a
    card store, an org and a clock, and a scratch tenant supplies all four — no seats, no live
    LLM and no connected mailbox are required (the renderer falls back to slots, which is a
    delivery mode and not a failure).

    So the row is earned. What is NOT earned, and is measured here rather than glossed, is the
    strict reading: the expert's sentence does not appear anywhere in the card's own copy. The
    card is bound to a decision that rests on a quoted claim — that is the row doc 06 defined —
    and the renderer's `why` block carries fact/value pairs. Both numbers are reported.
    """
    from scripts._gate import read_only_connection
    from scripts.l3_pilot_report import score

    org = "pk_l3_pilot_card"
    delivery = seed_admin_pilot(pg_store, org)["delivery"]
    assert delivery["built"] >= 1, delivery

    with read_only_connection(pg_store.engine) as conn:
        verdict = score(conn, org_id=org, since=EVAL_TIME.replace(year=2000), at=EVAL_TIME)
    assert verdict.cards_total >= 1
    assert verdict.cards_with_a_citation >= 1, (
        "a card was built on a decision carrying a quoted claim and the report did not see it")
    # The honest half. Asserted as an INEQUALITY rather than `== 0` so that a renderer which
    # starts quoting the doctrine makes this test better, not red.
    assert verdict.cards_quoting_in_their_own_copy <= verdict.cards_with_a_citation
    if not verdict.cards_quoting_in_their_own_copy:
        assert any("NONE renders it" in note for note in verdict.notes), (
            "the report must SAY that the quote reached the row and not the reader")


def test_the_pilot_report_scores_a_real_org(pg_store, capsys):
    """The J5 harness over the seeded tenant. Every number is printed for the gate to read."""
    from scripts._gate import read_only_connection
    from scripts.l3_pilot_report import score

    org = "pk_l3_pilot_report"
    seed_admin_pilot(pg_store, org)
    with read_only_connection(pg_store.engine) as conn:
        verdict = score(conn, org_id=org, since=EVAL_TIME.replace(year=2000), at=EVAL_TIME)
    print("\nJ5-SEEDED " + json.dumps(verdict.as_dict(), sort_keys=True))

    assert verdict.packages_total > 0
    assert verdict.packages_admin > 0, "the admin corpus compiled nothing for a seeded admin org"
    assert verdict.compiled_signals > 0
    assert verdict.situations_addressed > 0
    assert verdict.worst_addresses_per_situation == 1, (
        "one situation holds two package addresses — either knowledge changed between sweeps or "
        "this is the churn that took production read-only")
    assert verdict.generic_plays == 0, (
        "a compiled signal recommended the adapter's own placeholder play — this is the "
        "fake-success state doc 03 warns about")
    assert verdict.downgraded_signals == 0, "a stamped capability was still downgraded"
    assert verdict.signals_with_a_citation >= 1, (
        "no compiled signal carried a quoted claim — migration 0114's writer is not running")
    assert verdict.citation_quotes and all(q.strip() for q in verdict.citation_quotes)
    # ROW 6 and ROW 7, both earned on this tenant. The elimination row is scored against the
    # PILOT'S OWN domain, so a Sales rule firing here could not earn it.
    assert verdict.cards_total >= 1 and verdict.cards_with_a_citation >= 1
    assert verdict.domain_eliminations >= 1
    assert BLOCKING_RULE in verdict.elimination_rules
    assert ELIMINATED_PLAY in verdict.eliminated_plays
    # ROW 8 is J4's, and this tenant is not where it is earned. Whatever the brains hold is
    # reported either way, so a zero here is readable rather than mute.
    assert isinstance(verdict.brain_entries, dict)
    assert "expert" not in verdict.activated_domains
