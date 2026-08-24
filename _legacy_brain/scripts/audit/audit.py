"""
Genios MVP audit — probes the live brain and refreshes docs/analysis/GENIOS_MVP_ANALYSIS.md.

What it does:
  1. Reads scripts/audit/audit_probes.yaml (declarative check list).
  2. Hits /v1/context (and any endpoint probes) against your running brain.
  3. Evaluates each probe's assertion → status (met / missed / error).
  4. Rewrites the <!-- auto:* --> sections of docs/analysis/GENIOS_MVP_ANALYSIS.md.
  5. Appends a run record to scripts/audit/audit_history.jsonl for diffing.

Usage:
    python3 scripts/audit/audit.py                # use .env defaults
    GENIOS_BASE_URL=https://api.genios.ai python3 scripts/audit/audit.py

Config (env or sdks/mcp/.env):
    GENIOS_BASE_URL   default http://localhost:8000
    GENIOS_API_KEY    required
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent  # genios-brain/
HERE = Path(__file__).resolve().parent  # scripts/audit/
MD_PATH = ROOT / "docs" / "analysis" / "GENIOS_MVP_ANALYSIS.md"
PROBES_PATH = HERE / "audit_probes.yaml"
HISTORY_PATH = HERE / "audit_history.jsonl"

# Pick up the MCP server's .env first (base URL + key are already there)
load_dotenv(ROOT / "sdks" / "mcp" / ".env")
load_dotenv()

BASE_URL = os.getenv("GENIOS_BASE_URL", "http://localhost:8000").rstrip("/")
API_KEY = os.getenv("GENIOS_API_KEY")

STATUS_ICONS = {"met": "✅", "missed": "❌", "partial": "⚠️", "buggy": "🐛", "unknown": "?"}


def _headers() -> dict:
    if not API_KEY:
        raise RuntimeError("GENIOS_API_KEY not set. Configure it in sdks/mcp/.env or env.")
    return {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}


def _request_with_retry(method: str, url: str, **kwargs) -> tuple[dict, int]:
    """Do one request with up to 2 backoff retries on HTTP 429."""
    last_status = 0
    for attempt, wait in enumerate([0, 8, 20]):
        if wait:
            time.sleep(wait)
        try:
            r = requests.request(method, url, **kwargs)
        except requests.exceptions.RequestException as e:
            return {"error": f"request failed: {e}"}, 0
        last_status = r.status_code
        if r.status_code != 429:
            if r.headers.get("content-type", "").startswith("application/json"):
                return r.json(), r.status_code
            return {"error": r.text[:300]}, r.status_code
    return {"error": "rate-limited after 2 retries"}, last_status


def _call_context(entity: str, situation: str = "") -> tuple[dict, int]:
    # Use a dedicated agent_id so the audit has its own rate-limit bucket,
    # separate from MCP/Claude/dashboard traffic.
    payload = {"entity": entity, "agent_id": "audit-script"}
    if situation:
        payload["situation"] = situation
    return _request_with_retry(
        "POST", f"{BASE_URL}/v1/context", json=payload, headers=_headers(), timeout=20,
    )


def _call_endpoint(path: str) -> tuple[dict, int]:
    return _request_with_retry("GET", f"{BASE_URL}{path}", headers=_headers(), timeout=10)


def _eval_assertion(expr: str, response: dict) -> tuple[bool | None, str | None]:
    """Safely evaluate the probe assertion. Returns (result, error)."""
    try:
        result = bool(eval(expr, {"r": response, "__builtins__": {}}, {"isinstance": isinstance, "bool": bool, "len": len, "set": set, "lambda": lambda: None}))
        return result, None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _eval_assertion_safe(expr: str, response: dict) -> tuple[bool | None, str | None]:
    """Eval with a minimal but usable builtins dict — lambdas need some builtins."""
    safe_globals = {
        "__builtins__": {
            "isinstance": isinstance,
            "bool": bool,
            "len": len,
            "set": set,
            "dict": dict,
            "list": list,
            "str": str,
            "int": int,
            "float": float,
            "map": map,
            "filter": filter,
            "all": all,
            "any": any,
        }
    }
    try:
        result = eval(expr, safe_globals, {"r": response})
        return bool(result), None
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def run_probe(probe: dict, cache: dict) -> dict:
    """Execute a single probe. Reuses cached API responses when the same
    (contact, situation) has already been fetched in this run — keeps the
    total request count low enough to stay under per-minute limits."""
    pid = probe["id"]
    ptype = probe["type"]

    response: dict = {}
    http_status = 0
    latency_ms = 0

    t0 = time.time()
    if ptype == "endpoint":
        key = ("GET", probe["target"])
        if key in cache:
            response, http_status = cache[key]
        else:
            response, http_status = _call_endpoint(probe["target"])
            cache[key] = (response, http_status)
    elif ptype in ("field", "behavior"):
        key = ("CTX", probe["contact"], probe.get("situation", ""))
        if key in cache:
            response, http_status = cache[key]
        else:
            response, http_status = _call_context(probe["contact"], probe.get("situation", ""))
            cache[key] = (response, http_status)
    latency_ms = int((time.time() - t0) * 1000)

    # ── Decide status by looking at transport FIRST ─────────────────────────
    # This prevents false positives: if the API didn't return a usable body,
    # the assertion can accidentally pass on missing fields. Don't even eval.
    if http_status == 0:
        return {
            "id": pid, "capability": probe["capability"], "expected": probe["expected"],
            "status": "unknown", "detail": response.get("error", "network failure"),
            "http_status": 0, "latency_ms": latency_ms,
        }
    if http_status == 429:
        return {
            "id": pid, "capability": probe["capability"], "expected": probe["expected"],
            "status": "unknown", "detail": "rate-limited (HTTP 429)",
            "http_status": 429, "latency_ms": latency_ms,
        }
    if http_status >= 500:
        return {
            "id": pid, "capability": probe["capability"], "expected": probe["expected"],
            "status": "buggy", "detail": f"HTTP {http_status}",
            "http_status": http_status, "latency_ms": latency_ms,
        }

    # For field/behavior probes that need a bundle, refuse to eval if the
    # bundle came back empty or as an error envelope — otherwise a missing
    # field looks indistinguishable from a field that correctly holds None.
    if ptype in ("field", "behavior"):
        if response.get("error") or "entity" not in response:
            return {
                "id": pid, "capability": probe["capability"], "expected": probe["expected"],
                "status": "unknown",
                "detail": f"no entity in response (HTTP {http_status}) — cannot judge",
                "http_status": http_status, "latency_ms": latency_ms,
            }

    assertion_expr = probe.get("assertion", "").strip()
    passed, err = _eval_assertion_safe(assertion_expr, response)

    if err is not None:
        status = "missed"
        detail = f"assertion error: {err}"
    elif passed:
        status = "met"
        detail = None
    else:
        status = "missed"
        detail = None

    return {
        "id": pid,
        "capability": probe["capability"],
        "expected": probe["expected"],
        "status": status,
        "detail": detail,
        "http_status": http_status,
        "latency_ms": latency_ms,
    }


def render_reality(results: list[dict], counts: dict, base_url: str) -> str:
    lines = [f"- **Brain:** `{base_url}`"]
    lines.append(f"- **Probes run:** {len(results)}")
    lines.append(f"- **Met:** {counts['met']} · **Missed:** {counts['missed']} · **Buggy:** {counts['buggy']} · **Unknown:** {counts['unknown']}")
    met_pct = int(100 * counts["met"] / max(1, len(results)))
    lines.append(f"- **Overall health:** {met_pct}% ({counts['met']}/{len(results)} capabilities met)")
    avg_latency = int(sum(r["latency_ms"] for r in results) / max(1, len(results)))
    lines.append(f"- **Average probe latency:** {avg_latency} ms")
    return "\n".join(lines)


def render_matrix(results: list[dict]) -> str:
    rows = ["| # | Capability | Expected | Status | Notes |", "|---|---|---|---|---|"]
    for i, r in enumerate(results, 1):
        icon = STATUS_ICONS.get(r["status"], "?")
        notes = r["detail"] or ("meets bar" if r["status"] == "met" else "—")
        cap = r["capability"].replace("|", "\\|")
        exp = r["expected"].replace("|", "\\|")
        notes_clean = str(notes).replace("|", "\\|")[:80]
        rows.append(f"| {i} | {cap} | {exp} | {icon} | {notes_clean} |")
    return "\n".join(rows)


def replace_block(md: str, tag: str, new_content: str) -> str:
    pattern = re.compile(
        rf"(<!-- auto:{tag}_start -->)(.*?)(<!-- auto:{tag}_end -->)",
        re.DOTALL,
    )
    replacement = rf"\1\n{new_content}\n\3"
    result, n = pattern.subn(replacement, md)
    if n == 0:
        raise RuntimeError(f"Marker <!-- auto:{tag}_start --> not found in {MD_PATH}")
    return result


def append_history(run_record: dict):
    HISTORY_PATH.parent.mkdir(exist_ok=True)
    with HISTORY_PATH.open("a") as f:
        f.write(json.dumps(run_record) + "\n")


def main():
    if not PROBES_PATH.exists():
        print(f"ERROR: {PROBES_PATH} not found.", file=sys.stderr)
        sys.exit(1)
    probes = yaml.safe_load(PROBES_PATH.read_text())["probes"]

    print(f"→ Running {len(probes)} probes against {BASE_URL} ...")
    results: list[dict] = []
    counts = {"met": 0, "missed": 0, "buggy": 0, "unknown": 0, "partial": 0}
    cache: dict = {}
    sleep_between = float(os.getenv("AUDIT_SLEEP_SECONDS", "1.5"))
    for i, probe in enumerate(probes):
        # Only sleep before calls that will actually hit the network.
        key_preview = (
            ("GET", probe["target"]) if probe["type"] == "endpoint"
            else ("CTX", probe["contact"], probe.get("situation", ""))
        )
        if i > 0 and sleep_between > 0 and key_preview not in cache:
            time.sleep(sleep_between)
        r = run_probe(probe, cache)
        results.append(r)
        counts[r["status"]] = counts.get(r["status"], 0) + 1
        icon = STATUS_ICONS.get(r["status"], "?")
        detail = f" — {r['detail']}" if r["detail"] else ""
        cache_marker = " (cached)" if key_preview in cache and r["latency_ms"] < 10 else ""
        print(f"  {icon} {r['id']:32s} [{r['latency_ms']:4d} ms]{detail}{cache_marker}")

    if not MD_PATH.exists():
        print(f"ERROR: {MD_PATH} not found.", file=sys.stderr)
        sys.exit(1)

    md = MD_PATH.read_text()
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    last_updated = (
        f"**Last auto-refresh:** {timestamp}\n"
        f"**Brain tested:** `{BASE_URL}`\n"
        f"**Reality signals captured:** {len(results)}"
    )
    reality = render_reality(results, counts, BASE_URL)
    matrix = render_matrix(results)

    md = replace_block(md, "last_updated", last_updated)
    md = replace_block(md, "reality", reality)
    md = replace_block(md, "matrix", matrix)
    MD_PATH.write_text(md)

    append_history({
        "timestamp": timestamp,
        "base_url": BASE_URL,
        "counts": counts,
        "results": results,
    })

    print()
    print(f"✓ Refreshed: {MD_PATH}")
    print(f"✓ History appended: {HISTORY_PATH}")
    print()
    print(f"Overall: {counts['met']}/{len(results)} met "
          f"({int(100 * counts['met'] / max(1, len(results)))}%)")


if __name__ == "__main__":
    main()
