#!/bin/sh
# Run as root from the uploaded repository on the VM.
set -eu
cd "$(dirname "$0")"
umask 077
mkdir -p secrets
chmod 700 secrets
if [ ! -s secrets/db_password ]; then openssl rand -hex 32 > secrets/db_password; fi
if [ ! -s secrets/admin_password ]; then openssl rand -hex 24 > secrets/admin_password; fi
chmod 444 secrets/db_password secrets/admin_password
if [ ! -f .env ]; then cp .env.example .env; fi
docker compose config --quiet
# NODE_OPTIONS / Go parallelism in the Dockerfile allow a slow build with swap.
docker build --progress=plain -f Dockerfile.fork --build-arg FORK_COMMIT=3f9177a5 -t attribution-listmonk:3f9177a5 ../..
docker compose up -d db app
docker compose ps
# Bring up public HTTPS separately, once the DNS record points to the static IP.
