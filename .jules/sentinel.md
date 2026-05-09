## 2024-05-24 - Prevent Timing Attacks on API Key Comparison
**Vulnerability:** Timing attack vulnerability due to using standard `!=` string comparison for `INTERNAL_API_KEY` validation across internal routes.
**Learning:** Python's standard string comparison operators (`==`, `!=`) return early on the first mismatched character. This allows attackers to guess secrets by measuring response times. For security-sensitive string comparisons like API keys, a constant-time comparison must be used.
**Prevention:** Always use `secrets.compare_digest()` when comparing API keys, tokens, or other secrets to prevent timing side-channel attacks.
