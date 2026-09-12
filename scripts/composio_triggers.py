"""Wire Composio's Gmail push to the engine: one GMAIL_NEW_GMAIL_MESSAGE trigger per ACTIVE Gmail
connected account, and ONE project webhook subscription pointing at the engine's
`POST /webhooks/composio` (api/routes.composio_webhook; the router is mounted without a prefix).

DRY-RUN BY DEFAULT. Without `--apply` this makes READ-ONLY calls only (list connected accounts,
list active trigger instances, read the trigger type, read the webhook subscription) and prints
what it would change. Nothing is created, updated or deleted until `--apply` is passed.

Idempotent: an account that already has an ENABLED instance of the trigger is left alone; the
subscription is created once and patched (URL / events) thereafter.

    # 1 · look (read-only)
    GENIOS_COMPOSIO_API_KEY=... python scripts/composio_triggers.py \\
        --base-url https://squid-app-2zuqf.ondigitalocean.app
    # 2 · do it
    GENIOS_COMPOSIO_API_KEY=... python scripts/composio_triggers.py \\
        --base-url https://squid-app-2zuqf.ondigitalocean.app --apply

The webhook SIGNING SECRET is returned by Composio when the subscription is CREATED; the script
prints it once. Set it on the engine as GENIOS_COMPOSIO_WEBHOOK_SECRET — the webhook refuses
every delivery outside dev until it is set (403), and verifies every signature once it is.
A subscription that already exists does not hand its secret back; `--rotate-secret` (with
`--apply`) deletes and recreates it to obtain a fresh one — the old secret stops verifying at once.

Uses the Composio v3.1 REST API with `x-api-key` (the paths the installed SDK uses:
composio/core/models/triggers.py, composio_client/resources/*).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any

import httpx

API = os.environ.get("COMPOSIO_BASE_URL", "https://backend.composio.dev").rstrip("/")
TRIGGER = "GMAIL_NEW_GMAIL_MESSAGE"
TRIGGER_CONFIG = {"interval": 1, "labelIds": "INBOX"}          # poll every minute, inbox only
WEBHOOK_PATH = "/webhooks/composio"
SUBSCRIPTIONS = "/api/v3.1/webhook_subscriptions"
EVENTS = ["composio.trigger.message"]                          # the SDK's default V3 event
VERSION = "V3"


def _api_key() -> str:
    key = os.environ.get("GENIOS_COMPOSIO_API_KEY", "").strip()
    if key:
        return key
    try:                                    # the engine's own settings (reads .env) as a fallback
        from genios_engine.platform.config import get_settings
        return get_settings().composio_api_key.strip()
    except Exception:      # noqa: BLE001
        return ""


class Composio:
    def __init__(self, key: str) -> None:
        self._http = httpx.Client(base_url=API, headers={"x-api-key": key}, timeout=30.0)

    def get(self, path: str, **params: Any) -> Any:
        r = self._http.get(path, params={k: v for k, v in params.items() if v is not None})
        r.raise_for_status()
        return r.json()

    def send(self, method: str, path: str, body: dict | None = None) -> Any:
        r = self._http.request(method, path, json=body)
        r.raise_for_status()
        return r.json() if r.content else {}

    def paged(self, path: str, **params: Any) -> list[dict]:
        items: list[dict] = []
        cursor = None
        for _ in range(100):                                    # bounded: 100 pages × 100
            page = self.get(path, limit=100, cursor=cursor, **params)
            items.extend(page.get("items") or [])
            cursor = page.get("next_cursor")
            if not cursor:
                break
        return items


def _toolkit(acct: dict) -> str:
    tk = acct.get("toolkit") or {}
    return (tk.get("slug") if isinstance(tk, dict) else str(tk or "")).lower()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--base-url", required=True,
                    help="public engine URL, e.g. https://squid-app-2zuqf.ondigitalocean.app")
    ap.add_argument("--user-id", action="append", default=[],
                    help="only these Composio user ids (= GeniOS org ids); repeatable")
    ap.add_argument("--apply", action="store_true", help="make the changes (default: dry-run)")
    ap.add_argument("--rotate-secret", action="store_true",
                    help="with --apply: delete + recreate the subscription to get a new secret")
    args = ap.parse_args(argv)

    key = _api_key()
    if not key:
        print("GENIOS_COMPOSIO_API_KEY is not set", file=sys.stderr)
        return 2
    if args.rotate_secret and not args.apply:
        print("--rotate-secret needs --apply", file=sys.stderr)
        return 2
    webhook_url = args.base_url.rstrip("/") + WEBHOOK_PATH
    mode = "APPLY" if args.apply else "DRY-RUN (read-only; pass --apply to change anything)"
    print(f"mode: {mode}\ncomposio: {API}\nwebhook: {webhook_url}\n")
    c = Composio(key)

    # ── the trigger type exists and takes the config we send ─────────────────────────────────
    ttype = c.get(f"/api/v3.1/triggers_types/{TRIGGER}")
    props = ((ttype.get("config") or {}).get("properties") or {})
    unknown = sorted(set(TRIGGER_CONFIG) - set(props)) if props else []
    print(f"trigger type {TRIGGER}: config fields {sorted(props) or '(schema not returned)'}")
    if unknown:
        print(f"  WARNING: config keys {unknown} are not in the trigger's schema")

    # ── ACTIVE gmail accounts ────────────────────────────────────────────────────────────────
    accounts = [a for a in c.paged("/api/v3.1/connected_accounts", toolkit_slugs="gmail",
                                   statuses="ACTIVE",
                                   user_ids=",".join(args.user_id) or None)
                if a.get("status") == "ACTIVE" and _toolkit(a) == "gmail"
                and not a.get("is_disabled")]
    print(f"\nACTIVE gmail connected accounts: {len(accounts)}")

    # ── which already have the trigger (disabled ones count as missing: upsert re-enables) ───
    existing = c.paged("/api/v3.1/trigger_instances/active", trigger_names=TRIGGER,
                       show_disabled="true")
    enabled_for = {}
    for inst in existing:
        acct = inst.get("connected_account_id") or inst.get("connectedAccountId")
        if acct and not (inst.get("disabled_at") or inst.get("disabledAt")):
            enabled_for[acct] = inst
    missing = []
    for a in accounts:
        inst = enabled_for.get(a["id"])
        if inst:
            cfg = inst.get("trigger_config") or inst.get("triggerConfig") or {}
            note = "" if cfg.get("interval") in (1, "1") else "  (interval is not 1 min)"
            print(f"  ok       {a['id']}  user={a.get('user_id')}  trigger={inst.get('id')}  "
                  f"config={json.dumps(cfg)}{note}")
        else:
            missing.append(a)
            print(f"  MISSING  {a['id']}  user={a.get('user_id')}")

    for a in missing:
        if not args.apply:
            print(f"  would create {TRIGGER} {json.dumps(TRIGGER_CONFIG)} for {a['id']}")
            continue
        out = c.send("POST", f"/api/v3.1/trigger_instances/{TRIGGER}/upsert",
                     {"connected_account_id": a["id"], "trigger_config": TRIGGER_CONFIG})
        print(f"  created  {a['id']} → trigger {out.get('trigger_id') or out.get('id') or out}")

    # ── the project webhook subscription ────────────────────────────────────────────────────
    subs = c.get(SUBSCRIPTIONS, limit=10).get("items") or []
    current = subs[0] if subs else None
    body = {"webhook_url": webhook_url, "enabled_events": EVENTS, "version": VERSION}
    print(f"\nwebhook subscriptions: {len(subs)}")
    if current:
        print(f"  current  id={current.get('id')}  url={current.get('webhook_url')}  "
              f"events={current.get('enabled_events')}  version={current.get('version')}")
    secret = None
    if current is None:
        if args.apply:
            secret = c.send("POST", SUBSCRIPTIONS, body).get("secret")
            print("  created subscription")
        else:
            print(f"  would create {json.dumps(body)}")
    elif args.rotate_secret:
        c.send("DELETE", f"{SUBSCRIPTIONS}/{current['id']}")
        secret = c.send("POST", SUBSCRIPTIONS, body).get("secret")
        print("  recreated subscription (secret rotated)")
    elif (current.get("webhook_url") != webhook_url
          or sorted(current.get("enabled_events") or []) != sorted(EVENTS)
          or str(current.get("version") or "").upper() != VERSION):
        if args.apply:
            secret = c.send("PATCH", f"{SUBSCRIPTIONS}/{current['id']}", body).get("secret")
            print("  updated subscription")
        else:
            print(f"  would update to {json.dumps(body)}")
    else:
        print("  subscription already points at the engine")

    if secret:
        print("\nSET THIS ON THE ENGINE (shown once):\n"
              f"  GENIOS_COMPOSIO_WEBHOOK_SECRET={secret}")
    elif args.apply:
        print("\nNo secret returned (Composio only returns it on creation). If the engine does "
              "not already have GENIOS_COMPOSIO_WEBHOOK_SECRET, re-run with --apply --rotate-secret.")
    print(f"\nsummary: {len(accounts)} account(s), {len(missing)} missing a trigger"
          f"{' — created' if args.apply and missing else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
