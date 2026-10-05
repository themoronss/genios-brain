# STEP-04 · TO BUILD · who is us — one answer, used everywhere

**Owner:** Claude. **Depends on:** `STEP-00`. **Decision:** `06` D6 — ✅ answered 2026-10-05:
`mrrohitswerashi@gmail.com`, the source of Gmail and Calendar. **Must land before `STEP-05`**, because putting every mail
into memory with a broken notion of *us* multiplies the errors. **Moves:** cards with you as the
subject **≥ 3 → 0**; threads anchored on you **→ 0**.

---

## 1 · What is true now

| | Evidence |
|---|---|
| `ceo@thegenios.com` is a **service** node; `thegenios.com` an outside **company** | `[PROD]` graph `node_type` for both, 2026-10-04 |
| Your pitch threads are anchored on *"Mr Rohit Swerashi"* | `[PROD]` thread names; `[CODE]` `context/backfill.py:601` `name_thread_nodes` takes the oldest `corresponded_with` person with no self filter |
| Cards ask you to act on yourself | `[PROD]` *"Send Mr Rohit Swerashi your current traction metrics"*, *"Get Mr Rohit Swerashi's investor decision on GeniOS"*, and an offer card listing `ceo@thegenios.com` and you as *"waiting longest"* |
| Three or four modules decide "internal" three or four ways | `[CODE]` `context/runner._internal_emails` (seats + `orgs.email` + connection accounts, no domain rule); `context/support_situations._internal`; the outreach set; `_mailbox_owner_for`; the tenant-identity exclusion in `reason/runner.py:869-878, 907-909` |
| One mailbox only | `[PROD]` one Gmail connection; `ceo@thegenios.com` appears only as a recipient of your own mail |

## 2 · Why

*"Who is us"* sits under every judgment the expert makes: who owes the next move, who the target
is, whether a reply exists. Get it wrong once and every later step inherits the error.

## 3 · How

| # | Unit | Where | What |
|---|---|---|---|
| 3.1 | the identity service | new `platform/self_identity.py` | one function, `identity_for(conn, org_id) -> SelfIdentity`: seats and their emails; `orgs.email`; every connected account; every address the account sends **from**; the org's own non-public domains; and your declared list (3.2). Public mail domains (`gmail.com`, …) are never "us" as a domain — only as an exact address |
| 3.2 | your declared list | migration (next free number) `org_self_identities` | `(org_id, kind = address\|domain, value, declared_by, declared_at)`; seeded from D6 |
| 3.3 | one caller | the four modules in §1 | each calls `identity_for`. An AST guard (`tests/platform/test_one_answer_to_who_is_us.py`) fails if any module outside `platform/self_identity.py` builds an internal-address set itself — *check the AST, not the text* |
| 3.4 | threads name the other side | `context/backfill.py:601` | the thread's party is the oldest **non-self** correspondent |
| 3.5 | the repair | `scripts/repair_self_identity.py` (written by Claude, run by Harsh) | re-types the service and company nodes, renames threads anchored on you, retires the signals and cards whose subject is you — **each retirement writes a `card_event`** |
| 3.6 | the card guard | `deliver/card_builder.py` (and `STEP-14`'s contract check) | a card whose subject or recipient is us is refused, with a reason |

⛔ **Keep `7075014c`'s exception.** On `harsh/mvp`, a `dependency_stated` card may be grounded on
*your own* sentence — *"the sentence is the situation"*. Your words may be the evidence; you may
never be the person to chase.

## 4 · What will happen

| | Today | After |
|---|---|---|
| Manik's 8 Aug ask | *"Send Mr Rohit Swerashi your traction metrics"* | subject: Manik, Titan · owner: you · *"Manik asked for ___ on 8 Aug; you have not sent it"* |
| The offer to Khushi | *"…ceo@thegenios.com and Mr Rohit Swerashi have been waiting longest"* | Khushi is the counterparty; your two addresses are you |

## 5 · Expected

- 0 cards whose subject or recipient is one of your addresses or domains;
- 0 threads anchored on you;
- `ceo@thegenios.com` and `thegenios.com` typed as *us*;
- every *"waiting on you"* check reads all connected mailboxes.

## 6 · Verify

```
.venv/bin/python -m pytest tests/platform/test_one_answer_to_who_is_us.py -q
#   a fixture org with two founder addresses and a company domain; each of the four former
#   implementations, called through the service, agrees; the AST guard rejects a fifth
# production, read-only, after the repair:
#   cards whose business_subject or assignee resolves to a self identity → 0
```

## 7 · Risks

| Risk | Guard |
|---|---|
| A shared domain (a co-founder's company) marked as us by mistake | domains are only ever *declared*, never inferred |
| The repair retires a card you still wanted | every retirement is a `card_event` with its cause, so it can be audited and rebuilt |
