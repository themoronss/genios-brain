"""The corpus is runtime data, and the deploy image has to contain it.

`platform/corpus.authored_domains()` opens with `if not root.is_dir(): return`. That is the right
behaviour for a checkout that legitimately has no corpus — but it means an IMAGE without the
directory yields nothing, logs nothing and raises nothing. `packs/wiring.make_registry` then
registers only the four hand-written Python packs, every authored capability compiles to nothing,
and `admin` and `customer_support` — which carry no legacy rules by design — go dark entirely
while the tenant's activation switches all read LIVE.

There is no unit test that can see this, because every test runs from a checkout where the
directory is present. So this one reads the Dockerfile.
"""
from __future__ import annotations

import pathlib

import pytest

pytestmark = pytest.mark.unit

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _dockerfile() -> str:
    return (ROOT / "Dockerfile").read_text()


def test_the_dockerfile_copies_the_authored_corpus():
    body = _dockerfile()
    copied = any(
        line.startswith("COPY") and "Domain Expertise" in line
        for line in body.splitlines())
    assert copied, (
        "the deploy image does not COPY 'Domain Expertise' — authored_domains() will yield "
        "nothing in production, silently, and the admin/customer_support lanes will publish "
        "nothing while their switches read LIVE")


def test_the_corpus_that_would_be_copied_actually_exists_and_is_tracked():
    """A COPY line for a directory that is not in the build context fails the build, not the run —
    so assert the directory is really there and really has domains in it."""
    from genios_engine.platform.corpus import authored_domains, corpus_root

    assert corpus_root().is_dir(), f"{corpus_root()} is missing from the checkout"
    domains = sorted(d for d, _ in authored_domains())
    assert domains, "the corpus directory exists but yields no domains"
    for required in ("admin", "customer_support", "sales"):
        assert required in domains, f"authored domain '{required}' is gone: {domains}"


def test_the_test_suite_is_still_kept_out_of_the_image():
    """The reason the corpus was excluded was true of `tests/` and only of `tests/` — conftest
    carries scratch database URLs. Copying the corpus must not have relaxed that."""
    body = _dockerfile()
    assert not any(line.startswith("COPY") and " tests" in f" {line} "
                   for line in body.splitlines()), \
        "the image is shipping tests/ — tests/conftest.py carries scratch database URLs"
