"""P6 §3.7 egress guard — hermetic (resolver injected; literal IPs never touch DNS)."""
from __future__ import annotations

import socket

import pytest
from fastapi import HTTPException

from genios_engine.platform.egress import EgressRefused, check_url, pinned_request

PUBLIC = "93.184.215.14"


def _res(*ips):
    return lambda host, port: list(ips)


@pytest.mark.parametrize("url,code", [
    ("https://10.0.0.1/hook", "private_address"),
    ("https://192.168.1.5/hook", "private_address"),
    ("https://169.254.169.254/latest/meta-data/", "metadata_address"),
    ("https://[fd00:ec2::254]/", "metadata_address"),
    ("https://169.254.10.10/", "link_local_address"),
    ("https://100.64.1.2/", "cgnat_address"),
    ("https://224.0.0.1/", "multicast_address"),
    ("https://[::ffff:10.0.0.1]/", "private_address"),
    ("https://127.0.0.2/", "loopback_address"),
])
def test_non_public_addresses_are_refused(url, code):
    with pytest.raises(EgressRefused) as e:
        check_url(url, env="prod", resolver=_res(PUBLIC))
    assert e.value.code == code


def test_plain_http_to_a_public_host_is_refused_in_prod_and_dev():
    for env in ("prod", "dev"):
        with pytest.raises(EgressRefused) as e:
            check_url("http://evil.example/hook", env=env, resolver=_res(PUBLIC))
        assert e.value.code == "https_required"


def test_a_hostname_resolving_to_a_private_address_is_refused():
    with pytest.raises(EgressRefused) as e:
        check_url("https://hooks.evil.example/x", env="prod", resolver=_res("10.1.2.3"))
    assert e.value.code == "private_address"
    # one private answer among public ones is enough to refuse (the connect could pick it)
    with pytest.raises(EgressRefused):
        check_url("https://hooks.evil.example/x", env="prod", resolver=_res(PUBLIC, "172.16.0.9"))


def test_localhost_only_in_dev():
    for url in ("http://localhost:8080/hook", "http://127.0.0.1:9000/", "https://[::1]/"):
        assert check_url(url, env="dev").addresses == ()
        with pytest.raises(EgressRefused) as e:
            check_url(url, env="prod")
        assert e.value.code == "loopback_address"


def test_public_https_passes_with_the_checked_addresses():
    t = check_url("https://agent.client.example:8443/genios?x=1", env="prod", resolver=_res(PUBLIC))
    assert t.addresses == (PUBLIC,) and t.port == 8443 and t.host == "agent.client.example"


@pytest.mark.parametrize("url,code", [
    ("https://user:pw@agent.client.example/", "userinfo_not_allowed"),
    ("ftp://agent.client.example/", "scheme_not_allowed"),
    ("", "url_missing"),
    ("https:///nohost", "url_invalid"),
])
def test_malformed_urls_are_refused(url, code):
    with pytest.raises(EgressRefused) as e:
        check_url(url, env="prod", resolver=_res(PUBLIC))
    assert e.value.code == code


def test_unresolvable_host_is_refused():
    def boom(host, port):
        raise socket.gaierror("nodename nor servname provided")
    with pytest.raises(EgressRefused) as e:
        check_url("https://nope.invalid/", env="prod", resolver=boom)
    assert e.value.code == "dns_unresolvable"


def test_pinned_request_connects_to_the_checked_ip_and_keeps_the_name():
    t = check_url("https://agent.client.example:8443/genios?x=1", env="prod", resolver=_res(PUBLIC))
    url, headers, ext = pinned_request(t)
    assert url == f"https://{PUBLIC}:8443/genios?x=1"
    assert headers == {"Host": "agent.client.example:8443"}
    assert ext == {"sni_hostname": "agent.client.example"}
    t6 = check_url("https://agent.client.example/a", env="prod",
                   resolver=_res("2606:4700:90c5:72db:f20c:aff:ef6b:ff98"))
    assert pinned_request(t6)[0] == "https://[2606:4700:90c5:72db:f20c:aff:ef6b:ff98]/a"


def test_registration_uses_the_guard():
    from genios_engine.api.agent_mgmt_routes import _clean_webhook_url
    assert _clean_webhook_url("") is None
    for url, code in (("https://10.0.0.1/x", "private_address"),
                      ("https://169.254.169.254/", "metadata_address"),
                      ("http://evil.example/x", "https_required")):
        with pytest.raises(HTTPException) as e:
            _clean_webhook_url(url)
        assert e.value.status_code == 422 and e.value.detail["code"] == code
