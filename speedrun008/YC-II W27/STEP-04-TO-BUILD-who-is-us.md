# STEP-04 · TO BUILD · who is us — one answer, used everywhere

**Owner:** Claude. **Depends on:** `STEP-00`. **Decision:** `06` D6 — ✅ answered 2026-10-05:
`mrrohitswerashi@gmail.com`, the source of Gmail and Calendar. **Must land before `STEP-05`**, because putting every mail
into memory with a broken notion of *us* multiplies the errors. **Moves:** cards with you as the
subject **≥ 3 → 0**; threads anchored on you **→ 0**.

---

⚠️ **Re-checked against the code on 2026-10-06, claim by claim, and measured on the golden set (§8).**
The plan below is right in direction and wrong in size: "us" is decided in **18** places, not four;
two of them are live defects the draft did not name — a Gmail founder makes **every gmail.com sender
"us"** in the support lane, and a thread is named after **whoever sent its business claim**, the
founder included, and can never be renamed. The golden set does not reproduce the production defect
at all (its founder has one address). **What will be built is §8.4** — tree block `yc2_w27_s04`,
proposed, waiting for Rohit's go.

---

## 1 · What is true now

| | Evidence |
|---|---|
| `ceo@thegenios.com` is a **service** node; `thegenios.com` an outside **company** | `[PROD]` graph `node_type` for both, 2026-10-04 |
| Your pitch threads are anchored on *"Mr Rohit Swerashi"* | `[PROD]` thread names; `[CODE]` `context/backfill.py:601` `name_thread_nodes` takes the oldest `corresponded_with` person with no self filter |
| Cards ask you to act on yourself | `[PROD]` *"Send Mr Rohit Swerashi your current traction metrics"*, *"Get Mr Rohit Swerashi's investor decision on GeniOS"*, and an offer card listing `ceo@thegenios.com` and you as *"waiting longest"* |
| Three or four modules decide "internal" three or four ways | `[CODE]` `context/runner._internal_emails` (seats + `orgs.email` + connection accounts, no domain rule); `context/support_situations._internal`; the outreach set; `_mailbox_owner_for`; the tenant-identity exclusion in `reason/runner.py:869-878, 907-909` |
| One mailbox only | `[PROD]` one Gmail connection; `ceo@thegenios.com` appears only as a recipient of your own mail |

## 2 · Why

*"Who is us"* sits under every judgment the expert makes: who owes the next move, who the target
is, whether a reply exists. Get it wrong once and every later step inherits the error.

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | the identity service | new `platform/self_identity.py` | one function, `identity_for(conn, org_id) -> SelfIdentity`: seats and their emails; `orgs.email`; every connected account; every address the account sends **from**; the org's own non-public domains; and your declared list (3.2). Public mail domains (`gmail.com`, …) are never "us" as a domain — only as an exact address |
| 3.2 | your declared list | migration (next free number) `org_self_identities` | `(org_id, kind = address\|domain, value, declared_by, declared_at)`; seeded from D6 |
| 3.3 | one caller | the four modules in §1 | each calls `identity_for`. An AST guard (`tests/platform/test_one_answer_to_who_is_us.py`) fails if any module outside `platform/self_identity.py` builds an internal-address set itself — *check the AST, not the text* |
| 3.4 | threads name the other side | `context/backfill.py:601` | the thread's party is the oldest **non-self** correspondent |
| 3.5 | the repair | `scripts/repair_self_identity.py` (written by Claude, run by Harsh) | re-types the service and company nodes, renames threads anchored on you, retires the signals and cards whose subject is you — **each retirement writes a `card_event`** |
| 3.6 | the card guard | `deliver/card_builder.py` (and `STEP-14`'s contract check) | a card whose subject or recipient is us is refused, with a reason |

⛔ **Keep `7075014c`'s exception.** On `harsh/mvp`, a `dependency_stated` card may be grounded on
*your own* sentence — *"the sentence is the situation"*. Your words may be the evidence; you may
never be the person to chase.

## 4 · What will happen

| | Today | After |
|---|---|---|
| Manik's 8 Aug ask | *"Send Mr Rohit Swerashi your traction metrics"* | subject: Manik, Titan · owner: you · *"Manik asked for ___ on 8 Aug; you have not sent it"* |
| The offer to Khushi | *"…ceo@thegenios.com and Mr Rohit Swerashi have been waiting longest"* | Khushi is the counterparty; your two addresses are you |

## 5 · Expected

- 0 cards whose subject or recipient is one of your addresses or domains;
- 0 threads anchored on you;
- `ceo@thegenios.com` and `thegenios.com` typed as *us*;
- every *"waiting on you"* check reads all connected mailboxes.

## 6 · Verify

```
.venv/bin/python -m pytest tests/platform/test_one_answer_to_who_is_us.py -q
#   a fixture org with two founder addresses and a company domain; each of the four former
#   implementations, called through the service, agrees; the AST guard rejects a fifth
# production, read-only, after the repair:
#   cards whose business_subject or assignee resolves to a self identity → 0
```

## 7 · Risks

| Risk | Guard |
|---|---|
| A shared domain (a co-founder's company) marked as us by mistake | domains are only ever *declared*, never inferred |
| The repair retires a card you still wanted | every retirement is a `card_event` with its cause, so it can be audited and rebuilt |

---

## 8 · The check of 2026-10-06 — what the draft got right, and wrong

Every claim was re-read against `speedrun008` @ `81857ce2` by two read-only passes and spot-checked by
hand at the cited lines; the golden set was measured on a scratch database (all 40 founder cases,
recorded answers). Production was **not** read — reads need Rohit's permission; §8.6 is the SQL.

### 8.1 · Measured — the golden set does not show the defect

| | golden set |
|---|---|
| cards whose subject (`business_subject`) or headline names the founder | **0 of 18** |
| situations anchored on a founder node | **0** |
| thread nodes named after the founder | **0** |
| the founder's own company domain (`nimbuslabs.test`) | typed `company` — an outside company — in 14 of 40 cases (the founder's person node exists in 16) |
| "us" as the engine computes it (`context/runner._internal_emails`) | `{arjun@nimbuslabs.test}` — one address, which is also `orgs.email` |
| seats | **none** (F54) — so W-01's sent-folder half never fires |

**Why it shows nothing:** the golden founder has ONE address and it is `orgs.email`, so every
address-based check catches him. Production's shape is different — the connected Gmail address
plus `ceo@thegenios.com`, which appears only as a recipient of the founder's own mail, plus the
company domain, which is also GeniOS's platform domain. And the pass that names threads after
their party runs in the heartbeat, which the golden runner never calls. So STEP-04 adds
production-shaped founder cases and exercises the naming pass in its acceptance (§8.4, C5).

### 8.2 · The claims

| Claim | Verdict |
|---|---|
| "us" is decided four ways | ❌ **eighteen** — `context/runner._internal_emails` (seats ∪ `orgs.email` ∪ `connections.external_account_id`), and 17 others: three re-write the same SQL inline (`reason/runner.py:996-1014`, `context/meeting_touch.py:126-138`, `packs/brains/org_discovery.py:572-620`), five use a narrower or different set (`deliver/pipeline._tenant_identities` — orgs + seats, no connections; `deliver/timezone_infer`; `api/routes.KNOWN_FROM_SENT_SQL` — seats only; `context/backfill.py:106-109` — active seats only; `reason/moments/engagement` — seat domains), one is one address (`context/outreach_situations._mailbox_owner` — None as soon as a second sending address appears), one is fuzzy (`context/condition_situations._is_owner`), and one has no self test at all (`context/situation_bso` counts the founder as an external member) |
| `connections` carries the connected account's address | ❌ — `connections.external_account_id` is read in four places and **written nowhere** (`api/routes.py:821` says so); "us" is effectively `orgs.email` + active seats |
| ⛔ (new) a Gmail founder makes every gmail.com sender "us" | ✅ live — `context/support_situations._internal` (`:1355-1374`) adds the domain of `orgs.email` with no public-mail guard, and `:1425` marks a message internal on `domain in internal_domains` — so in the support lane an investor writing from gmail.com reads as one of us |
| `ceo@thegenios.com` is a service node | ✅ — `context/pipeline._person` (`:978-979`) types any `is_platform_sender` address `service`, and `settings.platform_domains` is `thegenios.com` (`platform/config.py:100`) — GeniOS's own product domain, which is also your company's. The type sticks (`find_or_create_node` never re-types) |
| `thegenios.com` is an outside company | ✅ — `_works_at` (`context/pipeline.py:1011-1043`) mints a `company` for every non-personal recipient domain; it is "ours" only inside one event's anchor exclusion (`:1036-1037`), and the runner's self set cannot match a domain key |
| threads are anchored on you — `backfill.name_thread_nodes` has no self filter | ⚠️ — the sweep has none (`backfill.py:640-645`), but the `corresponded_with` edges it reads are written only for non-internal addresses (`pipeline.py:1233, 1719`). ⛔ **The path that names threads after you is another one:** `pipeline.py:1494-1501` names a thread `"<sender> — <objective>"` from the message carrying its business claim, whatever its direction — your own outbound pitch included — and `graph_store.name_thread_node` never renames a label it did not generate (`:380-385, 610-611`). So "Mr Rohit Swerashi — <the pitch>" is frozen |
| cards ask you to act on yourself | ✅, by code — no check anywhere that a card's subject is not the tenant; `business_subject` falls back to `resolved_person_name(quotes)` — the FIRST person NAMED in the quotes (`deliver/card_builder.py:647-650, 905-906`), so an investor's "Rohit, can you send your traction metrics?" titles the card after you |
| "waiting longest" lists you and `ceo@thegenios.com` | ✅, by code — `ceo@` never sends, so every outbound mail to it writes `ball_in_court=them` (`pipeline.py:1248-1277`) and it waits forever; `read_organization_silence` and `_WAITING_ROWS` (`outreach_situations.py:197-249, 1235-1310`) filter neither "us" nor `service` nodes |
| keep `7075014c`'s exception | ✅ — `dependency_stated` is in `_GROUNDED_BY_OUR_OWN_WORDS` (`card_builder.py:104-121`): our own words may ground that card |
| `9e5cede8` anchors a stated dependency on the counterparty | ✅, with a fallback — `correlation_dependency.event_parties` (`:903-926`) prefers non-us parties by `_internal_emails`, but anchors on us when we are the only party |
| the reason-runner excludes the tenant (`reason/runner.py:869-878, 907-909`) | ⚠️ wrong lines — it is `:996-1014`, `:1044-1047`; exact address only, the pack-rule loop only — the compiled lane (`domain_shadow`) has no self check of its own |
| a signup gets a seat | ✅ — `platform/seats.ensure_owner_seat` makes `seat_owner` from `orgs.email` at signup, on owner login and every beat. The golden runner creates the org the way signup does **but not the seat** — F54 |

### 8.3 · What changes for you

| | Today | After STEP-04 |
|---|---|---|
| Manik's 8 Aug ask | *"Send Mr Rohit Swerashi your traction metrics"* | the subject is Manik; the card says he asked and you have not sent it |
| a pitch thread | "Mr Rohit Swerashi — <the pitch>", forever | named after the person you wrote to and what it is for |
| the offer to Khushi | *"ceo@thegenios.com and Mr Rohit Swerashi have been waiting longest"* | only outside people can be waiting; your two addresses never are |
| an investor writing from gmail.com, in the support lane | counted as one of us | an outside person |
| `ceo@thegenios.com`, `thegenios.com` | a service; an outside company | you, and your company — excluded everywhere a counterparty is chosen |

### 8.4 · What will be built — tree block `yc2_w27_s04` (milestone M22), proposed

| # | Units | Where | What |
|---|---|---|---|
| C1 | 4 | `migrations/0193_org_self_identities.sql`, new `platform/self_identity.py`, `scripts/declare_self_identity.py` | the declared list (address · domain, never a public mail domain); `SelfIdentity` and `identity_for(conn, org_id)` — seats, `orgs.email`, connected accounts, the declared list — and `is_us(email)` / `is_us_node(type, key)`; a script to declare D6's three values |
| C2 | 19 | every module in §8.2 | each one asks `identity_for` instead of building its own set — `_internal_emails` first, because ten callers read it; the support lane's domain half becomes the **declared** domains only (the gmail.com fix); a declared address is never typed `service`; a declared domain's company is excluded from anchors in every event; the thread is named after the **non-self** party; the waiting readings skip us and `service` nodes; and an AST guard (`tests/platform/test_one_answer_to_who_is_us.py`) fails if a module outside `platform/self_identity.py` builds its own set, with the seat-routing lookups declared |
| C3 | 1 | `deliver/card_builder.py` | the subject chain never resolves to us; a card whose subject is still us is refused with a reason. `7075014c`'s exception kept: your words may ground a `dependency_stated` card, you may never be the one to chase |
| C4 | 1 | `scripts/repair_self_identity.py` (written by Claude, run by Harsh) | dry run by default: the nodes to re-type, the threads to rename, the cards and signals whose subject is you — each retirement a `card_event` with its cause; `--apply` writes |
| C5 | 10 | the golden set | the runner gives the tenant its owner seat, as signup does (F54); **the board moves** — re-recorded, every moved case explained, and STEP-03's acceptance tables restated for the seated runner; four production-shaped founder cases (two addresses, a company domain that is also the platform's, an investor naming the founder in an ask, a gmail.com counterparty in a support thread); the marking refuses a card whose subject is us; **the acceptance**: across every case, 0 cards with us as the subject, 0 situations on us, 0 threads named after us (with the heartbeat's naming pass run), 0 of us waiting |
| C6 | 2 | `scripts/pipeline_health.py`, `platform/receipts.py` | *no open card is about us*; *no thread is named after us* — read-only, after the repair |

**37 units** — C1 4 · C2 19 (18 callers and the guard) · C3 1 · C4 1 · C5 10 (the founder contract,
the seat, the marking, STEP-03's tables and the board re-recorded, four cases F41–F44, the acceptance) ·
C6 2. Every caller depends on the answer alone, never on another caller; units sharing a file are
built one after the other. Order: C1 → C2 (`_internal_emails` first) → C3 → C5's seat and the board
re-record → C5's cases and marking → C4 → C6 → C5's acceptance last.

**Not in this block, with the reason:** L1's direction and capture-time thread reconstruction keep
one owner per connection (`api/routes._mailbox_owner_for`) — direction needs the mailbox owner, not
the tenant's identity, and the second address never sends; declared in the guard. Who owns what on
a team of several seats — `STEP-09`. A UI to declare identities — the script does it until `STEP-07`'s
brief can carry it.

### 8.5 · Decisions — none blocks the start

| | Question | Default, if you say nothing |
|---|---|---|
| D6 (✅) | the declared list: `mrrohitswerashi@gmail.com`, `ceo@thegenios.com`, domain `thegenios.com` | exactly these three — say if you send from any other address |
| D14 (new) | the repair retires the cards whose subject is you — Harsh runs the dry run, you read its list, then `--apply`? | yes — nothing is retired without the dry run's list in your hands |
| — | `invite@thegenios.com` (GeniOS's own product mail) — a service, or you? | both keep it out of every counterparty choice; it stays typed `service`, and only declared addresses are re-typed |

### 8.6 · Production — the numbers to read, after the deploy (read-only; Harsh or Rohit runs them)

```
-- who "us" is today, for the design partner
select email from orgs where id = :o;
select seat_id, email, active from org_seats where org_id = :o;
-- the defect's size
select node_type, count(*) from graph_nodes where org_id = :o and valid_to is null
   and (canonical_key like '%@thegenios.com' or canonical_key = 'thegenios.com') group by 1;
select count(*) from graph_nodes where org_id = :o and valid_to is null and node_type = 'thread'
   and display_name ilike 'Mr Rohit Swerashi — %';
select count(*) from cards where org_id = :o
   and state in ('queued', 'surfaced', 'snoozed', 'claimed', 'delivered')   -- CardStore.OPEN_STATES
   and business_subject ilike '%Rohit Swerashi%';
```

After the repair, the last two read **0**.
