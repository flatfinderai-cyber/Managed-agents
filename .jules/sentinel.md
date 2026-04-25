## 2024-05-16 - [Timing Attack in API Key Validation]
**Vulnerability:** Timing attack vulnerability due to using standard string equality `!=` when verifying `INTERNAL_API_KEY`.
**Learning:** Checking secure tokens with standard string equality operators opens the system up to timing attacks where an attacker can learn the token character by character based on how long the comparison takes.
**Prevention:** Always use constant-time comparison functions like `secrets.compare_digest()` for security-sensitive string comparisons like API keys, tokens, or passwords.
