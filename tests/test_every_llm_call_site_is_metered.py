"""THE GATE: every place in the engine that spends Anthropic money files a `llm_costs` row.

WHY THIS TEST EXISTS. Model spend is the product's largest variable cost and the only one billed
per unit. It is knowable per account and per person ONLY if every call site writes to the one
ledger — and a call site is three lines of code that any layer can add. Twice now a lane spent
real money invisibly for months (`l5_render`, then the T2 document reader), and both times the
symptom was the same: the reported bill sat below the Anthropic invoice and nobody could say by
how much or whose it was. Neither gap was a hard bug; both were an omission nothing checked.

So this file checks it. `_SITES` below is the complete register of modules that invoke a model,
and the test fails when the code and the register disagree in EITHER direction:

  * a NEW call site appears        → someone added model spend; make it record, then register it;
  * a registered site disappears   → the register is stale; delete the row.

WHAT TO DO WHEN THIS TEST FAILS — the whole procedure, so a reader never has to hunt for it:

  1. Record the spend. Call `GraphStore.record_cost(...)` (or hand your unit a `cost_sink` /
     `cost_recorder` the wiring binds) with a NEW `purpose` string naming your site, and pass
     `success=` / `error=` so a refused answer is billed too — it was still bought.
  2. Name the person, if your lane knows one. `seat_id=` is what makes a per-USER bill possible
     (migration 0175). Screen lanes and authenticated API calls always know it; a background
     sweep genuinely does not, and NULL is the correct answer there — never invent an owner.
  3. Pass the cache split (`cache_read_tokens` / `cache_write_tokens`) if your call uses a
     cacheable prefix. Recorded, never priced: `input_tokens` is already cost-equivalent.
  4. Add your module to `_SITES` with the purpose you chose.

The register is also the documentation: `purpose` values here are exactly what `/admin` groups
spend by, so the breakdown an operator reads is only as complete as this table.
"""
from __future__ import annotations

import pathlib
import re

ENGINE = pathlib.Path(__file__).resolve().parents[1] / "genios_engine"

#: A model invocation, in every spelling the engine actually uses: the shared `LLMClient.call`,
#: a raw `Anthropic().messages.create`, and the Message Batches API. Deliberately shape-based
#: rather than import-based — a new lane that reaches for `anthropic` directly (which is how both
#: historical gaps were introduced) is exactly what has to be caught.
_INVOCATION = re.compile(
    r"(?:\b(?:llm|client|_llm|_client|self\._client|self\._llm)\s*\.call\()"
    r"|(?:\)\s*\.call\()"
    r"|(?:messages\s*\.\s*create\()"
    r"|(?:messages\s*\.\s*batches)")

#: Tokens that mean "this module files the row itself". `_record` covers the units that wrap the
#: sink in a never-raises helper, which is the house style for accounting.
_RECORDS = ("record_cost", "record_model_run", "_record_cost", "cost_sink", "cost_recorder",
            "self._record(", "_record(res", "_record(result", "_record(response")

# ── the register ─────────────────────────────────────────────────────────────────────────────
# module → (purpose(s) it lands under, or the module that records on its behalf)
#
# "records": the module writes the row. "recorded_by": it hands the result up to a caller that
# does — a real and correct pattern for a pure unit that must stay runnable with no database,
# but one that has to be WRITTEN DOWN, because "someone else does it" is indistinguishable from
# "nobody does it" until you go and look.
_SITES: dict[str, dict[str, object]] = {
    # ── L1 capture ───────────────────────────────────────────────────────────────────────
    "capture/gate/relevance.py": {"records": True, "purpose": ("relevance_gate",)},
    "capture/esqe/relevance.py": {"records": True, "purpose": ("l1_relevance",)},
    "capture/semantic/extractor.py": {
        "recorded_by": "capture/pipeline.py", "purpose": ("l1_extract",)},

    # ── L2 context ───────────────────────────────────────────────────────────────────────
    "context/llm/client.py": {
        # THE TRANSPORT. It counts tokens and hands them back; recording here would file a row
        # for calls the caller may never use, and would know neither the org nor the purpose.
        "records": False, "purpose": ()},
    "context/extract/extractor.py": {
        "recorded_by": "context/pipeline.py", "purpose": ("extract",)},
    "context/angles/asker.py": {
        "recorded_by": "context/angles/store.py", "purpose": ("l2:<site>",)},
    "context/lifecycle/resolution.py": {"records": True, "purpose": ("l2:<site>",)},
    "context/analytic/cohort.py": {"records": True, "purpose": ("l2:<site>",)},

    # ── L4 reasoning ─────────────────────────────────────────────────────────────────────
    "reason/intelligence.py": {
        "recorded_by": "api/intelligence_routes.py", "purpose": ("intelligence_query",)},
    "reason/bundle/gate.py": {"records": True, "purpose": ("l4_bundle",)},
    "reason/llm_decision_maker.py": {"records": True, "purpose": ("l4_llm_decision",)},
    "reason/llm_interpretation.py": {"records": True, "purpose": ("l4_llm_decision",)},

    # ── moments (per-seat by construction — these always know the person) ────────────────
    "reason/moments/screen_insight.py": {
        "records": True, "purpose": ("moment.screen_insight",), "seat": True},
    "reason/moments/screen_memory_batch.py": {
        "records": True, "purpose": ("screen_memory_batch",), "seat": True},
    "reason/moments/seat_profile.py": {
        # `t1_text` is shared: `reply_draft` passes its own `followup_draft` purpose through it,
        # so that string lives in THAT module and is not claimed here.
        "records": True, "purpose": ("screen_profile",), "seat": True},
    "reason/moments/draft_review.py": {
        "records": True, "purpose": ("moment.draft_review",), "seat": True},

    # ── L5 delivery ──────────────────────────────────────────────────────────────────────
    "deliver/render.py": {"records": True, "purpose": ("l5_render",)},

    # ── packs / brains ───────────────────────────────────────────────────────────────────
    "packs/brains/org_rule_extract.py": {"records": True, "purpose": ("org_rule_extract",)},
    "packs/brains/behavior_distill.py": {
        # NOT WIRED IN PRODUCTION: `brain_pipeline_proposals` is always called with
        # `labeler=None`, so N-4 is deterministic and this site spends nothing today. The sink
        # is in place so the day it IS wired, its spend arrives in the ledger rather than as a
        # gap in the bill.
        "records": True, "purpose": ("brains.behavior_distill",)},

    # ── API ──────────────────────────────────────────────────────────────────────────────
    "api/intelligence_routes.py": {
        "records": True, "seat": True,
        "purpose": ("intelligence_query", "intelligence_analyze", "intelligence_draft")},
}

_HOWTO = (
    "\n\nA model call is only visible in the bill if it writes to `llm_costs`.\n"
    "  1. record it: GraphStore.record_cost(org_id=…, model=…, purpose='<new>', "
    "input_tokens=…, output_tokens=…, success=…, error=…)\n"
    "  2. name the person when your lane knows one: seat_id=… (NULL for background work)\n"
    "  3. pass cache_read_tokens/cache_write_tokens if the call uses a cacheable prefix\n"
    "  4. add your module to _SITES in tests/test_every_llm_call_site_is_metered.py\n"
    "See that file's docstring for why this is a gate and not a convention.")


def _modules_that_call_a_model() -> set[str]:
    found = set()
    for path in sorted(ENGINE.rglob("*.py")):
        if _INVOCATION.search(path.read_text(encoding="utf-8")):
            found.add(str(path.relative_to(ENGINE)))
    return found


def test_the_register_lists_exactly_the_modules_that_call_a_model():
    found = _modules_that_call_a_model()
    registered = set(_SITES)
    assert found == registered, (
        f"unregistered model call sites: {sorted(found - registered)}\n"
        f"registered but no longer calling a model: {sorted(registered - found)}" + _HOWTO)


def test_every_registered_site_either_records_or_names_who_records_for_it():
    missing = []
    for module, spec in _SITES.items():
        if spec.get("recorded_by") or spec.get("records") is False:
            continue
        src = (ENGINE / module).read_text(encoding="utf-8")
        if not any(token in src for token in _RECORDS):
            missing.append(module)
    assert not missing, f"these call sites spend money and file nothing: {missing}" + _HOWTO


def test_a_site_that_delegates_names_a_recorder_that_actually_records():
    """"My caller does it" is only true if the caller does it. Checked, not trusted."""
    broken = []
    for module, spec in _SITES.items():
        recorder = spec.get("recorded_by")
        if not recorder:
            continue
        path = ENGINE / str(recorder)
        if not path.exists():
            broken.append(f"{module} → {recorder} (no such module)")
            continue
        if not any(token in path.read_text(encoding="utf-8") for token in _RECORDS):
            broken.append(f"{module} → {recorder} (records nothing)")
    assert not broken, f"delegated recording that does not happen: {broken}" + _HOWTO


def test_the_per_seat_lanes_actually_pass_a_seat():
    """A lane that knows the person must SAY so, or a per-user bill silently under-counts them
    while the account total stays right — the failure that looks like nothing is wrong."""
    missing = [module for module, spec in _SITES.items()
               if spec.get("seat")
               and "seat_id=" not in (ENGINE / module).read_text(encoding="utf-8")]
    assert not missing, (
        f"these lanes know whose call it is and do not record it: {missing}" + _HOWTO)


#: Purposes the register names that are NOT literals in their own module's source, with the
#: reason. Anything else has to appear where it is claimed, or the register is fiction.
_PURPOSE_NOT_A_LITERAL = {
    "l2:<site>":            "built as f'l2:{site}' in context/model_audit.record_model_run",
    "l1_extract":           "the constant lives in the recorder, capture/pipeline.py",
    "extract":              "the constant lives in the recorder, context/pipeline.py",
    "intelligence_query":   "recorded by api/intelligence_routes for reason/intelligence",
    "l4_llm_decision":      "llm_interpretation records through llm_decision_maker's constant",
    "l4_bundle":            "the constant lives in reason/bundle/narrator.py",
}


def test_every_purpose_the_register_claims_exists_in_the_code():
    """Otherwise the table reads as documentation while naming labels nothing ever writes — and
    an operator reading /admin would look for a breakdown row that cannot appear."""
    wrong = []
    for module, spec in _SITES.items():
        src = (ENGINE / module).read_text(encoding="utf-8")
        for purpose in spec["purpose"]:          # type: ignore[union-attr]
            if purpose in _PURPOSE_NOT_A_LITERAL:
                continue
            if f'"{purpose}"' not in src and f"'{purpose}'" not in src:
                wrong.append(f"{module} claims {purpose!r}, which does not appear in it")
    assert not wrong, "\n".join(wrong) + _HOWTO


def test_every_registered_purpose_is_a_plain_reportable_string():
    """`purpose` is what /admin groups spend by, so an empty or duplicated one makes a breakdown
    that cannot be read. `l2:<site>` is the one templated value, and it is spelled once here."""
    seen: dict[str, str] = {}
    for module, spec in _SITES.items():
        for purpose in spec["purpose"]:          # type: ignore[union-attr]
            assert purpose and purpose.strip() == purpose, f"{module}: bad purpose {purpose!r}"
            if purpose in ("l2:<site>", "intelligence_query", "l4_llm_decision"):
                continue                          # deliberately shared by sibling modules
            assert purpose not in seen, (
                f"purpose {purpose!r} is claimed by both {seen[purpose]} and {module} — "
                "two lanes under one label cannot be told apart in the spend breakdown")
            seen[purpose] = module
