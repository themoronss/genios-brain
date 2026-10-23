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
    python scripts/golden_eval.py --dry-run --site reason_l2     # R-9's model and settings (GeniOS-011 S07.U1)
    GENIOS_TEST_DATABASE_URL=… GENIOS_GOLDEN_LIVE_KEY=sk-… python scripts/golden_eval.py \\
        --probe --site reason_l2 --l2-path --spend-ok --max-usd 0.5 [F13]   # R-9's first two calls, read first
        --live --site reason_l2 --l2-path --spend-ok --max-usd N [F03 …]    # R-9 on its tier, down the L2 path

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

  --site reason_l2  GeniOS-011 S07.U1 (the audit's `process-golden-eval-r9-wrong-model`): R-9, the Layer 2
              judgment, asked on ITS tier — `claude-sonnet-5`, thinking off, an 8,000-token ceiling, the site
              table's own (`reason/bundle/sites`) — where before it was asked on the default Haiku with none
              of R-9's settings. Today's path never asks R-9 (`l2_reasoning` is switched on only down the L2
              path, `engine_runner.switch_on_the_expert`), so its live pass and its probe need `--l2-path`. No
              cassette holds an R-9 answer — the L2 path is never recorded (`tests/replays/l2_score`) — so its
              dry run names the model, the settings and one call's worst case, never a recorded total.

  --l2-path   Runs the cases down the L2 path (`GENIOS_GOLDEN_L2=1`, `engine_runner.l2_path`) for the run alone,
              and puts the switch back after; the scorecard says which path it measured. Without it a run
              takes today's path, even from a shell that exported the switch. Never with `--record`: the
              cassettes are today's path, and CI replays them down it.

  --probe     A live pass's first two calls and no more (`PROBE_CALLS`), each one's `stop_reason` and
              `output_tokens` printed as it returns, and no scorecard — the 1-2 calls read before any paid
              pass (the Sonnet 5 pass of 12 Oct was 203 calls cut at the ceiling, found after the spend). It
              needs every consent `--live` needs: the key, `--spend-ok` and `--max-usd`.

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
import threading
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
#: A cassette site whose production model is its tier's, not the default: the expert's (R-7, T2) and the Layer 2
#: judgment's (R-9, T2). GeniOS-011 S07.U1: before R-9 was here, `--site reason_l2` asked Haiku, and the run's
#: site settings (`site_settings`, which only a site here gets) never reached R-9's row.
SITE_TIERS = {"expert": "R-7", "reason_l2": "R-9"}
#: The site R-9 answers. Today's path never asks it, so its live pass and probe need `--l2-path`.
L2_SITE = "reason_l2"
#: GeniOS-011 S07.U1 · the most live calls a `--probe` makes: "test 1-2 calls first", before any paid pass.
PROBE_CALLS = 2
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


def site_profile(site: str | None) -> dict | None:
    """What a site with a tier of its own is asked with in production: its R-site, its tier's model, and the site
    table's own thinking mode, output ceiling and per-call timeout (`reason/bundle/sites`) — what a live pass
    sends unless `--thinking`/`--ceiling` name an arm. None for a site on the default model. GeniOS-011 S07.U1:
    the dry run says it, so R-9's model and settings are checkable with no key, no database and no model."""
    if site not in SITE_TIERS:
        return None
    from genios_engine.reason.bundle import sites as site_table
    r_site = SITE_TIERS[site]
    return {"r_site": r_site, "model": model_for(site, None), "thinking": site_table.thinking_mode(r_site),
            "ceiling": site_table.max_output_tokens(r_site), "timeout_s": site_table.timeout_s(r_site)}


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


class ProbeComplete(BaseException):
    """The probe has made its calls, and the run stops here. A `BaseException` for the reason
    `harness.CassetteMiss` is one: every model site sits inside `except Exception`, which would swallow the stop
    and let the case ask again."""


class ProbeModel:
    """The live model for a probe (GeniOS-011 S07.U1): at most `limit` calls, each one's `stop_reason` and
    `output_tokens` printed as it returns — with the ceiling and thinking mode it was asked at — so the first
    calls are read before any paid pass. The count is taken under a lock: the L2 drain asks from a thread pool."""

    def __init__(self, inner, limit: int = PROBE_CALLS) -> None:
        self._inner, self.limit = inner, int(limit)
        self.model = getattr(inner, "model", "")
        self.made: list[dict] = []
        self._taken = 0
        self._lock = threading.Lock()

    @property
    def supports_thinking(self) -> bool:
        return bool(getattr(self._inner, "supports_thinking", False))

    @property
    def full(self) -> bool:
        return self._taken >= self.limit

    def content_hash(self, material: str) -> str:
        return self._inner.content_hash(material)

    def call(self, prompt: str, *, max_tokens: int = 4096, **kw):
        from tests.replays.harness import identify_site
        with self._lock:
            if self._taken >= self.limit:
                raise ProbeComplete(f"the probe's {self.limit} calls are made")
            self._taken += 1
            number = self._taken
        result = self._inner.call(prompt, max_tokens=max_tokens, **kw)
        stop_reason = getattr(self._inner, "stop_reason", lambda: None)()
        row = {"call": number, "site": identify_site(prompt), "model": self.model, "stop_reason": stop_reason,
               "output_tokens": int(getattr(result, "output_tokens", 0) or 0), "max_tokens": int(max_tokens),
               "thinking": kw.get("thinking"), "input_tokens": int(getattr(result, "input_tokens", 0) or 0),
               "error": getattr(result, "error", None)}
        with self._lock:
            self.made.append(row)
        error = f" · error={str(row['error'])[:160]}" if row["error"] else ""
        print(f"probe {number}/{self.limit} · {row['site']} · {self.model} · stop_reason={stop_reason} · "
              f"output_tokens={row['output_tokens']} of max_tokens={max_tokens} · thinking={row['thinking']} · "
              f"input_tokens={row['input_tokens']}{error}", flush=True)
        return result


@contextlib.contextmanager
def l2_path_for_the_run(l2: bool):
    """GeniOS-011 S07.U1 · the path the run's cases take is `--l2-path`'s — `GENIOS_GOLDEN_L2=1`, which
    `engine_runner.l2_path` reads — never an inherited shell's: unset, the switch is cleared for the run, so an
    exported one cannot turn an expert pass into an L2 pass with nothing on the command line saying so. Put back
    after, whatever the run does."""
    from tests.replays.engine_runner import L2_PATH_ENV
    before = os.environ.get(L2_PATH_ENV)
    try:
        if l2:
            os.environ[L2_PATH_ENV] = "1"
        else:
            os.environ.pop(L2_PATH_ENV, None)
        yield
    finally:
        if before is None:
            os.environ.pop(L2_PATH_ENV, None)
        else:
            os.environ[L2_PATH_ENV] = before


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


def scorecard_name(day: str, model: str, site: str | None, thinking: str | None, *, l2: bool = False) -> str:
    """`<day>-<model>[-<site>][-<thinking>][-l2]` — an arm of `06` D72 never overwrites the other, and a pass down
    the L2 path never overwrites today's path's (GeniOS-011 S07.U1)."""
    return "-".join(part for part in (day, model, site, thinking, "l2" if l2 else None) if part)


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
    profile = site_profile(site)
    if profile is not None:
        # GeniOS-011 S07.U1 · what production asks this site with — read with no key and no model.
        timeout = f", timeout {profile['timeout_s']:g} s" if profile["timeout_s"] is not None else ""
        print(f"\n{site}: production asks {profile['r_site']} on {profile['model']} · thinking "
              f"{profile['thinking']} · ceiling {profile['ceiling']} output tokens{timeout} (reason/bundle/sites)")
        if total_calls == 0 and site == L2_SITE:
            print(f"No {site} call is recorded to price: the cassettes hold today's path, and the L2 path is never "
                  f"recorded (tests/replays/l2_score). One call's output is capped at {profile['ceiling']} tokens — "
                  f"≤ ${profile['ceiling'] / 1e6 * price_out:.2f} on {model} at list price; --probe makes the first "
                  f"{PROBE_CALLS} real calls and prints their size.")
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
        # GeniOS-011 S07.U1 · the API's own `stop_reason`, kept per thread for `--probe`: `LLMClient.call` reads
        # it only to say `truncated`, and whether a call ended or was cut is the first thing a probe reads.
        self._stops = threading.local()
        self._client._client = _SeesStopReasons(self._client._client, self._stops)
        self.model = model

    @staticmethod
    def content_hash(material: str) -> str:
        from genios_engine.context.llm.client import LLMClient
        return LLMClient.content_hash(material)

    def stop_reason(self) -> str | None:
        """The last response's `stop_reason` on this thread — None before a call, or when the call failed."""
        return getattr(self._stops, "last", None)

    def call(self, prompt: str, *, max_tokens: int = 4096, **kw):
        self._stops.last = None
        return self._call(self._client, prompt, max_tokens=max_tokens, **kw)


class _SeesStopReasons:
    """The raw Anthropic client, seen through (GeniOS-011 S07.U1): each response's `stop_reason` kept for the
    thread that asked — through `with_options` too, the second client a site with its own timeout (R-7's, R-9's)
    is asked on. `messages.create` and `with_options` are the only two things `LLMClient.call` uses."""

    def __init__(self, raw, stops) -> None:
        self._raw, self._stops = raw, stops
        self.messages = self                    # `client.messages.create(…)` lands on `create` below

    def with_options(self, **opts):
        return _SeesStopReasons(self._raw.with_options(**opts), self._stops)

    def create(self, **kw):
        response = self._raw.messages.create(**kw)
        self._stops.last = str(getattr(response, "stop_reason", "") or "") or None
        return response


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
    from tests.replays.engine_runner import l2_path
    from tests.replays.engine_runner import pin_scratch_database, run_case
    from tests.replays.harness import CassetteRecorder
    from tests.replays.ideal_reader import IdealReader
    from tests.replays.marking import FAIL, NOT_EXERCISED, PASS, cards_about, judge

    pin_scratch_database()
    key = os.environ[LIVE_KEY_ENV]
    rows, tokens_in, tokens_out, calls, truncated = [], 0, 0, 0, 0
    # GeniOS-011 S07.U1 · the path the cases take, read where `run_case` reads it — named on the card and in it.
    on_l2_path = l2_path()
    name = scorecard_name(date.today().isoformat(), model, site, thinking, l2=on_l2_path)
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
            # GeniOS-011 S07.U1 · down the L2 path there is no cassette to replay (that path is never recorded,
            # `l2_score`), and today's missed at R-9's first prompt — after the live case was paid for. The authored
            # answers there are the ideal reader's own on the SAME path, so a verdict that moved is the model's,
            # never the path's.
            recorded = judge(case, run_case(case, IdealReader(case)) if on_l2_path else cassettes.replay(case))
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
    card = {"model": model, "site": site, "date": date.today().isoformat(), "l2_path": on_l2_path, "cases": rows,
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


def probe(ids: list[str], model: str, site: str | None = None, *, max_usd: float) -> int:
    """GeniOS-011 S07.U1 · `--probe`: the live pass's first `PROBE_CALLS` calls (of `site`, every other site answered
    by the ideal reader as in `live`), each one's `stop_reason` and `output_tokens` printed as it returns, then the
    run stops — before any paid pass, so a ceiling that cuts every answer (`stop_reason=max_tokens`, the Sonnet 5
    pass of 12 Oct) is read on two calls rather than paid for on two hundred. Under the same `--max-usd` cap; no
    scorecard, no cassette. The tenant is not kept: `run_case` removes it on every exit, the probe's stop included.
    Exit 1 when no call was made — the site was never asked on these cases, which a probe says rather than
    passing."""
    from tests.replays.engine_runner import pin_scratch_database
    from tests.replays.engine_runner import run_case
    from tests.replays.ideal_reader import IdealReader

    pin_scratch_database()
    cap = SpendCap(max_usd, model)
    asked = ProbeModel(LiveModel(os.environ[LIVE_KEY_ENV], model))
    for case in _cases(ids):
        capped = CappedModel(asked, cap)
        try:
            run_case(case, SiteModel(site, capped, IdealReader(case)) if site is not None else capped)
        except ProbeComplete:
            break
        if cap.reached:
            print(f"STOPPED at {case.case_id}: --max-usd {max_usd:g} reached (${cap.spent_usd:.4f} spent)")
            break
        if asked.full:
            break
    if not asked.made:
        print(f"\nthe probe made no call: {site or 'no site'} was never asked on these cases "
              f"(${cap.spent_usd:.4f} spent).", file=sys.stderr)
        return 1
    cut = sum(row["stop_reason"] == "max_tokens" for row in asked.made)
    print(f"\nprobe: {len(asked.made)} of {asked.limit} calls on {model} · {cut} cut at the ceiling · "
          f"${cap.spent_usd:.4f} spent · no scorecard written. A stop_reason of max_tokens means the ceiling cut "
          "the answer: read these before any paid pass.")
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
    ap.add_argument("--l2-path", action="store_true",
                    help="run the cases down the L2 path (GENIOS_GOLDEN_L2=1) for this run; R-9 needs it")
    ap.add_argument("--probe", action="store_true",
                    help=f"a live pass's first {PROBE_CALLS} calls only, each one's stop_reason and output_tokens "
                         "printed, no scorecard — read before any paid pass; needs what --live needs")
    ap.add_argument("cases", nargs="*", help="case ids (default: every case)")
    args = ap.parse_args(argv)
    run_settings = {"thinking": args.thinking, "ceiling": args.ceiling, "per_call_usd": args.per_call_usd}
    if any(v is not None for v in run_settings.values()) and args.site not in SITE_TIERS:
        ap.error("--thinking, --ceiling and --per-call-usd set one site's R-site for the run: name a "
                 f"--site with a tier of its own ({', '.join(SITE_TIERS)})")
    if args.ceiling is not None and args.ceiling <= 0:
        ap.error("--ceiling is a positive number of tokens")

    # GeniOS-011 S07.U1 · the probe is a live pass's first calls inside the chain, and the L2 path a run's path.
    if args.probe and (args.dry_run or args.record or args.site == BRIEF_SITE):
        ap.error("--probe makes a live pass's first calls inside the chain: not with --dry-run or --record, nor "
                 f"--site {BRIEF_SITE}, whose writer runs outside the chain")
    if args.l2_path and args.record:
        ap.error("--l2-path is never recorded over today's cassettes: CI replays them down today's path, and the "
                 "L2 path is scored beside it (tests/replays/l2_score) — drop --record")
    if args.l2_path and args.site == BRIEF_SITE:
        ap.error(f"--site {BRIEF_SITE} composes its day from today's cassettes: --l2-path does not apply")
    if (args.live or args.probe) and args.site == L2_SITE and not args.l2_path:
        ap.error(f"--site {L2_SITE}: today's path never asks R-9 (l2_reasoning is switched on only down the L2 "
                 "path), so the pass would spend nothing and measure nothing — add --l2-path")

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
    if args.live or args.probe:
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
        with l2_path_for_the_run(args.l2_path), \
                (site_settings(r_site, **run_settings) if r_site else contextlib.nullcontext()):
            if args.probe:
                return probe(args.cases, model, args.site, max_usd=args.max_usd)
            return live(args.cases, model, args.record, args.site, max_usd=args.max_usd, **run_settings)
    if args.record:
        from tests.replays.engine_runner import pin_scratch_database
        pin_scratch_database()
        record(args.cases)
        return 0
    ap.error("say what to do: --dry-run, --record, --probe or --live")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
