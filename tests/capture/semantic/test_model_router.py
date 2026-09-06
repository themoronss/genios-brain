"""G3 · ALG-05, the model router — Wave W3 (doc 04, L1.4.10-U1 and the derived U2).

    pytest tests/capture/semantic/test_model_router.py -q

Doc 04's acceptance block is four lines and they are the first four tests here, verbatim:

    a 200-char chat line                  -> T1
    a 6000-char email with $ and 2 dates  -> T2 or T3
    a PDF chunk                           -> never T1
    budget exhausted                      -> a T3 request comes back T2 with tier_demoted set

The last row is the one with teeth, and it is asserted in three parts rather than one: the tier
changed, the flag is set, AND `requested_tier` still says T3. A demotion that dropped what was
asked for would produce a stored row indistinguishable from a genuine T2, which makes doc 04's
FAILURE MODES line — *persistent demotion means the budget is wrong, not the router* — a
conclusion nobody can reach from the data.

**The counts are REAL.** Every row builds its `RouterCounts` by running the W2 structural
parser over actual text (`router_counts(scan(text))`), never by handing the router two integers
somebody typed. The whole claim of ALG-05 is that the tier is a function of what a regex found;
a test that supplied the counts directly would prove the arithmetic and leave the claim
untested — and it would still pass on the day the currency regex stopped matching `$84K`.

**No model is called, and none can be.** `tests/capture/conftest.py` refuses `socket.connect`
for every test in this tree without a `pg` or `llm` marker, so *"the model never chooses its own
tier"* is enforced by the harness rather than promised by a docstring.
"""

from __future__ import annotations

import pytest

from genios_engine.capture.semantic.model_router import (BUDGET_REASON,
                                                         CURRENCY_TOKENS_FOR_POINTS,
                                                         DATE_TOKENS_FOR_POINTS,
                                                         DEEP_THREAD_MESSAGES,
                                                         FLOOR_T2_PROFILES, LONG_CONTENT_CHARS,
                                                         NO_T3_BUDGET, SCORE_TABLE,
                                                         T2_THRESHOLD, T3_THRESHOLD, T3Budget,
                                                         TierRequest, UNLIMITED_T3, band_for,
                                                         decide_tier, record, route)
from genios_engine.capture.semantic.profiles import PROFILE_IDS, TIERS
from genios_engine.capture.structural.tokens import router_counts, scan

WAVE = "W3"
GATE = "G3"

#: A 200-character Slack line — doc 04's first acceptance row. No money, one weekday that the
#: parser does count as a date string, nothing long.
CHAT_LINE = ("hey — quick one, are we still good for the standup on monday? "
             "i can move it if that helps, no strong feelings either way. "
             "ping me when you get a sec and i'll update the invite for everyone.")

#: A 6,000-character email carrying one currency token and two date strings — doc 04's second
#: row. The three facts are asserted from the parser's own counts below, not assumed.
MONEY_EMAIL = (
    "Hi Rohit,\n\nConfirming the renewal terms we discussed. The annual contract moves to "
    "$84,000 from the current tier, effective Oct 15, 2026, and Finance need sign-off before "
    "Nov 3, 2026 or we fall back to the month-to-month rate.\n\n"
) + ("Background on the pricing change follows below for the record. " * 100)

#: A one-paragraph slice of an agreement — doc 04's third row. Deliberately SHORT: a long PDF
#: would clear the threshold on length alone and the floor override would never be exercised.
PDF_CHUNK = ("3.2 Termination. Either party may terminate this agreement upon written notice, "
             "provided that all obligations accrued prior to the effective date survive.")


def _counts(text: str):
    """The W2 structural parser's counts for `text` — the router's only content input."""
    return router_counts(scan(text))


def _request(profile_id: str, text: str, **kwargs) -> TierRequest:
    return TierRequest(profile_id=profile_id, content_length=len(text), counts=_counts(text),
                       **kwargs)


# ── doc 04's acceptance table, verbatim ─────────────────────────────────────────────────────

@pytest.mark.gate
def test_a_200_char_chat_line_is_t1():
    """Doc 04 row 1. The -30 chat row is what keeps a busy channel off the invoice."""
    assert 150 <= len(CHAT_LINE) <= 250, "the fixture must be the ~200 chars the doc names"
    decision = decide_tier(_request("chat", CHAT_LINE))
    assert decision.tier == "T1", (
        f"score {decision.tier_score} from {[c.name for c in decision.fired]}")
    assert decision.tier_demoted is False and decision.floor_applied is False


@pytest.mark.gate
def test_a_6000_char_email_with_currency_and_two_dates_is_t2_or_t3():
    """Doc 04 row 2 — and the three properties it names are read off the parser, not assumed.

    If the currency regex stops matching `$84,000` this test fails HERE, at the input assertion,
    which is the difference between "the tier arithmetic is wrong" and "the token scan is wrong".
    """
    counts = _counts(MONEY_EMAIL)
    assert len(MONEY_EMAIL) > LONG_CONTENT_CHARS, "the fixture must be the long one"
    assert counts.currency_token_count >= CURRENCY_TOKENS_FOR_POINTS
    assert counts.date_token_count >= DATE_TOKENS_FOR_POINTS

    decision = decide_tier(_request("email", MONEY_EMAIL), UNLIMITED_T3)
    assert decision.tier in ("T2", "T3"), f"score {decision.tier_score}"
    assert {c.name for c in decision.fired} >= {"long_content", "currency_tokens", "date_tokens"}


@pytest.mark.gate
@pytest.mark.parametrize("profile", sorted(FLOOR_T2_PROFILES))
def test_a_pdf_chunk_is_never_t1(profile):
    """Doc 04 row 3. The chunk is short enough to score T1 on its own — the floor is what stops
    it, and asserting `tier != T1` on a long document would pass without the floor existing."""
    request = _request(profile, PDF_CHUNK)
    assert band_for(decide_tier(request).tier_score) == "T1", (
        "this fixture must land in the T1 band before the override, or the floor is untested")
    decision = decide_tier(request)
    assert decision.tier == "T2" and decision.floor_applied is True


@pytest.mark.gate
def test_budget_exhausted_demotes_a_t3_to_t2_and_says_so():
    """Doc 04 row 4, the interesting one: the demotion must be VISIBLE, not silent.

    Three assertions, not one. The served tier changed, the flag is set, and `requested_tier`
    still records T3 — without that third fact a demoted row is indistinguishable from a
    genuine T2, and doc 04's FAILURE MODES line (*persistent demotion means the budget is
    wrong, not the router*) is unreachable from the stored data.
    """
    request = _request("document", MONEY_EMAIL, attachment_present=True)
    granted = decide_tier(request, UNLIMITED_T3)
    assert granted.tier == "T3", f"fixture must ask for T3; scored {granted.tier_score}"

    spent = T3Budget(t3_limit=5, t3_granted=5, day="2026-09-05")
    demoted = decide_tier(request, spent)
    assert demoted.tier == "T2"
    assert demoted.requested_tier == "T3"
    assert demoted.tier_demoted is True
    assert demoted.demotion_reason == BUDGET_REASON
    assert demoted.tier_score == granted.tier_score, (
        "the budget must not change the SCORE — the content deserved what it deserved, and a "
        "score that moved with the wallet could not be compared across days")


# ── the score table ─────────────────────────────────────────────────────────────────────────

#: One row per line of doc 04's pseudocode: the row name, its points, and a request that turns
#: exactly that row on relative to the same request with it off.
SCORE_ROWS = (
    ("long_content", 30, {"text": "x " * 3_000}, {"text": "x " * 10}),
    ("attachment_present", 25, {"attachment_present": True}, {"attachment_present": False}),
    ("currency_tokens", 25, {"text": "we agreed on $84,000 for the year"},
     {"text": "we agreed on the number for the year"}),
    ("date_tokens", 20, {"text": "Oct 15, 2026 and Nov 3, 2026 are the two dates"},
     {"text": "the two dates are in the appendix"}),
    ("deep_thread", 15, {"thread_depth": DEEP_THREAD_MESSAGES},
     {"thread_depth": DEEP_THREAD_MESSAGES - 1}),
    ("company_canon", 15, {"internal_kind": "pricing_policy"}, {"internal_kind": None}),
)


def _probe(text: str = "a short neutral line with nothing in it", *, profile: str = "email",
           **kwargs) -> TierRequest:
    return _request(profile, text, **kwargs)


@pytest.mark.gate
@pytest.mark.parametrize("name,points,on,off",
                         [pytest.param(*row, id=row[0]) for row in SCORE_ROWS])
def test_each_score_row_is_worth_exactly_the_points_doc_04_gives_it(name, points, on, off):
    """The row fires, and it moves the total by its own weight and by nothing else.

    Asserting the DIFFERENCE rather than the absolute total is what makes this a test of one
    row: a fixture that accidentally also triggered `long_content` would still show +30 in the
    total, and only the delta between two otherwise-identical requests isolates the row.
    """
    high = decide_tier(_probe(**on)).tier_score
    low = decide_tier(_probe(**off)).tier_score
    assert high - low == points, f"row {name!r} moved the score by {high - low}, not {points}"
    fired = {c.name for c in decide_tier(_probe(**on)).fired}
    assert name in fired and name not in {c.name for c in decide_tier(_probe(**off)).fired}


@pytest.mark.gate
def test_the_chat_profile_subtracts_thirty():
    """The one negative row. Same content, two profiles, -30 between them."""
    text = "we agreed on $84,000 for the year"
    email = decide_tier(_request("email", text)).tier_score
    chat = decide_tier(_request("chat", text)).tier_score
    assert chat - email == -30


@pytest.mark.gate
def test_the_heavy_profile_row_adds_twenty():
    """`profile in {document, transcript}` is worth +20 on top of the T2 floor."""
    text = "a short neutral line with nothing in it"
    email = decide_tier(_request("email", text)).tier_score
    for profile in sorted(FLOOR_T2_PROFILES):
        assert decide_tier(_request(profile, text)).tier_score - email == 20


@pytest.mark.gate
def test_every_score_row_has_a_test_row():
    """A weight added to the implementation without a row here is a cost lever nobody measured.

    `heavy_profile` and `cheap_profile` are exercised by their own named tests above, because
    both are properties of the profile rather than of the request and cannot be toggled by the
    `_probe` kwargs the parametrized table uses.
    """
    covered = {name for name, _, _, _ in SCORE_ROWS} | {"heavy_profile", "cheap_profile"}
    assert covered == {row.name for row in SCORE_TABLE}


#: Doc 04's band boundaries as LITERALS, both edges of both bands.
#:
#: Written out rather than derived from `T2_THRESHOLD`/`T3_THRESHOLD`, and that is the whole
#: point of the row: a table spelled `(T3_THRESHOLD - 1, "T2"), (T3_THRESHOLD, "T3")` moves with
#: the constant and passes for every value of it, so lowering the T3 threshold to 70 — which
#: silently re-tiers every org's traffic onto the most expensive model — would be green. It was,
#: until this table stopped asking the implementation what its own thresholds are.
BAND_TABLE = (
    (-30, "T1"), (0, "T1"), (39, "T1"),
    (40, "T2"), (74, "T2"),
    (75, "T3"), (10_000, "T3"),
)


@pytest.mark.gate
@pytest.mark.parametrize("score,expected",
                         [pytest.param(*row, id=f"{row[0]}->{row[1]}") for row in BAND_TABLE])
def test_the_bands_are_closed_at_their_lower_bound(score, expected):
    """Doc 04: `T1 if < 40`, `T2 if 40 <= s < 75`, `T3 if >= 75`. Both edges, both directions."""
    assert band_for(score) == expected


@pytest.mark.gate
def test_the_thresholds_are_the_ones_doc_04_names():
    """The constants themselves, pinned. `band_for` could be correct against any pair of
    thresholds; only this says WHICH pair, and the thresholds are the cost lever's dial."""
    assert (T2_THRESHOLD, T3_THRESHOLD) == (40, 75)


# ── the two overrides, and their interaction ────────────────────────────────────────────────

@pytest.mark.gate
def test_the_floor_never_fights_the_budget():
    """A document whose org has no T3 left is T2 — not T1, and not T3.

    The two overrides push in opposite directions on the same profile, so their composition is
    asserted rather than reasoned about: the floor raises to T2 and the budget lowers only to
    T2, which is why no ordering of them can produce a T1 for a document.
    """
    heavy = _request("document", MONEY_EMAIL, attachment_present=True)
    assert decide_tier(heavy, UNLIMITED_T3).tier == "T3"
    assert decide_tier(heavy, NO_T3_BUDGET).tier == "T2"
    thin = _request("document", PDF_CHUNK)
    assert decide_tier(thin, NO_T3_BUDGET).tier == "T2"
    assert decide_tier(thin, NO_T3_BUDGET).tier_demoted is False, (
        "a floor is not a demotion — counting it as one would inflate the signal the admin "
        "console watches with events that were never entitled to T3")


@pytest.mark.gate
def test_an_exhausted_budget_does_not_touch_a_t1_or_a_t2():
    """The budget is a T3 allowance. A cheap call that spent none must not be re-tiered."""
    for profile, text in (("chat", CHAT_LINE), ("email", "a short neutral line")):
        decision = decide_tier(_request(profile, text), NO_T3_BUDGET)
        assert decision.tier_demoted is False and decision.demotion_reason is None


@pytest.mark.gate
def test_a_decision_cannot_claim_a_demotion_it_did_not_make():
    """`tier_demoted` IS the disagreement between `tier` and `requested_tier`.

    Constructed through the real dataclass, because `__post_init__` is the invariant under test:
    a hand-built row that set the flag without changing the tier would be a false alarm in the
    monitored counter, and one that changed the tier without the flag is the silent downgrade.
    """
    from genios_engine.capture.semantic.model_router import TierDecision
    with pytest.raises(ValueError, match="tier_demoted"):
        TierDecision(tier="T2", tier_score=80, requested_tier="T2", tier_demoted=True,
                     demotion_reason=BUDGET_REASON, floor_applied=False, contributions=())
    with pytest.raises(ValueError, match="tier_demoted"):
        TierDecision(tier="T2", tier_score=80, requested_tier="T3", tier_demoted=False,
                     demotion_reason=None, floor_applied=False, contributions=())
    with pytest.raises(ValueError, match="reason"):
        TierDecision(tier="T2", tier_score=80, requested_tier="T3", tier_demoted=True,
                     demotion_reason=None, floor_applied=False, contributions=())


# ── U2 · the budget ledger and the demotion counter ─────────────────────────────────────────

@pytest.mark.gate
def test_a_served_t3_spends_allowance_until_the_budget_exhausts():
    """L1.4.10-U2. The override in U1 reads `budget.exhausted`; this is what makes it true.

    Without this unit the budget is a constant, the second override is dead code, and the only
    reason its test passes is that somebody handed it a pre-exhausted value.
    """
    budget = T3Budget(t3_limit=2, day="2026-09-05")
    request = _request("document", MONEY_EMAIL, attachment_present=True)

    tiers = []
    for _ in range(3):
        decision, budget = route(request, budget)
        tiers.append(decision.tier)
    assert tiers == ["T3", "T3", "T2"]
    assert (budget.t3_granted, budget.t3_demoted) == (2, 1)
    assert budget.exhausted is True


@pytest.mark.gate
@pytest.mark.parametrize("tier,demoted,expected", [
    pytest.param("T3", False, (1, 0), id="granted-T3-spends-allowance"),
    pytest.param("T2", True, (0, 1), id="demoted-T3-spends-none-but-is-counted"),
    pytest.param("T2", False, (0, 0), id="genuine-T2-moves-nothing"),
    pytest.param("T1", False, (0, 0), id="T1-moves-nothing"),
])
def test_record_moves_exactly_one_counter_and_only_for_t3(tier, demoted, expected):
    """A demoted request spends no allowance — it was never issued — but IS counted, because
    the counter is the FAILURE MODES signal doc 04 asks be surfaced in the admin console."""
    from genios_engine.capture.semantic.model_router import TierDecision
    decision = TierDecision(tier=tier, tier_score=99,
                            requested_tier="T3" if demoted else tier, tier_demoted=demoted,
                            demotion_reason=BUDGET_REASON if demoted else None,
                            floor_applied=False, contributions=())
    after = record(T3Budget(t3_limit=9, day="d"), decision)
    assert (after.t3_granted, after.t3_demoted) == expected
    assert after.t3_limit == 9 and after.day == "d", "record changes counters, not configuration"


@pytest.mark.gate
@pytest.mark.parametrize("granted,demoted,expected_bp", [
    pytest.param(0, 0, 0, id="no-t3-requests-is-a-healthy-day-not-undefined"),
    pytest.param(4, 0, 0, id="all-served"),
    pytest.param(2, 2, 5_000, id="half"),
    pytest.param(0, 3, 10_000, id="all-demoted"),
    pytest.param(2, 1, 3_333, id="one-third-floors-not-rounds"),
])
def test_the_demotion_rate_is_integer_basis_points(granted, demoted, expected_bp):
    """Basis points and floor division, never a float.

    This number is compared against a threshold in an alert; two processes disagreeing at the
    sixth decimal about whether 1/3 exceeds 0.3333 produce an alert that flaps, which is how a
    real signal gets muted.
    """
    budget = T3Budget(t3_limit=10, t3_granted=granted, t3_demoted=demoted)
    rate = budget.demotion_rate_bp
    assert rate == expected_bp
    assert isinstance(rate, int) and not isinstance(rate, bool)


@pytest.mark.gate
def test_a_zero_limit_budget_demotes_every_t3_and_never_exhausts_into_nonsense():
    """`NO_T3_BUDGET` is the default deliberately: an org wrongly capped at zero shows up as a
    climbing demotion counter, an org wrongly uncapped shows up as an invoice."""
    assert NO_T3_BUDGET.exhausted is True
    decision, after = route(_request("document", MONEY_EMAIL, attachment_present=True),
                            NO_T3_BUDGET)
    assert decision.tier == "T2" and decision.tier_demoted is True
    assert (after.t3_granted, after.t3_demoted) == (0, 1)
    assert after.demotion_rate_bp == 10_000


@pytest.mark.gate
def test_a_budget_is_a_value_the_caller_can_replay():
    """Frozen and returned-not-mutated, so two coroutines cannot race one counter and a stored
    budget can be compared against a recomputed one."""
    budget = T3Budget(t3_limit=3, day="2026-09-05")
    _, after = route(_request("document", MONEY_EMAIL, attachment_present=True), budget)
    assert budget.t3_granted == 0 and after.t3_granted == 1
    assert budget == T3Budget(t3_limit=3, day="2026-09-05")


@pytest.mark.gate
@pytest.mark.parametrize("kwargs", [
    pytest.param({"t3_limit": -1}, id="negative-limit"),
    pytest.param({"t3_limit": 1, "t3_granted": -2}, id="negative-granted"),
    pytest.param({"t3_limit": 1, "t3_demoted": -3}, id="negative-demoted"),
])
def test_a_negative_counter_is_refused(kwargs):
    """A negative `t3_granted` makes `exhausted` read False forever — an unenforceable budget
    that looks configured."""
    with pytest.raises(ValueError, match="negative count"):
        T3Budget(**kwargs)


# ── the determinism constraint ──────────────────────────────────────────────────────────────

@pytest.mark.gate
def test_the_same_request_scores_identically_every_time():
    """Replay is the property the L1.4.9 cache is built on. A tier that varied per call would
    make the same content cache under two keys, both claiming to be canonical."""
    request = _request("email", MONEY_EMAIL, thread_depth=4, internal_kind="pricing_policy")
    first = decide_tier(request, UNLIMITED_T3)
    assert all(decide_tier(request, UNLIMITED_T3) == first for _ in range(5))


@pytest.mark.gate
def test_every_contribution_is_reported_whether_or_not_it_fired():
    """*"This stayed T1 because it had no currency tokens"* is the explanation somebody needs
    when a card is missing an amount, and a list of only the rows that fired cannot give it."""
    decision = decide_tier(_request("chat", CHAT_LINE))
    assert {c.name for c in decision.contributions} == {row.name for row in SCORE_TABLE}
    assert decision.tier_score == sum(c.awarded for c in decision.contributions)
    assert sum(c.awarded for c in decision.contributions if not c.applied) == 0
    for contribution in decision.contributions:
        assert contribution.why.strip()


@pytest.mark.gate
def test_the_score_is_integer_arithmetic_end_to_end():
    """No float anywhere: the score is points, the demotion rate is basis points. A float that
    reached the score would make the band boundary a place two machines can disagree about."""
    decision = decide_tier(_request("email", MONEY_EMAIL), UNLIMITED_T3)
    values = [decision.tier_score, *(c.points for c in decision.contributions),
              *(row.points for row in SCORE_TABLE), T2_THRESHOLD, T3_THRESHOLD]
    assert all(isinstance(v, int) and not isinstance(v, bool) for v in values)


@pytest.mark.gate
@pytest.mark.parametrize("profile_id", ["structured", "newsletter", "", "EMAIL"])
def test_an_unregistered_profile_is_refused_rather_than_tiered(profile_id):
    """Unlike `get_profile`, this does NOT degrade to the email profile.

    The only ids that are not registered are the model-free `structured` bypass lane — which
    must make ZERO model calls — and a caller bug. Silently tiering either one buys a model
    call nobody asked for, and for `structured` it also breaks doc 03's guarantee.
    """
    with pytest.raises(ValueError, match="unknown extraction profile"):
        TierRequest(profile_id=profile_id, content_length=10, counts=_counts("hi"))


@pytest.mark.gate
@pytest.mark.parametrize("kwargs,match", [
    pytest.param({"content_length": -1}, "content_length", id="negative-length"),
    pytest.param({"thread_depth": -1}, "thread_depth", id="negative-depth"),
])
def test_a_negative_count_is_refused_rather_than_scored(kwargs, match):
    """A negative length suppresses the +30 row silently — the request is a caller bug, and the
    only visible symptom would be a contract read by the cheapest model."""
    base = {"profile_id": "email", "content_length": 10, "counts": _counts("hi")}
    with pytest.raises(ValueError, match=match):
        TierRequest(**{**base, **kwargs})


@pytest.mark.gate
def test_every_registered_profile_can_be_tiered_and_lands_in_a_known_tier():
    """No profile in the registry is unroutable — a profile the model router refuses is a
    prompt that can never run."""
    for profile_id in PROFILE_IDS:
        decision = decide_tier(_request(profile_id, MONEY_EMAIL), UNLIMITED_T3)
        assert decision.tier in TIERS and decision.requested_tier in TIERS
