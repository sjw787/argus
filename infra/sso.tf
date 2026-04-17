# IAM Identity Center (SSO) resources
#
# Prerequisites:
#   1. Register this account as SSO delegated administrator from the management
#      account (777653593792):
#
#      aws sso-admin register-delegated-administrator \
#        --account-id 052869941234 \
#        --service-principal sso.amazonaws.com \
#        --region us-east-1 \
#        --profile <management-account-profile>
#
#   2. Set manage_sso = true in your Terraform variables.
#
# Once active, Terraform manages:
#   - A permission set with Athena + Glue + S3 access
#   - An ArgusUsers group in the Identity Store
#   - Account assignment: ArgusUsers → this account with the permission set

data "aws_ssoadmin_instances" "main" {
  count = var.manage_sso ? 1 : 0
}

locals {
  sso_instance_arn      = var.manage_sso ? tolist(data.aws_ssoadmin_instances.main[0].arns)[0] : ""
  sso_identity_store_id = var.manage_sso ? tolist(data.aws_ssoadmin_instances.main[0].identity_store_ids)[0] : ""
}

# Permission set: full Athena + Glue + S3 results access
resource "aws_ssoadmin_permission_set" "athena_access" {
  count        = var.manage_sso ? 1 : 0
  name         = "ArgusAthenaAccess-${var.environment}"
  description  = "Athena, Glue, and S3 access for Argus for Athena"
  instance_arn = local.sso_instance_arn
  # Match AWS SSO credential lifetime
  session_duration = "PT8H"

  tags = {
    Name = "argus-athena-access-${var.environment}"
  }
}

resource "aws_ssoadmin_managed_policy_attachment" "athena_full" {
  count              = var.manage_sso ? 1 : 0
  instance_arn       = local.sso_instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.athena_access[0].arn
  managed_policy_arn = "arn:aws:iam::aws:policy/AmazonAthenaFullAccess"
}

resource "aws_ssoadmin_managed_policy_attachment" "glue_readonly" {
  count              = var.manage_sso ? 1 : 0
  instance_arn       = local.sso_instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.athena_access[0].arn
  managed_policy_arn = "arn:aws:iam::aws:policy/AWSGlueConsoleFullAccess"
}

# Group: ArgusUsers — add members via the Identity Center console or identitystore_user resources
resource "aws_identitystore_group" "argus_users" {
  count             = var.manage_sso ? 1 : 0
  identity_store_id = local.sso_identity_store_id
  display_name      = "ArgusUsers"
  description       = "Users with access to Argus for Athena (${var.environment})"
}

# Assign the ArgusUsers group to this account with the Athena permission set
resource "aws_ssoadmin_account_assignment" "argus_users" {
  count              = var.manage_sso ? 1 : 0
  instance_arn       = local.sso_instance_arn
  permission_set_arn = aws_ssoadmin_permission_set.athena_access[0].arn
  principal_id       = aws_identitystore_group.argus_users[0].group_id
  principal_type     = "GROUP"
  target_id          = data.aws_caller_identity.current.account_id
  target_type        = "AWS_ACCOUNT"
}
