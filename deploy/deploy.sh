#!/usr/bin/env bash
set -euo pipefail

# Usage: ./deploy/deploy.sh [environment] [hosted_zone_id] [output_location] [image_uri]
ENVIRONMENT="${1:-prod}"
HOSTED_ZONE_ID="${2:?hosted_zone_id required}"
OUTPUT_LOCATION="${3:?output_location required}"
IMAGE_URI="${4:?image_uri required (from build.sh output)}"

# Get AWS account/region
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"

echo "=== Running Terraform ==="
cd infra
terraform init -reconfigure
terraform apply \
  -var="environment=${ENVIRONMENT}" \
  -var="aws_region=${AWS_REGION}" \
  -var="hosted_zone_id=${HOSTED_ZONE_ID}" \
  -var="output_location=${OUTPUT_LOCATION}" \
  -var="image_uri=${IMAGE_URI}" \
  -auto-approve

# Get outputs
S3_BUCKET="$(terraform output -raw s3_bucket_name)"
CLOUDFRONT_ID="$(terraform output -raw cloudfront_distribution_id)"
cd ..

echo "=== Syncing frontend to S3 ==="
aws s3 sync frontend/dist/ "s3://${S3_BUCKET}/" \
  --delete \
  --cache-control "max-age=31536000,immutable" \
  --exclude "index.html"

aws s3 cp frontend/dist/index.html "s3://${S3_BUCKET}/index.html" \
  --cache-control "no-cache,no-store,must-revalidate"

echo "=== Invalidating CloudFront cache ==="
aws cloudfront create-invalidation \
  --distribution-id "${CLOUDFRONT_ID}" \
  --paths "/*"

echo "=== Deploy complete! ==="
terraform -chdir=infra output cloudfront_url
