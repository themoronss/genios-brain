from __future__ import annotations

import json
import re
from datetime import datetime

# E1 · Copy Renderer + validators (§5.10, §5.18). ONE temp-0 call fills headline, situation and
# the artifact together. Two deterministic gates stand between the model and the user:
#   V-01 length caps  — headline ≤60, situation ≤140 → reject + re-template (never truncate, Law 3)
#   V-02 invention    — every name/number/date in the output must exist in the fact set, else
#                       reject + raw-slot fallback (the hallucination guard, Law 2)
# The fallback is pure slot-interpolation from facts, so a card ALWAYS ships and is always honest.

HEADLINE_CAP = 60
SITUATION_CAP = 140


def _digit_runs(s: str) -> set[str]:
    return set(re.findall(r"\d+", s))


def _proper_nouns(s: str) -> list[str]:
    """Capitalised, non-sentence-initial alphabetic tokens — the shape of a name or company."""
    out: list[str] = []
    for sent in re.split(r"[.!?]\s+", s):
        for i, w in enumerate(sent.split()):
            core = re.sub(r"[^A-Za-z0-9]", "", w)
            if i == 0 or len(core) < 2 or not core.isalpha():
                continue                          # sentence-initial cap is grammar, not a name
            if core[0].isupper():
                out.append(core)
    return out


def _expand_dates(s: str) -> list[str]:
    """A faithful reformatting of a fact date is NOT invention: expand any ISO date in the facts
    into its human forms (month name + abbr + day + year) so 'July 22' for 2026-07-22 is grounded
    — while a hallucinated 'March 22' stays ungrounded (wrong month word) and is still rejected."""
    out: list[str] = []
    for m in re.finditer(r"\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2})?", s):
        try:
            dt = datetime.fromisoformat(m.group(0).replace(" ", "T"))
        except ValueError:
            continue
        mon, abbr = dt.strftime("%B").lower(), dt.strftime("%b").lower()
        out += [mon, abbr, str(dt.day), str(dt.year), f"{mon} {dt.day}"]
    return out


def _corpus(facts: dict, slots: dict) -> tuple[str, set[str]]:
    """Everything the render is ALLOWED to say: all fact values + computed slots (+ human date
    expansions), lowercased for substring checks plus the digit-runs that legitimately appear."""
    parts: list[str] = []
    for f in facts.values():
        v = f.get("value") if isinstance(f, dict) else f
        s = json.dumps(v, default=str) if not isinstance(v, str) else v
        parts.append(s)
        parts.extend(_expand_dates(s))
    parts.extend(str(v) for v in slots.values())
    text = " ".join(parts)
    nums = set()
    for p in parts:
        nums |= _digit_runs(p)
    return text.lower(), nums


def invention_ok(text: str, corpus_text: str, corpus_nums: set[str]) -> tuple[bool, str | None]:
    for num in _digit_runs(text):
        if num not in corpus_nums and num not in corpus_text:
            return False, f"number:{num}"
    for pn in _proper_nouns(text):
        if pn.lower() not in corpus_text:
            return False, f"name:{pn}"
    return True, None


def _fallback(template: dict, slots: dict) -> dict:
    fb = template.get("fallback", {})
    head = fb.get("headline", "{entity}").format(**slots)[:HEADLINE_CAP]
    sit = fb.get("situation", "{stage}").format(**slots)[:SITUATION_CAP]
    return {"headline": head, "situation": sit,
            "artifact": {"kind": template.get("artifact_kind", "draft"),
                         "body": "", "mode": "raw_slot"},
            "render_mode": "raw_slot", "reject_code": None}


def _prompt(reason_code: str, template: dict, facts: dict, slots: dict) -> str:
    kind = template.get("artifact_kind", "draft")
    return (
        "You are GeniOS, writing ONE decision card for a salesperson. Use ONLY the facts below — "
        "never invent a name, number, company or date that is not present.\n\n"
        f"Situation type: {reason_code}\n"
        f"Facts (typed, from the graph):\n{json.dumps({k: (v.get('value') if isinstance(v, dict) else v) for k, v in facts.items()}, default=str, indent=0)}\n"
        f"Key slots: {json.dumps(slots, default=str)}\n\n"
        f"Guidance: {template.get('render_hint', '')}\n\n"
        "Return STRICT JSON only:\n"
        '{"headline": "<= 60 chars, entity + problem, concrete not clever",\n'
        ' "situation": "<= 140 chars, the two facts that matter + the money",\n'
        f' "artifact": "the {kind} — the actual draft text, ready to use"}}'
    )


def render_copy(*, reason_code: str, template: dict, facts: dict, slots: dict,
                llm=None, cost_sink=None, org_id: str = "") -> dict:
    """Try the model; fall back to raw slots on any validator rejection. Returns copy dict with
    headline/situation/artifact + render_mode ('llm'|'raw_slot') + reject_code (V-01/V-02|None)."""
    if llm is None:
        return _fallback(template, slots)

    prompt = _prompt(reason_code, template, facts, slots)
    res = llm.call(prompt, max_tokens=600)
    if cost_sink is not None and (res.input_tokens or res.output_tokens):
        try:
            cost_sink(org_id=org_id, model=res.model, purpose="l5_render",
                      input_tokens=res.input_tokens, output_tokens=res.output_tokens)
        except Exception:       # noqa: BLE001 — cost logging never blocks delivery
            pass
    if not res.ok or not isinstance(res.parsed, dict):
        return _fallback(template, slots)

    head = str(res.parsed.get("headline", "")).strip()
    sit = str(res.parsed.get("situation", "")).strip()
    art = str(res.parsed.get("artifact", "")).strip()
    if not head or not sit:
        return _fallback(template, slots)

    if len(head) > HEADLINE_CAP or len(sit) > SITUATION_CAP:
        fb = _fallback(template, slots)
        fb["reject_code"] = "V-01"                # over-length → reject + re-template
        return fb

    corpus_text, corpus_nums = _corpus(facts, slots)
    for chunk in (head, sit, art):
        ok, why = invention_ok(chunk, corpus_text, corpus_nums)
        if not ok:
            fb = _fallback(template, slots)
            fb["reject_code"] = "V-02"            # invention → raw-slot fallback
            fb["reject_detail"] = why
            return fb

    return {"headline": head, "situation": sit,
            "artifact": {"kind": template.get("artifact_kind", "draft"),
                         "body": art, "mode": "llm"},
            "render_mode": "llm", "reject_code": None}
