# AWS SSO Authentication Mode

The default authentication mode for Argus for Athena. Users sign in via AWS SSO (IAM Identity Center).

## How It Works
1. User clicks "Sign in with AWS SSO"
2. Backend initiates device authorization flow with AWS SSO
3. User authenticates in browser via the SSO portal
4. Backend exchanges the device code for temporary AWS credentials
5. Credentials are stored in the session (DynamoDB in Lambda, memory in local dev)
6. All Athena/Glue API calls use these per-user credentials

## Configuration
- `ARGUS_AUTH_MODE=sso` (default)
- `ARGUS_SESSION_STORE=dynamodb` (required for Lambda, optional for local dev)
- `ARGUS_REGION=us-east-1` (or your AWS region)

## Local Development
No special setup needed — uses the existing SSO flow with in-memory session store.

After completing the SSO flow, credentials are written to `~/.aws/credentials` as a named
profile (e.g. `argus-for-athena`). Subsequent requests use that profile via boto3's standard
credential chain.

## Lambda Deployment
Set `ARGUS_SESSION_STORE=dynamodb` and ensure the Lambda IAM role has DynamoDB permissions for
the sessions table. The SSO credentials are returned to the browser and sent with each request,
so the Lambda doesn't need to write to `~/.aws/credentials`.

### Lambda SSO Flow
1. `POST /auth/sso/start` → returns `session_id`, `user_code`, `verification_uri`
2. User visits the verification URL and approves the device
3. Frontend polls `GET /auth/sso/poll/{session_id}` until `status=success`
4. Frontend calls `GET /auth/sso/{session_id}/accounts` → lists accounts
5. Frontend calls `GET /auth/sso/{session_id}/accounts/{account_id}/roles` → lists roles
6. Frontend POSTs `POST /auth/sso/select-role`:
   - Backend fetches role credentials from AWS SSO
   - Credentials are stored in DynamoDB session store under key `creds:{session_id}`
   - Response includes `credential_id` (the session_id)
7. Frontend stores `credential_id` in `localStorage` (via Zustand persist)
8. **Every subsequent request** includes `X-Credential-Id: {credential_id}` header
9. Backend retrieves credentials from DynamoDB and creates a per-request boto3 session

### DynamoDB Sessions Table
The table `argus-sessions` (configurable via `ARGUS_SESSION_TABLE`) stores:
- Device-auth sessions (`session_id`) — TTL: 10 minutes
- SSO access tokens (`token:{session_id}`) — TTL: 1 hour
- Role credentials (`creds:{session_id}`) — TTL: 1 hour

Ensure DynamoDB TTL is enabled on the `expires_at` attribute.

## Sign Out

Clicking **Sign Out** in the Settings panel calls `POST /api/auth/signout`.

- The backend deletes the session entry from DynamoDB (Lambda) or clears it from the in-memory store (local dev).
- The frontend clears its stored `credential_id` from Zustand (and `localStorage`).
- The UI returns to the login screen.

The sign-out endpoint invalidates server-side credentials immediately — any subsequent API call with the old `X-Credential-Id` header will be rejected.
