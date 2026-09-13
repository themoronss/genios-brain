"""P6 §1 / §7: GeniOS never writes to a provider. Nothing under `executive/` or `deliver/` may
import a connector (write) client — the client's own agent executes every action."""
from __future__ import annotations

import ast
from pathlib import Path

import genios_engine

ROOT = Path(genios_engine.__file__).parent
#: Connector clients live under capture/ (Composio, Gmail, calendar, trackers) or are provider SDKs.
FORBIDDEN_PREFIXES = ("genios_engine.capture", "composio", "googleapiclient", "google.oauth2",
                      "msal", "hubspot", "linear", "slack_sdk", "O365", "exchangelib")


def _imports(path: Path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            yield node.module


def test_act_layers_import_no_connector_write_client():
    bad = []
    for pkg in ("executive", "deliver"):
        for path in sorted((ROOT / pkg).rglob("*.py")):
            for mod in _imports(path):
                if mod.startswith(FORBIDDEN_PREFIXES) or "composio" in mod.lower():
                    bad.append(f"{path.relative_to(ROOT)} imports {mod}")
    assert not bad, bad


def test_the_boundary_scan_sees_the_act_modules():
    names = {p.name for p in (ROOT / "executive").glob("*.py")}
    assert {"delegation.py", "plays.py"} <= names
    assert (ROOT / "deliver" / "act_pump.py").exists()
