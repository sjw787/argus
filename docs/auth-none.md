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

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["athena:*", "glue:*", "s3:GetObject", "s3:PutObject", "s3:ListBucket"],
      "Resource": "*"
    }
  ]
}
```
