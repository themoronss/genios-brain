"""The ideal reader — a founder case's answers, served to the real prompts so they can be recorded.

`speedrun008/YC-II W27/STEP-01-NEXT-the-golden-set.md` §3.2. A golden case is replayed with the
model's answers recorded (`harness.RecordedLLM`). Something has to give those answers the first
time, and spend on the live model is the founder's call (`06-DECISIONS.md` D12). So each case
writes them down — per object in `read`, per situation in `model` — and this reader serves them to
the prompts the real chain builds, through `harness.CassetteRecorder`, into the case's cassette.

**What an answer is.** What a faithful model answers to the prompt AS WRITTEN: production's own
verdict where `04-NOW-VS-SHOULD-VS-EXPECTED.md` §2 records it (the AI filter junked the 30 Sep
portal mail; Boardy's one mail was "junk, not sure"), and a careful reading of the prompt
otherwise. Never the answer the founder wishes the model gave. A prompt that tells the junk filter
to drop automated mail drops a government portal's mail, and when that loses a live application
the failure is the engine's — the exam has to show it, not answer around it.

**It refuses to guess.** A prompt about no object of the case, a site the case gives no answer
for, a quote the content does not contain, an extraction the schema rejects — each raises
`IdealReaderError`, a `BaseException` for the reason `CassetteMiss` is one: every model site in
the chain sits inside `except Exception`, and a swallowed refusal would record a cassette with a
hole in it.
"""
from __future__ import annotations

import json
import re
from typing import Any

from tests.replays.founder_case import CaseObject, FounderCase
from tests.replays.harness import identify_site

MODEL = "claude-haiku-4-5-20251001"

#: The claim lists of `ExtractionResult` that carry a `confidence_bp` — defaulted when authored
#: without one, because a case states WHAT was said, and a confidence would be a number invented
#: by its author.
_CLAIM_LISTS = ("entity_mentions", "commitments", "decision_states", "dependencies",
                "business_facts", "questions", "roles", "availability",
                "unclassified_observations")
_DEFAULT_CONFIDENCE_BP = 9000

_GATE_KEEP = {"disposition": "keep", "relevance": 0.9, "reason": "a person writing to the founder"}
_GATE_DROP = {"disposition": "drop", "relevance": 0.05,
              "reason": "automated, nobody waits on a reply"}

_FENCED = re.compile(r"<<<CONTENT_[0-9a-f]+>>>\n(.*?)\n<<<END_[0-9a-f]+>>>", re.S)
_RELEVANCE_ITEM = re.compile(r"^item (\d+):\n<<<CONTENT_[0-9a-f]+>>>\n(.*?)\n<<<END_[0-9a-f]+>>>",
                             re.S | re.M)
_BATCH_ITEM = re.compile(r"^\[(\d+)\] ", re.M)


class IdealReaderError(BaseException):
    """The case does not answer this prompt. Author the answer; never let the reader guess."""


class IdealReader:
    """Answers a case's prompts as the case wrote them down. `LLMClient`'s `.model` / `.call()`."""

    model = MODEL

    def __init__(self, case: FounderCase) -> None:
        self.case = case
        self._mail = [o for o in case.objects if o.source == "gmail"]

    @staticmethod
    def content_hash(material: str) -> str:
        from genios_engine.context.llm.client import LLMClient
        return LLMClient.content_hash(material)

    def call(self, prompt: str, *, max_tokens: int = 4096, **_kw: Any):
        from genios_engine.context.llm.client import LLMResult
        site = identify_site(prompt)
        answer = self._answer(site, prompt)
        raw = json.dumps(answer, ensure_ascii=False)
        return LLMResult(parsed=answer, raw=raw, input_tokens=len(prompt) // 4,
                         output_tokens=max(1, len(raw) // 4), model=self.model)

    # ── per site ─────────────────────────────────────────────────────────────────────────────
    def _answer(self, site: str, prompt: str) -> Any:
        if site == "junk_gate":
            return _gate(self._match(prompt.split("EMAIL:\n", 1)[-1], site))
        if site == "junk_gate_batch":
            listing = prompt.split("EMAILS:\n", 1)[-1]
            marks = list(_BATCH_ITEM.finditer(listing))
            out = []
            for n, m in enumerate(marks):
                end = marks[n + 1].start() if n + 1 < len(marks) else len(listing)
                obj = self._match(listing[m.end():end], site)
                out.append({"i": int(m.group(1)), **_gate(obj)})
            return out
        if site == "relevance":
            items = _RELEVANCE_ITEM.findall(prompt)
            if not items:
                raise IdealReaderError("relevance prompt with no fenced items")
            return {"verdicts": [{"item": int(n), **_relevance(self._match(text, site))}
                                 for n, text in items]}
        if site == "extraction":
            fenced = _FENCED.findall(prompt)
            if len(fenced) != 1:
                raise IdealReaderError(f"an extraction prompt holds {len(fenced)} fenced regions")
            content = fenced[0]
            return _extraction(self._match(content, site), content)
        if site == "unknown":
            raise IdealReaderError("a prompt no known site writes (identify_site: unknown): "
                                   f"{prompt[:160]!r}")
        return self._case_level(site, prompt)

    def _case_level(self, site: str, prompt: str) -> Any:
        """A site that reads a situation, not one object: the first `model[site]` entry whose
        `when` terms all appear in the prompt."""
        lowered = prompt.lower()
        for entry in self.case.model.get(site) or ():
            terms = [str(t).lower() for t in entry.get("when") or ()]
            if terms and all(t in lowered for t in terms):
                return entry["answer"]
        raise IdealReaderError(
            f"{self.case.case_id}: the case gives the {site} site no answer for this prompt — "
            f"author model.{site} with the terms it names. Prompt opens: {prompt[:300]!r}")

    def _match(self, text: str, site: str) -> CaseObject:
        """The one object of the case this text is about, by how much of it the text contains."""
        seen = _norm(text)
        scored = []
        for obj in self._mail:
            pieces = [obj.subject, *(a.filename for a in obj.attachments),
                      *(s for s in re.split(r"(?<=[.?!])\s+|\n+", obj.body)
                        if len(s.strip()) >= 12)]
            score = sum(len(p) for p in {_norm(p) for p in pieces if p} if p and p in seen)
            if score:
                scored.append((score, obj.object_id, obj))
        if not scored:
            raise IdealReaderError(f"{self.case.case_id}: no object of the case is in this "
                                   f"{site} prompt: {text[:160]!r}")
        scored.sort(key=lambda t: (-t[0], t[1]))
        if len(scored) > 1 and scored[0][0] == scored[1][0]:
            raise IdealReaderError(f"{self.case.case_id}: the {site} prompt matches "
                                   f"{scored[0][1]} and {scored[1][1]} equally — make their "
                                   "text distinct")
        return scored[0][2]


# ── answers ──────────────────────────────────────────────────────────────────────────────────────
def _gate(obj: CaseObject) -> dict[str, Any]:
    answer = obj.read.get("gate")
    if answer == "keep":
        return dict(_GATE_KEEP)
    if answer == "drop":
        return dict(_GATE_DROP)
    if isinstance(answer, dict) and answer.get("disposition") in ("keep", "drop"):
        return {"disposition": answer["disposition"],
                "relevance": float(answer.get("relevance", 0.5)),
                "reason": str(answer.get("reason") or "")}
    raise IdealReaderError(f"{obj.provider_id}: no answer for the junk filter (read.gate)")


def _relevance(obj: CaseObject) -> dict[str, Any]:
    answer = obj.read.get("relevance")
    description = " ".join(obj.subject.split())[:80]
    if answer == "business":
        return {"business": True, "description": description, "category": "working",
                "human_authored": True, "asks_for_reply": None}
    if answer == "not_business":
        return {"business": False, "description": description, "category": "automated",
                "human_authored": False, "asks_for_reply": False}
    if isinstance(answer, dict) and isinstance(answer.get("business"), bool):
        return {"description": description, **answer}
    raise IdealReaderError(f"{obj.provider_id}: no answer for relevance (read.relevance)")


def _extraction(obj: CaseObject, content: str) -> dict[str, Any]:
    authored = obj.read.get("extraction")
    if not isinstance(authored, dict):
        raise IdealReaderError(f"{obj.provider_id}: no answer for extraction (read.extraction)")
    answer = _cite(authored, content, obj)
    for key in _CLAIM_LISTS:
        for claim in answer.get(key) or ():
            claim.setdefault("confidence_bp", _DEFAULT_CONFIDENCE_BP)
    from pydantic import ValidationError
    try:
        validate_extraction(answer)
    except ValidationError as e:
        raise IdealReaderError(f"{obj.provider_id}: the authored extraction does not fit the "
                               f"schema the prompt states: {e}") from None
    return answer


def validate_extraction(answer: dict[str, Any]):
    """The answer as the extractor would accept it: stamped with what the extractor stamps (the
    span's `source_ref`, the model and versions) and validated against `ExtractionResult`."""
    from genios_engine.contracts.extraction import ExtractionResult
    return ExtractionResult.model_validate({
        **_stamp(answer), "model_snapshot": MODEL, "prompt_version": "-", "schema_version": "-",
        "extraction_profile": "email", "input_tokens": 0, "output_tokens": 0})


def _stamp(node: Any) -> Any:
    if isinstance(node, list):
        return [_stamp(v) for v in node]
    if not isinstance(node, dict):
        return node
    out = {k: _stamp(v) for k, v in node.items()}
    if {"quote", "start_offset", "end_offset"} <= set(node):
        out["source_ref"] = "prepared_content:evt_golden"
    return out


def _cite(node: Any, content: str, obj: CaseObject) -> Any:
    """Authored `quote` / `quotes` → `evidence` spans with offsets into `content`."""
    if isinstance(node, list):
        return [_cite(v, content, obj) for v in node]
    if not isinstance(node, dict):
        return node
    out = {k: _cite(v, content, obj) for k, v in node.items() if k not in ("quote", "quotes")}
    quotes = [node["quote"]] if "quote" in node else list(node.get("quotes") or ())
    if quotes:
        out["evidence"] = [_span(str(q), content, obj) for q in quotes]
    return out


def _span(quote: str, content: str, obj: CaseObject) -> dict[str, Any]:
    """The quote's place in the content. Whitespace may differ (the body is prepared before the
    extractor sees it); the span then quotes the content's own characters, so
    `content[start:end] == quote` holds exactly — the check ALG-08 makes."""
    pattern = r"\s+".join(re.escape(w) for w in quote.split())
    m = re.search(pattern, content)
    if not quote.strip() or m is None:
        raise IdealReaderError(f"{obj.provider_id}: quote {quote!r} is not in the content the "
                               "extractor was shown")
    return {"quote": m.group(0), "start_offset": m.start(), "end_offset": m.end()}


def _norm(text: str) -> str:
    return " ".join(str(text).split()).lower()
