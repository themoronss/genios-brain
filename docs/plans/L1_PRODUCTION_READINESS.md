# Layer 1 — production readiness: what is actually running, what is dark, what is left

> **Created:** 2026-09-07 · **Status:** Active

**Purpose:** the code-, database- and migration-level verification of Layer 1 against the LIVE
production database (Gmail + Calendar + upload only), the **nine** defects it found and closed,
and the ordered list of everything still between here and "L1 is done and running" — with the
items that need an OWNER decision (model spend, a deploy image) named as such.

Read `L1_V2_BUILD_RECORD.md` first for *what was built*. This file is *what is running*, and the
two are not the same thing.

---

## 1. The one-paragraph version

Layer 1 v2 is built, deployed and **dark**. Every module exists, 8,786 tests pass on real
Postgres, migrations `0079`–`0106` are applied to production — and `qualified_signals` has **zero
rows**, because the S2 semantic lane is gated on a per-tenant activation row and
`l1_semantic_activation` is empty. No extraction ⇒ no detection ⇒ no signal ⇒ nothing for the
floor to qualify, the lifecycle to age or the publisher to store. Layer 2 therefore runs on its
pre-L1 fallback (`importance_fallback: true`), which means **any L2/L3 tuning done before the lane
is switched on is tuned against the fallback, not against Layer 1.**

---

## 2. Production evidence (read-only, 2026-09-07)

| Table | Rows | What it says |
|---|---|---|
| `source_events` | 2,973 | capture is running (2,123 mail · 776 attachments · 74 calendar) |
| `prepared_content` | 1,062 | S0/preprocess is running |
| `event_trace` | 17,856 | every stage is traced |
| `l1_extraction_results` | 355 | **all `profile_id`/`tier` NULL** → every row written by the LEGACY L2 extractor, none by S2 |
| `l1_semantic_activation` | **0** | the S2 lane is off for every tenant |
| `qualified_signals` | **0** | Layer 1 has never published |
| `qualification_drops` | **0** | and has never refused anything either |
| `publication_rejections`, `signal_conflicts`, `unclassified_observations` | 0 | same cause |
| `parked_events` | 775 (all `pending`) | 681 `DOC-02` + 86 `DOC-05`, **100% gmail attachments** |
| `source_coverage` | 8 | coverage IS working: `sales`/`admin`/`support` correctly `coverage_ready=false` (no CRM, no finance, no desk); only `fundraising` is ready |
| `schema_migrations` | 102 | latest `0106_l2_v2_activation.sql` |

**The funnel, from `event_trace` (all time):** 2,973 landed → 412 passed S1 → 287 passed S2 →
361 emitted. The S1 noise rules drop ~57% (`N-03` 610, `N-02` 546, `N-06` 470). The S4 stage
appears exactly twice in the whole table, both `short_circuit`.

**The document lane yields ~1%.** 776 attachment events, 767 parked, none drained. On 2026-09-07
itself: 7 attachments captured, 7 parked.

**Silently off in `.env.production`:** `GENIOS_ENABLE_OCR=false`, `GENIOS_ENABLE_L1_RELEVANCE=false`
(deterministic dev classifier — correct to be off, the LLM junk gate `GENIOS_L1_LLM_GATE` covers
it), `use_domain_compiler=false` (set in no environment — L3's, not L1's). There is **no
Dockerfile and no apt hook** in this repo: the DigitalOcean buildpack image has neither
`tesseract` nor `poppler`, so `enable_ocr=true` alone would not produce OCR.

---

## 3. What was wrong, and what is now fixed

All nine were found by driving the real path — a live-database read, an HTTP request, a sweep —
not by reading the tests. Every one of them was green in the suite while broken in production.

### 3.1 The upload door never published · **FIXED**

`POST /api/org/{org}/upload` captured chunks through `intake.ingest_manual` — the same one door a
sync uses — and then stopped. The four things L1 does after capture (file conflicts → run the
tenant's floor → age the lifecycle → publish) lived **inside `api/routes._run_ledger`**, which is
a `run_sync` hook. The upload door does not call `run_sync`, so an uploaded contract produced no
row in `qualified_signals`, silently. Two more arguments were missing underneath: `ingest_manual`
was called with no `semantic` lane and no `esqe` bundle.

* new `capture/esqe/finalize.py` — `finalize_l1(summary, org_id, stores)` + `ManualSweep`, the
  sequence written **once**, in its original order, with its original guarantees;
* `api/routes._run_ledger` now calls it (forty lines removed, no behaviour change);
* `upload_routes` threads `semantic` + `esqe` (one lane per FILE, not per chunk) and calls the
  same finalizer;
* `intake.ingest_manual` gained an `esqe` passthrough and now RETURNS its `CaptureResult`.

### 3.2 An untagged upload could never be extracted · **FIXED**

`_envelope_direction` returned `None` for anything with no `internal_kind` and no mailbox owner,
and `run_semantic_lane` skips a `direction_unknown` event. `internal_kind` is set by a TAG, so an
**untagged** upload — a signed MSA, an audit checklist, a vendor quote — was refused a direction
and never reached the model. Fixed by reading the registry's own `DELIBERATE_SOURCES`
(`upload`, `human`, `agent`, `internal`) — the same set the gate whitelists as W-05 — because a
file the tenant handed us has no counterparty to be inbound from.

Proven end-to-end: an uploaded MSA now produces qualified signals with verified spans and an
`org_history` baseline (`tests/capture/test_upload_door_publishes.py`, real Postgres, mutation-
checked — deleting the `finalize_l1` call turns it red).

### 3.3 Every OCR-able attachment was filed as permanently unreadable · **FIXED**

The Gmail connector's pre-download skip stubbed *every* non-extractable part as
`status="unsupported"` → `DOC-02`, which means *nothing can ever read this*. A screenshot invoice
or a scanned PO is the opposite: readable, unread only because no engine is wired — `DOC-06`
`ocr_unavailable`, one config line away, and already in `parked/drain.NEEDS_REFETCH` so the
refetch ladder picks it up. Fixed by using `documents/router.has_pages()` at the skip.

**The 681 existing `DOC-02` rows** were filed under the old, terminal code, and a stored park is a
permanent record. `scripts/recode_parked_documents.py` corrects them: it judges each row by the
SAME `documents/router.has_pages` the connector now uses, over the mime and filename retained in
`raw_payloads`, moves only the ones with pages to `DOC-06`, leaves a genuinely unsupported .zip
alone, and leaves any row whose payload has expired alone rather than guessing. Dry run by
default, `--apply` to write, idempotent, and it will not touch a park a human already acted on
(`status='pending'` only). Five tests on real Postgres.

```bash
# dry run first — it prints has_pages / genuinely_unsupported / payload_unavailable
python scripts/recode_parked_documents.py --database-url "<url>"
python scripts/recode_parked_documents.py --database-url "<url>" --apply
```

### 3.4 A receipt could not name its page or its section · **FIXED**

`EvidenceSpan` carried `source_ref` + character offsets + quote and nothing else, so a claim from a
signed PDF could cite *character 4,812 of the prepared text* and no more. A page number exists for
the moment `documents/native.py` joins a PDF's pages into one string and is unrecoverable
afterwards — concatenation is not invertible — so it had to be carried or lost, and it was lost.

* new `capture/documents/pages.py` — `PageMap`, built by the joiner from the same list it joins;
  `for_slice` re-expresses it in one chunk's coordinates (the upload door's case);
* `DocumentResult.page_offsets`, filled on BOTH PDF paths (native parse and rasterized OCR);
* the Gmail and Drive connectors put it on `raw["document"]`, and the pipeline reads it once and
  hands it to the extractor AND to ALG-08;
* `EvidenceSpan.page` / `.section` — attached at the alignment seam, including on receipts the
  binder synthesizes, and **recomputed** when ALG-08 relocates a quote (a moved span may have
  crossed a page break; a page that survives a relocation unexamined is a confident citation
  naming the wrong page);
* the upload door now chunks by SECTION — what doc-04 assigns to the `document` profile — and
  pages an oversized section by sentence with the heading INHERITED, so a 50-page agreement stays
  affordable without trading *Termination* for "somewhere in the agreement".

**Not done, and deliberately not faked:** table-cell provenance. `documents/native.py` flattens a
DOCX table into lines, so no row or column identity survives extraction and a `cell` field could
only ever hold a guess. It needs a table-aware extractor first; the contract says so where the
field would have gone.

### 3.5 The four provenance answers a stored signal could not give · **FIXED** (migration 0115)

`qualified_signals` could not say when we first saw the thing, whether the source had changed
since, why the floor let it through, or what replaced it:

| Column | What it answers | Where it comes from |
|---|---|---|
| `ingested_at` | did this reach us late? (`occurred_at` is when it HAPPENED) | `source_events.captured_at` |
| `content_hash` | has the source changed since we concluded this? | the SAME digest the extraction cache keys on — `cache.content_digest`, one function, both callers |
| `qualification_reason` | why it crossed, not merely that it did | ALG-18's verdict |
| `superseded_by` | what replaced this — the forward half of a link that only pointed back | written by the STORE when the replacement lands, keeps the FIRST link, survives replay |

All four are nullable, nothing is backfilled (a row written before 0115 genuinely does not know),
the digest shape is enforced by a CHECK as well as by the row, and **all four are returned by
`GET /qualification/signals`** — a provenance column no surface serves is the same defect as a
unit no request path reaches.

### 3.6 Two smaller ones

* **`l1_sync_runs.started_at` was never written.** The column has existed since the table did and
  the insert never named it, so all 443 production rows report a finish with no start and "how
  long did this tenant's sync take" was unanswerable from the ledger built to answer it.
  `run_sync` now stamps its own start from the injectable `_now` seam (so a replay is frozen, not
  raced) and `_run_ledger` writes it.
* **`wiring.make_open_lane_store` was defined twice**; the second shadowed the first. The dead one
  is gone.

### 3.7 OCR was a flag with no engine behind it · **FIXED (image side)**

`enable_ocr` has existed since L1.3.4 and turning it on has never produced OCR: App Platform
buildpacks cannot install apt packages, so the image has neither `tesseract` nor `poppler`. The
flag's only possible effect was to send every scanned attachment down a branch that fails.

New `Dockerfile` — python 3.11-slim, `tesseract-ocr` + `tesseract-ocr-eng` + `poppler-utils`,
installed from `requirements-lock.txt` (the tested set, not the range file), copying only the
engine, migrations and scripts, with a CMD identical to the `Procfile`'s.
`tests/test_deploy_image.py` pins the contract: both binaries present, language data beside the
engine, the lock file used, CMD and Procfile in step, `tests/` and `.env` never copied into the
image, and `enable_ocr` still defaulting to False — the image makes OCR **possible**, never
automatic.

**Two things are still the owner's:** pushing the deploy (the first deploy after this file lands
switches App Platform from buildpack to Docker — intended, and worth doing deliberately), and then
`GENIOS_ENABLE_OCR=true` + `GENIOS_OCR_ENABLED_ORGS=<pilot org>`. The image was **not built here**
— no Docker daemon on this machine — so the first build is the one that proves it.

### 3.8 W-04 was a whitelist rung nothing could reach · **FIXED**

`gate/rules.whitelist` has read `raw["important_attachment"]` since the gate was written and
**nothing in the engine ever set it**. The rung sat in the rule table, in `REASON_LABELS` and in
the docs, and could not fire.

It matters for one class. `N-02/03/04` already exempt a message carrying an attachment; `N-06/N-07`
do not — they drop on Gmail's own PROMOTIONS/SOCIAL guess regardless, which is **514 drops** in
production. The file always survived (`attachment_overrides_junk` forces the full fetch and the
attachment lands as its own event with no labels on it), but the covering email — where the date
and the amount are actually stated — did not. The connector now sets the flag when a part is
genuinely readable (`_is_extractable_part`, so an `invite.ics` or a signature image does not
count), and W-04 fires.

### 3.9 Test/wiring drift closed alongside

`test_lifecycle_digest_wired.py` and `test_alg19_reaches_the_table_layer_2_reads.py` both
inspected `_run_ledger` for a sequence that now lives in `finalize.py`; both were repointed and
still drive the real request path.

**Suite:** `8,831 passed · 152 xfailed · 0 failed` on a freshly created scratch Postgres, with the
locator and the finalizer both mutation-checked (neutralise the wiring, the tests go red). On a
dirty scratch DB the same run showed 8 unrelated failures — drop and recreate before every run.

---

## 4. What is left, in order

### P0 — switch the lane on, or none of the rest matters

**P0.1 · Deploy the four fixes above.** Uncommitted on `harsh/mvp`. No migration needed.

**P0.2 · Activate ONE org and watch it.** *Owner decision: this starts per-message model spend.*

```bash
# through the audited admin route, never a raw insert
curl -X POST "$BRAIN/admin/l1-activation/<org_id>" -H "Authorization: Bearer <owner JWT>" \
     -d '{"notes":"L1 pilot, day 1"}'
# then a sync, in the background (a sync sync/reason call gets killed by the gateway)
curl -X POST "$BRAIN/integrations/sync-all" -H "Authorization: Bearer <owner JWT>"
```

Verify, in this order — each answers a different failure:

```sql
select count(*) from l1_extraction_results where org_id = :o and profile_id is not null; -- S2 ran
select count(*) from qualified_signals where org_id = :o;                               -- L1 published
select count(*) from qualification_drops where org_id = :o;                             -- the floor ran
select signal_type, count(*), min(importance_bp), max(importance_bp)
  from qualified_signals where org_id = :o group by 1;                                  -- spread, not a constant
select count(*) filter (where not (evidence_refs @> '[{"verified":true}]'))::float
     / nullif(count(*),0) from qualified_signals where org_id = :o;                     -- unverified span rate < 5%
select sum(cost_minor) from llm_costs where org_id = :o and created_at > now()-interval '1 day';
```

**P0.3 · Close G10.** Seven days, no mid-week switch-off, then
`python -m scripts.l1_shadow_diff --org <org> --days 7 --database-url "<url>"`. Every "old found /
new missed" line needs an explanation before the legacy L2 extraction path is removed.

**P0.4 · Sequencing for L2/L3.** Do P0.2 **before** tuning Layer 2 or Layer 3 on this tenant.
`context/situation_bso` falls back to its pre-L1 score with `importance_fallback: true` when no
`qualified_signals` row exists, so anything tuned now is tuned against the fallback.

### P1 — the document lane (this is where the evidence is being lost)

**P1.1 · OCR — the image is written (3.7); what is left is a deploy and two env vars.**

```bash
# 1 · push, and confirm App Platform builds from the Dockerfile (it switches strategy)
# 2 · then, and only then:
GENIOS_ENABLE_OCR=true
GENIOS_OCR_ENABLED_ORGS=<pilot org id>
```

Order matters: `enable_ocr=true` on an image without the binaries is strictly worse than off — the
router degrades instead of crashing, but every scanned file becomes `ocr_failed` instead of the
`DOC-06` that says "one config line away".

**P1.2 · Drain the backlog.** The re-code half is built (3.3) and is a dry run away. After P1.1:
run `recode_parked_documents.py --apply`, then the refetch/drain ladder for
`DOC-02`/`DOC-05`/`DOC-06`, and confirm `parked_events.status` moves off `pending`. 767 files is
the single largest pool of unread evidence this tenant has.

**P1.3 · Evidence locator — page and section: DONE (3.4).** What remains is **table-cell
provenance**, and it is a build rather than a wiring fix: `documents/native.py` flattens a DOCX
table into lines, so *row "Document A" · column "Accountable"* needs a table-aware extractor that
keeps cell coordinates through parsing, chunking and masking. Required before an
audit-readiness / document-integrity application that has to cite a responsibility matrix; not
required for commitments, deadlines, renewals or ownership stated in prose.

### P2 — contract gaps on `QualifiedEnterpriseSignal`

Present and good: identity, `trace_id`, source, `occurred_at`, typed `signal_type`,
`importance_bp` + components + version, `confidence_bp` + vector, `evidence_refs` (non-empty at
construction), `visibility` (required), `coverage_ready` (tri-state), `state`, `supersedes`,
`expires_at`, extraction provenance (`model_snapshot`, `prompt_version`, `schema_version`,
`extraction_profile`), per-field confidence.

Added since (3.5, migration 0115): `ingested_at`, `content_hash`, `qualification_reason`,
`superseded_by` — all four written on the real path and served by the route.

Still missing, in the order they cost something. **Both need an owner decision, which is why they
were not simply done:**

1. **`importance_bp` is L1-local but named as if it were final.** L2 takes it as the base
   (`gather_l1_signals` → MAX over live scored signals) and the composition steps that were meant
   to fold in cross-source context are still open (`L2_MISSING_UNIT_SPECS.md` **A-1**). Two ways
   out and they are incompatible: RENAME to `local_salience_bp` (a stored column, a contract field
   and every L2 reader move together) or FINISH the L2 composition so the L1 number stops being
   the final answer. Doing neither is the state today; doing both is contradictory.
2. **First-class `actor` / `business_subject`.** Today the distinction lives inside
   `Commitment.actor`/`beneficiary` and an untyped `roles` lane, so *"Maya emailed Anisha about
   Imran's responsibility for Document A"* resolves correctly only through the commitment, never
   at signal level. This is an extraction-schema change (prompt + closed vocabulary + contract +
   every downstream reader), not a wiring fix, and it changes what the model is asked for — which
   is a decision about extraction quality and cost, not a defect to be quietly patched.
3. `coverage_ref` — a pointer to the `source_coverage` EPOCH a signal was judged under. Left out
   deliberately: `coverage_ready` is a per-event boolean today and the epoch is per
   `(org, domain)`, so filling this honestly means threading the epoch through capture. Inventing
   it at publish time would date a signal to the epoch that is current when it is stored rather
   than the one it was judged under, which is the wrong answer wearing the right column name.

### P3 — connectors, for the three sources we actually have

1. **Gmail deletions are never reconciled.** The connector pages with a query + `pageToken` and
   never reads `historyId`, so a deleted or moved message stays in `source_events` for ever and
   coverage cannot report it. (Calendar is fine — it cursors on `updated`, which catches moves.)
   **Not fixed here on purpose:** it is a new provider integration (Gmail's `history.list` through
   Composio, with the "history too old → full re-sync" fallback), and shipping an untested
   provider call against a live mailbox is how a sync starts silently losing mail. It needs the
   pilot mailbox to develop against.
2. `l1_sync_runs.started_at` — **DONE** (3.6).
3. The duplicate `make_open_lane_store` — **DONE** (3.6).
4. Calendar depth: 74 events total against 2,123 mails. Confirm recurring-event expansion and
   attendee roles on the pilot org before drawing any meeting-preparation conclusion from it.
   A measurement, not a code fix — it needs the pilot.

### P4 — evaluation (the reason "it looked done" and was not)

1. Golden corpus is **8 messages, not 30**. `scripts/extract_golden.py` is real; the corpus is not
   complete and must not be reported as such.
2. No recall / precision / date-accuracy / unsupported-assertion harness in CI — L1 quality is
   currently measured by looking at cards, which is the thing that failed here.
3. `scripts/l1_s1_report.py` and `l1_shadow_diff.py` exist and are read-only; make them a weekly
   run on the pilot org rather than a thing somebody remembers.

---

## 5. Migration hygiene — flagged, not touched

`migrations/` holds three UNTRACKED files that are **not applied to production**:
`0107_l3_activation.sql`, `0113_org_rule_discovery.sql`, `0114_signal_citations.sql` — and the
numbers `0108`–`0112` do not exist locally at all. **This file's own migration is `0115`**, taken
above the highest number present so it cannot collide with whatever `0108`–`0112` turn out to be. That is the parallel Layer 3 work; whoever owns
it must confirm the gap is intentional before the next deploy, because two branches minting
migration numbers independently is how a number gets used twice.

---

## 6. Definition of done for Layer 1

Not "every module exists". These, in this order:

1. one activated tenant with a non-zero `qualified_signals` count and a score spread, not a constant;
2. unverified span rate < 5% on that tenant;
3. attachments: parked count falling, not flat;
4. G10's seven-day shadow diff read, with every "v1 found / v2 missed" line explained;
5. the legacy L2 extraction path deleted — *after* 4, never before.
