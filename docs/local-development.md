# Local Development Guide

This guide walks you through setting up and running AthenaBeaver locally for development.

---

## Prerequisites

| Tool | Required version | Notes |
|------|-----------------|-------|
| Python | 3.10+ | 3.12 recommended |
| Node.js | 18+ | 20 recommended |
| npm | bundled with Node.js | — |
| AWS CLI | v2 | For SSO login or credential setup |
| Git | any recent version | — |

You also need an AWS account with access to Athena and the Glue catalog, plus an S3 bucket where Athena can write query results.

---

## Initial Setup

### 1. Clone the repository

```bash
git clone git@github.com:sjw787/AthenaBeaver.git
cd AthenaBeaver
```

### 2. Set up the Python virtual environment

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -e .
```

`pip install -e .` installs the package in editable mode so changes to `src/` are picked up immediately without reinstalling.

To include dev dependencies (pytest, moto for mocking):

```bash
pip install -e ".[dev]"
```

### 3. Install frontend dependencies

```bash
cd frontend && npm install
# or from repo root:
npm --prefix frontend install
```

### 4. Create your config file

```bash
cp athena_beaver.yaml.example athena_beaver.yaml
```

Edit `athena_beaver.yaml`. At minimum you need:

```yaml
aws:
  region: us-east-1          # your AWS region

defaults:
  output_location: s3://your-bucket/athena-results/
```

See the [Configuration Reference](#configuration-reference) below for all options.

---

## Configuration Reference

AthenaBeaver looks for config in this order:

1. `./athena_beaver.yaml` (repo root — recommended for development)
2. `~/.athena_beaver.yaml` (user home — useful for shared installs)
3. Environment variable `ATHENA_BEAVER_CONFIG` (JSON string of the full config)
4. Individual `AB_*` environment variables (see below)

### Full `athena_beaver.yaml` reference

```yaml
aws:
  region: us-east-1       # AWS region for Athena and Glue calls. Default: us-east-1
  profile: null           # Named AWS profile from ~/.aws/config. null = default credential chain

naming_schemas:
  # Define one or more schemas for auto-routing databases to workgroups.
  # Each schema extracts parts of a database name and maps them to a workgroup.
  default:
    description: "Standard schema: <purpose>_<clientid>_<environment>"
    pattern: "{purpose}_{client_id}_{environment}"        # Named capture groups
    client_id_regex: '\d{6}|\d{9}'                        # Regex to identify client IDs
    workgroup_pattern: "{purpose}_{client_id}_{environment}"  # Workgroup name template

active_schema: default    # Which naming_schema to use for workgroup resolution

workgroups:
  output_locations:
    # Map workgroup name → S3 URI. Queries routed to that workgroup use this output path.
    # analytics_123456_prod: s3://my-bucket/123456/prod/
    # analytics_123456_dev: s3://my-bucket/123456/dev/
  assignments:
    # Explicit database → workgroup overrides (bypass naming schema).
    # my_special_db: my-workgroup

defaults:
  output_location: s3://my-bucket/results/default/  # Fallback S3 path for results
  max_results: 100          # Default row limit returned to the UI
  query_timeout_seconds: 300  # How long to poll before treating a query as timed out

auth_mode: sso             # Auth mode: "sso" | "none" | "cognito". Default: sso

locked_settings: []
  # UI settings users cannot change. Omit or leave empty for no locks.
  # Valid keys: theme, sqlAutocomplete, sqlDiagnostics, showHistoryDefault,
  #             showInformationSchema, formatStyle, autoLimit
```

### Environment variable overrides

| Variable | Equivalent config key | Example |
|----------|-----------------------|---------|
| `AB_REGION` | `aws.region` | `us-west-2` |
| `AB_PROFILE` | `aws.profile` | `my-profile` |
| `AB_OUTPUT_LOCATION` | `defaults.output_location` | `s3://bucket/path/` |
| `AB_AUTH_MODE` | `auth_mode` | `none` |
| `ATHENA_BEAVER_CONFIG` | entire config as JSON | `'{"aws":{"region":"us-east-1"}}'` |

---

## Running the App

### Option A — `start.sh` (recommended)

```bash
# Dev mode: Vite on :5173 + FastAPI on :8000 (both with hot reload)
./start.sh dev

# Prod mode: FastAPI on :8000 serving the built frontend
./start.sh prod
```

`start.sh` handles activating the virtualenv, setting `PYTHONPATH`, auto-installing frontend deps if missing, and building the frontend if needed in prod mode.

### Option B — Manual (more control)

**Backend** (terminal 1):

```bash
source venv/bin/activate
PYTHONPATH=src uvicorn "athena_beaver.api.app:create_app" \
  --factory \
  --host 127.0.0.1 \
  --port 8000 \
  --reload \
  --reload-dir src
```

**Frontend** (terminal 2):

```bash
cd frontend
npm run dev
```

The Vite dev server runs on `http://localhost:5173` and proxies all `/api` requests to `http://localhost:8000`.

### Where to open the app

| Mode | URL |
|------|-----|
| Dev mode (frontend) | http://localhost:5173 |
| Dev mode (API docs) | http://localhost:8000/docs |
| Dev mode (ReDoc) | http://localhost:8000/redoc |
| Prod mode | http://localhost:8000 |

---

## Running Tests

### Python tests

```bash
source venv/bin/activate
PYTHONPATH=src python -m pytest tests/ -v
```

Tests use [moto](https://docs.getmoto.org/) to mock AWS services (Athena, Glue, S3) — no real AWS calls are made.

To run a specific test file:

```bash
PYTHONPATH=src python -m pytest tests/test_naming.py -v
```

### Frontend tests

```bash
cd frontend
npm test          # run once
npm run test:watch  # watch mode with vitest
```

---

## Common Issues

### AWS credentials not configured

**Symptom:** `NoCredentialError` or `Unable to locate credentials` in the backend logs.

**Fix:**
- For SSO: run `aws sso login --profile your-profile` and set `profile: your-profile` in `athena_beaver.yaml`.
- For access keys: ensure `~/.aws/credentials` has a `[default]` or named profile.
- Verify with: `aws sts get-caller-identity --region us-east-1`

### Port 8000 already in use

**Symptom:** `[Errno 48] Address already in use` when starting uvicorn.

**Fix:**
```bash
# Find what's using port 8000
lsof -ti :8000

# Kill it (replace PID with the actual number from above)
kill <PID>
```

Or change the port by editing the `--port` flag in `start.sh` or your manual command.

### `athena_beaver.yaml` missing

**Symptom:** Backend starts with defaults — no output location set, queries fail with `InvalidRequestException` from Athena.

**Fix:** Copy the example and fill in your S3 bucket:
```bash
cp athena_beaver.yaml.example athena_beaver.yaml
# Edit defaults.output_location
```

### `ModuleNotFoundError: No module named 'athena_beaver'`

**Symptom:** Seen when running uvicorn or pytest directly without setting `PYTHONPATH`.

**Fix:** Always prefix with `PYTHONPATH=src`, or activate the venv after running `pip install -e .`.

### Frontend shows stale data after backend restart

The frontend stores auth state and editor tabs in Zustand (in-memory). Just refresh the browser — there's nothing to clear on disk.

---

## Development Tips

### Hot reload

- **Backend:** uvicorn's `--reload --reload-dir src` watches `src/` and restarts on any `.py` change.
- **Frontend:** Vite's HMR updates components in-place without a full page reload.

### Inspecting Athena query results

Results land in S3 at the path configured in `defaults.output_location`. Each query creates a CSV file named `<QueryExecutionId>.csv`. You can download and inspect these directly:

```bash
aws s3 ls s3://your-bucket/athena-results/
aws s3 cp s3://your-bucket/athena-results/<query-id>.csv ./
```

The UI also supports exporting to CSV, JSON, Excel, or Parquet from the results pane.

### Resetting session state

Session/auth state is in-memory only — just restart the backend. There's no database or file to clear.

### API exploration

With the backend running in dev mode, interactive API docs are available at:
- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

### Building the frontend for prod mode

```bash
npm --prefix frontend run build
```

This outputs to `src/athena_beaver/api/static/`, where FastAPI picks it up automatically in prod mode.

---

## Architecture Overview

### Key directories

```
src/athena_beaver/
├── api/
│   ├── app.py              # FastAPI app factory (create_app)
│   ├── routers/            # Route handlers: auth, catalog, queries, workgroups, config, export
│   └── schemas.py          # API request/response Pydantic models
├── core/
│   ├── auth.py             # SSO device-code flow + session management
│   ├── config.py           # YAML/env config loader
│   ├── naming.py           # Workgroup name resolution from database names
│   └── session_store.py    # In-memory AWS session cache
├── models/schemas.py       # Core Pydantic config models (AppConfig, AWSConfig, etc.)
└── services/               # boto3 wrappers for Athena, Glue, and Workgroups

frontend/src/
├── api/                    # Axios API client (typed wrappers around /api/* endpoints)
├── components/             # React components: editor, navigator, results, auth, layout
├── stores/                 # Zustand state: auth, editor tabs, theme, UI settings
└── lib/                    # CodeMirror SQL completion and diagnostics engine

tests/                      # pytest suite (moto-mocked AWS)
```

### How auth works locally

With `auth_mode: sso` (default):
1. On first load the frontend calls `GET /api/auth/status`.
2. If no session is active, it redirects to the login page.
3. The login page calls `POST /api/auth/sso/start` → backend initiates a device-code flow with AWS IAM Identity Center.
4. You open the URL shown, approve the device, and the backend polls until credentials are issued.
5. Credentials are cached in-memory in `session_store.py` and used for all subsequent Athena/Glue calls.

With `auth_mode: none` (no-auth mode for local dev without SSO):
- The backend uses the ambient AWS credentials (profile or environment variables) directly.
- No login page is shown. Set this in `athena_beaver.yaml` if you just want to use your CLI credentials.

### Frontend ↔ Backend communication

- All API calls go through `/api/*` on the same origin.
- In dev mode, Vite proxies `/api` → `http://localhost:8000` (configured in `frontend/vite.config.ts`).
- In prod mode, FastAPI serves the built frontend from `src/athena_beaver/api/static/` and handles `/api` routes natively.
- Long-running query status is streamed via Server-Sent Events (`sse-starlette`).
