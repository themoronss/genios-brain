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

⛔ WHAT YOU SEE (STEP-14, `yc2_w27_s14` M42.C4.L-logic.V2.U03, s14-D4, s14-F2, s14-F14). A must-detect case counts a
card only once the APP showed it — the queue at a sweep's instant (`CardView.app_sweeps`, read by the runner): 6 of
the 21 passes were cards that sat in `cards` and reached no surface the founder opens. What a shown card is ABOUT is
read on every version it showed (a living card that was about the unit economics sheet and then about the review
deck was a card about each — F24); its `mentions` on its final words. Forbidden names and phrases, `forbidden:us` and a must-abstain case read EVERY card, shown
or not, and every version's words (`CardView.versions`) — a word a card once showed was shown. A case reports the
cards about its subject the app never showed (`unshown`), beside the verdict and deciding nothing.

THE MORNING BRIEF (STEP-15, `yc2_w27_s15` M44.C5.L-integration.V1.U04) is judged as the cards are: each line a case
expects present, in its section, about whom it says, saying what it must; every forbidden name and phrase absent from
every line; a must-abstain case's subjects — what its `max: 0` cards are about — absent from every line, as a line
or as a card (`golden-labels.md`: `no` is never surfaced). A case whose cards are brief-only (`06` D12d) is judged on
its brief. What a line QUOTES is read apart from what it says (`BriefLineView.quotes`), as STEP-13's judge reads a
card's sources (eb2b0486): a line that quotes "Introly connected us" is not a line about Introly. A run that composed
no brief (`brief=False`) leaves the brief not expressible — the negative control.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from tests.replays.founder_case import BriefLineExpectation, CardExpectation, CaseRun, FounderCase

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
    card_checks = [_card_check(i, exp, run, case.kind) for i, exp in enumerate(case.cards)
                   if case.expressible("cards")]
    checks += card_checks
    brief_checks = _brief_checks(case, run)
    checks += brief_checks
    if case.kind == "must_detect" and case.expressible("cards"):
        unshown = _unshown(case, run)
        if unshown:
            checks.append(Check("unshown", PASS, "the app never showed " + ", ".join(unshown)))
    hits = tuple(sorted(_forbidden(case, run)))
    if hits:
        checks.append(Check("forbidden", FAIL,
                            "; ".join(f"{card} says {term!r}" for card, term in hits)))
    ours = sorted(_about_us(case, run))
    if ours:
        checks.append(Check("forbidden:us", FAIL, "; ".join(
            f"card {card}'s subject is the founder ({subject!r})" for card, subject in ours)))

    witness = None
    if case.kind == "must_abstain" and case.witness is not None:
        witness = _witness_check(case, run)
        checks.append(witness)
    for key, reason in case.not_expressible.items():
        checks.append(Check(key, NOT_EXPRESSIBLE, reason))

    # ── the verdict ───────────────────────────────────────────────────────────────────────────
    deciding = [c for c in checks if c.name.startswith(("run", "cards", "forbidden", "brief"))]
    failed = [c for c in deciding if c.verdict == FAIL]
    if failed:
        verdict, reason = FAIL, " | ".join(c.reason for c in failed)
    elif not card_checks and not any(c.verdict == PASS for c in brief_checks):
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


def every_word(card) -> str:
    """Everything a card ever said: its final words and every version's (STEP-14, s14-F14)."""
    return "\n".join((card.text, *getattr(card, "versions", ())))


def cards_about(run: CaseRun, about: tuple[str, ...], *, shown: bool = False, ever: bool = False):
    """The cards about any of `about` — on their final words, or (`ever`) on every version's; and only those the
    app showed (`shown`, STEP-14)."""
    return [c for c in run.cards
            if (not shown or c.app_sweeps)
            and any(says(every_word(c) if ever else c.text, t) for t in about)]


def _unshown(case: FounderCase, run: CaseRun) -> list[str]:
    """The cards about a must-detect case's subjects that existed and the app never showed."""
    about = tuple(t for exp in case.cards for t in exp.about)
    return [c.card_id for c in cards_about(run, about) if not c.app_sweeps]


def _card_check(index: int, exp: CardExpectation, run: CaseRun, kind: str = "must_detect") -> Check:
    name = f"cards[{index}]"
    # STEP-14 (s14-D4): a must-detect card counts once the app showed it; silence is judged over every card.
    matched = (cards_about(run, exp.about, shown=True, ever=True) if kind == "must_detect"
               else cards_about(run, exp.about, ever=True))
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
        headline = str((getattr(card, "gold", None) or {}).get("headline") or "")
        unsaid = [t for t in getattr(exp, "headline_says", ()) if not says(headline, t)]
        if unsaid:
            return Check(name, FAIL, f"card {card.card_id} about {subject} does not say {unsaid} in its "
                                     f"headline (“{headline}”)")
    if exp.closed_from is not None:
        # `09` G6 · done means never raised again: open after a sweep at or past `closed_from`.
        still = [(c.card_id, max(c.sweeps)) for c in matched
                 if any(s >= exp.closed_from for s in c.sweeps)]
        if still:
            return Check(name, FAIL, "; ".join(f"card {cid} about {subject} is still open after "
                                               f"sweep {s} — closed from sweep {exp.closed_from}"
                                               for cid, s in still))
    return Check(name, PASS, f"{n} card(s) about {subject}")


def brief_judged(case: FounderCase, run: CaseRun) -> bool:
    """Whether the case's brief is judged on this run: it expects lines, its brief is expressible, and the run
    composed one."""
    return bool(case.brief is not None and case.brief.lines and case.expressible("brief")
                and run.brief is not None)


def lines_about(run: CaseRun, about: tuple[str, ...], section: str | None = None):
    """The brief's lines about any of `about` — in their words, never their quotes — in `section` when named."""
    return [l for l in (run.brief or ()) if (section is None or l.section == section)
            and any(says(l.text, t) for t in about)]


def _brief_line_check(index: int, exp: BriefLineExpectation, run: CaseRun) -> Check:
    name = f"brief[{index}]"
    matched = lines_about(run, exp.about, exp.section)
    n = len(matched)
    subject = "/".join(exp.about)
    if not exp.min <= n <= exp.max:
        elsewhere = sorted({l.section for l in lines_about(run, exp.about)} - {exp.section})
        bound = f"exactly {exp.min}" if exp.min == exp.max else f"{exp.min}–{exp.max}"
        return Check(name, FAIL, f"{n} line{'s' if n != 1 else ''} about {subject} in {exp.section}; expected "
                                 f"{bound}" + (f" (found in {elsewhere})" if elsewhere else ""))
    for line in matched:
        missing = [t for t in exp.mentions if not says(line.text, t)]
        if missing:
            return Check(name, FAIL, f"the {exp.section} line about {subject} does not say {missing}: "
                                     f"{line.text!r}")
    return Check(name, PASS, f"{n} line(s) about {subject} in {exp.section}")


def _brief_checks(case: FounderCase, run: CaseRun) -> list[Check]:
    """The brief's checks: each expected line (when judged), and — on every run that composed a brief — no
    forbidden name or phrase on any line, and no must-abstain subject."""
    out: list[Check] = []
    if case.brief is not None and case.brief.lines and case.expressible("brief") and run.brief is None:
        out.append(Check("brief", NOT_EXPRESSIBLE, "no brief was composed on this run"))
    if brief_judged(case, run):
        out += [_brief_line_check(i, exp, run) for i, exp in enumerate(case.brief.lines)]
    if run.brief is None:
        return out
    hits = sorted({(l.line_id, term) for l in run.brief
                   for term in (*case.forbidden_names, *case.forbidden_phrases) if says(l.text, term)})
    if hits:
        out.append(Check("brief:forbidden", FAIL, "; ".join(f"line {lid} says {term!r}" for lid, term in hits)))
    if case.kind == "must_abstain":
        never = tuple(t for c in case.cards if c.max == 0 for t in c.about)
        surfaced = [(l.section, l.text) for l in lines_about(run, never)] if never else []
        if surfaced:
            out.append(Check("brief:abstain", FAIL, "; ".join(f"the {sec} line names what the case forbids: "
                                                            f"{text!r}" for sec, text in surfaced)))
    return out


def _forbidden(case: FounderCase, run: CaseRun):
    for card in run.cards:
        # STEP-14: every card, every version's words — and (the crosscheck's finding 9) every gold line it showed.
        said = "\n".join((every_word(card), *getattr(card, "shown_lines", ())))
        for name in case.forbidden_names:
            if says(said, name):
                yield card.card_id, name
        # STEP-01 follow-up c (`yc2_w27_align` M34.C1.L-logic.V1.U05): a phrase is the CLAIM it names —
        # whole words, either case — as a name is. A substring match failed "ARR" on "arrived".
        for phrase in case.forbidden_phrases:
            if says(said, phrase):
                yield card.card_id, phrase


def _about_us(case: FounderCase, run: CaseRun):
    """STEP-04: cards whose SUBJECT is the founder — his name, any of his addresses, or a domain of
    the company's. Our words may be on a card (`7075014c`); we may never be what it is about."""
    from genios_engine.platform.self_identity import PUBLIC_MAIL_DOMAINS

    f = case.founder
    domains = {d for d in (*f.domains, f.domain) if d and d not in PUBLIC_MAIL_DOMAINS}
    for card in run.cards:
        subject = (card.subject or "").strip()
        if not subject:
            continue
        low = subject.lower()
        if (says(subject, f.name) or any(a in low for a in f.addresses)
                or any(re.search(rf"(?<![0-9a-z.-]){re.escape(d)}(?![0-9a-z-])", low) for d in domains)):
            yield card.card_id, subject


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
        ok, what = bool(cards_about(run, w.about, ever=True)), f"a card about {list(w.about)}"
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
