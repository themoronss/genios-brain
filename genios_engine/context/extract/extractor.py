from __future__ import annotations

from dataclasses import dataclass, field

from genios_engine.context.llm.client import LLMClient

from .envelope import Envelope
from .prompt import B3_PROMPT
from .vocab import field_vocabulary, vocabulary_note

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
    # WHO each party is in this exchange. Absent from the contract until now, which is why every
    # rule could only ask "did somebody write" and never "did the person who owes us an answer
    # write" — a connector, an introducer and the actual counterparty were the same thing.
    roles: list = field(default_factory=list)
    #: WHAT KIND of relationship each party is in — the lens L3/L4 reason under.
    relationships: list = field(default_factory=list)
    # Availability and time offers, split out of `commitments`. Nobody owes anything until a
    # time is agreed, and conflating the two minted commitment nodes with invented due dates
    # from sentences like "Can we do next week?".
    scheduling_proposals: list = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    ok: bool = True
    error: str | None = None
    raw: str = ""


def build_prompt(source: str, content: str, *,
                 envelope: Envelope | None = None,
                 effective: dict | None = None) -> str:
    """The extraction prompt for THIS tenant and THIS message.

    Two things used to be missing and both were structural. The envelope carries direction and
    parties, without which an outbound offer reads as an inbound request. The pack vocabulary
    carries the field and observation names the tenant's rules actually consult, without which
    the model invents synonyms that are stored and never read.

    Both default to absent so an unmigrated caller still works: no envelope means the prompt is
    told the direction is unknown rather than being handed a guess.
    """
    env = (envelope or Envelope()).as_prompt_fields()
    return B3_PROMPT.format(
        source=source,
        content=(content or "")[:8000],
        vocab_note=vocabulary_note(effective),
        field_names="  " + " · ".join(field_vocabulary(effective)),
        **env)


def _lst(p: dict, key: str) -> list:
    v = p.get(key)
    return v if isinstance(v, list) else []


def extract(llm: LLMClient, *, source: str, content: str,
            envelope: Envelope | None = None, effective: dict | None = None) -> Extraction:
    prompt = build_prompt(source, content, envelope=envelope, effective=effective)
    res = llm.call(prompt)
    if not res.ok:                          # one repair retry (temp-0 wobble / truncation)
        res = llm.call(prompt)
    if not res.ok:
        return Extraction(0.0, "", [], [], [], [], [], [],
                          input_tokens=res.input_tokens, output_tokens=res.output_tokens,
                          ok=False, error=res.error, raw=res.raw)
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
        roles=_lst(p, "roles"),
        relationships=_lst(p, "relationships"),
        scheduling_proposals=_lst(p, "scheduling_proposals"),
        input_tokens=res.input_tokens, output_tokens=res.output_tokens,
        ok=True, raw=res.raw)
