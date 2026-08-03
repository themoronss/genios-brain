from __future__ import annotations

from dataclasses import dataclass, field

from genios_engine.context.llm.client import LLMClient

from .prompt import B3_PROMPT

# B3 — the single combined call: relevance judgment + typed extraction with evidence.
# The ONLY LLM in L2. temp-0, one repair retry. Output is CANDIDATES (not graph rows) —
# B4 validates evidence spans, B5 resolves identity, B7 commits.


@dataclass
class Extraction:
    relevance: float
    noise_type: str
    domains: list
    entity_mentions: list
    fact_candidates: list
    commitments: list
    questions: list
    observations: list
    input_tokens: int = 0
    output_tokens: int = 0
    ok: bool = True
    error: str | None = None
    raw: str = ""


def build_prompt(source: str, content: str) -> str:
    return B3_PROMPT.format(source=source, content=(content or "")[:8000])


def _lst(p: dict, key: str) -> list:
    v = p.get(key)
    return v if isinstance(v, list) else []


def extract(llm: LLMClient, *, source: str, content: str) -> Extraction:
    prompt = build_prompt(source, content)
    res = llm.call(prompt)
    if not res.ok:                          # one repair retry (temp-0 wobble / truncation)
        res = llm.call(prompt)
    if not res.ok:
        return Extraction(0.0, "", [], [], [], [], [], [],
                          res.input_tokens, res.output_tokens, ok=False,
                          error=res.error, raw=res.raw)
    p = res.parsed
    try:
        rel = float(p.get("relevance", 0.0) or 0.0)
    except (TypeError, ValueError):
        rel = 0.0
    return Extraction(
        relevance=max(0.0, min(1.0, rel)),
        noise_type=str(p.get("noise_type", "none") or "none"),
        domains=_lst(p, "domains"),
        entity_mentions=_lst(p, "entity_mentions"),
        fact_candidates=_lst(p, "fact_candidates"),
        commitments=_lst(p, "commitments"),
        questions=_lst(p, "questions"),
        observations=_lst(p, "observations"),
        input_tokens=res.input_tokens, output_tokens=res.output_tokens,
        ok=True, raw=res.raw)
