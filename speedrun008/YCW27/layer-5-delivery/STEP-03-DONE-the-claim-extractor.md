# L5 STEP 03 · `M13.C1.U01` — the claim extractor · **DONE**

## What was there

A card's rendered copy is **one block of text**. Inside it, *"They wrote four days ago"*, *"this
deal is at risk"* and *"you should reply today"* are three completely different kinds of statement
— one lifted from a source, one concluded, one an instruction — and the reader has no way to tell
which is which.

⛔ **The vocabulary already existed.** `contracts/claim_state.py` defines
`OBSERVED / INFERRED / HYPOTHESISED / ENVELOPE` with `_MODEL_MAY_WRITE`. It classifies **fields**;
this classifies **sentences**. So the unit is real, at a different granularity, and it **reuses**
the enum: two spellings of one idea disagree the first time one is extended, which is what
`FEATURE_CARDS_FROM_SITUATIONS` cost this exact package.

## What was built

`deliver/claims.py` — `split_sentences`, `classify`, `extract`, `by_state`, `Claim`, `HEDGES`.
**Pure. No model.** §4: *"if the output is a number, a route or a permission, no model produces
it"* — a claim tag decides what the validator will demand of a sentence, which makes it a
permission.

## The precedence, and why it is this order

1. **An instruction or a question is `ENVELOPE` before anything else is asked.** *"Send the deck
   today"* contains no assertion to ground. Running it through the evidence rules would either
   refuse a correct instruction or — worse — pass it and record that an instruction was *observed*,
   which would then let the validator demand a citation for a sentence that never claimed anything.
2. ⛔ **A hedge outranks being grounded.** *"They will probably churn"* invents no number and no
   name, and it is not an observation. Letting grounding win here is precisely how a guess acquires
   a fact's authority — which `claim_state` forbids: a hypothesis is *"never rendered as fact"*.
3. **Grounded and quoting is `OBSERVED`**; grounded without a quote is `INFERRED` — the parts are
   real, the sentence assembling them is ours.
4. ⛔ **Anything ungrounded is `INFERRED`, not `HYPOTHESISED`.** An unhedged sentence asserting an
   invented number is not a modest proposal, it is a false claim, and tagging it as a hypothesis
   would route it to the rules written to be **lenient** with hypotheses. A wrong tag is not
   neutral here: it selects the check.

## Two details that are not cosmetic

**The sentence split stops at `.`/`?`/`!` only before whitespace.** Splitting on every period cuts
`4.5x` in half and `nikhil@addis.im` into three, and the validator then refuses the card for
numbers it broke itself.

**The grounding helpers are the renderer's own** — `_digit_runs`, `_fold`, `_haystack`,
`_proper_nouns`, imported, never reimplemented. Those folding rules exist because of measured
failures (`V-02:name:Sofa` against a graph holding *"Sofía Padrón"*). Two copies would give the
card two answers to *"is this name in the corpus"* the first time one was improved.

## Is this a blunt grep?

⛔ **No, and the distinction matters.** The family rule is *"assert on structure — the AST, the
column list — never on text that happens to sit near a thing."* It forbids inferring a fact about
**code** from words near it. Here the text **is** the subject: a sentence's hedging is what makes
it a hypothesis, not a proxy for something else. Applying the rule here would forbid the only
honest method there is.
