# 14 · For Harsh: what is on GitHub, how we work from now, and your production list, step by step

**Written for:** Harsh (CTO; owns production, deploys, switches, migrations).
**Date:** 23 Oct 2026. **Brain head:** `origin/speedrun008` (this file's commit). **Production:** `harsh/mvp` `0cc8d83c`.

---

## §0 · How we work from now (Rohit, 23 Oct)

1. **All code is written on the `speedrun008` branch** of `themoronss/genios-brain`. Each unit is one commit with its own tests and a mutation proof, titled `G012 <unit>: <what is now true>` (or `G011 <unit>` for GeniOS-011 units).
2. **Claude pushes `speedrun008`. Claude never pushes `harsh/mvp`, never deploys, never runs anything against production.** Production code is not touched by us.
3. **You pull `speedrun008`, review, and merge into `harsh/mvp` when CI is green on that SHA.** `speedrun008` is a strict descendant of `harsh/mvp` (`0cc8d83c`), so the merge is a fast-forward with no conflict, unless you commit to `harsh/mvp` in between (then merge `harsh/mvp` into `speedrun008` first, or tell us and we do it).
4. **Production actions are yours** (§3): plan state, switches, env, resync. Rohit says yes to anything that reads production data or spends model money.
5. **Every result goes in [13-LOG](13-LOG.md)**, one line, with the command or reading that showed it. Never commit production data (readings JSON, mail).

```bash
git fetch origin
git checkout harsh/mvp
git log --oneline harsh/mvp..origin/speedrun008      # what is new
# check CI on that SHA: https://github.com/themoronss/genios-brain/actions?query=branch%3Aspeedrun008
git merge --ff-only origin/speedrun008
git push origin harsh/mvp                              # the deploy host builds it
curl -s https://<brain host>/health | jq '.build_sha, .schema_head'
```

---

## §1 · Everything planned or drafted so far, and where it is on GitHub

### Brain: `themoronss/genios-brain` (public)

| What | Where | State | What you do |
|---|---|---|---|
| **GeniOS-011** audit (255 items), plan (43 steps), decisions, your production SQL | `speedrun008:speedrun008/GeniOS-011/` | docs | read [04-FOR-HARSH](../GeniOS-011/04-FOR-HARSH.md) §1 for every unit already merged |
| **GeniOS-011 units, built and merged** (19, each with tests and a mutation proof): S01.U1, S03.U1, S04.U1, S04.U3, S05.U1 (migration 0251), S06.U1, S06.U2, S07.U1, S14.U1, S18.U1–U3, S26.U2–U3, S27.U1, S36.U1–U2, S37.U2, S40.U2, S44.U1 | `speedrun008` | merged, **not deployed** | deploy (§3 Step 1) |
| **GeniOS-012** (this folder): the `/preview` gap traced to code, 32 loss points, 8 steps, 21 new units with agent briefs | `speedrun008:speedrun008/GeniOS-012/` | docs | read [00](00-START-HERE.md), then this file |
| **GeniOS-010 07-GENIOS-DESKTOP**: the Mac app design, every source file of the agreed dummy (commented out so nothing runs), screenshots, assets | `speedrun008:speedrun008/GeniOS-010/07-GENIOS-DESKTOP/` | docs, pushed with this file | reference for wiring the Mac app |
| **S02.U5** every door asks one gate; every skip is a row | branch `g011-S02U5` (`15a86e31`) | built, **held**: it makes Sync now refuse an expired org | merge only after Rohit's org is on a non-expiring plan (§3 Step 1.2) |
| **S16.U3** snapshot as-of, unknowns, contradictions | branch `g011-S16U3` (`bd260f0a`) | built, **held** until the replay harness pins knowledge time (U12-09) | nothing |
| **STEP-13b** claim-check repair ladder (held cards 79% → 18.5% on Haiku) | branches `yc2w27-int13b` (`42d61e8f`), `yc2w27-s13b` (`1eb37eb1`), plan `yc2w27-s13b-plan` (`7aeeee79`), **pushed today** | not merged; its migration `0250_expert_review_attempts.sql` collides with the head's 0250 | nothing; S20.U2 ports it after Rohit's go |
| **S34.U3** the card writer (`deliver/card_copy.py`, migration 0252) | uncommitted, in another session's worktree | being built | nothing yet |

### Dashboard: `themoronss/genios-brain-dashbaord` (private)

| What | Branch | State | What you do |
|---|---|---|---|
| `/preview`: the ideal-state dashboard, owner-only | `main` `ff13896` | **live** | to see it yourself, add your email to `PREVIEW_ALLOWED_EMAILS` (comma list) in the dashboard deploy env; the default allows only Rohit |
| The source of `/preview` (edit `src/02-data.js`, `./build.sh`, then `node scripts/ideal-preview-sync.mjs tools/ideal-dashboard/index.html`) | `rohit/ideal-dashboard-source` (`791fe1c4`) | pushed today; holds real mail, private repo only | do not merge to `main` unless Rohit asks; never copy into the brain repo |
| **Draft** "direct" route: the real Goals page reading goals written straight from the mail (`/api/direct`, `src/lib/direct-intel.ts`) | `rohit/direct-intel` (`c75dd100`) | pushed today; **draft, stopped by Rohit**; `tsc` green | **do not merge**; it is there for you to see |
| Cards UX, nav grouping | `rohit/cards-ux`, `rohit/nav-grouping` | merged into `main` earlier | — |
| Mac app UX rebuild | `rohit/desktop-ux` (`ed2724df`) | built (render check 16/16, cargo 254/254), **not merged** | Rohit's go (S38.U1) |

### Not on GitHub, on purpose

- `GeniOS-Ideal-Dashboard/` on Rohit's machine: the same source as `rohit/ideal-dashboard-source`.
- Production readings: never committed.

---

## §2 · What Claude builds next, in this order (you will see each as one commit on `speedrun008`)

| # | Unit | What becomes true | Touches |
|---|---|---|---|
| 1 | U12-02 | `scripts/activate_tenant.py` can switch on `expert_review`, `l2_reasoning`, `l2_cards` and `founder_office` (today it silently drops them) | `scripts/activate_tenant.py` + a test |
| 2 | U12-03 | a judged file is always decided, even with no compile flag | `reason/runner.py` + a test |
| 3 | U12-04 | evidence fetchers use the connection's real window, not 60 days | `api/routes.py` + a test |
| 4 | U12-01 | an expired org raises an alert once a day instead of going silent | `api/routes.py`, `platform/daily_health.py`, one additive migration |
| 5 | Step 4 L3 units: S14.U2 → U12-11 → S15.U1 → N4 → S15.U2 | stable ids; no destructive replay; one live situation per file; bounces visible | `context/` |
| then | the rest of [09](09-STEPS.md), unit by unit | — | — |

Each commit message says what changed, the flags, and how to roll it back (`git revert <sha>`). A migration is always additive.

---

## §3 · Your production list, in order

Do the steps in order. After each, add one line to [13-LOG](13-LOG.md).

### Step 0 · Know what is deployed (no changes)

```sql
-- 0.1 migrations applied
select filename, applied_at from schema_migrations where filename >= '0191' order by 1;
-- 0.2 Rohit's org plan state
select id, subscription_tier, plan_status, plan_expires_at, grace_until, is_internal
from orgs where id = '<ORG>';
-- 0.3 activation rows
select * from l3_activation          where org_id = '<ORG>';
select * from l1_semantic_activation where org_id = '<ORG>';
select * from l4_activation          where org_id = '<ORG>';
```
Plus: the deployed SHA and date; the values of `GENIOS_NEED_FETCHERS`, `GENIOS_L4_LLM_DECISION_MAKER` (must be unset), `GENIOS_BUILD_SHA`.

With Rohit's yes, the full read-only readings:
```bash
python scripts/g011_prod_readings.py --org <ORG> --show-sql     # prints the SQL, opens nothing
python scripts/g011_prod_readings.py --org <ORG> --out readings.json   # one read-only transaction
```
Send `readings.json` to Rohit/Claude. **Never commit it.**

### Step 1 · Make the chain run, switch the expert on

1.1 **Plan.** If 0.2 shows Rohit's org expired: set it on a non-expiring internal plan with your plan tool or the admin route (pricing rules as restored in `4f791884`): `plan_status='active'`, `plan_expires_at=null`, `grace_until=null`, `is_internal=true`. Same for each design partner.

1.2 **Deploy.** Fast-forward `harsh/mvp` to `origin/speedrun008` (§0), set `GENIOS_BUILD_SHA=<sha>`. Migration 0251 (`daily_health`) applies at boot (`main.py` `apply_migrations`). ⚠ A read-only database silently skips migrations; check `schema_head` on `/health`. Then tell us, and we merge `g011-S02U5`.

1.3 **Switches** (after Rohit's yes). Until U12-02 ships, use the admin routes with a staff token. They are idempotent and audited. Roll back with `DELETE /admin/l4-activation/<ORG>?feature=<name>` (or `/admin/l3-activation/<ORG>?domain=founder_office`):
```bash
curl -X POST https://<brain host>/admin/l4-activation/<ORG> -H "Authorization: Bearer <staff>" \
     -H "Content-Type: application/json" -d '{"feature":"expert_review","notes":"G012 S02.U3"}'
curl -X POST https://<brain host>/admin/l4-activation/<ORG> -H "Authorization: Bearer <staff>" \
     -H "Content-Type: application/json" -d '{"feature":"l2_reasoning","notes":"G012 S02.U3"}'
curl -X POST https://<brain host>/admin/l3-activation/<ORG> -H "Authorization: Bearer <staff>" \
     -H "Content-Type: application/json" -d '{"domain":"founder_office","notes":"G012 S02.U3"}'
```
Each response's `missing_preconditions` must be empty. **Leave `l2_cards` off** until the real-model pass (Step 5). **Keep `GENIOS_L4_LLM_DECISION_MAKER` unset.** If 0.3 showed no `l3_activation` and no `l1_semantic_activation` row, re-run onboarding activation for the org first (see [03 Part C](03-RUN-GATE-AND-SWITCHES.md)).

1.4 **Brief lines** Rohit accepts: his senders (the intro platform, each portal, each fund and programme) and his self identity. They feed the gate's W-07 bypass.

1.5 **Branch protection** on `harsh/mvp` (with Rohit, repo admin): require the CI checks; let the deploy host build only green SHAs.

**Check after 2 days:** no `l1_skipped_plan_expired` for the org in the sweep log; `select * from daily_health where org_id='<ORG>' order by day desc limit 2;` returns 2 rows; `expert_reviews` rows exist for the org.

### Step 2 · 365 days of mail (after Rohit's window decision and his spend yes)

Follow the runbook in [04 Part A](04-L1-SIGNALS.md) (the docstring of `scripts/resync_deleted_mail.py`):
```bash
python scripts/resync_deleted_mail.py --org <ORG> --days 365              # dry run → Rohit
# cost estimate from the dry run's count → Rohit says yes
curl -X PATCH https://<brain host>/connections/<gmail_id>/backfill-window ...   # 365 (and the Calendar connection)
GENIOS_ALLOW_PROD_WRITE=1 python scripts/resync_deleted_mail.py --org <ORG> --apply --days 365
curl -X POST https://<brain host>/connections/<gmail_id>/backfill        # NEVER /integrations/gmail/sync
# wait for "backfill drain done"; TRUNCATED → run again with ?limit=100
GENIOS_ALLOW_PROD_WRITE=1 python scripts/resync_deleted_mail.py --org <ORG> --finish
python scripts/pipeline_health.py
```
Then the archived intros and portal mail (dry run first, Rohit reads the list):
```bash
python scripts/promote_archived.py --org <ORG> --rule N-02 --sender-domain boardy.ai
GENIOS_ALLOW_PROD_WRITE=1 python scripts/promote_archived.py --org <ORG> --rule N-02 --sender-domain boardy.ai --apply --crypto-key "$GENIOS_CRYPTO_KEY"
```
And `GENIOS_NEED_FETCHERS=on` in the env (after U12-04 is deployed, so the fetchers use the 365-day window).

⚠ **Before Step 2, the database size:** production was 446 MB on 19 Oct and `daily_health` alerts at 450 MB (`GENIOS_DB_SIZE_CEILING_MB`). A 365-day resync adds bodies. Plan the tier first.

### Steps 3–8

Code units from Claude; your part in each is the deploy and the gate check in [09](09-STEPS.md). Rohit's spend yes comes before each real-model pass.

---

## §4 · What never to do

- Do not merge `rohit/direct-intel` or `rohit/ideal-dashboard-source` into the dashboard's `main`.
- Do not add an `org_channels` email row: email has no transport yet, and every card would burn its one email delivery.
- Do not set `GENIOS_L4_LLM_DECISION_MAKER`.
- Do not run `situations/backfill?rebuild=true` or `scripts/rebuild_graph.py` on Rohit's org until S14.U2 is deployed: a rebuild deletes situations and human decisions today.
- Do not commit production readings or mail anywhere. The brain repo is public.
- Do not merge `g011-S02U5` before Step 1.1 is done.

---

## §5 · If something goes wrong

| Symptom | First look | Roll back |
|---|---|---|
| no cards the day after a deploy | `daily_health` (cards by lane, refusals), the sweep log's `why_no_card` line, `GET /v1/workstreams/{file_id}` `why_no_card` | `git revert` the last unit on `speedrun008`, or fast-forward `harsh/mvp` back to the previous SHA |
| cost jumps | `llm_costs` per day and site | turn off the switch you flipped last (`DELETE /admin/l4-activation/<ORG>?feature=<name>`) |
| a migration did not apply | `/health` `schema_head` | re-run the boot with a writable database |
| the DB passes 450 MB | `daily_health.database_bytes` | raise `GENIOS_DB_SIZE_CEILING_MB` only after planning the tier |

Tell Claude (or write in 13-LOG) the symptom, the SHA and the reading.
