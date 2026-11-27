#!/usr/bin/env bash
# Runs the backend test suite in the isolated `resumetest` compose project.
# Extra pytest args: PYTEST_ARGS="-k chat -x" ./run-tests.sh
# Run another command in the test container: RUN_CMD="python -m tests.render_samples /out" ./run-tests.sh
#   (host-visible output lands in backend/tests/_out/)
# Never touches the production compose project (`app`).
set -u
cd "$(dirname "$0")/.." || exit 1

COMPOSE=(docker compose -p resumetest -f docker-compose.test.yml)

cleanup() {
  "${COMPOSE[@]}" down -v --remove-orphans >/dev/null 2>&1
}
trap cleanup EXIT

mkdir -p backend/tests/_out
export PYTEST_ARGS="${PYTEST_ARGS:-}"
export RUN_CMD="${RUN_CMD:-}"
timeout 900 "${COMPOSE[@]}" up --build --abort-on-container-exit --exit-code-from tests
exit $?
