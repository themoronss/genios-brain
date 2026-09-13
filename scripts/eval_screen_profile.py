"""D7 · screen-profile model eval — model A vs model B on stored screen deltas. READ-ONLY.

    python scripts/eval_screen_profile.py --org ORG --model-a claude-haiku-4-5-20251001 \
        --model-b claude-sonnet-4-5 [--limit 20] [--object-type screen_chat_thread] [--json]

WHAT IT REPLAYS. The screen deltas the promoter already rendered and landed: `source_events`
with `source='screen_session'`, whose `raw_payloads` row holds the rendered object (body with the
`context — do not extract` section, labelIds, watermark). Each one is rebuilt exactly as capture
builds it (HTML strip, subject + body, `preprocess`), routed by the production router, and put
through `extractor.extract()` twice — once per model, same profile, same tier, same envelope,
no cache — so the only variable is the model.

WHAT IT PRINTS. Per object and in total, a claim-level comparison per field: claims only A made,
only B made, and both (a claim is `field + normalised verbatim quote`). "Parity" = B found at
least `--parity-bp` of A's claims AND B parked no more objects than A. It is a report: it never
writes a row, never touches settings, and never switches a model — a switch is a config change a
human makes after reading this (plan D7: no switch without parity).

Needs GENIOS_DATABASE_URL, GENIOS_CRYPTO_KEY and GENIOS_ANTHROPIC_API_KEY. Each object costs two
model calls.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from datetime import timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text  # noqa: E402

from genios_engine.capture.documents.native import extract_native_text
from genios_engine.capture.preprocess.preprocess import preprocess
from genios_engine.capture.semantic.extractor import (EventEnvelope, ExtractionRequest,
                                                      extract)
from genios_engine.capture.semantic.profiles import get_profile
from genios_engine.capture.semantic.router import RoutingInput, select_profile
from genios_engine.platform.config import get_settings
from genios_engine.platform.crypto import decrypt
from genios_engine.platform.db import get_engine

#: The claim-bearing fields of `ExtractionResult` that are compared. Scalars (intent, stance)
#: are compared separately as a single agreement bit.
CLAIM_FIELDS = ("commitments", "availability", "business_facts", "scheduling_proposals",
                "questions", "entity_mentions", "dates_mentioned", "amounts",
                "decision_states", "dependencies", "roles", "relationships",
                "implied_actions", "unclassified_observations")

_SELECT = text(
    "select e.event_id, e.object_type, e.source_object_id, e.actor, e.occurred_at, "
    "p.enc_content from source_events e join raw_payloads p on p.event_id = e.event_id "
    "where e.org_id = :org and e.source = 'screen_session' "
    "and (cast(:ot as text) is null or e.object_type = :ot) "
    "order by e.occurred_at desc limit :n")


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().casefold()


def _quote_of(item: Any) -> str | None:
    """The verbatim receipt inside a claim, wherever the claim type keeps it."""
    if isinstance(item, dict):
        for key in ("quote", "evidence_text"):
            if isinstance(item.get(key), str) and item[key].strip():
                return item[key]
        for value in item.values():
            found = _quote_of(value)
            if found:
                return found
    elif isinstance(item, list):
        for value in item:
            found = _quote_of(value)
            if found:
                return found
    return None


def claim_keys(result: Any) -> dict[str, set[str]]:
    """field -> {normalised quote (or the claim itself when it has none)}."""
    keys: dict[str, set[str]] = {}
    if result is None:
        return keys
    for name in CLAIM_FIELDS:
        items = getattr(result, name, None) or []
        out: set[str] = set()
        for item in items:
            data = item.model_dump(mode="json") if hasattr(item, "model_dump") else item
            quote = _quote_of(data)
            out.add(_norm(quote) if quote else _norm(json.dumps(data, sort_keys=True,
                                                                  default=str)))
        if out:
            keys[name] = out
    return keys


def _request(row: Any, raw: dict[str, Any], org: str) -> ExtractionRequest:
    """The same request `run_semantic_lane` would build for this landed object."""
    actor = row.actor if isinstance(row.actor, dict) else json.loads(row.actor or "{}")
    body = raw.get("body") or raw.get("snippet") or ""
    stripped = extract_native_text(mime="text/html", data=body) or body
    subject = str(raw.get("subject") or "")
    prepared = preprocess((subject + "\n\n" + stripped) if subject else stripped,
                          event_id=row.event_id)
    choice = select_profile(RoutingInput(source="screen_session", object_type=row.object_type))
    labels = raw.get("labelIds") or []
    # §3.1: the promoter renders the seat's own lines as a separate `SENT` object.
    direction = "outbound" if "SENT" in labels else "inbound"
    envelope = EventEnvelope(direction=direction, sender=actor.get("email") or "",
                             recipients=(), thread_position=1, thread_depth=1,
                             subject=subject)
    profile = get_profile(choice.profile_id)
    return ExtractionRequest(org_id=org, event_id=row.event_id, source="screen_session",
                             profile_id=profile.profile_id, tier=profile.default_tier,
                             prepared=prepared, envelope=envelope,
                             eval_time=row.occurred_at.astimezone(timezone.utc))


def _run(request: ExtractionRequest, llm: Any) -> tuple[Any, dict[str, set[str]]]:
    outcome = extract(request, llm=llm, store=None, open_lane=None)
    return outcome, claim_keys(outcome.result)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--org", required=True)
    ap.add_argument("--model-a", required=True, help="the model in production today")
    ap.add_argument("--model-b", required=True, help="the candidate")
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--object-type", default=None,
                    choices=("screen_chat_thread", "screen_chat_sent", "screen_email_thread",
                             "screen_doc"))
    ap.add_argument("--parity-bp", type=int, default=9000,
                    help="share of A's claims B must also make (basis points)")
    ap.add_argument("--json", action="store_true", help="print one JSON document instead")
    args = ap.parse_args(argv)

    s = get_settings()
    missing = [n for n, v in (("GENIOS_DATABASE_URL", s.database_url),
                              ("GENIOS_CRYPTO_KEY", s.crypto_key),
                              ("GENIOS_ANTHROPIC_API_KEY", s.anthropic_api_key)) if not v]
    if missing:
        print(f"missing settings: {', '.join(missing)}", file=sys.stderr)
        return 2
    from genios_engine.context.llm.client import LLMClient
    llm_a = LLMClient(api_key=s.anthropic_api_key, model=args.model_a)
    llm_b = LLMClient(api_key=s.anthropic_api_key, model=args.model_b)

    with get_engine(s.database_url).connect() as conn:      # read-only: no begin(), no writes
        rows = conn.execute(_SELECT, {"org": args.org, "ot": args.object_type,
                                      "n": args.limit}).all()
    if not rows:
        print(f"no screen_session events with payloads for org {args.org}", file=sys.stderr)
        return 1

    totals = {"a": Counter(), "b": Counter(), "both": Counter()}
    parked = Counter()
    tokens = Counter()
    scalar_agree = 0
    objects = []
    for row in rows:
        raw = json.loads(decrypt(bytes(row.enc_content), s.crypto_key))
        request = _request(row, raw, args.org)
        (out_a, keys_a), (out_b, keys_b) = _run(request, llm_a), _run(request, llm_b)
        for tag, out in (("a", out_a), ("b", out_b)):
            parked[tag] += out.parked is not None
            tokens[f"{tag}_in"] += out.input_tokens
            tokens[f"{tag}_out"] += out.output_tokens
        same_scalars = (out_a.result is not None and out_b.result is not None
                        and (out_a.result.intent, out_a.result.stance)
                        == (out_b.result.intent, out_b.result.stance))
        scalar_agree += same_scalars
        per_field = {}
        for name in sorted(set(keys_a) | set(keys_b)):
            a, b = keys_a.get(name, set()), keys_b.get(name, set())
            per_field[name] = {"a_only": sorted(a - b), "b_only": sorted(b - a),
                               "both": len(a & b)}
            totals["a"][name] += len(a)
            totals["b"][name] += len(b)
            totals["both"][name] += len(a & b)
        objects.append({"event_id": row.event_id, "object_type": row.object_type,
                        "profile": request.profile_id,
                        "parked_a": out_a.parked is not None,
                        "parked_b": out_b.parked is not None,
                        "scalars_agree": same_scalars, "fields": per_field})

    a_total = sum(totals["a"].values())
    both_total = sum(totals["both"].values())
    recall_bp = 10000 if a_total == 0 else both_total * 10000 // a_total
    parity = recall_bp >= args.parity_bp and parked["b"] <= parked["a"]
    summary = {"org": args.org, "objects": len(rows), "model_a": args.model_a,
               "model_b": args.model_b, "claims_a": a_total,
               "claims_b": sum(totals["b"].values()), "claims_both": both_total,
               "b_recall_of_a_bp": recall_bp, "parked_a": parked["a"], "parked_b": parked["b"],
               "scalars_agree": scalar_agree, "tokens": dict(tokens),
               "per_field": {n: {"a": totals["a"][n], "b": totals["b"][n],
                                 "both": totals["both"][n]}
                             for n in sorted(set(totals["a"]) | set(totals["b"]))},
               "parity": parity}
    if args.json:
        print(json.dumps({"summary": summary, "objects": objects}, indent=2, default=str))
        return 0

    for obj in objects:
        print(f"\n{obj['event_id']}  {obj['object_type']} -> {obj['profile']}"
              f"  parked A={obj['parked_a']} B={obj['parked_b']}"
              f"  intent/stance agree={obj['scalars_agree']}")
        for name, diff in obj["fields"].items():
            print(f"  {name:<26} both={diff['both']:<3} A-only={len(diff['a_only']):<3} "
                  f"B-only={len(diff['b_only'])}")
            for quote in diff["a_only"]:
                print(f"      A only: {quote[:110]}")
            for quote in diff["b_only"]:
                print(f"      B only: {quote[:110]}")
    print(f"\n== {len(rows)} objects · A={args.model_a} · B={args.model_b}")
    print(f"{'field':<26} {'A':>5} {'B':>5} {'both':>5}")
    for name, counts in summary["per_field"].items():
        print(f"{name:<26} {counts['a']:>5} {counts['b']:>5} {counts['both']:>5}")
    print(f"B recall of A's claims: {recall_bp / 100:.1f}%  · parked A={parked['a']} "
          f"B={parked['b']} · intent/stance agree {scalar_agree}/{len(rows)}")
    print(f"tokens: {dict(tokens)}")
    print("PARITY" if parity else "NO PARITY — keep model A", "(report only; config unchanged)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
