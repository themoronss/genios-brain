"""GeniOS-011 S18.U2 — the expert pass still reviews when L2 cannot; one oversized file is that file's problem.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/expert/test_the_expert_pass_still_reviews_when_l2_cannot.py -q

`reason/expert/sweep.expert_pass`, against three verified audit items (GeniOS-011 audit, step S18):

  * `l2-cards-precondition-not-enforced` — with `l2_cards` on, the pass made no R-7 call and handed every file that
    moved to the L2 pass. But `l2_pass` judges only with `l2_reasoning` on and an R-9 client, and the switch's
    PRECONDITIONS are reported, never enforced (`platform/l4_activation`): with either missing, `l2_pass` returned
    `skipped`, nothing logged it, and NOBODY judged the file — it lost its cover and fell to the formula lanes.
    Now L2 judges only when it can (`l2_cards` AND `l2_reasoning` AND an R-9 client); else R-7 reviews as before
    and a WARNING says why.
  * `l2-r7-per-call-refusal-stops-pass` — any OVER_BUDGET broke the pass, a per-call refusal included, so one
    oversized file sorted first carried every file behind it, every sweep. The L2 pass's own fix (b8a8a43c),
    ported: that file is carried alone and the pass goes on; the DAY's cap still stops it.
  * `l2-skips-invisible` — a pass that skips says so in the log, with its reason.
"""
from __future__ import annotations

import logging
import re
from datetime import timedelta

import pytest
from sqlalchemy import text

from genios_engine.context.llm.client import LLMResult
from genios_engine.reason import llm_sites
from genios_engine.reason.bundle.budget import REASON_PER_CALL
from genios_engine.reason.bundle.budget import NarrativeBudget
from genios_engine.reason.bundle.budget import estimate_micro_usd
from genios_engine.reason.bundle.sites import SITE_EXPERT
from genios_engine.reason.expert import store as R
from genios_engine.reason.expert import sweep as P

ORG = "org_g011_s18u2_expert"
KUNAL, ASHA, MEERA = "kunal@meridianvc.test", "asha@tamarindfund.test", "meera@banyancap.test"
LOGGER = "genios.reason.expert.sweep"


class _Expert:
    """R-7 answering every review validly, citing the first event its dossier prints."""
    model = "claude-sonnet-5"

    def __init__(self):
        self.prompts: list[str] = []

    def call(self, prompt, *, max_tokens=400, **_):
        self.prompts.append(prompt)
        evidence = re.search(r"\[(evt_[^\]\s]+)\]", prompt).group(1)
        return LLMResult(parsed={
            "facts": [{"claim": "they wrote to us", "evidence": [evidence]}],
            "frames": {"primary": "a fund getting to know us", "rivals": ["a cold intro"]},
            "expected_vs_actual": {"stage": None, "expected": "a reply", "actual": "a reply came"},
            "scenarios": {"do_nothing": "it cools", "act": "it moves", "best": "a meeting",
                          "worst": "silence", "signals_to_watch": ["a reply"]},
            "appraisal": {"stakes": "medium", "urgency": "low", "reversibility": "reversible",
                          "reasons": ["early"]},
            "mode": "wait", "wait_or_stop": "wait for their reply", "done_when": "they reply"},
            raw="{}", ok=True, model=self.model, input_tokens=9000, output_tokens=900)


class _R9:
    """What the R-sites' door builds for R-9 when a model is configured. The expert pass only asks that one CAN be
    built — it never calls it (the L2 pass judges with its own)."""
    model = "claude-sonnet-5"

    def call(self, *_a, **_k):
        raise AssertionError("the expert pass never calls R-9")


def _activate(store, *features: str) -> None:
    with store.engine.begin() as c:
        for feature in features:
            c.execute(text("insert into l4_activation (org_id, feature, enabled_by) values (:o, :f, 'test')"),
                      {"o": ORG, "f": feature})


def _files(store) -> dict[str, str]:
    """Each counterparty's file: the node its first mail is anchored on."""
    with store.engine.connect() as c:
        return {r.event_id: r.anchor_node_id for r in c.execute(text(
            "select m.event_id, k.anchor_node_id from context_correlations k "
            "  join context_correlation_members m on m.org_id = k.org_id "
            "       and m.correlation_id = k.correlation_id where k.org_id = :o"), {"o": ORG})}


def _rows(store) -> dict[str, tuple[str, str | None]]:
    with store.engine.connect() as c:
        return {r.file_id: (r.status, r.reason) for r in c.execute(text(
            "select file_id, status, reason from expert_reviews where org_id = :o"), {"o": ORG})}


def _warnings(caplog) -> list[str]:
    return [r.getMessage() for r in caplog.records if r.name == LOGGER and r.levelno >= logging.WARNING]


# ── l2-cards-precondition-not-enforced ─────────────────────────────────────────────────────────────────────────
@pytest.fixture
def two_files(pg_store):
    """Two files that moved — Kunal's and Asha's — and the expert switched on."""
    from tests.context.workstream_world import FOUNDER
    from tests.context.workstream_world import process
    from tests.context.workstream_world import reset
    from tests.context.workstream_world import tenant
    from tests.reason.expert.test_the_dossier import NOW
    tenant(pg_store, ORG)
    process(pg_store, ORG, event_id="evt_k_in", sender=KUNAL, thread="t_k", at=NOW - timedelta(days=12))
    process(pg_store, ORG, event_id="evt_k_out", sender=FOUNDER, recipients=(KUNAL,), thread="t_k",
            at=NOW - timedelta(days=10))
    process(pg_store, ORG, event_id="evt_a_in", sender=ASHA, thread="t_a", at=NOW - timedelta(days=20))
    _activate(pg_store, "expert_review")
    try:
        yield pg_store, NOW
    finally:
        with pg_store.engine.begin() as c:
            c.execute(text("delete from l4_r_site_calls where org_id = :o"), {"o": ORG})
        reset(pg_store, ORG)


@pytest.mark.pg
def test_l2_cards_on_with_l2_reasoning_off_the_expert_still_reviews_and_says_why(two_files, monkeypatch, caplog):
    """The audit's case: `l2_cards` on, `l2_reasoning` off. The L2 pass would skip — so R-7 reviews every file
    that moved, covers it, and a WARNING names why L2 could not. Before, nothing was reviewed and nothing said."""
    store, now = two_files
    _activate(store, "l2_cards")
    monkeypatch.setattr(llm_sites, "make_site_client", lambda tier: _R9())    # an R-9 model IS configured
    caplog.set_level(logging.INFO, logger=LOGGER)
    expert = _Expert()
    receipt = P.expert_pass(store=store, org_id=ORG, now=now, llm=expert)
    files = _files(store)
    assert receipt["reviewed"] == {R.VALID: 2} and len(expert.prompts) == 2, receipt
    assert "to_l2" not in receipt and set(receipt["covered"]) == {files["evt_k_in"], files["evt_a_in"]}
    assert receipt["l2_cannot_judge"] == "l2_reasoning_not_activated"
    said = _warnings(caplog)
    assert any("l2_reasoning_not_activated" in w and ORG in w for w in said), said


@pytest.mark.pg
def test_l2_cards_and_l2_reasoning_on_with_no_r9_model_the_expert_still_reviews(two_files, monkeypatch, caplog):
    """Both switches on, but no R-9 client can be built (the door answers None, as it does with no key): the L2
    pass would skip `no_model_configured` — so R-7 reviews, and says why."""
    store, now = two_files
    _activate(store, "l2_reasoning", "l2_cards")
    monkeypatch.setattr(llm_sites, "make_site_client", lambda tier: None)
    caplog.set_level(logging.INFO, logger=LOGGER)
    expert = _Expert()
    receipt = P.expert_pass(store=store, org_id=ORG, now=now, llm=expert)
    assert receipt["reviewed"] == {R.VALID: 2} and len(expert.prompts) == 2, receipt
    assert "to_l2" not in receipt and len(receipt["covered"]) == 2
    assert receipt["l2_cannot_judge"] == "no_model_configured"
    said = _warnings(caplog)
    assert any("no_model_configured" in w and "l2_cards" in w for w in said), said


@pytest.mark.pg
def test_with_l2_able_to_judge_the_moved_files_are_handed_over_and_no_r7_call(two_files, monkeypatch, caplog):
    """The control: all three conditions hold — the L2 pass judges, the expert makes no call and hands every moved
    file over, and nothing is warned."""
    store, now = two_files
    _activate(store, "l2_reasoning", "l2_cards")
    monkeypatch.setattr(llm_sites, "make_site_client", lambda tier: _R9())
    caplog.set_level(logging.INFO, logger=LOGGER)
    expert = _Expert()
    receipt = P.expert_pass(store=store, org_id=ORG, now=now, llm=expert)
    assert receipt["to_l2"] == 2 and expert.prompts == [] and receipt["reviewed"] == {}, receipt
    assert "l2_cannot_judge" not in receipt and _warnings(caplog) == []


# ── l2-r7-per-call-refusal-stops-pass ──────────────────────────────────────────────────────────────────────────
#: The oversized file's mail: each touch's words are shown whole up to `WORDS_CHARS` (1,200), eight touches whole —
#: so eight long mails make Asha's prompt ~10,000 characters longer than a one-mail file's.
LONG = " ".join(f"line {i} of the diligence notes about the round and its terms." for i in range(60))


def _meeting(store, now, *, after: str, event_id: str, days: float, who: str) -> None:
    """A meeting booked `days` from now, filed with the event `after` (its file) — it orders the files."""
    with store.engine.begin() as c:
        c.execute(text(
            "insert into source_events (event_id, org_id, connection_id, source, object_type, "
            " source_object_id, parent_object_id, dedup_key, actor, recipients, occurred_at, "
            " captured_at, outcome) values (:e, :o, 'con_x', 'gcal', 'calendar_event', :e, null, "
            " :k, cast(:a as jsonb), :r, :at, :now, 'emitted')"),
            {"e": event_id, "o": ORG, "k": f"gcal:calendar_event:{event_id}",
             "a": f'{{"email": "{who}"}}', "r": [who], "at": now + timedelta(days=days), "now": now})
        c.execute(text(
            "insert into context_correlation_members (org_id, correlation_id, event_id) "
            "select org_id, correlation_id, :e from context_correlation_members "
            " where org_id = :o and event_id = :after"), {"o": ORG, "e": event_id, "after": after})


@pytest.fixture
def three_files(pg_store):
    """Kunal's file (a meeting tomorrow), Asha's (in two days — eight long mails), Meera's (in three): nearest first,
    the oversized file is the one BETWEEN the two small ones."""
    from tests.context.workstream_world import process
    from tests.context.workstream_world import reset
    from tests.context.workstream_world import tenant
    from tests.reason.expert.test_the_dossier import NOW
    tenant(pg_store, ORG)
    process(pg_store, ORG, event_id="evt_s18u2_k", sender=KUNAL, thread="t_k", at=NOW - timedelta(days=3))
    for n in range(8):
        event = f"evt_s18u2_a{n}"
        process(pg_store, ORG, event_id=event, sender=ASHA, thread="t_a", at=NOW - timedelta(days=3, hours=n + 1))
        with pg_store.engine.begin() as c:     # the words memory holds for the mail (`context/workstream_timeline`)
            c.execute(text("insert into prepared_content (event_id, org_id, prepared_content_id, clean_text) "
                           "values (:e, :o, :p, :t)"), {"e": event, "o": ORG, "p": f"pc_{event}", "t": LONG})
    process(pg_store, ORG, event_id="evt_s18u2_m", sender=MEERA, thread="t_m", at=NOW - timedelta(days=4))
    _meeting(pg_store, NOW, after="evt_s18u2_k", event_id="evt_s18u2_k_call", days=1, who=KUNAL)
    _meeting(pg_store, NOW, after="evt_s18u2_a0", event_id="evt_s18u2_a_call", days=2, who=ASHA)
    _meeting(pg_store, NOW, after="evt_s18u2_m", event_id="evt_s18u2_m_call", days=3, who=MEERA)
    _activate(pg_store, "expert_review")
    try:
        yield pg_store, NOW
    finally:
        with pg_store.engine.begin() as c:
            c.execute(text("delete from l4_r_site_calls where org_id = :o"), {"o": ORG})
        reset(pg_store, ORG)


def _estimates(store, now) -> dict[str, int]:
    """What the gate prices each file's R-7 call at (`reason/bundle/gate`, step 5): its prompt's characters and
    the output ceiling the call is made at."""
    from genios_engine.context.llm.client import output_ceiling
    from genios_engine.context.workstreams import files_for
    from genios_engine.reason.bundle.sites import max_output_tokens
    from genios_engine.reason.bundle.sites import thinking_mode
    from genios_engine.reason.expert.dossier import build_dossier
    from genios_engine.reason.expert.dossier import read_parts
    from genios_engine.reason.expert.prompt import build_prompt
    ceiling = output_ceiling(_Expert.model, max_output_tokens(SITE_EXPERT), thinking_mode(SITE_EXPERT))
    with store.engine.connect() as c:
        return {f.file_id: estimate_micro_usd(
                    site=SITE_EXPERT, max_output_tokens=ceiling,
                    prompt_chars=len(build_prompt(build_dossier(read_parts(c, ORG, f.file_id, now=now)), None)))
                for f in files_for(c, ORG, now=now).files}


@pytest.mark.pg
def test_an_oversized_file_between_two_small_ones_is_carried_alone(three_files, caplog):
    """A per-call ceiling between the small files' estimates and the oversized one's: Kunal's file is reviewed,
    Asha's is refused for its size and CARRIED (its row says over_budget, so it waits for tomorrow), and Meera's —
    behind it — is reviewed all the same. Before, the refusal broke the pass and Meera's was never reached."""
    store, now = three_files
    files = _files(store)
    kunal, asha, meera = files["evt_s18u2_k"], files["evt_s18u2_a0"], files["evt_s18u2_m"]
    priced = _estimates(store, now)
    assert priced[asha] > max(priced[kunal], priced[meera]) + 2_000, priced      # µ$: ~10,000 characters apart
    ceiling = (max(priced[kunal], priced[meera]) + priced[asha]) // 2
    budget = NarrativeBudget(org_id=ORG, site=SITE_EXPERT, daily_cap_micro_usd=2_000_000,
                             per_call_cap_micro_usd=ceiling)
    caplog.set_level(logging.INFO, logger=LOGGER)
    expert = _Expert()
    receipt = P.expert_pass(store=store, org_id=ORG, now=now, llm=expert, budget=budget)
    assert receipt["reviewed"] == {R.VALID: 2, R.OVER_BUDGET: 1}, receipt
    assert receipt["too_big"] == 1 and receipt["carried"] == 0, receipt
    rows = _rows(store)
    assert rows[kunal][0] == R.VALID and rows[meera][0] == R.VALID, rows
    assert rows[asha][0] == R.OVER_BUDGET and REASON_PER_CALL in (rows[asha][1] or ""), rows
    assert len(expert.prompts) == 2, "the refused call is never made"
    assert set(receipt["covered"]) == {kunal, meera}, "a carried file is never covered"
    assert any(asha in w and REASON_PER_CALL in w for w in _warnings(caplog)), _warnings(caplog)
    # The next sweep of the day: the two reviews stand, and the oversized file waits for tomorrow — no call.
    again = P.expert_pass(store=store, org_id=ORG, now=now + timedelta(minutes=15), llm=_Expert(),
                          budget=NarrativeBudget(org_id=ORG, site=SITE_EXPERT, daily_cap_micro_usd=2_000_000,
                                                 per_call_cap_micro_usd=ceiling))
    assert again["unchanged"] == 2 and again["waiting"] == {"carried_today": 1}, again


@pytest.mark.pg
def test_the_days_cap_still_stops_the_pass_and_carries_the_rest(three_files):
    """The half that must not move: a day's budget that is spent stops the pass at the first refusal, and every
    file it did not reach is carried, counted — none of them is 'too big'."""
    store, now = three_files
    spent = NarrativeBudget(org_id=ORG, site=SITE_EXPERT, daily_cap_micro_usd=1, per_call_cap_micro_usd=100_000)
    expert = _Expert()
    receipt = P.expert_pass(store=store, org_id=ORG, now=now, llm=expert, budget=spent)
    assert receipt["reviewed"] == {R.OVER_BUDGET: 1} and expert.prompts == [], receipt
    assert receipt["carried"] == 2 and receipt["too_big"] == 0, receipt
    assert [status for status, _why in _rows(store).values()] == [R.OVER_BUDGET]


# ── l2-skips-invisible · hermetic: every skip returns before a file is read ────────────────────────────────────
class _Store:
    engine = object()          # never touched: every skip below returns before the first read


@pytest.mark.unit
@pytest.mark.parametrize("activated, door, skipped, level", [
    (frozenset(), _R9, "expert_review_not_activated", logging.INFO),
    (frozenset({"expert_review"}), None, "no_model_configured", logging.WARNING),
    (frozenset({"expert_review", "l2_reasoning", "l2_cards"}), None, "no_model_configured", logging.WARNING),
])
def test_every_skip_is_logged_with_its_reason(monkeypatch, caplog, activated, door, skipped, level):
    """A skip was a key in a receipt `run_all` only returned: a tenant with the feature on and no model reviewed
    nothing, and no line said so. A tenant without the feature is the switch working (INFO); a switched-on
    expert that cannot run is a stop someone must see (WARNING)."""
    monkeypatch.setattr(P, "activated_features", lambda engine, org_id: activated)
    monkeypatch.setattr(llm_sites, "make_site_client", lambda tier: door() if door else None)
    caplog.set_level(logging.INFO, logger=LOGGER)
    assert P.expert_pass(store=_Store(), org_id=ORG) == {"skipped": skipped}
    said = [r for r in caplog.records if r.name == LOGGER and "skipped" in r.getMessage()
            and skipped in r.getMessage() and ORG in r.getMessage()]      # the skip's own line, not the L2 warning
    assert said and said[-1].levelno == level, [(r.levelname, r.getMessage()) for r in caplog.records]


@pytest.mark.unit
def test_a_pass_with_no_engine_says_so(caplog):
    class _NoEngine:
        engine = None
    caplog.set_level(logging.INFO, logger=LOGGER)
    assert P.expert_pass(store=_NoEngine(), org_id=ORG) == {"skipped": "no_engine"}
    assert any("no_engine" in w and ORG in w for w in _warnings(caplog)), caplog.records
