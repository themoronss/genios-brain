"""The `li:` handle rule exists twice on purpose: capture may not import platform/context layers, so
`capture/screen/render.py` keeps its own copy of the SCREEN_INTEL_P2_BUILD.md §3.2 rule. Two copies
of one rule drift silently — this pins them to the same output, so a sender rendered at capture time
always lands on the same person node identity resolves later."""
import pytest

from genios_engine.capture.screen import render
from genios_engine.platform import identity

URLS = [
    "https://www.linkedin.com/in/priyashah",
    "https://www.linkedin.com/in/priyashah/",
    "https://linkedin.com/in/PriyaShah",
    "http://www.linkedin.com/in/priyashah?utm_source=share&miniProfileUrn=x",
    "https://in.linkedin.com/in/priya-shah-12ab34/",
    "https://www.linkedin.com/in/priyashah#experience",
    "www.linkedin.com/in/priyashah",
    "https://www.linkedin.com/in/priya%C5%A1ah/",
    "https://www.linkedin.com/company/acme",
    "https://www.linkedin.com/messaging/thread/abc/",
    "https://example.com/in/priyashah",
    "",
    None,
]


@pytest.mark.parametrize("url", URLS)
def test_norm_linkedin_url_matches_identity(url):
    assert render.norm_linkedin_url(url) == identity.norm_linkedin_url(url)


@pytest.mark.parametrize("url", URLS)
def test_linkedin_handle_matches_identity(url):
    assert render.linkedin_handle(url) == identity.linkedin_handle(url)
