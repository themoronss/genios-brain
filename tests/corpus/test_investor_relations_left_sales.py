"""STEP-11 · investor relations left Sales — one copy of the doctrine, in the Founder Office.

    .venv/bin/python -m pytest tests/corpus/test_investor_relations_left_sales.py -q

Tree `yc2_w27_s11 · M30.C6.L-data.V2.U03`, `06` D2. Sales' `10-investor-relations` sat in the Sales
corpus "for an authority reason, not a taxonomic one" — its own note — and said that "if a fundraising
pack ever ships, this subdomain moves out whole". It moved (M30.C6.L-data.V1.U01), the L2 map followed
(M30.C1.L-logic.V1.U02), and the Sales copy is retired: its capability, two situations, playbook, two
heuristics and object deleted, its subdomain gone from the Sales roster, its routes gone from the Sales
registry. Two copies of one doctrine is how one of them goes stale.
"""
from __future__ import annotations

from pathlib import Path

import yaml

CORPUS = Path(__file__).resolve().parents[2] / "Domain Expertise"
SALES = CORPUS / "Sales Expertise"
RETIRED = ("sales.investor_relations.investor_relations", "sales.sit.live_investor_relationship",
           "sales.sit.live_investor_contact", "sales.pb.investor_relations.reopen_after_a_pass",
           "sales.heu.investor_relations.investors_do_not_chase",
           "sales.heu.investor_relations.a_pass_is_a_date_not_a_verdict",
           "sales.obj.investor_relations.investor_conversation")


def test_no_sales_file_defines_a_retired_id():
    defined = {}
    for path in SALES.rglob("*.yaml"):
        doc = yaml.safe_load(path.read_text()) or {}
        ident = doc.get("identity") if isinstance(doc, dict) else None
        if isinstance(ident, dict) and ident.get("id") in RETIRED:
            defined[ident["id"]] = str(path.relative_to(CORPUS))
    assert defined == {}


def test_the_sales_folders_are_gone():
    for rel in ("capabilities/10-investor-relations", "playbooks/investor_relations",
                "heuristics/investor_relations", "objects/investor-relations"):
        assert not (SALES / rel).exists(), rel


def test_the_sales_roster_and_registry_no_longer_name_it():
    domain = yaml.safe_load((SALES / "domain.yaml").read_text())
    assert "investor_relations" not in {s["id"] for s in domain["subdomains"]}
    registry = yaml.safe_load((SALES / "registry/situation-capability-map.yaml").read_text())
    for situation_type in ("investor_relationship", "investor_contact"):
        route = (registry.get("map") or {}).get(situation_type) or {}
        assert not any("investor" in str(s) for s in route.get("situations") or ()), situation_type


def test_the_doctrine_lives_on_in_the_founder_office():
    from genios_engine.packs.compiler.authoring import ExpertBrainCatalog, default_authoring_root
    catalog = ExpertBrainCatalog(default_authoring_root())
    founder = catalog.domains["founder_office"]
    assert "founder_office.fundraising.investor_relations" in founder.capabilities
    assert {"founder_office.sit.live_investor_relationship",
            "founder_office.sit.live_investor_contact"} <= set(founder.situations)
    assert not [cid for cid in catalog.domains["sales"].capabilities if "investor" in cid]


def test_the_corpus_still_validates():
    import subprocess
    import sys
    tool = CORPUS / "_tools" / "validate.py"
    result = subprocess.run([sys.executable, str(tool)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout[-2000:]
