"""A capability can be admitted, hash-pinned, and say nothing.

The ceremony asks three questions — is it stable, did a named human approve it, do the bytes still
match — and never asked whether there was anything to approve. 136 of the corpus's capabilities
passed it over a file whose own notes read "Phase 1 stub — identity, purpose and object load-set
only", and three of those were reached by EVERY routed situation on the design partner's org.
"""
import yaml
from pathlib import Path

from genios_engine.packs.compiler.capability_resolver import _LABEL_KEYS, _hollow
from genios_engine.packs.compiler.models import RoutePlan
from genios_engine.reason.domain_shadow import expert_catalog

CORPUS = Path("Domain Expertise")


class _Doc:
    def __init__(self, content):
        self.content = content


def _capability(domain, capability_id):
    return expert_catalog().domain(domain).capabilities[capability_id]


def test_a_name_a_sentence_and_a_question_is_hollow():
    assert _hollow(_Doc({"identity": {}, "description": "x", "question": "y", "metadata": {}}))
    assert not _hollow(_Doc({"identity": {}, "description": "x", "outcomes": ["a"]}))


def test_the_label_keys_are_the_ones_that_carry_no_expertise():
    assert _LABEL_KEYS == {"identity", "description", "question", "metadata", "admission"}


# ── the three capabilities every live route ran through ─────────────────────────
def test_the_capabilities_every_routed_situation_reaches_now_say_something():
    """`account_research` served `opportunity`, `relationship` AND `investor_relationship` — all 55
    routed situations on the live org — and carried a name and nothing else. `lead_generation`
    (18 situations) and `expansion` (23) were the other two hollow capabilities on a live route."""
    for capability_id in ("sales.prospecting_and_outreach.account_research",
                          "sales.prospecting_and_outreach.lead_generation",
                          "sales.post_sale_and_growth.expansion"):
        capability = _capability("sales", capability_id)
        assert not _hollow(capability), f"{capability_id} is still a placeholder"
        content = capability.content
        for key in ("outcomes", "kpis", "handoffs", "failure_modes", "applies_to"):
            assert content.get(key), f"{capability_id} carries no {key}"


def test_a_promoted_capability_states_no_thresholds():
    """No numbers in a capability file: thresholds and scores are Layer 4's arithmetic and live in
    the pack manifest. A number here means the L3/L4 boundary has leaked."""
    for capability_id in ("sales.prospecting_and_outreach.account_research",
                          "sales.prospecting_and_outreach.lead_generation",
                          "sales.post_sale_and_growth.expansion"):
        for kpi in _capability("sales", capability_id).content["kpis"]:
            assert set(kpi) <= {"name", "unit", "description"}, f"{capability_id}: {kpi}"
            assert "threshold" not in kpi and "target" not in kpi


# ── thinness is counted, and it is NOT an authority failure ─────────────────────
def test_hollow_is_reported_separately_from_admission():
    """`admission_gaps` drives `plan.admitted`, which drives the package's `review_state`, which
    decides whether a card may instruct. Folding a content observation into it would make "thin"
    silently mean "unauthorised" and stop any package holding one placeholder from ever being
    accepted."""
    plan = RoutePlan(domain_ids=("sales",), situation_ids=(), capability_ids=("a.b.c",),
                     required_object_ids=("x",), optional_object_ids=(), never_object_ids=(),
                     hollow_capability_ids=("a.b.c",))
    assert plan.admitted is True
    assert plan.admission_gaps == ()
    assert plan.hollow_capability_ids == ("a.b.c",)


def test_the_admin_route_reports_its_placeholders_rather_than_hiding_them():
    """All 57 Admin capabilities are hollow, including the three behind `account_admin`. That is
    exactly why hollow is reported and not gated: refusing them would un-route the type entirely
    and take live coverage backwards."""
    admin = expert_catalog().domain("admin")
    behind = admin.routes["account_admin"]["capabilities"]
    assert behind, "account_admin routes to nothing"
    assert all(_hollow(admin.capabilities[c]) for c in behind)


# ── the corpus-wide count, so the queue cannot quietly grow ─────────────────────
def test_the_promotion_queue_is_measurable_per_domain():
    counts = {}
    for domain_dir in sorted(p for p in CORPUS.iterdir()
                             if p.is_dir() and not p.name.startswith("_")):
        for path in domain_dir.rglob("capability.yaml"):
            content = yaml.safe_load(path.read_text()) or {}
            domain = ((content.get("identity") or {}).get("domain")) or domain_dir.name
            counts.setdefault(domain, [0, 0])[bool(_hollow(_Doc(content)))] += 1
    # Sales is the tenant's own pack lane and the only domain whose promotions can reach a user
    # today, so it is the one that must keep improving.
    full, thin = counts["sales"]
    assert full >= 8, f"sales lost promoted capabilities: {full} full, {thin} hollow"
    assert thin < full + thin, "every sales capability is a placeholder"
