"""Every model site the engine has, and what a golden run does with it.

`speedrun008/YC-II W27/` STEP-01 §3.2. A golden case
runs the real chain with the model's answers recorded. That is only honest if every site the chain
can reach is handed the RECORDED model — a site that quietly built its own client would, in a test
process with no key, return nothing and skip itself, and the case would be judged on a chain
production does not run. The junk filter is the sharpest instance: with no key (the tests' default)
it never runs, so a mail production junked would pass.

So the register below is held equal to `tests/test_every_llm_call_site_is_metered._SITES` — the
complete list of modules that invoke a model — in both directions. A new site cannot run in a
golden case until somebody decides here how it is reached:

  * `recorded` — the chain can reach it, and the runner hands it the recorded model through the
    named DOOR (`engine_runner.py` opens every door; its own test holds that);
  * `off` — the runner's chain cannot reach it, and the reason says why. If it ever is reached,
    the runner's transport refusal fails the case loudly (`engine_runner.UnrecordedModelCall`);
  * `transport` — the HTTP client every other site rides on, refused outright in a golden run.
"""
from __future__ import annotations

#: How the runner hands the recorded model to the chain. Each is a production seam, not a test
#: hook: the runner sets exactly what production's wiring sets, with the recorded model in place
#: of the real one.
DOORS: dict[str, str] = {
    "routes._llm": "the client `_run_l2_chain` hands the L2 drain (resolution) and the narrator",
    "wiring.make_llm_client": "the default client factory — the semantic lane (extraction and the "
                              "relevance page) and every lane the chain builds for itself, such as "
                              "the re-read pass",
    "wiring.make_relevance_classifier": "the junk filter, built the way every sync door builds it",
    "llm_decision_maker.client": "the decider and R-1 — on in production for every org "
                                 "(GENIOS_L4_LLM_DECISION_MAKER=true, speedrun008/YCW27/STATUS.md)",
    "llm_sites.make_site_client": "the R-site gate — the situation reasoner and the bundle narrator",
}

_SCREEN = ("the screen door: the runner drives mail and calendar, and a case that needs the screen "
           "declares it not expressible")

#: module (as `_SITES` names it) → (kind, door or reason, the sites its prompts are recognised as)
CHAIN_SITES: dict[str, tuple[str, str, tuple[str, ...]]] = {
    # ── L1 capture ──────────────────────────────────────────────────────────────────────────
    "capture/gate/relevance.py": (
        "recorded", "wiring.make_relevance_classifier", ("junk_gate", "junk_gate_batch")),
    "capture/esqe/relevance.py": ("recorded", "wiring.make_llm_client", ("relevance",)),
    "capture/semantic/extractor.py": ("recorded", "wiring.make_llm_client", ("extraction",)),
    "capture/domain/proposer.py": (
        "off", "no caller passes a proposer — capture/pipeline.py calls tag_domains without one, "
               "so the site spends nothing in production", ()),
    # ── L2 context ──────────────────────────────────────────────────────────────────────────
    "context/llm/client.py": (
        "transport", "the HTTP client itself — refused outright in a golden run, so a site that "
                     "built its own client fails the case instead of skipping itself", ()),
    "context/extract/extractor.py": (
        "off", "Layer 2 is handed llm=None (context/runner.py, process_event): it adapts Layer 1's "
               "stored extraction instead of reading the message again", ()),
    "context/angles/asker.py": (
        "off", "the sweep supplies no asker — evaluate_angle(asker=None) is the default and the "
               "only call the chain makes", ()),
    "context/lifecycle/resolution.py": ("recorded", "routes._llm", ("resolution",)),
    "context/analytic/cohort.py": (
        "off", "the cohort drafter runs from the cohort API (api/cohort_routes.py), never from "
               "the sweep", ()),
    # ── L4 reasoning ────────────────────────────────────────────────────────────────────────
    "reason/intelligence.py": ("off", "the Ask API, not the sweep", ()),
    "reason/bundle/gate.py": ("recorded", "llm_sites.make_site_client", ("bundle_narrator",)),
    "reason/llm_decision_maker.py": ("recorded", "llm_decision_maker.client", ("decider",)),
    "reason/llm_interpretation.py": ("recorded", "llm_decision_maker.client", ("r1",)),
    "reason/brief_drafter.py": (
        "off", "the company brief's drafter runs from scripts/draft_company_brief.py and the weekly "
               "review in the heavy tick, neither of which a case drives; a case's brief is seeded "
               "as the founder accepted it", ()),
    # ── moments — the screen door ───────────────────────────────────────────────────────────
    "reason/moments/screen_insight.py": ("off", _SCREEN, ()),
    "reason/moments/screen_memory_batch.py": ("off", _SCREEN, ()),
    "reason/moments/seat_profile.py": ("off", _SCREEN, ()),
    "reason/moments/draft_review.py": ("off", _SCREEN, ()),
    # ── L5 delivery ─────────────────────────────────────────────────────────────────────────
    "deliver/render.py": ("recorded", "routes._llm", ("narrator",)),
    # ── packs / brains ──────────────────────────────────────────────────────────────────────
    "packs/brains/org_rule_extract.py": ("recorded", "wiring.make_llm_client", ("org_rule_extract",)),
    "packs/brains/behavior_distill.py": (
        "off", "not wired in production: brain_pipeline_proposals is always called with "
               "labeler=None", ()),
    # ── API ─────────────────────────────────────────────────────────────────────────────────
    "api/intelligence_routes.py": ("off", "the Ask API, not the sweep", ()),
}

KINDS = ("recorded", "off", "transport")


def recorded_sites() -> frozenset[str]:
    """Every site name a golden case may legitimately call."""
    return frozenset(s for kind, _door, sites in CHAIN_SITES.values() if kind == "recorded"
                     for s in sites)
