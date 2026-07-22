# Security

- **Rate limiting** – API endpoints are protected against abuse with configurable rate limits (Redis‑backed).
- **PII redaction** – Uploaded CSV files are automatically scanned with Microsoft Presidio; sensitive information (emails, phones, credit cards) is replaced with `[REDACTED]` before analysis.
- **Content validation** – Files are validated by MIME type, size (<10MB), and filename; question input is sanitized.
- **Authentication** – All sensitive endpoints require a valid JWT (HS256). Passwords are hashed with bcrypt.
- **Sandbox isolation** – AI‑generated code runs in a separate container with read‑only filesystem, no network, and restricted imports.
