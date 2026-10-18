# L2 Reasoning — for Harsh

**Written for:** Harsh, who deploys and runs production. **Started:** 18 Oct 2026. Each pushed group of L2 work
adds a section at the bottom.

## 1 · What is happening to L2, in one paragraph

Today L2 (`reason/` + `packs/`) mostly decides by formula and rule:
- 23 deterministic reasoners score risk, priority and confidence;
- the pack rules fire;
- an optional LLM decider picks between the candidates.

The new architecture and Rohit's L2 spec make the **LLM the reasoning engine**:
- one bounded judgment pass per situation reads the signals, the company context, the history and the domain expertise;
- it returns a structured `ReasoningResult`: facts, inferences, hypotheses, unknowns, framing, consequences, options, next move and confidence per dimension;
- deterministic code only supports it: retrieval, IDs, permissions, exact numbers.

The STEP-12 expert pass is the starting point; it already works this way for *files*. The plan is
[`02-PLAN.md`](02-PLAN.md).

## 2 · What changes for you, and when

| When | What you will do | Why |
|---|---|---|
| **Now** | deploy `speedrun008` (L1 H1); then switch `l2_reasoning` on for Rohit's org and read the first rows (section G-1) | The L2 pass is built and runs in shadow |
| **Before any L2 work reaches production** | the Layer 1 deploy (`../layer-1-enterprise-signals/04-FOR-HARSH.md` §4 H1) | Production still runs `harsh/mvp`, 815+ commits behind |
| **Each L2 group pushed** | follow its section below: migration (if any), flag, what to watch, rollback | The new path runs **in shadow** first: it writes its own tables and changes no card |
| **The first switch** (awaiting reply / outreach) | turn one flag on for Rohit's org only; watch for one day; the steps will be written here | Only switched after the golden set shows the new path is at least as good |

## 3 · Things to have ready (read only, nothing to change yet)

1. **The value of `GENIOS_L4_LLM_DECISION_MAKER` in production.** The LLM decider will be retired. We need to know if it is on today.
2. **Whether `expert_review` is activated for Rohit's org** after the deploy (`08` §0.5). The new judgment pass grows out of it.
3. **The model key and spend limits.** The judgment pass runs Sonnet-class, about $2 a day for Rohit's org (as STEP-12). Any change will be written here before it ships.
4. **Database load.**
   - L2 currently opens two transactions per situation (`reason/audit.py:283` + `domain_shadow._persist_live`).
   - The new path batches them, one per sweep (plan unit L2-G1).
   - Expect the transaction count in the `DATABASE_LOAD_ANALYSIS` to fall once the switch happens, not before.

## 4 · How each switch will be written for you

Every switch section below will have these parts:
- **What changed:** files and behaviour, in plain words.
- **Migration:** number, what it adds, whether it can be re-run.
- **Flag:** name, which org, how to turn it on and off.
- **Run:** the exact commands.
- **You should see:** tables, counts, log lines.
- **It went wrong if:** the symptoms, and what to send back.
- **Roll back:** one line.

---

## Sections per pushed group

### G-1 · The L2 judgment pass, in SHADOW (pushed 18 Oct 2026, branch `speedrun008`)

**In one line.** A new pass reads each new Layer 1 bundle, works out what it is about, reasons over it with one
Sonnet-class call, checks every claim, and keeps a `ReasoningResult` with its receipt in a new table. It changes
**no card, no signal, no situation**. It is **off** until you switch it on for one org.

#### What changed

| Area | File(s) | What it does |
|---|---|---|
| L1 E1 | `capture/esqe/bundle_store.py`, `capture/esqe/finalize.py`, `platform/wiring.py`, `api/routes.py`, `api/upload_routes.py` | The bundles L1 already built every sweep are now **stored** in `signal_bundles` (table 0186 existed and was empty). Both capture doors (sync and upload) store them. |
| L1 E8 | `reason/l2/inputs.py` | L2 reads each bundle's signals back with everything L1 computed — whose turn, thread, direction, due date, coverage, the mail's quoted words, the sender — fields that were written and read by nobody. |
| L1 E2 | `capture/acquire/need_fetchers.py`, `capture/acquire/need_executor.py`, `api/routes.py` | Real fetchers for evidence needs: a Gmail **thread by id**, and a Gmail **date window**. The fetched mail goes through the normal capture door. **Off unless `GENIOS_NEED_FETCHERS=on`.** |
| L2 contracts | `contracts/reasoning_result.py` | `ReasoningResult`, `L2Request` (closed trigger list), six-dimension confidence (levels, never a number), `ReasoningReceipt`, and `lane_for` — the lane is decided by code, never by the model. |
| L2 runtime | `reason/l2/` — `snapshot.py`, `history.py`, `tools.py`, `plan.py`, `dossier.py`, `prompt.py`, `judge.py`, `evidence.py`, `store.py`, `replay.py`, `sweep.py` | The run: bounded context read (`read_bounded`, its first caller), comparable past work, the tools' arithmetic, the depth plan, the six-block dossier, one call through the R-9 gate, the STEP-13 claim check, evidence needs filed, one write per sweep, replay with no model. |
| Model site | `reason/bundle/sites.py`, `reason/bundle/budget.py` | New site **R-9**: Sonnet-class (T2), thinking off, 8,000 output tokens, 160 s timeout, **its own $2/day and $0.15/call** — it never spends the expert's (R-7) money. |
| Switch | `platform/l4_activation.py`, `platform/intelligence_onboarding.py` | New L4 feature **`l2_reasoning`**. Never default-on. |
| Sweep hook | `reason/runner.py` `run_all` | Runs right after the expert pass, wrapped in try/except. Its receipt is in `run_all(...)["l2"]`. |
| Table | `migrations/0243_reasoning_results.sql` | One row per (org, subject, fingerprint). Added to the reset/erasure list. |
| Report | `scripts/l2_shadow_report.py` | Read-only: what L2 concluded per subject, beside today's open cards and expert review. |

#### Migration

`0243_reasoning_results.sql` — creates `reasoning_results` and two indexes, adds the org cascade FK. Idempotent
(`create … if not exists`, `drop constraint if exists`). The app applies pending migrations at boot (`main.py`
lifespan), so the deploy applies it. Nothing else in the schema changes.

#### Switch it on (one org, Rohit's first)

```bash
# ON  (shadow only — nothing the founder sees changes)
python -c "
from genios_engine.platform.db import get_engine
from genios_engine.platform.l4_activation import activate, FEATURE_L2_REASONING
activate(get_engine('$DATABASE_URL'), '<ORG_ID>', feature=FEATURE_L2_REASONING, by='harsh', notes='GeniOS-008 L2 shadow')"

# OFF (the whole rollback)
python -c "
from genios_engine.platform.db import get_engine
from genios_engine.platform.l4_activation import deactivate, FEATURE_L2_REASONING
deactivate(get_engine('$DATABASE_URL'), '<ORG_ID>', feature=FEATURE_L2_REASONING, by='harsh')"
```

It needs the Anthropic key the expert pass already uses (no new secret).

**Before leaving it on:** let one sweep run, then read the first one or two rows (below). Rohit's rule: test one or
two calls before a paid pass. If a row is `truncated`, tell me — the 8,000-token ceiling is modelled, not measured.

#### You should see

| Where | What |
|---|---|
| Logs | `the L2 pass org=<org> {...}` once per sweep that reasoned something: `ended`, `lanes`, `depths`, `cost_micro_usd`, `carried`, `needs_filed` |
| `reasoning_results` | one row per subject that moved; `status` = `result` most of the time; `lane` one of decision / investigation / conflict / monitor / suppress |
| `l4_r_site_calls` | rows with `site = 'R-9'` (the gate's ledger) |
| `post_pass_watermarks` | a row with `pass_id = 'l2_reasoning'`, moving forward each sweep |
| `evidence_needs` | rows whose `need_id` starts `l2need:` — L2's own questions (they stay `open` until fetchers are armed) |
| Spend | at most $2.00/day for the org on R-9; at most 10 subjects per sweep; the rest are carried, never dropped |

```sql
-- what it concluded, newest first
select subject_ref, status, lane, depth, reason, cost_micro_usd, reasoned_at
  from reasoning_results where org_id = '<ORG_ID>' order by reasoned_at desc limit 20;
-- today's spend on R-9
select sum(cost_micro_usd)/1e6 as usd from reasoning_results
 where org_id = '<ORG_ID>' and reasoned_at >= date_trunc('day', now());
-- L2's questions to L1
select need_id, question, subject_ref, state from evidence_needs
 where org_id = '<ORG_ID>' and need_id like 'l2need:%' order by created_at desc;
```

Or the readable version: `python scripts/l2_shadow_report.py --org <ORG_ID> --database-url <url>` (production
also needs `GENIOS_ALLOW_PROD_WRITE=1` because of the shared resolver; the script only reads).

#### It went wrong if

| Symptom | Likely cause | Send me |
|---|---|---|
| No `the L2 pass` log line, no rows | feature not on, or no new bundles (E1 stores them from the deploy on — old mail has none) | `select * from l4_activation where org_id=…` and `select count(*) from signal_bundles where org_id=…` |
| Rows with `status = 'failed'` | the call failed, or the answer stayed misshapen after one repair | the `reason` column of 2–3 rows |
| Many `refused` | the claim check refused the answer (it cited things the dossier never printed) | `reason` of 2–3 rows |
| `truncated` | the 8,000-token ceiling cut the answer | the row's `output_tokens` |
| `over_budget` early in the day | the $2/day ceiling bit | the day's spend query above |
| `the L2 judgment pass failed org=…` in logs | a bug in the pass — the rest of the sweep still ran | the stack trace |

#### The evidence fetchers (L1 E2) — separate switch, later

`GENIOS_NEED_FETCHERS=on` (environment) arms them for the deployment. **Leave it off for now.** Before turning it on,
run one fetch by hand for Rohit's org and check the fetched thread lands as normal mail. Why careful: a need that is
closed stays closed forever (`on conflict do nothing`), so a broken fetcher would destroy questions. With it off the
executor refuses and closes nothing, exactly as today.

#### Roll back

Deactivate `l2_reasoning` (above). The table can stay; nothing reads it. To remove the fetchers, unset
`GENIOS_NEED_FETCHERS`.
