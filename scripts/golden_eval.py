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


def tally(rows: list[dict], attempts: list[dict]) -> dict:
    """What the check made of a run's expert reviews, and what the ladder did to get them (STEP-13 M35.C4.L-integration.
    V2.U04; STEP-13b M38.C3.L-interface.V2.U01): each review's status and fate, every dropped line's reason and every
    NOTED one's, the misquote rate (decisive facts misquoted over those that quote a mail), the rate of
    `unknown_evidence`, the lines whose source is the engine and the expert's own (and the own lines dropped), the
    tokens and cost, the held share of the valid reviews — and the ladder: which rung answered, every consult, why a
    file climbed and what each rung cost. Pure: `rows` are `expert_reviews` rows (status, checked, review, rung, tokens,
    cost), `attempts` are `expert_review_attempts` rows. Read from the run's tables before its tenant is removed."""
    statuses, fates, dropped, noted = Counter(), Counter(), Counter(), Counter()
    facts = quoting = misquoted = unknown = engine = own = own_dropped = 0
    tin = tout = cost = 0
    stood = Counter()
    for row in rows:
        statuses[row["status"]] += 1
        tin, tout, cost = (tin + int(row.get("input_tokens") or 0), tout + int(row.get("output_tokens") or 0),
                           cost + int(row.get("cost_micro_usd") or 0))
        stood[str(row.get("rung") or 1)] += 1
        checked = row.get("checked")
        if not checked:
            continue
        fates[str(checked.get("fate"))] += 1
        verdicts = checked.get("verdicts") or ()
        dropped.update(str(v.get("reason")) for v in verdicts if v.get("verdict") == "dropped")
        noted.update(str(v.get("reason")) for v in verdicts if v.get("verdict") == "noted")
        written = (row.get("review") or {}).get("facts") or ()
        facts += len(written)
        quoting += sum(1 for f in written if f.get("quote"))
        misquoted += len({str(v["line"]).partition(":")[2] for v in verdicts if v.get("verdict") == "dropped"
                          and v.get("reason") == "misquoted" and str(v.get("line", "")).partition(":")[0] in ("fact", "quote")})
        unknown += sum(1 for v in verdicts if v.get("verdict") == "dropped" and v.get("reason") == "unknown_evidence"
                       and str(v.get("line", "")).startswith("fact:"))
        engine += sum(1 for v in verdicts if v.get("source") in ("engine", "mixed")
                      and str(v.get("line", "")).partition(":")[0] in ("fact", "inference", "pattern"))
        own += sum(1 for v in verdicts if str(v.get("line", "")).startswith("own:"))
        own_dropped += sum(1 for v in verdicts if str(v.get("line", "")).startswith("own:") and v.get("verdict") == "dropped")
    consults, climbs, by_rung = Counter(), Counter(), Counter()
    for a in attempts:
        consults[f"{a['rung']}:{a['consult']}"] += 1
        if a.get("climbed_because"):
            climbs[a["climbed_because"]] += 1
        by_rung[str(a["rung"])] += int(a.get("cost_micro_usd") or 0)

    def rate(n: int, d: int):
        return round(n / d, 3) if d else None
    return {"reviews": dict(sorted(statuses.items())), "fates": dict(sorted(fates.items())),
            "dropped": dict(sorted(dropped.items())), "noted": dict(sorted(noted.items())),
            "held_share": rate(fates["held"], statuses["valid"]),
            "facts": facts, "facts_quoting": quoting, "misquoted": misquoted, "misquote_rate": rate(misquoted, quoting),
            "unknown_evidence": unknown, "unknown_evidence_rate": rate(unknown, facts),
            "engine_lines": engine, "own_lines": own, "own_dropped": own_dropped,
            "tokens_in": tin, "tokens_out": tout, "cost_micro_usd": cost,
            "ladder": {"stood": dict(sorted(stood.items())), "attempts": dict(sorted(consults.items())),
                       "climbs": dict(sorted(climbs.items())), "cost_micro_usd": dict(sorted(by_rung.items()))}}


#: The counts a tally sums over cases, the maps it merges, and the rates it works out again from the sums.
_SUMS = ("facts", "facts_quoting", "misquoted", "unknown_evidence", "engine_lines", "own_lines", "own_dropped",
         "tokens_in", "tokens_out", "cost_micro_usd")
_MAPS = ("reviews", "fates", "dropped", "noted")


def combine(tallies: list[dict]) -> dict:
    """The tallies of several cases as one — what a scorecard's total says. Counts are summed, maps merged, every rate
    worked out again from the sums (a mean of rates is no rate)."""
    out: dict = {key: dict(sorted(sum((Counter(t.get(key) or {}) for t in tallies), Counter()).items()))
                 for key in _MAPS}
    for key in _SUMS:
        out[key] = sum(int(t.get(key) or 0) for t in tallies)
    ladder = {k: dict(sorted(sum((Counter((t.get("ladder") or {}).get(k) or {}) for t in tallies), Counter()).items()))
              for k in ("stood", "attempts", "climbs", "cost_micro_usd")}

    def rate(n: int, d: int):
        return round(n / d, 3) if d else None
    out.update(held_share=rate(out["fates"].get("held", 0), out["reviews"].get("valid", 0)),
               misquote_rate=rate(out["misquoted"], out["facts_quoting"]),
               unknown_evidence_rate=rate(out["unknown_evidence"], out["facts"]), ladder=ladder)
    return out


def _checked(engine, org: str) -> dict:
    """`tally` of one tenant's expert reviews and attempts, read before the tenant is removed."""
    from sqlalchemy import text

    def json_of(value):
        return value if isinstance(value, (dict, list)) or value is None else json.loads(value)
    with engine.connect() as c:
        rows = [{**dict(r._mapping), "checked": json_of(r.checked), "review": json_of(r.review)}
                for r in c.execute(text("select status, checked, review, rung, input_tokens, output_tokens, "
                                        "cost_micro_usd from expert_reviews where org_id = :o"), {"o": org})]
        attempts = [dict(r._mapping) for r in c.execute(text(
            "select rung, consult, status, climbed_because, cost_micro_usd from expert_review_attempts "
            "where org_id = :o"), {"o": org})]
    return tally(rows, attempts)


class SharedCap:
    """ONE `--max-usd` for a pass that asks several models — the ladder's rungs. What is spent and whether a call was
    refused are shared; each rung's model is priced at its own list price (`for_model`)."""

    def __init__(self, max_usd: float) -> None:
        self.max_usd, self.spent_usd, self.reached = float(max_usd), 0.0, False

    def for_model(self, model: str) -> "RungCap":
        return RungCap(self, model)


class RungCap:
    """`SpendCap`'s shape (`CappedModel` reads it) over a `SharedCap`, for one rung's model."""

    def __init__(self, pool: SharedCap, model: str) -> None:
        self._pool = pool
        self.price_in, self.price_out = price_per_mtok(model)

    max_usd = property(lambda self: self._pool.max_usd)
    spent_usd = property(lambda self: self._pool.spent_usd)

    @property
    def reached(self) -> bool:
        return self._pool.reached

    @reached.setter
    def reached(self, value: bool) -> None:
        self._pool.reached = bool(value)

    def worst_usd(self, prompt: str, max_tokens: int) -> float:
        return (-(-len(prompt) // 4) / 1e6 * self.price_in + int(max_tokens) / 1e6 * self.price_out)

    def charge(self, result) -> None:
        self._pool.spent_usd += (int(getattr(result, "input_tokens", 0) or 0) / 1e6 * self.price_in
                                 + int(getattr(result, "output_tokens", 0) or 0) / 1e6 * self.price_out)


@contextlib.contextmanager
def ladder_settings(tiers: tuple[str, ...]):
    """The expert's ladder for the length of a run: `tiers` as the sweep's default rungs, an Opus-class rung allowed
    where it is named (the tenant's leave, s13b-D1, is the run's) — put back after, whatever the run does."""
    from genios_engine.reason.bundle import sites as site_table
    from genios_engine.reason.expert import sweep
    before_ladder, before_clients = site_table.EXPERT_LADDER, sweep._clients
    try:
        site_table.EXPERT_LADDER = tuple(tiers)
        sweep._clients = lambda llm, ladder, *, allow_opus: before_clients(llm, ladder, allow_opus=True)
        yield
    finally:
        site_table.EXPERT_LADDER, sweep._clients = before_ladder, before_clients


def _case_row(case, run, mark, checked, paid, extra=None):
    from tests.replays.marking import cards_about
    expected = sum(len(cards_about(run, e.about)) for e in case.cards if e.min >= 1)
    return {"case": case.case_id, "kind": case.kind, "verdict": mark.verdict, "lost_at": mark.lost_at,
            "cards": len(run.cards), "cards_about_the_subject": expected,
            "forbidden": [list(h) for h in mark.forbidden_hits], "reason": mark.reason,
            "calls": paid["calls"], "truncated_calls": paid["truncated_calls"], **checked, **(extra or {})}


def _board(rows: list[dict]) -> dict:
    """The board over a run's cases: recall, precision, the abstain failures and the forbidden outputs, and the check
    summed over every case (M35.C4.L-integration.V2.U04; STEP-13b M38.C3.L-interface.V2.U01)."""
    from tests.replays.marking import FAIL, NOT_EXERCISED, PASS
    detect = [r for r in rows if r["kind"] == "must_detect" and r["verdict"] != "not_expressible"]
    cards = sum(r["cards"] for r in rows)
    return {"recall": round(sum(r["verdict"] == PASS for r in detect) / len(detect), 3) if detect else None,
            "precision": round(sum(r["cards_about_the_subject"] for r in rows) / cards, 3) if cards else None,
            "abstain_failures": sum(r["kind"] == "must_abstain" and r["verdict"] in (FAIL, NOT_EXERCISED)
                                    for r in rows),
            "forbidden_outputs": sum(len(r["forbidden"]) for r in rows), **combine(rows)}


def live(ids: list[str], model: str, keep: bool, site: str | None = None, *, max_usd: float,
         thinking: str | None = None, ceiling: int | None = None, per_call_usd: str | None = None,
         ladder: tuple[str, ...] | None = None) -> int:
    """The real model on the golden set, scored. With `ladder` (`T1,T2[,T3]`, STEP-13b M38.C3.L-interface.V13.U03) the
    expert's review climbs the rungs, each its real model, all under ONE `--max-usd`; the card says which rung answered
    each review, why a file climbed and what each rung cost."""
    from tests.replays import cassettes
    from tests.replays.engine_runner import pin_scratch_database, run_case
    from tests.replays.harness import CassetteRecorder
    from tests.replays.ideal_reader import IdealReader
    from tests.replays.marking import judge

    pin_scratch_database()
    key = os.environ[LIVE_KEY_ENV]
    tiers = tuple(ladder) if ladder else None
    if tiers:
        from genios_engine.reason.llm_sites import tier_model
        models = {tier: tier_model(tier) for tier in tiers}
        model = "ladder:" + ",".join(tiers)
    rows, tokens_in, tokens_out, calls, truncated = [], 0, 0, 0, 0
    per_rung: dict[str, Counter] = {t: Counter() for t in (tiers or ())}
    name = scorecard_name(date.today().isoformat(), "ladder-" + "-".join(tiers) if tiers else model, site, thinking)
    beside = SCORES / name if site is not None else None
    cap = SharedCap(max_usd) if tiers else SpendCap(max_usd, model)
    stopped = None
    for case in _cases(ids):
        if tiers:
            recorders = {t: CassetteRecorder(SiteModel("expert", CappedModel(
                LiveModel(key, models[t]), cap.for_model(models[t])), IdealReader(case))) for t in tiers}
            recorder = CassetteRecorder(IdealReader(case))
            with ladder_settings(tiers):
                run = run_case(case, recorder, keep=True, rungs=recorders)
        else:
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
        if tiers:
            paids = {t: spend(recorders[t].ledger, "expert") for t in tiers}
            paid = {k: sum(p[k] for p in paids.values()) for k in ("calls", "truncated_calls", "tokens_in", "tokens_out")}
            for t, p in paids.items():
                per_rung[t].update(p)
        else:
            paid = spend(recorder.ledger, site)
        tokens_in += paid["tokens_in"]
        tokens_out += paid["tokens_out"]
        calls += paid["calls"]
        truncated += paid["truncated_calls"]
        recorded = None
        if beside is not None:
            # BESIDE, never instead: the live answers and the verdict they reach, kept apart from the
            # authored cassettes, and the authored verdict replayed for the comparison.
            beside.mkdir(parents=True, exist_ok=True)
            for label, cassette in ((t, recorders[t].cassette) for t in tiers) if tiers else (("", recorder.cassette),):
                (beside / (f"{case.case_id}.{label}.json" if label else f"{case.case_id}.json")).write_text(
                    json.dumps(cassette, indent=1, sort_keys=True) + "\n", encoding="utf-8")
            recorded = judge(case, cassettes.replay(case))
        elif keep and not tiers:
            cassettes.save(case, recorder.cassette, source=f"{cassettes.LIVE_PREFIX}{model}")
        rows.append(_case_row(case, run, mark, checked, paid,
                              {"authored_verdict": recorded.verdict} if recorded is not None else None))
        print(f"{case.case_id} {mark.verdict:<15} {mark.reason[:100]}")
        if cap.reached:
            stopped = case.case_id
            print(f"STOPPED at {case.case_id}: --max-usd {max_usd:g} reached (${cap.spent_usd:.4f} spent)")
            break
        if cap.spent_usd >= cap.max_usd:
            stopped = case.case_id
            print(f"STOPPED after {case.case_id}: --max-usd {max_usd:g} spent — no case starts past it")
            break
    if tiers:
        priced = {t: price_per_mtok(models[t]) for t in tiers}
        cost = sum(per_rung[t]["tokens_in"] / 1e6 * priced[t][0] + per_rung[t]["tokens_out"] / 1e6 * priced[t][1]
                   for t in tiers)
    else:
        price_in, price_out = price_per_mtok(model)
        cost = tokens_in / 1e6 * price_in + tokens_out / 1e6 * price_out
    card = {"model": model, "site": site, "date": date.today().isoformat(), "cases": rows, **_board(rows),
            "tokens_in": tokens_in, "tokens_out": tokens_out, "cost_usd": round(cost, 4),
            # Every call the pass paid for, a cut one included, and the run's own settings and cap.
            "calls": calls, "truncated_calls": truncated, "thinking": thinking, "ceiling": ceiling,
            "per_call_usd": per_call_usd, "max_usd": max_usd, "stopped_at_cap": stopped,
            "spent_usd": round(cap.spent_usd, 4)}
    if tiers:
        card["ladder_tiers"] = list(tiers)
        card["rungs"] = {t: {"model": models[t], **{k: int(per_rung[t][k]) for k in
                                                     ("calls", "truncated_calls", "tokens_in", "tokens_out")},
                             "cost_usd": round(per_rung[t]["tokens_in"] / 1e6 * priced[t][0]
                                               + per_rung[t]["tokens_out"] / 1e6 * priced[t][1], 4)} for t in tiers}
    if beside is not None:
        card["moved"] = [r["case"] for r in rows if r["verdict"] != r["authored_verdict"]]
    return _write(card, name, calls, truncated)


def _write(card: dict, name: str, calls: int, truncated: int) -> int:
    SCORES.mkdir(parents=True, exist_ok=True)
    out = SCORES / f"{name}.json"
    out.write_text(json.dumps(card, indent=1) + "\n", encoding="utf-8")
    print(f"\nrecall {card['recall']} · precision {card['precision']} · forbidden "
          f"{card['forbidden_outputs']} · ${card['cost_usd']} · {calls} calls, {truncated} cut → {out}")
    return 0


def replay_live(folder: Path, ids: list[str]) -> int:
    """A kept live pass re-judged with NO spend (STEP-13b M38.C3.L-interface.V3.U02): the expert's recorded answers in
    `folder` (`scores/<date>-<model>-expert/`) replayed through the current chain, every other site answered by the
    authored cassette, the same scorecard written beside the folder. A recorded answer the current prompt no longer asks
    is `unasked`, a question the current prompt asks that the folder does not answer a `miss` — counted per case, never
    guessed: a miss reads as the model failing that call."""
    from tests.replays import cassettes
    from tests.replays.engine_runner import pin_scratch_database, remove_tenant, run_case
    from tests.replays.harness import CassetteRecorder, RecordedLLM
    from tests.replays.marking import judge

    pin_scratch_database()
    folder = Path(folder)
    if not folder.is_dir():
        raise SystemExit(f"no such folder: {folder}")
    rows, name, calls, truncated = [], f"{folder.name}-replay", 0, 0
    kept = {p.stem.split(".")[0]: p for p in sorted(folder.glob("F*.json"))}
    for case in _cases(ids):
        if case.case_id not in kept:
            print(f"{case.case_id} not in {folder.name} — skipped")
            continue
        answers = json.loads(kept[case.case_id].read_text(encoding="utf-8"))
        theirs = RecordedLLM(answers)
        recorder = CassetteRecorder(SiteModel("expert", theirs, RecordedLLM(cassettes.load(case))))
        run = run_case(case, recorder, keep=True)
        from genios_engine.api import routes
        try:
            checked = _checked(routes._graph.engine, run.org_id)
        finally:
            remove_tenant(routes._graph.engine, run.org_id)
        mark = judge(case, run)
        asked = {key for _site, key in theirs.calls}
        extra = {"misses": len(theirs.misses), "unasked": len(set(answers) - asked)}
        rows.append(_case_row(case, run, mark, checked, spend(recorder.ledger, "expert"), extra))
        print(f"{case.case_id} {mark.verdict:<15} misses={extra['misses']} unasked={extra['unasked']}")
    card = {"replayed": str(folder.name), "site": "expert", "date": date.today().isoformat(), "cases": rows,
            **_board(rows), "misses": sum(r["misses"] for r in rows), "unasked": sum(r["unasked"] for r in rows),
            "spent_usd": 0.0}
    for r in rows:
        calls, truncated = calls + r["calls"], truncated + r["truncated_calls"]
    card["cost_usd"] = round(card["cost_micro_usd"] / 1e6, 4)
    SCORES.mkdir(parents=True, exist_ok=True)
    out = folder.parent / f"{name}.json"
    out.write_text(json.dumps(card, indent=1) + "\n", encoding="utf-8")
    print(f"\nrecall {card['recall']} · forbidden {card['forbidden_outputs']} · {card['misses']} misses, "
          f"{card['unasked']} unasked · nothing spent → {out}")
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


#: The targets of STEP-13b's live passes (M38.C4.L-integration.V15.U02), unless an index names others: forbidden outputs 0 and
#: must-abstain 13 of 13 on every model; the ladder's must-detect at least Sonnet-alone's; the ladder's cost per review below
#: Sonnet-alone's; the held share of Haiku's valid reviews below half (68 of 86 before this step).
TARGETS = {"forbidden": 0, "must_abstain": 13, "held_share_below": 0.5}
MET, MISSED, NOT_RUN = "met", "MISSED", "not run"


def _card_of(index_dir: Path, path) -> dict | None:
    """The kept scorecard an index names — None when it names none, or the file is not there."""
    if not path:
        return None
    file = (index_dir / path)
    return json.loads(file.read_text(encoding="utf-8")) if file.is_file() else None


def _per_review(card: dict) -> float | None:
    valid = (card.get("reviews") or {}).get("valid") or 0
    return round(float(card.get("cost_usd") or 0) / valid, 4) if valid else None


def assert_scorecards(index_path: Path) -> int:
    """The kept scorecards an index names meet their targets — no model, no database (STEP-13b M38.C3.L-interface.V13.U03).
    `{"scorecards": {"haiku": <file>, "sonnet": <file>, "ladder": <file>}, "targets": {…}}`, files relative to the index.
    Every target is said — met, MISSED, or not run — and one missed is said, never loosened: exit 1; any scorecard not
    yet kept leaves its targets not run: exit 3 (the passes are the lead's, they spend money); every target met: 0."""
    index_path = Path(index_path)
    if not index_path.is_file():
        print(f"no such index: {index_path}", file=sys.stderr)
        return 2
    index = json.loads(index_path.read_text(encoding="utf-8"))
    targets = {**TARGETS, **(index.get("targets") or {})}
    cards = {name: _card_of(index_path.parent, (index.get("scorecards") or {}).get(name))
             for name in ("haiku", "sonnet", "ladder")}
    results: list[tuple[str, str, str]] = []

    def said(name: str, state: str, detail: str) -> None:
        results.append((name, state, detail))
        print(f"{state:<8} {name}: {detail}")
    for model, card in cards.items():
        if card is None:
            said(f"{model}: forbidden and must-abstain", NOT_RUN, "no scorecard kept")
            continue
        abstain = [r for r in card.get("cases") or () if r.get("kind") == "must_abstain"]
        held_ok = (card.get("forbidden_outputs") == targets["forbidden"] and not card.get("abstain_failures")
                   and len(abstain) == targets["must_abstain"])
        said(f"{model}: forbidden {targets['forbidden']} and must-abstain {targets['must_abstain']} of "
             f"{targets['must_abstain']}", MET if held_ok else MISSED,
             f"forbidden {card.get('forbidden_outputs')}, abstain failures {card.get('abstain_failures')}, "
             f"{len(abstain)} abstain cases")
    ladder, sonnet, haiku = cards["ladder"], cards["sonnet"], cards["haiku"]
    if ladder is None or sonnet is None:
        said("the ladder's must-detect at least Sonnet-alone's", NOT_RUN, "needs the ladder's and Sonnet's scorecards")
        said("the ladder's cost per review below Sonnet-alone's", NOT_RUN, "needs the ladder's and Sonnet's scorecards")
    else:
        recall_l, recall_s = ladder.get("recall"), sonnet.get("recall")
        said("the ladder's must-detect at least Sonnet-alone's",
             MET if recall_l is not None and recall_s is not None and recall_l >= recall_s else MISSED,
             f"ladder {recall_l}, Sonnet {recall_s}")
        cost_l, cost_s = _per_review(ladder), _per_review(sonnet)
        said("the ladder's cost per review below Sonnet-alone's",
             MET if cost_l is not None and cost_s is not None and cost_l < cost_s else MISSED,
             f"ladder ${cost_l}, Sonnet ${cost_s} a valid review")
    if haiku is None:
        said(f"the held share of Haiku's valid reviews below {targets['held_share_below']}", NOT_RUN, "no scorecard kept")
    else:
        valid = (haiku.get("reviews") or {}).get("valid") or 0
        held = (haiku.get("fates") or {}).get("held", 0)
        share = round(held / valid, 3) if valid else None
        said(f"the held share of Haiku's valid reviews below {targets['held_share_below']}",
             MET if share is not None and share < targets["held_share_below"] else MISSED,
             f"{held} of {valid} held ({share}); 68 of 86 before this step")
    missed = [r for r in results if r[1] == MISSED]
    unrun = [r for r in results if r[1] == NOT_RUN]
    if missed:
        print(f"\n{len(missed)} target(s) MISSED — said, not loosened: the ladder then starts at T2 (s13b-D2).")
        return 1
    if unrun:
        print(f"\n{len(unrun)} target(s) not run: the scorecards are not all kept yet (the lead's live passes).")
        return 3
    print("\nevery target met")
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
    ap.add_argument("--ladder", default=None, metavar="T1,T2[,T3]",
                    help="--live --site expert: the expert's review climbs these rungs, each its real model, under "
                         "one --max-usd (STEP-13b); the scorecard says which rung answered and why it climbed")
    ap.add_argument("--replay-live", default=None, metavar="FOLDER",
                    help="re-judge a kept live pass (scores/<date>-<model>-expert/) with no spend: its recorded "
                         "answers replayed, the scorecard written beside it")
    ap.add_argument("--assert-scorecards", default=None, metavar="INDEX",
                    help="the kept scorecards an index names meet their targets — no model, no database")
    ap.add_argument("cases", nargs="*", help="case ids (default: every case)")
    args = ap.parse_args(argv)
    if args.assert_scorecards:
        if args.dry_run or args.live or args.record or args.ladder is not None or args.replay_live:
            ap.error("--assert-scorecards reads kept scorecards; it combines with nothing")
        return assert_scorecards(Path(args.assert_scorecards))
    tiers = None
    if args.ladder is not None:
        tiers = tuple(t.strip().upper() for t in args.ladder.split(",") if t.strip())
        from genios_engine.reason.bundle.sites import EXPERT_RUNGS
        if not tiers or any(t not in EXPERT_RUNGS for t in tiers) or list(tiers) != sorted(set(tiers)):
            ap.error(f"--ladder is rungs cheapest first, each once: one of {','.join(EXPERT_RUNGS)} (e.g. T1,T2)")
        if not args.live or args.site not in (None, "expert") or args.model or args.record:
            ap.error("--ladder is the expert's LIVE pass up the rungs: --live --site expert, each rung its own model "
                     "(no --model), nothing recorded")
        args.site = "expert"
    if args.replay_live:
        if args.live or args.dry_run or args.record or args.ladder is not None:
            ap.error("--replay-live spends nothing and runs nothing live: it combines with no other mode")
        return replay_live(Path(args.replay_live), args.cases)
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
        r_site = None if tiers else SITE_TIERS.get(args.site or "")
        with site_settings(r_site, **run_settings) if r_site else contextlib.nullcontext():
            return live(args.cases, model, args.record, args.site, max_usd=args.max_usd, ladder=tiers,
                        **run_settings)
    if args.record:
        from tests.replays.engine_runner import pin_scratch_database
        pin_scratch_database()
        record(args.cases)
        return 0
    ap.error("say what to do: --dry-run, --record, or --live")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
