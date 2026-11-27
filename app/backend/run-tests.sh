#!/usr/bin/env bash
# Runs the backend test suite in the isolated `resumetest` compose project.
# Extra pytest args: PYTEST_ARGS="-k chat -x" ./run-tests.sh
# Never touches the production compose project (`app`).
set -u
cd "$(dirname "$0")/.." || exit 1

COMPOSE=(docker compose -p resumetest -f docker-compose.test.yml)

cleanup() {
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1
}
trap cleanup EXIT

export PYTEST_ARGS="${PYTEST_ARGS:-}"
timeout 900 "${COMPOSE[@]}" up --build --abort-on-container-exit --exit-code-from tests
exit $?
