import asyncio
import requests
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.config import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET

DOCS_REDIRECT_URI = None  # Lazy-loaded

SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

# Minimum word count to index a document
MIN_WORD_COUNT = 150


def _get_redirect_uri():
    global DOCS_REDIRECT_URI
    if DOCS_REDIRECT_URI is None:
        import os
        DOCS_REDIRECT_URI = os.getenv("GOOGLE_DOCS_REDIRECT_URI", "")
    return DOCS_REDIRECT_URI


def create_docs_oauth_flow():
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
    )
    flow.redirect_uri = _get_redirect_uri()
    return flow


def build_docs_service(access_token, refresh_token=None):
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
    )
    return build("docs", "v1", credentials=creds)


def build_drive_service(access_token, refresh_token=None):
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
    )
    return build("drive", "v3", credentials=creds)


def get_docs_user_email(drive_service):
    about = drive_service.about().get(fields="user").execute()
    return about.get("user", {}).get("emailAddress")


def fetch_document_body(docs_service, doc_id):
    """
    Fetch document body content via Docs API v1.
    ALWAYS use suggestionsViewMode=PREVIEW_WITHOUT_SUGGESTIONS —
    never expose raw suggestion markup to the extraction pipeline.

    Signal taxonomy:
      - Never fetch revision history body — only current version
      - Use lastModifiedTime for staleness checks
    """
    doc = docs_service.documents().get(
        documentId=doc_id,
        suggestionsViewMode="PREVIEW_WITHOUT_SUGGESTIONS",
    ).execute()
    return doc


def fetch_document_comments(drive_service, doc_id, max_pages=5):
    """
    Fetch all comments from a document via Drive Comments API.
    CRITICAL: Paginate fully — loop nextPageToken until null.
    Hard limit: max_pages=5 (500 comments max) before truncation warning.

    Returns list of comment dicts.
    """
    comments = []
    page_token = None
    pages_fetched = 0

    while True:
        if pages_fetched >= max_pages:
            # Log truncation warning — document has > 500 comments
            import logging
            logging.warning(f"Doc {doc_id}: comment pagination truncated at {max_pages} pages")
            break

        params = {
            "fileId": doc_id,
            "fields": "comments(id,author,content,quotedFileContent,resolved,resolvedLastUpdateTime,replies),nextPageToken",
            "includeDeleted": False,
            "pageSize": 100,
        }
        if page_token:
            params["pageToken"] = page_token

        result = drive_service.comments().list(**params).execute()
        comments.extend(result.get("comments", []))
        page_token = result.get("nextPageToken")
        pages_fetched += 1

        if not page_token:
            break

    return comments


def fetch_document_and_comments_parallel(docs_service, drive_service, doc_id):
    """
    CRITICAL: Fetch document body AND comments simultaneously as two parallel operations.
    Both are REQUIRED before any processing — never process body without comments or vice versa.

    Returns (doc_body, comments) tuple.
    """
    # Use ThreadPoolExecutor for parallel API calls (both are I/O bound)
    from concurrent.futures import ThreadPoolExecutor, as_completed

    with ThreadPoolExecutor(max_workers=2) as executor:
        body_future = executor.submit(fetch_document_body, docs_service, doc_id)
        comments_future = executor.submit(fetch_document_comments, drive_service, doc_id)

        doc_body = body_future.result()
        comments = comments_future.result()

    return doc_body, comments


def traverse_structural_elements(content):
    """
    Parse Docs API structural elements into plain text with structure preserved.
    Returns list of {type, heading_level, text} dicts for chunking.

    Handles: paragraphs, tables (cell-by-cell), section breaks.
    Skips: images, inline objects, footnotes.
    """
    body = content.get("body", {})
    elements = body.get("content", [])
    result = []

    for element in elements:
        if "paragraph" in element:
            para = element["paragraph"]
            style = para.get("paragraphStyle", {}).get("namedStyleType", "NORMAL_TEXT")
            text = _extract_paragraph_text(para)

            if not text.strip():
                continue

            heading_level = None
            if style == "HEADING_1":
                heading_level = 1
            elif style == "HEADING_2":
                heading_level = 2
            elif style == "HEADING_3":
                heading_level = 3

            result.append({
                "type": "paragraph",
                "heading_level": heading_level,
                "text": text.strip(),
            })

        elif "table" in element:
            table = element["table"]
            for row in table.get("tableRows", []):
                for cell in row.get("tableCells", []):
                    for cell_element in cell.get("content", []):
                        if "paragraph" in cell_element:
                            text = _extract_paragraph_text(cell_element["paragraph"])
                            if text.strip():
                                result.append({
                                    "type": "table_cell",
                                    "heading_level": None,
                                    "text": text.strip(),
                                })

    return result


def _extract_paragraph_text(paragraph):
    """Extract plain text from a paragraph element."""
    text_runs = []
    for element in paragraph.get("elements", []):
        if "textRun" in element:
            text_runs.append(element["textRun"].get("content", ""))
    return "".join(text_runs)


def chunk_document(elements, max_tokens=500, min_tokens=50):
    """
    Semantic chunker for Docs content.
    Splits on H1/H2 boundaries, targets 400-600 tokens per chunk.

    Returns list of {section_heading, text_content, estimated_tokens}
    """
    chunks = []
    current_heading = ""
    current_texts = []
    current_tokens = 0

    for el in elements:
        text = el.get("text", "")
        estimated_tokens = len(text.split()) + 2
        heading_level = el.get("heading_level")

        # New chunk boundary on H1 or H2
        if heading_level in (1, 2):
            if current_texts and current_tokens >= min_tokens:
                chunks.append({
                    "section_heading": current_heading,
                    "text_content": "\n".join(current_texts),
                    "estimated_tokens": current_tokens,
                })
            current_heading = text
            current_texts = []
            current_tokens = 0
            continue

        # Flush if exceeds max tokens
        if current_tokens + estimated_tokens > max_tokens and current_texts:
            chunks.append({
                "section_heading": current_heading,
                "text_content": "\n".join(current_texts),
                "estimated_tokens": current_tokens,
            })
            current_texts = []
            current_tokens = 0

        current_texts.append(text)
        current_tokens += estimated_tokens

    if current_texts and current_tokens >= min_tokens:
        chunks.append({
            "section_heading": current_heading,
            "text_content": "\n".join(current_texts),
            "estimated_tokens": current_tokens,
        })

    return chunks


def classify_document(drive_file_metadata):
    """
    First-pass quality gate for Google Docs documents.
    Returns None if the document should be dropped.

    Signal taxonomy drop rules:
      - DROP title == "Untitled document" (draft)
      - DROP trashed: true (from Drive metadata)
      - DROP word_count < MIN_WORD_COUNT (too thin)
      - DROP auto-generated template docs
      - DROP personal/private docs (only owner has access)
      - DROP Docs created from Google Forms
    """
    if drive_file_metadata.get("trashed"):
        return None

    name = drive_file_metadata.get("name", "")
    if name.lower() in ("untitled document", "untitled", ""):
        return None

    # Detect Google Forms output docs
    description = drive_file_metadata.get("description", "") or ""
    if "form response" in description.lower():
        return None

    return {"title": name}


def count_words_in_elements(elements):
    """Count total words across all structural elements."""
    return sum(len(el.get("text", "").split()) for el in elements)
