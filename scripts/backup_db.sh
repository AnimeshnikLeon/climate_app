#!/usr/bin/env sh
set -eu

TS="$(date +"%Y%m%d_%H%M%S")"
OUT_DIR="./backups"
OUT_FILE="${OUT_DIR}/climate_service_${TS}.dump"

mkdir -p "${OUT_DIR}"

CONTAINER="climate_db"
DB="${POSTGRES_DB:-climate_service}"
USER="${POSTGRES_USER:-climate_user}"

docker exec -i "${CONTAINER}" pg_dump -U "${USER}" -F c -d "${DB}" > "${OUT_FILE}"

echo "Backup created: ${OUT_FILE}"