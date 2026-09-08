"""R-1/R-3/R-4 through the ONE gate — the delegation, the cache, and the shared vocabulary.

`reason/bundle/gate.RSiteGate` is C5 and it has its own tests. What is pinned HERE is that these
three sites go through it rather than around it, and the two things the gate deliberately leaves to
this module: the per-site generation cache (migration 0121) and the refusal shape.

THE FAILURE THIS FILE EXISTS TO CATCH is a second gate. Two gates means two activation reads, two
budgets over one ledger and two force-fail switches — so K4's doctrine replay could pass while these
sites went on calling a model. Several cases below assert exactly that: the SHIPPED switch turns
these sites off, the SHIPPED ledger receipts them, the SHIPPED budget refuses them.
"""

from __future__ import annotations

import os

import pytest
from sqlalchemy import text

from genios_engine.platform import l4_activation as ACT
from genios_engine.reason import llm_sites as S
from genios_engine.reason.bundle import budget as B
from genios_engine.reason.bundle import gate as G
from genios_engine.reason.bundle import sites as V

ORG = "org_scratch_tests"                       # seeded by tests/conftest.py; satisfies the FK


class Client:
    model = "claude-sonnet-5"

    def __init__(self, payload=None, ok=True):
        self.payload = payload if payload is not None else {"text": "fine"}
        self.ok = ok
        self.calls = 0
        self.prompts: list[str] = []

    def call(self, prompt, *, max_tokens=400):
        from genios_engine.context.llm.client import LLMResult
        self.calls += 1
        self.prompts.append(prompt)
        return LLMResult(parsed=self.payload, raw="", ok=self.ok, model=self.model,
                         input_tokens=1000, output_tokens=250,
                         error=None if self.ok else "boom")


def gate(client=None, *, engine=None, activated=frozenset({"bundle"}), budget=None):
    return S.make_gate(org_id=ORG, engine=engine, client=client, activated=activated) if budget \
        is None else G.RSiteGate(org_id=ORG, engine=engine, client=client,
                                 activated=activated, budget=budget)


def run(**kwargs):
    defaults = dict(site=S.SITE_R3, org_id=ORG, seed={"k": 1}, precondition=True,
                    build_prompt=lambda feedback: S.with_correction("prompt", feedback),
                    parse=lambda payload: dict(payload),
                    fallback=lambda: {"text": "template"})
    defaults.update(kwargs)
    return S.run_site(**defaults)


def _engine():
    url = os.environ.get("GENIOS_TEST_DATABASE_URL")
    if not url:
        pytest.skip("GENIOS_TEST_DATABASE_URL not set — the R-site ledger is not exercised")
    from genios_engine.platform.db import get_engine
    return get_engine(url)


@pytest.fixture
def engine():
    eng = _engine()
    _clean(eng)
    yield eng
    _clean(eng)


def _clean(eng) -> None:
    with eng.begin() as c:
        c.execute(text("delete from l4_r_site_calls where org_id = :o"), {"o": ORG})
        c.execute(text("delete from l4_r_site_generations where org_id = :o"), {"o": ORG})
        c.execute(text("delete from l4_activation where org_id = :o"), {"o": ORG})


def rows(eng):
    with eng.connect() as c:
        return [dict(row._mapping) for row in c.execute(text(
            "select site, outcome, tier, model, cost_micro_usd, attempts, reason_codes "
            "from l4_r_site_calls where org_id = :o order by id"), {"o": ORG})]


# ── one vocabulary, one gate ─────────────────────────────────────────────────────────────────

def test_the_site_ids_are_the_shared_ones_and_not_a_second_spelling():
    assert (S.SITE_R1, S.SITE_R3, S.SITE_R4) == (V.SITE_INTERPRET, V.SITE_ALTERNATIVES,
                                                 V.SITE_EFFECT)
    assert set(S.SITES) <= set(V.R_SITES)
    assert S.OUTCOMES is V.OUTCOMES and S.FALLBACK_OUTCOMES is V.FALLBACK_OUTCOMES


def test_the_tiers_are_the_shared_table_and_not_a_call_site_decision():
    assert (V.tier_for(S.SITE_R1), V.tier_for(S.SITE_R3), V.tier_for(S.SITE_R4)) == (
        "T2", "T1", "T1")


def test_an_unknown_site_is_refused_rather_than_run():
    with pytest.raises(ValueError):
        run(site="R-9", gate=gate(Client()))


def test_no_gate_is_answered_as_no_model_and_never_as_permission():
    result = run(gate=None)
    assert result.receipt.outcome == V.OUTCOME_NO_CLIENT
    assert result.payload == {"text": "template"}


# ── the steps the gate owns, exercised THROUGH this module ───────────────────────────────────

def test_a_tenant_that_is_not_activated_buys_nothing():
    client = Client()
    result = run(gate=gate(client, activated=frozenset()))
    assert result.receipt.outcome == V.OUTCOME_NOT_ACTIVATED
    assert client.calls == 0 and result.payload == {"text": "template"}


def test_a_site_with_no_precondition_never_composes_a_prompt():
    composed: list[int] = []
    client = Client()
    result = run(precondition=False, gate=gate(client),
                 build_prompt=lambda feedback: composed.append(1) or "prompt")
    assert result.receipt.outcome == V.OUTCOME_NO_PRECONDITION
    assert composed == [] and client.calls == 0


def test_the_shipped_force_fail_switch_turns_these_sites_off_too():
    """The doctrine switch is ONE switch. A site with a private one could keep calling a model
    through the very replay that is supposed to prove it cannot."""
    client = Client()
    with G.force_failed():
        result = run(gate=gate(client))
    assert result.receipt.outcome == V.OUTCOME_FORCE_FAILED
    assert client.calls == 0 and result.payload == {"text": "template"}


def test_a_rejected_generation_is_retried_exactly_once_and_never_a_third_time():
    client = Client()

    def refuse(payload):
        raise S.SiteRejection("bare_number", "84,000")

    result = run(gate=gate(client), parse=refuse)
    assert client.calls == G.MAX_ATTEMPTS == 2
    assert result.receipt.outcome == V.OUTCOME_FAILED_VALIDATION
    assert result.receipt.reason_codes == ("bare_number",)


def test_the_retry_is_told_the_rule_it_broke_and_never_the_answer():
    """A rejection that says only "invalid" buys a re-roll; one that names the rule buys a
    correction. What it must not do is supply content."""
    client = Client()

    def refuse(payload):
        raise S.SiteRejection("bare_number", "84,000")

    run(gate=gate(client), parse=refuse)
    assert len(client.prompts) == 2
    assert "digit" in client.prompts[1] and "84,000" not in client.prompts[1]


def test_a_transport_failure_and_a_refusal_are_different_facts():
    assert run(gate=gate(Client(ok=False))).receipt.outcome == V.OUTCOME_FAILED_GENERATION


def test_the_spend_is_priced_by_the_shared_cost_model():
    client = Client()

    def refuse(payload):
        raise S.SiteRejection("nope")

    result = run(gate=gate(client), parse=refuse)
    one = B.cost_micro_usd(tier=V.tier_for(S.SITE_R3), input_tokens=1000, output_tokens=250)
    assert result.receipt.cost_micro_usd == 2 * one > 0


def test_a_spent_day_degrades_to_the_template_and_never_blocks_a_card():
    spent = B.NarrativeBudget(org_id=ORG, daily_cap_micro_usd=1, per_call_cap_micro_usd=1)
    client = Client()
    result = run(gate=gate(client, budget=spent))
    assert result.receipt.outcome == V.OUTCOME_NO_BUDGET
    assert client.calls == 0 and result.payload == {"text": "template"}


# ── the half this module owns: the per-site cache ────────────────────────────────────────────

def test_a_cache_hit_costs_no_call_and_reports_the_generation_that_produced_it():
    cache = S.InMemorySiteCache()
    client = Client({"text": "generated"})
    site_gate = gate(client)
    first = run(gate=site_gate, cache=cache)
    second = run(gate=site_gate, cache=cache)
    assert first.receipt.outcome == V.OUTCOME_RAN
    assert second.receipt.outcome == V.OUTCOME_CACHED
    assert client.calls == 1
    assert second.generation == first.generation != "template_fallback"
    assert second.payload == {"text": "generated"}


def test_the_cache_key_covers_the_prompt_version_so_an_edit_cannot_serve_stale_prose():
    first = S.cache_key(site=S.SITE_R3, org_id=ORG, seed={"k": 1})
    original = S.PROMPT_VERSION
    try:
        S.PROMPT_VERSION = "l4-r-sites.v2"
        assert S.cache_key(site=S.SITE_R3, org_id=ORG, seed={"k": 1}) != first
    finally:
        S.PROMPT_VERSION = original


def test_two_sites_reading_one_decision_never_collide():
    seed = {"decision_hash": "dh_1"}
    assert (S.cache_key(site=S.SITE_R3, org_id=ORG, seed=seed)
            != S.cache_key(site=S.SITE_R4, org_id=ORG, seed=seed))


def test_a_rejected_generation_is_never_cached():
    cache = S.InMemorySiteCache()

    def refuse(payload):
        raise S.SiteRejection("bad_shape")

    run(gate=gate(Client()), cache=cache, parse=refuse)
    assert cache.get(ORG, S.SITE_R3, S.cache_key(site=S.SITE_R3, org_id=ORG, seed={"k": 1})) is None


# ── on real Postgres: the shared ledger, the shared switch ───────────────────────────────────

def test_every_outcome_including_every_skip_lands_in_the_shared_ledger(engine):
    run(gate=gate(Client(), engine=engine))                       # ran
    run(gate=gate(None, engine=engine))                           # skipped_no_client
    run(precondition=False, gate=gate(Client(), engine=engine))   # skipped_precondition
    recorded = [row["outcome"] for row in rows(engine)]
    assert recorded == [V.OUTCOME_RAN, V.OUTCOME_NO_CLIENT, V.OUTCOME_NO_PRECONDITION]
    assert all(row["tier"] == "T1" for row in rows(engine))


def test_the_activation_read_is_the_real_one_when_no_set_is_supplied(engine):
    """`make_gate` with no `activated` reads `l4_activation` — fail-closed, per feature."""
    client = Client()
    assert S.run_site(site=S.SITE_R3, org_id=ORG, seed={"k": 2}, precondition=True,
                      build_prompt=lambda feedback: "p",
                      parse=lambda payload: dict(payload),
                      fallback=lambda: {"text": "t"},
                      gate=S.make_gate(org_id=ORG, engine=engine, client=client),
                      ).receipt.outcome == V.OUTCOME_NOT_ACTIVATED

    ACT.activate(engine, ORG, feature=ACT.FEATURE_BUNDLE, by="tests")
    assert S.run_site(site=S.SITE_R3, org_id=ORG, seed={"k": 2}, precondition=True,
                      build_prompt=lambda feedback: "p",
                      parse=lambda payload: dict(payload),
                      fallback=lambda: {"text": "t"},
                      gate=S.make_gate(org_id=ORG, engine=engine, client=client),
                      ).receipt.outcome == V.OUTCOME_RAN


def test_the_durable_cache_survives_the_process_that_wrote_it(engine):
    client = Client({"text": "generated once"})
    site_gate = gate(client, engine=engine)
    first = run(gate=site_gate, cache=S.PostgresSiteCache(engine=engine))
    second = run(gate=site_gate, cache=S.PostgresSiteCache(engine=engine))
    assert client.calls == 1
    assert second.receipt.outcome == V.OUTCOME_CACHED
    assert second.payload == {"text": "generated once"}
    assert second.generation == first.generation


def test_the_durable_cache_stores_only_what_a_parser_accepted(engine):
    def refuse(payload):
        raise S.SiteRejection("bad_shape")

    run(gate=gate(Client(), engine=engine), cache=S.PostgresSiteCache(engine=engine),
        parse=refuse)
    with engine.connect() as c:
        assert c.execute(text("select count(*) from l4_r_site_generations where org_id = :o"),
                         {"o": ORG}).scalar() == 0


def test_an_unreadable_cache_is_an_empty_cache_and_never_a_failed_card():
    class Broken:
        def connect(self):
            raise RuntimeError("down")

        def begin(self):
            raise RuntimeError("down")

    cache = S.PostgresSiteCache(engine=Broken())
    result = run(gate=gate(Client()), cache=cache)
    assert result.receipt.outcome == V.OUTCOME_RAN
