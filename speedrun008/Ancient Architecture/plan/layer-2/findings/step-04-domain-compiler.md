# L2-4 · Domain Compiler — findings

**Run:** 2026-09-24 · premise checked BEFORE any code · **no migration · no model call**
**Against:** `speedrun008` @ `aa6ab06e`
**Result:** 17 tests, **12,993 passed · 14 failed (all pre-existing) · 0 regressions**

---

## 1. ⛔⛔ THE FINDING — the fundraising doctrine EXISTS, and one `None` makes it unreachable

The step file, §1:

> *"They die one layer later because **no fundraising corpus exists** — `Domain Expertise/` holds
> Admin, Sales and Customer Support and nothing else… **The fix is authoring, not code.**"*

And the routing table's own comment:

> *"`fundraising` and `general` map to NOTHING and that is not an oversight: **no corpus was
> authored for them**."*

**Measured against the catalog, 2026-09-24:**

```
sales.sit.live_investor_relationship      status=stable   review_status=approved
   "An ongoing relationship with a party that might fund us, read at the ACCOUNT level:
    the fund, the accelerator, the syndicate — not the individual"

sales.sit.live_investor_contact           status=stable   review_status=approved
   "A named individual at an investor, accelerator or programme, read at the PERSON level:
    where their conviction stands, what they last asked for"

sales.investor_relations.investor_relations
   "Reading and running the relationships with the people who might fund the company:
    funds, accelerators, angels and the operators who introduce them."
```

⛔ **The investor doctrine was authored — inside the Sales corpus — and the Sales registry routes
`investor_relationship` and `investor_contact` straight to it.** `_L2_TO_L3_DOMAIN["fundraising"]`
answers `None`, so **the pilot tenant's dominant domain cannot reach doctrine that already exists,
is stable, and is approved.**

**Nothing was missing. The plan's largest non-code item is a one-line code change.**

### 1.1 · And the objection the comment raises does not apply to `sales`

> *"Mapping them onto `admin` to 'get some coverage' would put Admin doctrine on a fundraising
> situation."*

True of `admin`. **Routing is per SITUATION TYPE, not a domain blanket**, and every type
`fundraising` can mint lands on investor-named doctrine and nothing else:

| fundraising anchor | situation type | routes to |
|---|---|---|
| `company` | `investor_relationship` | `sales.sit.live_investor_relationship` |
| `deal` | `investor_relationship` | `sales.sit.live_investor_relationship` |
| `person` | `investor_contact` | `sales.sit.live_investor_contact` |

**Zero generic-deal exposure**, proven by
`test_every_fundraising_type_would_land_on_investor_doctrine_only`, which keeps proving it.

### 1.2 · Declared, evidenced, and NOT armed

`domain_shadow.CANDIDATE_ROUTES` carries the route with its evidence and an **ENDS WHEN**.
`_L2_TO_L3_DOMAIN["fundraising"]` **stays `None`**, and a test asserts that it does.

**Why not just arm it:** arming makes every fundraising situation activatable at once and **nobody
has counted them on the pilot**. Same shape as L2-2's `OBSERVE` laws and L2-3's budget — measure,
declare, arm in one line. → **Harsh 26.**

`live_lane` still requires the tenant to have activated the `sales` corpus, so arming this is the
second of two switches, not the first.

---

## 2. ⛔ `general` is dark for a DIFFERENT reason, and one sentence covered for both

| domain | why it is dark | the mover |
|---|---|---|
| **fundraising** | a **stale sentence** — the doctrine exists | one line in the routing table |
| **general** | genuinely **ambiguous** — `relationship` is claimed by **all three** corpora | a **census** of what actually lands there |

Picking one of three corpora by hand is how Admin doctrine lands on a support thread. Both
declarations in `context/domain_silence.py` now say their own reason, and a test refuses `general`
a candidate route.

---

## 3. Three places stated one fact and agreed by coincidence

```
context/domain_spec.registered_domains()   admin · fundraising · general · sales · support
reason/domain_shadow._L2_TO_L3_DOMAIN      admin · sales · support · customer_support
context/domain_silence.DARK_DOMAINS        fundraising · general          (added by L2-0)
```

**They agreed. Nothing bound them.** `fundraising` and `general` were *absent* from the map, not
*declared* — and `.get()` answers `None` for a domain somebody decided about and for one somebody
forgot. **`support` was forgotten once and 33 situations died silently for it.**

The map is now **total** — every registered domain has a row, including the two that map to `None`
— and `tests/reason/test_domain_mapping_is_total.py` binds it to the registry in one direction and
to `DARK_DOMAINS` in the other. `customer_support` as a key is declared in `CORPUS_ID_ALIASES`
with its reason, and a row pointing at an unauthored corpus fails the build.

---

## 4. The count existed and threw away what made it actionable

`counts["unactivatable_domain"]` was already there, added when this silence was first found. **It
is a scalar.** `unactivatable_domain: 69` cannot say whether to author `fundraising` first or
`general` first — and the code's own comment says the answer is not close:

> *"`general:relationship` is the most-authored type in the corpus (15 situations across the three
> domains) and **the largest on the pilot (55 rows)**."*

**55 of the pilot's 159 active situations are one dark type.**

`reason/unroutable.tally_unroutable` keeps the scalar — a dashboard reading it must not notice —
and adds two keys:

```
unroutable:<domain>            WHICH corpus to author or route
unroutable:<domain>:<type>     WHICH SITUATION that corpus must describe first
unroutable_undeclared          ⛔ a domain that routes nowhere and DARK_DOMAINS never named —
                                  the `support` defect returning
```

A corpus is authored **per situation type**, so the third key is the one an author can act on.

---

## 5. ⛔ U4's model call was NOT built, and the cost check is why

The unit: *"When nothing routes, **one Haiku call** asks 'which authored corpus is nearest, and how
confident?'"* Cost check: *"only on an unroutable situation — **expected ~5%**."*

### 5.1 · The rate is wrong by an order of magnitude

`general:relationship` alone is **55 of 159 = 34%**, before fundraising. A call per unroutable
situation is **~69 per sweep, every sweep, forever.**

### 5.2 · And the answer does not vary per situation

*"Which authored corpus is nearest to a `fundraising:investor_relationship`?"* is a question about
the **type and the corpus**, not about this particular investor. There are exactly **four**
unroutable `(domain, type)` pairs. A per-situation call re-derives, sixty-nine times, an answer
that has four values.

### 5.3 · And the answer it would give is the one the step forbids

The nearest corpus to an investor thread, by vocabulary, is **Sales** — and §5 of the step says
*"It does not re-point `fundraising` at `admin`"*, with the mapping comment calling the borrow
*worse than silence*. **A confident model proposal is a nudge toward the exact error**, and
*"six VCs and three accelerator programmes became sales opportunities"* is how that error reads.

### 5.4 · And the question is already answered, deterministically and free

§1 answers it: the doctrine exists, it is named, and the route is provable from the registry. **A
model asked to guess what a registry states is a model spending money to be less certain.**

### 5.5 · What it would cost to build anyway

`reason/bundle/sites.R_SITES` is a **closed vocabulary** — `require_site` refuses an unregistered
name, and its docstring's own example of the danger is *"a ledger row under `R-6` that reads as an
activated site right up until the month's bill"*. A new site needs an id, a tier, an output ceiling
**and an activation feature no tenant has** — a ninth thing built and never switched on.

**ENDS WHEN:** a fourth corpus exists and routing is genuinely ambiguous — at which point the
question has more than four answers and a model earns its tier.

---

## 6. Cost check

| | |
|---|---|
| model calls | **none** — §5 |
| migration | none |
| runtime behaviour | **unchanged.** `l3_domain_for` answers exactly as before; the candidate route is not armed and a test asserts it |
| new keys in the sweep tallies | three, additive; the pre-existing scalar is unchanged |

---

## 7. Completion criteria

| # | criterion | verdict |
|---|---|---|
| 1 | unroutable count measured, by domain | ⚠️ **the report is built and its corpus half runs today** (`scripts/unroutable_report.py --corpus-only`). Per-domain **counts** need the pilot — **Harsh 26** |
| 2 | `UNROUTED` in the pass tallies — a silent miss impossible | ✅ **and per situation type**, which is what an author acts on. Plus `unroutable_undeclared` for the `support` defect returning |
| 3 | `_L2_TO_L3_DOMAIN` total, with a reason on every `None` | ✅ total over the registry, bound to `DARK_DOMAINS`, aliases declared, and a row pointing at an unauthored corpus fails the build |
| 4 | a miss produces a reviewable proposal, not a route | ⛔ **NOT BUILT, with a measured reason** — §5. The proposal exists and is **deterministic**: `CANDIDATE_ROUTES`, with its evidence |
| 5 | the admission gap reported per domain, with an owner | ⚠️ **reported** — the 24 `draft` situations are listed by id, per domain, in the report. **An owner is Rohit's to name** — Harsh 22 |
| 6 | the `fundraising` corpus has a named author, **or** the STATUS row says plainly that it stays dark | ✅ **and the answer is neither.** §1 — the doctrine exists; what it needs is a measurement and one line, not an author |

---

## 8. What this step does NOT do

* **It does not arm the fundraising route.** §1.2 — declared, evidenced, one line, waiting on a
  count. `live_lane` still requires the tenant to have activated `sales`.
* **It does not route `general`.** §2 — that is a choice between three corpora, and making it by
  hand is the defect.
* **It does not call a model.** §5 — five separate reasons, each measured.
* **It does not author anything.** The 24 `draft` situations are named; flipping them is an
  author's judgement.
