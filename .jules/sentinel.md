## 2024-05-08 - Timing Attack Vulnerability in API Key Comparison
**Vulnerability:** The codebase compares the internal API key using the standard string equality operator `!=` (e.g., `x_internal_key != expected`). This exposes the application to timing attacks where an attacker could deduce the key character by character based on how long the comparison takes.
**Learning:** Python's standard string comparison `==` or `!=` terminates early when characters do not match. When comparing secrets like API keys or tokens, constant-time comparison must be used to ensure the comparison time is independent of the input length and character matches.
**Prevention:** Always use `secrets.compare_digest()` from the Python standard library when comparing sensitive tokens, passwords, or API keys.
