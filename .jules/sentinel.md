## 2024-05-13 - [Sentinel] Timing Attack Vulnerability in API Key Check
**Vulnerability:** Comparing API keys using standard equality operators (`==` or `!=`) allows attackers to deduce the key character-by-character by measuring the time the comparison takes (timing attack).
**Learning:** Python's string equality short-circuits on the first mismatch, leading to measurable timing differences.
**Prevention:** Always use `secrets.compare_digest()` for comparing sensitive tokens, passwords, or API keys in Python to ensure constant-time comparison.
