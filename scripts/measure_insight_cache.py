"""Does the screen-insight rulebook actually cache? Ask the tokenizer, not an estimate.

Haiku 4.5 caches no prefix shorter than 4,096 tokens, and a short one fails SILENTLY — the flag
is accepted, `cache_creation_input_tokens` comes back 0, and the bill is unchanged. Characters
are not a proxy: Hinglish and JSON tokenize very differently from English prose. So this asks
`messages.count_tokens` for the real number.

    ANTHROPIC_API_KEY=... python scripts/measure_insight_cache.py

It counts tokens only (no completion), so it costs nothing beyond a token-count request. It
prints the rulebook, a typical dynamic half, and what one check costs at each cache hit rate —
the arithmetic that decides whether the rulebook is worth its size.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from genios_engine.reason.moments import screen_insight as SI   # noqa: E402

SCREEN = ("Priya Shah: kal tak revised quote bhej dena\n"
          "You: haan, kal subah bhej deta hoon\n"
          "Priya Shah: aur MSA ka signed copy bhi")


def count(client, model: str, text: str) -> int:
    return int(client.messages.count_tokens(
        model=model, messages=[{"role": "user", "content": text}]).input_tokens)


def main() -> int:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("ANTHROPIC_API_KEY is not set — this measurement needs the real tokenizer.")
        return 2
    from anthropic import Anthropic

    from genios_engine.reason.llm_sites import tier_model
    model = tier_model("T1")
    client = Anthropic(api_key=key)

    whole = SI.build_prompt(app="whatsapp", screen=SCREEN, facts=[],
                            now_local=SI.local_label(__import__("datetime").datetime.now(
                                __import__("datetime").timezone.utc), "Asia/Kolkata"))
    rulebook = whole[:SI.RULEBOOK_CHARS]
    dynamic = whole[SI.RULEBOOK_CHARS:]
    try:
        r, d = count(client, model, rulebook), count(client, model, dynamic)
    except Exception as e:      # noqa: BLE001 — an unusable key is an answer, not a traceback
        print(f"could not count tokens: {e}")
        print("\nThe rulebook is "
              f"{SI.RULEBOOK_CHARS} characters. At 3.2-4.5 characters per token that is roughly "
              f"{SI.RULEBOOK_CHARS // 45 * 10}-{SI.RULEBOOK_CHARS // 32 * 10} tokens — an "
              "ESTIMATE, which is exactly what this script exists to replace. Run it again with "
              "a working key before trusting any cache number.")
        return 3

    print(f"model            {model}")
    print(f"rulebook         {SI.RULEBOOK_CHARS:>6} chars  {r:>6} tokens "
          f"({SI.RULEBOOK_CHARS / max(r, 1):.2f} chars/token)")
    print(f"dynamic half     {len(dynamic):>6} chars  {d:>6} tokens")
    print(f"minimum to cache {SI.RULEBOOK_TOKENS_MIN:>6} tokens  → "
          f"{'CACHES' if r >= SI.RULEBOOK_TOKENS_MIN else 'DOES NOT CACHE (silently)'}")
    if r < SI.RULEBOOK_TOKENS_MIN:
        print(f"  short by {SI.RULEBOOK_TOKENS_MIN - r} tokens — add few-shots, do not pad")
    print()
    print(f"uncached, per check          {r + d:>6} tokens")
    for hit in (0.8, 0.9, 0.95):
        eff = (hit * 0.1 + (1 - hit) * 1.25) * r + d
        print(f"cached, {hit:.0%} hit rate        {eff:>6.0f} tokens "
              f"({(eff / (r + d) - 1) * 100:+.0f}% vs uncached)")
    print("\nA cache read is 0.1x and a write 1.25x, so a seat that checks once in a long while "
          "pays MORE for a big rulebook than a small one. The hit rate is the whole argument.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
