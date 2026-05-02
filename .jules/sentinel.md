## 2024-05-02 - Fix timing attack in API key verification
**Vulnerability:** Timing attack vulnerability in internal API key verification where standard string equality operators (`!=`) were used instead of constant-time comparison functions.
**Learning:** Python's standard `==` and `!=` operators exit early when comparing strings, allowing attackers to infer the correct characters of an API key by measuring response times.
**Prevention:** Always use `secrets.compare_digest()` for comparing security-sensitive strings like API keys, tokens, or passwords to ensure constant-time comparison and prevent timing attacks.
