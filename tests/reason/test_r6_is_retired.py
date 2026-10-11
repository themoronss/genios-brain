"""STEP-12 · R-6 is retired — no consult, no row per situation per pass, and its switch turns nothing on.

    GENIOS_TEST_DATABASE_URL=postgresql+psycopg://… pytest tests/reason/test_r6_is_retired.py -q

Tree `yc2_w27_s12` M32.C4.L-logic.V0.U02, `06` D51 (answered 10 Oct: yes), `03` F141. The Context Reasoner
(R-6) ran for every compiled situation — shadow ones included — AHEAD of STEP-02's change gate, built a
gate and a model client every sweep, and wrote a `situation_interpretations` row per situation per pass:
an empty proposal on every tenant, because its feature was off everywhere. It never ran in production,
and the expert pass reviews the FILE instead. So the sweep no longer builds it, consults it or records
it; its feature stays NAMED — a row written before still reads — and is never live: switching it on is
refused, and a row that exists anyway turns nothing on. The module and its own tests stay until a
clean-up deletes them together.
"""
from __future__ import annotations

import ast
import inspect
import textwrap

import pytest
from sqlalchemy import text

from genios_engine.platform import intelligence_onboarding as ONB
from genios_engine.platform import l4_activation as ACT
from genios_engine.reason import cutover, domain_shadow


def _shadow_compile() -> ast.FunctionDef:
    return ast.parse(textwrap.dedent(inspect.getsource(domain_shadow.shadow_compile))).body[0]


def _called(fn: ast.AST) -> set[str]:
    names = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            f = node.func
            names.add(f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute)
                      else "")
    return names


def test_the_sweep_consults_r6_no_more_by_the_ast():
    called = _called(_shadow_compile())
    assert not {"reason_over_situation", "record_interpretation", "make_gate",
                "make_site_client"} & called, sorted(called)
    module = ast.parse(inspect.getsource(domain_shadow))
    imported = {node.module for node in ast.walk(module) if isinstance(node, ast.ImportFrom)}
    assert not {"genios_engine.reason.situation_reasoner",
                "genios_engine.context.interpretation_store"} & imported


def test_its_switch_is_named_retired_and_refused():
    feature = ACT.FEATURE_SITUATION_REASONER
    assert feature in ACT.L4_FEATURES                      # a row written before still reads
    assert "D51" in ACT.RETIRED_FEATURES[feature] and ACT.EFFECTS[feature].startswith("RETIRED")
    with pytest.raises(ValueError, match="retired"):
        ACT.activate(None, "org_any", feature=feature, by="test")
    assert ACT.is_l4_activated(None, "org_any", feature) is False
    assert "RETIRED" in ONB.NOT_DEFAULT_ON[feature] and feature not in ONB.L4_DEFAULT_FEATURES


def test_no_cutover_is_left_for_it():
    assert "situation_reasoner" not in cutover.SWITCHES
    assert "situation_reasoner" not in cutover.CUTOVER_ORDER
    assert "reasoner_failed" not in {rule.reading for rule in cutover.PARITY_GATE.values()}


@pytest.mark.pg
def test_a_row_that_exists_anyway_turns_nothing_on(pg_store, monkeypatch):
    """The admin pilot tenant, with R-6's feature row written straight into the table (what a row
    from before looks like) and a model client that records every prompt: the sweep asks R-6
    nothing and writes no interpretation, and the reads say the feature is off."""
    from genios_engine.reason import llm_sites
    from tests.reason.adapters.l3_pilot_seed import seed_admin_pilot
    from tests.test_admin_support_packs import _seed_org

    prompts: list[str] = []

    class _Client:
        model = "claude-haiku-4-5"

        def call(self, prompt, *, max_tokens=400):
            from genios_engine.context.llm.client import LLMResult
            prompts.append(prompt)
            return LLMResult(parsed={}, raw="{}", ok=True, model=self.model, input_tokens=10,
                             output_tokens=2)

    monkeypatch.setattr(llm_sites, "make_site_client", lambda tier: _Client())
    org = "org_s12_r6_retired"
    _seed_org(pg_store, org)
    with pg_store.engine.begin() as c:
        c.execute(text("delete from situation_interpretations where org_id = :o"), {"o": org})
        c.execute(text("delete from l4_activation where org_id = :o"), {"o": org})
        c.execute(text("insert into l4_activation (org_id, feature, enabled_by) "
                       "values (:o, 'situation_reasoner', 'a row from before')"), {"o": org})
    try:
        counts = seed_admin_pilot(pg_store, org, build_cards=False)
        assert counts["compile"]["compiled"] >= 1, counts            # the sweep did run
        with pg_store.engine.connect() as c:
            rows = c.execute(text("select count(*) from situation_interpretations "
                                  "where org_id = :o"), {"o": org}).scalar()
        assert rows == 0, "the sweep still records an R-6 interpretation per situation"
        assert not [p for p in prompts if p.startswith("You are reading ONE business situation")]
        assert ACT.FEATURE_SITUATION_REASONER not in ACT.activated_features(pg_store.engine, org)
        assert ACT.is_l4_activated(pg_store.engine, org, ACT.FEATURE_SITUATION_REASONER) is False
    finally:
        with pg_store.engine.begin() as c:
            c.execute(text("delete from l4_activation where org_id = :o"), {"o": org})
