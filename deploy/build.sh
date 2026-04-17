#!/usr/bin/env bash
set -euo pipefail

# Usage: ./deploy/build.sh [environment] [aws-region] [aws-account-id]
ENVIRONMENT="${1:-prod}"
AWS_REGION="${2:-us-east-1}"
AWS_ACCOUNT_ID="${3:-$(aws sts get-caller-identity --query Account --output text)}"

ECR_REPO="${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com/athena-beaver-${ENVIRONMENT}"
IMAGE_TAG="$(git rev-parse --short HEAD)"

echo "=== Building frontend ==="
# Output to frontend/dist/ for deployment (local dev uses ../src/athena_beaver/api/static via vite config)
cd frontend && npm ci && npm run build -- --outDir dist
cd ..

echo "=== Authenticating with ECR ==="
aws ecr get-login-password --region "${AWS_REGION}" | \
  docker login --username AWS --password-stdin "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"

echo "=== Building Docker image ==="
docker build -f deploy/Dockerfile.backend -t "athena-beaver:${IMAGE_TAG}" .

echo "=== Tagging and pushing ==="
docker tag "athena-beaver:${IMAGE_TAG}" "${ECR_REPO}:${IMAGE_TAG}"
docker tag "athena-beaver:${IMAGE_TAG}" "${ECR_REPO}:latest"
docker push "${ECR_REPO}:${IMAGE_TAG}"
docker push "${ECR_REPO}:latest"

echo "=== Image URI ==="
echo "${ECR_REPO}:${IMAGE_TAG}"
