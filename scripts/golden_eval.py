"""The golden set against a model — the ideal reader's recordings, or the real model, outside CI.

    python scripts/golden_eval.py --dry-run                      # what a live run would cost; no DB
    python scripts/golden_eval.py --dry-run --site expert        # …the expert's calls alone (06 D50)
    python scripts/golden_eval.py --dry-run --site brief         # …the morning brief's R-8/R-8E (s15-D1)
    GENIOS_TEST_DATABASE_URL=… python scripts/golden_eval.py --record [F03 F07 …]
    GENIOS_TEST_DATABASE_URL=… GENIOS_GOLDEN_LIVE_KEY=sk-… python scripts/golden_eval.py \\
        --live --model claude-haiku-4-5-20251001 --spend-ok [--record] [F03 …]
    GENIOS_TEST_DATABASE_URL=… GENIOS_GOLDEN_LIVE_KEY=sk-… python scripts/golden_eval.py \\
        --live --site expert --spend-ok [F03 …]                  # the expert on its own model
        --live --site expert --spend-ok --max-usd 7 --thinking adaptive --ceiling 12000 --per-call-usd 0.15
                                                                 # 06 D72's arm B, stopped at $7
    GENIOS_TEST_DATABASE_URL=… GENIOS_GOLDEN_LIVE_KEY=sk-… python scripts/golden_eval.py \\
        --live --site brief --spend-ok --max-usd 1 [F03 …]       # the brief's writer, both tiers

`speedrun008/YC-II W27/` STEP-01 §3.9.

  --dry-run   Reads the cases and their cassettes and prints, per case, what wrote the cassette,
              how many model calls it holds, and what replaying them against a live model would
              cost at list price. Touches no database and no model.
  --record    Re-records cassettes with the ideal reader (`tests/replays/ideal_reader.py`) — no
              spend. A deliberate act: run it after a prompt change, never to make a case pass.
  --live      Replays the same cases against the REAL model and writes a scorecard — recall,
              precision, forbidden outputs, tokens, cost — to `speedrun008/YC-II W27/scores/`.
              Model spend is the founder's call (06-DECISIONS D12c, default: no spend), so it
              needs BOTH a key in GENIOS_GOLDEN_LIVE_KEY and `--spend-ok`. With `--record` it also
              replaces the cassettes, which then say `live:<model>`.

  --site      One model site only (a `tests/replays/harness.SITE_MARKERS` name). The dry run counts
              that site's recorded calls and prices them on its own model — the expert's is its tier's,
              `claude-sonnet-5` (`06` D7) — and the live pass asks the real model that site's prompts
              alone, every other site answered by the ideal reader (no spend). STEP-12 M33.C3
              (`06` D50): the expert's judgment on the real model, its answers and its board kept
              BESIDE the authored ones (`scores/<date>-<model>-<site>/`) and compared case by case —
              never instead of them, so `--record` is refused with `--site`.

  --site brief  STEP-15 (s15-D1): the morning brief's writer, OUTSIDE the normal chain — it runs
              AFTER a case's last sweep, never inside it, so it does not fit `identify_site`'s
              marker dispatch the way every site above does. There is also no cassette to read a
              dry-run estimate from (R-8/R-8E have never been recorded): the dry run composes each
              case's real day on the scratch database instead — no model asked, but not "no
              database" either, a documented exception to the rule above for this one site. The
              live pass always asks BOTH tiers (never one `--model`): R-8's Haiku-class draft,
              checked, and R-8E's Sonnet-class escalation once if it fails — each case's brief set
              beside its own `morning_template.template_brief`, which a `given_back` verdict on a
              line already is. `--record` is refused here too: there is no cassette shape for it.

The live model is handed to the chain through the same doors the recorded one is
(`tests/replays/model_sites.DOORS`); the runner's transport refusal still applies to every other
client, so a site that built its own would still fail the case rather than spend unseen.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from collections import Counter
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

SCORES = REPO / "speedrun008" / "YC-II W27" / "scores"
LIVE_KEY_ENV = "GENIOS_GOLDEN_LIVE_KEY"
#: The model a run is priced and asked on when none is named: Haiku 4.5, the model production runs
#: every site on (`Settings.anthropic_model`) — except a site with a tier of its own (`SITE_TIERS`).
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
#: A cassette site whose production model is its tier's, not the default: the expert's (R-7, T2).
SITE_TIERS = {"expert": "R-7"}
#: STEP-15 (s15-D1): the morning brief, OUTSIDE `identify_site`'s normal dispatch — see the module
#: docstring's `--site brief` section. Not in `SITE_TIERS`: it asks BOTH R-8 and R-8E, never one tier.
BRIEF_SITE = "brief"


def price_per_mtok(model: str) -> tuple[float, float]:
    """List price per million tokens (input, output) — the product's one table
    (`platform/metrics.LLM_PRICE`), never a second copy here."""
    from genios_engine.platform.metrics import llm_price
    price_in, price_out = llm_price(model)
    return round(price_in * 1e6, 6), round(price_out * 1e6, 6)


def model_for(site: str | None, model: str | None) -> str:
    """The named model, else the site's own tier's model, else the default."""
    if model:
        return model
    if site in SITE_TIERS:
        from genios_engine.reason.bundle.sites import tier_for
        from genios_engine.reason.llm_sites import tier_model
        return tier_model(tier_for(SITE_TIERS[site]))
    return DEFAULT_MODEL


#: ⛔ `yc2_w27_s18` M50.C4.L-interface.V1.U09 (the 13 Oct audit's s5t-F12, `06` D72). The Sonnet pass of
#: 12 Oct printed $0.35 for ≈ $10.4 spent: its card summed the cassette — only the answers kept — and a
#: cut answer was raised, retried and never counted. A live pass now sums the recorder's `ledger`
#: (every call), names its cut calls, and cannot start without a dollar cap it stops at.
class SpendCapReached(RuntimeError):
    """A live call was refused because its worst case would cross `--max-usd`. Raised before the call."""


class SpendCap:
    """The run's money: what has been spent (from each call's own tokens, a cut one included), and
    whether a call was refused. A call is priced at its worst case — the prompt at four characters a
    token, the output at its whole ceiling — before it is made."""

    def __init__(self, max_usd: float, model: str) -> None:
        self.max_usd = float(max_usd)
        self.price_in, self.price_out = price_per_mtok(model)
        self.spent_usd = 0.0
        self.reached = False

    def worst_usd(self, prompt: str, max_tokens: int) -> float:
        return (-(-len(prompt) // 4) / 1e6 * self.price_in + int(max_tokens) / 1e6 * self.price_out)

    def charge(self, result) -> None:
        self.spent_usd += (int(getattr(result, "input_tokens", 0) or 0) / 1e6 * self.price_in
                           + int(getattr(result, "output_tokens", 0) or 0) / 1e6 * self.price_out)


class CappedModel:
    """The live model behind the cap: a call whose worst case would cross it is never made."""

    def __init__(self, inner, cap: SpendCap) -> None:
        self._inner, self._cap = inner, cap
        self.model = getattr(inner, "model", "")

    @property
    def supports_thinking(self) -> bool:
        return bool(getattr(self._inner, "supports_thinking", False))

    def content_hash(self, material: str) -> str:
        return self._inner.content_hash(material)

    def call(self, prompt: str, *, max_tokens: int = 4096, **kw):
        if self._cap.spent_usd + self._cap.worst_usd(prompt, max_tokens) > self._cap.max_usd:
            self._cap.reached = True
            raise SpendCapReached(f"--max-usd {self._cap.max_usd:g}: ${self._cap.spent_usd:.4f} spent, "
                                  "the next call's worst case would cross it")
        result = self._inner.call(prompt, max_tokens=max_tokens, **kw)
        self._cap.charge(result)
        return result


@contextlib.contextmanager
def site_settings(r_site: str, *, thinking: str | None = None, ceiling: int | None = None,
                  per_call_usd: str | None = None):
    """One R-site's thinking mode, ceiling and per-call cap for the length of a run — `06` D72's arms —
    and put back after, whatever the run does. The day's cap is never the run's to move."""
    from genios_engine.reason.bundle import budget, sites as site_table
    before = (site_table.SITE_THINKING[r_site], site_table.SITE_MAX_OUTPUT_TOKENS[r_site],
              budget.OWN_BUDGETS.get(r_site))
    try:
        if thinking is not None:
            site_table.SITE_THINKING[r_site] = thinking
        if ceiling is not None:
            site_table.SITE_MAX_OUTPUT_TOKENS[r_site] = int(ceiling)
        if per_call_usd is not None:
            budget.OWN_BUDGETS[r_site] = (budget.OWN_BUDGETS[r_site][0], str(per_call_usd))
        yield
    finally:
        site_table.SITE_THINKING[r_site], site_table.SITE_MAX_OUTPUT_TOKENS[r_site] = before[:2]
        if before[2] is not None:
            budget.OWN_BUDGETS[r_site] = before[2]


def spend(ledger: list[dict], site: str | None) -> dict:
    """What a pass paid for: every call of the site (every call, without one) — a cut one included."""
    calls = [row for row in ledger if site is None or row.get("site") == site]
    return {"calls": len(calls), "truncated_calls": sum(bool(row.get("truncated")) for row in calls),
            "tokens_in": sum(int(row.get("input_tokens") or 0) for row in calls),
            "tokens_out": sum(int(row.get("output_tokens") or 0) for row in calls)}


def scorecard_name(day: str, model: str, site: str | None, thinking: str | None) -> str:
    """`<day>-<model>[-<site>][-<thinking>]` — an arm of `06` D72 never overwrites the other."""
    return "-".join(part for part in (day, model, site, thinking) if part)


def sites() -> tuple[str, ...]:
    from tests.replays.harness import SITE_MARKERS
    return tuple(site for site, _module, _marker in SITE_MARKERS)


def _cases(ids: list[str]):
    from tests.replays.founder_case import load_cases
    cases = load_cases()
    if ids:
        unknown = sorted(set(ids) - {c.case_id for c in cases})
        if unknown:
            raise SystemExit(f"no such case: {unknown}")
        cases = tuple(c for c in cases if c.case_id in ids)
    return cases


def dry_run(ids: list[str], model: str, site: str | None = None) -> int:
    from tests.replays import cassettes
    price_in, price_out = price_per_mtok(model)
    total_calls = total_in = total_out = 0
    print(f"{'case':<5} {'source':<16} {'calls':>5} {'tokens in':>10} {'tokens out':>10}  title")
    for case in _cases(ids):
        try:
            answers = cassettes.load(case)
            source = cassettes.source_of(case)
        except AssertionError:
            answers, source = {}, "NO CASSETTE"
        if site is not None:
            answers = {k: a for k, a in answers.items() if a.get("site") == site}
        tin = sum(int(a.get("input_tokens") or 0) for a in answers.values())
        tout = sum(int(a.get("output_tokens") or 0) for a in answers.values())
        total_calls, total_in, total_out = total_calls + len(answers), total_in + tin, total_out + tout
        print(f"{case.case_id:<5} {source:<16} {len(answers):>5} {tin:>10} {tout:>10}  "
              f"{case.title[:60]}")
    cost = total_in / 1e6 * price_in + total_out / 1e6 * price_out
    which = f"{site} " if site is not None else ""
    print(f"\n{total_calls} {which}model calls · {total_in} tokens in · {total_out} tokens out · "
          f"≈ ${cost:.2f} for one live pass on {model} at list price (${price_in:g} / ${price_out:g} "
          "a million tokens in / out; the recorded token counts are the ideal reader's estimates). "
          "Nothing was run.")
    return 0


def record(ids: list[str], model=None, source=None) -> list:
    from tests.replays import cassettes
    from tests.replays.marking import judge
    rows = []
    for case in _cases(ids):
        run, answers = cassettes.record(case, model)
        cassettes.save(case, answers, source=source or cassettes.IDEAL_READER)
        mark = judge(case, cassettes.replay(case))
        rows.append((case, run, answers, mark))
        print(f"{case.case_id} {mark.verdict:<15} {len(answers):>3} answers  {mark.reason[:100]}")
    return rows


class SiteModel:
    """One site's prompts to `live`, every other site's to `rest` — `LLMClient`'s `.model` / `.call()`.
    The live pass of one site: the real model judges, and nothing else it would ask is spent."""

    def __init__(self, site: str, live, rest) -> None:
        self.site, self._live, self._rest = site, live, rest
        self.model = getattr(live, "model", "")

    @property
    def supports_thinking(self) -> bool:
        return bool(getattr(self._live, "supports_thinking", False))

    @staticmethod
    def content_hash(material: str) -> str:
        from genios_engine.context.llm.client import LLMClient
        return LLMClient.content_hash(material)

    def call(self, prompt: str, **kw):
        from tests.replays.harness import identify_site
        if identify_site(prompt) == self.site:
            return self._live.call(prompt, **kw)
        if not getattr(self._rest, "supports_thinking", False):
            kw = {k: v for k, v in kw.items() if k not in ("thinking", "timeout_s")}
        return self._rest.call(prompt, **kw)


class LiveModel:
    """The real model, called through the transport the runner refuses to everyone else."""

    #: `LLMClient.call` takes the site's thinking mode and timeout (`context/llm/client`).
    supports_thinking = True

    def __init__(self, api_key: str, model: str) -> None:
        from genios_engine.context.llm.client import LLMClient
        self._client = LLMClient(api_key=api_key, model=model)
        self._call = LLMClient.call            # captured BEFORE the runner refuses the transport
        # …and the raw client BUILT before it too: `production_switches` replaces `anthropic.Anthropic` with a
        # class that raises, and a client built lazily on the first call was built inside the run — the live
        # pass refused itself on its first expert prompt (`06` D50 never ran).
        self._client._c()
        self.model = model

    @staticmethod
    def content_hash(material: str) -> str:
        from genios_engine.context.llm.client import LLMClient
        return LLMClient.content_hash(material)

    def call(self, prompt: str, *, max_tokens: int = 4096, **kw):
        return self._call(self._client, prompt, max_tokens=max_tokens, **kw)


def _checked(engine, org: str) -> dict:
    """What the check made of the expert's reviews on one case (STEP-13 M35.C4.L-integration.V2.U04): each
    review's status, each checked review's fate (shown, held, suppressed, refused), every dropped line's
    reason — and every NOTED one's (M35.C4.L-integration.V2.U05, the second crosscheck G10: the wording notes,
    `speaks_of_you` above all, were counted nowhere, against STEP-13 §8.4.6) — so a live pass says how often a
    real model's claims are held, and why, and how it speaks of you, not only the board."""
    from sqlalchemy import text

    statuses, fates, dropped, noted = Counter(), Counter(), Counter(), Counter()
    with engine.connect() as c:
        for row in c.execute(text("select status, checked from expert_reviews where org_id = :o"), {"o": org}):
            statuses[row.status] += 1
            checked = row.checked if isinstance(row.checked, dict) else (json.loads(row.checked) if row.checked else None)
            if checked:
                fates[str(checked.get("fate"))] += 1
                dropped.update(str(v.get("reason")) for v in checked.get("verdicts") or ()
                               if v.get("verdict") == "dropped")
                noted.update(str(v.get("reason")) for v in checked.get("verdicts") or ()
                             if v.get("verdict") == "noted")
    return {"reviews": dict(sorted(statuses.items())), "fates": dict(sorted(fates.items())),
            "dropped": dict(sorted(dropped.items())), "noted": dict(sorted(noted.items()))}


def live(ids: list[str], model: str, keep: bool, site: str | None = None, *, max_usd: float,
         thinking: str | None = None, ceiling: int | None = None, per_call_usd: str | None = None) -> int:
    from tests.replays import cassettes
    from tests.replays.engine_runner import pin_scratch_database, run_case
    from tests.replays.harness import CassetteRecorder
    from tests.replays.ideal_reader import IdealReader
    from tests.replays.marking import FAIL, NOT_EXERCISED, PASS, cards_about, judge

    pin_scratch_database()
    key = os.environ[LIVE_KEY_ENV]
    rows, tokens_in, tokens_out, calls, truncated = [], 0, 0, 0, 0
    name = scorecard_name(date.today().isoformat(), model, site, thinking)
    beside = SCORES / name if site is not None else None
    cap, stopped = SpendCap(max_usd, model), None
    for case in _cases(ids):
        inner = (SiteModel(site, CappedModel(LiveModel(key, model), cap), IdealReader(case))
                 if site is not None else CappedModel(LiveModel(key, model), cap))
        recorder = CassetteRecorder(inner)
        run = run_case(case, recorder, keep=True)
        from genios_engine.api import routes
        from tests.replays.engine_runner import remove_tenant
        try:
            checked = _checked(routes._graph.engine, run.org_id)
        finally:
            remove_tenant(routes._graph.engine, run.org_id)
        mark = judge(case, run)
        paid = spend(recorder.ledger, site)
        tokens_in += paid["tokens_in"]
        tokens_out += paid["tokens_out"]
        calls += paid["calls"]
        truncated += paid["truncated_calls"]
        if beside is not None:
            # BESIDE, never instead: the live answers and the verdict they reach, kept apart from the
            # authored cassettes, and the authored verdict replayed for the comparison.
            beside.mkdir(parents=True, exist_ok=True)
            (beside / f"{case.case_id}.json").write_text(
                json.dumps(recorder.cassette, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            recorded = judge(case, cassettes.replay(case))
        elif keep:
            cassettes.save(case, recorder.cassette, source=f"{cassettes.LIVE_PREFIX}{model}")
        expected = sum(len(cards_about(run, e.about)) for e in case.cards if e.min >= 1)
        rows.append({"case": case.case_id, "kind": case.kind, "verdict": mark.verdict,
                     "lost_at": mark.lost_at, "cards": len(run.cards),
                     "cards_about_the_subject": expected,
                     "forbidden": [list(h) for h in mark.forbidden_hits], "reason": mark.reason,
                     "calls": paid["calls"], "truncated_calls": paid["truncated_calls"],
                     **checked,
                     **({"authored_verdict": recorded.verdict} if beside is not None else {})})
        print(f"{case.case_id} {mark.verdict:<15} {mark.reason[:100]}")
        if cap.reached:
            stopped = case.case_id
            print(f"STOPPED at {case.case_id}: --max-usd {max_usd:g} reached (${cap.spent_usd:.4f} spent)")
            break
    detect = [r for r in rows if r["kind"] == "must_detect" and r["verdict"] != "not_expressible"]
    cards = sum(r["cards"] for r in rows)
    price_in, price_out = price_per_mtok(model)
    card = {"model": model, "site": site, "date": date.today().isoformat(), "cases": rows,
            "recall": round(sum(r["verdict"] == PASS for r in detect) / len(detect), 3)
            if detect else None,
            "precision": round(sum(r["cards_about_the_subject"] for r in rows) / cards, 3)
            if cards else None,
            "abstain_failures": sum(r["kind"] == "must_abstain" and r["verdict"] in
                                    (FAIL, NOT_EXERCISED) for r in rows),
            "forbidden_outputs": sum(len(r["forbidden"]) for r in rows),
            # The check, summed over every case (M35.C4.L-integration.V2.U04).
            **{key: dict(sorted(sum((Counter(r[key]) for r in rows), Counter()).items()))
               for key in ("reviews", "fates", "dropped", "noted")},
            "tokens_in": tokens_in, "tokens_out": tokens_out,
            "cost_usd": round(tokens_in / 1e6 * price_in + tokens_out / 1e6 * price_out, 4),
            # Every call the pass paid for, a cut one included, and the run's own settings and cap.
            "calls": calls, "truncated_calls": truncated, "thinking": thinking, "ceiling": ceiling,
            "per_call_usd": per_call_usd, "max_usd": max_usd, "stopped_at_cap": stopped,
            "spent_usd": round(cap.spent_usd, 4)}
    if beside is not None:
        card["moved"] = [r["case"] for r in rows if r["verdict"] != r["authored_verdict"]]
    SCORES.mkdir(parents=True, exist_ok=True)
    out = SCORES / f"{name}.json"
    out.write_text(json.dumps(card, indent=1) + "\n", encoding="utf-8")
    print(f"\nrecall {card['recall']} · precision {card['precision']} · forbidden "
          f"{card['forbidden_outputs']} · ${card['cost_usd']} · {calls} calls, {truncated} cut → {out}")
    return 0


# =================================================================================================
# `--site brief` (s15-D1) · outside the normal chain, so outside `identify_site`'s dispatch too.
# Every function above assumes a site's prompts turn up DURING `run_case`'s sweeps; the brief's
# writer runs AFTER the last one, through `executive/morning_writer.write_brief` directly — so
# this is a second, smaller pair of functions rather than a third branch threaded through `live`
# and `dry_run`, which would otherwise gain a site that cannot use either's own machinery.
# =================================================================================================

def _brief_day(case):
    """One case's day, composed on the scratch database with NO model (the ideal reader's own
    cassette answers the rest of the chain) — the input `write_brief` would be handed, and what a
    dry run prices without ever asking a real one."""
    from tests.replays import cassettes
    from tests.replays.engine_runner import remove_tenant, run_case
    from tests.replays.harness import RecordedLLM

    run = run_case(case, RecordedLLM(cassettes.load(case)), keep=True, brief=False)
    from genios_engine.api import routes
    from genios_engine.executive.morning_day import read_day
    from genios_engine.platform.seats import OWNER_SEAT_ID
    engine = routes._graph.engine
    try:
        with engine.connect() as conn:
            day = read_day(conn, run.org_id, OWNER_SEAT_ID, now=case.sweeps[-1])
    except Exception:
        remove_tenant(engine, run.org_id)
        raise
    return engine, run.org_id, day


def dry_run_brief(ids: list[str]) -> int:
    """What a live `--site brief` pass would cost, priced at each tier's own ceiling
    (`reason/bundle/sites.max_output_tokens`, `reason/bundle/budget.cost_micro_usd`) — never a
    cassette: R-8 and R-8E have no recorded calls to read one from. Touches the scratch database
    to compose each case's real day; asks no model."""
    from genios_engine.executive.morning_prompt import build_prompt
    from genios_engine.platform.seats import OWNER_SEAT_ID
    from genios_engine.reason.bundle.budget import cost_micro_usd
    from genios_engine.reason.bundle.sites import SITE_BRIEF, SITE_BRIEF_ESCALATE, TIER_T1, TIER_T2, max_output_tokens
    from tests.replays.engine_runner import pin_scratch_database, remove_tenant

    pin_scratch_database()
    cases = _cases(ids)
    t1_total = t2_total = 0.0
    print(f"{'case':<5} {'chars':>7} {'~tok in':>8} {'$ R-8':>9} {'$ R-8E':>9}  title")
    for case in cases:
        engine, org_id, day = _brief_day(case)
        try:
            prompt = build_prompt(items=day.items, now=case.sweeps[-1], tz=day.tz)
        finally:
            remove_tenant(engine, org_id)
        tokens_in = -(-len(prompt) // 4)
        t1 = cost_micro_usd(tier=TIER_T1, input_tokens=tokens_in,
                            output_tokens=max_output_tokens(SITE_BRIEF)) / 1e6
        t2 = cost_micro_usd(tier=TIER_T2, input_tokens=tokens_in,
                            output_tokens=max_output_tokens(SITE_BRIEF_ESCALATE)) / 1e6
        t1_total, t2_total = t1_total + t1, t2_total + t2
        print(f"{case.case_id:<5} {len(prompt):>7} {tokens_in:>8} ${t1:>8.4f} ${t2:>8.4f}  "
              f"{case.title[:50]}")
    print(f"\n{len(cases)} cases · if every R-8 draft holds: ${t1_total:.2f} · if every case also "
          f"escalates once to R-8E: ${t1_total + t2_total:.2f} (the upper bound, never both at "
          "once in a real pass) at list price, each tier's own ceiling. Composed from the scratch "
          "database (no cassette exists for these two sites yet); no model was asked.")
    return 0


def live_brief(ids: list[str], *, max_usd: float, key: str) -> int:
    """R-8's draft on each case's real day, checked; R-8E once if it fails; the template if that
    fails too — set beside its template (a `given_back` verdict already is that comparison, line
    by line). Two spend caps, one per tier, each stopping before a call whose worst case would
    cross `max_usd` — so the worst a run can spend is `2 * max_usd`, documented rather than shared
    arbitrarily between tiers that price differently."""
    from genios_engine.contracts import morning_brief as B
    from genios_engine.executive.morning_template import template_brief
    from genios_engine.executive.morning_writer import write_brief
    from genios_engine.platform.l4_activation import FEATURE_MORNING_BRIEF
    from genios_engine.platform.seats import OWNER_SEAT_ID
    from genios_engine.reason.bundle.sites import TIER_T1, TIER_T2
    from genios_engine.reason.llm_sites import tier_model
    from tests.replays.engine_runner import pin_scratch_database, remove_tenant

    pin_scratch_database()
    t1_model, t2_model = tier_model(TIER_T1), tier_model(TIER_T2)
    cap1, cap2 = SpendCap(max_usd, t1_model), SpendCap(max_usd, t2_model)
    rows, stopped = [], None
    for case in _cases(ids):
        engine, org_id, day = _brief_day(case)
        try:
            template = template_brief(org_id=org_id, seat_id=OWNER_SEAT_ID, items=day.items,
                                      now=case.sweeps[-1], tz=day.tz)
            try:
                brief = write_brief(
                    engine, org_id=org_id, seat_id=OWNER_SEAT_ID, items=day.items,
                    now=case.sweeps[-1], tz=day.tz, founder=(case.founder.name,),
                    client_t1=CappedModel(LiveModel(key, t1_model), cap1),
                    client_t2=CappedModel(LiveModel(key, t2_model), cap2),
                    activated=frozenset({FEATURE_MORNING_BRIEF}))
            except SpendCapReached as exc:
                stopped = case.case_id
                print(f"STOPPED at {case.case_id}: {exc}")
                break
        finally:
            remove_tenant(engine, org_id)
        kept = sum(1 for l in brief.lines if l.verdict == B.KEPT)
        given_back = sum(1 for l in brief.lines if l.verdict == B.GIVEN_BACK)
        rows.append({"case": case.case_id, "written_by": brief.written_by, "model": brief.model,
                     "tier": brief.tier, "cost_micro_usd": brief.cost_micro_usd,
                     "lines": len(brief.lines), "kept": kept, "given_back": given_back,
                     "template_lines": len(template.lines), "why": brief.why})
        print(f"{case.case_id} {brief.written_by:<10} kept={kept} given_back={given_back} "
              f"cost=${brief.cost_micro_usd / 1e6:.4f}")
    card = {"date": date.today().isoformat(), "t1_model": t1_model, "t2_model": t2_model,
            "max_usd": max_usd, "stopped_at": stopped, "cases": rows,
            "spent_usd": round(cap1.spent_usd + cap2.spent_usd, 4),
            "written": sum(r["written_by"] == B.WRITTEN for r in rows),
            "escalated": sum(r["written_by"] == B.ESCALATED for r in rows),
            "template": sum(r["written_by"] == B.TEMPLATE_BRIEF for r in rows)}
    SCORES.mkdir(parents=True, exist_ok=True)
    out = SCORES / f"{scorecard_name(date.today().isoformat(), 'brief', None, None)}.json"
    out.write_text(json.dumps(card, indent=1) + "\n", encoding="utf-8")
    print(f"\nwritten {card['written']} · escalated {card['escalated']} · template "
          f"{card['template']} · ${card['spent_usd']} spent → {out}")
    return 0


def _positive(value: str) -> float:
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {value!r}") from None
    if not number > 0:
        raise argparse.ArgumentTypeError(f"must be more than 0: {value!r}")
    return number


def _usd(value: str) -> str:
    """A positive dollar amount, kept as typed — the budget table holds dollars as text."""
    _positive(value)
    return value


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--dry-run", action="store_true", help="the estimate; no database, no model")
    ap.add_argument("--live", action="store_true", help="the real model (needs --spend-ok)")
    ap.add_argument("--record", action="store_true",
                    help="(re)write cassettes: with --live the live model's, alone the ideal "
                         "reader's")
    ap.add_argument("--model", default=None,
                    help=f"the model (default: the site's own tier's, else {DEFAULT_MODEL})")
    ap.add_argument("--site", default=None,
                    help="one model site only — a tests/replays/harness.SITE_MARKERS name")
    ap.add_argument("--spend-ok", action="store_true",
                    help="confirm that a live run may spend model money (D12c)")
    ap.add_argument("--max-usd", type=_positive, default=None,
                    help="--live only, and required: stop before a call whose worst case crosses it")
    ap.add_argument("--thinking", choices=("off", "adaptive"), default=None,
                    help="the site's thinking mode for this run (06 D72); default the site's own")
    ap.add_argument("--ceiling", type=int, default=None,
                    help="the site's output ceiling for this run (06 D72); default the site's own")
    ap.add_argument("--per-call-usd", type=_usd, default=None,
                    help="the site's per-call cap for this run, e.g. 0.15 (06 D72 arm B)")
    ap.add_argument("cases", nargs="*", help="case ids (default: every case)")
    args = ap.parse_args(argv)
    run_settings = {"thinking": args.thinking, "ceiling": args.ceiling, "per_call_usd": args.per_call_usd}
    if any(v is not None for v in run_settings.values()) and args.site not in SITE_TIERS:
        ap.error("--thinking, --ceiling and --per-call-usd set one site's R-site for the run: name a "
                 f"--site with a tier of its own ({', '.join(SITE_TIERS)})")
    if args.ceiling is not None and args.ceiling <= 0:
        ap.error("--ceiling is a positive number of tokens")

    if args.dry_run and (args.live or args.record):
        ap.error("--dry-run runs nothing; it cannot be combined with --live or --record")
    if args.site is not None and args.site != BRIEF_SITE and args.site not in sites():
        ap.error(f"no such site: {args.site!r} — one of {', '.join((*sites(), BRIEF_SITE))}")
    if args.site is not None and args.record:
        ap.error("--site's live pass is kept BESIDE the authored cassettes, never instead (06 D50) "
                 f"— {BRIEF_SITE!r} has no cassette shape at all: drop --record")
    if args.site == BRIEF_SITE and args.model:
        ap.error(f"--site {BRIEF_SITE} always asks both R-8 (Haiku-class) and R-8E (Sonnet-class) "
                 "on their own tiers (s15-D1): --model does not apply")
    if args.dry_run and args.site == BRIEF_SITE:
        return dry_run_brief(args.cases)
    model = model_for(args.site, args.model)
    if args.dry_run:
        return dry_run(args.cases, model, args.site)
    if args.live:
        if not os.environ.get(LIVE_KEY_ENV) or not args.spend_ok:
            print(f"--live spends model money: it needs a key in {LIVE_KEY_ENV} and --spend-ok "
                  "(06-DECISIONS D12c — the default is no spend). Run --dry-run for the "
                  "estimate.", file=sys.stderr)
            return 2
        if args.max_usd is None:
            print("--live needs --max-usd: the pass stops before a call whose worst case would cross "
                  "it (06 D65's money is finite)", file=sys.stderr)
            return 2
        if args.site == BRIEF_SITE:
            return live_brief(args.cases, max_usd=args.max_usd, key=os.environ[LIVE_KEY_ENV])
        r_site = SITE_TIERS.get(args.site or "")
        with site_settings(r_site, **run_settings) if r_site else contextlib.nullcontext():
            return live(args.cases, model, args.record, args.site, max_usd=args.max_usd, **run_settings)
    if args.record:
        from tests.replays.engine_runner import pin_scratch_database
        pin_scratch_database()
        record(args.cases)
        return 0
    ap.error("say what to do: --dry-run, --record, or --live")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
