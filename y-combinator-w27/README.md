# `y-combinator-w27` — what changed, and why

**Branch:** `y-combinator-w27`, cut from `harsh/mvp` @ `23d47640`
**Scope:** the inverted intelligence feed on the pilot tenant
**Result:** 6 source files changed (+350 / −12), 4 new test files (702 lines, 55 tests), zero regressions

| | Before | After |
|---|---|---|
| Test suite | 8787 passed, 24 failed | **8842 passed, 24 failed** |
| New tests | — | **+55** |
| Regressions | — | **0** |
| Tests weakened or skipped | — | **0** |

The 24 failures are pre-existing. They fail identically at `23d47640` and are concentrated in
`tests/capture/esqe/test_qualification_routes.py`, `test_rejection_ledger.py`,
`test_new_route_wiring.py`, `test_g9_gate_probes.py` and `test_h0_gate.py`. This branch neither
fixed nor caused them.

---

## 1. The problem, stated precisely

The pilot tenant produced **nine cards. Eight were marketing** — a mentorship pitch, a course
newsletter, a community blast, a cold outreach. Meanwhile **114 situations describing the real
inbox were held by the publisher and never shown.**

The feed was not noisy. It was **inverted**: noise passed every gate, and signal was refused at
the last one.

Two independent failures produced that, and they are worth separating because the fixes live in
different layers:

**A — noise got in.** A marketing sender became a graph `person` node by emailing once. From then
on `sender_known` was true for them, and `esqe/relevance._rule_verdict` short-circuits on
`sender_known` at 9000 bp — the second-highest rank in the table — which puts the
`List-Unsubscribe` check two lines below it out of reach. The header was fetched, parsed, and
never consulted.

**B — signal was blocked.** `awaiting_response` ("we wrote, they have not answered") is anchored on
a *synthetic* correlation the correlation engine deliberately cannot reach. So the L1 evidence
lookup missed, `evidence_verified_spans` was written as `0`, and the publisher's
`VERIFIED_EVIDENCE_REQUIRED` gate held every one of them — **on a number that was never computed
for them**, not because the claim lacked a receipt.

---

## 2. The four changes

### 2.1 `sender_known` means "we have corresponded", not "we have seen"

**File:** `genios_engine/api/routes.py` · **Tests:** `tests/api/test_sender_resolver.py` (12)

The resolver used to be, in full:

```sql
select canonical_key from graph_nodes
 where org_id = :o and node_type = 'person' and valid_to is null
```

That is "is this address any person node" — a far weaker claim than the name `sender_known`
makes. It is now:

```sql
select n.canonical_key from graph_nodes n
 where n.org_id = :o and n.node_type = 'person' and n.valid_to is null
   and exists (select 1 from graph_facts f
                where f.org_id = n.org_id and f.subject_node_id = n.node_id
                  and f.field = 'thread.last_outbound' and f.status = 'active')
```

`thread.last_outbound` is written onto the **recipient's own person node** every time we send
(`context/pipeline.py`, outbound leg). So "we have written to this person" was already a stored
fact. This is a filter over facts that exist, not a new computation.

> **What was deliberately NOT done.** The obvious fix is to reorder the cascade so the bulk-header
> rule outranks `sender_known`. That is wrong. `tests/capture/esqe/test_relevance.py:126`
> (`test_the_cascade_order_is_the_one_the_plan_fixed`) pins the current order on purpose, and its
> reason is correct: a counterparty we genuinely deal with, sending through Mailchimp, must not be
> dropped for carrying a `List-Unsubscribe` header. Building the reorder would have required
> weakening that test. **The cascade was right; it was being fed a lie.** Every relevance test is
> untouched and still green at 55 passed.

### 2.2 An absence carries the receipt for the message that created it

**File:** `genios_engine/context/situation_bso.py` · **Tests:** `tests/context/test_absence_receipt.py` (14)

Three additions, all reads:

| Added | Does |
|---|---|
| `outbound_event_ids()` | which messages we sent to this counterparty |
| `gather_l1_signals_for_events()` | the same projection and folding the correlation read uses, joined on the event instead |
| `backfill_absence_l1()` | when the correlation lookup found nothing and we *have* written to the anchor, compose the bundle from those events |

The claim is *"we wrote to them and nothing came back."* The first half of that is a real message
with real extracted spans quoting text we actually typed. **That is the receipt, and it has
existed the whole time.**

> **The gate was not touched.** The publisher's `_preflight` is unchanged. Two tests pin that this
> was a feeding change and not an opening:
>
> - `test_an_absence_carrying_our_own_sentence_publishes` → **ADMIT**
> - `test_an_absence_with_only_the_placeholder_is_still_held` → **still HOLD**, with
>   `VERIFIED_EVIDENCE_REQUIRED`
>
> A claim with no receipt is refused today exactly as it was before.

`backfill_absence_l1` is **additive only**: a correlation the bulk read already answered is never
touched, so every situation that publishes today publishes on exactly the evidence it publishes on
today.

### 2.3 A blast cannot outrank a message addressed to a person

**File:** `genios_engine/capture/esqe/importance.py` · **Tests:** `tests/capture/esqe/test_audience_size.py` (21)

`NormalizedSignal.recipients` — the To+Cc tuple — was already captured and carried, and the only
thing that read it was `capture/visibility_rules`, which decides who may **see** a result. The
system knew how many people a message went to and used it solely for permissions, never for how
much the message **mattered**.

| Recipients | Multiplier |
|---|---|
| absent / ≤ 10 | 10000 (neutral) |
| ≤ 50 | 8000 |
| ≤ 500 | 6000 |
| ≤ 5000 | 4000 |
| > 5000 | 3000 (floor, never zero) |

Three properties worth knowing:

- **Not a sixth weight.** `ImportanceWeights` is total-checked at import because `// 10000` is a
  weighted mean only while the five weights sum to 10000. A sixth term would silently rescale
  every score in the product with nothing going red. This is a **multiplier** on the finished
  mean — the shape the module already uses for `evidence_authority`.
- **Absent is neutral, and neutral is bit-identical.** `x * 10000 // 10000 == x`. A webhook, a CRM
  row and an uploaded document score exactly as before, so every stored score and every replay
  stays valid.
- **The company talking to itself is exempt.** An all-hands to 200 colleagues is a large audience
  and a real one; `internal_kind` mail is never discounted.

### 2.4 A promise is attributed to whoever made it

**Files:** `genios_engine/context/outreach_situations.py`, `context/domain_spec.py`,
`packs/general_v1.py` · **Tests:** `tests/context/test_commitment_owner.py` (8)

`context/pipeline.py` writes an `owns` edge from the commitment **actor** to the commitment node,
tagged `{"derived": "commitment actor"}`. It has been written on every commitment this system has
ever extracted. `read_overdue_commitments` never asked — and its own docstring, *"one finding per
promise of ours"*, was an assumption the code never checked.

Three of the pilot's nine cards therefore rendered **somebody else's promise as the founder's own
overdue obligation, at critical urgency, in the founder's voice.**

Now: `_COMMITMENT_OWNERS` is read in bulk beside `_EMPLOYERS`, the reading emits
`commitment.owner` and `commitment.owner_key`, and the card declares `commitment.owner` as
evidence so it is visible rather than merely stored.

> **Absent stays absent.** "We do not know who promised this" and "the founder promised this" are
> different cards, and the second was being shown for both. An unknown owner is never defaulted to
> us.

---

## 3. What was deliberately not built

This is the section worth reading twice. Seven planned units were retired **because contact with
the code proved the plan wrong**, and in every case the alternative would have meant weakening a
test that was protecting a correct decision.

| Unit | Planned | Why it was wrong |
|---|---|---|
| `M1.C1.U01/U02` | Reorder the relevance cascade | A real counterparty using a mailing platform must not be dropped. The order is right; its input was wrong. |
| `M2.C1.U01` | Invent a typed "absence receipt" contract | Not needed. The outbound message already produces ordinary `EvidenceSpan`s. |
| `M2.C1.U02` | Make the reader carry the receipt | Keeps `outreach_situations` a pure fact reader; the composition path fetches it instead. |
| `M2.C1.U03` | Widen `_preflight` to admit absence claims | **The gate is correct.** It was starving, not wrong. Widening it would have let receiptless claims through. |
| `M1.C1.U03/U04` | Loosen the LLM budget guard on cold tenants | "Alert rather than spend" is a deliberate cost decision, pinned by a test using a client that *raises* on any call. |
| `M1.C2` (category) | Widen the automated-sender regex | Would push role addresses (`billing@`, `support@`) to `node_type='service'`, so a vendor we genuinely correspond with would stop being a counterparty. Individually right, jointly wrong with §2.1. |

**Three of the four shipped fixes are not new intelligence.** They are reads of data the graph was
already writing and nobody was consuming: the outbound span, the recipients tuple, the `owns`
edge. That is why the risk is low and why the baseline did not move.

---

## 4. Known consequence to decide on

§2.1 tightens what counts as a known counterparty, so **the ambiguous share on a cold tenant
rises** and the LLM-5 budget guard will fire more often. That is correct signalling — the system
saying the graph does not know enough people yet — and the events it declines to read are kept at
3000 bp, the lowest non-refused rank, and now also carry the audience discount. They rank low
without anyone spending.

**Whether to raise the 10% ceiling is a cost decision for the budget's owner.** This branch did not
make it quietly.

---

## 5. Still open

| Item | Status |
|---|---|
| Card **voice** ("you promised" vs "Priya promised") | Not done here. Pack rules have no notion of who is reading; the layer that legitimately knows the recipient is L5.2's audience resolver. The card now *names* the owner, which removes the false accusation; the voice makes it read naturally. |
| Funnel report on the pilot tenant | **RED and honest.** `scripts/pipeline_funnel_report.py` needs `--org` and `--database-url` against the pilot Postgres. It is the only check that *proves* the feed flipped — marketing gone, `awaiting_response` present — and it has not been run. It was kept in the tree rather than quietly dropped. |
| The 24 pre-existing failures | Untouched. Out of scope for this branch. |

---

## 6. How to verify

```bash
export PATH="…/toolchains/bin:$PATH"
export UV_PROJECT_ENVIRONMENT="…/scratchpad/venv"

# the four new suites
uv run --no-sync pytest tests/api/test_sender_resolver.py -q          # 12 passed
uv run --no-sync pytest tests/context/test_absence_receipt.py -q      # 14 passed
uv run --no-sync pytest tests/capture/esqe/test_audience_size.py -q   # 21 passed
uv run --no-sync pytest tests/context/test_commitment_owner.py -q     #  8 passed

# the baselines that must not move
uv run --no-sync pytest tests/capture/esqe/test_relevance.py -q          # 55 passed
uv run --no-sync pytest tests/context/test_situation_publisher.py -q     # 32 passed, 5 skipped
uv run --no-sync pytest tests/capture/esqe/test_importance.py -q         # 98 passed, 6 skipped

# everything
uv run --no-sync pytest tests/ -q                                      # 8842 passed, 24 failed
```

Note: run the target files **individually**. Running `test_importance.py` alongside its siblings
produces six fixture-ordering errors that do not occur alone; that pollution predates this branch.

---

## 7. Files

| File | Δ | What |
|---|---|---|
| `genios_engine/api/routes.py` | +48 −5 | `KNOWN_COUNTERPARTY_SQL`, `known_counterparty_keys()` |
| `genios_engine/context/situation_bso.py` | +128 −1 | outbound events, per-event L1 gather, absence backfill |
| `genios_engine/capture/esqe/importance.py` | +109 −2 | audience ladder, multiplier, components |
| `genios_engine/context/outreach_situations.py` | +44 −2 | `_COMMITMENT_OWNERS`, owner on the finding |
| `genios_engine/packs/general_v1.py` | +24 −1 | `commitment.owner` as declared evidence |
| `genios_engine/context/domain_spec.py` | +9 | owner field declarations |

Supporting, not shipped to production paths: `tree.yaml` (the build tree, including every
retirement and its reason), `scripts/qa/check-tree.sh`, `.build/trace.log` (append-only decision
log).
