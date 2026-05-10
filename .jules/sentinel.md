## 2024-05-10 - Fix timing attack vulnerability in API key comparisons
**Vulnerability:** Timing attack vulnerability due to using `!=` for comparing API keys (`x_internal_key != expected`).
**Learning:** Using standard equality operators for security-sensitive strings allows attackers to perform timing attacks to guess the key.
**Prevention:** Always use `secrets.compare_digest()` for comparing security-sensitive strings like API keys or tokens to ensure constant-time comparison.
