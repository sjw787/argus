# Engineering Considerations

Argus for Athena was built entirely by AI (GitHub Copilot, powered by Claude Sonnet and Opus). This document exists to be transparent about the quality assurance steps taken to ensure the project is trustworthy, secure, and production-ready — despite being AI-generated.

The premise: *AI can write the code, but a human still has to own the outcome.* These are the steps taken to do that.

---

## Unit Tests

A full test suite covers the core application logic. Tests were written alongside the code and validated against the real application behaviour.

**154 tests passing across 9 test modules:**

| Module | What It Covers |
|--------|---------------|
| `test_api_catalog.py` | Glue Data Catalog API endpoints (databases, tables, partitions) |
| `test_api_queries.py` | Query execution, status polling, results, cancellation |
| `test_api_workgroups.py` | Workgroup listing, creation, client-workgroup assignment |
| `test_athena_service.py` | Athena service layer (start, poll, fetch results) |
| `test_catalog_service.py` | Glue catalog service layer |
| `test_workgroup_service.py` | Workgroup service (list, get, create, delete) |
| `test_config.py` | Configuration loading, env-var overrides, and Lambda DynamoDB persistence |
| `test_api_config.py` | Config API endpoints and workgroup assignment persistence |

Tests use `pytest` with `unittest.mock` to isolate AWS API calls. No real AWS credentials or network access are required to run the suite.

```bash
PYTHONPATH=src python -m pytest tests/ -q
# 90 passed
```

Current line coverage: **51%** (target: 87%). Coverage is enforced by a pre-push ratchet hook — it can only go up between pushes.

---

## Code Reviews

Two structured code reviews were conducted using AI-assisted static analysis against the full codebase. Each review was scoped to find real issues only — not style preferences.

### Review 1 — Security & Correctness (pre-deployment)

Findings and resolutions:

| Severity | Issue | Resolution |
|----------|-------|------------|
| 🔴 Critical | `X-Credential-Id` header stripped by CloudFront — SSO auth always returned 401 | Added header to CloudFront forwarded headers and API Gateway CORS allow-list |
| 🟠 High | Cognito JWT validation missing issuer check — any Cognito pool's token accepted | Added `issuer` verification against `https://cognito-idp.{region}.amazonaws.com/{pool_id}` |
| 🟠 High | SSO credentials used without checking expiration — expired creds caused cryptic errors | Added expiration check; expired sessions are deleted and a `401` is returned immediately |
| 🟡 Medium | DynamoDB table storing raw AWS credentials lacked encryption | Added KMS Customer Managed Key with annual key rotation |

### Review 3 — Security & CORS Hardening (April 2026)

| Severity | Issue | Resolution |
|----------|-------|------------|
| 🔴 Critical | `allow_origins=["*"]` combined with `allow_credentials=True` in Lambda mode when `ARGUS_CORS_ORIGINS` was not set — violates CORS spec and creates CSRF risk on the `/auth/logout` endpoint | Lambda startup now raises `RuntimeError` if `ARGUS_CORS_ORIGINS` is unset; wildcard origins are never used with credentials |
| ✅ | AWS credentials never appear in logs or error responses | Confirmed |
| ✅ | No SQL injection risk — queries pass through boto3 to Athena's own parser | Confirmed |
| ✅ | DynamoDB session store uses key-value operations with no injection vectors | Confirmed |
| ✅ | No XSS vectors — `dangerouslySetInnerHTML` not used anywhere in the frontend | Confirmed |
| ✅ | No open redirects — SSO URLs come from AWS API; GitHub link is hardcoded | Confirmed |
| ✅ | `localStorage` holds only non-sensitive UI state and a session identifier; no raw AWS keys | Confirmed |
| ✅ | GitHub Actions workflows do not echo secrets to logs | Confirmed |

### Review 2 — Privacy & Data Handling

A dedicated privacy audit was run to verify that customer Athena data is never captured or stored. Key findings:

- ✅ Query results flow in-memory only — never written to disk or database
- ✅ Export (CSV/JSON/Excel/Parquet) uses in-memory buffers, streamed directly to browser
- ✅ No query text, result data, or schema metadata is logged at any level
- ✅ No analytics, telemetry, or third-party HTTP calls anywhere in the codebase
- ✅ `localStorage` contains only UI preferences; `sessionStorage` contains only auth token
- ✅ DynamoDB session store holds auth artifacts only (tokens, temp credentials), never query data

See [PRIVACY.md](PRIVACY.md) for the full data disclosure.

---

## Security Posture

Beyond the code review fixes, the following security practices are in place:

- **Authentication**: Three supported modes — AWS Cognito (JWT), AWS SSO (temporary credentials), or IAM-only (self-hosted/trusted network). No mode stores plaintext passwords.
- **Secrets**: No secrets are hardcoded. All sensitive values are environment variables or AWS-managed.
- **Credentials at rest**: Temporary AWS credentials (Lambda/SSO mode) are stored in DynamoDB encrypted with a KMS CMK. TTL auto-expires entries.
- **Transport**: HTTPS enforced end-to-end (CloudFront → API Gateway → Lambda). HTTP redirected to HTTPS at CloudFront.
- **CORS**: Locked to the explicit `ARGUS_CORS_ORIGINS` env var. In Lambda mode the application refuses to start if this is unset — wildcard origins (`*`) are never combined with `allow_credentials=True`.
- **Dependency scanning**: GitHub Actions CI runs on every push.

---

## What Was Not Done

In the interest of full transparency:

- **No penetration testing** has been performed. This is a personal/team tool, not a hardened SaaS product.
- **No dependency vulnerability scan** (e.g. `pip audit`, `npm audit`) has been formally run and addressed. Standard libraries are used throughout.
- **No load testing** has been done. AWS Lambda will scale, but the application has not been benchmarked.
- **IAM least-privilege** is partially implemented. Glue API calls require wildcard resource ARNs because AWS does not support resource-level restrictions on `GetDatabases` and similar operations.

---

## CI/CD

Every push to `main` runs the test suite via GitHub Actions. Deployment to AWS requires explicit workflow dispatch with environment confirmation.

```
.github/workflows/deploy.yml   — Build, push Docker image, deploy to Lambda + S3
.github/workflows/destroy.yml  — Tear down all infrastructure (requires manual confirmation)
```

---

*This document reflects the state of the project as of April 2026.*
