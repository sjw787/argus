# Workgroup Routing & Output Locations (for Agents)

This document explains how Argus for Athena decides which **workgroup** and
**S3 output location** to use for each query. This is the original design
goal of the app: different clients' databases must always run in their own
dedicated workgroup so IAM/billing/result isolation is enforced.

Agents modifying query-execution code, auth flows, or configuration loading
should read this before making changes.

---

## The rule in one sentence

> For every `StartQueryExecution`, Argus resolves `(database → workgroup → S3
> output location)` using configuration. A missing step breaks the whole
> chain.

---

## How workgroup assignments happen today

Database-to-workgroup mappings are assigned **manually through the UI** and
persisted in the `workgroups.assignments` map in `argus.yaml` / the config
store. Assignments are always explicit — there is no automatic pattern-based
inference from database names.

Summary:
- User picks a database in the UI → assigns a workgroup to it
- Assignment is stored as `workgroups.assignments[database_name] = workgroup_name`
- Any database without an assignment falls through to the **primary**
  workgroup (see below)

---

## Configuration shape

The relevant shape (`src/argus/models/schemas.py`):

```yaml
workgroups:
  assignments:
    # database_name → workgroup_name (set via the UI)
    analytics_123456_prod: wg_123456_prod
    analytics_123456_dev:  wg_123456_dev
  output_locations:
    # workgroup_name → s3 URI
    wg_123456_prod: s3://argus-results/123456/prod/
    wg_123456_dev:  s3://argus-results/123456/dev/

defaults:
  output_location: s3://argus-results/default/   # app-wide fallback
```

Key env vars override config:
- `ARGUS_OUTPUT_LOCATION` → `config.defaults.output_location`
- `ARGUS_REGION`, `ARGUS_PROFILE`, `ARGUS_AUTH_MODE`, etc.

---

## The resolution chain

Two steps, both in `src/argus/services/athena_service.py`:

### 1. Database → Workgroup

```python
resolved_wg = workgroup or self._resolve_workgroup(database, schema_name)
```

`_resolve_workgroup` → `workgroups.assignments.get(database)`.

- **Explicit assignment only.** A DB without an `assignments` entry
  returns `None`. This is deliberate: Argus will not silently route a
  client's queries to a default workgroup.
- If `None`, the query runs against Athena's `primary` workgroup (Athena's
  default when `WorkGroup` is omitted).

### 2. Workgroup → Output location

```python
resolved_s3 = output_location or self._resolve_output(resolved_wg)
```

`_resolve_output(wg)`:
1. If `wg` is in `workgroups.output_locations` → return that.
2. Else return `config.defaults.output_location` (may be `None`).

If the final `resolved_s3` is `None` AND the workgroup has no
`ResultConfiguration` enforced on the AWS side, Athena returns:

```
InvalidRequestException: No output location provided.
```

---

## The `primary` workgroup (metadata queries)

`information_schema.*`, `SHOW DATABASES`, and most catalog-listing queries
aren't tied to a specific client workgroup. They run against Athena's
`primary` workgroup.

**Argus provisions `primary`'s output location via Terraform.** The
`infra/athena.tf` module:
- Creates an S3 bucket `argus-athena-metadata-<env>` for metadata query
  results
- Sets `primary`'s `ResultConfiguration.OutputLocation` to that bucket
- Exports the bucket URI as the `ARGUS_OUTPUT_LOCATION` Lambda env var,
  which populates `config.defaults.output_location`

This is infra-owned, not runtime-owned. The backend never mutates
workgroup configuration at request time.

Client-specific queries still get their own bucket via
`workgroups.output_locations[wg]` — those buckets are created outside this
repo (per-client infra).

---

## Invariants agents must preserve

1. **Never silently infer a client workgroup from a database name.**
   Assignments are explicit, set via UI. Silent fallbacks violate tenant
   isolation.
2. **Never write a client's query results to another client's bucket.**
   `_resolve_output` must look up `output_locations[wg]` *before* the
   default. The default is only for non-client (primary) queries.
3. **Never hardcode an S3 bucket in code.** Always route through
   `config.defaults.output_location` or `workgroups.output_locations`.
4. **Never strip `WorkGroup` from `StartQueryExecution` params.** If
   `resolved_wg` is set, it MUST be sent — AWS uses it for IAM and cost
   tracking per client.
5. **Configuration precedence:** explicit arg > per-workgroup map > app
   default. Do not change this order.
6. **Do not mutate workgroup configuration from request handlers.**
   Workgroup lifecycle is infra concern (Terraform). The `workgroups`
   router exposes CRUD via boto3 for admin UX but should not be triggered
   implicitly on query paths.

---

## Where this is wired up in the repo

| Concern | File |
|---|---|
| Pydantic shape of config | `src/argus/models/schemas.py` |
| Loading YAML + env vars | `src/argus/core/config.py` |
| Assignment lookup | `src/argus/services/athena_service.py::_resolve_workgroup` |
| Per-query resolution | `src/argus/services/athena_service.py::start_query_execution` |
| Workgroup CRUD (admin) | `src/argus/services/workgroup_service.py` |
| Env var surface | Lambda env via `infra/lambda.tf` |
| Metadata bucket + primary WG config | `infra/athena.tf` |
| Example config | `argus.yaml.example` |

---

## Common failure modes

| Error | Meaning | Fix |
|---|---|---|
| `No output location provided` | Final `resolved_s3` is None and WG has no configured location | Deploy `infra/athena.tf` (sets `ARGUS_OUTPUT_LOCATION` + primary WG) |
| Query runs but result appears under wrong client's prefix | `output_locations[wg]` missing → fell back to default | Add the mapping |
| Query fails with `InvalidRequestException: WorkGroup <x> not found` | Assignment points to a WG that doesn't exist in AWS | Create the WG or fix the assignment |
| Metadata query works locally (dev creds) but fails in Lambda | Default not set in Lambda env | Redeploy with updated `ARGUS_OUTPUT_LOCATION` |

---

## Tests to update when changing this logic

- `tests/test_athena_service.py` — covers `_resolve_workgroup`,
  `_resolve_output`, and `start_query_execution` params.
- `tests/test_api_queries.py` — covers the workgroup fallback in the query router.

Always add a test case for any new fallback path. Silent fallbacks are the
exact bug class this module exists to prevent.
