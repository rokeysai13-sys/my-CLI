"""
core/security.py — Input sanitization and security utilities.
"""
import re

def sanitize_input(text: str) -> str:
    """Basic sanitization: remove null bytes and excessive whitespace."""
    if not text:
        return text
    # Remove null bytes
    text = text.replace('\x00', '')
    # Normalize excessive newlines
    text = re.sub(r'\n{4,}', '\n\n', text)
    return text.strip()

def contains_suspicious_patterns(text: str) -> bool:
    """Check for suspicious command injection or path traversal attempts."""
    patterns = [
        r'(?i)(<script>|<img.*?onerror=)', # Basic XSS
        r'(\.\./\.\./)', # Path traversal
        r'(&&|;|\brm -rf\b|\bdel /s\b)' # Simple bash/cmd injections
    ]
    for p in patterns:
        if re.search(p, text):
            return True
    return False
