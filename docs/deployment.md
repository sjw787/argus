# Argus for Athena Deployment Guide

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| AWS CLI | ≥ 2.x | https://docs.aws.amazon.com/cli/latest/userguide/install-cliv2.html |
| Terraform | ≥ 1.7 | https://developer.hashicorp.com/terraform/install |
| Docker | ≥ 24.x | https://docs.docker.com/get-docker/ |
| Node.js | ≥ 20.x | https://nodejs.org/ |
| Git | any | https://git-scm.com/ |

AWS credentials must be configured (`aws configure` or IAM role). The deploying principal needs permissions for: ECR, Lambda, API Gateway, S3, CloudFront, Route53, ACM, DynamoDB, Cognito, and IAM.

---

## First-Time Setup

### 1. Bootstrap Terraform state (S3 backend)

```bash
# Create an S3 bucket and DynamoDB table for Terraform state (one-time)
aws s3 mb s3://your-terraform-state-bucket --region us-east-1
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region us-east-1
```

Update `infra/main.tf` backend block with your bucket name if it uses remote state.

### 2. Domain setup

Ensure your domain's hosted zone exists in Route53:
```bash
aws route53 list-hosted-zones --query 'HostedZones[*].[Name,Id]' --output table
```
Note the hosted zone ID (format: `Z1XXXXXXXXXXXXX`).

### 3. Athena output location

Your Athena query results bucket must exist:
```bash
aws s3 mb s3://your-athena-results-bucket --region us-east-1
```
The `output_location` value is in the format `s3://your-athena-results-bucket/`.

---

## Manual Deployment

### Step 1 — Build frontend + Docker image + push to ECR

```bash
# From project root
./deploy/build.sh [environment] [aws-region] [aws-account-id]

# Example
./deploy/build.sh prod us-east-1 123456789012
```

This will:
1. Build the React frontend (`npm run build -- --outDir dist`) → `frontend/dist/`
2. Authenticate Docker with ECR
3. Build the Lambda Docker image (`deploy/Dockerfile.backend`)
4. Push to ECR as `argus-for-athena-{environment}:latest` and `argus-for-athena-{environment}:{git-sha}`
5. Print the full image URI — **copy this for Step 2**

### Step 2 — Apply Terraform + sync frontend + invalidate CloudFront

```bash
./deploy/deploy.sh [environment] [hosted_zone_id] [output_location] [image_uri]

# Example
./deploy/deploy.sh prod Z1ABCDEFGHIJKL s3://my-athena-results/ 123456789012.dkr.ecr.us-east-1.amazonaws.com/argus-for-athena-prod:abc1234
```

This will:
1. Run `terraform init` + `terraform apply` in `infra/`
2. Sync `frontend/dist/` to the S3 bucket (immutable cache for assets, no-cache for `index.html`)
3. Create a CloudFront invalidation for `/*`
4. Print the application URL

---

## GitHub Actions (CI/CD)

### Required GitHub Secrets

Configure these in **Settings → Secrets and variables → Actions**:

| Secret | Description | Example |
|--------|-------------|---------|
| `AWS_DEPLOY_ROLE_ARN` | IAM role ARN for OIDC authentication | `arn:aws:iam::123456789012:role/github-deploy-role` |
| `AWS_ACCOUNT_ID` | AWS account ID (12-digit) | `123456789012` |
| `AWS_REGION` | AWS region for deployment | `us-east-1` |
| `HOSTED_ZONE_ID` | Route53 hosted zone ID | `Z1ABCDEFGHIJKL` |
| `ATHENA_OUTPUT_LOCATION` | S3 URI for Athena query results | `s3://my-athena-results/` |

### Setting up OIDC (recommended — no static keys)

Create an IAM OIDC provider for GitHub Actions:
```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

Create an IAM role with a trust policy allowing your repository:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::ACCOUNT_ID:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {
        "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
      },
      "StringLike": {
        "token.actions.githubusercontent.com:sub": "repo:sjw787/argus:*"
      }
    }
  }]
}
```

### Triggering a deploy

- **Automatic**: push to `main` branch
- **Manual**: Actions tab → "Deploy Argus for Athena" → "Run workflow" → select environment

### Destroy (dev only)

Actions tab → "Destroy Argus for Athena" → "Run workflow" → select `dev` environment → type `destroy` to confirm.

> ⚠️ `prod` is excluded from the destroy workflow intentionally.

---

## Configuring Auth Mode

The `auth_mode` Terraform variable controls authentication:

| Mode | Description |
|------|-------------|
| `none` | No authentication — open access |
| `cognito` | AWS Cognito hosted UI with user pool |

Set via Terraform variable:
```bash
# Manual deploy
terraform apply -var="auth_mode=cognito" ...

# GitHub Actions — add to the terraform apply step in deploy.yml:
-var="auth_mode=cognito"
```

When `auth_mode=cognito`, the `cognito_user_pool_id`, `cognito_client_id`, and `cognito_domain` outputs are populated.

---

## Updating After Code Changes

### Backend only (no infra changes)

```bash
# Build and push new image
./deploy/build.sh prod us-east-1

# Update Lambda to use new image (Terraform handles this)
./deploy/deploy.sh prod Z1ABCDEFGHIJKL s3://results/ <new-image-uri>
```

### Frontend only

```bash
cd frontend && npm run build -- --outDir dist && cd ..

S3_BUCKET=$(terraform -chdir=infra output -raw s3_bucket_name)
CF_ID=$(terraform -chdir=infra output -raw cloudfront_distribution_id)

aws s3 sync frontend/dist/ "s3://${S3_BUCKET}/" \
  --delete --cache-control "max-age=31536000,immutable" --exclude "index.html"
aws s3 cp frontend/dist/index.html "s3://${S3_BUCKET}/index.html" \
  --cache-control "no-cache,no-store,must-revalidate"
aws cloudfront create-invalidation --distribution-id "${CF_ID}" --paths "/*"
```

---

## Viewing Lambda Logs

```bash
# Tail live logs
aws logs tail /aws/lambda/argus-for-athena-prod --follow

# Last 100 lines
aws logs tail /aws/lambda/argus-for-athena-prod --since 1h

# Or via Lambda function name output
FUNCTION=$(terraform -chdir=infra output -raw lambda_function_name)
aws logs tail "/aws/lambda/${FUNCTION}" --follow
```

---

## Rollback

### Rollback Lambda to a previous image

```bash
# List available image tags in ECR
aws ecr list-images --repository-name argus-for-athena-prod \
  --query 'imageIds[*].imageTag' --output table

# Update Lambda to a specific image tag
OLD_TAG="abc1234"  # git SHA of the working commit
IMAGE_URI="$(aws ecr describe-repositories \
  --repository-names argus-for-athena-prod \
  --query 'repositories[0].repositoryUri' --output text):${OLD_TAG}"

aws lambda update-function-code \
  --function-name argus-for-athena-prod \
  --image-uri "${IMAGE_URI}"
```

### Rollback frontend

The S3 bucket versioning can be enabled to restore previous frontend assets. Alternatively, check out the previous commit and re-run the frontend sync commands above.

### Rollback via Terraform

```bash
# Revert to a previous image_uri in Terraform state
cd infra
terraform apply -var="image_uri=${OLD_IMAGE_URI}" ...
```

---

## Tear Down Infrastructure

```bash
# Interactive — confirms before destroying
./deploy/destroy.sh prod
```

> ⚠️ This destroys all infrastructure including the database, ECR images, and DNS records.
