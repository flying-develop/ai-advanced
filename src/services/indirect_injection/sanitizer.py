"""Defense Layer 1 — input sanitizer that strips hidden content before passing to agents."""

# stdlib
import logging
import re
import unicodedata

# third-party
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

ZERO_WIDTH_CHARS = [
    '​',  # Zero-Width Space
    '‌',  # Zero-Width Non-Joiner
    '‍',  # Zero-Width Joiner
    '⁠',  # Word Joiner
    '﻿',  # Zero-Width No-Break Space (BOM)
    '­',  # Soft Hyphen
]

_HIDING_STYLES = [
    'color:white', 'color: white',
    'color:#fff', 'color:#ffffff',
    'display:none', 'display: none',
    'visibility:hidden',
    'opacity:0',
    'font-size:0', 'font-size: 0',
    'height:0', 'width:0',
]


class InputSanitizer:
    """Defense Layer 1: remove hidden content from external data before passing to an agent."""

    def sanitize_email(self, raw: str) -> str:
        """Remove HTML comments and zero-width characters from email content."""
        cleaned = re.sub(r'<!--.*?-->', '', raw, flags=re.DOTALL)
        cleaned = self._strip_zero_width(cleaned)
        return cleaned.strip()

    def sanitize_document(self, raw: str) -> str:
        """Remove zero-width characters and normalize unicode in document content."""
        cleaned = self._strip_zero_width(raw)
        cleaned = unicodedata.normalize('NFKC', cleaned)
        return cleaned.strip()

    def sanitize_html(self, raw: str) -> str:
        """Extract only visible text from HTML, removing all hidden elements."""
        soup = BeautifulSoup(raw, 'html.parser')

        for tag in soup(['script', 'style']):
            tag.decompose()

        for tag in soup.find_all(style=True):
            style = tag['style'].lower().replace(' ', '')
            if any(p.replace(' ', '') in style for p in _HIDING_STYLES):
                tag.decompose()

        text = soup.get_text(separator='\n')
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return '\n'.join(lines)

    def _strip_zero_width(self, text: str) -> str:
        for char in ZERO_WIDTH_CHARS:
            text = text.replace(char, '')
        return text
