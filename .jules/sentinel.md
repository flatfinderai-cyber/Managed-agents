## 2025-05-01 - Fix Timing Attack in Internal API Key Validation
**Vulnerability:** The API used `!=` to validate the `x-internal-key` against `INTERNAL_API_KEY`, exposing endpoints to timing attacks as string comparison stops on the first mismatched character.
**Learning:** Comparing security-sensitive strings using standard equality operators allows attackers to guess valid keys via character-by-character timing differences.
**Prevention:** Always use `secrets.compare_digest()` for comparing security-sensitive strings (like API keys, tokens, or hashes) to guarantee constant-time comparison.
