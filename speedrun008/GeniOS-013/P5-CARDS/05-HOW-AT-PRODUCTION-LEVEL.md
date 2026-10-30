# P5 · Cards · 05 · How it will be done at production level

**Owner:** Harsh, and the agents Harsh assigns, for the engine (`deliver/`, `api/`, `contracts/`); the owners of the dashboard and the Mac app for the screens. Rohit approves each tenant's activation and every screen's dummy.
**Rule:** each step first passes in the notebook ([04](04-WHAT-NEEDS-TO-BE-DONE-NOW.md)); every screen change goes dummy first ([07](07-THE-CARDS-SPEC.md) §12.13).

---

## 1 · One card path

- **The card pass stays one door,** `deliver/pipeline.build_cards_for_org`, and changes its source per tenant: a switched tenant's pass reads admitted page versions with their results, and goal versions; an unswitched tenant keeps today's signal loop. The switch is the existing `cards_from_situations` row, made real (today it only relabels a counter).
- **The gate and the raise rule** (07 §2.1–2.2) are one module, `deliver/raise.py`, with every condition's why-not; the lane map (07 §5.1) is one table in it, carrying its hard-constraint id.
- **The six old writers stop delivering per tenant** at P1's parity gate, with P4-17: the legacy pack rules, the compiled lane, the expert file decisions (folded into the judge), the question signals (now the page's founder questions), the team emitter and the test-mode decider. Until the gate they keep writing beside the new path, invisible to the person.
- **The card guard** runs in CI for every switched type: a card that does not trace to a ReasoningResult or a goal version fails (CG-1, CG-23).

## 2 · The card record and its contract

- **The `cards` table** keeps its 47 columns and gains: `work_id`, `page_version`, `snapshot_revision`, `result_id`, `goal_id`, `goal_version`, `trace_id`, `raised_by`, `card_source`, `card_lane`, `kinds`, `kind`, `severity`, `tier`, `rank_inputs`, `hc_ref`, `number`, `check_in`, `audience`, `delivery_why_not` (one migration, additive).
- **New tables:** `card_goal_ordinals (goal_id, card_id, ordinal)`, never reused; `card_refusals` gains the rule ids CC-1 to CC-28.
- **The identity index:** one open card per `(org, work_id)`, and per `(org, goal_id, reached)` for reached cards. Today's `cards_one_per_signal` and `cards_one_open_card_per_file` stay for old-path cards until the cutover.
- **The CardView** (07 §3) is the contract, served whole by `GET /cards/{id}` and as a summary by `GET /cards`; `contracts/card_view.py` holds its schema, and the dashboard's `card-read.ts` is its one reader.
- **The founder's acts, `card_outcomes`, `predictions` and the `surface` field** are P2's tables (P2 §4.7, §7.2, §7.5); P5 writes them through P2's door.
- **The card contract** (`contracts/card_contract.py`) grows to CC-1 to CC-28 (07 §4.10), run at render and again before any surface draws.

## 3 · Words

- **R-10** (`deliver/card_copy.py`) narrowed to the face (subject, summary, how, banner line) and switched on per tenant through `l4_activation`'s `card_copy` row: in shadow first (copy written, the screens still showing the fallback), then shown after a week of copy with every sentence passing the contract.
- **The held-file question** reworded at `reason/expert/verify.py:812`; the lane prefix removed from `deliver/render.py:217-254`; the template consequences and codes removed at their builders (07 §4.5).
- **The renderer refers to parties by id** and writes "you" for the reader's own party (07 §4.5).

## 4 · Lanes, kinds, severity and rank

- **The severity table and the rank order** are hard constraints `hc.p5.severity` and `hc.p5.rank` in `_reasoning/hard_constraints.yaml`, owned by P5, with Rohit as their reviewer; every code path that writes a severity, a tier, a rank or a card lane carries the id (CG-6).
- **`deliver/bands.py` is replaced** by the severity module; `queue()` (`deliver/store.py:973-990`) orders by the rank.
- **The kind chip** is chosen in the CardView builder from the result's `kinds`.

## 5 · Attention and channels

- **Reused as built:** `deliver/timing.py` (quiet hours, the meeting hold), `gate.py`, `policy.py` (kill switch, holds, floors, opt-out), `rate_limiter.py` (atomic windows; 1 an hour for cards), `scheduler.py` and `outbox.py`.
- **The budgets per person** live in the tenant's policy row, with the Atlas's starting values; L6's would-tune rows sit beside them in shadow.
- **Email** is the first push channel: a transactional sender is chosen and registered in `deliver/channels/email.py` (today registered with no transport); every send is an outbox row, re-checked with `still_open()` at send.
- **The morning brief** has its own job at 08:00 in the company's time zone, a seat's own only when it sets one (P1 R4), and the dashboard's Today card and the Mac app read it from `GET /v1/executive/morning`.
- **The phone** waits for a mobile client or web push; nothing is built for it in V1.

## 6 · Closing

- **The check-in evaluator** is a pure function in `deliver/check_in.py`, run on every new evidence and nightly by Maintain (P1-6).
- **The authority window stops being a card clock:** the card window is no longer cut to `authority_expires_at` (`deliver/card_builder.py:1305-1317`), and `platform/card_lifecycle.expire_lapsed` closes only waiting cards past a stated date and superseded versions (07 §8.7).
- **`resolve_cards`** gains the end types of 07 §8.8 and writes `card_outcomes` on every close.

## 7 · Actions, delegation and approval

- **`POST /cards/{id}/action`** (`deliver/actions.py`) gains `pick_side`, `drop`, `right` and `undo`, and every press writes a P2 founder act with the card and page versions and the evidence shown.
- **`POST /cards/{id}/delegate`** is new: a seat, a step, a due date, a note; pressed by the workspace owner or an admin (07 §10.2).
- **`POST /v1/delegations`** (built) builds the play from the card and adds the task contract's parts to the request (`contracts/plays.py:239-259`); an agent lacking a registered play, or whose scope does not fit the step, is not offered; an approved proposal dispatches at most once; the agent lane can be stopped per tenant (07 §10.8).
- **The Approvals page** reads open delegation proposals, not the unused `approvals_queue`.

## 8 · Screens

- **The dashboard** (the private repo): every surface reads through `src/lib/card-read.ts`; the Cards page, the Goals page and Home change as 07 §12.3–12.5 says, each after Rohit approves its dummy; the Goals page's mapper is removed; there is no sample mode on Cards, and no sample number outside sample mode anywhere.
- **The Mac app:** the approved design on `rohit/desktop-ux` (`0.3.0`) is finished (Delegate live, the goal line, the kind chip) and merged after its dummy sign-off; until then, the shipped app's "Not useful" opens the reasons and its refusals are shown, not swallowed.
- **DMGs** are built only through `scripts/mac-dev-dmg.sh` (its fixed local signature keeps the Accessibility grant).

## 9 · Cost

| Item | Cost |
|---|---|
| R-10, the card writer | about $0.005 a material version at list price; a tenant with 30 material versions a day spends about $0.15; ceilings $0.02 a call and $0.50 a day |
| Drafts made before they are asked for (D-P5-21) | one call of P4's draft site per high or critical card version whose first step sends a message, and per waiting card that turns into a nudge: a few a day for the design partner, inside Act's budget (P1) |
| Email | the transactional sender's price per mail; at most a few mails a day per person by the budgets |
| Everything else in P5 | code: 0 model calls |
| A quiet day | 0 model calls and 0 versions from P5 |

The test-mode decider's 3,695 calls a week stop at the cutover (P4-17), which is the larger saving.

## 10 · Rollout, shadow and rollback

1. **Census first** (P5-0) on every tenant; the baseline in 08-LOG.
2. **Shadow:** for a tenant, the new path writes its cards beside the old, invisible; `COMPARISON_KEYS` and the recall guard run every sweep for a week.
3. **R-10 in shadow,** then shown.
4. **Screens:** each dummy approved by Rohit, then the real files; the parity test green.
5. **The switch** at P1's parity gate, per tenant, with Rohit's approval: the new path delivers, the old writers stop.
6. **Rollback** is the activation row: flipping it restores today's cards; the new cards stay in shadow.
7. **New tenants** start on the new path once it has passed the acceptance set (D-P1-9), with no switch flipped by hand.

## 11 · Monitoring

- **The census** per tenant per day (07 §16.2), on each tenant's support view.
- **The alerts** of 07 §16.6, to the tenant's owner and to Harsh.
- **A breach of a "never" line pauses delivery** for that tenant (cards still listed in shadow) until it is fixed.

## 12 · Failure modes

As 07 §17: the writer's failure never removes a card; a refused subject waits for the next version; a failed body says so; a failed run never overwrites a card; races use compare-and-set; a failed send retries and falls back to the Mac drop and the brief; a refused press shows its sentence; an overstepping agent stops its lane.

## 13 · What must never happen

- **Two open cards about one situation.**
- **A card raised by a date, a signal or a rule after the tenant's cutover,** with no judgment behind it.
- **The checker's words, a held reason, an internal code, or the reader in the third person on any surface.**
- **A number, a date or a name on a card that is not in its facts.**
- **A card that names no goal and is not counted as not linked.**
- **A card closed as done without proof or the person's recorded word.**
- **Anything sent, posted, paid, signed or submitted without a named person's approval of the exact bytes.**
- **A refused press hidden from the person.**
- **A card from a private source shown to a seat that may not see it, or a notification carrying it.**
- **A mute armed without Rohit's decision, or any mute on a safety, legal or compliance card.**
- **A person's action that changes nothing.**
