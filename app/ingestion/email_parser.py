from email.utils import parseaddr, parsedate_to_datetime, getaddresses
import base64
import re


def parse_headers(payload):
    """
    Parse Gmail message headers into a structured dict.

    Returns:
        dict with keys: from_email, from_name, to_email, to_name, subject,
                        date, cc_list (list of {name, email} dicts)
    """
    headers = payload.get("headers", [])

    data = {
        "from_email": None,
        "from_name": None,
        "to_email": None,
        "to_name": None,
        "subject": None,
        "date": None,
        "cc_list": [],  # Update 3: many-to-many CC support
        "has_unsubscribe": False,  # List-Unsubscribe header detection
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
            except Exception:
                data["date"] = None

        # Detect List-Unsubscribe header (marketing/automated signal)
        if h["name"].lower() == "list-unsubscribe":
            data["has_unsubscribe"] = True

        # Update 3: Parse CC into a list of {name, email} dicts
        # getaddresses() handles comma-separated multi-address strings correctly
        if h["name"] == "Cc" and h["value"].strip():
            raw_pairs = getaddresses([h["value"]])
            cc_list = []
            for name, email_addr in raw_pairs:
                email_addr = email_addr.strip().lower()
                if email_addr and "@" in email_addr:
                    cc_list.append({
                        "name": name.strip() or email_addr,
                        "email": email_addr,
                    })
            data["cc_list"] = cc_list

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
