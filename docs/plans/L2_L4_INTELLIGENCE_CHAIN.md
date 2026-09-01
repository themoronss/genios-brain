> **Created:** 2026-08-31 · **Status:** 🟢 Active — Passes A–C shipped, the flag flip is not done
>
> **Purpose:** Close the L2 → L3 → L5 chain that made every card generic — the facts derived from
> silence, the situations named after what is happening, the slots a card may state, and the
> refresh that lets any of it become visible.

## The diagnosis this fixes

The corpus was not the problem. Three separate breaks upstream and downstream of it were:

1. **Cards could state seven things.** `deliver/slots.py::compute_slots` returned `entity, days,
   stage, money, action, who, concerns`. The invention guard in `render.py` rejects any name,
   number or date not in facts + slots, so an authored `render_hint` asking for "since when, how
   many times, is that unusual for them" failed the guard and fell to its template stub — on every
   row. That, not thin expertise, is why eighteen live cards read alike.
2. **Nothing was derived from absence.** L2 wrote `thread.last_inbound/last_outbound`,
   `deal.*`, `party.role`, `relationship.nature`, `commitment.*`, `meeting.*` — all records of
   things that HAPPENED. No source system emits "they have not replied", so no layer could.
3. **Situations named subjects, never states.** `situation_type(anchor_type, domain)` maps a node
   type to a name, so a person became `admin_contact`. A capability written for "we wrote and
   nobody answered" had nothing to bind to and fell into a person-shaped lane whose only
   available predicate was `thread.ball_in_court` — which every waiting relationship satisfies.

Two more, found while fixing the above:

4. **`missing_fields` was a hardcoded `()`.** `context_adapter.evaluate` consults exactly that set
   to decide UNKNOWN, so an `exists:` test on a field nothing writes returned a confident FALSE.
5. **`observation_vocabulary()` was dead code.** The extraction prompt carried its own hand-typed
   kind list, so `CANONICAL_OBS_KINDS` could grow and the model never learned the words existed.

## Pass A — a card can say something (shipped)

| Change | File |
|---|---|
| Five facts derived from silence: `thread.days_waiting`, `thread.follow_up_count`, `thread.last_heard_days`, `thread.response_expected`, `party.reply_cadence_days` | `context/waiting.py` (new) |
| `missing_fields` derived from the domain spec instead of hardcoded empty | `context/situation_bso.py` |
| Slots 7 → 13: `waited_days`, `follow_ups`, `last_heard_days`, `their_cadence`, `role`, `ball` | `deliver/slots.py` |
| Stale cards rebuild in place — same `card_id`, same queue state, never re-pushed | `deliver/store.py`, `deliver/pipeline.py`, `deliver/card_builder.py`, migration `0077` |

The timeline source is `graph_source_refs`, not the facts: `thread.last_outbound` is single-valued
and holds the latest message, while every write (including a corroborating no-op) leaves a ref
bound to its event, and the field name carries the direction. That is the only place a follow-up
COUNT or a reply CADENCE can come from.

**Proven on real Postgres.** Same signal, before and after:

```
BEFORE: Investor A
AFTER : Investor A — investor, waiting 3d after 2 follow-ups; they normally reply in 2d
```

## Pass B — L2 reads admin reality in admin words (shipped)

- **17 new observation kinds** across approvals, money/documents, fundraising and meetings.
  `pass_received` is deliberately not `closed_lost_mention`: a fund passing is often reversible,
  and filing it as a lost deal is what produced "Save the deal now" on a rejection.
- **The dead vocabulary is now the live one.** `signal_kinds_block()` renders the prompt section
  from `OBS_GROUPS`, so the prompt is a VIEW of the vocabulary rather than a copy of it.
- **Three state-based situation types**, minted by `context/outreach_situations.py`:
  `awaiting_response`, `commitment_overdue`, `meeting_follow_through`. Declared on **admin alone**
  — the readers mint one situation per claiming domain, so a second claimant would mean two
  situations, two compiles and two cards for one silence.

## Pass C — the expertise gets the situation (shipped)

- Three authored situation files with real multi-condition gates, each pairing its `render_hint`
  with slots that actually exist:
  `outbound-awaiting-reply.yaml` · `promise-past-its-date.yaml` ·
  `meeting-without-follow-through.yaml`
- Corpus vocabulary extended (facts, kinds, L2 types); routing index regenerated.
  Admin now routes **8** L2 types; `l2_types_unrouted_globally: 0`.
- `MAX_PLAYS` 4 → 16. A play is a candidate, not a card, so the cap limited CHOICE and cut
  whatever sorted last alphabetically — nine authored strategies on `account_admin`.

**Proven on real Postgres**, end to end:

```
awaiting_response  ROUTED -> admin.sit.outbound_awaiting_reply, 4 capabilities
                   missing_fields declared = ('outreach.objective',)
```

## Deliberately NOT done, and why

**One manifest per capability.** The audit called for it. It would make things worse: the compile
loop emits one signal per manifest, so `account_admin`'s thirteen capabilities would become
thirteen cards about one person. The real fix for the collapse is a NARROW route — a state
situation with a real gate reaches 4 capabilities, not 13 — which is what Pass B/C did instead.

**`GENIOS_USE_DOMAIN_COMPILER`.** Still unset, deliberately. It is a production decision, it needs
migrations `0076` and `0077` applied first, and `expertise_packages` growth is what took production
read-only once already.

## Declared gaps — named, not hidden

| Name | Why it has no writer |
|---|---|
| `outreach.objective` | Nothing knows what an outbound was FOR. The extraction envelope carries direction and parties, no purpose. It is the difference between a follow-up and a reminder, and it shows in `missing` on every `awaiting_response` row. |
| `commitment.delivered_at` | No source reports that a promise was kept. An outbound after a due date is not evidence the promised thing was in it. So a card may say "still showing as open" and never "you did not send it". |
| `meeting.recap_sent` | An outbound within a day of a meeting is not a recap of it. Inferring one would let unrelated mail mark the strongest finding resolved. |

## Verification

- Hermetic: **1906 passed**, 121 skipped, 152 xfailed.
- Real Postgres: **2025 passed**, 2 failed — both **pre-existing on clean HEAD**
  (`test_a_deal_fact_from_correspondence_mints_a_deal_node`,
  `test_pg_a_channel_without_an_adapter_is_terminated_by_the_drain_on_sight`), confirmed by
  stashing this work and re-running.
- Corpus: `validate.py` **0 errors**, 283 warnings (was 286 — the three new routing gaps closed).

## What is left

1. Apply `0076` + `0077` to production.
2. Set `GENIOS_USE_DOMAIN_COMPILER` for one tenant and read the cards.
3. Give `outreach.objective` a writer — it is the largest single remaining lift in card quality.
