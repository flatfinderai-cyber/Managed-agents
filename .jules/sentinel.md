## 2025-04-29 - Prevent Timing Attacks in API Key Verification
**Vulnerability:** String comparison for internal API keys was done using standard equality operators (`!=`), which can be vulnerable to timing attacks. An attacker could measure the time taken to verify a key character by character and potentially guess the correct key.
**Learning:** Security-sensitive strings like API keys or tokens should always be compared using constant-time comparison functions to prevent information leakage through timing side-channels.
**Prevention:** Use `secrets.compare_digest()` for comparing security-sensitive strings instead of `==` or `!=`.
