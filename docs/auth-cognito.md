# Cognito Authentication Mode

Use this mode for production deployments that require user authentication and access control before
users can query Athena.

## How It Works

1. **User navigates to the app** — the React frontend detects no valid session and redirects to the
   Cognito hosted UI login page.
2. **User authenticates** — Cognito validates credentials (or federated identity provider) and
   redirects back to `https://<domain>/auth/callback` with an authorization code.
3. **Frontend exchanges code for tokens** — the SPA calls Cognito's token endpoint and receives
   an ID token, access token, and refresh token.
4. **API calls include the Bearer token** — every request to `/api/*` includes the Cognito ID token
   as `Authorization: Bearer <id_token>`.
5. **Lambda validates the JWT** — the backend verifies the token's signature against Cognito's
   JWKS endpoint (`https://cognito-idp.<region>.amazonaws.com/<user_pool_id>/.well-known/jwks.json`),
   checks the `aud` (client ID) and `exp` claims.
6. **Athena queries run under the Lambda IAM role** — once the JWT is validated, the Lambda uses
   its IAM execution role (not the user's identity) to call Athena and Glue.

## Configuration

Set `auth_mode = "cognito"` in your Terraform variables file (or via `-var`):

```hcl
# terraform.tfvars
auth_mode        = "cognito"
domain_name      = "abvr.samwylock.com"
hosted_zone_id   = "ZXXXXXXXXXXXXX"
output_location  = "s3://my-athena-results/prefix/"
```

The Lambda environment variables `ARGUS_AUTH_MODE`, `ARGUS_COGNITO_USER_POOL_ID`, and
`ARGUS_COGNITO_CLIENT_ID` are set automatically by Terraform — no manual configuration needed.

## Terraform Setup

```bash
terraform init
terraform apply -var="auth_mode=cognito"
```

After `apply`, retrieve the Cognito outputs:

```bash
terraform output cognito_user_pool_id
terraform output cognito_client_id
terraform output cognito_domain
```

## Adding Users

### AWS Console
1. Open **Cognito → User pools → argus-for-athena-\<env\>**
2. Click **Create user**
3. Enter the user's email address and set a temporary password
4. The user will be prompted to change their password on first login

### AWS CLI

```bash
# Create a user
aws cognito-idp admin-create-user \
  --user-pool-id <user_pool_id> \
  --username user@example.com \
  --user-attributes Name=email,Value=user@example.com Name=email_verified,Value=true \
  --temporary-password "TempPass1!" \
  --message-action SUPPRESS

# Set a permanent password
aws cognito-idp admin-set-user-password \
  --user-pool-id <user_pool_id> \
  --username user@example.com \
  --password "PermanentPass1!" \
  --permanent
```

## Disabling Cognito

To switch back to SSO or no auth, change `auth_mode` and re-apply. Terraform will destroy the
Cognito resources. Make sure to update your frontend configuration accordingly.

```bash
terraform apply -var="auth_mode=sso"
```
