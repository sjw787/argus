# No-Auth / IAM-Only Mode

Use this mode for internal/VPN-only deployments where authentication is handled at the network layer.

## Configuration

Set `ARGUS_AUTH_MODE=none` in your Lambda environment variables (or `argus.yaml` for local dev).

The Lambda function's IAM execution role must have permissions for Athena, Glue, and S3.

## Security Considerations

- This mode provides NO application-level authentication
- Only use behind a VPN, internal load balancer, or other network-level access control
- All users share the same Lambda IAM role permissions

## Required IAM Permissions

Scope permissions to the specific resources your deployment uses rather than `*`. The following is a least-privilege template — replace the placeholder ARNs with your actual values:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AthenaQueries",
      "Effect": "Allow",
      "Action": [
        "athena:StartQueryExecution",
        "athena:StopQueryExecution",
        "athena:GetQueryExecution",
        "athena:GetQueryResults",
        "athena:ListWorkGroups",
        "athena:GetWorkGroup",
        "athena:BatchGetQueryExecution",
        "athena:ListQueryExecutions"
      ],
      "Resource": [
        "arn:aws:athena:<region>:<account-id>:workgroup/*"
      ]
    },
    {
      "Sid": "GlueCatalogRead",
      "Effect": "Allow",
      "Action": [
        "glue:GetDatabase",
        "glue:GetDatabases",
        "glue:GetTable",
        "glue:GetTables",
        "glue:GetPartition",
        "glue:GetPartitions"
      ],
      "Resource": [
        "arn:aws:glue:<region>:<account-id>:catalog",
        "arn:aws:glue:<region>:<account-id>:database/*",
        "arn:aws:glue:<region>:<account-id>:table/*/*"
      ]
    },
    {
      "Sid": "AthenaResultsBucket",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
        "s3:GetBucketLocation"
      ],
      "Resource": [
        "arn:aws:s3:::your-athena-results-bucket",
        "arn:aws:s3:::your-athena-results-bucket/*"
      ]
    }
  ]
}
```

If you query multiple workgroups or write results to multiple buckets, add each ARN to the appropriate `Resource` list.

## Sign Out

The Settings page shows a **Sign Out** button even in no-auth mode. Clicking it only clears frontend state (Zustand store + `localStorage`) — there are no server-side credentials to revoke and no session to invalidate. The page returns to the login/landing screen.
