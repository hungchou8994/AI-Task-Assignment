"""Wave 0 TDD stubs for email preprocessing layer.

These tests will FAIL at collection time (ImportError) until Plan 02 implements:
  - app.ai.preprocessor: preprocess_email, strip_reply_chain, extract_urls_from_body, ParsedEmail
  - app.ai.gemini_client: call_gemini updated signature (accepts list[types.Part])
  - app.routers.ai: AnalyzeResponse updated with skipped_attachments, failed_urls fields

This is intentional — the RED phase of Wave 0 TDD.
After Plan 02 implements these, all 10 tests should go GREEN without modifying this file.

Requirements covered: EMAIL-02, EMAIL-03, EMAIL-04, EMAIL-05, EMAIL-07, EMAIL-08, EMAIL-09
"""

import pytest
from unittest.mock import patch, MagicMock
from google.genai import types as genai_types

# stdlib MIME helpers for building test emails
import email as email_mod
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

# --- Imports from modules that will exist after Plan 02 ---
# These raise ImportError until Plan 02 creates them — intentional for Wave 0.
from app.ai.preprocessor import (
    preprocess_email,
    strip_reply_chain,
    extract_urls_from_body,
    ParsedEmail,
)
from app.ai.gemini_client import call_gemini
from app.routers.ai import AnalyzeResponse


# ---------------------------------------------------------------------------
# Module-level fixture strings
# ---------------------------------------------------------------------------

PLAIN_EMAIL = """\
From: alice@example.com
To: bob@example.com
Subject: Test

Please fix the login bug by Friday.
Review the attached report.
"""

REPLY_CHAIN_EMAIL = """\
From: alice@example.com
To: bob@example.com
Subject: Re: Test

Got it, will do.

> On Mon, 9 Mar 2026, Bob wrote:
> Please fix the login bug.
> Thanks.
"""

GMAIL_STYLE_REPLY = """\
Will handle this tomorrow.

On Mon, Mar 9, 2026 at 10:00 AM Bob Smith <bob@example.com> wrote:
Please review the quarterly report.
"""

SIGNATURE_EMAIL = """\
Let's meet tomorrow at 10am to discuss.

-- 
Alice Johnson
Senior Engineer | Acme Corp
alice@example.com
"""

JAPANESE_URL_TEXT = "詳細はhttps://example.com/path参照してください。"


# ---------------------------------------------------------------------------
# Helper — build a multipart/mixed email with a single attachment
# ---------------------------------------------------------------------------


def build_multipart_email_with_attachment(
    body: str, filename: str, content_type: str, payload: bytes
) -> str:
    """Construct a minimal RFC-2822 multipart email with one attachment.

    Returns the email as a raw string suitable for passing to preprocess_email().
    """
    msg = MIMEMultipart()
    msg["From"] = "test@example.com"
    msg["To"] = "other@example.com"
    msg["Subject"] = "Test with attachment"
    msg.attach(MIMEText(body, "plain"))
    maintype, subtype = content_type.split("/", 1)
    part = MIMEBase(maintype, subtype)
    part.set_payload(payload)
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", "attachment", filename=filename)
    msg.attach(part)
    return msg.as_string()


# ---------------------------------------------------------------------------
# Tests — EMAIL-02: plain email body parsing
# ---------------------------------------------------------------------------


def test_parse_plain_body():
    """preprocess_email() on a plain-text email returns ParsedEmail with non-empty body."""
    result = preprocess_email(PLAIN_EMAIL)
    assert isinstance(result, ParsedEmail)
    assert "login bug" in result.body
    assert isinstance(result.attachments, list)
    assert isinstance(result.skipped_attachments, list)
    assert isinstance(result.raw_urls, list)


# ---------------------------------------------------------------------------
# Tests — EMAIL-03: reply chain stripping
# ---------------------------------------------------------------------------


def test_strip_reply_chain_quoted_lines():
    """strip_reply_chain() removes lines starting with '>' from text."""
    result = strip_reply_chain(REPLY_CHAIN_EMAIL)
    assert "> Please fix" not in result
    assert "Got it" in result  # original content preserved


def test_strip_gmail_style():
    """strip_reply_chain() removes 'On DATE, NAME wrote:' transition lines."""
    result = strip_reply_chain(GMAIL_STYLE_REPLY)
    assert "On Mon, Mar 9, 2026" not in result
    assert "Will handle this tomorrow" in result


def test_preserves_signature():
    """strip_reply_chain() keeps content after '-- ' signature separator."""
    result = strip_reply_chain(SIGNATURE_EMAIL)
    assert "Let's meet tomorrow" in result
    # Signature NOT stripped (user decision: keep signatures for context)
    assert "Alice Johnson" in result


# ---------------------------------------------------------------------------
# Tests — EMAIL-04 / EMAIL-05: attachment handling
# ---------------------------------------------------------------------------


def test_unsupported_attachment_skipped():
    """image/png attachment goes to ParsedEmail.skipped_attachments, not .attachments."""
    raw = build_multipart_email_with_attachment(
        body="Review the attached image.",
        filename="photo.png",
        content_type="image/png",
        payload=b"\x89PNG\r\n",
    )
    result = preprocess_email(raw)
    assert "photo.png" in result.skipped_attachments
    assert not any(f == "photo.png" for f, _, _ in result.attachments)


def test_pdf_attachment_extracted():
    """PDF attachment appears in ParsedEmail.attachments as (filename, bytes, mime_type) tuple."""
    raw = build_multipart_email_with_attachment(
        body="See the attached PDF.",
        filename="report.pdf",
        content_type="application/pdf",
        payload=b"%PDF-1.4 fake content",
    )
    result = preprocess_email(raw)
    assert len(result.attachments) == 1
    fname, data, mime = result.attachments[0]
    assert fname == "report.pdf"
    assert mime == "application/pdf"


# ---------------------------------------------------------------------------
# Tests — EMAIL-07: URL extraction
# ---------------------------------------------------------------------------


def test_url_dedup():
    """extract_urls_from_body() returns each URL only once even if it appears twice."""
    text = "See https://example.com/page and also https://example.com/page for more."
    urls = extract_urls_from_body(text)
    assert urls.count("https://example.com/page") == 1


def test_url_cjk_boundary():
    """URL regex does NOT include trailing Japanese '。' punctuation in extracted URL."""
    urls = extract_urls_from_body(JAPANESE_URL_TEXT)
    assert len(urls) == 1
    assert urls[0] == "https://example.com/path"
    assert "。" not in urls[0]


# ---------------------------------------------------------------------------
# Tests — EMAIL-08: call_gemini multi-part support
# ---------------------------------------------------------------------------


def test_call_gemini_parts():
    """call_gemini() can be called with a list[types.Part] without raising TypeError."""
    parts = [genai_types.Part.from_text(text="extract tasks from: fix the login bug")]
    with patch("app.ai.gemini_client.genai") as mock_genai:
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_resp = MagicMock()
        mock_resp.parsed = MagicMock()
        mock_resp.parsed.tasks = []
        mock_resp.parsed.source_summary = "test"
        mock_client.models.generate_content.return_value = mock_resp
        with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
            result = call_gemini(parts, "system prompt")
        # Verify generate_content was called — contents arg should be the parts list
        assert mock_client.models.generate_content.called


# ---------------------------------------------------------------------------
# Tests — EMAIL-09: AnalyzeResponse schema extension
# ---------------------------------------------------------------------------


def test_analyze_response_has_skipped_fields():
    """AnalyzeResponse model can be instantiated with skipped_attachments and failed_urls fields."""
    resp = AnalyzeResponse(
        candidates=[],
        source_summary="test",
        skipped_attachments=["photo.png"],
        failed_urls=["https://broken.example.com"],
    )
    assert resp.skipped_attachments == ["photo.png"]
    assert resp.failed_urls == ["https://broken.example.com"]
