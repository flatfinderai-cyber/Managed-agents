## 2025-05-20 - Prevent Timing Attacks in Internal API Key Checks
**Vulnerability:** The `_require_internal_key` function checked the internal API key using `!=`, which allows a timing attack since string comparison returns early on mismatch.
**Learning:** Use `secrets.compare_digest` for secure, constant-time comparison of sensitive strings like API keys, tokens, or passwords to prevent timing attacks.
**Prevention:** Always check if a variable being compared is a secret. If so, use `secrets.compare_digest()` instead of standard equality operators.
