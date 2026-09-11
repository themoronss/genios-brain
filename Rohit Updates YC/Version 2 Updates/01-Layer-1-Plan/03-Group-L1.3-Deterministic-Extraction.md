# L1.3 — Deterministic Extraction (Stage S1)

**Group responsibility:** extract everything that is **objectively present** in the
event, before any interpretation happens.

**Group law:** *No LLM. No interpretation. If it requires judgement, it belongs in S2.*

**Package:** `genios_engine/capture/` (existing modules, regrouped)
**Input:** `RawObject` from a connector
**Output:** `RoutedEvent` + `PreparedContent` + `StructuralTokens`
**LLM sites:** LLM-3 (speech-to-text) and LLM-4 (OCR fallback) only — both are
*transcription*, not interpretation. They convert a non-text medium into text so that
S2 can read it.

---

## Component map

| # | Component | ALG | Units | Wave | Status |
|---|---|---|---|---|---|
| L1.3.1 | Event Normalizer | — | 1 | — | ✅ exists |
| L1.3.2 | Metadata Extraction | — | 2 | — | ✅ exists, strong |
| L1.3.3 | Content Normalizer | — | 2 | — | ✅ exists |
| L1.3.4 | Document Router | ALG-01 | 4 | W2 | ⚠️ 3 gaps |
| L1.3.5 | **Structural Parser** | ALG-04 | 3 | W2 | 🆕 **NEW** |
| L1.3.6 | Thread Reconstructor | ALG-03 | 2 | W2 | ⚠️ partial |
| L1.3.7 | Deduplication | ALG-02 | 2 | — | ✅ exists |
| L1.3.8 | Attachment Resolver | — | 2 | W2 | ⚠️ refetch missing |
| L1.3.9 | **Structured Mapper** | ALG-21 | 3 | W2 | ⚠️ **exists, not in v1 plan** |

**Why this group matters more than it looks:** its outputs are the *deterministic
inputs* to the Model Router (ALG-05) and to Importance Scoring (ALG-17). A currency
token counted here decides whether a document goes to Opus or Haiku. Get S1 wrong and
S2 is priced and prompted wrong.

---

# L1.3.5 · Structural Parser (ALG-04) — NEW

> The one genuinely new component in this group, and the one S2 and S4 both depend on.

### L1.3.5-U1 · Token scan

**WHAT** — Finds every objectively identifiable token in the cleaned text and records
it with an offset.

**WHY** — Three separate consumers need these counts and **none of them may ask an LLM
for them**:
1. **ALG-05 Model Router** — currency-token count and date-token count decide the model tier.
2. **ALG-12 Conflict Detector** — needs the literal numbers present in the source to
   check the model did not invent one.
3. **L1.5.1 Span Validator** — an amount the model claims must correspond to a token found here.

**WHERE** — `genios_engine/capture/structural/tokens.py`

**WHEN** — W2. Depends on L1.3.3 (Content Normalizer) only.

**HOW** (ALG-04) — an ordered regex ruleset over `PreparedContent.clean_text`:

| token type | what it catches | notes |
|---|---|---|
| `url` | http/https/www, bare domains | never followed, only recorded |
| `email_address` | RFC-ish addresses | feeds provisional identity |
| `currency_token` | symbol+number, code+number, number+code | **does not parse the value** — that is L1.5.3 |
| `bare_number` | integers/decimals with separators | includes locale-ambiguous forms |
| `percentage` | `33%`, `33 percent` | |
| `date_string` | ISO, `Oct 15`, `15/10/2026`, weekday names | **does not resolve** — that is L1.5.2 |
| `duration_string` | `30 days`, `2 weeks`, `Q3` | |
| `time_string` | `9am`, `09:00`, `9:00 IST` | |
| `phone` | E.164 and common national formats | |
| `identifier` | invoice/PO/ticket/contract refs | pattern-configurable per tenant |
| `file_ref` | filenames with known extensions | |

**Critical separation of concerns:** this unit **finds** and **counts**. It does not
**interpret**. `$84K` is recorded as a `currency_token` at offset 42-47 with
`raw="$84K"`. Turning that into `Money(8_400_000, "USD")` is L1.5.3's job, and it
happens after the model has had its say — so the model's claim and the source token can
be compared.

**LLM** — no. **EMBEDDINGS** — no. **STORAGE** — pure; result attached to `PreparedContent`.

**OUTPUT**
```python
@dataclass(frozen=True)
class StructuralToken:
    token_type: str
    raw: str
    start_offset: int
    end_offset: int

@dataclass(frozen=True)
class StructuralTokens:
    tokens: tuple[StructuralToken, ...]
    counts: dict[str, int]      # token_type -> count, for the model router
```

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| Over-matching (`2026` as both bare_number and date_string) | inflated counts skew the tier router | tokens may overlap, but `counts` de-duplicates by offset span |
| Missing a currency format | document routed to a cheap tier | the golden corpus asserts token counts, not just extraction quality |
| Regex catastrophic backtracking | ingest stalls | every pattern is linear-time; a test asserts each compiles and runs under 10ms on a 40KB input |

**ACCEPTANCE**
```
pytest tests/capture/structural/test_tokens.py -q
```
Required rows: `$84K`, `USD 84,000`, `₹84,00,000`, `84.000,50`, `Oct 15`, `15/10/2026`,
`next Friday`, `30 days`, `9am IST`, `33%`, an invoice ref, a URL, an email address —
each producing the right `token_type` and correct offsets. Plus: a 40KB document parses
in under 100ms.

**REVERSE PROMPT**
```
TASK: Build the structural token parser. This is S1's new component.
FILE: genios_engine/capture/structural/tokens.py

WHY IT MATTERS: three consumers depend on these counts and NONE may ask an LLM for them:
  1. the model tier router (ALG-05) uses currency_token and date_string counts
  2. the conflict detector (ALG-12) compares model-claimed amounts against source tokens
  3. the span validator (L1.5.1) checks a claimed amount corresponds to a real token

Implement:
  @dataclass(frozen=True) StructuralToken(token_type, raw, start_offset, end_offset)
  @dataclass(frozen=True) StructuralTokens(tokens, counts)
  def scan(clean_text: str) -> StructuralTokens

Token types and patterns: the table in doc 03 section L1.3.5-U1.

HARD RULES:
1. This unit FINDS and COUNTS. It does NOT parse values, resolve dates or infer meaning.
   "$84K" -> StructuralToken(currency_token, "$84K", 42, 47). Nothing more.
   Turning it into Money is L1.5.3's job and must happen LATER, so the model's claim can
   be compared against the source token.
2. PURE. No DB, no network, no LLM, no clock.
3. Every regex must be linear-time. No nested quantifiers that can backtrack
   catastrophically. Add a test asserting a 40KB input scans in under 100ms.
4. Tokens MAY overlap (2026 is both a bare_number and part of a date_string). The
   `counts` dict de-duplicates by offset span so the tier router is not double-counting.
5. Offsets are into clean_text and must round-trip: clean_text[start:end] == raw.
   Add a property test asserting this for every token found.

TEST tests/capture/structural/test_tokens.py — table-driven with every example in the
ACCEPTANCE list of doc 03 L1.3.5-U1, plus:
  - offset round-trip property test over a corpus of 50 real messages
  - performance test: 40KB in < 100ms
  - empty string, whitespace-only, and a string of 10000 dollar signs (no crash)
```

### L1.3.5-U2 · Counts for the model router

**WHAT** — Exposes `counts` in the exact shape ALG-05 consumes.

**WHY** — Keeps the tier decision deterministic and auditable: *"this went to Opus
because it had 4 currency tokens and 3 date strings"* is a sentence you can check.

### L1.3.5-U3 · Tenant-configurable identifier patterns

**WHAT** — Per-tenant regex for invoice / PO / ticket / contract reference formats.

**WHY** — Every company numbers its documents differently. A hardcoded pattern finds
nothing at most tenants.

**STORAGE** — `tenant_identifier_patterns(org_id, pattern_name, regex, created_by)`.
Patterns are validated for linear-time execution **before** they are stored.

---

# L1.3.4 · Document Router (ALG-01)

### L1.3.4-U1 · Native text extraction — ✅ exists
`documents/native.py`. PDF/DOCX/XLSX/PPTX/TXT/MD. Keep as is.

### L1.3.4-U2 · OCR — ⚠️ exists, disabled

**GAP:** `enable_ocr` defaults `False` and the Tesseract binary is not present in the
deploy image. A scanned contract therefore becomes an empty document silently.

**FIX**
1. Add Tesseract to the container image.
2. Enable per-tenant, not globally.
3. **LLM-4 fallback:** when Tesseract confidence is below threshold, route the page
   image to a vision model. This is transcription, not interpretation — allowed.
4. A failed OCR emits a **low-confidence marker, never nothing.** An empty document is
   indistinguishable from a document with nothing in it, and that ambiguity propagates.

**ACCEPTANCE** — a scanned PDF fixture produces text; a deliberately unreadable scan
produces a marker with `ocr_failed`, not an empty string.

### L1.3.4-U3 · Speech-to-Text (LLM-3) — 🆕 MISSING ENTIRELY

**WHAT** — Audio/video -> timestamped, diarized text.

**WHY** — Meeting commitments that never touch email are invisible today. Globe lists
this as an always-on L1 site; the code has no audio path at all.

**HOW** — transcription model, output persisted and hashed exactly like any other
extraction so replay reads the transcript, never re-transcribes.

**OUTPUT** — text + speaker labels + timestamps. Then the `transcript` extraction
profile (L1.4.2) runs on it, at T3.

**FAILURE MODES** — diarization errors attribute a commitment to the wrong person.
Mitigation: speaker labels carry confidence; a commitment whose speaker confidence is
below threshold has `actor="unknown"` rather than a guess.

### L1.3.4-U4 · Chunking (ALG-01) — ✅ exists, ⚠️ upgrade

**Current:** `documents/chunking.py` packs whole sentences to 2000 chars. Correct as far
as it goes — it will not cut mid-sentence.

**GAP:** it is not **section-aware**. Globe's requirement is that a 50-page agreement
becomes semantically bounded chunks (Overview / Pricing / Renewal / Termination / SLA),
because *a cancellation clause split across two chunks is a clause never found*.

**FIX** — add a `section` strategy used by the `document` profile:
1. Detect headings (numbered clauses, ALL-CAPS lines, markdown headers, bold runs).
2. Chunk on heading boundaries first, sentence boundaries second.
3. **Never split inside a detected clause**, even if it exceeds `max_chars` — emit the
   oversized chunk and flag it, rather than destroying the clause.
4. Carry `section_title` on every chunk so evidence spans can cite it.

**ACCEPTANCE** — a fixture contract with a Termination clause spanning a would-be chunk
boundary yields that clause **whole**, in one chunk, with `section_title="Termination"`.

---

# L1.3.6 · Thread Reconstructor (ALG-03)

### L1.3.6-U1 · Direction and turn index

**WHAT** — For each message: is it inbound or outbound, and where in the conversation does it sit?

**WHY** — Without direction, *an outbound offer reads as an inbound request.* This bug
has already occurred once in this codebase and was fixed by adding an envelope to the
extraction prompt. S1 must compute it so S2 can be told.

**HOW** (ALG-03)
```
direction = outbound if actor_email in org_mailbox_identities else inbound
turn_index = position in the in-reply-to chain, 0-based
thread_depth = total messages in the chain at ingest time
last_inbound_at / last_outbound_at = derived from the chain
ball_in_court = the party who did NOT send the most recent message
```

`ball_in_court` is a deterministic derivation, **not** a judgement — it is simply "who
spoke last". Whether that means someone is stalling is L2's question.

**ACCEPTANCE** — a 5-message thread produces correct direction and turn index for each;
a forwarded message is not counted as a reply; `ball_in_court` flips correctly on each turn.

---

# L1.3.8 · Attachment Resolver

### L1.3.8-U1 · Refetch of parked stubs — ⚠️ GAP

**WHAT** — Attachments parked as `NEEDS_REFETCH` are re-fetched and processed.

**WHY** — Today `DOC-02/05/06` stubs park with `NEEDS_REFETCH` and **no code path ever
refetches them.** A contract that failed to download on first sync is lost permanently,
silently. This is a small unit with a large blast radius: the single most
intelligence-dense object in an email is the attachment.

**FIX** — add a drain job: select `NEEDS_REFETCH` older than 10 minutes, refetch via the
tenant connector factory, bounded retry ladder, dead-letter after 5 attempts with an
admin-console surface.

**ACCEPTANCE** — a fixture attachment that fails first fetch is present after one drain
cycle; after 5 failures it appears in the admin console rather than vanishing.

### L1.3.8-U2 · Gmail fast-path attachment recovery — ⚠️ GAP

**WHAT** — On the Gmail fast path, a confidently-dropped message retains only the list
snippet and **its attachments are never fetched.**

**WHY** — A junk-classified email with a real contract attached loses the contract.

**FIX** — if a message carries an attachment with an extractable mime type, it is
**never** eligible for the confident fast-path drop. Attachment presence overrides junk
confidence.

---

---

# L1.3.9 · Structured Mapper (ALG-21) — the S2 bypass

> **This component was missing from the first draft of this plan.** It exists in code
> and carries the highest-value data GeniOS will ever ingest.

### L1.3.9-U1 · Mapping application

**WHAT** — Populates an `ExtractionResult` from a **registered field mapping** instead of
from a language model, for sources that are already typed.

**WHY** — A HubSpot deal has `amount`, `dealstage` and `closedate` as typed fields. A
Stripe subscription has `status`, `plan` and `current_period_end`. Asking a model to
"extract" a number that is already sitting in a typed column is pure waste **and a
hallucination risk** — the model can get it wrong; the field cannot.

**And this is the load-bearing point for the customer bar:** billing and product-usage
data are structured. Churn cohorts, LTV lookalikes and pricing analysis all depend on
them. A Layer 1 plan that only described the unstructured path would have left the
highest-value sources with no route through the layer at all.

**WHERE** — `genios_engine/capture/structured/apply.py` (exists), extended to emit an
`ExtractionResult`.

**WHEN** — W2. No dependency on S2.

**HOW** (ALG-21)
```
1. LOOKUP    has_mapping(source, object_type)?   -> registry.py
             gate/gate.py S1.5 already short-circuits on ctx.is_structured
2. APPLY     map typed source fields -> ExtractionResult fields via the mapping
3. NORMALIZE money fields go through L1.5.3 exactly like extracted ones
             date fields go through L1.5.2 exactly like extracted ones
4. EVIDENCE  synthesize an EvidenceSpan whose source_ref is the field path
             e.g. "structured:hubspot.deal.v1#amount"
             quote = the raw field value, verified = True (a typed field IS its own receipt)
5. CONFIDENCE field_confidence = 10000 for every mapped field.
             A typed field is not a guess.
6. AUTHORITY authority_rank = 4 (structured source of record) — above email prose,
             below company canon and signed documents
```

**Registered mappings today** (`structured/registry.py`):
`hubspot.deal.v1` · `stripe.subscription.v1` · `gcal.event.v1` ·
`postgres.customer_accounts.v1`

Note `stripe.subscription.v1` is registered for a source that **cannot currently be
built** — the mapping is waiting for the connector (L1.1 priority P1). That is the
cheapest possible billing integration: the mapping half is already done.

**LLM** — **no, and this is the point.** Structured events never reach S2.
**EMBEDDINGS** — no.
**STORAGE** — writes `l1_extraction_results` with `profile_id="structured"` and
`model_snapshot="mapping:<mapping_id>"`, so the provenance record is uniform and a
replay reads it the same way.

**FAILURE MODES**

| Failure | Consequence | Mitigation |
|---|---|---|
| A mapping drifts from the provider's schema | silently empty fields | mapping is versioned (`.v1`); a field that maps to nothing raises rather than writing null |
| A structured source is *not* registered | falls to `needs_extraction`, model runs on JSON | acceptable fallback, but counted — `unmapped_structured` metric |
| Money in a typed field with no currency column | wrong currency | mapping must declare the currency field or a fixed currency; no default |
| Downstream treats structured as lower-trust | good data discounted | confidence 10000 + authority rank 4, asserted in tests |

**ACCEPTANCE**
```
pytest tests/capture/structured/test_mapper.py -q
```
Required: a HubSpot deal fixture produces an `ExtractionResult` with a `Money`, a
`ResolvedDate` and `field_confidence == 10000`, **and zero LLM calls**; the synthesized
evidence span has `verified=True`; an unregistered structured source falls through to
`needs_extraction` and increments `unmapped_structured`.

**REVERSE PROMPT**
```
TASK: Extend the structured mapper to emit an ExtractionResult, bypassing S2.

THIS ALREADY PARTLY EXISTS. Read first:
  genios_engine/capture/structured/registry.py   (4 registered mappings)
  genios_engine/capture/structured/apply.py
  genios_engine/capture/gate/gate.py  S1.5       (the short-circuit on ctx.is_structured)
Do not rebuild the registry. Extend the apply path.

WHY: a HubSpot deal / Stripe subscription / calendar event / DB row is ALREADY TYPED.
Running an LLM over it is waste and a hallucination risk — the model can get a number
wrong; the typed field cannot. Billing and usage data are structured, and they are the
sources the customer's churn/LTV/pricing questions depend on.

IMPLEMENT in structured/apply.py:
  def apply_mapping(raw, mapping) -> ExtractionResult

  - map typed fields -> ExtractionResult fields per the mapping
  - money fields go through capture/validate/money.py (L1.5.3) — the SAME normalizer the
    extracted path uses. Do not write a second one.
  - date fields go through capture/validate/dates.py (L1.5.2). Same rule.
  - synthesize an EvidenceSpan per mapped field:
        source_ref = f"structured:{mapping.mapping_id}#{field_name}"
        quote      = the raw field value as a string
        verified   = True          # a typed field is its own receipt
  - field_confidence = 10000 for every mapped field
  - authority_rank = 4
  - profile_id = "structured", model_snapshot = f"mapping:{mapping.mapping_id}"

ROUTING: a structured event goes S1 -> apply_mapping -> S3 -> S4. It MUST NOT reach the
semantic extractor. Add a test asserting zero LLM calls on a structured fixture.

FROM S3 ONWARD nothing may branch on whether the ExtractionResult came from a model or a
mapping. Same validation, same conflict detection, same importance scoring. Add a test
asserting an identical (amount, date, authority) produces an identical importance_bp
whichever path produced it.

METRIC: increment `unmapped_structured` when a structured-looking source has no
registered mapping and falls through to needs_extraction.

TEST tests/capture/structured/test_mapper.py — everything in doc 03 L1.3.9-U1 ACCEPTANCE.
```

### L1.3.9-U2 · Mapping coverage report

**WHAT** — Which structured sources are connected but unmapped.

**WHY** — An unmapped structured source silently pays for an LLM call it did not need,
and gets model-confidence where it deserved 10000.

### L1.3.9-U3 · Product-usage event intake

**WHAT** — A generic structured mapping for product-usage events arriving by webhook.

**WHY** — L1.1 priority P2. Usage data is the missing half of every churn signal, and it
is structured by nature. The mapping registry supports tenant-supplied mappings already
(`mapping_from_dict`, `registry.py:141`) — this is a configuration surface, not a new
subsystem.

---

## Group acceptance gate

```
pytest tests/capture/structural tests/capture/documents tests/capture/structured -q
grep -rn "float(" genios_engine/capture/structural/            # no matches
```

Plus, on a pilot tenant over 30 days:

| Metric | Gate |
|---|---|
| attachments in `NEEDS_REFETCH` older than 1h | 0 |
| documents with empty text and no `ocr_failed` marker | 0 |
| structural token offset round-trip failures | 0 |
| clauses split across chunk boundaries in the contract fixture set | 0 |
