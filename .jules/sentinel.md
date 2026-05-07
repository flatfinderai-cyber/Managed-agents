## 2024-05-20 - Prevent Information Leakage in Error Responses
**Vulnerability:** Information Leakage
**Learning:** Returning exception strings directly in HTTPException details leaks internal stack traces and database implementation details to users.
**Prevention:** Catch exceptions, log them securely on the server-side if needed, and return generic, sterile error messages to the client.
