locals {
  # Use a placeholder image when image_uri is not yet set (before first ECR push)
  effective_image_uri = var.image_uri != "" ? var.image_uri : "${aws_ecr_repository.app.repository_url}:latest"

  lambda_env_base = {
    ARGUS_REGION          = var.aws_region
    ARGUS_AUTH_MODE       = var.auth_mode
    ARGUS_SESSION_STORE   = "dynamodb"
    ARGUS_SESSION_TABLE   = aws_dynamodb_table.sessions.name
    LAMBDA_RUNTIME        = "1"
    ARGUS_OUTPUT_LOCATION = var.output_location
    ARGUS_CORS_ORIGINS    = "https://${var.domain_name}"
    ARGUS_SSO_START_URL   = var.sso_start_url
  }

  lambda_env_cognito = var.auth_mode == "cognito" ? {
    ARGUS_COGNITO_USER_POOL_ID = length(aws_cognito_user_pool.app) > 0 ? aws_cognito_user_pool.app[0].id : ""
    ARGUS_COGNITO_CLIENT_ID    = length(aws_cognito_user_pool_client.app) > 0 ? aws_cognito_user_pool_client.app[0].id : ""
  } : {}

  lambda_env = merge(local.lambda_env_base, local.lambda_env_cognito)
}

# IAM role for Lambda
resource "aws_iam_role" "lambda" {
  name = "argus-for-athena-lambda-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "lambda.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_athena" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonAthenaFullAccess"
}

resource "aws_iam_role_policy" "lambda_custom" {
  name = "argus-for-athena-lambda-custom-${var.environment}"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "GlueReadAccess"
        Effect = "Allow"
        Action = [
          "glue:GetDatabase",
          "glue:GetDatabases",
          "glue:GetTable",
          "glue:GetTables",
          "glue:GetPartition",
          "glue:GetPartitions",
          "glue:BatchGetPartition",
        ]
        Resource = "*"
      },
      {
        Sid    = "AthenaOutputS3"
        Effect = "Allow"
        Action = [
          "s3:GetBucketLocation",
          "s3:GetObject",
          "s3:ListBucket",
          "s3:ListBucketMultipartUploads",
          "s3:ListMultipartUploadParts",
          "s3:AbortMultipartUpload",
          "s3:PutObject",
          "s3:DeleteObject",
        ]
        Resource = [
          "arn:aws:s3:::${replace(replace(var.output_location, "s3://", ""), "/", "")}",
          "arn:aws:s3:::${replace(replace(var.output_location, "s3://", ""), "/", "")}/*",
          # Broad wildcard for the bucket prefix — narrow if output_location contains a sub-path
          "arn:aws:s3:::${split("/", replace(var.output_location, "s3://", ""))[0]}",
          "arn:aws:s3:::${split("/", replace(var.output_location, "s3://", ""))[0]}/*",
        ]
      },
      {
        Sid    = "DynamoDBSessions"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
        ]
        Resource = aws_dynamodb_table.sessions.arn
      },
      {
        Sid    = "ECRPull"
        Effect = "Allow"
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:GetAuthorizationToken",
        ]
        Resource = "*"
      },
    ]
  })
}

resource "aws_lambda_function" "app" {
  function_name = "argus-for-athena-${var.environment}"
  role          = aws_iam_role.lambda.arn
  package_type  = "Image"
  image_uri     = local.effective_image_uri
  memory_size   = var.lambda_memory_mb
  timeout       = var.lambda_timeout_seconds

  environment {
    variables = local.lambda_env
  }

  lifecycle {
    ignore_changes = [image_uri]
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic,
    aws_iam_role_policy_attachment.lambda_athena,
    aws_iam_role_policy.lambda_custom,
    aws_ecr_repository_policy.app,
  ]
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.app.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.app.execution_arn}/*/*"
}
