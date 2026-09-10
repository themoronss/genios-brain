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
REQUIREMENTS = ROOT / "requirements.txt"
REQ_FILE_NAMES = [q.name for q in ROOT.glob("requirements*.txt")]


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


def test_the_image_installs_the_maintained_dependency_set(dockerfile):
    """One dependency file, and it is the one people edit.

    This used to assert the opposite — `requirements-lock.txt`, "the set that was actually
    tested". That lock was a `pip freeze` from a developer laptop and could never have built
    here: it carried `-e /Users/<someone>/Desktop/.../genios-engine`, an editable install of a
    path no image has, so this very RUN would have failed on it. It had also drifted past
    `python-multipart`, which is what parses `POST /api/org/{org}/upload` — an image built from
    it could not have accepted a file. Two dependency files is how that drift happened.
    """
    assert re.search(r"pip install[^\n]*requirements\.txt", dockerfile)
    assert REQ_FILE_NAMES == ["requirements.txt"], (
        f"more than one dependency file ({REQ_FILE_NAMES}) — that is how the image drifted "
        "out of sync with the code before")


def test_every_runtime_dependency_is_pinned():
    """A range specifier resolves differently on the day a dependency ships, which is the one
    property the deleted lock file was right to want. Kept, without the second file."""
    unpinned = []
    for line in REQUIREMENTS.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        if "==" not in line:
            unpinned.append(line)
    assert unpinned == ["razorpay>=1.4", "stripe>=7.0"], (
        f"unpinned runtime dependencies: {unpinned} — only the lazy-imported billing SDKs, "
        "which no request path imports unless billing is configured, may float")


def test_ocr_python_bindings_ship_with_the_ocr_binaries():
    """Both halves of OCR or neither.

    The apt packages went into the image while `pytesseract`, `Pillow` and `pdf2image` were in
    no requirements file. `tesseract_available()` probed only the binary, so it said yes, an
    engine was wired, and every scanned document came back `ocr_failed: ModuleNotFoundError` —
    a whole capability that reported as broken documents rather than as a missing dependency.
    """
    reqs = REQUIREMENTS.read_text().lower()
    for pkg, why in [("pytesseract", "the bindings tesseract.py imports"),
                     ("pillow", "pytesseract decodes the page image through PIL"),
                     ("pdf2image", "a scanned PDF is rasterised before it can be OCR'd")]:
        assert pkg in reqs, f"{pkg} missing from requirements.txt — {why}"


def test_office_parsers_ship_with_the_formats_the_dashboard_offers():
    """The upload UI offers these extensions; a parser that is not installed makes that offer a
    lie that surfaces as "No extractable text found in this file"."""
    reqs = REQUIREMENTS.read_text().lower()
    for pkg, fmt in [("openpyxl", ".xlsx"), ("xlrd", ".xls"), ("python-pptx", ".pptx"),
                     ("python-docx", ".docx"), ("pypdf", ".pdf")]:
        assert pkg in reqs, f"{pkg} missing from requirements.txt — {fmt} would not parse"


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


def test_ocr_is_on_by_default_now_that_both_halves_of_the_stack_ship():
    """This test asserted the opposite — "the image makes OCR POSSIBLE; it must not make it
    automatic" — and that was right while the stack was half-installed and a wired engine
    raised on its first call.

    Two things changed. The image now carries both halves (apt: tesseract-ocr,
    tesseract-ocr-eng, poppler-utils; pip: pytesseract, Pillow, pdf2image), and
    `tesseract_available()` checks both, so a host that cannot OCR wires nothing regardless of
    this flag — the failure mode the opt-in was protecting against is now impossible by
    construction rather than by policy.

    What the opt-in cost, meanwhile, was measurable: 767 of 776 attachments parked with
    readable pages, and an upload dialog that accepts a PNG and returns "no extractable text".
    Off is still reachable, per tenant, through `ocr_disabled_orgs`.
    """
    from genios_engine.platform.config import Settings

    assert Settings.model_fields["enable_ocr"].default is True


def test_a_host_without_the_ocr_stack_wires_no_engine_even_when_enabled():
    """The guarantee the default flip rests on. If this ever stops holding, `enable_ocr` must go
    back to False the same day: an engine wired on a host that cannot run it converts empty
    documents into failed ones, which is strictly worse than not reading them."""
    from genios_engine.capture.documents.enablement import resolve_ocr_availability

    decision = resolve_ocr_availability(org_id="org_1", global_enabled=True, allowlist=set(),
                                        denylist=set(), engine_present=False)
    assert decision.enabled is False
