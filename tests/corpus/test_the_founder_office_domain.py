"""STEP-11 · the Founder Office is a corpus of its own — authored, activatable per tenant, off by default.

    .venv/bin/python -m pytest tests/corpus/test_the_founder_office_domain.py -q

Tree `yc2_w27_s11 · M30.C1.L-contract.V0.U01`, `06` D2. The founder's work — raising, programmes,
introductions, compliance, hiring and the meetings they turn on — is neither Admin nor Sales, and
investor relations sat in Sales only because a compiled signal could carry authority in no other
lane. `packs/wiring._corpus_packs` now gives every authored corpus its own lane with no engine code
(STEP-11 §8.2), so the domain is a folder: `Domain Expertise/Founder Office Expertise/`. It is OFF for
a tenant nobody configured and switched on for the pilot org only; every capability it declares either
routes or names why it does not (its `deferrals.yaml`).
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2] / "Domain Expertise" / "Founder Office Expertise"

#: The six kinds of founder work, in the order a raise usually needs them (STEP-11 §3.2).
CAPABILITIES = ("investor_relations", "program_applications", "introductions",
                "registrations_and_recognition", "offers_and_joining", "external_meetings")


def _domain() -> dict:
    return yaml.safe_load((ROOT / "domain.yaml").read_text())


def test_the_corpus_is_authored_and_named_founder_office():
    from genios_engine.platform.corpus import authored_domain_ids
    assert _domain()["identity"]["id"] == "founder_office"
    assert "founder_office" in authored_domain_ids()


def test_it_is_off_for_a_tenant_nobody_configured():
    from genios_engine.platform.corpus import default_on_domains
    assert _domain()["activation"]["default_on"] is False
    assert "founder_office" not in default_on_domains()


def test_a_tenant_can_switch_it_on():
    from genios_engine.platform.l3_activation import L3_DOMAINS, require_domain
    assert "founder_office" in L3_DOMAINS
    assert require_domain("founder_office") == "founder_office"


def test_its_card_lane_needs_no_engine_code():
    """The synthesised pack: an authority lane, and nothing else — no rules, no plays, no fields the
    extractor would be told to go and find."""
    from genios_engine.packs.wiring import _corpus_packs
    [pack] = [p for p in _corpus_packs() if p["id"] == "founder_office"]
    assert (pack["rules"], pack["plays"], pack["schema"]) == ([], {}, {"fields": []})
    assert pack["version"] == _domain()["identity"]["version"]


def test_it_declares_the_six_kinds_of_founder_work():
    declared = [c for s in _domain()["subdomains"] for c in s["capabilities"]]
    assert tuple(declared) == CAPABILITIES


def test_every_capability_routes_or_says_why_not():
    deferred = {d["capability"]: d for d in
                yaml.safe_load((ROOT / "deferrals.yaml").read_text())["deferred"]}
    registry = yaml.safe_load((ROOT / "registry" / "situation-capability-map.yaml").read_text())
    routed = {c for entry in (registry.get("map") or {}).values()
              for c in entry.get("capabilities", ())}
    for cap in Path(ROOT / "capabilities").glob("*/*/capability.yaml"):
        cid = yaml.safe_load(cap.read_text())["identity"]["id"]
        assert cid in routed or (cid in deferred and deferred[cid]["reason"].strip()), cid


def test_its_core_objects_are_on_its_roster_and_authored():
    """The roster and the folder agree both ways (`validate.py` warns on either drift)."""
    rostered = {name for names in (_domain().get("core_objects") or {}).values() for name in names}
    authored = {yaml.safe_load(p.read_text())["identity"]["id"].rsplit(".", 1)[1]
                for p in (ROOT / "objects" / "core").glob("*.yaml")}
    assert rostered == authored == {"company", "contact", "next_action", "risk"}
