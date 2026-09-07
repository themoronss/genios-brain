"""The deploy image can read a scanned document, and says the same thing the Procfile does.

    pytest tests/test_deploy_image.py -q

`enable_ocr` has been a settings flag since L1.3.4 and turning it on has never produced OCR: the
buildpack image has no `tesseract` binary and no `poppler` rasterizer, so the flag's only effect
would have been to send every scanned attachment down a branch that fails. 767 parked attachments
in production are the cost of that gap, and a `Dockerfile` is the only thing that closes it —
App Platform buildpacks cannot install apt packages.

These are checks on the DEPLOY CONTRACT, not on Docker: they cannot build an image and do not try.
What they catch is the two ways this file goes stale — a binary quietly dropped from the install
line while `enable_ocr` stays true, and the image's start command drifting away from the one the
Procfile declares, which is how staging and production end up running two different servers.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "Dockerfile"
PROCFILE = ROOT / "Procfile"


@pytest.fixture(scope="module")
def dockerfile() -> str:
    if not DOCKERFILE.exists():
        pytest.fail("Dockerfile is gone — with it, GENIOS_ENABLE_OCR=true is a flag that only "
                    "produces ocr_failed, and every scanned document parks for ever")
    return DOCKERFILE.read_text()


@pytest.mark.parametrize("binary, why", [
    ("tesseract-ocr", "capture/documents/tesseract.py shells to it through pytesseract"),
    ("poppler-utils", "pdf2image needs it to rasterize a scanned PDF's pages"),
])
def test_the_image_installs_what_ocr_actually_needs(dockerfile, binary, why):
    assert binary in dockerfile, f"{binary} missing from the image — {why}"


def test_language_data_is_installed_beside_the_engine(dockerfile):
    """`tesseract-ocr` alone is a binary with no alphabet: it installs, it runs, and it reads
    nothing. The failure is silent — an empty OCR result is indistinguishable from a blank page."""
    assert "tesseract-ocr-eng" in dockerfile


def test_the_image_installs_the_locked_dependency_set(dockerfile):
    """`requirements-lock.txt`, not `requirements.txt`: the image that runs must be the set that
    was tested, and a range specifier resolves differently on the day a dependency ships."""
    assert "requirements-lock.txt" in dockerfile
    assert not re.search(r"pip install[^\n]*requirements\.txt", dockerfile)


def test_the_start_command_matches_the_procfile():
    """Two files, one server. The Procfile is what the buildpack runs and the Dockerfile CMD is
    what the image runs; a deploy that switches strategy must not also switch process."""
    proc = PROCFILE.read_text()
    docker = DOCKERFILE.read_text()
    for token in ("uvicorn", "genios_engine.main:app", "--host 0.0.0.0", "--port"):
        assert token in proc, f"Procfile no longer declares {token!r}"
        assert token in docker, f"Dockerfile CMD no longer declares {token!r}"


def test_the_test_suite_is_not_shipped_in_the_image(dockerfile):
    """`tests/conftest.py` resolves scratch database URLs and `.env` names production. An image
    that ships either is an image where a stray `pytest` reaches a paying tenant."""
    copied = re.findall(r"^COPY\s+([^\s]+)", dockerfile, re.MULTILINE)
    assert "tests" not in copied and "." not in copied, (
        f"the image copies {copied} — a blanket copy ships tests/ and .env with the server")


def test_ocr_is_still_off_by_default_after_the_image_can_do_it():
    """The image makes OCR POSSIBLE; it must not make it automatic. Turning it on stays two
    deliberate acts — a fleet flag and a tenant allowlist — per capture/documents/enablement.py."""
    from genios_engine.platform.config import Settings

    assert Settings.model_fields["enable_ocr"].default is False
