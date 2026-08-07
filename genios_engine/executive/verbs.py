"""Recommendation verbs — the executive answer to "so what should I do about it?".

Eight verbs, one PURE selector. The verb is a deterministic function of the signal's
level, score band, confidence and prediction — never an LLM choice, never engine-buried
tenant policy: every threshold comes from pack data (scoring.verbs, mergeable/pinnable
like any scoring default) with the defaults below as LVL1 baseline.

    do        act now — prescriptive, high-band, confident
    consider  worth attention, not compelled — mid-band or lower confidence
    delay     real but not yet — preventive-mode findings before the threshold trips
    escalate  beyond this seat's authority — critical band or authority mismatch
    delegate  actionable by someone/something else — L6 decides WHO (never this layer)
    approve   a pending item cleared its checks (needs an approvals source — future)
    reject    evidence says stop — negative prediction with high confidence
    dont      explicit counter-recommendation — a red-line/policy hit

Vision boundary holds: the verb says WHAT KIND of action the moment deserves; it never
names an owner, a channel or a tool."""
from __future__ import annotations

VERBS = ("do", "consider", "delay", "escalate", "delegate", "approve", "reject", "dont")

# LVL1 defaults — overridable per pack/tenant via effective["scoring"]["verbs"].
DEFAULTS = {
    "do_band": "high",              # band at/above which a prescriptive signal → do
    "do_c_min": 70,                 # ... provided integer confidence C ≥ this
    "escalate_band": "critical",    # band at/above which → escalate
    "reject_close_prob_max": 15,    # predicted close probability (bp/100) ≤ this → reject
    "reject_c_min": 70,
}

_BAND_ORDER = {"standard": 0, "high": 1, "critical": 2}


def select_verb(*, level: str, band: str, confidence_pct: int,
                preventive: bool = False, policy_blocked: bool = False,
                close_probability_pct: int | None = None,
                cfg: dict | None = None) -> tuple[str, str]:
    """(verb, reason). Pure — every input explicit, every threshold from cfg.

    Order matters and is part of the contract:
      policy block → dont            (a red line outranks everything)
      preventive   → delay           (the whole point: act BEFORE it trips)
      hopeless prediction → reject   (don't pour effort into a 10% deal)
      critical band → escalate
      prescriptive + high band + confident → do
      otherwise → consider
    """
    c = {**DEFAULTS, **(cfg or {})}
    if policy_blocked:
        return "dont", "a policy/red-line check failed"
    if preventive:
        return "delay", "threshold not yet crossed — act before it trips"
    if (close_probability_pct is not None
            and close_probability_pct <= int(c["reject_close_prob_max"])
            and confidence_pct >= int(c["reject_c_min"])):
        return "reject", f"predicted success {close_probability_pct}% — evidence says stop"
    if _BAND_ORDER.get(band, 0) >= _BAND_ORDER.get(str(c["escalate_band"]), 2):
        return "escalate", f"{band} band exceeds this seat's normal authority"
    if (level == "prescriptive"
            and _BAND_ORDER.get(band, 0) >= _BAND_ORDER.get(str(c["do_band"]), 1)
            and confidence_pct >= int(c["do_c_min"])):
        return "do", f"prescriptive at {band} band with C={confidence_pct}"
    return "consider", f"{level} at {band} band"


def band_of(score: int, bands_cfg: dict | None = None) -> str:
    """Pack-data band cut (same semantics as the delivery layer's — duplicated here
    because executive (5) must not import deliver (6); 5 lines, shared tests)."""
    cfg = bands_cfg or {"high": 70, "critical": 85}
    if score >= int(cfg.get("critical", 85)):
        return "critical"
    if score >= int(cfg.get("high", 70)):
        return "high"
    return "standard"
