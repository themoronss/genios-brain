"""M8.C1.L-contract.V1.U07 — an authored vertical reaches the compiler as a variant.

    pytest tests/packs/test_a_vertical_is_loaded.py -q

NOBODY HAD EVER PROVEN THIS. The corpus has carried a `models/` tree for a long time — 88
authored branch nodes on 2026-09-15, 20 admin, 33 sales, 35 support — and ZERO verticals. Selection
is `l3_activation.variant_ids`, and that column reads `[]` on every activation row of every
tenant. So the loader, the inheritance rule and the selection path had never once carried a
document to a compile, and a defect anywhere along it would have looked exactly like the silence
it already produced.

This file walks the path with a real authored document: `authoring.py` files it as a `variant`,
its parent resolves, and the branch declares what it declares. It is the same class of check the
Layer 2 lane audit applies — a mechanism that produces nothing is indistinguishable from one that
is broken until something makes it produce.
"""
from __future__ import annotations

import pathlib

import pytest
import yaml

pytestmark = pytest.mark.unit

ROOT = pathlib.Path("Domain Expertise")
VERTICAL = ROOT / "Admin Expertise/verticals/early_stage_ai_product/vertical.yaml"


@pytest.fixture(scope="module")
def doc():
    return yaml.safe_load(VERTICAL.read_text())


def test_the_vertical_exists_and_is_a_vertical(doc) -> None:
    """`kind` separates the two axes the tree carries: a MODEL is how the motion runs (b2b, plg,
    tiered) and a VERTICAL is what kind of company runs it. Mislabelling one as the other puts it
    in the wrong inheritance chain."""
    assert doc["identity"]["kind"] == "vertical"
    assert doc["identity"]["domain"] == "admin"


def test_it_names_a_parent_that_resolves(doc) -> None:
    """Resolution is vertical -> model -> canonical, and the schema requires a parent on a
    vertical for exactly that reason. A parent that does not resolve breaks the chain silently:
    the branch loads, inherits nothing, and looks like a thin document rather than a broken one."""
    parent = doc["identity"]["parent"]
    assert parent, "a vertical with no parent inherits nothing"
    found = [p for p in ROOT.rglob("models/**/*.yaml")
             if (yaml.safe_load(p.read_text()) or {}).get("identity", {}).get("id") == parent]
    assert found, f"parent {parent!r} resolves to no authored model"


def test_the_corpus_loader_files_it_as_a_variant() -> None:
    """THE STEP 88 MODELS NEVER HAD PROVEN. `authoring.py` classifies `model.yaml`,
    `vertical.yaml` and `offering.yaml` as `variant`; everything downstream — the retriever, the
    brain resolver, the expertise builder — addresses them by that kind."""
    from genios_engine.packs.compiler.authoring import ExpertBrainCatalog

    catalog = ExpertBrainCatalog(ROOT)          # loads every domain in __init__
    record = catalog.domains["admin"]
    variants = dict(record.variants)
    assert variants, "the admin domain loaded no variants at all"
    assert "admin.model.early_stage_ai_product" in variants, (
        f"the authored vertical was not loaded as a variant; loaded ids: "
        f"{sorted(variants)[:6]}")
    # …and it arrives as a document the rest of the compiler can address, not a bare dict.
    document = variants["admin.model.early_stage_ai_product"]
    assert getattr(document, "kind", None) == "variant", (
        f"loaded under kind {getattr(document, 'kind', None)!r}, so the retriever will not see it")


def test_it_declares_what_this_branch_requires(doc) -> None:
    """`require_properties` is the corpus's own words for "canonical properties that become
    mandatory in this branch" — which is what an expectation IS. The overlay onto Layer 2's
    `expected_fields` reads this, so a vertical that declares none changes nothing about coverage.
    """
    extends = (doc.get("objects") or {}).get("extends") or []
    assert extends, "the branch extends no object, so it declares no expectation"
    required = {r for e in extends for r in (e.get("require_properties") or ())}
    assert required, "no property is made mandatory in this branch"


def test_it_declares_what_this_branch_must_not_load(doc) -> None:
    """The other half, and the one that answers "too much unwanted data". An object that is
    genuinely absent at this stage produces a card whose every field is missing, which reads as a
    gap in the data rather than as a stage of company."""
    never = (doc.get("objects") or {}).get("never_load") or []
    assert never, "the branch filters nothing"


def test_it_cannot_reach_a_live_card_until_a_human_accepts_it(doc) -> None:
    """THE ADMISSION CEREMONY, unchanged for a vertical. `review_status` is not `approved` and
    there is no accepted content hash, so `CapabilityResolver` may carry it as measurement and
    never as authority. A first document authored from ONE tenant must not become doctrine
    because it validated."""
    assert doc["metadata"]["review_status"] != "approved"
    assert not (doc.get("admission") or {}).get("accepted_content_hash")


def test_the_claims_are_sourced(doc) -> None:
    """Every number in this document came off the live graph. A vertical authored from an
    impression of a category is exactly the per-customer hardcode this layer refuses, and the
    difference between the two is whether the evidence is written down."""
    text = VERTICAL.read_text()
    assert "2026-09-15" in text, "the document does not say when it was measured"
    assert "143" in text or "97" in text, "the document cites no measured shape"
