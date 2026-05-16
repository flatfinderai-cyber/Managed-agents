## 2024-05-16 - Prevent Timing Attacks on Internal API Key
**Vulnerability:** The internal API key validation routes (search_blitz, human_review, orchestrator, stack_decisions) compare the `X-Internal-Key` against the environment's `INTERNAL_API_KEY` using standard string equality `!=`. This can expose the length and contents of the secret key to timing attacks.
**Learning:** Comparing sensitive secrets like API keys or passwords should never be done with standard equality operators `==` or `!=`.
**Prevention:** Always use constant-time comparison functions like `secrets.compare_digest()` for comparing security-sensitive strings.
