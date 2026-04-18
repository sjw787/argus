# Audit logging infrastructure — only created when enable_audit_logging = true.
#
# When enabled:
#   - A CloudWatch Log Group is created with 365-day retention (FedRAMP AU-11)
#   - The Lambda execution role gains write-only access to that group
#   - ARGUS_AUDIT_LOGGING and ARGUS_AUDIT_LOG_GROUP env vars are injected into Lambda
#     (see lambda.tf → local.lambda_env_compliance)
#
# The log group is append-only from Argus's perspective — no Argus code can
# read or delete audit events, satisfying FedRAMP non-repudiation (AU-9).

resource "aws_cloudwatch_log_group" "audit" {
  count             = var.enable_audit_logging ? 1 : 0
  name              = "/argus/${var.environment}/audit"
  retention_in_days = 365

  tags = {
    Purpose    = "FedRAMP audit log"
    Compliance = "FedRAMP-AU"
  }
}

resource "aws_iam_role_policy" "lambda_audit_logs" {
  count = var.enable_audit_logging ? 1 : 0
  name  = "argus-for-athena-audit-logs-${var.environment}"
  role  = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AuditLogWrite"
        Effect = "Allow"
        Action = [
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogStreams",
        ]
        # Write-only access to the audit log group — Lambda cannot read or delete logs.
        Resource = "${aws_cloudwatch_log_group.audit[0].arn}:*"
      }
    ]
  })
}
