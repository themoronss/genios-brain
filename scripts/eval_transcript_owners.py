"""P5 · transcript owner-attribution eval — the gate on the T1 transcript profile. READ-ONLY.

    python scripts/eval_transcript_owners.py [--runs 10] [--threshold 9] [--model MODEL]
        [--fixture tests/capture/transcripts/fixtures/meet_iso_audit.txt] [--json]

WHAT IT RUNS. The fixture is parsed and split EXACTLY as the ingest door splits it
(`capture/transcripts/parse` → `ingest.build_parts`), routed by the production router
(`upload` / `meeting_transcript` → the `transcript` profile), and put through the real
`extractor.extract()` at the profile's own tier — `--runs` times, each with a FRESH fence nonce
(`secrets.token_hex(8)`) and no cache, so every run is an independent model call.

WHAT IT SCORES. Owner attribution only. A run PASSES when every expected promise is extracted
with its speaker as actor (Shalini → supplier quality records, Emru → audit checklist, Priya →
signed delivery logs), no expected promise is attributed to anyone else, and nothing is
attributed to the uploader (Rohit Mehta — a speaker who promises nothing, and the envelope's
sender: the exact person the old sender fallback filed everything against). Actors are resolved
the way Layer 2 resolves them: against the transcript's own speaker labels (exact label or
unique first name), never against anything wider.

EXIT. 0 when passes ≥ --threshold; 1 below it (keep the T2 floor: revert the profile commit);
2 when no model key is configured. Needs GENIOS_ANTHROPIC_API_KEY only — no database.
"""
from __future__ import annotations

import argparse
import json
import secrets
import sys
from datetime import datetime, time, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from genios_engine.capture.preprocess.preprocess import preprocess  # noqa: E402
from genios_engine.capture.semantic.extractor import (EventEnvelope, ExtractionRequest,  # noqa: E402
                                                      extract)
from genios_engine.capture.semantic.profiles import get_profile  # noqa: E402
from genios_engine.capture.semantic.router import RoutingInput, select_profile  # noqa: E402
from genios_engine.capture.transcripts.ingest import OBJECT_TYPE, build_parts  # noqa: E402
from genios_engine.capture.transcripts.parse import parse_transcript  # noqa: E402
from genios_engine.capture.transcripts.speakers import Candidate, resolve_label  # noqa: E402
from genios_engine.platform.config import get_settings  # noqa: E402

DEFAULT_FIXTURE = (Path(__file__).resolve().parents[1]
                   / "tests/capture/transcripts/fixtures/meet_iso_audit.txt")
#: (owner label, words that identify the promise in its action / quote)
EXPECTED: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Shalini Iyer", ("supplier quality",)),
    ("Emru Khan", ("checklist",)),
    ("Priya Shah", ("delivery log",)),
)
UPLOADER_LABEL = "Rohit Mehta"
UPLOADER_EMAIL = "rohit.mehta@voltex.example"


def _candidates(labels: tuple[str, ...]) -> list[Candidate]:
    return [Candidate(email=f"{'.'.join(l.lower().split())}@eval.invalid", name=l)
            for l in labels]


def owner_of(actor: str | None, cands: list[Candidate]) -> str | None:
    cand, _ = resolve_label(str(actor or ""), cands)
    return cand.name if cand is not None else None


def score_run(commitments: list[dict], labels: tuple[str, ...]) -> tuple[bool, list[str]]:
    """(passed, reasons). `commitments`: [{actor, action, quote}]."""
    cands = _candidates(labels)
    reasons: list[str] = []
    rows = [(owner_of(c.get("actor"), cands),
             f"{c.get('action') or ''} {c.get('quote') or ''}".casefold(), c) for c in commitments]
    for owner, words in EXPECTED:
        hits = [r for r in rows if any(w in r[1] for w in words)]
        if not hits:
            reasons.append(f"missing: {owner} → {words[0]}")
            continue
        wrong = [r for r in hits if r[0] != owner]
        if wrong:
            reasons.append(f"misattributed {words[0]!r} to "
                           f"{[r[2].get('actor') for r in wrong]} (expected {owner})")
    for who, _, c in rows:
        if who == UPLOADER_LABEL:
            reasons.append(f"attributed to the uploader: {c.get('action')!r}")
    return not reasons, reasons


def _commitments(result) -> list[dict]:
    out = []
    for item in getattr(result, "commitments", None) or []:
        spans = getattr(item, "evidence", None) or []
        quote = " ".join(getattr(s, "quote", "") or "" for s in spans)
        out.append({"actor": getattr(item, "actor", None),
                    "action": getattr(item, "action", None), "quote": quote})
    return out


def build_request(body: str, title: str, eval_time: datetime, run: int,
                  nonce: str) -> ExtractionRequest:
    choice = select_profile(RoutingInput(source="upload", object_type=OBJECT_TYPE))
    profile = get_profile(choice.profile_id)
    event_id = f"eval_owner_{run}_{nonce}"
    prepared = preprocess(f"{title}\n\n{body}", event_id=event_id)
    envelope = EventEnvelope(direction="internal", sender=UPLOADER_EMAIL, recipients=(),
                             thread_position=1, thread_depth=1, subject=title)
    return ExtractionRequest(org_id="eval_transcript_owners", event_id=event_id,
                             source="upload", profile_id=profile.profile_id,
                             tier=profile.default_tier, prepared=prepared, envelope=envelope,
                             eval_time=eval_time)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--threshold", type=int, default=9)
    ap.add_argument("--model", default=None, help="default: the configured anthropic_model")
    ap.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    s = get_settings()
    if not s.anthropic_api_key:
        print("missing settings: GENIOS_ANTHROPIC_API_KEY", file=sys.stderr)
        return 2
    from genios_engine.context.llm.client import LLMClient
    model = args.model or s.anthropic_model
    llm = LLMClient(api_key=s.anthropic_api_key, model=model)

    parsed = parse_transcript(Path(args.fixture).read_text(encoding="utf-8"),
                              filename=Path(args.fixture).name)
    parts = build_parts(parsed.turns)
    title = parsed.title or "Meeting"
    day = parsed.date or datetime.now(timezone.utc).date()
    eval_time = datetime.combine(day, time(9, 0), tzinfo=timezone.utc)
    profile = get_profile(select_profile(
        RoutingInput(source="upload", object_type=OBJECT_TYPE)).profile_id)

    runs = []
    for i in range(args.runs):
        nonce = secrets.token_hex(8)
        commitments, parked, tokens = [], [], [0, 0]
        for n, body in enumerate(parts):
            out = extract(build_request(body, title, eval_time, i, f"{nonce}_{n}"), llm=llm,
                          store=None, open_lane=None, nonce=nonce)
            tokens[0] += out.input_tokens
            tokens[1] += out.output_tokens
            if out.parked is not None or out.result is None:
                parked.append(str(getattr(out.parked, "reason_code", "no_result")))
                continue
            commitments += _commitments(out.result)
        ok, reasons = score_run(commitments, parsed.labels)
        if parked:
            ok, reasons = False, reasons + [f"parked: {parked}"]
        runs.append({"run": i + 1, "nonce": nonce, "passed": ok, "reasons": reasons,
                     "commitments": commitments, "tokens": tokens})
        if not args.json:
            print(f"run {i + 1:>2}  {'PASS' if ok else 'FAIL'}  "
                  f"({len(commitments)} commitments, {tokens[0]}+{tokens[1]} tok)"
                  + ("" if ok else f"  — {'; '.join(reasons)}"))
    passes = sum(r["passed"] for r in runs)
    summary = {"model": model, "profile": profile.profile_id, "tier": profile.default_tier,
               "max_input_chars": profile.max_input_chars, "parts": len(parts),
               "runs": len(runs), "passes": passes, "threshold": args.threshold,
               "gate": passes >= args.threshold}
    if args.json:
        print(json.dumps({"summary": summary, "runs": runs}, indent=2, default=str))
    else:
        print(f"\n{passes}/{len(runs)} runs attributed every owner correctly "
              f"(model {model}, profile {profile.profile_id} {profile.default_tier} "
              f"{profile.max_input_chars} chars, {len(parts)} part(s))")
        print("GATE PASS — keep T1" if summary["gate"]
              else "GATE FAIL — revert the transcript profile commit (T2 floor stays)")
    return 0 if summary["gate"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
