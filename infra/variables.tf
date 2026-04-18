variable "domain_name" {
  description = "The custom domain for the application (e.g. argus.samwylock.com)"
  type        = string
  default     = "argus.samwylock.com"
}

variable "hosted_zone_id" {
  description = "Existing Route 53 hosted zone ID. Required when create_hosted_zone = false (default)."
  type        = string
  default     = ""
}

variable "create_hosted_zone" {
  description = <<-EOT
    When false (default), use an existing hosted zone specified by hosted_zone_id.
    When true, create a new hosted zone for domain_name in this account and output
    the NS records to add to your parent zone (e.g. in a legacy account).
  EOT
  type        = bool
  default     = false
}

variable "aws_region" {
  description = "AWS region for Lambda and other resources"
  type        = string
  default     = "us-east-1"
}

variable "auth_mode" {
  description = "Authentication mode: cognito, sso, or none"
  type        = string
  default     = "sso"
  validation {
    condition     = contains(["cognito", "sso", "none"], var.auth_mode)
    error_message = "auth_mode must be one of: cognito, sso, none"
  }
}

variable "environment" {
  description = "Deployment environment (dev or prod)"
  type        = string
  default     = "prod"
}

variable "image_uri" {
  description = "ECR image URI for the Lambda function (set after first ECR push)"
  type        = string
  default     = ""
}

variable "lambda_memory_mb" {
  description = "Lambda memory in MB"
  type        = number
  default     = 1024
}

variable "lambda_timeout_seconds" {
  description = "Lambda timeout in seconds (max 29 for API Gateway compatibility)"
  type        = number
  default     = 29
}

variable "output_location" {
  description = "S3 path for Athena query results (e.g. s3://my-bucket/athena-results/)"
  type        = string
  default     = ""
}

variable "sso_start_url" {
  description = "AWS IAM Identity Center SSO start URL (e.g. https://samwylock.awsapps.com/start)"
  type        = string
  default     = ""
}

variable "manage_sso" {
  description = "When true, Terraform manages IAM Identity Center permission sets and account assignments. Requires 052869941234 to be registered as SSO delegated administrator."
  type        = bool
  default     = false
}

# ── Government / compliance options (all disabled by default) ──────────────────

variable "enable_audit_logging" {
  description = <<-EOT
    When true, create a CloudWatch Log Group (/argus/{environment}/audit) with
    365-day retention and grant the Lambda role permission to write audit events.
    Required for FedRAMP/GovRAMP and NIST 800-53 AU-2/AU-3 compliance.
    Has no effect on standard (non-government) deployments when left false.
  EOT
  type        = bool
  default     = false
}

variable "govcloud" {
  description = <<-EOT
    When true, use the aws-us-gov ARN partition in all IAM and resource ARN
    constructions. Set aws_region to us-gov-west-1 or us-gov-east-1 when
    deploying into AWS GovCloud (US).
  EOT
  type        = bool
  default     = false
}

variable "use_fips_endpoints" {
  description = <<-EOT
    When true, configure the backend Lambda to call FIPS-validated AWS service
    endpoints (Athena, Glue, S3, STS). Required for FedRAMP High and GovCloud
    deployments. Endpoints must be available in the target region.
  EOT
  type        = bool
  default     = false
}

variable "fips_container" {
  description = <<-EOT
    When true, pass FIPS_CONTAINER=true to the Docker build so that the image
    enables FIPS-mode OpenSSL. Works in combination with use_fips_endpoints.
    Requires the container runtime host to be FIPS-enabled (GovCloud EC2/Fargate).
  EOT
  type        = bool
  default     = false
}
