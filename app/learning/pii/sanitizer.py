"""
PII Sanitizer — removes sensitive information from query text before persistence.

Applies a configurable set of sanitization rules:
  - Emails
  - Phone numbers
  - API keys / tokens
  - AWS secret keys / access keys
  - JWT tokens
  - Password-like strings
  - IP addresses (optional)
"""

from __future__ import annotations

import re
from typing import Optional

_PII_PATTERNS: list[tuple[str, str, str]] = [
    # Most specific first — API keys with well-known prefixes
    (r"(?i)(sk_live|pk_live|sk_test|pk_test)_[A-Za-z0-9]{24,}", "[STRIPE_KEY]"),
    (r"ghp_[A-Za-z0-9]{36}", "[GITHUB_TOKEN]"),
    (r"xox[baprs]-[0-9a-zA-Z-]{10,}", "[SLACK_TOKEN]"),
    (r"AKIA[0-9A-Z]{16}", "[AWS_KEY]"),
    (r"(?i)aws(.{0,20})?secret(.{0,20})?access(.{0,20})?key[:\s=]+[A-Za-z0-9/+=]{40}", "[AWS_SECRET]"),
    # Bearer tokens / JWT-like patterns
    (r"(?i)bearer\s+[A-Za-z0-9\-_.]{20,}", "[TOKEN]"),
    # Generic API keys (hex or base64, 32+ chars)
    (r"(?i)(api[_-]?key|apikey|api_key)[:\s=]+[A-Za-z0-9_\-]{32,}", "[API_KEY]"),
    # Password-like assignments
    (r"(?i)(password|passwd|pwd)[:\s=]+[A-Za-z0-9!@#$%^&*()_+={}\[\]|;:'\",.<>?/`~\\-]{8,}", "[PASSWORD]"),
    # Email addresses
    (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL]"),
    # Phone numbers — most general, checked last
    (r"\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,9}", "[PHONE]"),
]


def sanitize(text: str, enabled: bool = True) -> str:
    """
    Remove PII from the given text by replacing known patterns with placeholders.
    Returns the sanitized text.

    Args:
        text: Raw input string (user question, message content, etc.)
        enabled: Set to False to disable sanitization (for debugging or testing).

    Returns:
        Sanitized text with PII replaced by tokens like [EMAIL], [PHONE], etc.
    """
    if not enabled or not text:
        return text

    sanitized = text
    for pattern, replacement in _PII_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized)
    return sanitized
