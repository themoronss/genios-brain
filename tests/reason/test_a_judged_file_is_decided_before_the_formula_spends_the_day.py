"""GeniOS-011 S18.U1 · a judged file is decided before the formula spends the day — and every no-card reason is counted.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_a_judged_file_is_decided_before_the_formula_spends_the_day.py -q

Closes `l2-daily-cap-formula-first` and the covered-file half of `l2-skips-invisible` (the GeniOS-011 audit).

ONE CAP, AND THE JUDGED FILES USED TO PAY IT LAST. The compiled lane's daily allowance is the tenant's one cap
(`domain_shadow._daily_allowance`: budget per seat per day, less every signal already published today), and the
situation loop spent it first — formula situations, confidence-descending — while each file a VALID expert/L2 review
covers was decided only AFTER the loop (`_decide_covered_files`). On a day with seven formula situations to publish,
the review's next move — the judgment the architecture makes primary (`GeniOS-008/00-ARCHITECTURE.md`, "L2 is the
primary layer") — was `budget_exhausted`, and the founder got seven formula cards and not the one the expert wrote.
The files are now decided BEFORE the loop, from the same shared pool: no second allowance, and the formula takes
what is left.

AND A FILE THAT MAKES NO CARD SAYS WHY. Four ways a judged file made no card were a counter inside one INFO line for
the whole pass: no situation to bind it to (`covered_without_situation`), no tenant pack for its corpus
(`expert_no_tenant_pack`), a dark or unactivated domain (`expert_shadow`), the day's cap (`budget_exhausted`). Each
is now said at WARNING with the file and the reason, and the pass's result names each such file under its reason
(`covered_no_card`) — always present, empty included — for the sweep's outcomes to carry (S18.U3).
"""
from __future__ import annotations

import ast
import inspect
import logging
import os
import textwrap
from collections import Counter
from datetime import datetime
from datetime import timezone
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from genios_engine.contracts.reasoning import DecisionOutcome
from genios_engine.reason import domain_shadow as DS
from tests.reason.test_a_programme_is_not_decided_as_an_investor import admitted  # noqa: F401 — a fixture

# ── the shape, read from the code ───────────────────────────────────────────────────────────────


def _shadow_compile() -> ast.FunctionDef:
    tree = ast.parse(textwrap.dedent(inspect.getsource(DS.shadow_compile)))
    [fn] = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    return fn


def _calls(node: ast.AST, name: str) -> list[ast.Call]:
    return [call for call in ast.walk(node) if isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name) and call.func.id == name]


def _situation_loop(fn: ast.FunctionDef) -> ast.For:
    """The pass's one walk over the situations it read: `for row in situations:`."""
    loops = [node for node in ast.walk(fn) if isinstance(node, ast.For)
             and isinstance(node.iter, ast.Name) and node.iter.id == "situations"]
    assert len(loops) == 1, f"expected one situation loop in shadow_compile, found {len(loops)}"
    return loops[0]


@pytest.mark.unit
def test_the_covered_files_are_decided_before_the_situation_loop_and_only_there():
    """THE ORDER, HELD IN THE HERMETIC JOB TOO (the PG test below proves what it buys). The AST, never the text: a
    comment that names the call is not the call."""
    fn = _shadow_compile()
    loop = _situation_loop(fn)
    calls = _calls(fn, "_decide_covered_files")
    assert len(calls) == 1, f"the covered files are decided in exactly one place, found {len(calls)}"
    [call] = calls
    assert call.lineno < loop.lineno, (
        "the covered files are decided after the situation loop: the formula spends the day's cap first")
    assert not _calls(loop, "_decide_covered_files"), "a covered file is decided inside the situation loop"


@pytest.mark.unit
def test_the_loop_stands_a_situation_down_from_what_was_read_before_it():
    """The files decided first need to know, before the loop, what each review explains (a file's home and the
    signals its situations left): one reading, made before the loop — the loop never asks `covers` again, so the
    situations that stand down and the ones the files were decided against cannot disagree."""
    fn = _shadow_compile()
    loop = _situation_loop(fn)
    asked_in_loop = [call for call in ast.walk(loop) if isinstance(call, ast.Call)
                     and isinstance(call.func, ast.Attribute) and call.func.attr == "explaining"]
    assert not asked_in_loop, "the loop asks the covers again instead of reading what was decided against"
    [read] = _calls(fn, "_explained_situations")
    assert read.lineno < loop.lineno


# ── every no-card reason, counted, named and said — hermetic ─────────────────────────────────────

NOW = datetime(2026, 8, 20, tzinfo=timezone.utc)
FILE = "node_judged_file"
#: A review as the expert pass hands it over: checked (production never covers a file with an unchecked review).
CHECKED = SimpleNamespace(version="check.test")
PACK = {"pack_id": "admin", "version": "1.0.0", "revision": 1, "snapshot_id": "cfg_admin",
        "rule_ids": set(), "budget_per_day": 7}


class _Rows(list):
    def first(self):
        return self[0] if self else None

    def fetchall(self):
        return list(self)


class _Conn:
    """A read connection holding one home — or none — for the file."""

    def __init__(self, home=None):
        self.home = home
        self.rolled_back = 0

    def execute(self, statement, _params=None):
        if str(statement) == DS._FILES_HOME and self.home is not None:
            return _Rows([self.home])
        return _Rows()

    def rollback(self):
        self.rolled_back += 1


def _home(domain: str):
    return SimpleNamespace(anchor_node_id=FILE, situation_id="sit_home", domain=domain, node_type="company")


def _decide(monkeypatch, *, home, live_domains=frozenset(), pack=None, allowance=7):
    from genios_engine.reason.expert import decide as expert

    execution = SimpleNamespace(trace=SimpleNamespace(run_id="run_1"),
                                decision=SimpleNamespace(outcome=DecisionOutcome.DECISION))
    monkeypatch.setattr(expert, "request_for", lambda *_a, **_k: object())
    monkeypatch.setattr(expert, "decide", lambda _request: execution)
    monkeypatch.setattr(DS, "_tenant_pack", lambda *_a, **_k: pack)
    monkeypatch.setattr(DS, "_daily_allowance", lambda *_a, **_k: allowance)
    counts: Counter = Counter()
    no_card: dict[str, str] = {}
    review = SimpleNamespace(fingerprint="ffp-judged-file-review-000", checked=CHECKED, review=None)
    DS._decide_covered_files(
        store=None, conn=_Conn(home), org_id="org_s18u1", reviews={FILE: review}, stood_down={},
        gate=DS._CompiledGate(), counts=counts, eval_time=NOW, graph_version=1, live=False,
        live_domains=live_domains, registry=None, reasoning_store=None, packs={}, remaining=[None],
        no_card=no_card)
    return counts, no_card


@pytest.mark.unit
@pytest.mark.parametrize("reason, setup", [
    ("covered_without_situation", {"home": None}),
    ("expert_shadow", {"home": _home("general")}),                       # `general` is dark: no corpus
    ("expert_shadow", {"home": _home("admin")}),                         # a corpus the tenant has not switched on
    ("expert_no_tenant_pack", {"home": _home("admin"), "live_domains": frozenset({"admin"})}),
    ("budget_exhausted", {"home": _home("admin"), "live_domains": frozenset({"admin"}), "pack": PACK,
                          "allowance": 0}),
])
def test_a_judged_file_that_makes_no_card_is_counted_named_and_said(monkeypatch, caplog, reason, setup):
    with caplog.at_level(logging.WARNING, logger=DS.__name__):
        counts, no_card = _decide(monkeypatch, **setup)
    assert counts[reason] == 1, counts
    assert no_card == {FILE: reason}, "the file is named under the reason it made no card"
    said = [r for r in caplog.records if r.levelno == logging.WARNING and r.name == DS.__name__]
    assert len(said) == 1, [r.getMessage() for r in said]
    assert FILE in said[0].getMessage() and reason in said[0].getMessage(), said[0].getMessage()


@pytest.mark.unit
def test_a_file_whose_decision_failed_is_named_and_the_read_connection_is_rolled_back(monkeypatch, caplog):
    """A failed decision is a no-card reason too — and, decided before the loop now, its failed read must not poison
    the connection every situation after it reads on (`shadow_compile`'s own `finally: conn.rollback()` rule)."""
    from genios_engine.reason.expert import decide as expert

    def _boom(*_a, **_k):
        raise RuntimeError("the decision could not be built")
    monkeypatch.setattr(expert, "request_for", _boom)
    conn = _Conn(_home("general"))
    counts: Counter = Counter()
    no_card: dict[str, str] = {}
    review = SimpleNamespace(fingerprint="ffp-judged-file-review-000", checked=CHECKED, review=None)
    with caplog.at_level(logging.WARNING, logger=DS.__name__):
        DS._decide_covered_files(
            store=None, conn=conn, org_id="org_s18u1", reviews={FILE: review}, stood_down={},
            gate=DS._CompiledGate(), counts=counts, eval_time=NOW, graph_version=1, live=False,
            live_domains=frozenset(), registry=None, reasoning_store=None, packs={}, remaining=[None],
            no_card=no_card)
    assert counts["expert_error"] == 1 and no_card == {FILE: "expert_error"}, (counts, no_card)
    assert conn.rolled_back == 1


@pytest.mark.unit
def test_a_file_that_made_its_card_is_named_nowhere(monkeypatch, caplog):
    """⛔ THE NEGATIVE CONTROL: a file whose decision went out says nothing at WARNING and is no one's no-card."""
    from genios_engine.reason.expert import decide as expert

    monkeypatch.setattr(DS, "_persist_live", lambda **_k: "emitted")
    monkeypatch.setattr(DS, "_renews_its_decision", lambda *_a, **_k: False)
    monkeypatch.setattr(DS, "_retire_stood_down", lambda *_a, **_k: 0)
    from genios_engine.reason.expert import asks
    monkeypatch.setattr(asks, "retire_question", lambda *_a, **_k: False)
    monkeypatch.setattr(expert, "decision_ref", lambda *_a, **_k: "ref")
    with caplog.at_level(logging.WARNING, logger=DS.__name__):
        counts, no_card = _decide(monkeypatch, home=_home("admin"), live_domains=frozenset({"admin"}), pack=PACK)
    assert counts["expert_emitted"] == 1 and no_card == {}, (counts, no_card)
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING and r.name == DS.__name__]


# ── the day, end to end on Postgres ──────────────────────────────────────────────────────────────

#: Seven funds, each a formula situation the compiled lane decides and publishes on its own; and the one file a
#: valid review judged — Banyan Seed Fund, STEP-11's fund. Every fact is substring-backed.
FORMULA_FUNDS = (("Kabir", "Cedar One Fund", "cedarone.test"), ("Meera", "Teak Ventures", "teakventures.test"),
                 ("Rohan", "Peepal Capital", "peepalcapital.test"), ("Isha", "Neem Partners", "neempartners.test"),
                 ("Dev", "Sal Growth Fund", "salgrowth.test"), ("Tara", "Ashoka Seed", "ashokaseed.test"),
                 ("Vikram", "Deodar Fund", "deodarfund.test"))
JUDGED = ("Arjun", "Banyan Seed Fund", "banyanseed.test")
REVIEW_FP = "ffp-judged-banyan-review-00"


def _fund_mail(person: str, company: str, domain: str) -> tuple[str, dict]:
    content = (f"{person} at {company} asked for our latest deck and the metrics from last quarter "
               f"before the partner meeting.")
    read = {
        "relevance": 0.9, "noise_type": "none", "domains": ["fundraising"],
        "entity_mentions": [
            {"type": "person", "name": person, "email": f"{person.lower()}@{domain}",
             "evidence_text": f"{person} at {company}"},
            {"type": "company", "name": company, "email": None, "evidence_text": f"at {company}"}],
        "fact_candidates": [
            {"subject": person, "field": "thread.ball_in_court", "value": "us",
             "evidence_text": "asked for our latest deck"}],
        "commitments": [], "questions": [], "observations": [],
    }
    return content, read


def _busy_tenant(store, org: str):
    """A founder with eight funds' mail — seven for the formula, one the expert judged — and the Founder Office on."""
    from genios_engine.context import situations
    from genios_engine.packs.wiring import ensure_defaults
    from genios_engine.packs.wiring import make_registry
    from genios_engine.platform import company_brief
    from genios_engine.platform import l3_activation
    from tests.l1_supply import attach_l1_signals
    from tests.reason.test_a_programme_is_not_decided_as_an_investor import _mail
    from tests.test_admin_support_packs import _erase_tenant
    from tests.test_admin_support_packs import _seed_org

    _seed_org(store, org)
    _erase_tenant(store, org)
    with store.engine.begin() as conn:
        for table in ("situation_outcomes", "situation_admission_decisions", "signals", "company_brief_lines",
                      "expert_reviews", "reasoning_fingerprints"):
            conn.execute(text(f"delete from {table} where org_id = :o"), {"o": org})
    for person, company, domain in (*FORMULA_FUNDS, JUDGED):
        content, read = _fund_mail(person, company, domain)
        _mail(store, org, f"{org}_{domain}", content, f"{person.lower()}@{domain}", read)
    situations.refresh_situations(store, org, eval_time=NOW)
    assert attach_l1_signals(store, org, eval_time=NOW) > 0
    company_brief.invalidate(org)
    l3_activation.activate(store.engine, org, domain="founder_office", by="test",
                           notes="the founder's own work, as the pilot org (06 D2)")
    registry = make_registry(store.engine.url.render_as_string(hide_password=False))
    ensure_defaults(registry, org)
    return registry


def _judged_file(store, org: str) -> tuple[str, set[str]]:
    """The judged fund's file — the anchor its situations share — and every event behind them."""
    with store.engine.connect() as c:
        rows = c.execute(text(
            "select s.anchor_node_id, m.event_id from context_situations s "
            "  join graph_nodes n on n.org_id = s.org_id and n.node_id = s.anchor_node_id and n.valid_to is null "
            "  join context_correlation_members m on m.org_id = s.org_id and m.correlation_id = s.correlation_id "
            " where s.org_id = :o and s.status in ('active', 'partial') and n.canonical_key like :k"),
            {"o": org, "k": f"%{JUDGED[2]}"}).all()
    anchors = {r.anchor_node_id for r in rows}
    assert len(anchors) == 1, anchors
    return anchors.pop(), {r.event_id for r in rows}


#: The day's cap per seat the audit measured (`l2-daily-cap-formula-first`: the packs' default seven). The Founder
#: Office pack states fifteen; the fixture states seven, so seven formula situations fill the day exactly.
CAP_PER_DAY = 7


@pytest.fixture
def busy_day(pg_store, admitted, monkeypatch, request):
    org = f"g011s18u1_{request.node.name[5:32]}"
    registry = _busy_tenant(pg_store, org)
    monkeypatch.setattr(DS, "expert_catalog", lambda: admitted)
    tenant_pack = DS._tenant_pack

    def _seven_a_day(*args, **kwargs):
        # The pack's own figure, restated — `_daily_allowance` still subtracts the seats and what today published.
        pack = tenant_pack(*args, **kwargs)
        return {**pack, "budget_per_day": CAP_PER_DAY} if pack else pack
    monkeypatch.setattr(DS, "_tenant_pack", _seven_a_day)
    return pg_store, org, registry


def _compile(store, org, registry, *, covered):
    return DS.shadow_compile(store=store, org_id=org, eval_time=NOW, registry=registry, covered=covered,
                             live_domains=frozenset({"founder_office"}))


def _open(store, org, node, rule):
    with store.engine.connect() as c:
        return c.execute(text("select signal_id from signals where org_id = :o and subject_node_id = :n "
                              "   and rule_id = :r and status = 'open'"), {"o": org, "n": node, "r": rule}).all()


@pytest.mark.pg
def test_seven_formula_situations_fill_the_day_without_the_judged_file(busy_day):
    """⛔ THE PREMISE AND THE NEGATIVE CONTROL: with nothing covered, the day's cap is seven, and the eight funds'
    situations — the formula's seven and the judged fund's own — ask for more than it holds."""
    store, org, registry = busy_day
    counts = _compile(store, org, registry, covered=None)
    assert counts["budget_allowance"] == 7, counts
    assert counts.get("emitted") == 7 and counts.get("budget_exhausted", 0) >= 1, counts
    assert counts["covered_no_card"] == {}, "nothing covered, nothing named"


@pytest.mark.pg
def test_the_judged_file_has_its_card_on_a_day_seven_formula_situations_would_fill(busy_day):
    """THE DONE WHEN: seven formula situations ready to publish, a cap of seven, then one judged file — the judged
    file's card exists. The formula pays for it: one of the seven waits for tomorrow."""
    from genios_engine.deliver import pipeline
    from genios_engine.deliver.store import CardStore
    from tests.reason.expert.test_a_covered_file_decides_once import _write

    store, org, registry = busy_day
    anchor, events = _judged_file(store, org)
    _write(store, org, anchor, REVIEW_FP, events)
    counts = _compile(store, org, registry, covered={anchor: REVIEW_FP})
    assert counts["budget_allowance"] == 7 and counts["covered_situations"] >= 1, counts
    assert counts.get("expert_emitted") == 1, counts
    assert counts["covered_no_card"] == {}, counts["covered_no_card"]
    assert counts.get("emitted") == 6 and counts.get("budget_exhausted") == 1, \
        "the formula takes what the judged file left: six of its seven, one held for tomorrow"
    [(signal_id,)] = _open(store, org, anchor, "file_review")
    built = pipeline.build_cards_for_org(graph=store, card_store=CardStore(os.environ["GENIOS_TEST_DATABASE_URL"]),
                                         org_id=org, eval_time=NOW)
    with store.engine.connect() as c:
        card = c.execute(text("select card_id from cards where org_id = :o and signal_id = :s"),
                         {"o": org, "s": signal_id}).first()
    assert card is not None, ("the judged file has no card", built)


@pytest.mark.pg
def test_on_a_spent_day_the_judged_file_is_named_and_said(busy_day, caplog):
    """The cap already spent by publications earlier today: the judged file makes no card — and says so, by name, at
    WARNING, and on the pass's result."""
    from tests.reason.expert.test_a_covered_file_decides_once import _write
    from tests.reason.expert.test_a_renewal_is_never_capped import _spend_the_day

    store, org, registry = busy_day
    anchor, events = _judged_file(store, org)
    _write(store, org, anchor, REVIEW_FP, events)
    _spend_the_day(store, org, NOW)
    with caplog.at_level(logging.WARNING, logger=DS.__name__):
        counts = _compile(store, org, registry, covered={anchor: REVIEW_FP})
    assert counts["budget_allowance"] == 0 and counts["covered_no_card"] == {anchor: "budget_exhausted"}, counts
    assert any(anchor in r.getMessage() and "budget_exhausted" in r.getMessage()
               for r in caplog.records if r.levelno == logging.WARNING), "the file's lost card was never said"
