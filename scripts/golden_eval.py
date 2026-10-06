"""The golden set against a model — the ideal reader's recordings, or the real model, outside CI.

    python scripts/golden_eval.py --dry-run                      # what a live run would cost; no DB
    GENIOS_TEST_DATABASE_URL=… python scripts/golden_eval.py --record [F03 F07 …]
    GENIOS_TEST_DATABASE_URL=… GENIOS_GOLDEN_LIVE_KEY=sk-… python scripts/golden_eval.py \\
        --live --model claude-haiku-4-5-20251001 --spend-ok [--record] [F03 …]

`speedrun008/YC-II W27/STEP-01-PENDING-owner-rohit-and-harsh-the-golden-set.md` §3.9.

  --dry-run   Reads the cases and their cassettes and prints, per case, what wrote the cassette,
              how many model calls it holds, and what replaying them against a live model would
              cost at list price. Touches no database and no model.
  --record    Re-records cassettes with the ideal reader (`tests/replays/ideal_reader.py`) — no
              spend. A deliberate act: run it after a prompt change, never to make a case pass.
  --live      Replays the same cases against the REAL model and writes a scorecard — recall,
              precision, forbidden outputs, tokens, cost — to `speedrun008/YC-II W27/scores/`.
              Model spend is the founder's call (06-DECISIONS D12c, default: no spend), so it
              needs BOTH a key in GENIOS_GOLDEN_LIVE_KEY and `--spend-ok`. With `--record` it also
              replaces the cassettes, which then say `live:<model>`.

The live model is handed to the chain through the same doors the recorded one is
(`tests/replays/model_sites.DOORS`); the runner's transport refusal still applies to every other
client, so a site that built its own would still fail the case rather than spend unseen.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

SCORES = REPO / "speedrun008" / "YC-II W27" / "scores"
LIVE_KEY_ENV = "GENIOS_GOLDEN_LIVE_KEY"
#: List price per million tokens (input, output), for the dry-run estimate. Haiku 4.5 is the model
#: production runs every site on (`Settings.anthropic_model`).
PRICES = {"claude-haiku-4-5-20251001": (1.0, 5.0)}


def _cases(ids: list[str]):
    from tests.replays.founder_case import load_cases
    cases = load_cases()
    if ids:
        unknown = sorted(set(ids) - {c.case_id for c in cases})
        if unknown:
            raise SystemExit(f"no such case: {unknown}")
        cases = tuple(c for c in cases if c.case_id in ids)
    return cases


def dry_run(ids: list[str], model: str) -> int:
    from tests.replays import cassettes
    price_in, price_out = PRICES.get(model, PRICES["claude-haiku-4-5-20251001"])
    total_calls = total_in = total_out = 0
    print(f"{'case':<5} {'source':<16} {'calls':>5} {'tokens in':>10} {'tokens out':>10}  title")
    for case in _cases(ids):
        try:
            answers = cassettes.load(case)
            source = cassettes.source_of(case)
        except AssertionError:
            answers, source = {}, "NO CASSETTE"
        tin = sum(int(a.get("input_tokens") or 0) for a in answers.values())
        tout = sum(int(a.get("output_tokens") or 0) for a in answers.values())
        total_calls, total_in, total_out = total_calls + len(answers), total_in + tin, total_out + tout
        print(f"{case.case_id:<5} {source:<16} {len(answers):>5} {tin:>10} {tout:>10}  "
              f"{case.title[:60]}")
    cost = total_in / 1e6 * price_in + total_out / 1e6 * price_out
    print(f"\n{total_calls} model calls · {total_in} tokens in · {total_out} tokens out · "
          f"≈ ${cost:.2f} for one live pass on {model} at list price (the recorded token counts "
          "are the ideal reader's estimates). Nothing was run.")
    return 0


def record(ids: list[str], model=None, source=None) -> list:
    from tests.replays import cassettes
    from tests.replays.marking import judge
    rows = []
    for case in _cases(ids):
        run, answers = cassettes.record(case, model)
        cassettes.save(case, answers, source=source or cassettes.IDEAL_READER)
        mark = judge(case, cassettes.replay(case))
        rows.append((case, run, answers, mark))
        print(f"{case.case_id} {mark.verdict:<15} {len(answers):>3} answers  {mark.reason[:100]}")
    return rows


class LiveModel:
    """The real model, called through the transport the runner refuses to everyone else."""

    def __init__(self, api_key: str, model: str) -> None:
        from genios_engine.context.llm.client import LLMClient
        self._client = LLMClient(api_key=api_key, model=model)
        self._call = LLMClient.call            # captured BEFORE the runner refuses the transport
        self.model = model

    @staticmethod
    def content_hash(material: str) -> str:
        from genios_engine.context.llm.client import LLMClient
        return LLMClient.content_hash(material)

    def call(self, prompt: str, *, max_tokens: int = 4096, **kw):
        return self._call(self._client, prompt, max_tokens=max_tokens, **kw)


def live(ids: list[str], model: str, keep: bool) -> int:
    from tests.replays import cassettes
    from tests.replays.engine_runner import pin_scratch_database, run_case
    from tests.replays.harness import CassetteRecorder
    from tests.replays.marking import FAIL, NOT_EXERCISED, PASS, cards_about, judge

    pin_scratch_database()
    key = os.environ[LIVE_KEY_ENV]
    rows, tokens_in, tokens_out = [], 0, 0
    for case in _cases(ids):
        recorder = CassetteRecorder(LiveModel(key, model))
        run = run_case(case, recorder)
        mark = judge(case, run)
        tokens_in += sum(int(a["input_tokens"] or 0) for a in recorder.cassette.values())
        tokens_out += sum(int(a["output_tokens"] or 0) for a in recorder.cassette.values())
        if keep:
            cassettes.save(case, recorder.cassette, source=f"{cassettes.LIVE_PREFIX}{model}")
        expected = sum(len(cards_about(run, e.about)) for e in case.cards if e.min >= 1)
        rows.append({"case": case.case_id, "kind": case.kind, "verdict": mark.verdict,
                     "lost_at": mark.lost_at, "cards": len(run.cards),
                     "cards_about_the_subject": expected,
                     "forbidden": [list(h) for h in mark.forbidden_hits], "reason": mark.reason})
        print(f"{case.case_id} {mark.verdict:<15} {mark.reason[:100]}")
    detect = [r for r in rows if r["kind"] == "must_detect" and r["verdict"] != "not_expressible"]
    cards = sum(r["cards"] for r in rows)
    price_in, price_out = PRICES.get(model, (0.0, 0.0))
    card = {"model": model, "date": date.today().isoformat(), "cases": rows,
            "recall": round(sum(r["verdict"] == PASS for r in detect) / len(detect), 3)
            if detect else None,
            "precision": round(sum(r["cards_about_the_subject"] for r in rows) / cards, 3)
            if cards else None,
            "abstain_failures": sum(r["kind"] == "must_abstain" and r["verdict"] in
                                    (FAIL, NOT_EXERCISED) for r in rows),
            "forbidden_outputs": sum(len(r["forbidden"]) for r in rows),
            "tokens_in": tokens_in, "tokens_out": tokens_out,
            "cost_usd": round(tokens_in / 1e6 * price_in + tokens_out / 1e6 * price_out, 4)}
    SCORES.mkdir(parents=True, exist_ok=True)
    out = SCORES / f"{card['date']}-{model}.json"
    out.write_text(json.dumps(card, indent=1) + "\n", encoding="utf-8")
    print(f"\nrecall {card['recall']} · precision {card['precision']} · forbidden "
          f"{card['forbidden_outputs']} · ${card['cost_usd']} → {out}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="the estimate; no database, no model")
    ap.add_argument("--live", action="store_true", help="the real model (needs --spend-ok)")
    ap.add_argument("--record", action="store_true",
                    help="(re)write cassettes: with --live the live model's, alone the ideal "
                         "reader's")
    ap.add_argument("--model", default="claude-haiku-4-5-20251001")
    ap.add_argument("--spend-ok", action="store_true",
                    help="confirm that a live run may spend model money (D12c)")
    ap.add_argument("cases", nargs="*", help="case ids (default: every case)")
    args = ap.parse_args(argv)

    if args.dry_run and (args.live or args.record):
        ap.error("--dry-run runs nothing; it cannot be combined with --live or --record")
    if args.dry_run:
        return dry_run(args.cases, args.model)
    if args.live:
        if not os.environ.get(LIVE_KEY_ENV) or not args.spend_ok:
            print(f"--live spends model money: it needs a key in {LIVE_KEY_ENV} and --spend-ok "
                  "(06-DECISIONS D12c — the default is no spend). Run --dry-run for the "
                  "estimate.", file=sys.stderr)
            return 2
        return live(args.cases, args.model, args.record)
    if args.record:
        from tests.replays.engine_runner import pin_scratch_database
        pin_scratch_database()
        record(args.cases)
        return 0
    ap.error("say what to do: --dry-run, --record, or --live")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
