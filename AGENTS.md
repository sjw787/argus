# Agent Instructions

This file provides instructions for AI agents (GitHub Copilot, Claude, etc.) working on the Argus for Athena project. Follow these guidelines to maintain code quality and keep project documentation accurate as the codebase evolves.

---

## Project Overview

Argus for Athena is a browser-based DBMS for AWS Athena. It has a **FastAPI backend** and a **React/TypeScript frontend**, deployable locally or on AWS Lambda + CloudFront. The codebase was initially generated entirely by AI and is maintained with continued AI assistance.

Key directories:
```
src/argus/   — Python backend (FastAPI)
  api/routers/       — HTTP route handlers
  services/          — AWS SDK business logic (Athena, Glue, SSO)
  core/              — Config, auth, session store
  models/            — Pydantic schemas
frontend/src/        — React/TypeScript frontend
  components/        — UI components
  stores/            — Zustand state stores
  hooks/             — Custom React hooks
  api/               — Axios client and API functions
infra/               — Terraform (Lambda, CloudFront, S3, DynamoDB, Cognito)
deploy/              — Dockerfile, build/deploy shell scripts
tests/               — pytest test suite
docs/                — Markdown guides (see `docs/workgroup-routing.md` for
                       the app's core tenant-isolation invariants)
```

---

## Development Rules

### Always run the test suite after making changes
```bash
source venv/bin/activate
PYTHONPATH=src python -m pytest tests/ -q --cov=argus --cov-report=term-missing
```
All tests must pass before committing. Do not skip or delete tests to make the suite pass.

### Code coverage requirements

Coverage is enforced automatically by a pre-push git hook (`scripts/pre-push`). Install it once after cloning:
```bash
bash scripts/install-hooks.sh
```

The hook enforces a two-phase coverage policy with a **ratchet**:

| Phase | Condition | Behaviour |
|-------|-----------|-----------|
| **Ratchet active** | Coverage < 87% | Push **blocked** if coverage dropped below `.coverage-baseline`. Otherwise allowed with progress warning. Baseline updated on every successful push. |
| **Target achieved** | Coverage first reaches 87% | `.coverage-threshold-met` is created. Ratchet replaced by floor. |
| **Floor enforced** | Coverage < 85% after target met | **Push blocked.** Restore coverage before pushing. |

The `.coverage-baseline` file is committed to the repo and updated automatically after every successful push. This means coverage can only ever go up (or hold) until the 87% target is reached.

**As an agent, when you add new features or modify existing code:**
1. Add or update tests to cover the new behaviour
2. Run coverage locally and check the percentage
3. If coverage dropped and the floor is active (`.coverage-threshold-met` exists), write additional tests before pushing
4. Aim to increase coverage with every meaningful change — the current target is **87%**

### Do not write data to disk during request handling
The application is a pass-through to AWS APIs. Query results, schema data, and SQL text must **never** be written to files, databases, or logs. Use in-memory buffers only. See [PRIVACY.md](PRIVACY.md).

### No secrets in source code
All sensitive values (AWS credentials, API keys, Cognito pool IDs) must come from environment variables or AWS-managed secrets. Never hardcode them.

### Keep CORS locked down
Do not change CORS to allow all origins (`*`). The `ARGUS_CORS_ORIGINS` env var is the correct mechanism.

### Prefer env vars over config file changes
Runtime behaviour should be controlled via environment variables (see `src/argus/core/config.py`). The `argus.yaml` config file is for user preferences only.

---

## When You Add or Modify Tests

Update the test count and module table in **[CONSIDERATIONS.md](CONSIDERATIONS.md)**:

1. Run `PYTHONPATH=src python -m pytest tests/ -q` and note the new total
2. Update the count in the **Unit Tests** section header: `**N tests passing across M test modules:**`
3. If you added a new test file, add a row to the module table describing what it covers
4. If you deleted tests, explain why in your commit message

---

## When You Conduct a Code Review

Before starting, read the dedicated review guides:
- **[CODE_REVIEW.md](CODE_REVIEW.md)** — full checklist: correctness, quality, tests, deps, infra, docs
- **[SECURITY_REVIEW.md](SECURITY_REVIEW.md)** — focused security checklist: auth, injection, tenant isolation, CORS, IAM, frontend XSS

Append findings to the **Code Reviews** section in **[CONSIDERATIONS.md](CONSIDERATIONS.md)**:

1. Add a new `### Review N — <Topic> (<Month Year>)` subsection
2. List each finding with severity (🔴 Critical / 🟠 High / 🟡 Medium / 🔵 Low)
3. Document the resolution (or note if left unresolved and why)
4. If the review found no issues, record that explicitly — it's meaningful

Severity guide:
- 🔴 **Critical** — exploitable vulnerability, data loss risk, or auth bypass
- 🟠 **High** — security weakness, incorrect behaviour under realistic conditions
- 🟡 **Medium** — missing best practice, degraded security posture
- 🔵 **Low** — minor issue, informational, or cosmetic

---

## When You Update the Privacy or Security Posture

If you change how data flows, what is stored, or how auth works:

1. Update **[PRIVACY.md](PRIVACY.md)** to reflect the new behaviour
2. Update the **Security Posture** section in **[CONSIDERATIONS.md](CONSIDERATIONS.md)** if applicable
3. If a new category of data is now stored (even temporarily), add it to the storage table in PRIVACY.md with retention and purpose

---

## When You Add Infrastructure

If you add a new AWS resource in `infra/`:

1. Document it in [`docs/deployment.md`](docs/deployment.md)
2. Add any new required env vars to the table in [README.md](README.md)
3. Check whether the new resource stores customer data — if so, update PRIVACY.md

---

## Commit Message Format

```
<type>: <short description>

[optional body]

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `infra`

---

## What This Project Does Not Do (Keep It That Way)

- ❌ No analytics or telemetry — do not add tracking scripts, error reporting SDKs, or usage metrics
- ❌ No persistent query storage — do not add a query history database or result cache
- ❌ No third-party HTTP calls — all network requests go to AWS endpoints only
- ❌ No logging of query text or result data — logs must never contain customer data

If a feature would require any of the above, flag it explicitly and discuss with the project owner before implementing.

---

## Running Locally

```bash
# Backend
source venv/bin/activate
python main.py

# Frontend
cd frontend && npm run dev

# Tests
PYTHONPATH=src python -m pytest tests/ -q
```

See [`docs/local-development.md`](docs/local-development.md) for full setup instructions.
