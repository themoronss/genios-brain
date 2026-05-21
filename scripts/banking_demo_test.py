#!/usr/bin/env python3
"""
Banking demo — end-to-end isolation + cross-department context test.

Run this AFTER the agent-isolation fix is deployed. It provisions a banking
agent setup, seeds a small realistic dataset, and asserts that:
  * all four department agents share ONE customer brain (cross-department), and
  * a separately-scoped probe agent is correctly isolated.

Usage:
    export GENIOS_BASE_URL=https://squid-app-2zuqf.ondigitalocean.app
    export GENIOS_MASTER_KEY=gn_live_...        # org master / default_agent key
    python3 scripts/banking_demo_test.py

Cost: ~7-10 LLM calls total (small seed). Re-runnable — ingests are idempotent
on external_id; agents are reused (key rotated) if they already exist.

Exit code 0 = all checks passed, 1 = at least one failed.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get("GENIOS_BASE_URL", "").rstrip("/")
MASTER_KEY = os.environ.get("GENIOS_MASTER_KEY", "").strip()

if not BASE or not MASTER_KEY:
    sys.exit("Set GENIOS_BASE_URL and GENIOS_MASTER_KEY env vars first.")


def api(method: str, path: str, key: str, body: dict | None = None):
    """Minimal JSON HTTP call. Returns (status_code, parsed_json_or_text)."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}{path}", data=data, method=method)
    req.add_header("Authorization", f"Bearer {key}")
    if data:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=40) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except Exception:
            return e.code, raw
    except Exception as e:  # noqa: BLE001 - network/timeout surfaced to caller
        return 0, str(e)


def ensure_agent(slug: str, name: str, scope: dict) -> str:
    """Create the agent, or rotate its key if it already exists. Returns the key."""
    st, resp = api("POST", "/v1/agents", MASTER_KEY, {
        "agent_id": slug, "name": name,
        "description": "banking demo test agent", "scope": scope,
    })
    if st == 201:
        print(f"  created agent  {slug}")
        return resp["key"]
    if st == 409:
        st2, resp2 = api("POST", f"/v1/agents/{slug}/keys", MASTER_KEY, {"revoke_old": True})
        if st2 == 201:
            print(f"  reused agent   {slug} (key rotated)")
            return resp2["key"]
        sys.exit(f"  FAILED to rotate key for {slug}: {st2} {resp2}")
    sys.exit(f"  FAILED to create agent {slug}: {st} {resp}")


def ingest_email(agent_key: str, ext_id: str, from_addr: str, subject: str, body_text: str) -> None:
    st, resp = api("POST", "/v1/ingest/email", agent_key, {
        "external_id": ext_id,
        "from_address": from_addr,
        "to": ["desk@demobank.com"],
        "subject": subject,
        "body_text": body_text,
        "sent_at": "2026-05-21T10:00:00Z",
        "direction": "inbound",
    })
    tag = "deduped" if isinstance(resp, dict) and resp.get("deduped") else "new"
    state = "ok" if st in (200, 202) else f"ERROR {st} {resp}"
    print(f"  ingest {ext_id:22s} {from_addr:28s} -> {state} ({tag})")


# ── result tracking ──────────────────────────────────────────────────────────
PASSED: list[str] = []
FAILED: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    (PASSED if condition else FAILED).append(label)
    mark = "PASS" if condition else "FAIL"
    print(f"  [{mark}] {label}" + (f"  ({detail})" if detail else ""))


print(f"\nGeniOS banking demo test  ->  {BASE}\n")

# ── 1. Agents ────────────────────────────────────────────────────────────────
# Banking dept agents share one customer brain: data_visibility='all' +
# max_age_days high so they are fully unrestricted (cross-department context).
# The probe agent is data_visibility='own' to verify isolation enforcement.
print("1. Provisioning agents...")
SHARED = {"data_visibility": "all", "max_age_days": 3650, "min_confidence": 0.0}
PROBE = {"data_visibility": "own", "max_age_days": 3650, "min_confidence": 0.0}

sales = ensure_agent("bank_sales", "Bank Sales Agent", SHARED)
onboard = ensure_agent("bank_onboarding", "Bank Onboarding Agent", SHARED)
kyc = ensure_agent("bank_kyc", "Bank KYC Agent", SHARED)
support = ensure_agent("bank_support", "Bank Support Agent", SHARED)
probe = ensure_agent("iso_probe", "Isolation Probe", PROBE)

# ── 2. Seed — multi-department customer journeys ─────────────────────────────
print("\n2. Seeding banking customer data...")
ingest_email(onboard, "bank-anita-onb-1", "anita.desai@example.com",
             "New savings account opening",
             "I would like to open a savings account. Sharing my details for onboarding.")
ingest_email(kyc, "bank-anita-kyc-1", "anita.desai@example.com",
             "KYC documents for savings account",
             "Submitting PAN and Aadhaar for KYC verification of my new account.")
ingest_email(sales, "bank-rahul-sal-1", "rahul.mehta@example.com",
             "Interested in a premium credit card",
             "I saw your premium credit card offer. My credit score is 780. Interested.")
ingest_email(support, "bank-rahul-sup-1", "rahul.mehta@example.com",
             "Issue with credit card statement",
             "There is a discrepancy in my latest credit card statement. Please help.")
ingest_email(kyc, "bank-vikram-kyc-1", "vikram.rao@example.com",
             "KYC re-verification",
             "Reaching out for periodic KYC re-verification of my current account.")

# ── 3. Assertions ────────────────────────────────────────────────────────────
print("\n3. Running assertions...")

# Cross-department: Support agent never touched Anita, but shares the brain.
st, _ = api("POST", "/v1/context", support, {"entity": "anita.desai@example.com"})
check("Cross-dept: Support agent CAN see Anita (onboarded + KYC'd elsewhere)",
      st == 200, f"status {st}")

# Cross-department: KYC agent sees Rahul (a sales + support customer).
st, _ = api("POST", "/v1/context", kyc, {"entity": "rahul.mehta@example.com"})
check("Cross-dept: KYC agent CAN see Rahul (sales + support customer)",
      st == 200, f"status {st}")

# Isolation: probe agent (own scope, ingested nothing) must NOT see Anita.
st, _ = api("POST", "/v1/context", probe, {"entity": "anita.desai@example.com"})
check("Isolation: Probe agent CANNOT see Anita (expects 404 not_in_scope)",
      st == 404, f"status {st}")

# Isolation list: probe agent's contact list excludes banking customers.
st, resp = api("GET", "/v1/contacts?limit=100", probe)
listed = json.dumps(resp) if isinstance(resp, (dict, list)) else str(resp)
check("Isolation: Probe agent's /v1/contacts excludes banking customers",
      st == 200
      and "anita.desai@example.com" not in listed
      and "rahul.mehta@example.com" not in listed
      and "vikram.rao@example.com" not in listed,
      f"status {st}")

# Master key sees everything.
st, resp = api("GET", "/v1/contacts?limit=100", MASTER_KEY)
listed = json.dumps(resp) if isinstance(resp, (dict, list)) else str(resp)
check("Master key sees all banking customers",
      st == 200
      and "anita.desai@example.com" in listed
      and "rahul.mehta@example.com" in listed,
      f"status {st}")

# ── Summary ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 56)
print(f"RESULT: {len(PASSED)} passed, {len(FAILED)} failed")
if FAILED:
    for f in FAILED:
        print(f"  FAILED -> {f}")
    print("\nIf isolation checks failed, confirm the isolation fix is DEPLOYED.")
    sys.exit(1)
print("All banking isolation + cross-department checks passed.")
sys.exit(0)
