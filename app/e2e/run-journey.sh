#!/usr/bin/env bash
# Browser journey against the fake-provider API in the isolated `resumetest` project (profile e2e).
# Usage: app/e2e/run-journey.sh      Always tears the stack down (down -v). Never calls the real API.
set -u
cd "$(dirname "$0")/.." || exit 1   # -> app/

COMPOSE=(docker compose -p resumetest -f docker-compose.test.yml --profile e2e)
cleanup() { "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1; }
trap cleanup EXIT

E2E_API_PORT="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1])')"
export E2E_API_PORT

(cd frontend && timeout 300 npm run build) || exit 1
[ -d e2e/node_modules/playwright ] || (cd e2e && PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 timeout 300 npm install --no-audit --no-fund) || exit 1

timeout 600 "${COMPOSE[@]}" up -d --build api || exit 1
(cd e2e && timeout 600 node journey.spec.mjs)
rc=$?
if [ "$rc" -ne 0 ]; then "${COMPOSE[@]}" logs --tail 60 api 2>&1 | tail -60; fi
exit "$rc"
