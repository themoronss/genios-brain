"""P4 · the admin domain's tools are work apps; HR tools stay blocked.

A work host's pages go to extraction without an extra AI relevance check. Adding a host must
never unblock anything: login pages keep their sensitive path markers, and HR/payroll tools
(including Zoho People/Payroll, whose parent zoho.com is a work host) stay blocked.
"""

from __future__ import annotations

import pytest

from genios_engine.capture.screen.relevance import _work_bundle, _work_host, rule_verdict
from genios_engine.platform.capture_policy import SENSITIVE_DOMAINS, url_block_reason

ADMIN_HOSTS = [
    "zoom.us", "meet.google.com", "teams.microsoft.com", "adobesign.com", "echosign.com",
    "spotdraft.com", "leegality.com", "ariba.com", "coupahost.com", "netsuite.com",
    "concursolutions.com", "fylehq.com", "expensify.com", "happay.com", "happay.in",
    "freshservice.com", "service-now.com", "mca.gov.in", "gst.gov.in", "epfindia.gov.in",
    "diligent.com", "mybiz.makemytrip.com", "navan.com", "travelperk.com", "snipe-it.io",
    "assetpanda.com", "typeform.com",
]


@pytest.mark.parametrize("host", ADMIN_HOSTS)
def test_admin_tools_are_work_hosts_and_not_blocked(host):
    assert _work_host(host) and _work_host("app." + host)
    assert url_block_reason(f"https://app.{host}/dashboard", SENSITIVE_DOMAINS) is None
    assert rule_verdict({"host": host}).reason == "work_host"


def test_login_pages_of_work_hosts_stay_blocked():
    assert url_block_reason("https://system.netsuite.com/login", SENSITIVE_DOMAINS) is not None


def test_consumer_travel_is_not_a_work_host():
    assert not _work_host("www.makemytrip.com")


@pytest.mark.parametrize("url", ["https://people.zoho.com/acme/home", "https://people.zoho.in/x",
                                 "https://payroll.zoho.in/app", "https://acme.keka.com/leave"])
def test_hr_tools_stay_blocked(url):
    assert url_block_reason(url, SENSITIVE_DOMAINS) is not None


@pytest.mark.parametrize("exe", ["EXCEL.EXE", "winword.exe", "ms-teams.exe", "TallyPrime.exe",
                                 "tally.exe"])
def test_windows_work_apps_match_case_insensitively(exe):
    assert _work_bundle(exe)


def test_ordinary_windows_apps_are_not_work_apps():
    assert not _work_bundle("notepad.exe") and not _work_bundle("chrome.exe")


def test_mac_bundles_still_match():
    assert _work_bundle("com.microsoft.Excel") and not _work_bundle("com.apple.Safari")
