"""The writer: R-8 writes the day's checked material, line by line; R-8E once if it fails (STEP-15).

`speedrun008/YC-II W27/` STEP-15 §8.3 point 3, §8.4 item 3, tree `yc2_w27_s15` M45.C2.L-logic.V1.U03.
`executive/morning_prompt.build_prompt` hands the day's items over; `executive/morning_check.check_answer`
holds the answer to them. This module is the one that puts them through `reason/llm_sites.run_site`
on R-8 (Haiku-class), decides whether the draft stands, and — only on a real failure, never on a
preference — asks R-8E (Sonnet-class) once. Never T3: the ladder doc 11 and STEP-15 §8.3 agree on has
two rungs, and climbing past the second one is not this module's decision to make.

**A FAILURE, NOT A PREFERENCE, ESCALATES.** Malformed (the answer did not come back as `{"lines": [N
strings]}`, even after the gate's one syntax repair), or the check gave back `MAX_GIVEN_BACK` lines or
more — never fewer lines held, never a stylistic judgment. The SAME bar is held against R-8E: failing
it too, the template stands — the real, deterministic one (`executive/morning_template.template_brief`),
not a draft with some lines kept and some given back, because "the template stands" is read literally.

**THE ONE LINE IS NEVER THE MODEL'S.** Neither prompt asks for it (`morning_prompt.build_prompt` asks
only for "one line per item … in order"); `executive/morning_template.one_line` computes it from the
day's own shape, the same for a written brief as for a template one.

**THE FULL DAY IS ORDERED ONCE** (`executive/morning_order.order`), and the SAME `Ordered` is reused for
the prompt (so the model reads the whole day — `fit`-ting it first and feeding the model a reduced set
would risk a second `order()` call reseating an item `fit` cut from the back into a freed slot of
`today`, since `today`'s composition is a property of the WHOLE candidate pool). The budget is enforced
AFTER the model answers, by `fit`-ting the SAME `Ordered` with the words that actually stand — the
model's where a line was kept, the template's where it was given back — so a verbose model never
produces a brief past `WORD_BUDGET`; it only produces a shorter one, its cut counted exactly as the
template path's already is.

**WHAT THE TEMPLATE-STANDS BRIEF COSTS, AND WHERE THAT NUMBER ACTUALLY LIVES.** `Brief.__post_init__`
(M44.C1, frozen) refuses a `TEMPLATE_BRIEF` with a `cost_micro_usd`, a `model` or a `tier` —
"the template brief spends nothing and names no model" — a rule written for the case where no writer
was ever armed. It is still true by the letter when the writer WAS armed and both attempts failed: this
Brief holds `0`/`None`/`None` regardless of what the two consults actually spent. That spend is not
lost — `RSiteGate._record` and `_record_platform_cost` write it to `l4_r_site_calls` and `llm_costs`
on every consult, failed or not, which is the system of record for it everywhere else in this
codebase — but it is a real gap between this unit's own "what it cost" and the Brief object's own
field on exactly this path, surfaced here rather than resolved by loosening a contract this unit does
not own.

Two gates, two budgets (`reason/bundle/budget.OWN_BUDGETS`), built here directly rather than through
`reason/llm_sites.make_gate` — which has no `budget=` parameter — the same way `reason/expert/sweep.py`
builds R-7's own-budget gate directly. `activated_features` is read once and handed to both, so a
connection blip cannot arm the switch for R-8 and not for R-8E inside the same compose.
"""
from __future__ import annotations

import dataclasses
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, datetime
from typing import Any

from genios_engine.contracts import morning_brief as B
from genios_engine.executive.morning_check import AnswerCheck, LineCheck, check_answer
from genios_engine.executive.morning_order import Ordered, fit, order
from genios_engine.executive.morning_prompt import PROMPT_VERSION, build_prompt
from genios_engine.executive.morning_template import ONE_LINE_RESERVE, one_line, template_brief
from genios_engine.platform.l4_activation import FEATURE_MORNING_BRIEF
from genios_engine.platform.logging import get_logger
from genios_engine.reason.bundle.budget import NarrativeBudget
from genios_engine.reason.bundle.gate import MALFORMED, REPAIR_SYNTAX, RSiteGate
from genios_engine.reason.bundle.sites import SITE_BRIEF, SITE_BRIEF_ESCALATE, TIER_T1, TIER_T2
from genios_engine.reason.llm_sites import SiteRejection, make_site_client, run_site, with_correction

_log = get_logger("genios.executive.morning_writer")

WRITER_VERSION = "morning_writer.v1"

#: STEP-15 §8.3 point 3: "Two failed lines … and the brief is asked ONCE of Sonnet." Held against
#: BOTH attempts, the same bar each time — never loosened for the escalation.
MAX_GIVEN_BACK = 2

_TEMPLATE_WRITER_WHY = ("the chief of staff's Haiku-class draft failed its check and the one "
                       "Sonnet-class escalation failed it too; code's own words stand")


def _flatten(ordered: Ordered) -> tuple[tuple[B.Item, ...], tuple[str, ...]]:
    items: list[B.Item] = []
    sections: list[str] = []
    for section, held in ordered.sections:
        items.extend(held)
        sections.extend([section] * len(held))
    return tuple(items), tuple(sections)


def _seed(*, org_id: str, seat_id: str, local_date: date, items: Sequence[B.Item],
          company_brief_version: str) -> Mapping[str, str]:
    """What the gate's cache keys on: the day's material and the prompt version (the unit's own
    words) — plus the company brief's version, the same way `situation_reasoner.consult_seed` joins
    it, so a changed brief is not answered with the reading made under the old one."""
    seed = {"org": str(org_id), "seat": str(seat_id), "date": local_date.isoformat(),
            "material": B.digest_of(items), "prompt": PROMPT_VERSION}
    if company_brief_version:
        seed["company_brief"] = str(company_brief_version)
    return seed


def _envelope(n: int) -> str:
    return ("\n\nRespond with exactly one JSON object and nothing else — no words outside it: "
            f'{{"lines": [{n} string{"s" if n != 1 else ""}, one for each item above, in the exact '
            "order given]}.")


def _parse(payload: Mapping[str, Any], *, n: int) -> dict[str, list[str]]:
    lines = payload.get("lines") if isinstance(payload, Mapping) else None
    if (not isinstance(lines, list) or len(lines) != n
            or not all(isinstance(t, str) for t in lines)):
        raise SiteRejection(MALFORMED,
                            f'expected {{"lines": [...{n} strings]}}, held {payload!r}'[:300])
    return {"lines": [str(t) for t in lines]}


def _failed(check: AnswerCheck | None) -> bool:
    """A real failure: no usable answer at all, a malformed count, or the given-back bar reached —
    never a stylistic judgment, and never loosened for the escalation (same bar, both attempts)."""
    if check is None or check.malformed:
        return True
    return sum(1 for l in check.lines if l.verdict == B.GIVEN_BACK) >= MAX_GIVEN_BACK


def _gate(site: str, *, org_id: str, engine: Any, client: Any, activated: frozenset[str] | None,
          now: datetime) -> RSiteGate:
    """One site's own gate, on its own budget (`OWN_BUDGETS`) — never through `llm_sites.make_gate`,
    which has no `budget=` of its own to give it (the same reason `reason/expert/sweep.py` builds
    R-7's gate directly)."""
    store = None
    cost_recorder = None
    if engine is not None:
        from genios_engine.reason.bundle.store import BundleStore
        store = BundleStore(engine)
        from genios_engine.context.graph_store import GraphStore
        cost_recorder = GraphStore(engine=engine).record_cost
    return RSiteGate(org_id=org_id, engine=engine, client=client, store=store,
                     budget=NarrativeBudget.for_site(site, org_id=org_id, engine=engine, now=now),
                     activated=activated, cost_recorder=cost_recorder, eval_time=now)


def _ask(site: str, *, org_id: str, seat_id: str, local_date: date, items: Sequence[B.Item],
         sections: Sequence[str], company_brief: str, now: datetime, tz: str,
         founder: Iterable[str | None], gate: RSiteGate, cache: Any) -> tuple[AnswerCheck | None, Any]:
    """One site's attempt: the model's lines through the gate, then checked. `None` for the check
    means the gate produced no usable answer at all (not activated, no budget, no client, failed
    generation or malformed past its one syntax repair, truncated, force-failed) — a fact the caller
    reads off `result.receipt.outcome`, never guessed from the check alone."""
    n = len(items)
    base = build_prompt(items=items, company_brief=company_brief, now=now, tz=tz) + _envelope(n)

    def _build(feedback: str | None) -> str:
        return with_correction(base, feedback)

    result = run_site(
        site=site, org_id=org_id,
        seed=_seed(org_id=org_id, seat_id=seat_id, local_date=local_date, items=items,
                   company_brief_version=""),
        precondition=bool(items), build_prompt=_build, parse=lambda p: _parse(p, n=n),
        fallback=lambda: {"lines": []}, gate=gate, cache=cache, feature=FEATURE_MORNING_BRIEF,
        subject_ref=f"{org_id}:{seat_id}:{local_date.isoformat()}", repair=REPAIR_SYNTAX)
    if result.fell_back:
        return None, result
    texts = list(result.payload.get("lines") or [])
    if len(texts) != n:
        return None, result           # a cache hit from a differently-shaped past answer
    return check_answer(items, texts, sections=sections, founder=founder), result


def write_brief(engine: Any, *, org_id: str, seat_id: str, items: Iterable[B.Item], now: datetime,
                tz: str, founder: Iterable[str | None] = (), company_brief: str = "",
                client_t1: Any = None, client_t2: Any = None, cache: Any = None,
                activated: frozenset[str] | None = None) -> B.Brief:
    """The day's brief, in the chief of staff's own words where they stand — Haiku first, Sonnet once
    if Haiku fails its check, the template if both do. Never raises: every path that is not a clean
    write ends in `template_brief`, the same deterministic brief `morning.compose` already reads when
    no writer is armed at all — this function is safe to call UNCONDITIONALLY, armed or not, because
    `RSiteGate`'s own step 1 degrades an unarmed tenant to that same template for free, before a
    prompt is built or a token spent."""
    items = tuple(items)
    ordered = order(items, now=now, tz=tz)
    flat_items, flat_sections = _flatten(ordered)
    local_date = _local_date(now, tz)

    if not flat_items:
        return template_brief(org_id=org_id, seat_id=seat_id, items=items, now=now, tz=tz)

    if cache is None:
        from genios_engine.reason.llm_sites import PostgresSiteCache
        cache = PostgresSiteCache(engine) if engine is not None else None

    if activated is None and engine is not None:
        from genios_engine.platform.l4_activation import activated_features
        activated = activated_features(engine, org_id)

    client1 = client_t1 if client_t1 is not None else make_site_client(TIER_T1)
    gate1 = _gate(SITE_BRIEF, org_id=org_id, engine=engine, client=client1, activated=activated, now=now)
    check1, result1 = _ask(SITE_BRIEF, org_id=org_id, seat_id=seat_id, local_date=local_date,
                           items=flat_items, sections=flat_sections, company_brief=company_brief,
                           now=now, tz=tz, founder=founder, gate=gate1, cache=cache)

    if not _failed(check1):
        return _assemble(org_id=org_id, seat_id=seat_id, items=items, ordered=ordered, check=check1,
                         written_by=B.WRITTEN, why="the chief of staff's Haiku-class draft held",
                         model=result1.receipt.model, tier=result1.receipt.tier,
                         cost_micro_usd=result1.receipt.cost_micro_usd, now=now, tz=tz)

    client2 = client_t2 if client_t2 is not None else make_site_client(TIER_T2)
    gate2 = _gate(SITE_BRIEF_ESCALATE, org_id=org_id, engine=engine, client=client2,
                 activated=activated, now=now)
    check2, result2 = _ask(SITE_BRIEF_ESCALATE, org_id=org_id, seat_id=seat_id, local_date=local_date,
                           items=flat_items, sections=flat_sections, company_brief=company_brief,
                           now=now, tz=tz, founder=founder, gate=gate2, cache=cache)

    if not _failed(check2):
        spent = result1.receipt.cost_micro_usd + result2.receipt.cost_micro_usd
        why = ("the Haiku-class draft failed its check; the one Sonnet-class escalation held "
              f"({_why_failed(check1)})")
        return _assemble(org_id=org_id, seat_id=seat_id, items=items, ordered=ordered, check=check2,
                         written_by=B.ESCALATED, why=why, model=result2.receipt.model,
                         tier=result2.receipt.tier, cost_micro_usd=spent, now=now, tz=tz)

    why = (f"{_TEMPLATE_WRITER_WHY} (the draft: {_why_failed(check1)}; the escalation: "
          f"{_why_failed(check2)})")
    return dataclasses.replace(
        template_brief(org_id=org_id, seat_id=seat_id, items=items, now=now, tz=tz), why=why)


def _local_date(now: datetime, tz: str) -> date:
    from zoneinfo import ZoneInfo
    return now.astimezone(ZoneInfo(tz)).date()


def _why_failed(check: AnswerCheck | None) -> str:
    if check is None:
        return "no usable answer"
    if check.malformed:
        return check.reason or "malformed"
    given_back = sum(1 for l in check.lines if l.verdict == B.GIVEN_BACK)
    return f"{given_back} line(s) given back"


def _assemble(*, org_id: str, seat_id: str, items: tuple[B.Item, ...], ordered: Ordered,
             check: AnswerCheck, written_by: str, why: str, model: str | None, tier: str | None,
             cost_micro_usd: int, now: datetime, tz: str) -> B.Brief:
    """The final brief from a winning check: `fit` the SAME `Ordered` by the words that actually
    stand (the model's where kept, the template's where given back), never re-ordering — only
    cutting whole items from the back, exactly as `template_brief` already does."""
    local = _local_date(now, tz)
    # Every item `fit` may keep came from `ordered`, which is exactly what `check` was computed
    # over — so every one of them has a `LineCheck` here. A `KeyError` below is a real bug (the two
    # fell out of step), never a case to paper over with a silent template word.
    by_item: dict[str, LineCheck] = {l.item_id: l for l in check.lines}

    def _words_of(section: str, item: B.Item) -> int:
        return B.count_words(by_item[item.item_id].words)

    fitted = fit(ordered, _words_of, budget=B.WORD_BUDGET - ONE_LINE_RESERVE)
    lines = []
    for section, held in fitted.sections:
        for item in held:
            lc = by_item[item.item_id]
            if lc.verdict == B.KEPT:
                words, by, verdict, reason = lc.words, B.WRITER, B.KEPT, None
            else:
                words, by, verdict, reason = lc.words, B.TEMPLATE, B.GIVEN_BACK, lc.reason
            lines.append(B.Line(
                line_id=B.line_id_for(org_id, seat_id, local, section, item.item_id),
                item_id=item.item_id, section=section, words=words, kind=item.kind,
                subject=item.subject, sources=item.sources, by=by, verdict=verdict, reason=reason))
    return B.Brief(org_id=org_id, seat_id=seat_id, local_date=local, timezone=tz, as_of=now,
                   one_line=one_line(fitted), lines=tuple(lines), items=items, written_by=written_by,
                   why=why, model=model, tier=tier, cost_micro_usd=cost_micro_usd, cut=fitted.cut,
                   material_digest=B.digest_of(items), flexed=fitted.flexed)


__all__ = ["MAX_GIVEN_BACK", "WRITER_VERSION", "write_brief"]
