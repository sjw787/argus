resource "aws_cognito_user_pool" "app" {
  count = var.auth_mode == "cognito" ? 1 : 0
  name  = "athena-beaver-${var.environment}"

  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]

  password_policy {
    minimum_length                   = 8
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = false
    require_uppercase                = true
    temporary_password_validity_days = 7
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  schema {
    name                     = "email"
    attribute_data_type      = "String"
    required                 = true
    mutable                  = true
    developer_only_attribute = false
    string_attribute_constraints {
      min_length = 5
      max_length = 254
    }
  }

  tags = {
    Name = "athena-beaver-${var.environment}"
  }
}

# SPA client — no client secret
resource "aws_cognito_user_pool_client" "app" {
  count        = var.auth_mode == "cognito" ? 1 : 0
  name         = "athena-beaver-spa-${var.environment}"
  user_pool_id = aws_cognito_user_pool.app[0].id

  generate_secret                      = false
  prevent_user_existence_errors        = "ENABLED"
  enable_token_revocation              = true
  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["code"]
  allowed_oauth_scopes                 = ["openid", "email", "profile"]

  callback_urls = ["https://${var.domain_name}/auth/callback"]
  logout_urls   = ["https://${var.domain_name}/"]

  supported_identity_providers = ["COGNITO"]

  access_token_validity  = 1
  id_token_validity      = 1
  refresh_token_validity = 30

  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }
}

resource "aws_cognito_user_pool_domain" "app" {
  count        = var.auth_mode == "cognito" ? 1 : 0
  domain       = "athena-beaver-${var.environment}"
  user_pool_id = aws_cognito_user_pool.app[0].id
}
