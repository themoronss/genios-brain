r"""`C.U01` · the draft receipt asks what its own claim and detail already described.

⛔ WHAT WAS WRONG. The receipt asked `render_mode <> 'llm'` and expected zero, while its detail said
*"raw_slot with an **empty artifact body** is a card with no content"*. Measured on production:

    llm        105 cards,  13 with an empty artifact body
    raw_slot    59 cards,  24
    template     1 card,    1

Wrong in BOTH directions: it **counted 35** `raw_slot` cards that do have a body — a deterministic
fallback carrying real content is the designed behaviour, not a stub — and **missed 13** `llm` cards with
an empty body, which by its own detail are cards with no content.

⛔ AND THE HONEST QUESTION IS NARROWER STILL. Of the 38 empty-body cards, **19 abstained** (13 `review`,
6 `observation`), and an abstained card is SUPPOSED to carry no draft: `card_builder` strips `run_play`
and `render.py` sets `art = ""` when the artifact is rejected.

**What is left is 18: a card at an instructing level, with no content, giving an order.**

⛔ THE REWRITTEN RECEIPT STILL FAILS, AT 18. A receipt is not fixed by making it green.
"""
from __future__ import annotations

import pytest

from genios_engine.platform import receipts as R

CLAIM = "no card gives an order with an empty draft"


def _receipt(org="org_1"):
    found = [r for r in R.receipts(org) if r.claim == CLAIM]
    assert len(found) == 1, [r.claim for r in R.receipts(org) if "draft" in r.claim]
    return found[0]


def test_the_old_question_is_gone():
    """⛔ `render_mode <> 'llm'` counted a working fallback as a failure. If it comes back, so does a
    permanently-red receipt for designed behaviour."""
    for r in R.receipts("org_1"):
        assert "render_mode <> 'llm'" not in r.sql, r.claim


def test_the_receipt_asks_about_an_empty_artifact_body():
    sql = _receipt().sql
    assert "artifact->>'body'" in sql
    assert "coalesce(" in sql, "a NULL body must read as empty, not as absent from the count"


def test_an_abstained_card_is_excluded():
    """⛔ THE CORRECTION THAT MATTERS MOST. 19 of the 38 empty-body cards abstained, and an abstained
    card carries no draft BY DESIGN. Counting them would demand a draft the engine deliberately
    refused to write."""
    assert "abstained_because is null" in _receipt().sql


def test_only_an_instructing_level_is_counted():
    """`level in ('prescriptive','predictive')` is `abstention.ACTIONABLE`. A `review` or
    `observation` card is not giving an order, so an empty draft on one is not this defect."""
    sql = _receipt().sql
    assert "'prescriptive'" in sql and "'predictive'" in sql
    for benign in ("'review'", "'observation'"):
        assert benign not in sql, f"{benign} is not an instructing level"


def test_a_null_level_is_excluded_rather_than_assumed():
    """⛔ `calibrate._PRECISION_SQL` states the rule: *"a card whose level nobody recorded is
    ungradeable, and defaulting it to 'instruction' is how the old behaviour comes back."* An `in`
    list excludes NULL by construction — asserted so nobody swaps it for `<> 'review'`, which would
    include it."""
    sql = _receipt().sql
    assert "level in (" in sql
    assert "level <>" not in sql and "level !=" not in sql


def test_both_conditions_are_required_not_either():
    """A card can be downgraded by level with no abstention reason — one such card exists — and a
    reason without a downgrade is a contradiction the card layer does not produce. So the receipt
    needs both, joined by `and`."""
    sql = " ".join(_receipt().sql.split())
    body = sql.split("where", 1)[1]
    assert " or " not in body, f"the conditions are disjunctive: {body}"
    assert body.count(" and ") >= 2


def test_the_claim_and_the_detail_now_describe_the_same_thing():
    """⛔ THE DEFECT CLASS THIS FIXES. The old claim said *a written draft*, the detail said *an empty
    artifact body*, and the SQL asked about `render_mode`. Three descriptions of three different
    things, and only one of them was checked."""
    receipt = _receipt()
    assert "empty draft" in receipt.claim
    assert "empty" in receipt.detail or "nothing to act with" in receipt.detail
    assert "abstained" in receipt.detail.lower(), (
        "the exclusion must be stated where a reader of the failure will see it")


def test_zero_passes_and_anything_above_it_fails():
    receipt = _receipt()
    assert receipt.expect(0) is True
    assert receipt.expect(1) is False
    assert receipt.expect(18) is False


def test_it_is_still_tenant_scoped():
    """It asks about this tenant's cards; an unfiltered query would report every tenant's on one
    tenant's readiness page — the hazard `Receipt.fleet_wide` exists to make explicit."""
    assert ":org" in _receipt("org_1").sql
    assert ":org" not in _receipt(None).sql


def test_the_receipt_was_not_made_to_pass():
    """⛔ THE POINT, PINNED. Measured against production the rewritten receipt answers 18 and FAILS.
    If somebody later relaxes it so it passes while those cards still exist, this is the test that
    has to be argued with."""
    receipt = _receipt()
    assert receipt.expect(18) is False, (
        "the receipt now tolerates 18 instructing cards with no content; that is the defect, not the "
        "baseline")


def test_the_card_level_vocabulary_matches_the_abstention_contract():
    """⛔ Derived rather than retyped: if `abstention.ACTIONABLE` changes, this test fails and somebody
    has to decide whether the receipt should follow."""
    from genios_engine.contracts.abstention import Level

    sql = _receipt().sql
    actionable = {Level.PRESCRIPTIVE.value, Level.PREDICTIVE.value}
    for level in actionable:
        assert f"'{level}'" in sql, f"{level} is actionable and is not counted"
