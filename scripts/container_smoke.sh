#!/usr/bin/env bash
# Builds the deployment image, runs it on a loopback port and checks the
# public page, the health endpoint, the non-root user and Docker's healthcheck.
set -euo pipefail

image="${1:-propane-reconciliation-demo:smoke}"
port="${SMOKE_PORT:-18080}"
name="propane-smoke-$$"

docker build --quiet --tag "$image" . >/dev/null
docker run --detach --name "$name" --publish "127.0.0.1:${port}:8080" "$image" >/dev/null
trap 'docker rm --force "$name" >/dev/null' EXIT

status=starting
for _ in $(seq 1 30); do
  status="$(docker inspect --format '{{.State.Health.Status}}' "$name")"
  [ "$status" = healthy ] && break
  sleep 1
done
[ "$status" = healthy ] || { echo "container health: $status" >&2; exit 1; }

curl --fail --silent --show-error --include "http://127.0.0.1:${port}/healthz"
page="$(curl --fail --silent --show-error --include "http://127.0.0.1:${port}/")"
sed -n '1,12p' <<<"$page"
user="$(docker exec "$name" id -u)"
[ "$user" != 0 ] || { echo "container runs as root" >&2; exit 1; }
echo "container: $(docker exec "$name" id) health=${status}"
docker image inspect --format 'image size: {{.Size}} bytes' "$image"
