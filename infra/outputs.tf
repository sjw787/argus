output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID (for cache invalidations)"
  value       = aws_cloudfront_distribution.app.id
}

output "cloudfront_url" {
  description = "CloudFront distribution URL"
  value       = "https://${aws_cloudfront_distribution.app.domain_name}"
}

output "cloudfront_domain" {
  description = "CloudFront domain name (for DNS validation)"
  value       = aws_cloudfront_distribution.app.domain_name
}

output "app_url" {
  description = "Application URL via custom domain"
  value       = "https://${var.domain_name}"
}

output "api_gateway_url" {
  description = "API Gateway invoke URL"
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "s3_bucket_name" {
  description = "S3 bucket name for frontend static assets"
  value       = aws_s3_bucket.frontend.id
}

output "ecr_repository_url" {
  description = "ECR repository URL for Docker image pushes"
  value       = aws_ecr_repository.app.repository_url
}

output "dynamodb_table_name" {
  description = "DynamoDB table name for session state"
  value       = aws_dynamodb_table.sessions.name
}

output "lambda_function_name" {
  description = "Lambda function name"
  value       = aws_lambda_function.app.function_name
}

output "cognito_user_pool_id" {
  description = "Cognito user pool ID (only set when auth_mode = cognito)"
  value       = length(aws_cognito_user_pool.app) > 0 ? aws_cognito_user_pool.app[0].id : null
}

output "cognito_client_id" {
  description = "Cognito app client ID (only set when auth_mode = cognito)"
  value       = length(aws_cognito_user_pool_client.app) > 0 ? aws_cognito_user_pool_client.app[0].id : null
}

output "cognito_domain" {
  description = "Cognito hosted UI domain (only set when auth_mode = cognito)"
  value       = length(aws_cognito_user_pool_domain.app) > 0 ? "${aws_cognito_user_pool_domain.app[0].domain}.auth.${var.aws_region}.amazoncognito.com" : null
}
