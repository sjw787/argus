# FedRAMP / GovRAMP Deployment Guide

This guide covers deploying Argus for Athena in environments that require FedRAMP or GovRAMP compliance. All compliance features are **opt-in** — a standard deployment is completely unchanged when these variables are not set.

---

## Compliance Features Overview

| Feature | Terraform variable | Env var (auto-set) | Default |
|---|---|---|---|
| Audit logging | `enable_audit_logging` | `ARGUS_AUDIT_LOGGING` | `false` |
| GovCloud partition | `govcloud` | `ARGUS_AWS_PARTITION` | `false` |
| FIPS endpoints | `use_fips_endpoints` | `ARGUS_USE_FIPS_ENDPOINTS` | `false` |
| FIPS container | `fips_container` | (build arg) | `false` |

---

## 1. Audit Logging

**Satisfies**: NIST 800-53 AU-2, AU-3, AU-9, AU-11

### What is logged

Every HTTP request produces one structured JSON record in CloudWatch:

```json
{
  "timestamp": "2024-01-15T14:32:01Z",
  "request_id": "req-abc123",
  "user_identity": "alice@example.com",
  "action_type": "QUERY_EXECUTE",
  "http_method": "POST",
  "path": "/api/v1/queries/execute",
  "status_code": 202,
  "duration_ms": 87.4,
  "database": "prod_db",
  "workgroup": "prod_wg",
  "execution_id": "qe-12345"
}
```

**Action types**: `QUERY_EXECUTE`, `QUERY_CANCEL`, `EXPORT`, `LOGIN`, `LOGOUT`, `CONFIG_CHANGE`, `CATALOG_READ`, `EXPLAIN`, `OTHER`

### What is NEVER logged

- SQL query text
- Query result data, column values, or row data
- AWS credentials or session tokens

This is enforced in code and verified by tests. See [PRIVACY.md](../PRIVACY.md).

### Non-repudiation

The CloudWatch log group is append-only. No Argus code has `logs:GetLogEvents` or `logs:DeleteLogGroup` permissions. Audit records cannot be altered or deleted by the application (AU-9).

### Enabling

```hcl
# terraform.tfvars
enable_audit_logging = true
```

Terraform will:
1. Create `/argus/{environment}/audit` CloudWatch Log Group with 365-day retention
2. Grant the Lambda role write-only access to that group
3. Set `ARGUS_AUDIT_LOGGING=true` and `ARGUS_AUDIT_LOG_GROUP=...` as Lambda env vars

The middleware fires automatically — no code changes required.

### Viewing audit logs

```bash
# AWS CLI — stream audit events in real time
aws logs tail "/argus/prod/audit" --follow --region us-east-1

# Filter by action type
aws logs filter-log-events \
  --log-group-name "/argus/prod/audit" \
  --filter-pattern '{ $.action_type = "QUERY_EXECUTE" }' \
  --region us-east-1
```

---

## 2. GovCloud Deployment

**Satisfies**: FedRAMP data residency requirements

### Enabling

```hcl
# terraform.tfvars
govcloud   = true
aws_region = "us-gov-west-1"   # or us-gov-east-1
```

When `govcloud = true`:
- All IAM policy ARNs use `arn:aws-us-gov:` partition
- Lambda environment receives `ARGUS_AWS_PARTITION=aws-us-gov`
- Terraform provider region targets GovCloud

### GovCloud prerequisites

1. Your AWS account must be a GovCloud account (separate from commercial)
2. Update your S3 backend configuration for the GovCloud region:
   ```hcl
   # backend.tf
   backend "s3" {
     bucket = "your-govcloud-tfstate-bucket"
     key    = "argus-for-athena/terraform.tfstate"
     region = "us-gov-west-1"
   }
   ```
3. Pre-create the S3 state bucket in the GovCloud account
4. Cognito is available in GovCloud (`us-gov-west-1`); SSO/Identity Center requires GovCloud-compatible configuration

### IAM Identity Center in GovCloud

AWS IAM Identity Center is available in GovCloud but requires separate setup. If using Cognito auth (`auth_mode = "cognito"`), the setup is the same as commercial.

---

## 3. FIPS-Validated Endpoints

**Satisfies**: FIPS 140-2/140-3 cryptographic requirements

### Enabling

```hcl
# terraform.tfvars
use_fips_endpoints = true
```

When enabled, all boto3 service clients use FIPS-validated endpoints:

| Service | FIPS endpoint |
|---|---|
| Athena | `athena-fips.{region}.amazonaws.com` |
| Glue | `glue-fips.{region}.amazonaws.com` |
| S3 | `s3-fips.{region}.amazonaws.com` |
| STS | `sts-fips.{region}.amazonaws.com` |

### FIPS endpoint availability

FIPS endpoints are available in:
- Commercial: `us-east-1`, `us-east-2`, `us-west-1`, `us-west-2`
- GovCloud: `us-gov-west-1`, `us-gov-east-1`

Verify endpoint availability for your region at [AWS FIPS Endpoints](https://aws.amazon.com/compliance/fips/).

### Verifying FIPS connectivity

```bash
# From the Lambda function or a test instance
curl -v https://athena-fips.us-east-1.amazonaws.com/ 2>&1 | grep "TLS"
```

---

## 4. FIPS-Capable Container

**Satisfies**: FIPS 140-2 validated cryptographic modules at the container level

### Enabling

```hcl
# terraform.tfvars
fips_container = true
```

When `fips_container = true`, the Docker build passes `--build-arg FIPS_CONTAINER=true`, which enables FIPS-mode OpenSSL in the container image.

> **Note**: Full FIPS enforcement requires the container runtime host to also be FIPS-enabled. In GovCloud, Lambda execution environments are FIPS-capable when FIPS endpoints are configured.

### Combining FIPS options

For a fully FIPS-compliant deployment:

```hcl
# terraform.tfvars
govcloud           = true
aws_region         = "us-gov-west-1"
use_fips_endpoints = true
fips_container     = true
enable_audit_logging = true
```

---

## 5. Full Government Deployment Checklist

### Pre-deployment

- [ ] GovCloud AWS account provisioned
- [ ] S3 bucket for Terraform state created in GovCloud
- [ ] ECR repository created in GovCloud region
- [ ] Domain/certificate configured (ACM in `us-east-1` for CloudFront, or GovCloud ACM)
- [ ] SSO/Cognito identity provider configured

### Terraform variables (`terraform.tfvars`)

```hcl
# Identity
domain_name  = "argus.agency.gov"
aws_region   = "us-gov-west-1"
environment  = "prod"

# Auth
auth_mode     = "cognito"   # or "sso" if using GovCloud IAM Identity Center

# Compliance
govcloud             = true
use_fips_endpoints   = true
fips_container       = true
enable_audit_logging = true

# Athena
output_location = "s3://agency-athena-results/argus/"
```

### Post-deployment verification

1. **Verify FIPS endpoints**: Check Lambda logs for successful connections to FIPS endpoints
2. **Verify audit logging**: Run a test query and confirm the record appears in `/argus/prod/audit`
3. **Verify TLS version**: Ensure all connections use TLS 1.2+
4. **Run penetration test**: FedRAMP requires annual penetration testing

---

## 6. Incident Response

### Suspicious query activity

1. Search audit logs for the user identity and time window:
   ```bash
   aws logs filter-log-events \
     --log-group-name "/argus/prod/audit" \
     --filter-pattern '{ $.user_identity = "suspect@example.com" }' \
     --start-time $(date -d '24 hours ago' +%s)000
   ```
2. Revoke the user's SSO session or Cognito tokens
3. Rotate the affected workgroup's output S3 bucket permissions if needed

### Unauthorized access attempt

1. Check audit logs for 401/403 responses:
   ```bash
   aws logs filter-log-events \
     --log-group-name "/argus/prod/audit" \
     --filter-pattern '{ $.status_code = 401 || $.status_code = 403 }'
   ```
2. Review CloudFront access logs for source IP patterns
3. Update WAF rules if a source IP is identified

### Data exfiltration concern

Argus does not store query results. If a user exported data:
1. Search for `EXPORT` action type in audit logs with the user's identity
2. Check S3 access logs on the Athena output bucket for `GetObject` calls

---

## 7. Audit Log Schema Reference

| Field | Type | Always present | Description |
|---|---|---|---|
| `timestamp` | ISO 8601 string | Yes | UTC time of the event |
| `request_id` | UUID string | Yes | Unique request identifier |
| `user_identity` | string | Yes | Username, email, or credential ID |
| `action_type` | string | Yes | One of the action type constants |
| `http_method` | string | Yes | HTTP verb (GET, POST, etc.) |
| `path` | string | Yes | URL path (no query string) |
| `status_code` | integer | Yes | HTTP response status code |
| `duration_ms` | float | Yes | Request processing time in milliseconds |
| `database` | string | No | Database name from query parameters |
| `workgroup` | string | No | Workgroup name from query parameters |
| `execution_id` | string | No | Athena execution ID if returned |

Fields absent from a record were not applicable to that request.
