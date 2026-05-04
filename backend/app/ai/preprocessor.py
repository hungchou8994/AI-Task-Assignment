"""app.ai.preprocessor — Fetch URLs, strip HTML, and parse emails.

Pure functions: no DB, no Gemini imports.
Exports: fetch_url, strip_html, preprocess,
         ParsedEmail, preprocess_email, strip_reply_chain, extract_urls_from_body
"""

import re
import email as email_mod
from dataclasses import dataclass, field
from typing import Union

import httpx

from app.config import get_settings


SUPPORTED_ATTACHMENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "text/plain",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # .xlsx
    "text/csv",
}


@dataclass
class ParsedEmail:
    body: str
    attachments: list[tuple[str, bytes, str]] = field(
        default_factory=list
    )  # (filename, data, mime_type)
    skipped_attachments: list[str] = field(default_factory=list)
    raw_urls: list[str] = field(default_factory=list)


def fetch_url(url: str, timeout: int = 10) -> str:
    """Fetch a URL and return its text content."""
    resp = httpx.get(url, timeout=timeout, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def strip_html(html: str) -> str:
    """Strip script/style blocks and HTML tags; collapse whitespace.

    Process order:
      1. Remove <script>...</script> blocks (including content)
      2. Remove <style>...</style> blocks (including content)
      3. Strip remaining HTML tags
      4. Collapse whitespace
    """
    # Remove script and style blocks (including their content)
    html = re.sub(
        r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE
    )
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # Strip remaining HTML tags
    stripped = re.sub(r"<[^>]+>", "", html)
    # Collapse whitespace
    return re.sub(r"\s+", " ", stripped).strip()


def strip_reply_chain(text: str) -> str:
    """Strip quoted reply history. Keep email signatures.

    Three passes:
      1. Remove lines starting with > (Gmail/standard quoting)
      2. Remove Outlook-style -----Original Message----- blocks onward
      3. Remove Gmail/Apple "On DATE, NAME wrote:" transition lines
    Signatures (content after --, ***, ---) are deliberately preserved.
    """
    text = re.sub(r"^>.*$", "", text, flags=re.MULTILINE)
    text = re.sub(
        r"(-{4,}|_{4,})\s*(Original Message|Forwarded [Mm]essage).*",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )
    text = re.sub(r"\nOn\s+.{10,200}?wrote:\s*\n", "\n", text, flags=re.DOTALL)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


_URL_RE = re.compile(
    # Stop at whitespace, common URL-terminating punctuation, and CJK characters
    # CJK ranges: CJK Unified (4E00-9FFF), Hiragana (3040-309F), Katakana (30A0-30FF),
    # CJK punctuation (3000-303F), Fullwidth forms (FF00-FFEF)
    r'https?://[^\s<>"\')\]\\,\u3000-\u9FFF\uFF00-\uFFEF]+',
    re.UNICODE,
)


def extract_urls_from_body(text: str) -> list[str]:
    """Extract unique https/http URLs from plain text; deduplicated, order preserved."""
    seen: set[str] = set()
    result: list[str] = []
    for url in _URL_RE.findall(text):
        if url not in seen:
            seen.add(url)
            result.append(url)
    return result


def preprocess_email(raw_email: str) -> ParsedEmail:
    """Pure function: parse raw email string into structured result. No IO.

    Uses compat32 policy (email.message_from_string default) — required for
    get_payload(decode=True) to return bytes for attachments.
    """
    msg = email_mod.message_from_string(raw_email)

    body_parts: list[str] = []
    attachments: list[tuple[str, bytes, str]] = []
    skipped: list[str] = []
    found_plain_body = False

    for part in msg.walk():
        ct = part.get_content_type()
        cd = part.get("Content-Disposition", "")
        filename = part.get_filename()

        # First text/plain part that is not an attachment = email body
        if ct == "text/plain" and "attachment" not in cd and not found_plain_body:
            payload = part.get_payload(decode=True)
            if payload:
                charset = part.get_content_charset() or "utf-8"
                body_parts.append(payload.decode(charset, errors="replace"))
                found_plain_body = True

        # Attachments (has filename)
        elif filename:
            payload = part.get_payload(decode=True)
            if payload:
                if ct in SUPPORTED_ATTACHMENT_TYPES:
                    attachments.append((filename, payload, ct))
                else:
                    skipped.append(filename)

    raw_body = "\n".join(body_parts)
    cleaned_body = strip_reply_chain(raw_body)
    urls = extract_urls_from_body(cleaned_body)

    return ParsedEmail(
        body=cleaned_body,
        attachments=attachments,
        skipped_attachments=skipped,
        raw_urls=urls,
    )


def preprocess(source_type: str, content: str) -> Union[str, ParsedEmail]:
    """Resolve content based on source_type.

    - 'url': fetch URL, strip HTML, cap at 20k chars
    - 'email': parse email into ParsedEmail dataclass
    - 'text': return content as-is
    """
    if source_type == "url":
        html = fetch_url(content)
        return strip_html(html)[: get_settings().ai_url_strip_chars]
    if source_type == "email":
        return preprocess_email(content)
    return content
