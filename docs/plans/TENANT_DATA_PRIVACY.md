# Tenant Data Privacy — "koi insaan customer ka data nahi dekh sakta"

> **Created:** 2026-09-11 · **Status:** Active
> **Purpose:** Rohit jaisi kisi bhi org ka data (emails, facts, cards) sirf us org ke login se dikhe — GeniOS staff, Supabase/DB access, backup leak, dusri org: kisi ko nahi. Product behaviour same rahe. Saath me legal + certification track taaki claim audit-proof ho.

Code paths `genios-brain/` ke relative hain. Har claim 2026-09-11 ko code me verify kiya gaya.

---

## 0. Aaj ki reality (code-verified)

| Area | Aaj | Where |
|---|---|---|
| API tenant isolation | ✅ 115/115 `{org}` routes pe mismatch guard; org JWT se aata hai | `api/brain_routes.py:41` (pattern), `platform/auth.py:270` |
| Agent API | ✅ key org se bandhi; DB me sirf sha256 hash | `api/routes.py:4040`, `migrations/0009_auth.sql:26` |
| Admin console | ✅ sirf counts, content nahi (1 exception `examples`, audited) | `api/admin_routes.py:12,623` |
| Raw email body | 🟡 encrypted, lekin **ek global Fernet key** (`GENIOS_CRYPTO_KEY`) DB URL ke saath same env me | `platform/crypto.py`, `capture/payload_store.py` |
| Derived content | 🔴 **plaintext**: cards, signals evidence, quotes, clean_text, graph facts/nodes, memories | §2 list |
| Uploaded files | 🔴 local disk `uploads/` pe plaintext | `api/upload_routes.py:285`, `api/account_routes.py:557` |
| DB-level isolation | 🔴 **0 RLS policies** — ek DB credential = saare tenants | `migrations/` |
| Login token | 🔴 HS256, default `"genios-dev-secret-change-in-prod"` — secret wala kisi bhi org ka token bana sakta hai | `platform/config.py:37`, `platform/auth.py:40,165` |
| Staff access | 🔴 Supabase SQL editor / prod DB URL / local scripts se sab dikhta hai | ops |

**Nateeja:** dusri org API se nahi padh sakti, lekin **DB / Supabase / backup / env access wala insaan sab padh sakta hai.** Yahi band karna hai.

---

## 1. Target design (ek line)

Har org ki **alag key** (DEK) → KMS ki master key (KEK) se wrapped → **decrypt sirf server ki machine identity kar sakti hai, koi insaan nahi**. DB me sirf ciphertext. Server Rohit ke valid login pe memory me decrypt karta hai → LLM (TLS, zero-retention) → card. RLS DB level pe dusri deewar. Staff access sirf customer-approved break-glass, customer ko audit dikhe.

```
Connector (Gmail/Calendar/Upload/… 10 aur)
      │ plaintext (memory only)
      ▼
 platform/vault.py  ──wrap/unwrap──►  KMS (KEK)   ← IAM: sirf server role
      │ ciphertext (AES-256-GCM, AAD=org|table|col)
      ▼
 Postgres (RLS: org_id = app.org_id)          Supabase/backup = sirf ciphertext
      ▲
 Rohit login (JWT) → set app.org_id → read → decrypt in memory → LLM / card
```

---

## 2. Phases

### Phase 0 — Turant (1–2 din, mostly ops)
1. **JWT secret:** DigitalOcean env me `GENIOS_JWT_SECRET` strong random hai, ye confirm karo. Code: prod me default secret ho to **startup fail** (`platform/config.py`).
2. Supabase: MFA, dashboard members = 1–2 owners, prod DB URL laptops/scripts se hatao.
3. Anthropic: commercial terms (no training) + Zero Data Retention confirm.
4. Rohit trial agreement me consent clause (QA ke liye data access).

### Phase 1 — Vault + key hierarchy (~1 hafta)
- **New `platform/vault.py`:** `seal(org_id, plaintext, aad) -> bytes`, `open(org_id, blob, aad) -> str`. AES-256-GCM (`cryptography` already dependency). Format: `v1|key_version|nonce|ct`.
- **`KeyProvider` protocol:** `wrap(dek)`, `unwrap(wrapped)`. Implementations:
  - `LocalKeyProvider`: existing `GENIOS_CRYPTO_KEY` as KEK (dev + transition).
  - `AwsKmsProvider` (**recommended**, DigitalOcean ke paas managed KMS nahi hai). IAM policy: `kms:Decrypt` sirf server role ko.
- **Migration `0132_org_keys.sql`:** `org_keys(org_id pk, wrapped_dek bytea, kek_id text, key_version int, created_at, rotated_at, destroyed_at)`.
- DEK in-process cache (TTL ~5 min). AES-GCM microseconds me hota hai, LLM ke saamne cost negligible.
- **AAD = `org_id|table|column`**, taaki org A ka ciphertext org B ki row me copy karke decrypt na ho sake.
- `platform/crypto.py` (global Fernet) sirf legacy-read path ke liye bachega.

### Phase 2 — Content encrypt karna (~2–3 hafte, sabse bada)
**Rule:** encryption **store layer** me ho, connector me nahi. Tab naya connector (10 aur) automatically covered rahega. `get_engine` 32 files me hai; seal/open inhi store classes me lagega.

| Tier | Columns (encrypt) |
|---|---|
| **A: raw** | `raw_payloads.enc_content` (global key se org DEK pe move), `prepared_content.clean_text`, `uploads/` files (file bytes encrypt), `source_events.actor` |
| **B: cards / intelligence** | `cards.headline, situation, why, actions, artifact, business_subject`; `signals.evidence`; `graph_source_refs.evidence`; `situation_resolution_claims.quote`; `unclassified_observations.quote`; `reasoning_evidence_digests.rendered_text`; `l4_reasoning_bundles.rendered`; `reasoning_context_payloads.payload`; `context_read_models.payload`; `graph_facts.value`; `graph_nodes.display_name, attributes` |
| **C: memory / misc** | `knowledge_suggestions.body`, `learned_brain_entries.value`, `temporary_memories.value`, `learning_objects.evidence`, `user_tasks.text`, `decisions.question, envelope`, `delivery_outbox.payload`, `approvals_queue.payload` |

**Plaintext rehne do:** ids, `org_id`, types, status, timestamps, scores, hashes, `reason_code`. Queries inhi pe chalti hain.

**Search / filter problem:**
- Step 1 audit: jo SQL in columns pe `WHERE`/`ORDER BY`/`->>` karta hai, uski list banao.
- Jo non-sensitive enum field filter me use hota hai (jaise stage), use alag plaintext column me nikaalo.
- `graph_nodes.canonical_key` (email identity/merge): **blind index** `HMAC(org_index_key, normalized)`.
- Name ka fuzzy search app side pe decrypted set pe karo.

**Migration strategy (zero downtime):**
1. `enc_*` columns add karo.
2. Dual-write shuru karo.
3. Per-org backfill (in-process BackgroundTasks, **Celery nahi**).
4. Reads switch karo.
5. Plaintext null karo.

⚠️ Purana plaintext Supabase PITR/backups me unki retention tak rahega. Claim tab se valid hoga.

### Phase 3 — RLS: DB khud mana kare (~1–2 hafte)
- **Do DB roles:**
  - `genios_app`: table owner **nahi**, no `BYPASSRLS`. Saari requests isi se chalengi.
  - `genios_system`: `BYPASSRLS`, sirf org-enumerating loops ke liye.
- Har `org_id` wale table pe:
  ```sql
  alter table X enable row level security; alter table X force row level security;
  create policy tenant_isolation on X
    using (org_id = current_setting('app.org_id', true))
    with check (org_id = current_setting('app.org_id', true));
  ```
- **`platform/db.py`:** request dependency ek contextvar set kare. Engine ka `begin` event `select set_config('app.org_id', :org, true)` chalaye. Ye transaction-local hai, isliye transaction pooler (6543) ke saath safe hai. Context set nahi hai to 0 rows (fail-closed).
- **Cross-org loops `genios_system` se chalenge, phir per-org tenant context:** `api/routes.py:647,826,870,913`, `deliver/outbox.py:1110`, `feedback/orchestrator.py:221`, `platform/seats.py:102`, admin counts.
- **CI test (mandatory):**
  1. Har `{org}` route ko org B ke JWT se org A ke liye call karo, 403 aana chahiye.
  2. Har tenant table pe `app.org_id=A` set karke `where org_id=B` query karo, 0 rows aani chahiye.
  3. Naya route bina guard ke aaye to build fail ho.

### Phase 4 — Insaan ka access (~1 hafta)
- **Koi impersonation / "login as" feature nahi.** Staff ke paas customer ka password ya token nahi hoga.
- **Break-glass:**
  - `access_grants(grant_id, org_id, requested_by, reason, approved_by, expires_at)`.
  - Staff request karta hai, customer owner Settings me approve karta hai.
  - Time-limited `support` scope milta hai.
  - Har read `audit_log` me `actor_type='staff'` ke saath jaata hai, aur customer ko Settings → Audit me dikhta hai.
- **JWT hardening:**
  - Secret secrets manager me.
  - `kid` ke saath rotation.
  - Customer ko har login / naya device dikhe.
- **Audit hash-chain:** tamper-evident. Ye `ENGINE_PRODUCTION_HARDENING.md` ka surviving L7 item hai, yahi close hoga.

### Phase 5 — Lifecycle (~3–4 din)
- **Org delete:** `org_keys.wrapped_dek` wipe + `destroyed_at`. Ye crypto-shred hai, backups me pada data bhi padhne layak nahi rahega. Saath me deletion certificate (`ENGINE_PRODUCTION_HARDENING` item).
- **Retention:** har table ki TTL. `purge_expired` already raw payloads ke liye hai.
- **Logs / analytics me content nahi:**
  - `logger.*(body|content)` sweep.
  - PostHog events me content nahi.
  - DO logs scrub.

### Phase 6 — BYOK (enterprise, baad me)
Customer apne AWS KMS me KEK rakhe (cross-account grant). `org_keys.kek_id` per-org hai, isliye koi rework nahi. Customer key revoke kare to data khatam. Ye GeniOS owner se bhi protection hai.

---

## 3. Fix ke baad kaun kya dekh sakta hai

| Kaun / raasta | Result |
|---|---|
| Rohit + uske team members (apna login) | Sab kuch, same product |
| Dusri org | Nahi (API guard + RLS) |
| Supabase / DB / backup leak | Sirf ciphertext |
| DB se API key nikalna | Nahi (sirf hash) |
| GeniOS staff | Nahi. Sirf customer-approved break-glass, jo logged hai |
| Deploy access wala (code badal ke) | **Residual risk.** Bachav: deploy review, KMS log, SOC 2. Poora band sirf BYOK se |
| LLM (Anthropic) | Processing ke waqt plaintext, zero-retention terms |

---

## 4. Legal + certification track (code ke parallel)

| Kya | Kyun | Kaun |
|---|---|---|
| ToS, Privacy Policy, **DPA**, subprocessor list (Anthropic, Supabase, DO, Composio, AWS KMS) | Claim aaye to pehla bachav: data customer ka, hum processor | Tech lawyer |
| **DPDP Act + Rules:** consent notice at connect, grievance officer, export/delete rights | India law | Lawyer + product |
| **Incident Response Plan:** breach ki poori report Board + customer ko 72 ghante me | DPDP + SOC 2 | Founder |
| **Google OAuth verification + CASA** (restricted Gmail scope, yearly) + Limited Use policy | Gmail data bina consent koi insaan nahi padh sakta | Founder |
| **VAPT** (CERT-In empanelled) | Sabse sasta trust proof | Vendor |
| **SOC 2 Type I, phir Type II** (Sprinto/Vanta/Drata) | Upar ke controls ka bahar ka proof | Auditor |
| ISO 27001 | India/EU enterprise | Baad me |
| Cyber insurance | Claim ka kharcha | Broker |

**Claim → proof mapping:**

| Claim | Proof |
|---|---|
| "Data aapki alag key se encrypted hai" | `org_keys` + KMS config (SOC 2 evidence) |
| "Koi insaan bina permission nahi dekh sakta" | KMS IAM policy + break-glass audit + KMS CloudTrail |
| "Har access aapko dikhta hai" | Settings → Audit (hash-chained) |
| "Delete = hamesha ke liye khatam" | DEK destroy + deletion certificate |

---

## 4b. Cost (approx, 2026 list prices — final quote vendor se lo)

**Engineering side (KMS):**

| Option | Kharcha | Kya bachata hai |
|---|---|---|
| **Free start:** `LocalKeyProvider`, master key DO env secret me (DB me nahi) | ₹0 | DB / Supabase / backup leak. Env access wala phir bhi decrypt kar sakta hai |
| **AWS KMS** (recommended before SOC 2) | ~$1/month (1 master key) + ~$0.03 per 10k calls, ~20k calls/month free. Per-org keys hamare DB me wrapped hain, **per-org KMS charge nahi** → **~₹100–200/month** | Upar ka sab + koi insaan decrypt nahi kar sakta (IAM) + har use ka log |
| GCP Cloud KMS | AWS se bhi sasta (~$0.06/key-version/month + calls) | Same as AWS |
| Supabase Vault (pgsodium) | Free | ❌ Is goal ke liye nahi — key Supabase ke paas, Supabase access = decrypt |
| Self-host HashiCorp Vault / OpenBao | Free software, ops ka bojh | Same, lekin khud chalana padega; recommend nahi |
| BYOK (enterprise) | Customer ke AWS bill me ~$1/month | Owner se bhi protection |

Code `KeyProvider` interface pe hai, isliye free se AWS pe switch sirf config change hai, rewrite nahi.

**Legal / trust side (one-time ya yearly):**

| Item | Approx |
|---|---|
| Tech lawyer (ToS, Privacy, DPA) | ₹30k–1.5L one-time |
| Google CASA Tier 2 (authorized lab) | ~$500–1,500+/year, lab pe depend |
| VAPT (CERT-In empanelled) | ~₹50k–2L per test |
| SOC 2 automation (Sprinto/Vanta/Drata) | ~$5k–15k/year |
| SOC 2 auditor | Type I ~$5k–15k; Type II zyada |
| Cyber insurance | Cover pe depend, broker quote |

## 4c. Rollout — sab automatic (per-org manual kaam nahi)

**Start = free path:** `LocalKeyProvider`, master key DO encrypted env secret me (`GENIOS_MASTER_KEY`, DB me kabhi nahi). DO account pe MFA + sirf owner access. AWS KMS pe switch baad me (SOC 2 se pehle), sirf config change.

| Kya | Kaise | Manual? |
|---|---|---|
| Master key | Ek baar generate → DO env me set | ✅ Ek baar, owner |
| Nayi org ki key | Org create / pehle write pe `org_keys` row khud banegi | ❌ Automatic |
| Purani orgs ka data | Deploy ke baad ek backfill job saari orgs pe (in-process background, per-org, resumable) | ✅ Ek baar trigger |
| Naya sync / naya connector | Store layer pe seal → khud encrypted | ❌ Automatic |
| Customer (Rohit) | Kuch nahi badalta | — |

## 5. Owner decisions (build se pehle)
1. **KMS provider:** AWS KMS (recommended) ya GCP KMS.
2. **`graph_nodes.display_name` encrypt karna hai?** Dashboard ka name search app side pe chala jaayega. Recommend: haan, blind index ke saath.
3. **Order:** Phase 0 abhi. Phase 1–3 ek saath ship honge (claim tabhi valid hai). Phase 4–5 uske baad.

## 6. Plan alignment
- Backfill aur KMS calls in-process me, **Celery / Upstash pe koi naya periodic task nahi**.
- Credits pe koi asar nahi, charge sirf `/v1/intelligence/query` pe.
- User-facing copy me koi "v1/v2" naam nahi. Ciphertext format ka `v1|` tag internal hai.
- `ENGINE_PRODUCTION_HARDENING.md` ke 2 surviving L7 items (hash-chain audit, deletion certificates) yahan Phase 4/5 me absorb hote hain.

## 7. Honest limits
- Server ko data padhna padega (LLM). Zero-knowledge possible nahi, aur claim bhi nahi karna.
- Migration se pehle ka plaintext backups me retention khatam hone tak rahega.
- Deploy-access wala insaan residual risk hai, jab tak BYOK nahi.
- Effort ke numbers estimates hain.
