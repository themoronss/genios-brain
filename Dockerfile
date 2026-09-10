# GeniOS Engine — the image that can actually read a scanned document.
#
# WHY THIS FILE EXISTS. `enable_ocr` has been a settings flag since L1.3.4 and turning it on has
# never produced OCR, because the buildpack image the app deploys from has no `tesseract` binary
# and no `poppler` rasterizer. That is worse than the flag being off: `documents/router.py` would
# take the OCR branch, `pytesseract` would raise on the first scanned attachment, and a config
# change nobody could test would surface as a failed sync. The router now degrades instead of
# crashing (`ocr_failed`, with the reason), but a degraded read is still a document nobody read —
# 767 parked attachments in production and counting.
#
# So the fix is not a flag, it is an image. Two apt packages:
#
#   tesseract-ocr    the OCR engine `documents/tesseract.py` shells to through pytesseract
#   poppler-utils    the PDF rasterizer `pdf2image` needs to turn a scanned PDF into page images
#                    (`native._ocr_pdf_bytes`; without it that path returns `ocr_failed`)
#
# DEPLOY NOTE — READ BEFORE PUSHING. DigitalOcean App Platform prefers a Dockerfile over its
# buildpack the moment one exists at the component root, so the FIRST deploy after this file lands
# switches the build strategy. That is the intended change and it is not reversible by accident:
# the runtime command below is the same one `Procfile` declares, the Python version is pinned to
# the one the lock file was resolved against, and nothing else about the app moves. Enabling OCR
# itself is still two deliberate acts after that — `GENIOS_ENABLE_OCR=true` plus the org allowlist
# `GENIOS_OCR_ENABLED_ORGS`, per `capture/documents/enablement.py`.

FROM python:3.11-slim-bookworm

# tesseract-ocr-eng is the language data; the engine package alone reads nothing.
# --no-install-recommends keeps the image from pulling a desktop's worth of X11 for poppler.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        tesseract-ocr \
        tesseract-ocr-eng \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

# Requirements first, so a code change does not re-resolve the dependency tree.
#
# `requirements.txt`, not the old `requirements-lock.txt`. The lock was a `pip freeze` taken on
# a developer laptop and it could never have built here: it carried the line
#   -e /Users/<someone>/Desktop/geniosfull/genios-engine
# — an editable install of a path that does not exist in any image — so this RUN would fail on
# it. It had also drifted: no `python-multipart`, which is what parses the multipart body of
# `POST /api/org/{org}/upload`, so an image built from it could not accept a file at all.
# `requirements.txt` is fully pinned and is the file that is actually maintained; two
# dependency files is how the drift happened, so there is now one.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY genios_engine ./genios_engine
COPY migrations ./migrations
COPY scripts ./scripts
COPY pyproject.toml ./

# The engine reads its own version and nothing else from the tree; the corpus, the docs and the
# test suite are deliberately not copied — an image that ships them is an image that ships the
# scratch database URLs in `tests/conftest.py`.

EXPOSE 8080

# Identical to `Procfile`, so the two cannot drift into two different production commands.
CMD ["sh", "-c", "uvicorn genios_engine.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
