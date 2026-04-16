# AthenaBeaver 🦫

A local DBMS CLI for AWS Athena with **automatic workgroup routing** — query your Athena databases without ever manually specifying workgroups. AthenaBeaver uses configurable naming schemas to parse database names and automatically resolve the correct workgroup and S3 output location.

## Features

- 🎯 **Auto workgroup resolution** — extracts client IDs and environments from database names
- 🔍 **Glue Data Catalog management** — browse databases, tables, and partitions
- 🗂️ **Named queries & prepared statements** — full lifecycle management
- 🏷️ **Workgroup tagging** — tag and untag Athena resources
- 🔧 **Flexible configuration** — YAML config with multiple naming schemas
- 🎨 **Rich terminal output** — beautiful tables powered by [Rich](https://github.com/Textualize/rich)

---

## Installation

```bash
pip install -e .
```

For development (includes pytest, moto, pytest-mock):

```bash
pip install -e ".[dev]"
```

---

## Quick Start

### 1. Create a configuration file

```bash
athena-beaver config init
```

This generates `athena_beaver.yaml` in the current directory. Edit it to match your setup.

### 2. Validate your config

```bash
athena-beaver config validate
```

### 3. Run a query

```bash
athena-beaver query run "SELECT * FROM my_table LIMIT 10" --database analytics_123456_prod
```

AthenaBeaver automatically resolves the workgroup (`analytics_123456_prod`) and S3 output location from your config — no `--workgroup` flag needed.

### 4. Preview workgroup resolution

```bash
athena-beaver workgroup resolve analytics_123456_prod
# Database:          analytics_123456_prod
# Parsed parts:      {'purpose': 'analytics', 'client_id': '123456', 'environment': 'prod'}
# Resolved workgroup: analytics_123456_prod
# S3 output:         s3://my-athena-results/123456/prod/
```

---

## Configuration Reference

AthenaBeaver searches for config in this order:
1. `./athena_beaver.yaml` (current directory)
2. `~/.athena_beaver.yaml` (home directory)

You can always override with `--config /path/to/config.yaml`.

### Full YAML schema

```yaml
aws:
  region: us-east-1          # AWS region (default: us-east-1)
  profile: null              # AWS profile name (null = default credential chain)

naming_schemas:
  default:
    description: "Human-readable description"
    pattern: "{purpose}_{client_id}_{environment}"
    # Fields in {braces} become named capture groups.
    # 'client_id' uses client_id_regex; all others match [^_]+

    client_id_regex: '\d{6}|\d{9}'
    # Regex for the client_id field only. Supports alternation.

    workgroup_pattern: "{purpose}_{client_id}_{environment}"
    # Python str.format() template using the same field names.

active_schema: default       # Which schema to use by default

workgroups:
  output_locations:
    # workgroup_name: s3://bucket/prefix/
    analytics_123456_prod: "s3://my-results/123456/prod/"
    analytics_123456_dev:  "s3://my-results/123456/dev/"

defaults:
  output_location: "s3://my-results/default/"  # Fallback S3 location
  max_results: 100
  query_timeout_seconds: 300
```

### How naming schemas work

Given `pattern: "{purpose}_{client_id}_{environment}"` and `client_id_regex: '\d{6}|\d{9}'`:

| Database name | purpose | client_id | environment | Workgroup |
|---|---|---|---|---|
| `analytics_123456_prod` | analytics | 123456 | prod | `analytics_123456_prod` |
| `reporting_123456789_dev` | reporting | 123456789 | dev | `reporting_123456789_dev` |
| `bad_name` | — | — | — | *(no match → uses default)* |

---

## CLI Reference

All commands support `--config`, `--profile`, and `--region` overrides.

### `athena-beaver query`

| Command | Description |
|---|---|
| `query run <SQL> --database <db>` | Execute a SQL query (auto-resolves workgroup) |
| `query status <query-id>` | Get query execution status and stats |
| `query results <query-id>` | Fetch and display results |
| `query cancel <query-id>` | Cancel a running query |
| `query list` | List recent query executions |
| `query named create <name>` | Create a named query |
| `query named list` | List named queries |
| `query named get <id>` | Get named query details |
| `query named delete <id>` | Delete a named query |
| `query prepared create <name>` | Create a prepared statement |
| `query prepared list --workgroup <wg>` | List prepared statements |
| `query prepared get <name> --workgroup <wg>` | Get a prepared statement |
| `query prepared update <name> --workgroup <wg>` | Update a prepared statement |
| `query prepared delete <name> --workgroup <wg>` | Delete a prepared statement |

**`query run` options:**

```
--database, -d    Target Athena database (required)
--workgroup, -w   Override auto-resolved workgroup
--output, -o      Override S3 output location
--wait/--no-wait  Wait for completion (default: --wait)
--results/--no-results  Show results table (default: --results)
--schema, -s      Use a specific naming schema
```

### `athena-beaver catalog`

| Command | Description |
|---|---|
| `catalog databases list` | List all Glue databases |
| `catalog databases get <name>` | Get database details |
| `catalog databases create <name>` | Create a database |
| `catalog databases delete <name>` | Delete a database |
| `catalog search --client-id <id>` | Find all databases for a client |
| `catalog tables list --database <db>` | List tables in a database |
| `catalog tables get <name> --database <db>` | Get table schema |
| `catalog tables delete <name> --database <db>` | Delete a table |
| `catalog partitions list --database <db> --table <t>` | List partitions |

### `athena-beaver workgroup`

| Command | Description |
|---|---|
| `workgroup list` | List all workgroups |
| `workgroup get <name>` | Get workgroup details |
| `workgroup create <name>` | Create a workgroup |
| `workgroup update <name>` | Update a workgroup |
| `workgroup delete <name>` | Delete a workgroup |
| `workgroup resolve <database>` | Preview workgroup resolution for a database name |
| `workgroup tags list <arn>` | List tags for a resource |
| `workgroup tags add <arn> KEY=VALUE ...` | Add tags |
| `workgroup tags remove <arn> KEY ...` | Remove tags |

### `athena-beaver config`

| Command | Description |
|---|---|
| `config show` | Display current configuration |
| `config validate` | Validate the configuration file |
| `config init` | Generate an example `athena_beaver.yaml` |
| `config schemas` | List configured naming schemas |

---

## Examples

### Automatic workgroup routing

```bash
# These databases match the default schema — no --workgroup needed:
athena-beaver query run "SELECT count(*) FROM orders" --database analytics_123456_prod
athena-beaver query run "SELECT * FROM users LIMIT 5" --database reporting_123456789_dev

# Override when needed:
athena-beaver query run "SELECT 1" --database mydb --workgroup my-custom-workgroup
```

### Find all databases for a client

```bash
athena-beaver catalog search --client-id 123456
# Returns all databases whose client_id field is "123456"
```

### Multi-schema setup

```yaml
naming_schemas:
  standard:
    pattern: "{purpose}_{client_id}_{environment}"
    client_id_regex: '\d{6}|\d{9}'
    workgroup_pattern: "{purpose}_{client_id}_{environment}"
  
  legacy:
    pattern: "{client_id}_{purpose}"
    client_id_regex: '[a-z]{3}\d{4}'
    workgroup_pattern: "wg_{client_id}"

active_schema: standard
```

```bash
# Use the legacy schema for a specific query:
athena-beaver query --schema legacy run "SELECT 1" --database abc1234_reports
```

### Preview resolution before running

```bash
athena-beaver workgroup resolve analytics_123456_prod --schema standard
```

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run a specific test file
pytest tests/test_naming.py -v
```

### Project layout

```
src/athena_beaver/
├── cli/           # Typer CLI commands
├── core/          # Config loading, naming resolution, AWS auth
├── services/      # Athena, Glue, Workgroup service wrappers
└── models/        # Pydantic schemas
tests/             # pytest test suite
```
