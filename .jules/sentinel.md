## 2025-03-01 - Prevent Timing Attacks in API Key Validation
**Vulnerability:** Comparing sensitive tokens like API keys using `!=` is vulnerable to timing attacks.
**Learning:** Plain string comparison exits early on a mismatch, leaking information about the expected string.
**Prevention:** Always use `secrets.compare_digest()` for security-sensitive token comparisons.
