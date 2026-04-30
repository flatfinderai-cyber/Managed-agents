## 2024-05-24 - Fix Timing Attack in API Key Validation
**Vulnerability:** The `_require_internal_key` function was using standard string equality (`!=`) to validate the `x-internal-key` header against the `INTERNAL_API_KEY` environment variable. This allows an attacker to perform a timing attack to guess the API key character by character.
**Learning:** Comparing security-sensitive strings (e.g., API keys, tokens) using standard equality operators introduces timing attack vulnerabilities because the comparison stops at the first mismatched character.
**Prevention:** Always use constant-time comparison functions like `secrets.compare_digest()` to compare security-sensitive strings and secrets.
