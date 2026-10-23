"""The card writer's live probe — one or two real calls before any tenant is armed (GeniOS-011 S34.U3, C1).

⛔ BLOCKED ON ROHIT'S YES TO SPEND. Run without `--live` it builds the prompt for each invented card, prints its size
and the pre-flight price at the site's ceiling, and calls nothing. With `--live` it makes at most two calls
(`--calls 1|2`) on the R-10 site's own tier, with thinking off and the site's ceiling, and prints what came back.

    python scripts/card_copy_probe.py                    # dry: the prompts and their price; no call, no spend
    python scripts/card_copy_probe.py --live --calls 1   # one real call (needs the Anthropic key in settings)

WHY (memory: claude5-thinks-by-default; `reason/bundle/sites.SITE_MAX_OUTPUT_TOKENS`): Claude 5 models think unless
told not to and spend their thinking from `max_tokens`. R-10 asks with thinking OFF and its 1,600-token ceiling is
`[MODELLED]`. Before a paid pass the first call says: the model the tier names, input and output tokens against the
ceiling (output near 1,600 means the ceiling is too low or the model thought anyway), whether it was cut, what
stood and what the check dropped, and what it cost. Read those, then size the ceiling — never the other way round.

INVENTED CARDS ONLY: the golden set's names (`tests/replays/founder_case.REAL_NAMES` is the deny-list), never a
tenant's mail. The spend is printed here; a probe has no tenant, so it is not written to `llm_costs`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from genios_engine.deliver import card_copy as CC  # noqa: E402
from genios_engine.platform.l4_activation import FEATURE_CARD_COPY  # noqa: E402
from genios_engine.reason.bundle.budget import NarrativeBudget  # noqa: E402
from genios_engine.reason.bundle.budget import estimate_micro_usd  # noqa: E402
from genios_engine.reason.bundle.gate import RSiteGate  # noqa: E402
from genios_engine.reason.bundle.sites import SITE_CARD_COPY  # noqa: E402
from genios_engine.reason.bundle.sites import max_output_tokens  # noqa: E402
from genios_engine.reason.bundle.sites import tier_for  # noqa: E402
from genios_engine.reason.llm_sites import InMemorySiteCache  # noqa: E402
from genios_engine.reason.llm_sites import tier_model  # noqa: E402

ORG = "probe_card_copy"

#: Two invented cards: an investor's ask with a move and a goal, and a formula card with no expert lines.
CARDS = [
    ({"signal_id": "probe_1", "file_id": "probe_file_1", "business_subject": "Tara Sethi",
      "relationship_role": "investor", "why_now": "Tara Sethi asked for the deck before the call",
      "success_signal": "Tara has your deck and a call is booked", "outcome_window_days": 3,
      "_quotes": [{"quote": "could you send me your deck before we speak on Thursday?", "event_id": "evt_p1",
                   "name": "Tara Sethi", "author": "tara@kestrel.example", "source_verified": True}],
      "_facts": {"party.name": {"value": "Tara Sethi"}, "party.company": {"value": "Kestrel Capital"}}},
     {"headline": "Send Tara Sethi your deck to read ahead of a call",
      "situation": "An investor your connector introduced has asked for your deck"},
     {"capability_render": {"gold": {
         "subject": "Tara Sethi", "company": "Kestrel Capital", "role": "investor",
         "recommended": {"what": "Send Tara Sethi your deck to read ahead of a call, and offer her two times "
                                 "for the call", "by_when": "2026-10-29", "to": "Tara Sethi"},
         "alternative": "Ask Tara Sethi which day suits her"}}}),
    ({"signal_id": "probe_2", "business_subject": "Sofia Brandt", "relationship_role": "customer",
      "unresolved_item": "a twenty-minute product demo", "outcome_window_days": 5,
      "_quotes": [{"quote": "could we do a twenty-minute product demo next week?", "event_id": "evt_p2",
                   "name": "Sofia Brandt", "author": "sofia@ferngrove.example", "source_verified": True}],
      "_facts": {"party.name": {"value": "Sofia Brandt"}, "thread.ball_in_court": {"value": "us"}}},
     {"headline": "Reply to Sofia Brandt", "situation": "Sofia Brandt asked for a product demo next week"},
     {}),
]
GOALS = ({"line_id": "cbl_probe_seed", "text": "Close the seed round by December"},)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--live", action="store_true", help="make real calls (spends money: Rohit's yes first)")
    parser.add_argument("--calls", type=int, default=1, choices=(1, 2), help="how many cards to ask about")
    args = parser.parse_args(argv)

    ceiling = max_output_tokens(SITE_CARD_COPY)
    model = tier_model(tier_for(SITE_CARD_COPY))
    print(f"site {SITE_CARD_COPY} · tier {tier_for(SITE_CARD_COPY)} · model {model} · thinking off · "
          f"ceiling {ceiling} tokens")
    for card, copy, signal in CARDS[:args.calls]:
        prompt = CC.build_prompt(CC.card_facts(card, copy, signal, goals=GOALS))
        price = estimate_micro_usd(site=SITE_CARD_COPY, prompt_chars=len(prompt), max_output_tokens=ceiling)
        print(f"\n{card['signal_id']}: prompt {len(prompt)} characters · at most ${price / 1e6:.4f}")
    if not args.live:
        print("\ndry run — no call made, nothing spent. Add --live only on Rohit's yes to spend.")
        return 0

    from genios_engine.platform.config import get_settings
    from genios_engine.context.llm.client import LLMClient

    key = get_settings().anthropic_api_key
    if not key:
        print("no Anthropic key in settings — nothing called", file=sys.stderr)
        return 2
    client = LLMClient(api_key=key, model=model)
    gate = RSiteGate(org_id=ORG, engine=None, client=client, activated=frozenset({FEATURE_CARD_COPY}),
                     budget=NarrativeBudget.for_site(SITE_CARD_COPY, org_id=ORG, engine=None))
    writer = CC.CopyWriter(org_id=ORG, gate=gate, cache=InMemorySiteCache(), goals=GOALS)

    class Printed:
        def set_copy(self, org_id, card_id, stored, *, version, headline):
            print(json.dumps(stored, indent=1, ensure_ascii=False))
            return True

    for card, copy, signal in CARDS[:args.calls]:
        writer.write(Printed(), card_id=card["signal_id"], version=1, card=card, copy=copy, signal=signal)
        r = writer.last_receipt
        print(f"{card['signal_id']}: outcome {r.outcome} · model {r.model} · in {r.input_tokens} · out "
              f"{r.output_tokens} of {ceiling} · ${r.cost_micro_usd / 1e6:.4f} · {', '.join(r.reason_codes)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
