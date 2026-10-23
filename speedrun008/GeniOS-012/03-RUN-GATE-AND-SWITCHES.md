# 03 · Before L1: does the chain run, and is the expert switched on? (D1–D3, D28)

**Written for:** Harsh (production) and coding agents (the code units).
**Fixes:** D1, D2, D3 and D28 of [02](02-THE-PATH-OF-ONE-MAIL.md).
**Why first:** nothing in files 04–08 matters if the scheduled sweep skips the org, or if the expert never runs. These are mostly production actions (no new code), plus two small code units.

Unit ids: existing GeniOS-011 units keep their ids (`S02.U1`…). New units found by this folder's crosscheck are `U12-nn`. Each has an agent brief in [10-UNIT-BRIEFS](10-UNIT-BRIEFS.md).

Status key: ✅ built and merged on `origin/speedrun008` · ⏸ built and held · 🔨 being built · ⬜ open · 🔒 waiting on a named person.

---

## Part A · The plan gate (D1, D2)

### What happened, and how

1. On 4 Oct, commit `7075014c` made billing real: an org whose trial lapsed should stop costing model money.
2. It added `_plan_expired(org_id)` (`api/routes.py:1042-1077`), which asks `platform/billing.py:338` `expiry_state(...)`. Both scheduled ticks call `run_sync_sweep` (`routes.py:1117`). At `:1211-1214` an expired org is skipped for L1, and at `:1289-1290` it is removed from the L2/L3/L5 pass. The warm lane refuses it at the door (`platform/warm_lane.py:175-177`).
3. The same commit measured Rohit's own org: its grace closed on **21 Sep**. Nobody extended it. So from 4 Oct the schedule has made no cards for the founder's own org.
4. Sync now kept working because its path (`_onboarding_sync_bg`, `routes.py:3988`) checks only the daily LLM cap. That is why cards still appear "sometimes".
5. GeniOS-011 built **S02.U5** (branch `g011-S02U5`, `15a86e31`): one `_sweep_gate(org_id, door=…)` that every door asks (paused → plan_expired → over_budget → sync_quota), plus an `l1_sync_runs` row for every refusal. It is **held on purpose**: merged before Rohit's org is fixed, it would close Sync now too, the last path still making his cards.

### Units

| Unit | Owner | What | Exactly how | Done when | Rollback | Status |
|---|---|---|---|---|---|---|
| **S02.U1** | Harsh | Put Rohit's org, and every design partner, on a non-expiring internal plan | Read first: `select id, subscription_tier, plan_status, plan_expires_at, grace_until, is_internal from orgs where id = '<ORG>';`<br>Then, with the plan tool or the admin route (pricing rules stay as restored in `4f791884`): `plan_status = 'active'`, `plan_expires_at = null`, `grace_until = null`, `is_internal = true`. | the readings' `org_plan_state` (S01.U1) shows `active`; the next heavy tick's log has no `l1_skipped_plan_expired` for the org; tomorrow's `daily_health` row (S05.U1) exists for the org | restore the three columns from the read above | 🔒 Harsh |
| **S02.U5** | Claude (built) | Every door asks one gate, and every skip is a row | Merge branch `g011-S02U5` into `speedrun008` **only after S02.U1 is confirmed** | `l1_sync_runs` shows `skipped: plan_expired` rows for a test org you expire on purpose; Rohit's org shows none | `git revert` the merge | ⏸ held until S02.U1 |
| **U12-01** | Claude | An expired org is never silent | When `_plan_expired` skips an org, write one `ops_alert` per org per day ("org X skipped: plan expired since D"), and put `plan_state` on `GET /health` for staff and on the `daily_health` row. Files: `api/routes.py` (the skip at `:1211-1214`), `platform/daily_health.py`, `migrations/02xx_daily_health_plan_state.sql` (one column) | A test org set to expired produces one alert per day and a `plan_state='expired'` row; an active org produces none. Mutation: remove the alert call → the test goes red | revert the commit; the column is additive | ⬜ |

**For customers (not just Rohit):** a lapsed trial must stop *spending*, but it must never silently stop *without anyone knowing*. U12-01 is the minimum. Whether a lapsed customer still gets read-only cards is Rohit's product call (D-12-1 in [00](00-START-HERE.md)).

---

## Part B · The switches (D3)

### What happened, and how

1. The expert review (R-7), the L2 judgment (R-9) and L2 cards were built in shadow (GeniOS-008) and are **off by default**, on purpose: `platform/l4_activation.py` `NOT_DEFAULT_ON` (`:167-203`) excludes `expert_review`, `l2_reasoning`, `l2_cards`, `morning_brief`, `calibration_apply`, `cards_from_situations` and `situation_reasoner`.
2. The preconditions are coded: `PRECONDITIONS[l2_cards] = (l2_reasoning, expert_review)` and `CROSS_LAYER_PRECONDITIONS[l2_cards] = ("l3_domain",)`.
3. Onboarding (`platform/intelligence_onboarding.make_tenant_live`, `:222`) switches on every L3 domain whose `domain.yaml` says `activation.default_on: true`. Only **Admin** does. Founder Office says `default_on: false` (`Domain Expertise/Founder Office Expertise/domain.yaml:44-45`).
4. GeniOS-011 07 Phase A told Harsh to switch these on with `scripts/activate_tenant.py`. **That does not work.** `_plan_for` (`scripts/activate_tenant.py:155-179`) appends only the L4 features named in its `PLAN` (`:51-61`: roster_v2, ranking_v2, bundle, critique, brief). So `--features expert_review,l2_reasoning,l2_cards` passes `require_feature` and is then **silently dropped**. This is new in this crosscheck.
5. The model decider `GENIOS_L4_LLM_DECISION_MAKER` (`platform/config.py:110`, default False) is a test mode that replaces the deterministic Decision Maker. It ran in production on 1 Oct and DEFERred every decision. It must stay **unset**.

### Units

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **U12-02** | Claude | `activate_tenant.py` can switch on what it says it can | In `_plan_for`, accept every feature in `L4_FEATURES`, not only those in `PLAN`; respect `PRECONDITIONS` order (expert_review → l2_reasoning → l2_cards); accept `--domains founder_office`; refuse (exit 2) a feature name it will not apply, instead of dropping it. Files: `scripts/activate_tenant.py`, `tests/scripts/test_activate_tenant_plan.py` (new) | `--features expert_review,l2_reasoning --dry-run` prints both steps; an unknown feature exits 2. Mutation: restore the `PLAN` filter → red | ⬜ |
| **S02.U3** | Rohit says yes, Harsh does | Switch the expert on for Rohit's org | Until U12-02 ships, use the admin routes (staff token; idempotent, audited; `DELETE` on the same path rolls back):<br>`POST /admin/l4-activation/<ORG>` body `{"feature": "expert_review", "notes": "G012 S02.U3"}`, then the same with `"l2_reasoning"` (`api/admin_routes.py:1409`, model `L4PilotActivation` `:1331`). The response lists `missing_preconditions`; it must be empty.<br>`POST /admin/l3-activation/<ORG>` body `{"domain": "founder_office", "notes": "G012 S02.U3"}` (`:1229`, model `L3PilotActivation` `:1168`). **Leave `l2_cards` off** until the real-model pass (S07.U2) and the per-type gate (S25). Log one dated line per flip in [13-LOG](13-LOG.md), with its rollback. Read back with the SQL in GeniOS-011 [04 §A2](../GeniOS-011/04-FOR-HARSH.md). | the readings show `expert_review`, `l2_reasoning` and `founder_office` active for the org; `GENIOS_L4_LLM_DECISION_MAKER` unset | 🔒 Rohit's yes, then Harsh |
| **S02.U4** | Rohit accepts, Harsh/Claude apply | Brief lines that protect founder senders and name the work | Company-brief lines (accepted) naming: Boardy as an intro source; the programme portals and the government registration portal; every accelerator, programme and investor in conversation (the list is on `/preview` → Company, owner-only); Rohit's self identity (his addresses and company domain as "us"). These feed the gate's W-07 bypass (D8) and `file_quiet_days` (90 days for investor/program in-motion lines, `correlation.find_or_open`). | `GET /v1/company-brief` lists them as accepted; a fresh portal mail passes the gate with `W-07` in its trace | 🔒 Rohit |

---

## Part C · The compile gate (D28), new in this crosscheck

### What happened, and how

`reason/runner.run_all` calls `shadow_compile` at `:2029` **only if** one of three things is true:
- `live_compile` = `get_settings().use_domain_compiler` (`runner.py:1971`; a global boolean, default False, set in no environment);
- `l3_domains` = `activated_domains(engine, org_id)` (`runner.py:1993`) is non-empty;
- `l1_seam_enabled(engine, org_id)` (`platform/config.py:310`), i.e. the tenant has an `l1_semantic_activation` row.

`shadow_compile` is where `_decide_covered_files` turns a judged ("covered") file into a card. With all three false, the expert can judge a file correctly and **no card is ever made**, with no log line.

For an org onboarded through `make_tenant_live` this is normally safe: onboarding activates Admin (so `l3_domains` is non-empty) and the L1 semantic row. It bites a tenant whose L3 activation was deleted or never written (an org created before onboarding existed, or reset with `/reset`). It is a hardening unit, not the cause of Rohit's missing cards, unless the readings show his org has neither row.

| Unit | Owner | What | Exactly how | Done when | Status |
|---|---|---|---|---|---|
| **H-check** | Harsh | Read the two rows for Rohit's org | `select * from l3_activation where org_id='<ORG>';` and `select * from l1_semantic_activation where org_id='<ORG>';` (both are in `scripts/g011_prod_readings.py`). Write the result in [13-LOG](13-LOG.md). If both are empty, re-run onboarding activation for the org. | the result is logged | 🔒 Harsh |
| **U12-03** | Claude | A judged file is always decided | Decide covered files whenever the expert or L2 produced at least one covered file, whatever the compile flags say: call `_decide_covered_files` outside the guard at `run_all:2029`, or make the guard also true when `covered` is non-empty. If a covered file still gets no decision, count `covered_not_decided` in `WHY_NO_CARD` (`runner.py:1842-1891`). Files: `reason/runner.py`, `reason/domain_shadow.py`, a test in `tests/reason/` | with no activated domain, no L1 row and one covered file, a card or a counted no-card reason results. Mutation: put the guard back → red | ⬜ |

---

## Part D · Seeing what is deployed and whether it runs

| Unit | Owner | What | Status |
|---|---|---|---|
| **S03.U1** | Claude (built) + Harsh | `GET /health` returns `build_sha` and `schema_head`. Harsh sets `GENIOS_BUILD_SHA=<sha>` at deploy. | ✅ code · 🔒 env |
| **S05.U1** | Claude (built) | Migration `0251_daily_health`: one row per org per day (cards by builder and lane, refusals, expert/L2/admission counts, the funnel, LLM calls, R-site outcomes, DB size), with `ops_alert` when cards fall below half the 14-day median or the DB passes 450 MB. | ✅ |
| **S01.U1** | Claude (built) | `scripts/g011_prod_readings.py --org <ORG>`: 86 read-only readings, refuses anything but SELECT/WITH/SHOW. Run with Rohit's permission; **never commit the output**. | ✅ · 🔒 run |
| **S03.U2** | Rohit + Harsh | Branch protection on `harsh/mvp`: require CI; the deploy host builds green SHAs only. | 🔒 |

---

## After this file: what should be true

1. The heavy tick runs for Rohit's org every time (no `l1_skipped_plan_expired`).
2. `expert_review`, `l2_reasoning` and `founder_office` are active for the org; `l2_cards` is still off.
3. A covered file is always decided (U12-03), and when no card results, `why_no_card` says why.
4. `GET /health` names the SHA; `daily_health` has a row for yesterday.

**Cards expected to appear after Parts A–D alone** (old lanes, current window): `f4` (waiting on a reviewer, inside 60 days). Most other cards still need Steps 2–7, because their mail is outside the window or archived. Record what actually appears in [13-LOG](13-LOG.md); never edit this line to match.
