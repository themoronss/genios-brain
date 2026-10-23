"""GeniOS-012 U12-03 · a judged file is always decided, whatever the compile flags say.

    PYTHONPATH=. pytest -q tests/reason/test_a_judged_file_is_decided_without_compile_flags.py

`reason/runner.run_all` entered `shadow_compile` — where `_decide_covered_files` turns a judged ("covered") file
into its decision — only when `use_domain_compiler` was set, or the tenant had an activated Layer 3 domain, or an
`l1_semantic_activation` row. A tenant with none of the three had its files judged by the expert (and paid for)
and never decided: no card, and no count saying why (GeniOS-012 D28). A covered file now enters the pass on its
own; with no live domain it is decided in shadow, which the pass counts (`expert_shadow`), never silently.
"""
from __future__ import annotations

from datetime import datetime
from datetime import timezone
from types import SimpleNamespace

from genios_engine.reason import runner

NOW = datetime(2026, 10, 23, 9, 0, tzinfo=timezone.utc)


class _Rows:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, *a, **k):
        return iter(())


def _sweep(monkeypatch, *, expert):
    """`run_all` for a tenant with NO compile flag: no global flag, no activated domain, no Layer 1 row."""
    from genios_engine.platform import l3_activation
    from genios_engine.reason import bundle
    from genios_engine.reason import domain_shadow
    from genios_engine.reason.expert import sweep as expert_sweep
    from genios_engine.reason.l2 import sweep as l2_sweep
    calls: list[dict] = []

    def _compile(**kw):
        calls.append(kw)
        return {"covered_no_card": {node: "expert_shadow" for node in kw.get("covered") or {}}}
    monkeypatch.setattr(expert_sweep, "expert_pass", lambda **kw: expert)
    monkeypatch.setattr(l2_sweep, "l2_pass", lambda **kw: {"skipped": "l2_reasoning_not_activated"})
    monkeypatch.setattr(domain_shadow, "shadow_compile", _compile)
    monkeypatch.setattr(runner, "ensure_defaults", lambda registry, org_id: None)
    monkeypatch.setattr(runner, "l1_seam_enabled", lambda engine, org_id: False)
    monkeypatch.setattr(l3_activation, "activated_domains", lambda engine, org_id: frozenset())
    monkeypatch.setattr(bundle, "narrate_published", lambda **kw: {})
    assert runner.get_settings().use_domain_compiler is False, "the test needs the global flag off"
    store = SimpleNamespace(engine=SimpleNamespace(connect=_Rows))
    result = runner.run_all(org_id="org_u12_03", store=store, eval_time=NOW, registry=object())
    return calls, result


def test_a_covered_file_enters_the_pass_with_no_compile_flag(monkeypatch):
    review = {"valid": True}
    calls, result = _sweep(monkeypatch, expert={"covered": {"node_a": review}, "people": {}})
    assert len(calls) == 1, "the judged file was never handed to the pass that decides it"
    assert calls[0]["covered"] == {"node_a": review}
    assert calls[0]["live"] is False and not calls[0]["live_domains"], "no live domain: decided in shadow"
    assert result["why_no_card_files"] == {"node_a": "expert_shadow"}, "and the reason is counted"


def test_with_nothing_judged_and_no_flag_the_pass_still_does_not_run(monkeypatch):
    """Unchanged for every other tenant: no flag and nothing covered, no compiled pass."""
    calls, _result = _sweep(monkeypatch, expert={"covered": {}, "people": {}})
    assert calls == []
