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

#: What `capture/esqe/relevance._item_block` puts in the fence when an object has no subject and no
#: snippet — every calendar event, because its text is a `summary`, not a `subject`. Production
#: asks the model about it anyway; a faithful model, told that "a guess is worse than an absence",
#: says it is not business and leaves the rest unknown.
NO_TEXT = "(no readable text)"
_NO_TEXT_VERDICT = {"business": False, "description": "no readable text", "category": "unknown",
                    "human_authored": None, "asks_for_reply": None}

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
            return {"verdicts": [{"item": int(n), **(dict(_NO_TEXT_VERDICT)
                                                     if text.strip() == NO_TEXT else
                                                     _relevance(self._match(text, site)))}
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
        authored = self._authored(site, prompt)
        if site == "r1":
            return authored if authored is not None else read_stances(prompt)
        if site == "resolution":
            return resolve_message(prompt, authored, self.case.case_id)
        if site == "bundle_narrator":
            if "CORRECTION" in prompt or "was refused" in prompt:
                raise IdealReaderError(f"{self.case.case_id}: the bundle narration was refused by "
                                       f"the gauntlet — {_excerpt(prompt[-1500:])}")
            return authored if authored is not None else narrate_decision(prompt)
        if _REFUSED in prompt:
            # The site rejected an answer this reader gave and is asking again. A recording must
            # never hold a refused answer, so the authoring error surfaces here.
            raise IdealReaderError(f"{self.case.case_id}: the {site} site refused the answer it "
                                   f"was given — {prompt[prompt.find(_REFUSED):][:400]!r}")
        if authored is None:
            raise IdealReaderError(
                f"{self.case.case_id}: the case gives the {site} site no answer for this prompt "
                f"— author model.{site} with terms the prompt names. Prompt: {_excerpt(prompt)}")
        if site == "decider":
            return decide_from_formula(prompt, authored, self.case.case_id)
        return authored

    def _authored(self, site: str, prompt: str) -> Any:
        """A site that reads a situation, not one object: the first `model[site]` entry whose
        `when` terms all appear in the prompt, or None."""
        lowered = prompt.lower()
        for entry in self.case.model.get(site) or ():
            terms = [str(t).lower() for t in entry.get("when") or ()]
            if terms and all(t in lowered for t in terms):
                return entry["answer"]
        return None

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


def _excerpt(prompt: str) -> str:
    """Enough of a situation prompt to author an answer from: its head and its situation block."""
    at = prompt.find("SITUATION:")
    return repr(prompt[:200] + (" … " + prompt[at:at + 900] if at > 0 else ""))


# ── R-1: the prompt's own reading rules, applied mechanically ───────────────────────────────────
_R1_ITEM = re.compile(r"^(\d+)\. \[([^\]]*)\] (.*)$", re.M)
_R1_HEDGES = re.compile(r"hedged \(words like ([^)]*)\)")
_COMMITMENT = re.compile(r"\b(i|we)(\s+will|'ll|\s+shall)\b|\bpromise[sd]?\b|\bcommit(ted|s)?\b",
                         re.I)
_DECISION = re.compile(r"\b(decided|confirmed|approved|signed|accepted|agreed|chose|chosen|"
                       r"selected|rejected|declined|cancelled|canceled|completed)\b", re.I)
_INTENT = re.compile(r"\b(plan(ning)? to|intend(s|ing)? to|going to|want(s)? to|aim(s|ing)? to)\b",
                     re.I)
_WEIGHING = ("consider", "evaluat", "explor", "thinking about", "looking into", "leaning")


def read_stances(prompt: str) -> dict[str, Any]:
    """R-1's answer when a case authors none: each item read by the rules R-1's own prompt states.

    The hedge words are taken from the prompt itself; a plain settled statement is not ambiguous;
    a record that disagrees with itself is; an item with no stance is NOT_INTERPRETABLE, because
    the prompt says to answer that "rather than guessing". Mechanical on purpose — R-1 classifies
    short statements, and a case that needs a different reading authors `model.r1`.
    """
    words_line = _R1_HEDGES.search(prompt)
    hedges = re.findall(r"'([^']+)'", words_line.group(1)) if words_line else []
    listing = prompt.split("ITEMS:", 1)[-1].split("\n\nAnswer with ONLY", 1)[0]
    readings = []
    for number, field_label, text in _R1_ITEM.findall(listing):
        lowered = text.lower()
        hedge = next((h for h in hedges if re.search(rf"\b{re.escape(h)}\b", lowered)), None)
        disputed = "THE RECORD DISAGREES ABOUT THIS" in field_label
        if hedge:
            stance = ("EVALUATING_ALTERNATIVES" if any(w in hedge for w in _WEIGHING)
                      else "SPECULATION_ONLY")
        elif _COMMITMENT.search(text):
            stance = "COMMITMENT_MADE"
        elif _DECISION.search(text):
            stance = "DECISION_MADE"
        elif _INTENT.search(text):
            stance = "INTENT_STATED"
        else:
            stance = "NOT_INTERPRETABLE"
        readings.append({"item": int(number), "ambiguous": bool(hedge) or disputed,
                         "classification": stance,
                         "confidence_bp": 5000 if stance == "NOT_INTERPRETABLE" else 6000})
    return {"readings": readings}


# ── the decider: the formula's utilities, moved only where the case says why ────────────────────
_PLAY = re.compile(r"^- play_id=([^ |]+) \|.*formula utility (\d+)", re.M)
#: The answer template names exactly the plays the decider must score (`parse_answer` refuses any
#: other set): the ELIGIBLE ones, which can be fewer than the plays the prompt lists.
_TEMPLATE_SCORES = re.compile(r'"scores": \{(.*?)\}, "confidence_bp"', re.S)
_TEMPLATE_KEY = re.compile(r'"([^"]+)": "<int 0-10000>"')
#: How every situation-level site asks again after refusing an answer.
_REFUSED = "CORRECTION — your previous answer was refused"


def decide_from_formula(prompt: str, authored: dict[str, Any], case_id: str) -> dict[str, Any]:
    """The decider's answer: `outcome`, `confidence_bp`, `rationale` and `missing` as authored, and
    a utility for EVERY eligible play the prompt lists — the formula's own, as the prompt says to
    start from, moved only where the case names the play in `move`. A move naming no listed play is
    an authoring error, not a play to invent."""
    listed = {pid: int(n) for pid, n in _PLAY.findall(prompt)}
    template = _TEMPLATE_SCORES.search(prompt)
    required = _TEMPLATE_KEY.findall(template.group(1)) if template else list(listed)
    if not required:
        raise IdealReaderError(f"{case_id}: a decider prompt listing no eligible play")
    unpriced = [pid for pid in required if pid not in listed]
    if unpriced:
        raise IdealReaderError(f"{case_id}: plays to score with no formula utility shown: "
                               f"{unpriced}")
    plays = {pid: listed[pid] for pid in required}
    scores = dict(plays)
    for name, utility in (authored.get("move") or {}).items():
        hits = [pid for pid in plays if pid == name or pid.endswith("." + name)]
        if len(hits) != 1:
            raise IdealReaderError(f"{case_id}: decider move {name!r} names {len(hits)} of the "
                                   f"listed plays {sorted(plays)}")
        scores[hits[0]] = int(utility)
    outcome = authored.get("outcome")
    if outcome not in ("decision", "defer"):
        raise IdealReaderError(f"{case_id}: decider outcome {outcome!r} is not decision | defer")
    return {"outcome": outcome, "scores": scores,
            "confidence_bp": int(authored["confidence_bp"]),
            "rationale": str(authored.get("rationale") or ""),
            "missing": list(authored.get("missing") or [])}


# ── the bundle narrator: the fixed decision, told from its own material ─────────────────────────
_COMMITTED = re.compile(r"committed action\s*:\s*(\S+)")


def narrate_decision(prompt: str) -> dict[str, str]:
    """The bundle narrator's answer when a case authors none: a plain narration of the decision
    the prompt fixes, from that prompt's material alone.

    The narrator's prompt names the committed action and a catalogue of computed numbers, and
    forbids everything else — digits, unnamed entities, instructions outside the rationale. So
    this says what a faithful model can say from it: the action, by its own label; the priced
    numbers, by placeholder; nothing about who it concerns, because the prompt names nobody.
    """
    committed = _COMMITTED.search(prompt)
    if committed is None:
        raise IdealReaderError("a bundle narration prompt with no committed action")
    label = committed.group(1).rsplit(".", 1)[-1].replace("_", " ").strip()
    has = {name for name in re.findall(r"^\s*\{(\w+)\} =", prompt, re.M)}

    def number(name: str, text: str, fallback: str) -> str:
        return text if name in has else fallback

    out = {
        "headline": (label[:1].upper() + label[1:])[:90],
        "situation_summary": f"The {label} is the action this decision committed to.",
        "why_it_matters": number(
            "do_nothing_cost_bp",
            "Leaving it alone carries a priced inaction cost of {do_nothing_cost_bp} basis points.",
            f"Leaving it alone leaves the {label} undone, and its cost is not priced."),
        "root_cause": number(
            "confidence_pct",
            "The engine holds this reading at {confidence_pct} percent confidence.",
            f"The reading behind the {label} rests on what the units found."),
        "recommendation_rationale": number(
            "recommended_score_pct",
            f"The {label} ranked first at {{recommended_score_pct}} percent, ahead of every "
            "alternative that lost.",
            f"The {label} ranked first, ahead of every alternative that lost."),
        "expected_effect": number(
            "outcome_window_days",
            f"Acting on the {label} shows its effect within {{outcome_window_days}} days, and "
            "without it the situation stands as it is.",
            f"Acting on the {label} changes the situation, and without it the situation stands "
            "as it is."),
    }
    if "WHAT ELSE WAS ON THE TABLE" in prompt and "runner_up_score_pct" in has:
        out["alternatives_narrative"] = ("The strongest alternative scored "
                                         "{runner_up_score_pct} percent and lost to the "
                                         "recommendation.")
    return out


# ── resolution: does the message SAY an obligation is complete? ─────────────────────────────────
_ASKS = re.compile(r"\?|\b(could|can|would|will) you\b|\bplease\b|\blet me know\b|\bi'?ll\b|"
                   r"\bwe'?ll\b|\bwill\b|\bplan\b", re.I)


def resolve_message(prompt: str, authored: dict[str, Any] | None, case_id: str) -> dict[str, Any]:
    """The resolution site's answer. A case that knows a message reports completion authors it
    (`model.resolution`: verdict, certainty, scope and a `quote`, whose offsets are found here);
    otherwise the message is read as stating no completion — NOT_RESOLVED, quoting its first ask or
    question as INTENT_ONLY, or its first line as AMBIGUOUS. The prompt's own rule: "If you cannot
    point at a sentence, the verdict is NOT_RESOLVED"."""
    fenced = _FENCED.findall(prompt)
    if len(fenced) != 1:
        raise IdealReaderError(f"{case_id}: a resolution prompt holds {len(fenced)} messages")
    message = fenced[0]
    if authored is not None:
        span = re.search(r"\s+".join(re.escape(w) for w in str(authored["quote"]).split()), message)
        if span is None:
            raise IdealReaderError(f"{case_id}: resolution quote {authored['quote']!r} is not in "
                                   "the message")
        return {"verdict": authored["verdict"], "certainty": authored["certainty"],
                "scope": list(authored.get("scope") or ()), "quote": span.group(0),
                "start_offset": span.start(), "end_offset": span.end(),
                "speaker_role_said": authored.get("speaker_role_said", "unknown")}
    sentences = [m for m in re.finditer(r"[^\n.?!]+[.?!]?", message) if m.group(0).strip()]
    if not sentences:
        raise IdealReaderError(f"{case_id}: a resolution prompt with an empty message")
    ask = next((m for m in sentences if _ASKS.search(m.group(0))), None)
    chosen = ask or sentences[0]
    start = chosen.start() + (len(chosen.group(0)) - len(chosen.group(0).lstrip()))
    end = chosen.start() + len(chosen.group(0).rstrip())
    return {"verdict": "NOT_RESOLVED", "certainty": "INTENT_ONLY" if ask else "AMBIGUOUS",
            "scope": [], "quote": message[start:end], "start_offset": start, "end_offset": end,
            "speaker_role_said": "unknown"}
