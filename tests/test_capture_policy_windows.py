"""P1 leftover · the server's privacy gate knows Windows apps.

The Windows device sends the executable name as its bundle id. The server list held only macOS
bundle ids, so a terminal or password manager session from Windows passed the server gate.
"""

from __future__ import annotations

import pytest

from genios_engine.platform.capture_policy import bundle_blocked, is_blocked


@pytest.mark.parametrize("exe", [
    "cmd.exe", "WindowsTerminal.exe", "pwsh.exe", "Code.exe", "cursor.exe", "idea64.exe",
    "1Password.exe", "KeeperPasswordManager.exe", "consent.exe", "LockApp.exe", "genios.exe",
])
def test_windows_sensitive_apps_are_blocked_whatever_the_case(exe):
    assert bundle_blocked(exe) is True
    assert is_blocked(None, exe, {}) is True


@pytest.mark.parametrize("exe", ["chrome.exe", "msedge.exe", "slack.exe", "notepad.exe",
                                 "outlook.exe"])
def test_ordinary_windows_apps_are_not_blocked(exe):
    assert bundle_blocked(exe) is False


def test_mac_bundle_ids_still_match_exactly():
    assert bundle_blocked("com.apple.Terminal") is True
    assert bundle_blocked("com.jetbrains.pycharm") is True
    assert bundle_blocked("com.google.Chrome") is False
