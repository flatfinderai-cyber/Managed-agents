## 2024-05-05 - Timing Attack Vulnerability in API Key Comparison
**Vulnerability:** API key string comparison used the standard `!=` operator, creating a timing attack vulnerability that could allow attackers to guess the API key character by character.
**Learning:** Standard string equality checks take variable time depending on how many characters match, leaking information.
**Prevention:** Always use constant-time comparison functions like `secrets.compare_digest()` for security-sensitive strings like API keys or tokens.
