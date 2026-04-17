# Athena metadata results bucket + primary workgroup configuration.
#
# Information-schema and other metadata queries run against the built-in
# "primary" workgroup. We provision a dedicated S3 bucket for those results
# and configure primary's OutputLocation to point at it. The same bucket URI
# is surfaced as ARGUS_OUTPUT_LOCATION on the Lambda so it also serves as the
# app-wide fallback for any query whose workgroup has no explicit mapping.
#
# See docs/workgroup-routing.md for the full resolution chain.

locals {
  metadata_bucket_name = "argus-athena-metadata-${var.environment}-${data.aws_caller_identity.current.account_id}"
  metadata_bucket_uri  = "s3://${local.metadata_bucket_name}/results/"
  # Prefer an explicit override from var.output_location if set, else use the provisioned bucket.
  effective_output_location = var.output_location != "" ? var.output_location : local.metadata_bucket_uri
}

resource "aws_s3_bucket" "athena_metadata" {
  bucket        = local.metadata_bucket_name
  force_destroy = false

  tags = {
    Name    = local.metadata_bucket_name
    Purpose = "athena-primary-workgroup-results"
  }
}

resource "aws_s3_bucket_public_access_block" "athena_metadata" {
  bucket                  = aws_s3_bucket.athena_metadata.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "athena_metadata" {
  bucket = aws_s3_bucket.athena_metadata.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "athena_metadata" {
  bucket = aws_s3_bucket.athena_metadata.id

  rule {
    id     = "expire-results"
    status = "Enabled"

    filter {}

    expiration {
      days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

# Configure the built-in primary workgroup's OutputLocation so metadata
# queries (information_schema, SHOW DATABASES, catalog listings) work
# without the caller specifying a ResultConfiguration.
#
# We import the primary workgroup (it always exists) and manage only the
# ResultConfiguration. State is NOT enforced (so users can still override
# per-query).
resource "aws_athena_workgroup" "primary" {
  name          = "primary"
  force_destroy = false

  configuration {
    enforce_workgroup_configuration    = false
    publish_cloudwatch_metrics_enabled = true

    result_configuration {
      output_location = local.metadata_bucket_uri
    }
  }

  tags = {
    ManagedBy = "argus-for-athena"
    Purpose   = "metadata-queries"
  }

  lifecycle {
    # Don't destroy the primary workgroup on `terraform destroy`.
    prevent_destroy = true
  }
}
