# Security Review Guide for Argus for Athena

This document tells AI agents how to conduct a focused security review of this project. It complements [CODE_REVIEW.md](CODE_REVIEW.md), which covers general correctness and quality. Record findings in the **Code Reviews** section of [CONSIDERATIONS.md](CONSIDERATIONS.md).

Security reviews should be run:
- Before any code is pushed to `main` that touches auth, query execution, credential handling, or infrastructure.
- When a new auth mode or AWS service is added.
- Periodically (recommended: every significant release).

---

## Threat Model

Argus for Athena is a **privileged internal tool**: it proxies AWS API calls on behalf of authenticated users. The threat model assumes:

- **Trusted users**: Users who can reach the app have legitimate AWS access. The goal is isolation (one user/client can't touch another's data), not hardening against malicious users trying to break the app.
- **Untrusted input**: All query text, filter values, column names, and database names coming from the browser must be treated as untrusted.
- **Shared Lambda execution role**: In Cognito and no-auth modes, all users share the same IAM execution role. The app itself is the only access control layer.
- **SSO credentials are per-user**: In SSO mode, each user's temporary credentials are scoped to their AWS role. A credential leak is equivalent to leaking an AWS access key.
- **No customer data at rest**: The app is a pass-through. Query results, SQL text, and schema metadata must never be persisted anywhere.

---

## Security Checklist

### 1. Authentication & Session Management

- [ ] **Auth mode detection** (`src/argus/api/routers/auth.py`, `src/argus/api/dependencies.py`): Does the correct auth dependency run for every protected route? Are there any routes that skip auth in non-`none` modes?
- [ ] **JWT validation (Cognito mode)**: Does the backend verify:
  - Signature against the Cognito JWKS endpoint?
  - `aud` claim matches the configured `client_id`?
  - `iss` claim matches `https://cognito-idp.{region}.amazonaws.com/{pool_id}`?
  - Token expiry (`exp` claim)?
  - Token type (`id` token, not `access`)?
- [ ] **SSO credential expiry**: Before using cached SSO credentials, does the backend check the `Expiration` field? Expired credentials must return a `401`, not a cryptic `ClientError` from boto3.
- [ ] **Session fixation**: When a new SSO auth flow is started, is the old `session_id` invalidated? Can an attacker reuse a session_id from a previous flow?
- [ ] **DynamoDB session TTL**: Are session records auto-expiring? Check that TTL is enabled on the `expires_at` attribute in the `infra/` Terraform and that item TTLs are being set correctly in `core/session_store.py`.
- [ ] **Sign-out completeness**: Does `POST /api/auth/signout` delete the DynamoDB record (in Lambda mode), not just return 200? A sign-out that only clears the frontend but leaves the server-side session is a security risk.
- [ ] **Credential storage in the browser**: The `credential_id` (session identifier) is stored in `localStorage`. Verify that **no raw AWS credentials** (access key, secret key, session token) are ever stored in `localStorage`, `sessionStorage`, cookies, or any other browser-accessible location.

---

### 2. Input Handling & Injection

Argus sends user-supplied values to AWS APIs. It does not construct SQL server-side (Athena is its own SQL engine), but it does pass strings into boto3 calls.

- [ ] **boto3 parameters**: Are all user-supplied strings (database name, table name, workgroup name, query text) passed directly as boto3 parameters without string interpolation into a raw API call? There is no SQL injection risk via boto3 — Athena parses the SQL itself — but parameter injection into Glue/Athena API fields (e.g. a crafted `workgroup` name in a URL path param) could cause unexpected behaviour.
- [ ] **WHERE clause injection** (frontend — `ResultsGrid.tsx`): Values inserted into SQL via the "Add to WHERE" feature must be escaped. Verify:
  - String values: single quotes are doubled (`'` → `''`)
  - NULL: renders as `IS NULL` (no value to escape)
  - Numeric: regex-validated before being rendered unquoted
  - Boolean: only `true`/`false` rendered, not the raw cell value
  - Temporal: prefixed with `DATE`/`TIMESTAMP`/`TIME` keyword
  - Column names: always double-quoted to prevent keyword collision
- [ ] **Path parameter validation**: URL path parameters (e.g. `database_name`, `table_name`, `query_execution_id`) — are they validated by Pydantic or FastAPI's type system, or passed raw to boto3?
- [ ] **Export endpoint** (`api/routers/export.py`): Does it validate that the `query_execution_id` belongs to the requesting user/session? An attacker with a valid session shouldn't be able to download another user's results by guessing a UUID.

---

### 3. Tenant & Workgroup Isolation

This is the core security concern of the application. See [docs/workgroup-routing.md](docs/workgroup-routing.md) for the full invariant list.

- [ ] **No implicit workgroup inference**: A database with no explicit assignment must NOT be silently routed to a client workgroup derived from its name. The naming-schema auto-resolution code exists for backwards compatibility but must not be wired to query execution for new paths.
- [ ] **Output location isolation**: A client workgroup's S3 output location must be looked up from `workgroups.output_locations[wg]`, not from `defaults.output_location`. The default is only for the `primary` / non-client workgroup. Verify `_resolve_output` checks the per-workgroup map first.
- [ ] **WorkGroup always sent to Athena**: If `resolved_wg` is set, it must appear in the `StartQueryExecution` call. Dropping it causes queries to fall back to `primary` and run with the wrong IAM/billing scope.
- [ ] **Config write access**: Can an authenticated user modify `workgroups.assignments` via the API to reroute another user's queries? The config write endpoint should be admin-only or at minimum scoped to the current user's databases.

---

### 4. Data Privacy

- [ ] **No query text in logs**: Search for any `logger.info`, `logger.debug`, or `print` calls that include `sql`, `query`, or query result data. These must not exist.
- [ ] **No result data in logs**: Same for result rows, column values, or schema metadata.
- [ ] **No result data in error responses**: Error handlers must not echo back query results or SQL in HTTP responses.
- [ ] **In-memory only**: Verify that no route handler or service method writes to a file, database (other than the DynamoDB session store for auth artifacts), or cache. Use `grep -r "open(" src/` and `grep -r "write(" src/` as a quick check.
- [ ] **Export buffer**: The export endpoint streams results to the browser via an in-memory buffer (`io.BytesIO`). Confirm it is not writing to `/tmp` or any persistent path (important for Lambda, where `/tmp` is shared between warm invocations).

---

### 5. Transport & CORS

- [ ] **HTTPS enforcement**: CloudFront should redirect HTTP → HTTPS. Verify the Terraform config in `infra/` sets `viewer_protocol_policy = "redirect-to-https"`.
- [ ] **CORS configuration** (`src/argus/api/app.py`):
  - `allow_credentials=True` must NEVER be combined with `allow_origins=["*"]`.
  - In Lambda mode the app must raise `RuntimeError` if `ARGUS_CORS_ORIGINS` is unset.
  - In local dev mode (`auth_mode=none`), wildcard origins are acceptable because there are no session credentials to protect.
- [ ] **`X-Credential-Id` header forwarding**: This custom header must be in the CloudFront forwarded-headers list and the API Gateway CORS allowed-headers list. If it's stripped, SSO auth silently breaks.
- [ ] **Cookie security**: The app does not use cookies for auth (uses headers). Confirm no `Set-Cookie` headers are issued anywhere.

---

### 6. Infrastructure Security

- [ ] **Secrets in Terraform state**: Terraform state may contain sensitive values. Confirm that `backend.tf` uses an S3 remote backend (not local state) and that the S3 bucket has versioning, encryption, and blocked public access.
- [ ] **Lambda environment variables**: Do `terraform output` values for sensitive variables (Cognito pool ID, client secret if any) show as `<sensitive>`? Check `infra/outputs.tf`.
- [ ] **ECR image scanning**: Is ECR image scanning on push enabled? Check the ECR repository Terraform resource.
- [ ] **GitHub Actions OIDC**: The deploy workflow uses GitHub OIDC (no static AWS keys in secrets). Verify the trust policy's `sub` condition is scoped to `repo:sjw787/argus:*` and not a wildcard.
- [ ] **Destroy workflow protection**: The destroy workflow should be restricted to non-prod environments and require a manual confirmation string. Verify this in `.github/workflows/destroy.yml`.
- [ ] **IAM role scope**: The Lambda execution role should not have `*` on Athena/S3 actions where resource-level scoping is possible. `glue:GetDatabases` and similar require wildcard — document these as known exceptions in CONSIDERATIONS.md.

---

### 7. Dependency Vulnerabilities

Run these commands and review the output:

```bash
# Python
source venv/bin/activate
pip-audit

# JavaScript
cd frontend && npm audit
```

- Flag any **Critical** or **High** severity CVEs as 🔴 or 🟠 findings.
- For each finding, check whether the vulnerable code path is actually reachable in this application (e.g. a vuln in a test-only dependency is lower risk).
- Check that `ag-grid-enterprise` is NOT in `package.json` — only `ag-grid-community` (MIT licensed) is permitted.

---

### 8. Frontend Security

- [ ] **XSS**: Search for `dangerouslySetInnerHTML` in `frontend/src/`. Any use must have a documented justification. Currently there should be none.
- [ ] **Open redirects**: Any redirect after auth should use a fixed known URL (e.g. `/`), not a URL taken from a query parameter.
- [ ] **`localStorage` contents**: Run a review of everything stored via Zustand persist. Confirm only UI preferences and the `credential_id` (session identifier) are stored — never raw AWS keys or tokens.
- [ ] **Content Security Policy**: Is a CSP header set? CloudFront can add it via a response-headers policy. A missing CSP is 🟡 Medium.
- [ ] **Dependency integrity**: `package-lock.json` should be committed and `npm ci` used in CI (not `npm install`) to enforce lock-file integrity.

---

## High-Risk Files to Always Check

These files are the most sensitive. Any change to them should trigger a security review:

| File | Why it's sensitive |
|---|---|
| `src/argus/api/dependencies.py` | Defines auth dependency — used by every protected route |
| `src/argus/api/routers/auth.py` | SSO device flow, Cognito JWT validation, sign-out |
| `src/argus/core/session_store.py` | Reads/writes AWS credentials to DynamoDB |
| `src/argus/services/athena_service.py` | Constructs `StartQueryExecution` — workgroup and output location assignment |
| `src/argus/core/config.py` | Config loading — env var overrides, defaults |
| `src/argus/api/app.py` | CORS configuration, middleware setup |
| `frontend/src/stores/authStore.ts` | Stores credential_id in localStorage |
| `frontend/src/api/client.ts` | All outbound API calls — ensure credential header is always sent |
| `frontend/src/components/results/ResultsGrid.tsx` | WHERE clause value injection |
| `infra/iam.tf` / `infra/lambda.tf` | IAM roles and Lambda env vars |

---

## Recording Findings

Append to [CONSIDERATIONS.md](CONSIDERATIONS.md) under **Code Reviews**:

```markdown
### Review N — Security: <Scope> (<Month Year>)

| Severity | Issue | Resolution |
|---|---|---|
| 🔴 Critical | ... | Fixed / Not fixed (reason) |
| ✅ | Area reviewed | No issues found |
```

If you fix an issue during the review, describe the change in the Resolution column. If you choose not to fix something, explain why. A `✅` on a reviewed area that found no issues is as valuable as a finding — it documents that the area was checked.
