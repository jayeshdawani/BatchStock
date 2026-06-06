#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  printf 'Docker is not installed or not on PATH.\n' >&2
  exit 1
fi

if docker ps -a --format '{{.Names}}' | grep -qx 'batchdock-redis'; then
  docker start batchdock-redis >/dev/null
else
  docker run --name batchdock-redis -p 6379:6379 -d redis:8-alpine >/dev/null
fi

printf 'Redis container is running. Test it with: docker exec -it batchdock-redis redis-cli ping\n'
