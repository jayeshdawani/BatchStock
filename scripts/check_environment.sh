#!/usr/bin/env bash
set -euo pipefail

printf 'BatchDock environment check\n'
printf '===========================\n'

if command -v python3 >/dev/null 2>&1; then
  printf '✓ python3: '
  python3 --version
else
  printf '✗ python3 is not installed or not on PATH.\n'
  exit 1
fi

if command -v redis-cli >/dev/null 2>&1; then
  if redis-cli ping >/dev/null 2>&1; then
    printf '✓ redis: PONG received\n'
  else
    printf '! redis-cli is installed, but no local Redis reply was received. Start Redis before running the app.\n'
  fi
else
  printf '! redis-cli is not installed. Install Redis or use Docker.\n'
fi

if command -v docker >/dev/null 2>&1; then
  printf '✓ docker: available as an optional Redis startup method\n'
else
  printf '! docker: not found; this is fine when Redis is installed locally.\n'
fi
