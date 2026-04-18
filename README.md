# Argus for Athena 🦫

[![codecov](https://codecov.io/gh/sjw787/argus/graph/badge.svg?token=)](https://codecov.io/gh/sjw787/argus)

A browser-based database manager for **AWS Athena** — inspired by DBeaver. Browse schemas, write and execute SQL, view results, and manage workgroups from a clean web UI. Runs locally or deployed to AWS Lambda + CloudFront.

---

## Features

### SQL Editor
- Multi-tab editor with syntax highlighting (CodeMirror + Athena/Presto dialect)
- SQL autocomplete — keywords, functions, table and column names from the active database
- Real-time syntax diagnostics (600 ms delay)
- Run multiple queries in one pane separated by `;` — executed in parallel
- Run only the selected text
- Format query (standard or compact style)
- Auto-limit — appends `LIMIT N` to `SELECT` queries with no limit
- Cancel running queries from the results pane or the Active Queries panel

### Results
- Paginated data grid with column sorting
- Export to CSV, JSON, Excel, or Parquet
- Query execution time and rows scanned
- Per-query status: running, succeeded, failed, cancelled

### Database Navigator
- Browse all Glue catalog databases and tables
- Lazy-loaded with server-side search — handles 500+ databases
- Context menus: Select Top 100, copy table name, view DDL, ER diagram
- Optional `information_schema` pinned at the top

### ER Diagram
- Visual entity-relationship diagram for any database
- Interactive: zoom, pan, drag nodes

### Query History & Active Queries
- History panel: recent executions with status, duration, and query text
- Active Queries panel: real-time view of running queries with cancel support

### Authentication
- **AWS SSO** — browser-based device code flow, multi-account and multi-role support
- **Amazon Cognito** — JWT-based auth for hosted deployments, with hosted UI redirect
- **No-auth / IAM-only** — for VPN-internal deployments where auth is handled at the network layer
- Auth mode is runtime-configurable; the frontend adapts automatically

### Workgroup Routing
- Explicit database → workgroup assignments via the UI
- Automatically routes queries to the correct Athena workgroup and S3 output location

### Settings
- Dark / light theme
- Toggle autocomplete, diagnostics, history panel, `information_schema`
- Format style and auto-limit row count
- Administrator-lockable settings (via `locked_settings` in config)

---

## Deployment Options

| Mode | Description |
|---|---|
| **Local** | FastAPI + Vite, runs on `localhost:8000`. No AWS infrastructure needed beyond Athena access. |
| **Lambda + CloudFront** | Docker image on Lambda behind API Gateway, frontend on S3/CloudFront, custom domain via Route 53. Fully managed by Terraform. |

See [`docs/deployment.md`](docs/deployment.md) for the full deployment guide.

---

## Requirements

- Python 3.12+
- Node.js 20+
- An AWS account with Athena and Glue access
- AWS SSO configured, or a valid `~/.aws/credentials` profile (for local dev)

---

## Local Setup

### 1. Clone and install

```bash
git clone git@github.com:sjw787/ArgusForAthena.git
cd Argus for Athena

python3 -m venv venv
source venv/bin/activate
pip install -e .
npm --prefix frontend install
```

### 2. Configure

```bash
cp argus.yaml.example argus.yaml
```

Edit `argus.yaml` — at minimum set your AWS region and S3 output location:

```yaml
aws:
  region: us-east-1
  profile: null  # null = default credential chain

defaults:
  output_location: s3://my-athena-results/default/
```

### 3. Run

```bash
# Production mode — FastAPI serves the built frontend at http://localhost:8000
./start.sh

# Development mode — Vite HMR on :5173, FastAPI with hot reload on :8000
./start.sh dev
```

See [`docs/local-development.md`](docs/local-development.md) for the full local dev guide.

---

## Configuration Reference

Argus for Athena looks for config in this order: env vars → `./argus.yaml` → `~/.argus.yaml`

### Key environment variables (Lambda / hosted)

| Variable | Description |
|---|---|
| `ARGUS_AUTH_MODE` | `sso` (default) \| `cognito` \| `none` |
| `ARGUS_REGION` | AWS region |
| `ARGUS_OUTPUT_LOCATION` | S3 URI for Athena query results |
| `ARGUS_CORS_ORIGINS` | Comma-separated allowed origins (default: `*` on Lambda) |
| `ARGUS_SESSION_STORE` | `memory` (default) \| `dynamodb` |
| `LAMBDA_RUNTIME` | Set to `1` when running on Lambda |
| `ARGUS_CONFIG` | Full config as a JSON string (overrides YAML) |

### `argus.yaml`

```yaml
aws:
  region: us-east-1
  profile: null                   # Named AWS profile, or null for default chain

workgroups:
  output_locations:
    my-workgroup: s3://my-bucket/results/

defaults:
  output_location: s3://my-bucket/results/default/
  max_results: 100
  query_timeout_seconds: 300

# Optional: lock settings so users can't change them
# locked_settings:
#   - autoLimit
#   - formatStyle
# Valid keys: theme, sqlAutocomplete, sqlDiagnostics, showHistoryDefault,
#             showInformationSchema, formatStyle, autoLimit
```

### Workgroup routing

Assign databases to workgroups through the UI (**Settings → Workgroup Assignments**) or directly in `argus.yaml`:

```yaml
workgroups:
  assignments:
    analytics_123456_prod: wg_123456_prod
    analytics_123456_dev:  wg_123456_dev
  output_locations:
    wg_123456_prod: s3://my-bucket/123456/prod/
    wg_123456_dev:  s3://my-bucket/123456/dev/
```

Databases without an explicit assignment fall back to Athena's `primary` workgroup.

---

## Project Layout

```
src/argus/
├── api/
│   ├── routers/       # FastAPI route handlers (auth, catalog, queries, workgroups, config)
│   ├── schemas.py     # API request/response models
│   ├── dependencies.py # Auth dependencies (Cognito JWT, SSO, no-auth)
│   └── app.py         # FastAPI app factory
├── core/              # Config loading, auth, session store, workgroup naming
├── models/            # Pydantic data models
├── services/          # Athena, Glue, and Workgroup boto3 service wrappers
└── lambda_handler.py  # Mangum entry point for Lambda

frontend/src/
├── api/               # API client (axios)
├── components/        # React UI (editor, navigator, results, layout, auth dialogs)
├── hooks/             # useQueryStatus (SSE + polling fallback), useAuthConfig
├── stores/            # Zustand state (auth, editor tabs, theme, UI)
└── lib/               # CodeMirror SQL completion and diagnostics

infra/                 # Terraform — ECR, Lambda, API Gateway, S3, CloudFront, Route 53, ACM, DynamoDB, Cognito
deploy/                # Dockerfile, build.sh, deploy.sh, destroy.sh
.github/workflows/     # CI/CD (deploy.yml, destroy.yml)
docs/                  # Deployment and auth guides
tests/                 # pytest suite
```

---

## Government Deployment (FedRAMP / GovRAMP)

Argus supports deployment in federal environments with all compliance features **opt-in** — a standard deployment is completely unchanged.

| Capability | Terraform variable | Description |
|---|---|---|
| Audit logging | `enable_audit_logging = true` | Structured metadata records in CloudWatch (no SQL or result data) |
| GovCloud | `govcloud = true` | Correct `aws-us-gov` ARN partition for all IAM resources |
| FIPS endpoints | `use_fips_endpoints = true` | Route boto3 calls through FIPS-validated AWS endpoints |
| FIPS container | `fips_container = true` | Enable FIPS-mode OpenSSL in the container image |

See **[docs/fedramp-deployment.md](docs/fedramp-deployment.md)** for the full checklist, audit log schema, and incident response guide.

---

## Documentation

| Doc | Description |
|---|---|
| [`docs/local-development.md`](docs/local-development.md) | Local dev setup, config reference, troubleshooting |
| [`docs/deployment.md`](docs/deployment.md) | Lambda + CloudFront deployment guide |
| [`docs/auth-sso.md`](docs/auth-sso.md) | AWS SSO auth mode |
| [`docs/auth-cognito.md`](docs/auth-cognito.md) | Cognito auth mode |
| [`docs/auth-none.md`](docs/auth-none.md) | No-auth / IAM-only mode |

---

## API Docs

Interactive API docs are available when running locally:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc


---

## Acknowledgements

This project was designed by [@sjw787](https://github.com/sjw787) and built entirely by [GitHub Copilot](https://github.com/features/copilot) (powered by Claude Sonnet and Opus). Every line of code — backend, frontend, infrastructure, tests, and documentation — was written by AI from a series of prompts, ideas, and product decisions made by the human author.

The ideas, product vision, and architectural direction are the author's. The implementation is AI's. It's an experiment in what's possible when you bring a clear vision and let the tools do the building.
