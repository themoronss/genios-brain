"""How a founder case is marked — one rule, read by the founder test and by the board.

`speedrun008/YC-II W27/` STEP-01 §5. A case's VERDICT
is about what the founder sees: the cards it expects (about whom, how many over every sweep, saying
what), the cards it forbids, and the names and phrases no card may carry. The stage checks — what
Layer 1 did with each object, whether it reached memory — are reported beside the verdict as
`lost_at`, because "where was it lost" is what the next step needs; they never decide it. A mail
the gate ARCHIVED (STEP-03) is lost at the gate exactly as a dropped one was — nobody read it — and
its check says it was kept, because an archived must-detect mail is the one STEP-05 can promote.

Four verdicts:

  PASS             every expressible card expectation holds and nothing forbidden appears;
  FAIL             one does not, a forbidden term appears, a sweep's chain crashed, or the run
                   swallowed a cassette miss (it is then not the recorded run at all);
  NOT_EXERCISED    a must-abstain case whose witness did not hold: silence from a chain that never
                   reached the stage says nothing about a decision to stay silent;
  NOT_EXPRESSIBLE  every card expectation of the case is declared not expressible — counted apart.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from tests.replays.founder_case import CardExpectation, CaseRun, FounderCase

PASS, FAIL, NOT_EXERCISED, NOT_EXPRESSIBLE = "pass", "fail", "not_exercised", "not_expressible"
VERDICTS = (PASS, FAIL, NOT_EXERCISED, NOT_EXPRESSIBLE)


@dataclass(frozen=True)
class Check:
    name: str
    verdict: str
    reason: str


@dataclass(frozen=True)
class Mark:
    case_id: str
    kind: str
    verdict: str
    reason: str
    checks: tuple[Check, ...]
    forbidden_hits: tuple[tuple[str, str], ...]
    #: For a must-detect case that failed: `gate`, `memory` or `reasoning` — the first stage its
    #: objects did not get past. None when it passed, or when the case names no stage to read.
    lost_at: str | None


def judge(case: FounderCase, run: CaseRun) -> Mark:
    checks: list[Check] = []

    # ── the run itself ─────────────────────────────────────────────────────────────────────────
    crashed = [i for i, ok in enumerate(run.chain_ok) if not ok]
    if run.misses:
        sites = sorted({site for site, _key in run.misses})
        checks.append(Check("run", FAIL, f"the run swallowed {len(run.misses)} cassette miss(es) "
                                         f"at {sites} — it is not the recorded run"))
    if crashed:
        checks.append(Check("run", FAIL, "the chain failed at sweep "
                                         + ", ".join(str(i) for i in crashed)))

    # ── stage checks: reported, never the verdict ─────────────────────────────────────────────
    stages = _stage_checks(case, run)
    checks += stages

    # ── what the founder sees ─────────────────────────────────────────────────────────────────
    card_checks = [_card_check(i, exp, run) for i, exp in enumerate(case.cards)
                   if case.expressible("cards")]
    checks += card_checks
    hits = tuple(sorted(_forbidden(case, run)))
    if hits:
        checks.append(Check("forbidden", FAIL,
                            "; ".join(f"{card} says {term!r}" for card, term in hits)))

    witness = None
    if case.kind == "must_abstain" and case.witness is not None:
        witness = _witness_check(case, run)
        checks.append(witness)
    for key, reason in case.not_expressible.items():
        checks.append(Check(key, NOT_EXPRESSIBLE, reason))

    # ── the verdict ───────────────────────────────────────────────────────────────────────────
    deciding = [c for c in checks if c.name.startswith(("run", "cards", "forbidden"))]
    failed = [c for c in deciding if c.verdict == FAIL]
    if failed:
        verdict, reason = FAIL, " | ".join(c.reason for c in failed)
    elif not card_checks:
        verdict, reason = NOT_EXPRESSIBLE, "every card expectation is declared not expressible"
    elif witness is not None and witness.verdict != PASS:
        verdict, reason = NOT_EXERCISED, witness.reason
    else:
        verdict, reason = PASS, "what the founder sees is what the case expects"
    lost_at = _lost_at(case, run, stages) if (verdict == FAIL and case.kind == "must_detect"
                                             and not crashed and not run.misses) else None
    return Mark(case_id=case.case_id, kind=case.kind, verdict=verdict, reason=reason,
                checks=tuple(checks), forbidden_hits=hits, lost_at=lost_at)


# ── helpers ──────────────────────────────────────────────────────────────────────────────────────
def says(text: str, term: str) -> bool:
    """Whole word (or phrase), any case — `Kavya` is not `Kavyas`."""
    pattern = r"\s+".join(re.escape(w) for w in term.split())
    return re.search(rf"(?<![0-9A-Za-z]){pattern}(?![0-9A-Za-z])", text, re.IGNORECASE) is not None


def cards_about(run: CaseRun, about: tuple[str, ...]):
    return [c for c in run.cards if any(says(c.text, t) for t in about)]


def _card_check(index: int, exp: CardExpectation, run: CaseRun) -> Check:
    name = f"cards[{index}]"
    matched = cards_about(run, exp.about)
    n = len(matched)
    subject = "/".join(exp.about)
    if not exp.min <= n <= exp.max:
        bound = f"exactly {exp.min}" if exp.min == exp.max else f"{exp.min}–{exp.max}"
        return Check(name, FAIL, f"{n} card{'s' if n != 1 else ''} about {subject} over every "
                                 f"sweep; expected {bound}")
    for card in matched:
        missing = [t for t in exp.mentions if not says(card.text, t)]
        if missing:
            return Check(name, FAIL, f"card {card.card_id} about {subject} does not say "
                                     f"{missing}")
    return Check(name, PASS, f"{n} card(s) about {subject}")


def _forbidden(case: FounderCase, run: CaseRun):
    for card in run.cards:
        for name in case.forbidden_names:
            if says(card.text, name):
                yield card.card_id, name
        for phrase in case.forbidden_phrases:
            if phrase.lower() in card.text.lower():
                yield card.card_id, phrase


def _primary(run: CaseRun, case: FounderCase, object_id: str):
    """The object's OWN event — an email's attachments land beside it under `<id>::attN`."""
    provider_id = case.object(object_id).provider_id
    return next((x for x in run.landed if x.source_object_id == provider_id), None)


def _stage_checks(case: FounderCase, run: CaseRun) -> list[Check]:
    out: list[Check] = []
    for oid, expected in case.expected_gate.items():
        if not case.expressible("gate"):
            break
        want, _, code = expected.partition(":")
        landed = _primary(run, case, oid)
        if landed is None:
            out.append(Check(f"gate:{oid}", FAIL, "never reached the gate"))
            continue
        got = landed.outcome + (f":{landed.reason}" if landed.reason else "")
        if landed.outcome == "archived":
            got += " — kept, read by no model"
        ok = landed.outcome == want and (not code or landed.reason == code)
        out.append(Check(f"gate:{oid}", PASS if ok else FAIL,
                         f"{got} (expected {expected})"))
    for oid, expected in case.expected_memory.items():
        if not case.expressible("memory"):
            break
        facts = int(run.memory.get(oid, 0))
        ok = (facts > 0) == expected
        out.append(Check(f"memory:{oid}", PASS if ok else FAIL,
                         f"{facts} fact(s) in memory (expected {'some' if expected else 'none'})"))
    return out


def _witness_check(case: FounderCase, run: CaseRun) -> Check:
    w = case.witness
    if w.stage == "gate":
        missing = [o for o in w.objects if _primary(run, case, o) is None]
        ok, what = not missing, f"reached the gate (missing: {missing})"
    elif w.stage == "memory":
        missing = [o for o in w.objects if int(run.memory.get(o, 0)) == 0]
        ok, what = not missing, f"reached memory (missing: {missing})"
    elif w.stage == "situation":
        ok = any(any(says(s.anchor, t) or says(s.situation_type, t) for t in w.about)
                 for s in run.situations)
        what = f"a situation about {list(w.about)}"
    else:
        ok, what = bool(cards_about(run, w.about)), f"a card about {list(w.about)}"
    return Check("witness", PASS if ok else NOT_EXERCISED,
                 f"witness at {w.stage}: {what}" if not ok else f"witness held at {w.stage}")


def _lost_at(case: FounderCase, run: CaseRun, stages: list[Check]) -> str | None:
    if any(c.name.startswith("gate:") and c.verdict == FAIL for c in stages):
        return "gate"
    if any(c.name.startswith("memory:") and c.verdict == FAIL for c in stages):
        return "memory"
    if stages:
        return "reasoning"
    return None
