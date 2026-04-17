# AthenaBeaver 🦫

A local, browser-based database manager for **AWS Athena** — inspired by DBeaver. Connect to your Athena databases via AWS SSO, browse schemas, write and execute SQL, and view results, all from a clean web UI running on your machine.

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
- AWS SSO login flow (browser-based device code)
- Multi-account and multi-role support
- Automatic session refresh detection

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

## Requirements

- Python 3.10+
- Node.js 18+ (for building the frontend)
- An AWS account with Athena and Glue access
- AWS SSO configured, or a valid `~/.aws/credentials` profile

---

## Setup

### 1. Clone and install

```bash
git clone git@github.com:sjw787/AthenaBeaver.git
cd AthenaBeaver

python3 -m venv venv
source venv/bin/activate
pip install -e .
```

### 2. Configure

```bash
cp athena_beaver.yaml.example athena_beaver.yaml
```

Edit `athena_beaver.yaml` — at minimum set your AWS region and S3 output location:

```yaml
aws:
  region: us-east-1
  profile: null  # null = default credential chain, or specify a named profile

workgroups:
  output_locations:
    primary: s3://my-athena-results/default/

defaults:
  output_location: s3://my-athena-results/default/
```

### 3. Install frontend dependencies

```bash
npm --prefix frontend install
```

---

## Running

```bash
# Production mode — FastAPI serves the built frontend on http://localhost:8000
./start.sh

# Development mode — Vite on :5173, FastAPI on :8000 with hot reload
./start.sh dev
```

Open **http://localhost:8000** in your browser. You'll be prompted to sign in via AWS SSO on first launch.

---

## Configuration Reference

AthenaBeaver looks for config in this order:
1. `./athena_beaver.yaml`
2. `~/.athena_beaver.yaml`

```yaml
aws:
  region: us-east-1
  profile: null                   # Named AWS profile, or null for default chain

workgroups:
  output_locations:
    # Map workgroup name → S3 URI for query results
    my-workgroup: s3://my-bucket/results/

defaults:
  output_location: s3://my-bucket/results/default/
  max_results: 100
  query_timeout_seconds: 300

# Optional: lock UI settings so users can't change them
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

If your databases follow a naming convention (e.g. `analytics_123456_prod`), AthenaBeaver can automatically route queries to the right workgroup:

| Database | Resolved workgroup |
|---|---|
| `analytics_123456_prod` | `analytics_123456_prod` |
| `reporting_789012_dev` | `reporting_789012_dev` |
| `other_db` | *(default output location)* |

---

## Development

```bash
# Run backend with hot reload + Vite dev server
./start.sh dev

# Run tests
source venv/bin/activate
pytest tests/ -v

# Build frontend only
npm --prefix frontend run build
```

### Project layout

```
src/athena_beaver/
├── api/
│   ├── routers/       # FastAPI route handlers (auth, catalog, queries, workgroups, config)
│   ├── schemas.py     # API request/response models
│   └── app.py         # FastAPI app factory
├── core/              # Auth (SSO), config loading, workgroup naming resolution
├── models/            # Pydantic data models
└── services/          # Athena, Glue, and Workgroup boto3 service wrappers

frontend/src/
├── api/               # Axios API client
├── components/        # React UI components (editor, navigator, results, layout, auth)
├── stores/            # Zustand state (auth, editor tabs, theme, UI)
└── lib/               # CodeMirror SQL completion and diagnostics

tests/                 # pytest suite
```

---

## API Docs

When running in dev mode, interactive API docs are available at:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

