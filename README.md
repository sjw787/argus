# AthenaBeaver 🦫

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
- Configurable naming schema: extracts client IDs and environments from database names
- Automatically routes queries to the correct Athena workgroup and S3 output location
- Manual overrides available per database

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
git clone git@github.com:sjw787/AthenaBeaver.git
cd AthenaBeaver

python3 -m venv venv
source venv/bin/activate
pip install -e .
npm --prefix frontend install
```

### 2. Configure

```bash
cp athena_beaver.yaml.example athena_beaver.yaml
```

Edit `athena_beaver.yaml` — at minimum set your AWS region and S3 output location:

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

AthenaBeaver looks for config in this order: env vars → `./athena_beaver.yaml` → `~/.athena_beaver.yaml`

### Key environment variables (Lambda / hosted)

| Variable | Description |
|---|---|
| `AB_AUTH_MODE` | `sso` (default) \| `cognito` \| `none` |
| `AB_REGION` | AWS region |
| `AB_OUTPUT_LOCATION` | S3 URI for Athena query results |
| `AB_CORS_ORIGINS` | Comma-separated allowed origins (default: `*` on Lambda) |
| `AB_SESSION_STORE` | `memory` (default) \| `dynamodb` |
| `LAMBDA_RUNTIME` | Set to `1` when running on Lambda |
| `ATHENA_BEAVER_CONFIG` | Full config as a JSON string (overrides YAML) |

### `athena_beaver.yaml`

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

# Optional: auto-route databases to workgroups by name pattern
naming_schemas:
  default:
    description: "Standard schema: <purpose>_<clientid>_<environment>"
    pattern: "{purpose}_{client_id}_{environment}"
    client_id_regex: '\d{6}|\d{9}'
    workgroup_pattern: "{purpose}_{client_id}_{environment}"

active_schema: default
```

### Workgroup routing

If your databases follow a naming convention (e.g. `analytics_123456_prod`), AthenaBeaver automatically routes queries to the correct workgroup:

| Database | Resolved workgroup |
|---|---|
| `analytics_123456_prod` | `analytics_123456_prod` |
| `reporting_789012_dev` | `reporting_789012_dev` |
| `other_db` | *(default output location)* |

---

## Project Layout

```
src/athena_beaver/
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

