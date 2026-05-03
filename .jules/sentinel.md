## 2025-02-23 - Prevent Timing Attacks on API Key Validation
**Vulnerability:** Timing attack vulnerability due to comparing security-sensitive API keys (x-internal-key) using standard equality operators (`!=`).
**Learning:** Standard string comparison operators (`==`, `!=`) return early on the first mismatching character. This allows attackers to guess valid keys one character at a time by measuring the time it takes for the server to reject the request.
**Prevention:** Always use constant-time comparison functions like `secrets.compare_digest()` from the `secrets` module when comparing sensitive tokens, passwords, or API keys.
