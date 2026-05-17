## 2026-05-18 - Fix timing attack in API key comparisons
**Vulnerability:** Internal API key checks used standard string equality (`!=`), exposing the endpoints to timing attacks where an attacker could theoretically guess the key byte-by-byte.
**Learning:** Python's standard equality operator short-circuits, making it unsuitable for security-sensitive comparisons.
**Prevention:** Always use `secrets.compare_digest()` for comparing security tokens, API keys, or passwords to ensure constant-time comparison.
