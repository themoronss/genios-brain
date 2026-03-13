from email.utils import parseaddr, parsedate_to_datetime
import base64
import re


def parse_headers(payload):

    headers = payload.get("headers", [])

    data = {
        "from_email": None,
        "from_name": None,
        "to_email": None,
        "to_name": None,
        "subject": None,
        "date": None,
    }

    for h in headers:

        if h["name"] == "From":
            name, email = parseaddr(h["value"])
            data["from_email"] = email
            data["from_name"] = name

        if h["name"] == "To":
            name, email = parseaddr(h["value"])
            data["to_email"] = email
            data["to_name"] = name

        if h["name"] == "Subject":
            data["subject"] = h["value"]

        if h["name"] == "Date":
            try:
                data["date"] = parsedate_to_datetime(h["value"])
            except:
                data["date"] = None

    return data


def extract_email_body(payload):
    """
    Extract plain text body from Gmail message payload.
    Handles both simple and multipart messages.

    Args:
        payload: Gmail message payload

    Returns:
        str: Plain text body content
    """
    body_text = ""

    # Check if message has parts (multipart)
    if "parts" in payload:
        body_text = extract_from_parts(payload["parts"])
    else:
        # Simple message with body directly in payload
        if "body" in payload and "data" in payload["body"]:
            body_text = decode_base64(payload["body"]["data"])

    # Clean up the text
    body_text = clean_email_body(body_text)

    return body_text


def extract_from_parts(parts):
    """
    Recursively extract text from multipart message.
    Prioritizes text/plain over text/html.
    """
    text_content = ""
    html_content = ""

    for part in parts:
        mime_type = part.get("mimeType", "")

        # Recursive for nested parts
        if "parts" in part:
            text_content += extract_from_parts(part["parts"])

        # Extract text/plain
        elif mime_type == "text/plain":
            if "data" in part.get("body", {}):
                text_content += decode_base64(part["body"]["data"])

        # Extract text/html as fallback
        elif mime_type == "text/html":
            if "data" in part.get("body", {}):
                html_content += decode_base64(part["body"]["data"])

    # Prefer plain text, fallback to HTML (stripped)
    if text_content:
        return text_content
    elif html_content:
        return strip_html_tags(html_content)

    return ""


def decode_base64(data):
    """Decode base64 URL-safe encoded data."""
    try:
        decoded = base64.urlsafe_b64decode(data.encode("ASCII"))
        return decoded.decode("utf-8", errors="ignore")
    except Exception:
        return ""


def strip_html_tags(html_text):
    """Remove HTML tags and return plain text."""
    # Remove HTML tags
    clean = re.sub("<.*?>", "", html_text)
    # Remove extra whitespace
    clean = re.sub(r"\s+", " ", clean)
    return clean.strip()


def clean_email_body(text):
    """
    Clean email body text:
    - Remove excessive newlines
    - Remove email signatures and footers
    - Truncate to reasonable length
    """
    if not text:
        return ""

    # Remove excessive whitespace
    text = re.sub(r"\n\s*\n", "\n\n", text)
    text = re.sub(r" +", " ", text)

    # Truncate to 5000 characters (keep first part of email)
    if len(text) > 5000:
        text = text[:5000] + "..."

    return text.strip()
