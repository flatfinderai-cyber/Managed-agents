## 2024-05-18 - Fix timing attack vulnerability in API key verification
**Vulnerability:** The standard `!=` operator was used to compare the internal API key (`x_internal_key != expected`), which exposes the application to timing attacks, allowing an attacker to potentially guess the key character-by-character.
**Learning:** String comparisons for security-sensitive tokens must execute in constant time regardless of where the mismatch occurs.
**Prevention:** Always use `secrets.compare_digest()` from the Python standard library instead of standard equality operators (`==`, `!=`) for comparing tokens, passwords, or API keys.
