# L1.5 — Validation and Normalization (Stage S3)

> **This is where GeniOS becomes trustworthy.** S2 produced understanding. S3 decides
> whether that understanding is true, makes it machine-usable, and refuses to let a
> single confident model output become fact without a receipt.

**Group responsibility:** make the model's understanding **verified, normalized and
comparable**.

**Group law:** *NO LLM in this group. Every unit is a pure function.*

**Package:** `genios_engine/capture/validate/`
**Input:** `ExtractionResult` (C-09) + `PreparedContent`
**Output:** validated `ExtractionResult` + `list[Conflict]` + `confidence_vector`
**LLM sites:** **zero**. If a reviewer sees an LLM import in this package, reject the PR.

---

## Component map

| # | Component | ALG | Units | Wave | Status |
|---|---|---|---|---|---|
| L1.5.0 | **Claim Group Assembler** | ALG-22, ALG-23 | 2 | W5 | 🆕 **NEW — prerequisite for conflict detection** |
| L1.5.1 | **Evidence Span Validator** | ALG-08 | 2 | W1 | NEW — highest priority |
| L1.5.2 | **Date/Time Normalizer** | ALG-09 | 3 | W1 | NEW |
| L1.5.3 | **Currency Normalizer** | ALG-10 | 2 | W1 | NEW |
| L1.5.4 | Entity Canonicalizer | ALG-11 | 2 | W2 | partial exists |
| L1.5.5 | **Conflict Detector** | ALG-12 | 3 | W5 | NEW |
| L1.5.6 | Schema Validator | — | 1 | W1 | partial exists |
| L1.5.7 | **Confidence Composer** | ALG-13 | 2 | W1 | partial exists |
| L1.5.8 | Authority Weighter | ALG-14 | 1 | W2 | partial exists |

**Why W1 for most of this group:** these are pure functions with no dependencies. They
can be built and fully tested before a single LLM call exists. Build them first — they
are the cheapest units in Layer 1 and the ones everything else leans on.

---

# L1.5.0 · Claim Group Assembler (ALG-22, ALG-23)

> **This component was missing from the first draft and its absence was a real defect:
> without it, the conflict detector could not have caught the founder's own worked
> example.**

### L1.5.0-U1 · Subject key derivation (ALG-22)

**WHAT** — Computes a stable `subject_key` identifying *what a claim is about*.

**WHY** — Conflict detection compares claims about the **same thing**. Signal lifecycle
supersedes signals about the **same thing**. Both were specified against a `subject_key`
that was never defined — which makes both unimplementable.

**WHERE** — `genios_engine/capture/validate/subject.py`

**HOW** (ALG-22) — ordered cascade, first match wins:
```
1. structured id     "hubspot:deal:12345", "stripe:subscription:sub_abc"
                     -> subject_key = f"{source}:{object_type}:{external_id}"
2. document identity "contract:aws-enterprise-agreement"
                     -> from document_register.py, already exists
3. named entity      canonical entity + field family
                     -> f"entity:{canonical_hint}:{field_family}"
4. thread            f"thread:{thread_group_key}"
5. fallback          f"event:{event_id}"     (a claim about nothing else groups alone)
```

`subject_key` is **deterministic and stable across runs**. It is not an id we mint; it
is derived, so the same real-world subject produces the same key from any event that
mentions it.

**LLM** — no. **STORAGE** — pure.

### L1.5.0-U2 · Claim group assembly (ALG-23) — **the defect fix**

**WHAT** — Gathers every claim that should be compared with every other claim, **across
events**.

**WHY — this is the fix.** The first draft specified conflict detection as *"group all
claims across the event's extractions"*. But `capture/connectors/composio.py:383` is
explicit:

> *"One Gmail message → `[email_message]` + one `[email_attachment]` per file."*

**They are separate events.** So an email claiming \$84K and its attached signed PDF
claiming \$74K would have been in two different groups and **never compared** — the
exact scenario this whole component exists to catch would have slipped through.

**HOW** (ALG-23) — the grouping key is the **document group**, not the event:
```
thread_group_key = walk parent_object_id upward to the root
                   attachment --parent--> email --parent--> thread
                   (composio.py:499 "links the file back to its email"; :452 -> thread)

claim_group = all claims where
                subject_key matches
              OR thread_group_key matches AND field family matches

WINDOW:  claims within the same thread_group_key, unbounded in time
         (a contract amendment six months later must still conflict with the original)
         PLUS claims sharing a structured subject_key, unbounded
```

**Both linkage keys already exist in the data.** `parent_object_id` is populated by the
Gmail connector for attachment→email and email→thread. This unit walks that chain; it
does not need new ingestion work.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Group too wide | false conflicts across unrelated deals | subject_key must match, not merely the thread |
| Group too narrow | **the founder's example is missed** | thread_group_key walks the full parent chain — tested explicitly |
| Parent chain broken (forwarded attachment) | attachment orphaned | fall back to document identity (ALG-22 rule 2), then to `event:` |
| Very long thread | group grows unbounded | cap at 500 claims per group; beyond that, most-recent-500 by authority rank |

**ACCEPTANCE**
```
pytest tests/capture/validate/test_claim_group.py -q
```
**The required fixture — this is the acceptance test for the whole component:**
an `email_message` claiming \$84K plus its `email_attachment` (a signed PDF) claiming
\$74K, ingested as two separate events, **land in one claim group** and produce one
`Conflict`.

Plus: two unrelated deals in the same thread do **not** merge; a forwarded attachment
with a broken parent chain falls back to document identity; a 600-claim thread caps at 500.

**REVERSE PROMPT**
```
TASK: Build the claim group assembler. This is the prerequisite for conflict detection.

THE DEFECT THIS FIXES: conflict detection must compare claims ACROSS EVENTS.
capture/connectors/composio.py:383 emits "One Gmail message -> [email_message] + one
[email_attachment] per file" — SEPARATE events. So an email saying $84K and its attached
signed PDF saying $74K are two events. Grouping by event would never compare them, and
that is precisely the case conflict detection exists to catch.

FILE: genios_engine/capture/validate/subject.py

Implement:
  def subject_key(claim, extraction, event) -> str
      # ordered cascade, doc 05 L1.5.0-U1, first match wins

  def thread_group_key(event, event_lookup) -> str
      # walk parent_object_id upward to the root.
      # attachment --parent--> email --parent--> thread
      # parent_object_id is ALREADY populated: composio.py:499 and :452

  def assemble_claim_groups(claims, events) -> dict[str, list[NormalizedClaim]]
      # group by subject_key, OR by (thread_group_key + field family)
      # window: unbounded in time — a contract amendment six months later must still
      #         conflict with the original
      # cap 500 claims per group, keeping highest authority_rank first

HARD RULES:
1. subject_key is DERIVED and STABLE, never minted. The same real-world subject must
   produce the same key from any event that mentions it. Add a test proving two
   different events about the same HubSpot deal produce an identical subject_key.
2. PURE. event_lookup is injected as a callable, not a DB handle.
3. Broken parent chain -> fall back to document identity, then to f"event:{event_id}".
   Never raise.

TEST tests/capture/validate/test_claim_group.py — MUST include the headline fixture:
  an email_message claiming $84K and its email_attachment claiming $74K, as two separate
  events, land in ONE group.
Plus: unrelated deals in one thread do not merge; broken chain falls back; 600 claims
cap at 500 by authority rank.
```

---

# L1.5.1 · Evidence Span Validator (ALG-08)

> **The single most important new unit in Layer 1.** It is the difference between
> "the AI said so" and "here is the sentence."

### L1.5.1-U1 · Span resolution

**WHAT** — Confirms that every `EvidenceSpan.quote` appears byte-for-byte in the source
text at the stated offsets.

**WHY** — Without this, a hallucinated quote is indistinguishable from a real one, and
every downstream "receipt" is theatre. This unit is what makes Globe Rule 04
(*confidence without receipts is a guess*) enforceable rather than aspirational.

**WHERE** — `genios_engine/capture/validate/spans.py`

**WHEN** — W1. No dependencies beyond contracts.

**HOW** (ALG-08)
```
def verify_span(span: EvidenceSpan, source_text: str) -> SpanVerdict:

    1. BOUNDS      if end > len(source) or start < 0 or end <= start
                       -> INVALID_BOUNDS
    2. EXACT       actual = source[span.start_offset : span.end_offset]
                   if actual == span.quote                -> VERIFIED
    3. WHITESPACE  if normalize_ws(actual) == normalize_ws(span.quote)
                       -> VERIFIED_WHITESPACE   (offsets corrected, span rewritten)
    4. RELOCATE    idx = source.find(span.quote)
                   if idx >= 0  -> VERIFIED_RELOCATED  (offsets corrected)
                                   confidence_bp = conf * 9 // 10
    5. FUZZY       if normalize_ws(span.quote) in normalize_ws(source)
                       -> VERIFIED_FUZZY
                          confidence_bp = conf * 7 // 10
    6. otherwise   -> UNVERIFIED   (the quote is not in the source at all)
```

**Step 6 is the hallucination catch.** A quote that cannot be found anywhere in the
source means the model invented the sentence it claims to be citing.

**Policy on UNVERIFIED** — deliberately graded, not binary:

| Claim type | Action on UNVERIFIED |
|---|---|
| `Money` | **DROP the claim.** A fabricated amount is worse than a missing one. |
| `ResolvedDate` | **DROP the claim.** Same reason — a wrong deadline is acted on. |
| `Commitment`, `DecisionState`, `Dependency` | keep, `confidence_bp * 5 // 10`, flag `unverified` |
| `UnclassifiedObservation` | keep, flag — the open lane is for review, not for rules |
| `intent`, `stance`, `topics` | keep — these are summary judgements, not citations |

**LLM** — no. **EMBEDDINGS** — no. Exact and whitespace-normalized matching only;
a fuzzy semantic match would defeat the entire purpose of the unit.

**STORAGE** — pure. Writes nothing. Returns verdicts.

**INPUT** — `EvidenceSpan`, `source_text: str`
**OUTPUT** — `SpanVerdict` enum + corrected span

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Offsets computed against masked text | every span UNVERIFIED | L1.4.6-U2 aligns offsets first; this unit runs after |
| Source text mutated after extraction | mass UNVERIFIED | validate against the same `prepared_content` version the extraction used |
| Model paraphrases instead of quoting | UNVERIFIED | prompt Block 5 + this unit's rejection; monitored as `unverified_rate` |
| Unicode normalization differences | false UNVERIFIED | NFC-normalize both sides before comparison |

**ACCEPTANCE**
```
pytest tests/capture/validate/test_spans.py -q
```
Required table rows:
- exact match -> VERIFIED
- extra whitespace -> VERIFIED_WHITESPACE, offsets corrected
- correct quote, wrong offsets -> VERIFIED_RELOCATED, confidence reduced
- quote absent from source -> UNVERIFIED
- a `Money` claim with an UNVERIFIED span is **dropped**
- a `Commitment` with an UNVERIFIED span **survives** at half confidence
- unicode: "café" NFC vs NFD -> VERIFIED

**REVERSE PROMPT**
```
TASK: Build the evidence span validator. This is L1's anti-hallucination unit.
FILE: genios_engine/capture/validate/spans.py

Implement:
  class SpanVerdict(str, Enum):
      VERIFIED, VERIFIED_WHITESPACE, VERIFIED_RELOCATED, VERIFIED_FUZZY,
      UNVERIFIED, INVALID_BOUNDS

  def verify_span(span: EvidenceSpan, source_text: str) -> tuple[SpanVerdict, EvidenceSpan]
  def apply_verdicts(result: ExtractionResult, source_text: str)
        -> tuple[ExtractionResult, dict[str, int]]   # result + counters

Algorithm: the 6 ordered steps in doc 05 section L1.5.1-U1. Follow the order exactly;
each step is cheaper than the next.

DROP POLICY (implement exactly, this is a safety rule):
  Money        -> DROP on UNVERIFIED
  ResolvedDate -> DROP on UNVERIFIED
  Commitment / DecisionState / Dependency -> keep, confidence_bp = conf * 5 // 10,
                                              set verified=False
  UnclassifiedObservation -> keep, set verified=False
  intent / stance / topics -> untouched (not citation-bearing)

RULES:
- PURE. No DB, no network, no LLM, no clock.
- Integer math only for confidence. Use `conf * 9 // 10`, never `conf * 0.9`.
- NFC-normalize both strings before any comparison (unicodedata.normalize).
- NEVER use fuzzy string similarity, edit distance, or embeddings. If a quote is not
  literally present after whitespace normalization, it is UNVERIFIED. Semantic matching
  here would defeat the entire purpose of the unit.

TEST tests/capture/validate/test_spans.py — table-driven, one row per bullet in the
ACCEPTANCE list of doc 05 L1.5.1-U1, plus:
  - empty source text
  - span longer than source
  - negative offsets
  - a quote appearing twice in the source (first occurrence wins, deterministically)

ACCEPTANCE: pytest tests/capture/validate/test_spans.py -q  -> pass, 0 skips
```

### L1.5.1-U2 · Unverified-rate monitor

**WHAT** — Emits `unverified_rate` per org per prompt version.

**WHY** — A rising rate is the earliest signal that a prompt change broke citation
behaviour. It is a release gate: a new prompt version whose unverified rate exceeds the
previous by more than 5 percentage points does not ship.

**STORAGE** — counter into `llm_costs`-adjacent metrics table.

---

# L1.5.2 · Date/Time Normalizer (ALG-09)

### L1.5.2-U1 · Relative date resolution

**WHAT** — Turns `"pretty soon"`, `"next week"`, `"by Friday"`, `"end of Q3"` into a
`ResolvedDate` with an explicit certainty.

**WHY** — *"Our renewal is coming up pretty soon"* is worthless as a string and
dangerous as a fabricated timestamp. The deadline-proximity term of the importance
formula (ALG-17) needs a range; inventing a point value invents urgency.

**WHERE** — `genios_engine/capture/validate/dates.py`

**HOW** (ALG-09) — ordered rule cascade against an explicit `eval_time`:

| # | Pattern | earliest | latest | certainty |
|---|---|---|---|---|
| 1 | ISO / explicit date | that date | same | `EXACT` |
| 2 | "October 15" (no year) | next occurrence >= eval_time | same | `EXACT` |
| 3 | weekday name ("Friday") | next such weekday | same | `EXACT` |
| 4 | "tomorrow" / "today" | computed | same | `EXACT` |
| 5 | "next week" | next Mon | next Sun | `RANGE` |
| 6 | "this week" | eval_time | coming Sun | `RANGE` |
| 7 | "end of month/quarter" | last 3 days of period | period end | `RANGE` |
| 8 | "in N days/weeks/months" | computed | computed | `EXACT` if N given |
| 9 | "soon" / "shortly" / "pretty soon" | eval_time | eval_time + 14d | `RELATIVE` |
| 10 | "later" / "sometime" / "down the line" | eval_time | eval_time + 90d | `RELATIVE` |
| 11 | no match | None | None | `UNRESOLVED` |

**Non-negotiable design points:**
- `eval_time` is an **explicit parameter**, never `datetime.now()`. Replay of a March
  event must resolve "next week" against March.
- `resolved_against` is stored on the `ResolvedDate` so the resolution is auditable.
- Rows 9 and 10 windows are **heuristics and are labelled as such** by
  `certainty=RELATIVE`. Downstream must never treat a RELATIVE range as a deadline.
- Timezone: resolve in the **org's** timezone, not UTC, not the server's. Store UTC.

**LLM** — no. The model already emitted the phrase in `as_written`; converting a phrase
to a range is arithmetic.

**FAILURE MODES**

| Failure | Mitigation |
|---|---|
| Ambiguous "next Friday" (this week's or next?) | rule 3 = next occurrence strictly after eval_time; documented and tested |
| Locale date order (03/04 = Mar 4 or Apr 3) | require an explicit locale from the connection; if unknown -> `UNRESOLVED`, never guess |
| Past date in an active message | resolve as written, flag `date_in_past` — do not silently roll forward |
| DST boundary | resolve in org tz, store UTC, test the boundary explicitly |

**ACCEPTANCE**
```
pytest tests/capture/validate/test_dates.py -q
```
Required rows: every one of the 11 cascade rows, plus DST boundary, plus
locale-unknown -> UNRESOLVED, plus the same input at two different `eval_time` values
producing two different answers (proves no hidden clock).

### L1.5.2-U2 · Duration and recurrence

**WHAT** — `"every quarter"`, `"annual"`, `"30 days notice"` -> structured recurrence /
duration.

**WHY** — Contract renewal notice periods are duration expressions. A renewal date
without its notice period gives the founder the wrong deadline.

### L1.5.2-U3 · Business-day arithmetic

**WHAT** — `"in 5 business days"` respecting weekends and the org's holiday calendar.

**WHY** — "5 business days" is 7 calendar days at minimum, more across a holiday.
Getting this wrong makes every compliance deadline wrong.

**REVERSE PROMPT**
```
TASK: Build the date/time normalizer.
FILE: genios_engine/capture/validate/dates.py

Implement:
  def resolve_date(as_written: str, *, eval_time: datetime, tz: str,
                   locale: str | None) -> ResolvedDate

ALGORITHM: the ordered 11-row cascade in doc 05 L1.5.2-U1. First match wins.

HARD RULES:
1. eval_time is an EXPLICIT parameter. This module must never call datetime.now(),
   date.today(), or read a clock in any way. Add a test that greps the module source
   for "now()" and fails if found.
2. Resolve in the org timezone `tz`, store UTC in earliest/latest.
3. Set resolved_against = eval_time on every returned ResolvedDate.
4. certainty must be EXACT only when earliest == latest.
5. If locale is None and the string is an ambiguous numeric date (03/04/2026),
   return UNRESOLVED. Never guess day/month order.
6. A resolved date earlier than eval_time is returned as-is with a `date_in_past`
   flag on the object. Do NOT roll it forward.

ALSO implement:
  def resolve_duration(as_written: str) -> timedelta | None      # "30 days notice"
  def resolve_recurrence(as_written: str) -> str | None          # "annual" -> RRULE-ish
  def add_business_days(start: datetime, n: int, holidays: frozenset[date]) -> datetime

TEST tests/capture/validate/test_dates.py:
  - one row per cascade rule
  - "next Friday" on a Wednesday and on a Saturday -> different, documented answers
  - same input, two different eval_time values -> two different outputs
  - DST spring-forward and fall-back boundaries
  - locale=None + "03/04/2026" -> UNRESOLVED
  - a past date keeps its date and sets date_in_past
  - source-grep test: module contains no "now()" / "today()"

PURE. No DB, no network, no LLM.
ACCEPTANCE: pytest tests/capture/validate/test_dates.py -q -> pass, 0 skips
```

---

# L1.5.3 · Currency Normalizer (ALG-10)

### L1.5.3-U1 · Amount parsing

**WHAT** — `"$84K"`, `"USD 84,000"`, `"₹84,00,000"`, `"84k"` -> `Money`.

**WHY** — The Globe worked fault is literally this: *"card said \$84K but contract is
\$8.4K — a locale decimal-separator bug"*. Every layer above faithfully propagated a
wrong number because nothing normalized it once, at the source.

**WHERE** — `genios_engine/capture/validate/money.py`

**HOW** (ALG-10)
```
1. SYMBOL/CODE   detect currency from symbol ($, €, £, ₹) or ISO code
                 ambiguous "$" -> use the connection's declared locale
                 still ambiguous -> currency = "UNKNOWN", DO NOT DEFAULT TO USD
2. SEPARATORS    strip thousands separators using the LOCALE's convention:
                   en-US: 84,000.50   ->  84000.50
                   de-DE: 84.000,50   ->  84000.50
                   en-IN: 84,00,000   ->  8400000     (lakh grouping)
                 if locale unknown and the string is ambiguous -> return None
3. MULTIPLIER    k/K = 1e3, m/M/mn = 1e6, bn = 1e9, lakh = 1e5, crore = 1e7
4. MINOR UNITS   multiply by the currency's minor-unit exponent (USD 2, JPY 0, KWD 3)
                 result is int; NEVER float at any point
5. RANGE CHECK   reject > 1e15 minor units as a parse error, not a real amount
```

**Step 2 is the actual fix for the \$84K/\$8.4K class of bug** — and note that the
answer to an ambiguous case is `None`, not a guess.

**LLM** — no. **EMBEDDINGS** — no. **STORAGE** — pure.

**FAILURE MODES**

| Failure | Mitigation |
|---|---|
| `$` with unknown locale (USD? CAD? AUD?) | `currency="UNKNOWN"`, retained, surfaced — never defaulted |
| Indian lakh/crore grouping | explicit en-IN branch, tested |
| Float precision | integer arithmetic end to end; a test asserts no float appears |
| "84" with no currency at all | not a `Money` — stays a bare number in `structural_tokens` |

**ACCEPTANCE**
```
pytest tests/capture/validate/test_money.py -q
```
Required: `$84K` -> 8_400_000 USD; `$8.4K` -> 840_000 USD (**the two must never
collide**); `84.000,50 EUR` de-DE -> 8_400_050 EUR; `₹84,00,000` en-IN -> 840_000_000
INR; `¥84000` -> 84_000 JPY (0 minor exponent); ambiguous `$84` with no locale ->
currency `UNKNOWN`; no float anywhere in the module (source-grep test).

**REVERSE PROMPT**
```
TASK: Build the currency/quantity normalizer.
FILE: genios_engine/capture/validate/money.py

Implement:
  def parse_money(as_written: str, *, locale: str | None) -> Money | None

ALGORITHM: the 5 ordered steps in doc 05 L1.5.3-U1.

HARD RULES:
1. INTEGER MATH ONLY. No float appears anywhere in this module, at any point, including
   intermediate values. Parse the fractional part as a separate integer.
   Add a source-grep test that fails if "float(" appears in the file.
2. Ambiguous currency symbol + unknown locale -> Money(currency="UNKNOWN"). NEVER
   default to USD.
3. Ambiguous thousands/decimal separator + unknown locale -> return None. Never guess.
4. Support locale grouping: en-US, en-GB, de-DE, fr-FR, en-IN (lakh/crore).
5. Multipliers: k/K, m/M/mn, bn, lakh, crore.
6. Minor-unit exponent per ISO 4217 (USD/EUR=2, JPY=0, KWD/BHD=3). Ship a small table;
   do not add a dependency for this.
7. as_written is preserved verbatim on the Money object — the card and the conflict
   display both need the original string.

TEST tests/capture/validate/test_money.py — table-driven. MUST include:
  ("$84K",  "en-US") -> 8_400_000 USD
  ("$8.4K", "en-US") ->   840_000 USD      <- these two must never collide
  ("84.000,50", "de-DE") -> 8_400_050
  ("84,000.50", "en-US") -> 8_400_050
  ("Rs 84,00,000", "en-IN") -> 840_000_000 INR
  ("¥84000", "ja-JP") -> 84_000 JPY  (exponent 0)
  ("$84", None) -> currency == "UNKNOWN"
  ("84,000", None) -> None            (ambiguous separator, no locale)
  source-grep: no "float(" in the module

PURE. No DB, no network, no LLM.
ACCEPTANCE: pytest tests/capture/validate/test_money.py -q -> pass, 0 skips
```

---

# L1.5.5 · Conflict Detector (ALG-12)

> **This is the unit that makes GeniOS trustworthy rather than merely confident.**

### L1.5.5-U1 · Cross-evidence disagreement

**WHAT** — Detects when two pieces of evidence assert different values for the same field.

**WHY** — Your worked case: the signed PDF says \$74K, an email says \$84K. Today the
graph writes whichever arrived last and the founder is told a number with no indication
that the other exists. That is the failure mode that destroys trust permanently — not
being wrong, but being **confidently wrong with a receipt that looks legitimate**.

**WHERE** — `genios_engine/capture/validate/conflict.py`

**WHEN** — W5. Depends on **L1.5.0 (claim groups)**, L1.5.1 (spans), L1.5.3 (money),
L1.5.2 (dates), L1.5.8 (authority).

**HOW** (ALG-12)
```
1. GROUP     take the claim groups from L1.5.0 (ALG-23) and sub-group by field
             e.g. ("contract:aws-enterprise-agreement", "contract.value")

             CRITICAL: the group spans EVENTS, not one event. An email and its
             attached PDF are separate events (composio.py:383). Grouping by event
             would miss the headline case entirely. L1.5.0 owns this.

2. COMPARE   for each group with >= 2 distinct normalized values:
             values compared AFTER normalization (Money by minor_units+currency,
             ResolvedDate by overlap of [earliest, latest])

3. TOLERANCE dates: NOT a conflict if the ranges OVERLAP
             money: NOT a conflict if identical minor_units AND currency
                    (no percentage tolerance — money is exact)
             text:  NOT a conflict if casefold-equal after whitespace normalization

4. RESOLVE   compare authority_rank (ALG-14) of the competing claims:
             rank difference >= 2  -> resolution = resolved_by_authority
                                      resolved_value = higher-rank claim
             rank equal            -> resolution = unresolved_surface_both
                                      resolved_value = None
             rank difference == 1  -> resolution = unresolved_surface_both
                                      (one step of authority is not enough to silence
                                       the other side)

5. EMIT      Conflict object retaining BOTH claims with their evidence, always —
             even when resolved. The losing claim is never deleted.
```

**Design law:** the conflict record **always retains both sides**. Even
`resolved_by_authority` keeps the loser's evidence, because the founder may know
something the authority ranking does not.

**LLM** — no. **EMBEDDINGS** — no. **STORAGE** — `signal_conflicts` table.

```sql
create table if not exists signal_conflicts (
    conflict_id    text primary key,
    org_id         text not null,
    signal_id      text not null,
    field          text not null,
    subject_key    text not null,
    claims         jsonb not null,        -- full ConflictClaim list, both sides
    resolution     text not null,
    resolved_value jsonb,
    detected_at    timestamptz not null default now()
);
create index conflicts_by_signal on signal_conflicts (org_id, signal_id);
```

**FAILURE MODES**

| Failure | Mitigation |
|---|---|
| Same value written twice -> false conflict | step 3 tolerance; compare normalized values not raw strings |
| A draft vs a signed version -> false conflict | authority rank separates them (draft < signed); step 4 resolves |
| Amendment supersedes original -> false conflict | recency is a tie-break only **within** the same authority rank |
| Conflict storm on one entity | cap 20 conflicts per signal; beyond that emit one `INFORMATION_CONFLICT` signal and stop |

**ACCEPTANCE**
```
pytest tests/capture/validate/test_conflict.py -q
```
Required rows:
- **\$74K signed PDF (event A) vs \$84K email (event B), two SEPARATE events linked by
  `parent_object_id`** -> one conflict, `resolved_by_authority`, resolved to \$74K,
  **and the \$84K claim is still present in `claims`**. This is the headline fixture; if
  it passes only when both claims are in one event, the test is wrong.
- \$84K email vs \$84K email -> no conflict
- Oct 10-17 range vs Oct 15 exact -> no conflict (overlap)
- Oct 15 vs Nov 15 -> conflict, equal authority -> `unresolved_surface_both`
- two claims one authority rank apart -> `unresolved_surface_both` (not auto-resolved)

### L1.5.5-U2 · Conflict-to-signal escalation

**WHAT** — A conflict on a material field emits its own `INFORMATION_CONFLICT` signal.

**WHY** — *"Your systems disagree about the refund window"* is itself intelligence, and
often more valuable than either value.

**HOW** — Material fields (configurable per domain): `contract.value`,
`contract.renewal_date`, `contract.notice_period`, `deal.amount`, `policy.*`.

### L1.5.5-U3 · Card rendering contract

**WHAT** — The exact shape delivery consumes to render a conflict.

**HOW** — Both values, both authorities, both verbatim quotes, and **no
recommendation about which is right** unless `resolved_by_authority`:

> Signed document says **\$74,000** — *"total annual commitment of \$74,000"*
> (aws_agreement.pdf, chunk 42)
> An email says **\$84,000** — *"the \$84K annual contract"* (thread 8f2a)
> **Conflict detected. The signed document has higher authority.**

**REVERSE PROMPT**
```
TASK: Build the conflict detector. This is L1's trust unit.
FILE: genios_engine/capture/validate/conflict.py

PREREQUISITE: L1.5.1 spans, L1.5.2 dates, L1.5.3 money, L1.5.8 authority all green.

Implement:
  def detect_conflicts(claims: list[NormalizedClaim]) -> list[Conflict]

ALGORITHM: the 5 ordered steps in doc 05 L1.5.5-U1.

HARD RULES:
1. The Conflict object ALWAYS retains every competing claim with its evidence, even
   when resolution == resolved_by_authority. The losing claim is NEVER deleted.
   Add a test asserting len(conflict.claims) >= 2 in every resolution mode.
2. Money comparison is exact on (minor_units, currency). No percentage tolerance.
3. Date comparison is by RANGE OVERLAP. Two ranges that overlap are NOT a conflict.
4. Authority rank difference of 1 is NOT enough to auto-resolve -> unresolved_surface_both.
   Only a difference >= 2 resolves.
5. Recency is a tie-break ONLY within the same authority rank. A newer email never beats
   an older signed document.
6. Cap 20 conflicts per signal; beyond that emit one INFORMATION_CONFLICT and stop.

MIGRATION: create table signal_conflicts (DDL in doc 05 L1.5.5-U1). New migration file;
do not edit an already-applied migration.

TEST tests/capture/validate/test_conflict.py — table-driven, MUST include every row in
the ACCEPTANCE list of doc 05 L1.5.5-U1, plus:
  - draft vs signed same value -> no conflict
  - amendment vs original, same authority, different date -> resolved_by_recency
  - 25 competing claims -> capped at 20 + one INFORMATION_CONFLICT

PURE except for the store write. Split it: detect_conflicts() is pure; a separate
ConflictStore.put() does the I/O.
ACCEPTANCE: pytest tests/capture/validate/test_conflict.py -q -> pass, 0 skips
```

---

# L1.5.7 · Confidence Composer (ALG-13)

### L1.5.7-U1 · Rule 11 composition

**WHAT** — Composes a single `confidence_bp` plus a `confidence_vector` from the
evidence available.

**WHY** — Globe Rule 11: *a layer may lower confidence; it may only raise it by adding
independent evidence, and it must name that evidence.* Violating this "looks exactly
like rigour" and is the hardest failure to detect.

**WHERE** — `genios_engine/capture/validate/confidence.py`

**HOW** (ALG-13) — all integer basis points:
```
COMBINE same source:      conf = (a * b) // 10000          # multiplies, never rises
CORROBORATE independent:  conf = a + ((10000 - a) * b) // 10000 // 2
                          # bounded increase, and `evidence` MUST name the new source
AGE DECAY:                conf = conf * max(0, 10000 - days_old * DECAY_BP) // 10000
SPAN PENALTY:             applied by L1.5.1 before this unit runs
```

**The vector** — four independent axes, never collapsed before the card:

| axis | means |
|---|---|
| `evidence_bp` | how well-supported by source text |
| `expertise_bp` | is there authored domain knowledge covering this? (L1 sets 0; L3 fills) |
| `freshness_bp` | how recent is the newest supporting evidence |
| `coverage_bp` | are the sources complete enough to trust an absence? |

Globe's own open-blocker list names *"confidence modelled as a scalar rather than a
vector — cannot distinguish strong-evidence-no-expertise from weak-evidence."* The
vector is that fix, and it starts here.

**GUARD** — a raise with no named independent source **raises**, it does not warn:
```python
if new > old and not named_independent_source:
    raise ConfidenceViolation("Rule 11: raise without named independent evidence")
```

**ACCEPTANCE**
```
pytest tests/capture/validate/test_confidence.py -q
```
Required: combining two 8000s gives 6400 (not 8000, not 9000); corroboration from a
named independent source raises but stays bounded; corroboration from the **same**
source does not raise; a raise without a named source **raises ConfidenceViolation**;
age decay monotonically decreases; all outputs are `int` in `0..10000`.

---

# L1.5.8 · Authority Weighter (ALG-14)

### L1.5.8-U1 · Authority ranking table

**WHAT** — Assigns an authority rank to a piece of evidence by its provenance.

**WHY** — *A signed PDF is not a Slack aside.* Conflict resolution (ALG-12) and
confidence composition (ALG-13) both depend on this ordering.

**HOW** — lookup table, extending the existing `authority_rank_for()`:

| rank | provenance | example |
|---|---|---|
| 6 | signed / executed document | countersigned agreement |
| 5 | company canon (`internal_kind`) | uploaded pricing policy |
| 4 | structured source of record | HubSpot deal field, client DB row |
| 3 | attached document | PDF quote in an email |
| 2 | email prose | "the \$84K contract" |
| 1 | chat aside | Slack one-liner |
| 0 | inferred / unattributed | no evidence pointer |

**STORAGE** — pure table. **ACCEPTANCE** — every `EvidenceSpan.source_ref` prefix maps
to exactly one rank; unmapped prefix -> rank 0 and a logged warning, never a crash.

---

## Group acceptance gate (must pass before Wave W6)

```
pytest tests/capture/validate -q          # ALL pass, ZERO skips
pytest tests/test_layer_topology.py -q    # still green
grep -rn "float(" genios_engine/capture/validate/          # -> no matches
grep -rn "datetime.now\|date.today" genios_engine/capture/validate/   # -> no matches
grep -rn "llm\|anthropic\|LLMClient" genios_engine/capture/validate/  # -> no matches
```

**The three greps are the group law, enforced.** No floats, no hidden clock, no LLM.
