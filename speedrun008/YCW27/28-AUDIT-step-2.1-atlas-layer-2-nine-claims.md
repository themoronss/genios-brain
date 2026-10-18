# ⛔⛔ AUDIT · STEP 2.1 · ATLAS LAYER 2 — nine claims, two receipts, eleven corrections

**2026-10-03.** The largest remaining block, and the one the plan called *"the nine open claims"*.
Four units built. ⛔ **Eleven corrections along the way, nine of them to my own first reading** —
which is the reason this document is longer than the code it describes.

```
units        U01 receipt 45 · U02 receipt 46 + a declaration · U03 a declaration · U04 paperwork
receipts     44 → 46    both correctness, both L2, both org-scoped
tests        52 new     50 written (18 + 20 + 12) + 2 that appeared by themselves
             ⛔ I predicted 15,387 and the suite reported 15,389. The two extra are
             `test_a_receipt_names_the_package_it_guards`, which is parametrised
             `sorted(C.RECEIPT_PACKAGE)` -- one case per DECLARED claim. Adding two
             receipts added two guard cases without an edit. ✅ That is the declaration
             table being genuinely wired rather than merely consulted, and the
             discrepancy was accounted for rather than waved through.
mutations    49 valid, 49 caught · 0 surviving · 2 invalid (named below, with why)
claims       9 re-checked · 1 EXPIRED · 2 located · 1 partly expired · 1 measured · 4 Rohit's
```

---

# PART 1 · THE TWO THINGS THAT WERE FOUND

Both were graded **STILL TRUE** by the Atlas six weeks ago and never located. Both are now a
receipt, and both turned out to be **worse than the Atlas said**.

⛔ **AND NEITHER QUERY HAS EVER BEEN EXECUTED.** No database URL is configured in this checkout, and
the platform suite drives receipts through a **fake engine** (`class _Engine`), so every assertion
in this document about the receipts is about the *query they render and the conditions under which
they refuse* — never about a number they returned. That is condition **P1** of this programme's own
definition of "production level" (*a receipt against production data*), and it is unmet for all 46
receipts, not just these two. ⛔ Receipt 46 additionally uses `bool_or`, which is **Postgres-only**
and the first use of it in this file — so its SQL has not been parsed by any database either. That
is why `H9` hands Harsh the query **written out by hand**: the first execution is a reading somebody
takes deliberately, not a side effect of a readiness run.

## ⛔⛔ 1 · L2-11 — the alphabetically first domain picks the reasoning's playbook

The Atlas: *"Wrong first domain or restricted mixed-domain evidence can still enter the wrong
view."* Here it is, with the mechanism traced rather than suspected:

```
packs/compiler/capability_resolver.py:833   domain_ids=tuple(sorted(selected_domains))   ← a SET
packs/compiler/expertise_builder.py:87      "domain_ids": plan.domain_ids                ← written
reason/adapters/expertise.py:1463           domain = str(domain_ids[0]) …                ← PICKED
reason/adapters/expertise.py:1511           CapabilityManifest(domain=domain, …)
reason/domain_shadow.py:1169-1172           packs[manifest.domain] = _tenant_pack(…)     ← the
                                                                                           KNOWLEDGE
reason/runner.py:760                        if capability.domain == effective["pack_id"]  ← gated
```

⛔ **The index does not pick a label. It picks the pack.** And because the list is `sorted()` over
a `set`, `[0]` is the **alphabetically first** domain — not the primary one, not the most
confident one, not the one the situation is mostly about. Alphabetical.

⛔ **And it is reachable, not theoretical.** `selected_domains` is a `set` filled in a loop, and a
situation with no usable hint resolves against `sorted(self.catalog.domains.keys())` — *every
authored domain*. **Nothing anywhere records that a choice was made**, while the same package's
citation tags (`reason/adapters/citations.py:127`) carry every domain it was built across. Two
surfaces, one package, no explanation.

✅ **The contract already owns the accessor that does not do this.** `domain_hints` returns every
entry, sorted and unique, and `packs/compiler/runtime_brains.py:205` consumes it that way. The
routing site reaches past it into the raw metadata bag.

**Receipt 45** — *no published reasoning package was routed by picking one of several domains* —
counts the packages where the pick had something to pick between.

## ⛔⛔ 2 · L2-01 — two authority scales share one integer column, and the column decides who wins

The Atlas: *"Incorrect authority configuration would still be applied consistently."* Graded with
the note that the guard is correctness-of-**ordering**, not correctness-of-**config**. That was
right, and underneath it:

| | |
|---|---|
| the ladder | `capture/validate/authority.AUTHORITY_RANK` — dense, `0..6`, seven classes, no ties. `inferred` 0 · `chat_aside` 1 · `email_prose` 2 · `attachment` 3 · `structured_source` 4 · `company_canon` 5 · `signed_document` 6 |
| ⛔⛔ the other scale | `context/analytic/publish.DEFAULT_AUTHORITY_RANK = **100**`, and `FACT_TABLE = "graph_facts"` — **the same table and the same column** |
| the comparison | `context/graph_store.fact_write_action`: `if held_rank is not None and new_rank < held_rank: return "discrepancy"` … else `"supersede"` |

⛔ **So a row at 100 can never be superseded by anything**, and a **countersigned contract**
arriving against one comes back a `discrepancy` and is **discarded in favour of the derived
value**. The ladder's own module already says why the scale may not be stretched: ALG-12's gap of
`>= 2` *"only means anything because the ranks here are a dense, evenly-spaced ladder rather than
scores: subtracting two of these and comparing the difference to 2 is arithmetic that becomes
meaningless the moment the scale changes."*

### ⛔ And three more ranks do not say how they were decided

| rank | also means | where |
|---|---|---|
| **0** | `inferred`, a legitimate class | `UNMAPPED_AUTHORITY` — the floor when **none** of the four tables matched |
| **1** | `chat_aside` | a **bare integer default** at `graph_store.write_fact` and `reason/evidence.build_evidence_ref` |
| **2** | `email_prose` | a **bare integer default** at `graph_store.write_edge` |

⛔ **Rank 1's ambiguity is load-bearing, not latent.** `graph_store` has a promotion rule keyed on
exactly that value — `held.authority_rank == 1 and authority_rank >= 2` → `supersede` — so *"the
caller passed nothing"* is promoted exactly as *"this is a stated Slack aside"* is.

⛔ **The code's own named mitigation is a log line.** `weigh_authority` returns the floor **and**
warns, and says so in writing: *"rank 0 AND a warning. The warning is the half that gets the table
fixed — a floor that is silent is indistinguishable from a correct answer."* ✅ `AuthorityBasis.UNMAPPED`
is the value that tells the two apart, and it is recorded on **exactly one lane's trace**
(`capture/pipeline.py:1685`, `STRUCTURED_STAGE`). Nowhere else does the basis cross the seam. **A
log line is not a reader.**

### ✅ What is NOT claimed, because it was measured instead of assumed

⛔ **No live corruption.** Two things keep the scales apart today:

1. `publish_derived_fact` scopes its own lookup by `version_prefix`, so it never supersedes an
   observed row — *"a module may only"* touch its own.
2. Across the whole engine the observed and derived writers share **no literal field name**:
   observed writes `deal.stage`, `party.role`, `thread.ball_in_court`…; derived writes
   `derived.contract_spend.summary` and friends. **Intersection: none.**

⛔ **But `write_fact`'s lookup is NOT prefix-scoped.** It takes the first active row for
`(org, node, field)` whoever wrote it. So the separation rests entirely on two field vocabularies
never meeting, **and nothing enforces that**.

⛔ **And the measurement states its own blind spot**, because one that hides it reads as a proof:
**31 call sites pass a `field=` this resolver could not evaluate statically** (10 `write_fact`,
14 `_write_fact`, 7 `publish_derived_fact`). *A resolver reports its coverage beside its verdict.*

**Receipt 46** — *no fact holds two authority scales at once* — is the thing that notices the first
meeting, which is the moment the hazard becomes a corruption. ⛔ It deliberately does **not** ask
"does an off-ladder rank exist", which is true today and would be red for ever.

---

# PART 2 · THE TWO THINGS THAT WERE ALREADY CLOSED

## ✅ L2-03 — the scorecard row was wrong

*"First claimant owns a same-name alias, so later name-only prose can attach to the wrong human."*
**Closed in code, and the chain holds in both directions:**

```
observe_person_name        a SECOND LIVE person by the same name → origin='contended'
resolve_alias              excludes contended, AND returns None on 2+ rows
resolve_alias_candidates   so a surface can SEE an ambiguity rather than infer it
tests/context/test_a_person_the_graph_knows_by_name.py
```

The docstring states the law — *"a name shared by several anchored people resolves to NOBODY, not
to the first claimant"* — and unusually the implementation earns it: the writer marks, the reader
excludes, and a third function exists so *"nobody"* and *"several"* are not conflated.

⛔ **I nearly got this one wrong in the other direction.** `resolve_person_name` is a one-line
delegation to `resolve_alias`, so reading it alone makes the docstring look like a claim the code
does not keep. The mechanism is in the **writer**, two hundred lines away. *A law enforced at the
write is invisible at the read.*

## ✅ L2-09 — measured, and the half I expected to find unread is read

| half | verdict |
|---|---|
| constant importance | ✅ already expired — `compose_situation_importance`, `importance_source` in metadata, a named fallback |
| ⛔ empty relationships / dependencies | **TRUE.** `context/situation_bso.py` is **2,133 lines** and mentions `relationships` **0 times** and `dependencies` **0 times** — against `evidence` 66, `anchor` 55, `entities` 7. ✅ But **declared twice**: `contracts/situation.py`'s GAP FLAG and `contracts/dependency.py`, both naming the X8 cutover |
| ✅ *"0 derived facts"* | **CLOSED.** `context/conversion.py` is the census built for exactly that number — *"the number that was not anywhere"* — and it has a **writer** (both correlators call `record_conversion`), a **reader** (`runner.py:1400`), and a test |

⛔ **This was the one I expected to find unread**, on the pattern of L6's four ledgers and
`reset.latest_reset_at`. It is read. The prediction was wrong and the module is better than the
scorecard row implied.

---

# PART 3 · L2-04 — the views, and a count with no list behind it

⛔⛔ **My first reading of this row was wrong twice, and both mistakes came from the same habit.**

| my first reading | ⛔ what measuring properly showed |
|---|---|
| "all four absent" | **`authority` is built** — `context/authority_view.py`, `L2.1.4`, three stated laws, and imported in production by `context/patterns/store.py`. So it is a surface, not a draft |
| "ownership absent" | the **data** is written: `commitment.owner` is a fact, and `context/pipeline.py:1948` records why it had to become one — `executive/assignment.resolve_owner` **cannot see edges**, so ownership sat in the graph unreadable at the one point that needed it and *"all 43 cards carry `assignee = NULL`"*. What is absent is the **surface**, which the same file calls *"the distinction an ownership surface is built out of"* |
| "`projections.py` covers this" | ⛔ no — it holds **domain lenses** (the Sales/Support/HR cut of one graph) and answers none of the four questions |

**Both mistakes were module filenames read as evidence.** *A name that is not distinctive is not
evidence* — the rule the `reason/` audit produced, and I broke it on the next claim.

### ⛔ The finding nobody was looking for

`authority_view.py` opened with: *"**The eighth view over the one graph**, and the only one that
was missing entirely."*

**Nothing in the repository enumerates eight views.** The phrase appeared **exactly once**,
engine-wide; `L2.1.4` is the only view-numbered module in `context/`; the list is in doc 01, which
is not in the repo. ⛔ So the ordinal cannot be checked from here, and a reader who tried would
conclude seven siblings existed somewhere. **The line is now attributed instead of counted**, and
two tests hold it that way — one on the file, one across the whole engine, because a second copy of
an uncheckable number is the same defect in a new place.

### ⛔⛔ And then my own declaration falsified its own measurement

The `use_restriction` entry said the term *"appears in **0 files** engine-wide."* Writing that
sentence **put the term in a file**. The new test caught it immediately:

```
AssertionError: `use_restriction` now appears in ['authority_view.py']
```

*The observer can alter what it measures.* The count now reads **"0 files engine-wide other than
this declaration"**, the qualifier is itself asserted, and the entry explains why it is
load-bearing — a later count of 1 is the declaration, not a surface.

### What goes to Rohit

⛔ **Three new read surfaces is a roadmap decision, not a unit this programme may mint for
itself.** Every absent entry carries `Rohit's` in its mover, and a test asserts it does.

---

# PART 4 · ELEVEN CORRECTIONS, EACH WITH WHAT CAUGHT IT

⛔ Nine are to my own first reading. The list is the audit — a step that produced two receipts and
eleven corrections learned more from the corrections.

| # | the claim I was about to make | ⛔ what was actually true | what caught it |
|---|---|---|---|
| 1 | *"`AuthorityBasis` is computed and thrown away"* | **persisted** at `capture/pipeline.py:1685` | reading the CALLER, not just the function that returns it |
| 2 | *"two call sites disagree about `domain_ids`' arity"* | ⛔ **unfair.** `citations.py` builds a TAG SET where taking all is right; routing takes one, also right. The defect is that the pick is **silent** | reading what the other site DOES with the value |
| 3 | *"the only writer emits ≤1 domain, so `[0]` is safe"* | ⛔⛔ **WRONG — there is a SECOND writer.** `packs/compiler/expertise_builder.py:87` writes `plan.domain_ids`, which is `tuple(sorted(selected_domains))` over a **set**. Multi-valued by construction | grepping every spelling of the key instead of the first one found |
| 4 | *"`ExpertisePackage._NON_CONTENT_METADATA` proves the key survives"* | ⛔⛔ **WRONG CLASS.** That attribute belongs to `SituationCandidate`, 300 lines earlier in the same file. The real filter is `addressable_metadata` over `OBSERVATION_METADATA_KEYS` | the receipt builder raised `AttributeError` on first run |
| 5 | *"three of L2-04's four views are absent"* | ⛔ `authority` is built and imported in production | measuring the concept, not the filename |
| 6 | *"ownership is absent"* | ⛔ the **data** is written; the **surface** is not | reading `context/pipeline.py`'s own comments |
| 7 | *"the eighth view over the one graph"* (inherited) | ⛔ **uncheckable** — no list anywhere | grepping the phrase engine-wide: 1 hit |
| 8 | my guard: `assert len(why) > 80` | ⛔ measures **length**, not content. A reason could be 90 characters of nothing | **a surviving mutation** |
| 9 | my guard: `any(token in state for token in (…))` | ⛔ an OR over a hand-listed set — an entry citing the WRONG module would pass | **a mutation that did not do what its label said** |
| 10 | my declaration: *"0 files engine-wide"* | ⛔⛔ **false the moment it was written** | the test I wrote for it, on its first run |
| 11 | my own `f"…MAX_AUTHORITY_RANK…"` | ⛔ an f-string with **no placeholder** — it *looked* interpolated and was a literal | re-reading my own diff |

### ⛔ Two mutations were invalid, and saying so is the discipline

| | |
|---|---|
| **M17** | mutated the **test's own** assertion threshold. A test cannot catch a weakening of itself — invalid **by construction**, not a survivor. Re-run as **M17b** against the SOURCE (emptying the declaration table): **CAUGHT, 10 failures** |
| **M9** | its label said *"an absent grade cites no measurement"* but it stripped the **reasoning** and left the **citation** standing. Invalid by its own label. ⛔ It still exposed a real weakness (#9 above), which is why an invalid mutation is read rather than discarded. Re-run as **M9b**: **CAUGHT** |

And two anchors matched **0×** (my mutation text did not match the file's line wrapping) — reported,
retried with the real text, caught.

---

# PART 5 · WHAT EACH UNIT LEFT BEHIND

| unit | code | tests | mutations |
|---|---|---|---|
| **U01** L2-11 | receipt 45 · `_MULTI_DOMAIN_ROUTED_PACKAGE_SQL` with two refusals · a `RECEIPT_PACKAGE` declaration | 18 | **13 caught · 0 survived** |
| **U02** L2-01 | receipt 46 · `_MIXED_AUTHORITY_SCALE_SQL` · `UNINTERPRETABLE_RANKS` (4 entries, both-ways) | 20 | **22 caught · 0 survived · 1 invalid** |
| **U03** L2-04 | `ATLAS_L2_04_VIEWS` (4 entries, both-ways) · the attribution correction | 12 | **14 caught · 0 survived · 1 invalid** |
| **U04** paperwork | 5 scorecard rows + the summary paragraph, which had two struck items | — | — |

### ⛔ Both receipts refuse rather than going green by themselves

This is the failure mode that has now bitten this programme twice, so each builder names the one
change that would make it always-green and **refuses**:

| receipt | the always-green failure, guarded |
|---|---|
| **45** | `domain_ids` joining `OBSERVATION_METADATA_KEYS` → the key is stripped from the stored payload, the column is absent, the count is 0 for ever |
| **45** | `RoutePlan` losing the field, or ceasing to be a dataclass. ⛔ The second was found by my own test failing with `TypeError: must be called with a dataclass type or instance` — a message that names no claim |
| **46** | nothing off-ladder left in `UNINTERPRETABLE_RANKS` → the `> top` half can never match |

---

# PART 6 · THE NINE, SETTLED

| claim | state after 2.1 |
|---|---|
| **L2-01** | ⛔ located · **receipt 46** + `UNINTERPRETABLE_RANKS` · the two numbers are **Rohit's** |
| **L2-02** | Rohit's — the mover is `H8.5`, a read-only query already on Harsh's page |
| **L2-03** | ✅ **EXPIRED** — closed in code, both directions, with a test |
| **L2-04** | ⚠️ partly expired · declared · three surfaces are **Rohit's** |
| **L2-05** | Rohit's — `unit_health.py` already calls it *ONE ROOT, FOURTEEN SYMPTOMS* |
| **L2-07** | Rohit's — the ConfidenceVector axes, open since `02-DECISIONS` #1 |
| **L2-09** | ✅ measured · the census half is CLOSED · the v1 half is **declared twice** |
| **L2-11** | ⛔ located · **receipt 45** |
| **L2-12** | Rohit's — a tenant replay is a reprocessing-cost decision, not a missing function |

```
9 claims · 1 expired · 2 located with a receipt · 1 partly expired · 1 measured · 4 Rohit's
⛔ 0 unmeasured
```

---

# DOCTRINE THIS STEP PRODUCED

| rule |
|---|
| ⛔⛔ **a declaration can falsify its own measurement** — writing "0 files" puts the word in a file |
| ⛔⛔ **two `to_semantic_dict` methods in one module make the right-looking name the wrong object** |
| ⛔ **`len(why) > 80` measures length, not content** — hold a reason to naming its own evidence, derived |
| ⛔ **a citation that does not resolve is worse than none** — it reads as a measurement somebody took |
| ⛔ **an OR over a hand-listed token set is not a check** — an entry citing the wrong thing passes |
| ⛔ **a test cannot catch a weakening of itself** — mutate the SOURCE, or the mutation is invalid |
| ⛔ **an invalid mutation is read, not discarded** — M9 did not do what its label said and still found a real hole |
| ⛔ **a law enforced at the write is invisible at the read** — `resolve_person_name` is one line and looks like a lie |
| ⛔ **an f-string with no placeholder looks interpolated and is a literal** |
| ⛔ **grep every spelling of a key, not the first one found** — the second writer was the one that mattered |
| ⛔ **a comment's count ages faster than its claim** — *"what the four writers already stamp"*, and there are eight callers |
