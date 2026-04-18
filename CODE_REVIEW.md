# Code Review Guide for Argus for Athena

This document tells AI agents how to conduct a structured code review of this project. Read it before starting any review. Record your findings in the **Code Reviews** section of [CONSIDERATIONS.md](CONSIDERATIONS.md) using the format described in [AGENTS.md](AGENTS.md).

---

## Before You Start

1. Read [AGENTS.md](AGENTS.md) — understand the project rules and invariants.
2. Read [SECURITY_REVIEW.md](SECURITY_REVIEW.md) — security concerns are separated into their own checklist.
3. Read [docs/workgroup-routing.md](docs/workgroup-routing.md) — the core tenant-isolation invariants are defined there; treat violations as 🔴 Critical.
4. Read [PRIVACY.md](PRIVACY.md) — data-handling commitments that must be upheld.
5. Scope the review: a full review covers all layers; a targeted review can focus on a specific area (e.g. "query execution path", "auth flow"). State the scope clearly in CONSIDERATIONS.md.

---

## Review Checklist

Work through these areas in order. Mark each finding with its severity before moving on.

---

### 1. Correctness

**Backend — `src/argus/`**

- [ ] **Query execution path** (`services/athena_service.py`, `api/routers/queries.py`): Does `StartQueryExecution` always receive the correct `WorkGroup` and `OutputLocation`? Trace `_resolve_workgroup` and `_resolve_output` for every code path including the case where no assignment exists.
- [ ] **Error propagation**: Do boto3 `ClientError` exceptions surface a useful HTTP status code, or do they silently become 500s? Check all routers for bare `except Exception`.
- [ ] **Pagination**: Glue/Athena APIs paginate via `NextToken`. Verify that `catalog_service.py` and `athena_service.py` handle pagination correctly and don't silently truncate results.
- [ ] **SSE stream** (`api/routers/queries.py`): Does the event stream close cleanly when a query reaches a terminal state (`SUCCEEDED`, `FAILED`, `CANCELLED`)? Is there a timeout guard so the stream doesn't stay open forever?
- [ ] **Config loading** (`core/config.py`): What happens when a required config value is missing? Are defaults safe? Check `output_location=None` path — it causes a confusing Athena error rather than a clear 400.
- [ ] **Workgroup assignment persistence**: Does saving a workgroup assignment (`POST /api/config/workgroup-assignment`) correctly write to the config store and is the change reflected immediately in subsequent queries?

**Frontend — `frontend/src/`**

- [ ] **SQL injection into WHERE clause** (`components/results/ResultsGrid.tsx` — `addWhereCondition`): Is the value correctly escaped? Single quotes inside string values must be doubled. NULL, boolean, numeric, and temporal types must follow their formatting rules. Verify the regex for converting `= value` to `IN (...)` handles quoted strings with embedded commas or parens.
- [ ] **Editor tab SQL state**: When `updateTab` writes new SQL back to the store, does the CodeMirror editor reflect the change, or does it hold stale state? Check how `editorStore` → CodeMirror sync works.
- [ ] **Multi-query execution**: When multiple statements are separated by `;`, are they all dispatched? Is the UI correctly showing per-query status tabs?
- [ ] **Race conditions in query polling**: The `useQueryStatus` hook polls/uses SSE. Is there a risk of a stale state overwriting a newer one if the component re-renders mid-flight?
- [ ] **Auto-limit**: Does the `LIMIT N` injection logic correctly detect existing `LIMIT` clauses to avoid double-limiting? Check the regex in `lib/` or wherever this lives.

---

### 2. Code Quality

- [ ] **Duplication**: Are service methods duplicated across routers? All AWS API calls should go through the service layer (`services/`), not be inlined in routers.
- [ ] **Type safety**: All FastAPI request/response models must use Pydantic (`models/` or `api/schemas.py`). Raw dicts or `Any` types in route handlers are a red flag.
- [ ] **Frontend types**: No `any` in TypeScript without a comment explaining why. Check `api/client.ts` — all API response types must be typed.
- [ ] **Dead code**: Check for unused imports, unused Pydantic fields, and unreachable branches (especially in `naming.py` — the old naming-schema auto-resolution is deprecated).
- [ ] **Consistent error handling**: Frontend API calls should go through the typed client in `api/client.ts` and handle errors uniformly. Watch for uncaught promise rejections.
- [ ] **React anti-patterns**: No business logic in render functions. Expensive computations (e.g. `colDefs`, `rowData`) should be memoized if they depend on data that changes frequently. Check `ResultsGrid.tsx`.
- [ ] **Zustand store hygiene**: Transient query state (`isLoading`, `queryError`, `queryExecutions`) must be stripped from persisted state — verify the `partialize` function in `editorStore.ts` is correct.

---

### 3. Test Coverage

- [ ] Run `PYTHONPATH=src python -m pytest tests/ -q --cov=argus --cov-report=term-missing` and note the uncovered lines.
- [ ] Identify any new code added since the last review that has **no test coverage**.
- [ ] Verify that the critical paths (workgroup resolution, auth middleware, query execution, config loading) have unit tests.
- [ ] Check that error paths are tested — not just the happy path. A service that always succeeds in tests but fails in prod is worse than no test.
- [ ] Note the current coverage baseline (`.coverage-baseline`) and whether it matches the reported percentage.

---

### 4. Dependency Health

- [ ] Run `pip-audit` (or `pip install pip-audit && pip-audit`) on the Python dependencies.
- [ ] Run `npm audit` in `frontend/` on the JavaScript dependencies.
- [ ] Flag any package with a known CVE at **High** or **Critical** severity. Low-severity findings can be noted as 🔵 Low.
- [ ] Check that `ag-grid-community` is used, not `ag-grid-enterprise` (no license required for community edition). Verify `frontend/package.json`.
- [ ] Check that all licenses are compatible with the project's MIT license. `npm ls --all` or `license-checker` can help.

---

### 5. Infrastructure & Configuration

- [ ] **Terraform state** (`infra/`): Are all sensitive outputs marked `sensitive = true`? Check `outputs.tf`.
- [ ] **IAM roles**: Are Lambda execution roles following least-privilege? Glue requires some wildcard resource ARNs (AWS limitation), but Athena and S3 actions should be scoped to specific buckets/prefixes where possible.
- [ ] **KMS**: Is the DynamoDB session table encrypted with the CMK defined in `infra/`? Is key rotation enabled?
- [ ] **CloudFront headers**: Is the `X-Credential-Id` header in the CloudFront forwarded-headers list? Without it, SSO auth breaks at the CDN layer.
- [ ] **CORS**: In Lambda mode, does the app refuse to start if `ARGUS_CORS_ORIGINS` is unset? Wildcard + credentials is a known misconfiguration.
- [ ] **GitHub Actions secrets**: Are workflow files reading secrets via `${{ secrets.NAME }}` only? No secret values printed to logs with `echo` or `run: echo $SECRET`.

---

### 6. Documentation Accuracy

- [ ] Do the env var tables in `README.md` and `docs/local-development.md` match the variables actually read in `src/argus/core/config.py`?
- [ ] Does `CONSIDERATIONS.md` reflect the current test count and coverage percentage?
- [ ] Is `PRIVACY.md` still accurate? If new data is stored or logged anywhere, it needs a table entry.
- [ ] Are the auth flow descriptions in `docs/auth-sso.md` and `docs/auth-cognito.md` consistent with the actual implementation in `src/argus/api/routers/auth.py`?

---

## Severity Definitions

| Severity | Label | Criteria |
|---|---|---|
| 🔴 Critical | Critical | Exploitable vulnerability, auth bypass, data loss risk, tenant isolation violation |
| 🟠 High | High | Security weakness exploitable under realistic conditions, incorrect behaviour with real data |
| 🟡 Medium | Medium | Missing best practice, degraded security posture, correctness issue only hit in edge cases |
| 🔵 Low | Low | Minor issue, dead code, cosmetic, informational |
| ✅ | Confirmed OK | Area reviewed, no issues found — record this explicitly |

---

## Recording Your Findings

Append a new section to [CONSIDERATIONS.md](CONSIDERATIONS.md):

```markdown
### Review N — <Scope> (<Month Year>)

| Severity | Issue | Resolution |
|---|---|---|
| 🔴 Critical | Description | Fixed / Not fixed (reason) |
| ✅ | Area reviewed | No issues found |
```

- Number reviews sequentially.
- If no issues are found in a reviewed area, record `✅` — it is meaningful that you checked.
- If you fix an issue as part of the review, describe the fix in the Resolution column.
- If you choose not to fix something (e.g. known limitation, out of scope), say so explicitly and explain why.
