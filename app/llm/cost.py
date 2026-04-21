"""LLM cost table (USD per 1M tokens). Update when providers change pricing."""

PRICING = {
    # Groq — https://groq.com/pricing
    ("groq", "llama-3.3-70b-versatile"): {"input": 0.59, "output": 0.79},
    ("groq", "llama-3.1-8b-instant"):    {"input": 0.05, "output": 0.08},

    # Gemini — https://ai.google.dev/pricing
    ("gemini", "gemini-2.5-flash"):     {"input": 0.075, "output": 0.30},
    ("gemini", "gemini-2.0-flash"):     {"input": 0.10,  "output": 0.40},
    ("gemini", "gemini-embedding-001"): {"input": 0.0,   "output": 0.0},

    # Anthropic — wired for Phase 1.5
    ("anthropic", "claude-haiku-4-5-20251001"): {"input": 1.00, "output": 5.00},
    ("anthropic", "claude-sonnet-4-6"):         {"input": 3.00, "output": 15.00},
}


def calc_cost_usd(provider: str, model: str, in_tok: int, out_tok: int) -> float:
    p = PRICING.get((provider, model))
    if not p:
        return 0.0
    return (in_tok * p["input"] + out_tok * p["output"]) / 1_000_000
