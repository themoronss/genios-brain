# 🔑 Access — the scratch Postgres

## ⛔ 991 of 995 skipped tests are one environment variable

A skip is **not** a pass. Until this exists, every step in both layers ends with *"verified
hermetically, real-DB proof pending"* — and Layer 1's step-17 adversarial suite **cannot run at
all.**

```bash
export GENIOS_TEST_DATABASE_URL="postgres://..."
.venv/bin/python -m pytest -m pg -q
```

Any throwaway Postgres 15+ works.

⛔ **IT MUST NOT BE PRODUCTION.** The suite **drops and recreates the schema.**

> This one line closes the open half of Layer 1 steps 1, 2, 3 and 5 at once, and unblocks
> **618 tests**.

---

## The read-only path, for the measurements

The six scripts in [`01-measurements.md`](01-measurements.md) read production and never write.
That is enforced structurally, not by convention:

* the target resolves through `scripts/_db.py`, which has **no fallback to `Settings`** —
  *"nothing in the invocation names production; you get it by running the script at all"*;
* every statement in every one of them is a `select`;
* `scripts/_db.py` additionally requires `GENIOS_ALLOW_PROD_WRITE=1` before any write can reach a
  Supabase host, and none of these scripts writes.

```bash
export GENIOS_TARGET_DATABASE_URL="postgres://...supabase..."   # read-only use
```

**Do not set `GENIOS_ALLOW_PROD_WRITE`.** Nothing in this handoff needs it.
