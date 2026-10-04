#!/bin/sh
# Run on the VM. Local backups add no separate AWS storage resource.
set -eu
umask 077
cd "$(dirname "$0")"
mkdir -p backups
stamp=$(date -u +%Y%m%dT%H%M%SZ)
db_tmp="backups/db-${stamp}.dump.tmp"
uploads_tmp="backups/uploads-${stamp}.tar.gz.tmp"
trap 'rm -f "$db_tmp" "$uploads_tmp"' EXIT HUP INT TERM
docker compose exec -T db pg_dump -U listmonk -d listmonk -Fc > "$db_tmp"
docker compose exec -T app tar -czf - -C /listmonk uploads > "$uploads_tmp"
mv "$db_tmp" "backups/db-${stamp}.dump"
mv "$uploads_tmp" "backups/uploads-${stamp}.tar.gz"
find backups -type f \( -name 'db-*.dump' -o -name 'uploads-*.tar.gz' \) -mtime +7 -delete
