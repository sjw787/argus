# Privacy & Data Disclosure

Argus for Athena is a pass-through interface to your AWS Athena environment. This document explains exactly what data the application does and does not handle.

---

## What We Do Not Collect

Argus for Athena **never** captures, stores, logs, or transmits any of the following:

- **Query results** — data returned by your Athena queries
- **Query text** — the SQL statements you write and execute
- **Table contents** — rows, columns, or cell values from your databases
- **Schema metadata** — database names, table names, or column definitions
- **S3 object data** — files stored in your Athena results bucket
- **Analytics or telemetry** — no usage tracking of any kind

---

## How Your Data Flows

```
Your Browser → Argus for Athena Backend → AWS Athena API → Back to Your Browser
```

Query results travel entirely in-memory through the application and are discarded immediately after being delivered to your browser. Nothing is written to disk or a database at any point in this flow.

**Exports** (CSV, JSON, Excel, Parquet) follow the same pattern: results are fetched from the Athena API, serialized into an in-memory buffer, and streamed directly to your browser as a file download. No export data is written to the server.

---

## What Is Stored

The only data Argus for Athena persists is what is strictly necessary to maintain your authenticated session:

| Data | Where Stored | Retention | Purpose |
|------|-------------|-----------|---------|
| SSO device auth session | Memory (local) / DynamoDB (Lambda) | 10 minutes | Complete AWS SSO login flow |
| Temporary AWS credentials | Memory (local) / DynamoDB (Lambda) | Until expiration (max 1 hour) | Authenticate API calls to Athena on your behalf |
| Cognito JWT token | Browser `sessionStorage` | Browser session | Authenticate requests to the backend |
| UI preferences (theme, etc.) | Browser `localStorage` | Until cleared | Remember your display settings |

Temporary AWS credentials stored in DynamoDB (Lambda deployment only) are encrypted at rest using a dedicated AWS KMS Customer Managed Key with annual key rotation. Entries are automatically deleted when they expire.

---

## Where Your Data Lives

All Athena data remains in your AWS account at all times:

- **Query history** — stored in AWS Athena (your account)
- **Query results** — stored in your S3 results bucket (your account)
- **Named queries & prepared statements** — stored in AWS Athena (your account)
- **Database and table definitions** — stored in AWS Glue Data Catalog (your account)

Argus for Athena reads from these services on your behalf using your credentials. It does not copy, cache, or replicate this data anywhere.

---

## External Connections

Argus for Athena makes network requests **only** to:

- **AWS service endpoints** — Athena, Glue, S3, STS, and (if using SSO) IAM Identity Center
- **AWS Cognito** — to validate JWTs when Cognito auth mode is enabled (fetches your pool's public signing keys)

No data is sent to any third-party service.

---

## No Telemetry

Argus for Athena contains no analytics scripts, usage tracking, error reporting services, or telemetry of any kind — in either the frontend or the backend.

---

## Administrator-Controlled Settings

If your organization self-hosts Argus for Athena, your administrator may configure:

- The authentication mode (Cognito, AWS SSO, or none)
- Which AWS workgroups and regions are accessible
- CORS and network access policies

Contact your administrator for details specific to your deployment.

---

## Open Source

Argus for Athena is open source. You can inspect every line of code to verify these claims:  
[https://github.com/sjw787/ArgusForAthena](https://github.com/sjw787/ArgusForAthena)

---

*Last updated: April 2026*
