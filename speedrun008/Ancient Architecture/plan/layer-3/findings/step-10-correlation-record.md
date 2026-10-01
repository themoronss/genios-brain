# L3-10 · The correlation decision record — findings

**Run:** 2026-09-25 · premise checked before any code · ⛔ **no migration — the plan was wrong again**

---

## 1. ⛔ Eighth premise wrong — the record exists, and its design is better than the spec's

The plan said:

> *"There is no correlation decision record. 'A candidate rejected for the wrong audit period and
> a candidate not retrieved at all are different failures' — **today they are the same failure:
> silence.** Grep finds reason codes in exactly two modules."*

**`context/residue.py` is the record**, and it answers the question from the other end.

| | the spec's design | what exists |
|---|---|---|
| shape | a **LOG** of rejected candidates | ⛔ **CURRENT STATE** — "still unexplained as of the last sweep" |
| growth | unbounded; needs retention **and a permissions policy of its own** | **cannot exceed the size of the graph, and shrinks as coverage improves** |
| lifecycle | append | ⛔ **the row is DELETED when a reading finally covers the subject** |
| age | a timestamp per attempt | `first_seen_at`, never updated — *"how long a thing has gone unexplained is the number that makes this a work queue"* |

⛔ **The spec itself warns about its own design** — *"rejected and unresolved candidates need
bounded audit retention… respect source permissions and deletion requirements rather than storing
unrestricted copies."* **Residue solves that by construction.**

Four kinds, each a checkable join: evidence held and never spoken about; the founder's own case
(*"they replied, we went quiet, nothing said so"*); an ask still open and attached to nothing; and
Layer 1 verdicts no Layer 2 reading consumes.

### 1.1 · And truncation was already reported

CC-30 / FX-13's *"a top-k result treated as an exhaustive search"* is handled in both places that
cap: `campaign_candidates` (*"a cost ceiling, not a sample. A truncated pass reports that it
truncated"*) and `correlation_timeline` (*"returns whether the cap CUT anything, so the drain can
say so"*). Residue tracks it per kind.

---

## 2. What was actually missing — the four kinds were not a vocabulary

Four bare string constants. **No collection, no guard.**

⛔ **And for this table the failure direction is one-way.** A kind that silently stops being
recorded makes the sweep look **more complete than it is**: nothing goes red, no row appears, and
*"what is happening in my mailbox that this thing never mentioned"* quietly starts answering
*"nothing"*.

`RESIDUE_KINDS` now closes it, guarded both ways — declared ⟷ recorded — read from the source
rather than assumed.

### 2.1 · And correlation's stated limitation is now pinned

`correlation.py` declares this honestly and **nothing guarded it**:

> *"Two independent deals with the same company, with no CRM connected, correlate into one
> situation… **Guessing the split from wording would be exactly the over-correlation this module
> refuses to do.**"*

That is BS-07, CC-26 and INT-08's case. ⛔ **The tempting fix — split them by subject similarity —
is the one the module exists to refuse, and it would look like an improvement**: more situations,
finer granularity. The governing principle one line up is what makes it wrong: *"wrongly MERGING
two situations builds a chimera and reasons about it at full confidence."* Both are pinned.

---

## 3. ⛔ A docstring that is not literally true, said out loud instead of repeated

`residue.py` opens with *"no model, no clock of its own."*

**The model half is exactly true.** The clock half is not: `now = eval_time or datetime.now(...)` —
a **defaulted** clock, not an absent one.

⛔ **The test pins the property rather than the sentence:** `eval_time` is a parameter, and the
production caller passes it, so a replay can pin the instant and the fallback is reachable only
from a direct call. **A test asserting "no clock" would have been asserting a sentence.**

---

## 4. Three of my own test bugs in one step

| | |
|---|---|
| the `first_seen_at` slice matched **the comment explaining the rule** | comments stripped before scanning the SQL |
| the banned-token scan hit the **fallback clock**, which is real | rewritten to pin the parameter, and to say the docstring overstates |
| a prose assertion **spanned a wrapped line** and failed against correct text | whitespace normalised — *"any assertion about documented reasoning has to be reflow-proof or it pins the line width"* |

**Eighth, ninth and tenth in the same family.** Every one: an assertion about text rather than about
the thing the text describes.

---

## 5. Result

```
FULL SUITE   13,244 passed · 1,061 skipped · 152 xfailed · 14 failed
                                                          └── all 14 pre-existing
before L3-10: 13,237 passed · 14 failed
```

**+7 tests · 0 regressions · no migration · no model call. ⛔ Wave 3 complete.**

**Technique 3 — five mutations, all red:** a kind stops being recorded; a kind declared and never
recorded; `first_seen_at` refreshed; a capped pass stops saying so; the refusal removed from
correlation's docstring.

## 6. What this step does NOT do

* ⛔ **It does not build a rejection log.** Residue answers the same question with bounded growth
  and no retention policy of its own. **Eighth "already built" in this layer.**
* **It does not split two deals at one company.** That limitation is declared, and now guarded so it
  cannot be "fixed" into a chimera.
