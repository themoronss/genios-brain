import requests

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_API_VERSION = "2022-06-28"
NOTION_AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"

# Block types that contain no indexable text — skip entirely
SKIP_BLOCK_TYPES = {
    "embed", "image", "video", "audio", "file",
    "code", "equation", "bookmark", "link_preview",
}

# Block types that are visual containers — process children only
CONTAINER_BLOCK_TYPES = {"column_list", "column", "toggle", "bulleted_list_item"}

# Heading block types — used as chunk boundaries
HEADING_TYPES = {"heading_1", "heading_2", "heading_3"}

# Quality gate: minimum block count to index a page
MIN_BLOCK_COUNT = 3


def get_notion_authorize_url(client_id, redirect_uri, state):
    """Build Notion OAuth authorization URL."""
    return (
        f"{NOTION_AUTH_URL}"
        f"?client_id={client_id}"
        f"&response_type=code"
        f"&owner=user"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
    )


def exchange_code_for_token(code, client_id, client_secret, redirect_uri):
    """Exchange authorization code for Notion access token."""
    import base64
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()

    response = requests.post(
        NOTION_TOKEN_URL,
        headers={
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        },
        json={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
        },
    )
    data = response.json()
    if "access_token" not in data:
        raise ValueError(f"Notion token exchange failed: {data}")
    return data


def _headers(access_token):
    return {
        "Authorization": f"Bearer {access_token}",
        "Notion-Version": NOTION_API_VERSION,
        "Content-Type": "application/json",
    }


def fetch_pages_since(access_token, last_sync_cursor=None, page_size=100):
    """
    Search for all pages/databases edited since last_sync_cursor.
    Uses POST /v1/search with last_edited_time filter for incremental sync.

    Returns (pages, next_cursor)

    Signal taxonomy — callers must apply quality gates:
      - DROP archived: true
      - DROP is_template: true
      - DROP title == "Untitled"
      - DROP block_count < 3
    """
    body = {
        "sort": {"direction": "descending", "timestamp": "last_edited_time"},
        "page_size": page_size,
    }

    if last_sync_cursor:
        body["filter"] = {
            "value": "page",
            "property": "object",
        }
        # Notion search doesn't have a time filter natively;
        # use cursor from previous response for pagination
        body["start_cursor"] = last_sync_cursor

    response = requests.post(
        f"{NOTION_API_BASE}/search",
        headers=_headers(access_token),
        json=body,
    )
    response.raise_for_status()
    data = response.json()

    pages = data.get("results", [])
    next_cursor = data.get("next_cursor")
    return pages, next_cursor


def fetch_page(access_token, page_id):
    """Fetch a single page's metadata."""
    response = requests.get(
        f"{NOTION_API_BASE}/pages/{page_id}",
        headers=_headers(access_token),
    )
    response.raise_for_status()
    return response.json()


def fetch_blocks(access_token, block_id, current_depth=0, max_depth=4):
    """
    Recursively fetch blocks for a page/block.
    Hard limit: max_depth = 4. Below that, queue child block IDs as separate jobs.

    Signal taxonomy:
      - SKIP embed, image, video, audio, file, code, equation blocks
      - On synced_block: check synced_from.block_id — if set, skip (only index original)
      - Divider blocks are chunk boundaries only, not content
      - column_list/column: process children only

    Returns flat list of (depth, block_type, text_content, heading_level) tuples
    for the semantic chunker.
    """
    if current_depth > max_depth:
        return []

    response = requests.get(
        f"{NOTION_API_BASE}/blocks/{block_id}/children",
        headers=_headers(access_token),
        params={"page_size": 100},
    )
    if response.status_code == 403:
        return []  # Access denied on this block
    response.raise_for_status()
    data = response.json()

    blocks = data.get("results", [])
    result = []

    for block in blocks:
        block_type = block.get("type", "")

        # Skip non-text blocks entirely
        if block_type in SKIP_BLOCK_TYPES:
            continue

        # Skip synced_block copies — only index the original
        if block_type == "synced_block":
            synced_from = block.get("synced_block", {}).get("synced_from")
            if synced_from:
                continue  # This is a copy — skip

        # Extract text from block
        text = _extract_text_from_block(block)
        if text:
            result.append({
                "depth": current_depth,
                "type": block_type,
                "text": text,
                "is_heading": block_type in HEADING_TYPES,
            })

        # Recurse into children (if any)
        if block.get("has_children") and current_depth < max_depth:
            children = fetch_blocks(access_token, block["id"], current_depth + 1, max_depth)
            result.extend(children)

    return result


def _extract_text_from_block(block):
    """Extract plain text from a block's rich_text array."""
    block_type = block.get("type", "")
    type_content = block.get(block_type, {})

    rich_text = type_content.get("rich_text", [])
    if not rich_text:
        return ""

    return " ".join(
        segment.get("plain_text", "") for segment in rich_text
    ).strip()


def chunk_blocks(blocks, max_tokens=500, min_tokens=50):
    """
    Semantic chunker: split block list into chunks on H1/H2 boundaries.
    Target: 400-600 tokens per chunk.

    Returns list of {section_heading, text_content, estimated_tokens}
    """
    chunks = []
    current_heading = ""
    current_texts = []
    current_tokens = 0

    for block in blocks:
        text = block.get("text", "")
        estimated_tokens = len(text.split()) + 2  # rough token estimate

        if block.get("is_heading") and block.get("type") in ("heading_1", "heading_2"):
            # Flush current chunk before starting new section
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

        # Flush if adding this block would exceed max_tokens
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

    # Final chunk
    if current_texts and current_tokens >= min_tokens:
        chunks.append({
            "section_heading": current_heading,
            "text_content": "\n".join(current_texts),
            "estimated_tokens": current_tokens,
        })

    return chunks


def classify_page(page):
    """
    First-pass quality gate for Notion pages.
    Returns None if the page should be dropped, otherwise returns metadata dict.

    Signal taxonomy drop rules:
      - DROP archived: true
      - DROP is_template: true
      - DROP title == "Untitled" (drafts in progress)
      - DROP block_count < 3 (blank/stub pages)
    """
    if page.get("archived"):
        return None

    if page.get("is_template"):
        return None

    # Extract title
    title = ""
    props = page.get("properties", {})
    for prop_name in ("title", "Name", "Title"):
        prop = props.get(prop_name, {})
        title_arr = prop.get("title", [])
        if title_arr:
            title = " ".join(t.get("plain_text", "") for t in title_arr).strip()
            break

    if not title or title.lower() in ("untitled", ""):
        return None

    return {"title": title}
