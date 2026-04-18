# UI Features Reference

A practical guide to the Argus for Athena browser interface. Target audience: developers and data analysts who know SQL but are new to the app.

---

## SQL Editor

The editor area occupies the main (right) panel. Each editor tab is independent — it has its own SQL text, query state, and results.

### Tabs

| Action | How |
|--------|-----|
| Open a new tab | Click the **+** button to the right of the tab bar |
| Rename a tab | Double-click the tab title, or right-click → **Rename** |
| Close a tab | Right-click → **Close**, or click the × on the tab |
| Close others | Right-click → **Close Others** |
| Close all | Right-click → **Close All** |

Tabs persist across page reloads via Zustand's `persist` middleware (stored in `localStorage`). Each tab restores its SQL text, scroll position, and last results on refresh.

### Running Queries

| Action | Shortcut / Control |
|--------|--------------------|
| Run the entire query | **Ctrl+Enter** (Windows/Linux) or **Cmd+Enter** (macOS), or click the **Run** button |
| Run selected text only | Select any text in the editor, then press the run shortcut — only the selection is sent |
| Cancel a running query | Click the **Cancel** button that appears in the results pane while a query is in flight |

### Multi-Statement Queries

Separate multiple SQL statements with `;`. All statements run in parallel — each statement gets its own results sub-tab inside the current editor tab. Sub-tabs are labelled `Result 1`, `Result 2`, etc.

```sql
SELECT count(*) FROM orders;
SELECT count(*) FROM customers;
```

### Formatting

Click the **Format** button in the editor toolbar to reformat the SQL in the active tab. Two styles are available (configured in Settings):

| Style | Description |
|-------|-------------|
| **Standard** | Keywords on their own lines — readable for complex queries |
| **Compact** | Single-line output — useful for copying into scripts |

### Auto-Limit

When enabled, Argus automatically appends `LIMIT N` to any `SELECT` query that does not already have a `LIMIT` clause. The default is **100 rows**. Configure the row count in **Settings → Auto-limit**. Disable it by setting the limit to `0` or toggling it off.

---

## Results Grid

Query results are displayed in a paginated [AG Grid](https://www.ag-grid.com/) table.

### Column Features

- **Sort**: click a column header to sort ascending/descending
- **Resize**: drag the column header border
- **Data type tooltip**: hover over a column header to see the **Athena data type** (e.g., `varchar`, `bigint`, `timestamp`)

### Cell Right-Click Menu

Right-click any cell to open a context menu with two options:

#### Filter by `<value>`

Applies an AG Grid client-side column filter to show only rows matching that cell's value. No re-query is issued — this filters the already-loaded result set.

#### Add to WHERE: `"col" = 'value'`

Injects a SQL predicate into the SQL of the originating editor tab. The predicate is built intelligently:

| Situation | Result |
|-----------|--------|
| First click on any column | `WHERE "col" = 'value'` appended |
| Same column clicked again | Converts to `WHERE "col" IN ('value1', 'value2')` |
| Third+ value, same column | Appended to the `IN` list |
| Different column | `AND "col2" = 'value2'` appended |
| NULL cell | `IS NULL` predicate |
| Numeric column | Unquoted: `WHERE "amount" = 42` |
| Date/timestamp column | `DATE 'YYYY-MM-DD'` or `TIMESTAMP 'YYYY-MM-DD HH:MM:SS'` literals |
| Boolean column | `true` or `false` literals |

Keyword casing (`WHERE`/`AND`/`IN`) matches the style already used in the query (uppercase or lowercase).

### Export

Use the toolbar above the grid to export the current result set:

| Format | Notes |
|--------|-------|
| **CSV** | Comma-separated, UTF-8 |
| **JSON** | Array of row objects |
| **Excel** | `.xlsx` workbook |
| **Parquet** | Binary columnar format |

---

## Database Navigator

The left pane shows all Glue catalog databases, grouped by their assigned Athena workgroup.

### Browsing

- **Expand a database** to load its tables (lazy-loaded on first expand)
- **Search box** at the top filters databases and tables via a server-side call — handles catalogs with 500+ databases without client-side performance issues
- **`information_schema`** can be pinned to the top of the list via **Settings → Show Information Schema**

### Table Right-Click Menu

Right-click any table in the navigator to see:

| Action | Description |
|--------|-------------|
| **Select Top 100 rows** | Opens a new editor tab with `SELECT * FROM <table> LIMIT 100` |
| **Copy table name** | Copies the fully-qualified table name to the clipboard |
| **View DDL** | Opens a new editor tab with `SHOW CREATE TABLE <table>` and runs it |
| **View ER diagram** | Opens (or focuses) an ER Diagram tab for the table's database |

---

## ER Diagram Tab

Each database can have one **ER Diagram** tab. Open it by right-clicking any table in the navigator and selecting **View ER diagram**.

- If an ER Diagram tab for that database is already open, it is brought into focus rather than opening a duplicate.
- Tab title: `ER: <database_name>` with a diagram icon.
- The diagram is interactive: zoom, pan, and drag individual table nodes.
- Edges between tables represent foreign-key relationships detected from the Glue schema.

---

## Query History Pane

A collapsible panel at the bottom of the screen shows recent query executions.

### Columns

| Column | Description |
|--------|-------------|
| Status | `SUCCEEDED`, `FAILED`, or `CANCELLED` |
| Duration | Wall-clock time for the query |
| Rows | Number of rows returned |
| Query | Truncated query text |

Click **Open in editor** on any row to load that query's SQL into a new editor tab.

### Collapse / Expand

- Click the **▲ Query History** bar at the bottom of the screen to toggle the pane.
- The collapse state **persists across page reloads** — if you close it, it stays closed on refresh.
- The default collapsed state is configurable in **Settings → Show Query History by Default**.

---

## Settings

Open Settings via the **gear icon** (⚙) in the top toolbar.

| Setting | Description | Default |
|---------|-------------|---------|
| **Theme** | Light or Dark | Light |
| **SQL Autocomplete** | Toggle CodeMirror SQL completion on/off | On |
| **SQL Diagnostics** | Real-time error highlighting (600 ms delay after typing) | On |
| **Show Query History by Default** | Whether the history pane starts expanded | On |
| **Show Information Schema** | Pin `information_schema` at the top of the navigator | Off |
| **Format Style** | `Standard` (keyword-per-line) or `Compact` (single line) | Standard |
| **Auto-limit** | Default `LIMIT N` appended to SELECT queries | 100 |
| **Sign Out** | End the current session and return to the login screen | — |

All settings are persisted in `localStorage` via Zustand.

### Locked Settings

Administrators can prevent users from changing specific settings by adding keys to `locked_settings` in `argus.yaml`:

```yaml
locked_settings:
  - theme
  - autoLimit
  - showInformationSchema
```

Locked settings are displayed but greyed out in the Settings panel.

### Sign Out Behaviour by Auth Mode

| Auth mode | Sign Out effect |
|-----------|----------------|
| **SSO** | Calls `POST /api/auth/signout` — invalidates the server-side session (DynamoDB entry deleted), clears `credential_id` from frontend, returns to login screen |
| **Cognito** | Redirects to `https://<cognito_domain>/logout?client_id=<id>&logout_uri=<app_url>`, invalidating the Cognito session; frontend token state is cleared before redirect |
| **None** | Clears frontend state only — no server-side credentials exist to revoke |

---

## Workgroup Assignment

Databases can be assigned to specific Athena workgroups directly in the UI. Assignments are saved to `argus.yaml` (or the config store in Lambda deployments). Databases without an explicit assignment use Athena's `primary` workgroup.

See [`docs/workgroup-routing.md`](workgroup-routing.md) for the full routing logic and failure modes.
