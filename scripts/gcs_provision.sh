#!/usr/bin/env bash
set -euo pipefail

# Provision GCS bucket settings for pik-artifacts-dev
# Usage:
#   PROJECT_ID=<your-project> REGION=europe-west3 ./scripts/gcs_provision.sh

BUCKET=${BUCKET:-pik-artifacts-dev}
REGION=${REGION:-europe-west3}
LOG_BUCKET=${LOG_BUCKET:-pik-artifacts-logs}

echo "Creating log bucket gs://${LOG_BUCKET} (if not exists)"
gcloud storage buckets create gs://${LOG_BUCKET} --location=${REGION} --uniform-bucket-level-access || true

echo "Updating ${BUCKET}: UBLA, Public Access Prevention, Autoclass"
gsutil uniformbucketlevelaccess set on gs://${BUCKET} || true
gsutil pap set enforced gs://${BUCKET} || true
echo "(Autoclass is already enabled in console; skipping if CLI unsupported)"

echo "Enabling server access logs"
gsutil logging set on -b gs://${LOG_BUCKET} -o access/ gs://${BUCKET}

echo "Enabling versioning"
gsutil versioning set on gs://${BUCKET}

echo "Applying lifecycle rules"
gsutil lifecycle set infra/gcs/pik-artifacts-dev/lifecycle.json gs://${BUCKET}

echo "Applying CORS"
gsutil cors set infra/gcs/pik-artifacts-dev/cors.json gs://${BUCKET}

echo "Done. Current settings:"
gsutil ls -Lb gs://${BUCKET}
