# Engineering Considerations

Argus for Athena was built entirely by AI (GitHub Copilot, powered by Claude Sonnet and Opus). This document exists to be transparent about the quality assurance steps taken to ensure the project is trustworthy, secure, and production-ready — despite being AI-generated.

The premise: *AI can write the code, but a human still has to own the outcome.* These are the steps taken to do that.

---

## Unit Tests

A full test suite covers the core application logic. Tests were written alongside the code and validated against the real application behaviour.

**295 tests passing across 19 test modules:**

| Module | What It Covers |
|--------|---------------|
| `test_api_catalog.py` | Glue Data Catalog API endpoints (databases, tables, partitions); SQL injection prevention on information_schema endpoint |
| `test_api_queries.py` | Query execution, status polling, results, cancellation, EXPLAIN |
| `test_api_workgroups.py` | Workgroup listing, creation, client-workgroup assignment |
| `test_athena_service.py` | Athena service layer (start, poll, fetch results) |
| `test_catalog_service.py` | Glue catalog service layer |
| `test_workgroup_service.py` | Workgroup service (list, get, create, delete) |
| `test_config.py` | Configuration loading, env-var overrides, and Lambda DynamoDB persistence |
| `test_api_config.py` | Config API endpoints and workgroup assignment persistence |
| `test_api_auth.py` | Auth router: status, SSO flow, credential-id session check |
| `test_export.py` | Export router: CSV/JSON/XLSX, access control |
| `test_session_store.py` | In-memory and DynamoDB session store backends (100% coverage) |
| `test_sso_service.py` | SsoService: device-auth flow, polling, accounts/roles, credentials, profiles (100% coverage) |
| `test_lambda_handler.py` | Lambda Mangum handler: invocation, API Gateway event routing (100% coverage) |
| `test_aws_endpoints.py` | FIPS endpoint URL helper: service mapping, region interpolation, enable/disable (100% coverage) |
| `test_audit_logger.py` | AuditLogger: enable/disable, field correctness, privacy guarantees, action classification, middleware integration |
| `test_auth_session_cache.py` | boto3 session cache: TTL expiry, per-key isolation, invalidation, reset |
| `test_error_sanitization.py` | `sanitize_error` helper: generic client messages, request_id correlation, verbose-mode opt-in, server-side logging |
| `functional/test_query_flow.py` | HTTP-level execute → status → results flow; error cases |
| `functional/test_export_flow.py` | HTTP-level export access control, CSV/JSON formats, error propagation |

Tests use `pytest` with `unittest.mock` to isolate AWS API calls. No real AWS credentials or network access are required to run the suite.

```bash
PYTHONPATH=src python -m pytest tests/ -q
# 295 passed
```

Current line coverage: **59%** (target: 87%). Key service modules (`sso_service.py`, `session_store.py`, `lambda_handler.py`, `aws_endpoints.py`) are now at 100% coverage. Remaining gap is concentrated in the Typer CLI layer (0%) and some router dependency paths. Coverage is enforced by a pre-push ratchet hook — it can only go up between pushes.

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

### Review 4 — FedRAMP Compliance Components (April 2026)

Code review of the FedRAMP audit logging, FIPS endpoint, and GovCloud changes. Three real issues found and fixed:

- 🟠 **CloudWatch Logs client bypassed FIPS endpoints** (`audit_logger.py:82`): `AuditLogger._init_cloudwatch()` created the boto3 `"logs"` client without an `endpoint_url`, even when `ARGUS_USE_FIPS_ENDPOINTS=true`. Fixed: added `"logs"` to `_FIPS_HOSTS` in `aws_endpoints.py` and wired `get_endpoint_url("logs", region)` into the CloudWatch client constructor. ✅ Resolved.
- 🟠 **SSO/OIDC clients bypassed FIPS endpoints** (`sso_service.py:66-67`): Both `sso-oidc` and `sso` boto3 clients were created without FIPS endpoints, missing from `_FIPS_HOSTS`. Fixed: added both services to `_FIPS_HOSTS` and wired `get_endpoint_url()` into `SsoService.__init__()`. ✅ Resolved.
- 🟠 **CloudWatch sequence token race condition** (`audit_logger.py:141-156`): `self._sequence_token` is mutable shared state on a module-level singleton; concurrent Lambda invocations sharing the same execution environment could collide on `put_log_events`. Fixed: added `self._lock = threading.Lock()` and wrapped the read-modify-write in `with self._lock:`. ✅ Resolved.
- 🔵 **Misleading comment in audit middleware** (`middleware.py:32-33`): Comment claimed `request.state.user_identity` is "populated by `get_current_user()`" — it never is. Fixed: updated comment to accurately describe the `X-Credential-Id` header fallback. ✅ Resolved.

7 new tests added covering: FIPS endpoint for `logs`, `sso`, `sso-oidc` services; CloudWatch client `endpoint_url` injection; `threading.Lock` presence; `_emit_to_cloudwatch` sequence token update.

### Review 5 — Security & Correctness, Round 2 (April 2026)

Second full-codebase review focusing on areas not covered in prior reviews. Two real issues found and fixed:

- 🔴 **SQL injection in information_schema table endpoint** (`catalog.py:255`): The `table_name` URL path parameter was directly interpolated into an Athena SQL query via an f-string (`AND table_name = '{table_name}'`). Since Athena doesn't support parameterized queries, a crafted path with `UNION SELECT` could exfiltrate data from any database the IAM role has access to. Fixed: added strict allowlist validation (`^[a-zA-Z0-9_]+$`) that returns HTTP 400 before any query is constructed. ✅ Resolved. 18 new tests cover both malicious inputs (6 bad names → 400) and valid inputs (4 good names → 200 with safe query).
- 🟠 **boto3 session cache had no TTL** (`auth.py:6-36`): The `_session_cache` dict held `boto3.Session` objects indefinitely by `(profile, region)` key. If credentials from the underlying profile expired (e.g. after an 8-hour SSO session), requests would fail with `ExpiredToken` errors that required a process restart. Fixed: changed the cache value to `(Session, created_at)` tuple; sessions are evicted after 1 hour (`_SESSION_TTL = 3600`). Added `invalidate_session(profile, region)` for targeted on-demand invalidation. 8 new tests cover TTL expiry, per-key isolation, reset, and invalidation.

### Review 6 — Frontend Auth & Error Hygiene, Round 3 (April 2026)

Third review focused on the full-stack auth flow and how backend exceptions surface to clients. Three real issues were fixed; one agent finding was reviewed and dismissed.

- 🔴 **Cognito Authorization header never sent** (`frontend/src/api/client.ts`): `AuthCallback.tsx` stored the Cognito access token in `sessionStorage`, but the axios client only had an interceptor for `X-Credential-Id` (SSO mode). In Cognito mode, every API request went out without an `Authorization` header, so the backend consistently rejected them with 401. Fixed: added a second request interceptor that reads `sessionStorage.getItem('cognito_access_token')` and sets `Authorization: Bearer <token>` when present. The logout flow (`authStore.clear`) now also clears the token from sessionStorage. ✅ Resolved.
- 🟠 **`credentialId` persisted to `localStorage`** (`frontend/src/stores/authStore.ts`): The Zustand `persist` middleware defaulted to localStorage, so the credentialId — which is effectively a bearer token for the DynamoDB-stored AWS credentials — survived tab closes and was readable by any script in the origin. Fixed: switched the persisted store to `createJSONStorage(() => sessionStorage)` so the token now expires when the tab closes and does not outlive the browser session. ✅ Resolved.
- 🟠 **AWS error strings leaked via `HTTPException(detail=str(e))`** (40 sites across `catalog.py`, `queries.py`, `workgroups.py`, `export.py`, `auth.py`): Raw `boto3`/`botocore` exceptions were propagated to clients verbatim, including account IDs, role ARNs, bucket names, and `QueryExecutionId`s. Fixed: introduced `argus.api.errors.sanitize_error()` which logs the full exception server-side (with a short `request_id`) and returns an `HTTPException` with a generic message plus that `request_id` for correlation. Set `ARGUS_VERBOSE_ERRORS=true` to opt back into raw messages for local development. All 40 sites refactored. ✅ Resolved. 6 new tests cover the helper; 4 existing tests updated to assert sanitized output.
- ❌ **"IDOR via `X-Credential-Id`" — misclassified**: The agent flagged that a user could read another user's credentials by sending a different `X-Credential-Id`. This finding was dismissed on inspection: the credential id is a server-generated `uuid.uuid4()` (122 bits of entropy) that IS the bearer token in the SSO architecture. There is no separate "user identity" layer to bypass. Knowing the uuid means being the user, by design — this is the same security model as a session cookie, not an Insecure Direct Object Reference. No code change required.

---

## Security Posture

Beyond the code review fixes, the following security practices are in place:

- **Authentication**: Three supported modes — AWS Cognito (JWT), AWS SSO (temporary credentials), or IAM-only (self-hosted/trusted network). No mode stores plaintext passwords.
- **Secrets**: No secrets are hardcoded. All sensitive values are environment variables or AWS-managed.
- **Credentials at rest**: Temporary AWS credentials (Lambda/SSO mode) are stored in DynamoDB encrypted with a KMS CMK. TTL auto-expires entries.
- **Transport**: HTTPS enforced end-to-end (CloudFront → API Gateway → Lambda). HTTP redirected to HTTPS at CloudFront.
- **CORS**: Locked to the explicit `ARGUS_CORS_ORIGINS` env var. In Lambda mode the application refuses to start if this is unset — wildcard origins (`*`) are never combined with `allow_credentials=True`.
- **Dependency scanning**: GitHub Actions CI runs on every push.
- **Audit logging**: Available for government deployments via `enable_audit_logging = true`. Logs metadata only — SQL text and result data are never captured. CloudWatch log group is append-only (write-only IAM permissions). See [docs/fedramp-deployment.md](docs/fedramp-deployment.md).
- **FIPS / GovCloud**: `use_fips_endpoints`, `govcloud`, and `fips_container` Terraform variables enable FedRAMP-compatible infrastructure with zero impact on standard deployments.

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
