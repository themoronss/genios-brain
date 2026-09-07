"""J2 — the Admin corpus routing gate.

WHAT THIS FILE IS FOR. Twenty-one Admin capabilities were authored, admission-stamped and
reachable by nothing, and nothing anywhere said so: `index.py` printed an orphan list nobody read
and the compiler was perfectly happy, because a capability no situation names simply never comes
up. That is the failure mode this file exists to make impossible — not "some capability is
unrouted", which is often correct, but "some capability is unrouted and nobody decided that".

THE INVARIANT. Every authored Admin capability is ROUTED or DEFERRED, never neither and never
both. A deferral is structural: the capability appears in no route, every situation it owns is
suppressed from the generated map, and it therefore compiles into zero packages. It is not a
label on a file that still routes.

The tests below are written against three sources that must agree — the authored corpus, the
generated registry, and `deferrals.yaml`. Disagreement between any two of them is the bug.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
CORPUS_ROOT = REPO_ROOT / "Domain Expertise"
TOOLS = CORPUS_ROOT / "_tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from _lib import DEFERRAL_KINDS, deferrals, walk  # noqa: E402

from genios_engine.packs.compiler.authoring import ExpertBrainCatalog  # noqa: E402
from genios_engine.platform.canonical import semantic_hash  # noqa: E402

ADMIN_ROOT = CORPUS_ROOT / "Admin Expertise"
REGISTRY = ADMIN_ROOT / "registry" / "situation-capability-map.yaml"

#: The two capabilities L3.4-U1 and U2 authored. Both must be admitted AND reachable: an
#: admission-stamped capability nothing routes is exactly the state this whole file is about.
NEW_CAPABILITIES = (
    "admin.executive_support.opportunity_tracking",
    "admin.admin_operations.goal_and_progress",
)

#: The two subdomains deferred wholesale for V1 (L3.4-U5). Ten capabilities.
DEFERRED_SUBDOMAINS = ("facilities_and_assets", "travel_and_events")

#: The founder surfaces in scope for V1 — the fifteen minus #8 Coordination and #15 Risk, both of
#: which are explicitly out per the product's own scope note. Each maps to at least one capability
#: that must be ROUTED, because a surface whose only home is deferred has no home.
#:
#: Surface 3 (Deadline) is listed against `commitment_tracking` rather than `statutory_filing`.
#: The statutory half of that surface is deferred — no pack emits a filing date — and the half a
#: founder actually meets is a dated obligation past its date, which commitment tracking owns.
#: Recording that here rather than in prose is the point: if somebody defers commitment tracking,
#: this test says which founder surface just went dark.
GLOBE_SURFACES: dict[str, tuple[str, ...]] = {
    "1_commitment": ("admin.executive_support.commitment_tracking",
                     "admin.meeting_operations.action_item_tracking"),
    "2_follow_up": ("admin.executive_support.inbox_and_correspondence",
                    "admin.meeting_operations.follow_up_coordination"),
    "3_deadline": ("admin.executive_support.commitment_tracking",),
    "4_scheduling": ("admin.meeting_operations.meeting_scheduling",
                     "admin.executive_support.briefing_and_preparation"),
    "5_decision_debt": ("admin.executive_support.approval_coordination",),
    "6_ownership": ("admin.executive_support.delegation_and_task_routing",),
    "7_founder_bottleneck": ("admin.executive_support.gatekeeping",),
    "9_process": ("admin.admin_operations.process_improvement",
                  "admin.admin_operations.sop_management",
                  "admin.admin_operations.service_level_management"),
    "10_document_integrity": ("admin.records_and_documentation.document_control",),
    "11_vendor_and_contract": ("admin.contract_and_vendor.contract_administration",
                               "admin.contract_and_vendor.renewal_management"),
    "12_financial_obligation": ("admin.finance_administration.invoice_processing",
                                "admin.finance_administration.receivables_follow_up"),
    "13_goal_and_progress": ("admin.admin_operations.goal_and_progress",),
    "14_opportunity": ("admin.executive_support.opportunity_tracking",),
}


# ── the three sources ────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def corpus() -> dict:
    """Capabilities and situations as AUTHORED, read straight off disk."""
    capabilities: dict[str, dict] = {}
    situations: dict[str, dict] = {}
    for kind, _path, data in walk(ADMIN_ROOT):
        identity = (data.get("identity") or {}) if isinstance(data, dict) else {}
        if kind == "capability" and identity.get("id"):
            capabilities[identity["id"]] = data
        elif kind == "situation" and identity.get("id"):
            situations[identity["id"]] = data
    return {"capabilities": capabilities, "situations": situations}


@pytest.fixture(scope="module")
def registry() -> dict:
    """The GENERATED reverse index — what the compiler actually reads."""
    return yaml.safe_load(REGISTRY.read_text())


@pytest.fixture(scope="module")
def ledger() -> dict:
    return deferrals(ADMIN_ROOT)


@pytest.fixture(scope="module")
def routed(registry) -> set[str]:
    out: set[str] = set()
    for route in (registry.get("map") or {}).values():
        out.update(route.get("capabilities") or ())
    return out


# ── the partition ────────────────────────────────────────────────────────────────────────

def test_every_capability_is_routed_or_deferred(corpus, routed, ledger):
    """The gate. No third state, and no capability in both states."""
    authored = set(corpus["capabilities"])
    deferred = set(ledger)

    neither = sorted(authored - routed - deferred)
    assert not neither, (
        f"{len(neither)} capabilities are authored, routed by nothing, and carry no deferral. "
        f"Each needs a door or a written reason it has none: {neither}")

    both = sorted(routed & deferred)
    assert not both, (
        f"deferred and still routed — the deferral is a label, not a structure: {both}")

    assert len(routed) + len(deferred) == len(authored)
    # The concrete split, pinned so a later wave cannot quietly unroute something and stay green
    # on the identity above (which any partition satisfies).
    assert len(deferred) == 24, f"expected 24 deferrals, found {len(deferred)}"
    assert len(routed) == len(authored) - 24


def test_the_original_fifty_seven_still_partition(corpus, routed, ledger):
    """L3.4's own arithmetic: of the 57 capabilities that existed before U1 and U2, every one is
    routed or deferred. Stated separately from the total so that adding a capability cannot
    disguise the loss of a route on an old one."""
    original = set(corpus["capabilities"]) - set(NEW_CAPABILITIES)
    assert len(original) == 57
    assert original <= (routed | set(ledger))
    assert len(original & routed) + len(original & set(ledger)) == 57


def test_every_deferral_carries_a_real_reason(corpus, ledger):
    assert ledger, "the deferral ledger is empty — deferrals.yaml is missing or unreadable"
    for capability_id, entry in sorted(ledger.items()):
        assert capability_id in corpus["capabilities"], \
            f"{capability_id} is deferred and is not an authored capability"
        assert entry.get("kind") in DEFERRAL_KINDS, \
            f"{capability_id}: kind {entry.get('kind')!r} is outside {list(DEFERRAL_KINDS)}"
        reason = " ".join(str(entry.get("reason") or "").split())
        # A category is not a reason. The sentence is the half a reader six months from now
        # actually needs, and it is the half that is skipped when the ledger is filled in a hurry.
        assert len(reason) >= 40, f"{capability_id}: deferral reason is a label, not a reason"


def test_the_two_out_of_scope_subdomains_are_wholly_deferred(corpus, ledger):
    for subdomain in DEFERRED_SUBDOMAINS:
        members = {c for c in corpus["capabilities"] if c.split(".")[1] == subdomain}
        assert members, f"no capabilities found in {subdomain}"
        undeferred = sorted(members - set(ledger))
        assert not undeferred, f"{subdomain} is deferred but these are not: {undeferred}"
        for capability_id in members:
            assert ledger[capability_id]["kind"] == "out_of_v1_scope"


# ── deferral is structural: zero packages ────────────────────────────────────────────────

def test_a_deferred_capability_reaches_no_route(registry, ledger):
    """The registry is what the compiler reads. If a deferred capability is named in a route, the
    resolver can select it and a package can be built through it."""
    for situation_type, route in (registry.get("map") or {}).items():
        overlap = sorted(set(route.get("capabilities") or ()) & set(ledger))
        assert not overlap, f"route {situation_type!r} names deferred capabilities {overlap}"


def test_situations_owned_by_a_deferred_capability_are_suppressed(corpus, registry, ledger):
    """The stronger half. `CapabilityResolver` builds its capability set from each route's
    SITUATIONS — owner plus also_serves — and uses the route's capability list only as a
    staleness check. So a deferral that removed the capability and left the situation would not
    prevent the compile; it would make the compile raise `AuthoringIntegrityError` instead.
    Suppressing the situation is what makes zero packages true."""
    owned_by_deferred = {
        sid for sid, s in corpus["situations"].items()
        if (s.get("identity") or {}).get("owner_capability") in ledger
    }
    assert owned_by_deferred, "expected at least one situation owned by a deferred capability"
    in_map: set[str] = set()
    for route in (registry.get("map") or {}).values():
        in_map.update(route.get("situations") or ())
    leaked = sorted(owned_by_deferred & in_map)
    assert not leaked, f"situations owned by a deferred capability still route: {leaked}"


def test_no_live_situation_serves_a_deferred_capability(corpus, ledger):
    """The one shape suppression cannot fix: a deferred id sitting in the `also_serves` of a
    situation somebody else owns. The resolver would add the capability, the generated map would
    not list it, and the compile would die on the staleness check rather than on anything a
    reader can see."""
    for sid, situation in sorted(corpus["situations"].items()):
        owner = (situation.get("identity") or {}).get("owner_capability")
        if owner in ledger:
            continue                      # suppressed wholesale; nothing it names can route
        if not ((situation.get("matches") or {}).get("l2_situation_types") or []):
            continue                      # pending, routes nothing
        offenders = sorted(set(situation.get("also_serves") or ()) & set(ledger))
        assert not offenders, (
            f"live situation {sid!r} serves deferred capabilities {offenders}")


def test_deferred_capabilities_are_not_deleted_or_deprecated(corpus, ledger):
    """Deferral preserves the knowledge. A deferred capability whose status has been flipped to
    `deprecated` has been quietly retired instead, which is a different decision needing a
    different conversation."""
    for capability_id in ledger:
        identity = corpus["capabilities"][capability_id]["identity"]
        assert identity.get("status") == "stable", \
            f"{capability_id} is deferred AND {identity.get('status')!r} — deferral is not retirement"


# ── the two new surfaces ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("capability_id", NEW_CAPABILITIES)
def test_new_capability_is_authored_and_admitted(corpus, capability_id):
    content = corpus["capabilities"].get(capability_id)
    assert content is not None, f"{capability_id} is not authored"
    identity, metadata = content["identity"], content["metadata"]
    assert identity.get("status") == "stable"
    assert not identity.get("stub")
    assert metadata.get("review_status") == "approved"
    assert str(metadata.get("reviewed_by") or "").strip(), "admission needs a named human"
    accepted = str((content.get("admission") or {}).get("accepted_content_hash") or "")
    # The hash pin is over the document MINUS the admission block, so an edit after review
    # silently un-accepts. Recomputing it here is the same check the resolver makes.
    assert accepted == semantic_hash({k: v for k, v in content.items() if k != "admission"}), \
        f"{capability_id} admission hash does not match its content"


@pytest.mark.parametrize("capability_id", NEW_CAPABILITIES)
def test_new_capability_is_routed(routed, capability_id):
    assert capability_id in routed, (
        f"{capability_id} is authored and stamped and reaches nothing — knowledge does not count "
        f"as shipped until something can consume it")


@pytest.mark.parametrize("capability_id", NEW_CAPABILITIES)
def test_new_capability_has_a_live_door_and_a_declared_gap(corpus, capability_id):
    """Each of U1 and U2 authored two situations: one that routes on evidence the pipeline emits
    today, and one that declares the trigger Layer 2 has yet to build. Both halves matter — the
    live one is the V1 product, the pending one is the requirement, and collapsing either into the
    other is how a corpus starts lying about its own coverage."""
    owned = [s for s in corpus["situations"].values()
             if (s.get("identity") or {}).get("owner_capability") == capability_id]
    live = [s for s in owned if ((s.get("matches") or {}).get("l2_situation_types") or [])]
    pending = [s for s in owned
               if ((s.get("matches") or {}).get("pending_l2_situation_types") or [])]
    assert live, f"{capability_id} owns no situation bound to a type Layer 2 emits"
    assert pending, f"{capability_id} owns no situation declaring what Layer 2 still owes it"


def test_the_admission_hash_invalidates_on_content_change(corpus):
    """Must-not-regress #3, checked as a property of the hash rather than by writing to disk: a
    single changed byte outside the admission block produces a different digest, so the stamp
    stops matching and the capability stops carrying authority."""
    for capability_id in NEW_CAPABILITIES:
        content = dict(corpus["capabilities"][capability_id])
        reviewed = {k: v for k, v in content.items() if k != "admission"}
        stamped = str((content.get("admission") or {}).get("accepted_content_hash") or "")
        mutated = dict(reviewed)
        mutated["question"] = str(mutated["question"]) + " "
        assert semantic_hash(mutated) != stamped


# ── coverage of the founder surfaces ─────────────────────────────────────────────────────

@pytest.mark.parametrize("surface", sorted(GLOBE_SURFACES))
def test_every_in_scope_founder_surface_has_a_routed_home(routed, surface):
    homes = GLOBE_SURFACES[surface]
    reachable = [c for c in homes if c in routed]
    assert reachable, (
        f"founder surface {surface} has no ROUTED capability; its homes are {list(homes)}")


# ── the generated registry is generated ──────────────────────────────────────────────────

def test_validate_reports_zero_errors():
    import validate                                     # noqa: PLC0415
    validate.ERRORS.clear()
    validate.WARNINGS.clear()
    assert validate.main() == 0, f"validate.py errors: {validate.ERRORS}"


def test_the_registry_is_in_sync_with_the_corpus():
    """Must-not-regress #7 — the generated registry is never hand-edited. Regenerating it must be
    a no-op; any difference means either somebody typed into the generated file or somebody
    changed the corpus and did not regenerate, and both read the same way at compile time."""
    before = {domain.name: (domain / "registry" / "situation-capability-map.yaml").read_text()
              for domain in (CORPUS_ROOT / "Admin Expertise",
                             CORPUS_ROOT / "Customer Support Expertise",
                             CORPUS_ROOT / "Sales Expertise")}
    import index                                        # noqa: PLC0415
    assert index.main() == 0
    for name, text in before.items():
        after = (CORPUS_ROOT / name / "registry" / "situation-capability-map.yaml").read_text()
        assert after == text, f"{name}: registry is stale — run _tools/index.py and commit it"


def test_the_registry_records_the_deferrals(registry, ledger):
    """The receipt. A compile can be asked what the domain deliberately does not know and get a
    list with reasons, rather than a shrug."""
    recorded = registry.get("deferred_capabilities") or {}
    assert set(recorded) == set(ledger)
    for capability_id, entry in recorded.items():
        assert entry.get("kind") in DEFERRAL_KINDS
        assert len(str(entry.get("reason") or "")) >= 40
    assert registry.get("deferral_contradictions") in (None, [], ())
    assert registry["stats"]["capabilities_deferred"] == len(ledger)
    assert registry["stats"]["capabilities_unrouted_unreasoned"] == 0
    assert registry.get("suppressed_situations"), \
        "no situation was suppressed — the travel-and-events door is still open"


# ── the compiler agrees ──────────────────────────────────────────────────────────────────

def test_the_compiler_loads_the_corpus_and_sees_no_deferred_capability(ledger):
    """The end of the chain. `ExpertBrainCatalog` is what the compile path reads; if it can load
    the tree and no route it holds names a deferred capability, deferred categories compile into
    zero packages."""
    catalog = ExpertBrainCatalog(CORPUS_ROOT)
    admin = catalog.domain("admin")
    assert len(admin.capabilities) == len(admin.object_manifests) == len(admin.knowledge_manifests)
    for capability_id in NEW_CAPABILITIES:
        assert capability_id in admin.capabilities
        assert capability_id in admin.object_manifests
        assert capability_id in admin.knowledge_manifests
    for situation_type, route in admin.routes.items():
        overlap = sorted(set(route.get("capabilities") or ()) & set(ledger))
        assert not overlap, f"{situation_type}: compiler route reaches deferred {overlap}"
