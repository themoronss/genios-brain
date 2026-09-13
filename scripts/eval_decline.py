"""P4 carry-over eval — does a counterparty's LinkedIn decline reach `deal.status=lost`? READ-ONLY.

    GENIOS_ANTHROPIC_API_KEY=... python scripts/eval_decline.py [--runs 10] [--model M] [--json]

WHY. The P2 gate saw the same LinkedIn decline written as `deal.stage` on one run and lost on the
next: the model's subject/field wording varies. P4 moved the rule onto the reliable fact — a
`decision.*` fact whose words state a lost outcome (`context/pipeline._decision_decline`). This
measures that on the REAL model: the same decline goes through the production screen extraction
N times (screen profile, same router, no cache — a fresh nonce per run), is graded and adapted
exactly as Layer 2 reads it (`runner.graded_extraction` → `qes_adapter.adapt_qes_extraction`), and
each run is scored on whether the rule fires. Pass = at least `--pass-runs` of `--runs` (default
9/10, P4 acceptance §7.3).

It never writes a row and needs no database: the rule's database half (one external account, one
open deal, counterparty-authored) is covered by tests/test_p4_verify_pg.py. Each run is one model
call. Exit code 0 on pass, 1 on fail, 2 when no key is configured.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

#: The decline as the promoter renders a LinkedIn thread's RECEIVED side (#in): the
#: counterparty's new line after the context section (plan §3.1 render shape).
SUBJECT = "LinkedIn · Priya Sharma (Acme Logistics)"
DECLINE = (
    "Priya Sharma: Hi Rohit, thank you for the proposal and the time your team put into the demo. "
    "After discussing it internally we have decided to go with another vendor for this rollout, "
    "so we won't be proceeding with GeniOS at this stage. Really appreciate your patience and "
    "hope we can stay in touch.\n\n"
    "context — do not extract\n"
    "You: Hi Priya, sharing the revised proposal for the Acme Logistics rollout. Happy to walk "
    "through it this week.")


def one_run(i: int, *, llm, now: datetime) -> dict:
    from genios_engine.capture.preprocess.preprocess import preprocess
    from genios_engine.capture.semantic.extractor import EventEnvelope, ExtractionRequest, extract
    from genios_engine.capture.semantic.profiles import get_profile
    from genios_engine.capture.semantic.router import RoutingInput, select_profile
    from genios_engine.context.pipeline import (_counterparty_decline, _decision_decline,
                                                _normalise_deal_status)
    from genios_engine.context.qes_adapter import adapt_qes_extraction
    from genios_engine.context.runner import graded_extraction

    event_id = f"eval_decline_{now:%Y%m%d%H%M%S}_{i}"
    prepared = preprocess(SUBJECT + "\n\n" + DECLINE, event_id=event_id)
    choice = select_profile(RoutingInput(source="screen_session",
                                         object_type="screen_chat_thread"))
    profile = get_profile(choice.profile_id)
    request = ExtractionRequest(
        org_id="eval_decline", event_id=event_id, source="screen_session",
        profile_id=profile.profile_id, tier=profile.default_tier, prepared=prepared,
        envelope=EventEnvelope(direction="inbound", sender="", recipients=(), thread_position=1,
                               thread_depth=1, subject=SUBJECT),
        eval_time=now)
    # The prompt fence needs 16 lowercase hex characters (capture/semantic/injection.fence);
    # a fresh one per run also keeps every run an uncached, independent call.
    outcome = extract(request, llm=llm, store=None, open_lane=None, nonce=secrets.token_hex(8))
    if outcome.result is None:
        return {"run": i, "fired": False, "parked": getattr(outcome.parked, "reason", "parked"),
                "decisions": [], "deal_facts": []}
    graded = graded_extraction(outcome.result, prepared.clean_text, event_id)
    qualified = adapt_qes_extraction(graded, confidence_bp=5000)
    facts = list(qualified.fact_candidates or [])
    decisions = [{k: f.get(k) for k in ("subject", "field", "value", "evidence_text")}
                 for f in facts if str(f.get("field") or "").startswith("decision.")]
    deal_facts = [{"field": f.get("field"), "value": f.get("value"),
                   "as_status": _normalise_deal_status(f.get("value"))[0]}
                  for f in facts if str(f.get("field") or "").startswith("deal.")]
    # The rule exactly as Layer 2 applies it: the decision.* fact, else the counterparty's own
    # new lines + L1's intent/stance (context/pipeline.py).
    by_decision = _decision_decline(facts) is not None
    by_words = _counterparty_decline(prepared.clean_text, intent=qualified.intent,
                                     stance=qualified.stance) is not None
    return {"run": i, "fired": by_decision or by_words, "by_decision": by_decision,
            "by_words": by_words, "intent": qualified.intent, "stance": qualified.stance,
            "parked": None, "decisions": decisions, "deal_facts": deal_facts}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--pass-runs", type=int, default=9)
    ap.add_argument("--model", default=None, help="default: the engine's configured model")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    from genios_engine.platform.config import get_settings
    s = get_settings()
    if not s.anthropic_api_key:
        print("GENIOS_ANTHROPIC_API_KEY is not set — nothing run.", file=sys.stderr)
        return 2
    from genios_engine.context.llm.client import LLMClient
    from genios_engine.reason.llm_sites import tier_model
    model = args.model or str(s.anthropic_model or tier_model("T1"))
    llm = LLMClient(api_key=s.anthropic_api_key, model=model)
    now = datetime.now(timezone.utc)
    runs = [one_run(i, llm=llm, now=now) for i in range(args.runs)]
    fired = sum(1 for r in runs if r["fired"])
    ok = fired >= args.pass_runs
    if args.json:
        print(json.dumps({"model": model, "runs": runs, "fired": fired, "of": args.runs,
                          "pass": ok}, indent=2, default=str))
    else:
        for r in runs:
            print(f"run {r['run']}: {'FIRED' if r['fired'] else 'missed'}"
                  + (f" (parked: {r['parked']})" if r["parked"] else "")
                  + (f" · decision={r.get('by_decision')} words={r.get('by_words')}"
                     f" intent={r.get('intent')} stance={r.get('stance')}"
                     if not r["parked"] else "")
                  + f" · decisions={len(r['decisions'])} deal_facts={r['deal_facts']}")
        print(f"\n{model}: rule fired {fired}/{args.runs} — {'PASS' if ok else 'FAIL'} "
              f"(need {args.pass_runs})")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
