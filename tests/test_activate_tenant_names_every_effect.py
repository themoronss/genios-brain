"""`03` F135 · `scripts/activate_tenant.py` names the effect of every switch it lists.

    pytest tests/test_activate_tenant_names_every_effect.py -q

`yc2_w27_s18` M49.C2.L-interface.V0.U06 (scripts), STEP-18 §8.3 s18-F12.

⛔ WHAT WAS WRONG. The dry run an operator reads before `--apply` lists EVERY Layer 3 domain and EVERY
Layer 4 feature (`_state`), and printed each one's effect from the script's own `EFFECT` table — which
had no `founder_office` line (`03` F135) and none for four Layer 4 features either (`situation_reasoner`,
`cards_from_situations`, `calibration_apply`, `expert_review`): blank, on the one column read before a
switch is flipped. `calibration_apply` is the switch that arms unattended muting (`06` D13). A Layer 3
domain's effect is now `platform/l3_activation.EFFECTS`'s own line; a Layer 4 feature's is the script's
operator wording where it has one (`SPENDS` is said there), else `platform/l4_activation.EFFECTS`'s.
"""
from __future__ import annotations

import pytest

from genios_engine.platform.l3_activation import EFFECTS as L3_EFFECTS
from genios_engine.platform.l3_activation import L3_DOMAINS
from genios_engine.platform.l4_activation import EFFECTS as L4_EFFECTS
from genios_engine.platform.l4_activation import L4_FEATURES
from scripts import activate_tenant as script

LISTED = ([("L1", "semantic"), ("L2", "analytic"), ("L2", "patterns")]
          + [("L3", d) for d in L3_DOMAINS] + [("L4", f) for f in L4_FEATURES])


@pytest.mark.parametrize("layer, name", LISTED, ids=lambda v: str(v))
def test_every_switch_the_dry_run_lists_says_what_it_does(layer, name):
    assert script.effect_of(layer, name).strip(), f"{layer} {name} is listed with a blank effect"


def test_the_founder_office_says_what_it_turns_on():
    assert "founder_office" in L3_DOMAINS
    assert script.effect_of("L3", "founder_office") == L3_EFFECTS["founder_office"]


@pytest.mark.parametrize("domain", L3_DOMAINS)
def test_a_layer_three_line_is_the_layer_s_own(domain):
    """One spelling: the script keeps no Layer 3 line of its own to drift from the module's."""
    assert script.effect_of("L3", domain) == L3_EFFECTS[domain]
    assert ("L3", domain) not in script.EFFECT


def test_the_switch_that_arms_muting_says_so():
    assert script.effect_of("L4", "calibration_apply") == L4_EFFECTS["calibration_apply"]


def test_the_operator_wording_wins_where_the_script_has_it():
    assert "SPENDS" in script.effect_of("L4", "bundle")
    assert script.effect_of("L4", "bundle") == script.EFFECT[("L4", "bundle")]


def test_an_unknown_switch_has_no_effect_to_name():
    assert script.effect_of("L4", "no_such_feature") == ""
    assert script.effect_of("L9", "anything") == ""


# ── the two lines an operator reads: the status listing and the dry run's plan ────────────────
# The PG fixture and runner of `tests/test_activate_tenant.py`, imported so both files seed one way.
from tests.test_activate_tenant import _run, pg_url, tenant  # noqa: E402,F401 — pytest fixtures


def _line(out: str, layer: str, name: str) -> str:
    return next(line for line in out.splitlines() if f"{layer} {name} " in line)


def test_the_status_listing_names_the_founder_office_and_the_muting_switch(tenant, capsys):
    _engine, url = tenant
    assert _run(url, "--status") == 0
    out = capsys.readouterr().out
    assert L3_EFFECTS["founder_office"] in _line(out, "L3", "founder_office")
    assert L4_EFFECTS["calibration_apply"] in _line(out, "L4", "calibration_apply")


def test_the_dry_runs_plan_names_what_it_would_flip(tenant, capsys):
    _engine, url = tenant
    assert _run(url, "--domains", "founder_office") == 0
    plan = capsys.readouterr().out.split("WOULD FLIP", 1)[1]
    assert L3_EFFECTS["founder_office"] in _line(plan, "L3", "founder_office")
