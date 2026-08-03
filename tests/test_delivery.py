from __future__ import annotations

from datetime import datetime, timedelta, timezone

from genios_engine.deliver.actions import BUTTONS, snooze_until
from genios_engine.deliver.bands import band
from genios_engine.deliver.render import (HEADLINE_CAP, SITUATION_CAP, _fallback,
                                          invention_ok, render_copy, _corpus)
from genios_engine.deliver.slots import compute_slots
from genios_engine.packs.sales_v1 import SALES_V1

# L5 delivery — offline, deterministic. The DB path (persist + queue state machine + agent claim)
# is proven against real Supabase; here we lock the pure logic: band cuts, the invention/length
# validators that stand between the model and the user, slot computation, and snooze arithmetic.

NOW = datetime(2026, 7, 31, tzinfo=timezone.utc)
BANDS = SALES_V1["scoring_defaults"]["bands"]


# ---- E2 band assigner ------------------------------------------------------

def test_bands_cut_from_pack():
    assert band(54, BANDS) == "standard"
    assert band(69, BANDS) == "standard"
    assert band(70, BANDS) == "high"
    assert band(84, BANDS) == "high"
    assert band(85, BANDS) == "critical"


def test_small_deal_supremum_never_reaches_critical():
    # spec §5.11: small-deal S maxes at 83 → critical (85) is unreachable, by construction
    assert band(83, BANDS) == "high"


# ---- V-01 length caps ------------------------------------------------------

def test_over_length_headline_falls_back_not_truncated():
    template = {"artifact_kind": "draft_followup",
                "fallback": {"headline": "{entity} quiet {days}d", "situation": "{stage} · {money}"}}
    slots = {"entity": "Acme", "days": 9, "stage": "proposal", "money": "$200k",
             "action": "x", "who": "Acme"}

    class FakeLLM:
        def call(self, prompt, max_tokens=600):
            from genios_engine.context.llm.client import LLMResult
            long_head = "X" * (HEADLINE_CAP + 5)     # 65 chars, over cap
            return LLMResult(parsed={"headline": long_head, "situation": "ok", "artifact": "hi"},
                             raw="", input_tokens=1, output_tokens=1, ok=True)

    out = render_copy(reason_code="stalled_deal", template=template, facts={}, slots=slots,
                      llm=FakeLLM())
    assert out["render_mode"] == "raw_slot" and out["reject_code"] == "V-01"
    assert len(out["headline"]) <= HEADLINE_CAP        # fallback fits, no ellipsis


# ---- V-02 invention validator (the trust story) ----------------------------

def test_invention_validator_rejects_unknown_number():
    facts = {"deal.value": {"value": 200000}}
    slots = {"entity": "Acme", "days": 9, "money": "$200k", "stage": "proposal",
             "action": "x", "who": "Acme"}
    corpus_text, corpus_nums = _corpus(facts, slots)
    ok, why = invention_ok("Acme owes us $999999 by Friday", corpus_text, corpus_nums)
    assert ok is False and why.startswith("number:")


def test_invention_validator_rejects_unknown_name():
    facts = {"deal.status": {"value": "open"}}
    slots = {"entity": "Acme", "days": 9, "money": "no value set", "stage": "open",
             "action": "x", "who": "Acme"}
    corpus_text, corpus_nums = _corpus(facts, slots)
    ok, why = invention_ok("Reach out to Zephyr about the deal", corpus_text, corpus_nums)
    assert ok is False and why == "name:Zephyr"


def test_invention_validator_allows_grounded_copy():
    facts = {"deal.value": {"value": 200000}, "deal.status": {"value": "proposal"}}
    slots = {"entity": "Acme", "days": 9, "money": "$200k", "stage": "proposal",
             "action": "x", "who": "Acme"}
    corpus_text, corpus_nums = _corpus(facts, slots)
    ok, why = invention_ok("Acme deal quiet 9 days at proposal", corpus_text, corpus_nums)
    assert ok is True and why is None


def test_faithful_date_reformatting_is_grounded_but_wrong_month_is_not():
    # fact date 2026-07-22 → "July 22" is faithful (grounded); "March 22" flips the month (invented)
    facts = {"deal.last_inbound": {"value": "2026-07-22T07:39:20+00:00"}}
    slots = {"entity": "Acme", "days": 9, "money": "x", "stage": "open", "action": "x", "who": "Acme"}
    ct, cn = _corpus(facts, slots)
    ok_july, _ = invention_ok("No inbound since July 22", ct, cn)
    ok_march, why = invention_ok("No inbound since March 22", ct, cn)
    assert ok_july is True
    assert ok_march is False and why == "name:March"


def test_sentence_initial_capital_is_not_flagged_as_a_name():
    facts = {"deal.status": {"value": "open"}}
    slots = {"entity": "Acme", "days": 2, "money": "x", "stage": "open", "action": "x", "who": "Acme"}
    corpus_text, corpus_nums = _corpus(facts, slots)
    ok, _ = invention_ok("They have gone quiet.", corpus_text, corpus_nums)
    assert ok is True                          # "They" is grammar, not an invented name


def test_no_llm_means_deterministic_fallback():
    template = {"artifact_kind": "draft_reply",
                "fallback": {"headline": "Reply owed: {entity}", "situation": "{days}d waiting"}}
    slots = {"entity": "Acme", "days": 3, "money": "x", "stage": "open", "action": "x", "who": "Acme"}
    out = render_copy(reason_code="unanswered_email", template=template, facts={}, slots=slots,
                      llm=None)
    assert out["render_mode"] == "raw_slot"
    assert out["headline"] == "Reply owed: Acme" and out["situation"] == "3d waiting"


# ---- slots -----------------------------------------------------------------

def test_slots_compute_days_and_money():
    facts = {"deal.last_inbound": {"value": (NOW - timedelta(days=9)).isoformat()},
             "deal.value": {"value": 200000}, "deal.status": {"value": "proposal"}}
    s = compute_slots("stalled_deal", "Acme", facts, NOW)
    assert s["days"] == 9 and s["money"] == "$200k" and s["stage"] == "proposal"


def test_slots_degrade_safely_when_facts_missing():
    s = compute_slots("stalled_deal", "", {}, NOW)
    assert s["entity"] == "this account" and s["days"] == "several"   # never a fabricated number


# ---- snooze arithmetic -----------------------------------------------------

def test_snooze_options():
    assert snooze_until("4h", NOW) == NOW + timedelta(hours=4)
    assert snooze_until("3d", NOW) == NOW + timedelta(days=3)
    assert snooze_until("tomorrow_09", NOW).hour == 9
    assert "requeue" in BUTTONS and "wrong" in BUTTONS
