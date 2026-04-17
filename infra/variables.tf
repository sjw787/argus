variable "domain_name" {
  description = "The custom domain for the application (e.g. abvr.samwylock.com)"
  type        = string
  default     = "abvr.samwylock.com"
}

variable "hosted_zone_id" {
  description = "Route 53 hosted zone ID for the domain"
  type        = string
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
}
