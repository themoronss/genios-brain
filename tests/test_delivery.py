from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from genios_engine.deliver.actions import BUTTONS, snooze_until
from genios_engine.deliver.bands import band
from genios_engine.deliver.card_builder import _why
from genios_engine.deliver.store import CardStore
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
    # 1.11.0 calibrated the cuts to the LIVE score distribution (min 42 / median 45.5 / max 56):
    # the old 70/85 sat ABOVE the maximum reachable score, so `high` was arithmetically
    # unreachable and the push layer ran on an empty input for months while reading as healthy.
    assert band(45, BANDS) == "standard"
    assert band(51, BANDS) == "standard"
    assert band(52, BANDS) == "high"
    assert band(59, BANDS) == "high"
    assert band(60, BANDS) == "critical"


def test_the_push_band_is_reachable_by_the_live_score_range():
    """The invariant the old fixture values silently violated: a band nothing can reach is not a
    threshold, it is a disabled feature wearing one's clothes. Live open signals span 42-56."""
    assert BANDS["high"] <= 56, "high must be reachable by the live maximum"
    assert BANDS["critical"] > BANDS["high"]


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
    # The clock is the RULE's declared `urgency.path`, passed by the caller. It used to come from
    # a 6-entry map that covered 6 of 25 rules; the other 19 looked up the fact named "" and
    # printed the sentinel word into a `{days}d` slot.
    s = compute_slots("stalled_deal", "Acme", facts, NOW, "deal.last_inbound")
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


def test_card_why_never_pads_a_decision_with_unrelated_live_facts():
    why = _why(
        [{"field": "deal.status", "value": "open"}],
        {"deal.status": {"value": "open"}, "deal.value": {"value": 900_000}},
    )

    assert why == [{"field": "deal.status", "value": "open", "source": "crm"}]


def test_card_build_lease_is_durable_bounded_and_owner_released():
    calls = []

    class _Result:
        def __init__(self, *, first=None, rowcount=0):
            self._first = first
            self.rowcount = rowcount

        def first(self):
            return self._first

    class _Connection:
        def execute(self, statement, params=None):
            sql, values = str(statement), dict(params or {})
            calls.append((sql, values))
            if "insert into card_build_claims" in sql:
                return _Result(first=SimpleNamespace(claim_token=values["token"]))
            return _Result(rowcount=1)

    class _Engine:
        @contextmanager
        def begin(self):
            yield _Connection()

    store = CardStore.__new__(CardStore)
    store._engine = _Engine()
    token = store.claim_build("org_1", "sig_1", eval_time=NOW)
    assert token and store.release_build("org_1", "sig_1", token) is True
    claim_sql, claim_params = calls[0]
    assert "not exists (select 1 from cards" in claim_sql.lower()
    assert "card_build_claims.expires_at<=:now" in claim_sql.lower()
    assert claim_params["expires"] == NOW + timedelta(minutes=15)
    release_sql, release_params = calls[1]
    assert "claim_token=:token" in release_sql.lower()
    assert release_params["token"] == token


def test_card_insert_is_fenced_by_the_current_build_lease():
    calls = []

    class _Result:
        def first(self):
            return None

    class _Connection:
        def execute(self, statement, params=None):
            calls.append((str(statement), dict(params or {})))
            return _Result()

    class _Engine:
        @contextmanager
        def begin(self):
            yield _Connection()

    store = CardStore.__new__(CardStore)
    store._engine = _Engine()
    card_id, created = store.insert_card(
        {"org_id": "org_1", "signal_id": "sig_1", "_authority_time": NOW},
        {},
        build_claim_token="stale_or_foreign_token",
    )

    assert (card_id, created) == (None, False)
    assert len(calls) == 1
    lease_sql, lease_params = calls[0]
    assert "claim_token=:token" in lease_sql.lower()
    assert "expires_at>:authority_time" in lease_sql.lower()
    assert "for update" in lease_sql.lower()
    assert lease_params["token"] == "stale_or_foreign_token"


def test_worker_without_card_build_lease_never_invokes_renderer(monkeypatch):
    from genios_engine.deliver import pipeline

    rendered = []
    monkeypatch.setattr(pipeline, "ensure_default", lambda *_args: None)
    monkeypatch.setattr(pipeline, "_open_signals_without_cards", lambda *_args: [{
        "signal_id": "sig_1", "effective_config": {},
    }])
    monkeypatch.setattr(pipeline, "render_copy", lambda **_kwargs: rendered.append(True))
    store = SimpleNamespace(claim_build=lambda *_args, **_kwargs: None)

    result = pipeline.build_cards_for_org(
        graph=object(), card_store=store, org_id="org_1", registry=object(), eval_time=NOW)

    assert result["build_in_progress"] == 1
    assert rendered == []


# ── the invention guard must catch inventions, not English ───────────────────────────────────
def _guard_corpus():
    from genios_engine.deliver.render import _corpus
    return _corpus(
        {"company": {"value": "Unstuck"},
         "role": {"value": "Partner & Co-founder"},
         "thread.last_inbound": {"value": "2026-07-22T10:00"}},
        {"entity": "maria@alystventures.com"},
        ("Rohit Swerashi", "mrrohitswerashi@gmail.com"))


def test_a_fluent_grounded_draft_is_not_rejected_for_saying_thanks():
    """The guard exists to catch an invented ENTITY, not ordinary capitalised English.

    It flagged every capitalised token and checked it against the same five-field fact record the
    model had been given, so any readable sentence failed: 25 of one org's 41 cards were rejected
    on words like "Thanks", "Best" and the founder's own name, and shipped as empty template
    stubs. The model was called, produced correct copy, and the copy was discarded.
    """
    from genios_engine.deliver.render import invention_ok

    ct, cn = _guard_corpus()
    ok, why = invention_ok(
        "Hi Maria,\n\nThanks for reaching out. Happy to walk you through Unstuck.\n\nBest,\nRohit",
        ct, cn)
    assert ok, f"a grounded, fluent draft was rejected on {why!r}"


def test_the_senders_own_name_is_not_an_invented_person():
    """Signing a draft is the sender naming himself, not a claim the facts must support."""
    from genios_engine.deliver.render import invention_ok

    ct, cn = _guard_corpus()
    ok, why = invention_ok("Best regards, Rohit", ct, cn)
    assert ok, f"the account holder's own name was rejected as invention: {why!r}"


def test_an_actually_invented_company_is_still_caught():
    """Narrowing the guard must not disarm it — this is the case it exists for."""
    from genios_engine.deliver.render import invention_ok

    ct, cn = _guard_corpus()
    ok, why = invention_ok("Our friends at Initech will handle it", ct, cn)
    assert not ok and why == "name:Initech"


def test_a_date_the_evidence_does_not_support_is_still_invention():
    """Calendar words are deliberately NOT exempt.

    A weekday or month is not an entity, but it IS a factual claim, and a draft proposing a date
    the facts do not support is inventing it — in mail the user is about to send. Exempting them
    as "grammar" would have quietly licensed made-up dates.
    """
    from genios_engine.deliver.render import invention_ok

    ct, cn = _guard_corpus()
    assert invention_ok("No inbound since July 22", ct, cn)[0], "the real fact date must pass"
    ok, why = invention_ok("No inbound since March 22", ct, cn)
    assert not ok and why == "name:March"


def test_an_invented_name_cannot_escape_by_starting_a_sentence():
    """Position must not be an exemption — only the word can decide.

    Exempting a sentence's first word looks safe: "Reach out to them" opens with a capital that
    is pure grammar. But it equally exempts "Initech will vouch for us", so an invented company
    escapes by the accident of where it sits. A stop-list covers both jobs — the imperative
    openers a positional rule was protecting, and the greetings and sign-offs it never reached in
    a multi-paragraph draft.
    """
    from genios_engine.deliver.render import _proper_nouns

    # the case position silently allowed through
    assert _proper_nouns("Initech will vouch for us") == ["Initech"]
    # the case position existed to protect
    assert _proper_nouns("Reach out to Zephyr about the deal") == ["Zephyr"]
    # greetings and sign-offs anywhere in the draft
    assert _proper_nouns("Hi there,\nThanks for the note") == []
    assert _proper_nouns("They have gone quiet.") == []


def test_every_rule_gets_a_real_day_count_not_a_word():
    """The clock comes from the rule, so all 25 rules can state a duration — or none at all.

    `objection_open` was absent from the hand-written map, so its card read "Raised severald ago
    — still unanswered". That is worse than saying nothing: it looks like a number the system
    measured.
    """
    from genios_engine.packs.general_v1 import GENERAL_V1

    facts = {"thread.last_inbound": {"value": (NOW - timedelta(days=8)).isoformat()}}
    assert compute_slots("objection_open", "x", facts, NOW, "thread.last_inbound")["days"] == 8

    # every rule in both packs declares one, so none can fall through to the sentinel
    for pack in (SALES_V1, GENERAL_V1):
        for rule in pack["rules"]:
            assert (rule.get("urgency") or {}).get("path"), (
                f"{rule['id']} declares no urgency path — its card cannot state a duration")


def test_a_duration_we_cannot_compute_is_omitted_not_worded():
    """Saying nothing is honest; "severald" is neither a number nor a sentence."""
    from genios_engine.deliver.render import _fallback

    template = {"fallback": {"headline": "Handle {entity}'s objection now",
                             "situation": "Raised {days}d ago — still unanswered"}}
    unknown = _fallback(template, {"entity": "x@y.com", "days": "several"})
    assert "several" not in unknown["situation"]
    assert unknown["situation"] == "still unanswered", "the rest of the sentence must survive"

    known = _fallback(template, {"entity": "x@y.com", "days": 8})
    assert known["situation"] == "Raised 8d ago — still unanswered"


# ── the clarity gate must be written, not annotated ──────────────────────────────────────────
def test_a_card_with_no_known_ask_is_written_as_an_observation():
    """The gate existed, was correct, and changed nothing anyone saw.

    `_actionability` ran inside a read projection on `GET /cards/{card_id}` and ADDED a sibling
    field — it never rewrote the headline, lowered the level, or removed the button. `GET /cards`,
    the list view a user actually scans, applied no gate at all. So "Reply to boardy@boardy.ai
    now" was shown as a confident instruction while the detail view of the same card knew the ask
    was unknown.
    """
    from genios_engine.deliver.card_builder import clarity_verdict

    grounded, missing, recommended = clarity_verdict("unanswered_email", {"introduction"}, set())
    assert not grounded
    assert missing == "what response they need"
    assert recommended, "an abstention must say what a human should do instead"


def test_a_card_whose_ask_is_known_keeps_its_imperative():
    """The gate must not disarm the product — a grounded card still instructs."""
    from genios_engine.deliver.card_builder import clarity_verdict

    assert clarity_verdict("unanswered_email", {"question"}, set())[0]
    assert clarity_verdict("commitment_overdue", set(), {"commitment.action"})[0]


def test_a_rule_with_no_clarity_requirement_is_untouched():
    """Only the reason codes whose imperative depends on a specific fact are gated."""
    from genios_engine.deliver.card_builder import clarity_verdict

    assert clarity_verdict("closed_lost_risk", set(), set())[0]
    assert clarity_verdict(None, set(), set())[0]
