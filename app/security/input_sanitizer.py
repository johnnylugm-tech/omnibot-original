"""Input sanitizer - L2 character normalization"""

import unicodedata


class InputSanitizer:
    """
    L2 Input sanitization: character normalization only.
    No pattern matching (handled by Phase 2 PromptInjectionDefense L3).
    """

    def sanitize(self, text: str) -> str:
        # NFKC normalization (compatibility decomposition)
        text = unicodedata.normalize("NFKC", text)
        # Remove control characters, keep newlines and tabs
        text = "".join(c for c in text if c.isprintable() or c in "\n\t")
        return text.strip()
