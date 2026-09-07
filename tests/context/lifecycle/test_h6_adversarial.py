"""H6 · the gate's own attack on M-4, and the two guards it forced.

`test_resolution.py` grades the wave's golden set. This file grades the set the GATE wrote to
break it, and it exists because measuring a false-positive rate against fixtures chosen by the
same hand that wrote the guards measures the guards against exactly the inputs they were written
for. Of `m4_resolution.json`'s 28 must-not-close fixtures only FOUR present the hardest shape —
verdict RESOLVED, band EXPLICIT_COMPLETION, an org-internal sender — and each of those four is
caught by a different named guard. Every other one concedes the case in the answer itself: an
INTENT_ONLY band, an AMBIGUOUS band, an external or machine sender, or a NOT_RESOLVED verdict.

So this set hands the deterministic layer nothing but the hard shape, and it found two refusals
ALG-08 cannot make. Both are pinned below and both are one-directional: they can turn a close
into a rejection and never the reverse, so the worst either costs is one unnecessary nudge.

THE `known_limit` FIXTURES ARE THE HONEST HALF. Seven of them are a model that labelled plain
sarcasm, a forward-looking modal, a conditional or hearsay as EXPLICIT_COMPLETION while quoting
and scoping correctly. There is no deterministic answer to that: refusing it would require the
code to re-read the prose and overrule the description, which is the doctrine this unit is built
on, read backwards. They are committed so the limit is a COUNTED number in the H6 record rather
than a matter of opinion, and `test_known_limits_have_not_grown` fails if a later change adds to
them.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from genios_engine.context.lifecycle.authority import role_for_scope
from genios_engine.context.lifecycle.contract import (
    DECISION_APPLY,
    VERDICT_PARTIALLY_RESOLVED,
    VERDICT_RESOLVED,
    Message,
    Obligation,
)
from genios_engine.context.lifecycle.gate import gate_decision
from genios_engine.context.lifecycle.judge import judge
from genios_engine.context.lifecycle.prompt import parse_description
from genios_engine.context.lifecycle.textguard import (in_quoted_history, negator_in_clause,
                                                       quoted_regions)

from tests.context.lifecycle.conftest import AT

_SET = (pathlib.Path(__file__).resolve().parents[2] / "golden" / "l2" / "m4_adversarial.json")

#: The count of fixtures no deterministic guard can refuse, as measured at H6. A RATCHET: a later
#: change may drive it down, never up. Spelled here rather than derived from the file so that
#: adding a `known_limit` to the JSON to make a failing test pass fails this test instead.
KNOWN_LIMITS_AT_H6 = 8


def _fixtures():
    return json.loads(_SET.read_text(encoding="utf-8"))["fixtures"]


def _run(fx):
    """The shipped path, model call replaced by the fixture's recorded answer. Nothing else."""
    obligations = tuple(Obligation(o["id"], o["subject"], o.get("owner"))
                        for o in fx["obligations"])
    message = Message(event_id=fx["fixture_id"], text=fx["message"],
                      sender_email=fx["sender"], occurred_at=AT)
    internal = fx["internal_emails"]
    role = role_for_scope(fx["sender"], obligations, internal_emails=internal)
    decision = gate_decision(
        status="active", resolved_by=None, terminal_by_fact=False, has_new_signal=True,
        already_examined=False, has_text=bool(fx["message"].strip()), speaker_role=role,
        calls_today_for_situation=0, calls_today_for_org=0)
    if not decision.fires:
        return "gated", None
    answer = dict(fx["model_answer"])
    answer["start_offset"] = max(fx["message"].find(answer["quote"]), 0)
    answer["end_offset"] = answer["start_offset"] + len(answer["quote"])
    description = parse_description(answer)
    assert description is not None, fx["fixture_id"]
    claim = judge(description, situation_id="sit_adv", message=message,
                  obligations=obligations, internal_emails=internal)
    return claim.decision, claim.verdict


def _closes(decision, verdict) -> bool:
    return decision == DECISION_APPLY and verdict in (VERDICT_RESOLVED,
                                                      VERDICT_PARTIALLY_RESOLVED)


@pytest.mark.parametrize("fx", [f for f in _fixtures()
                                if not f["truth"]["must_close"] and "known_limit" not in f],
                         ids=lambda f: f["fixture_id"])
def test_the_hard_shape_is_refused(fx):
    """Every guard-provable attack must end with the situation still open."""
    decision, verdict = _run(fx)
    assert not _closes(decision, verdict), (
        f"{fx['fixture_id']} CLOSED a live thread — {fx['truth']['why']}")


@pytest.mark.parametrize("fx", [f for f in _fixtures() if f["truth"]["must_close"]],
                         ids=lambda f: f["fixture_id"])
def test_the_controls_still_close(fx):
    """The guards must not have bought their refusals by refusing everything.

    Without these the whole file passes by rejecting every fixture, which is exactly the
    degenerate 'safe direction' a one-sided metric rewards.
    """
    decision, verdict = _run(fx)
    assert _closes(decision, verdict), f"{fx['fixture_id']} should have closed, got {decision}"


def test_false_positive_rate_on_the_gates_own_set():
    """The measured number, over the fixtures a deterministic layer can actually decide."""
    gradeable = [f for f in _fixtures() if "known_limit" not in f]
    closed_wrongly = [f["fixture_id"] for f in gradeable
                      if not f["truth"]["must_close"] and _closes(*_run(f))]
    rate_bp = len(closed_wrongly) * 10_000 // len(gradeable)
    print(f"\nM-4 adversarial set: {len(gradeable)} gradeable fixtures — "
          f"false positives {len(closed_wrongly)} ({rate_bp} bp, ceiling 200 bp); "
          f"{KNOWN_LIMITS_AT_H6} further fixtures are recorded model-fidelity limits.")
    assert rate_bp < 200, closed_wrongly


def test_known_limits_have_not_grown():
    """A ratchet. Marking a newly-failing fixture `known_limit` must not be a way to pass."""
    limits = [f["fixture_id"] for f in _fixtures() if "known_limit" in f]
    assert len(limits) <= KNOWN_LIMITS_AT_H6, sorted(limits)


# ── the two guards, unit-level, each with the case that dies without it ──────────────────────

def test_a_completion_quoted_from_the_reply_history_never_closes():
    """The single most available false close on a real inbox: every mail client quotes below."""
    text = ("I don't think this ever actually happened, can you confirm?\n\n"
            "> On 12 Feb, Priya wrote:\n"
            "> all sorted, we signed yesterday and finance has the PO number.\n")
    at = text.find("we signed yesterday")
    assert in_quoted_history(text, at, at + len("we signed yesterday"))
    # and the live sentence in the same message is NOT in history
    live = text.find("ever actually happened")
    assert not in_quoted_history(text, live, live + 10)


def test_a_negated_quote_never_closes_but_a_neighbouring_clause_does_not_block_one():
    """ALG-08 proves the words are there. It says nothing about polarity."""
    negated = "To be clear: we have not signed the MSA yet and legal still holds it."
    at = negated.find("signed the MSA")
    assert negator_in_clause(negated, at, at + len("signed the MSA")) == "not"

    # THE WINDOW IS THE QUOTE'S OWN CLAUSE, and this half of the assertion is the one that costs
    # something. A negator in the clause BEFORE must not refuse a real resolution — widen the
    # window to the whole message and every long email containing the word "not" anywhere stops
    # resolving. The sentence below carries a live negator from `NEGATORS` in its first clause and
    # a genuine completion in its second.
    fine = "Legal could not agree the indemnity last week, but we signed yesterday and it is done."
    at = fine.find("we signed yesterday")
    assert negator_in_clause(fine, at, at + len("we signed yesterday")) is None, (
        "the negation window reaches across a clause boundary — this refuses real resolutions")

    # And the same negator, moved INTO the quote's own clause, must still be found. Without this
    # pair the test above passes on a guard that never fires at all.
    same_clause = "We could not sign the MSA and it is still with legal."
    at = same_clause.find("sign the MSA")
    assert negator_in_clause(same_clause, at, at + len("sign the MSA")) == "cannot" or \
        negator_in_clause(same_clause, at, at + len("sign the MSA")) == "not"


def test_neither_guard_is_applied_to_a_contradiction():
    """The reopen path must stay unguarded — its quote is SUPPOSED to carry a negator.

    Guarding it would make a wrong close permanent, which is the opposite of the reversibility
    doc 12 calls "the structural guard behind all nine".
    """
    text = ("Sorry to reopen this, but it is actually not done — the MSA was never countersigned "
            "and it is still sitting with legal.")
    quote = "actually not done"
    at = text.find(quote)
    assert negator_in_clause(text, at, at + len(quote)) is not None, "the guard WOULD fire here"
    claim = judge(
        parse_description({"verdict": "CONTRADICTED", "certainty": "EXPLICIT_COMPLETION",
                           "scope": ["ob_msa"], "quote": quote,
                           "start_offset": at, "end_offset": at + len(quote)}),
        situation_id="sit_adv",
        message=Message(event_id="e_contra", text=text, sender_email="priya@ourco.example",
                        occurred_at=AT),
        obligations=(Obligation("ob_msa", "countersign the MSA", "priya@ourco.example"),),
        internal_emails=["priya@ourco.example"])
    assert claim.decision == DECISION_APPLY and claim.verdict == "CONTRADICTED"


# =================================================================================================
# TWO GUARDS THE H6 MUTATION RUN FOUND WITH NO RED TEST
# =================================================================================================
#
# Both survived a mutation, and for different reasons. The INTENT_ONLY band survived because a
# SECOND lock holds the same door — `judge.py` step 3 refuses an intent-carrying resolution before
# the band is ever weighed — so the mutation is invisible while both exist and fatal the moment
# somebody removes the one that is tested. The per-org ceiling survived because nothing tested it
# at all. A guard with no red test is not a guard, whichever of the two it is.

def test_the_intent_band_is_worth_zero_and_not_merely_little():
    """`CERTAINTY_BP[INTENT_ONLY] == 0` — the belt, tested separately from the lock.

    Doc 12 case 1 calls a forward-looking modal a HARD NEGATIVE, and a hard negative that still
    contributes 2000 bp is a soft one. `judge.py` also rejects INTENT_ONLY outright, which is why
    changing this number breaks nothing today; this test is what makes the two independent, so a
    later refactor that leans on the band alone still lands above the floor and fails here rather
    than in production.
    """
    from genios_engine.context.lifecycle.contract import (AUTHORITY_BP, CERTAINTY_BP,
                                                          CERTAINTY_INTENT, CLOSE_FLOOR_BP,
                                                          REVIEW_FLOOR_BP, ROLE_OWNER)
    assert CERTAINTY_BP[CERTAINTY_INTENT] == 0

    # Stated as the property rather than the literal: even from the strongest possible speaker,
    # an intention cannot reach either floor on the band alone.
    strongest = CERTAINTY_BP[CERTAINTY_INTENT] * AUTHORITY_BP[ROLE_OWNER] // 10_000
    assert strongest < REVIEW_FLOOR_BP < CLOSE_FLOOR_BP, (
        f"an intention from the obligation's own owner is worth {strongest} bp — a forward-looking "
        "modal can reach a floor on its band alone")


def test_the_per_org_daily_ceiling_refuses_and_names_itself():
    """Doc 11's *"per-org daily L2 LLM calls: 200"*, which had no test of its own.

    The per-SITUATION cap was covered; this one was not, so raising it would have been silent —
    and the failure it guards against is a runaway sweep spending a tenant's whole budget, which
    is exactly the failure that shows up as an invoice rather than as a red test.
    """
    from genios_engine.context.lifecycle.gate import (MAX_CALLS_PER_ORG_PER_DAY,
                                                      SKIP_BUDGET_ORG, gate_decision)
    common = dict(status="active", resolved_by=None, terminal_by_fact=False, has_new_signal=True,
                  already_examined=False, has_text=True, speaker_role="owner",
                  calls_today_for_situation=0)

    at_ceiling = gate_decision(**common, calls_today_for_org=MAX_CALLS_PER_ORG_PER_DAY)
    assert at_ceiling.fires is False
    assert at_ceiling.reason == SKIP_BUDGET_ORG, (
        "the org ceiling refused under some other name — an operator cannot tell a budget miss "
        "from a situation that had nothing to say")
    assert at_ceiling.budget_exhausted is True

    # One below it still fires, or the ceiling is a ban rather than a budget.
    assert gate_decision(**common,
                         calls_today_for_org=MAX_CALLS_PER_ORG_PER_DAY - 1).fires is True
    assert MAX_CALLS_PER_ORG_PER_DAY == 200, "doc 11's number moved without the doc moving"


def test_the_per_situation_daily_cap_refuses_at_its_boundary():
    """Doc 11's *"M-4 fires per situation per day: max 3"*, asserted as a BOUNDARY.

    The existing coverage drives this cap by writing `range(MAX_CALLS_PER_SITUATION_PER_DAY)`
    claims, which is the natural way to write it and has one bad property: raise the constant and
    that test LOOPS rather than fails. A hang reads as "inconclusive" in a mutation run, so the
    guard looked protected without being provably so. This states the boundary directly, in three
    assertions that cannot hang.
    """
    from genios_engine.context.lifecycle.gate import (MAX_CALLS_PER_SITUATION_PER_DAY,
                                                      SKIP_BUDGET_SITUATION, gate_decision)
    common = dict(status="active", resolved_by=None, terminal_by_fact=False, has_new_signal=True,
                  already_examined=False, has_text=True, speaker_role="owner",
                  calls_today_for_org=0)
    assert MAX_CALLS_PER_SITUATION_PER_DAY == 3, "doc 11's number moved without the doc moving"
    at = gate_decision(**common,
                       calls_today_for_situation=MAX_CALLS_PER_SITUATION_PER_DAY)
    assert at.fires is False and at.reason == SKIP_BUDGET_SITUATION and at.budget_exhausted
    assert gate_decision(**common,
                         calls_today_for_situation=MAX_CALLS_PER_SITUATION_PER_DAY - 1).fires


def test_the_quoted_history_test_is_OVERLAP_and_not_containment():
    """A quote that STRADDLES the boundary is not this sender's sentence either.

    Requiring full containment would make the guard avoidable by widening the quote by one
    character — the model returns a span that starts in the live text and runs down into the
    history, and a containment test says "not quoted" about a sentence that is mostly quoted.
    This is the difference the H6 mutation run flagged, and it is one operator on one line.
    """
    text = ("Can you confirm this actually happened?\n"
            "> On 12 Feb, Priya wrote:\n"
            "> all sorted, we signed yesterday.\n")
    (region_start, region_end), = quoted_regions(text)

    # Fully inside — both readings agree.
    inside = text.find("we signed yesterday")
    assert in_quoted_history(text, inside, inside + len("we signed yesterday"))

    # STRADDLING the boundary: begins in the live text, ends inside the history. Containment says
    # no; overlap says yes, and overlap is right.
    assert in_quoted_history(text, region_start - 12, region_start + 20), (
        "a span straddling the quote boundary was treated as this sender's own words")

    # And live text well clear of the history is still quotable, or the guard refuses everything.
    assert not in_quoted_history(text, 0, len("Can you confirm"))
