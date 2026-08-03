from __future__ import annotations

import json
import re


def strip_code_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1]
        if s.startswith("json"):
            s = s[4:]
        s = s.strip()
        if s.endswith("```"):
            s = s[:-3].strip()
    return s


def parse_json_lenient(raw: str) -> dict | None:
    """Strict json.loads, then minimal repair for Haiku's two real failure modes:
    trailing commas, and mid-array truncation at max_tokens. On truncation, rewind to
    the last consistent state (depth>0, not in a string, just after a closed value) and
    close the open brackets — drops the half-written tail, keeps every completed entry."""
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    cleaned = re.sub(r",\s*([\]}])", r"\1", raw)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    opens: list[str] = []
    in_string = escape = prev_value_close = False
    last_safe_idx = -1
    last_safe_opens: list[str] = []
    for i, ch in enumerate(cleaned):
        if escape:
            escape = False
            prev_value_close = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch == '"':
            if in_string:
                in_string = False
                prev_value_close = True
                if opens:
                    last_safe_idx, last_safe_opens = i, list(opens)
            else:
                in_string = True
                prev_value_close = False
            continue
        if in_string:
            continue
        if ch in "[{":
            opens.append(ch)
            prev_value_close = False
        elif ch in "]}":
            if opens and ((opens[-1] == "[" and ch == "]") or (opens[-1] == "{" and ch == "}")):
                opens.pop()
            prev_value_close = True
            if opens:
                last_safe_idx, last_safe_opens = i, list(opens)
        elif ch.isalnum() and prev_value_close is False:
            prev_value_close = True

    if last_safe_idx < 0:
        return None
    suffix = "".join("}" if o == "{" else "]" for o in reversed(last_safe_opens))
    try:
        return json.loads(cleaned[: last_safe_idx + 1] + suffix)
    except json.JSONDecodeError:
        return None
