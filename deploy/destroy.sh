#!/usr/bin/env bash
set -euo pipefail

ENVIRONMENT="${1:-prod}"

echo "WARNING: This will destroy ALL Argus for Athena infrastructure for environment: ${ENVIRONMENT}"
echo "Type 'yes' to confirm:"
read -r CONFIRM

if [ "${CONFIRM}" != "yes" ]; then
  echo "Aborted."
  exit 1
fi

cd infra
terraform destroy \
  -var="environment=${ENVIRONMENT}" \
  -auto-approve
