## 2026-05-04 - Timing Attack Vulnerability in API Key Verification
**Vulnerability:** API key string comparisons were using standard `!=` equality operators, making them susceptible to side-channel timing attacks where an attacker could incrementally guess the key.
**Learning:** Standard string comparisons fail fast on the first mismatched character, leaking timing information about the validity of the prefix.
**Prevention:** Always use `secrets.compare_digest()` for comparing security-sensitive tokens, keys, and passwords to ensure constant-time comparison regardless of the input.
